#include "ClaudeAPI.h"
#include "core/LogManager.h"
#include "core/PipelineEvent.h"
#include "core/LatencyMetrics.h"
#include "core/MetricsManager.h"
#include "core/TraceManager.h"

#include <QNetworkRequest>
#include <QJsonDocument>
#include <QJsonObject>
#include <QJsonArray>
#include <QJsonParseError>
#include <QRegularExpression>
#include <QUrl>
#include <QDateTime>
#include <QThread>
#include <QSet>
#include <QFile>

namespace {
// LLM LOCK 2026-05-16 — mapping interne uniquement pour le payload HTTP sortant.
// L'identifiant canonique EXO reste "claude-opus-4.7" (config, logs, affichage,
// validation). L'API Anthropic publie ce meme modele sous l'id "claude-opus-4-7"
// (tirets, pas de point). On ne traduit qu'au moment d'ecrire le champ JSON
// "model" envoye a https://api.anthropic.com/v1/messages.
inline QString anthropicWireModelId(const QString &canonical)
{
    if (canonical == QLatin1String("claude-opus-4.7"))
        return QStringLiteral("claude-opus-4-7");
    return canonical; // jamais atteint grace au lock, mais filet de securite
}
} // namespace

// ═══════════════════════════════════════════════════════
//  Construction / Destruction
// ═══════════════════════════════════════════════════════

ClaudeAPI::ClaudeAPI(QObject *parent)
    : QObject(parent)
    , m_networkManager(new QNetworkAccessManager(this))
    , m_timeoutTimer(new QTimer(this))
    , m_retryTimer(new QTimer(this))
    , m_maxTokens(DEFAULT_MAX_TOKENS)
    , m_topP(-1.0)
    , m_topK(-1)
    , m_timeoutMs(DEFAULT_TIMEOUT)
{
    // LLM LOCK 2026-05-16 : modele canonique force des la construction. Aucun
    // appel a setModel(...) ulterieur ne pourra le remplacer par autre chose.
    m_model = QStringLiteral("claude-opus-4.7");
    m_fallbackModel.clear();
    hClaude() << "[LLM] Modèle actif :" << m_model;

    m_timeoutTimer->setSingleShot(true);
    m_retryTimer->setSingleShot(true);

    connect(m_timeoutTimer, &QTimer::timeout,
            this, &ClaudeAPI::onTimeout);
    connect(m_retryTimer, &QTimer::timeout,
            this, &ClaudeAPI::onRetryTimer);

    hClaude() << "ClaudeAPI v4 initialisée — streaming SSE, Function Calling, retry exponentiel";
}

ClaudeAPI::~ClaudeAPI()
{
    cancelCurrentRequest();
    hClaude() << "ClaudeAPI détruite —"
              << m_totalRequests << "requêtes,"
              << m_totalErrors << "erreurs";
}

// ═══════════════════════════════════════════════════════
//  Configuration
// ═══════════════════════════════════════════════════════

void ClaudeAPI::setApiKey(const QString &apiKey)
{
    m_apiKey = apiKey;
    m_requestDirty = true;
    bool wasReady = m_isReady;
    m_isReady = !apiKey.isEmpty();

    if (m_isReady) {
        hClaude() << "Clé API configurée";
    }
    if (wasReady != m_isReady) {
        emit readyChanged();
    }
}

void ClaudeAPI::setModel(const QString &model)
{
    // LLM LOCK 2026-05-16 : seul claude-opus-4.7 est autorise. Toute autre
    // valeur est REFUSEE (pas de substitution silencieuse cote setter -- on
    // emit une erreur explicite via setError pour que l'appelant sache).
    static const QString kCanonicalModel = QStringLiteral("claude-opus-4.7");
    if (model != kCanonicalModel) {
        const QString msg = QStringLiteral(
            "Modèle LLM invalide : claude-opus-4.7 attendu (reçu: %1)").arg(model);
        hClaude() << "[LLM] Refus :" << msg;
        setError(msg);
        // On force quand meme l'etat interne au modele canonique pour que les
        // prochaines requetes partent avec la bonne valeur.
    }
    if (m_model != kCanonicalModel) {
        m_model = kCanonicalModel;
        m_skeletonDirty = true;
        hClaude() << "[LLM] Modèle actif :" << m_model;
        emit modelChanged();
    }
}

void ClaudeAPI::setFallbackModel(const QString &fallbackModel)
{
    // LLM LOCK 2026-05-16 : aucun fallback autorise. On ignore silencieusement
    // toute valeur differente du modele canonique et on loggue le refus.
    static const QString kCanonicalModel = QStringLiteral("claude-opus-4.7");
    if (!fallbackModel.isEmpty() && fallbackModel != kCanonicalModel) {
        hClaude() << "[LLM] Refus : seul claude-opus-4.7 est autorisé (fallback ignoré:"
                  << fallbackModel << ")";
    }
    m_fallbackModel.clear(); // desactive tryFallbackModel
}

// LLM LOCK 2026-05-16 : setTemperature() supprimé — claude-opus-4.7 rejette
// le champ `temperature` (HTTP 400 invalid_request_error). Skeleton omet déjà.

void ClaudeAPI::setMaxTokens(int tokens)
{
    m_maxTokens = qBound(1, tokens, 200000);
    m_skeletonDirty = true;
}

void ClaudeAPI::setTopP(double topP)
{
    m_topP = (topP >= 0.0 && topP <= 1.0) ? topP : -1.0;
    m_skeletonDirty = true;
}

void ClaudeAPI::setTopK(int topK)
{
    m_topK = (topK >= 1) ? topK : -1;
    m_skeletonDirty = true;
}

void ClaudeAPI::setTimeout(int timeoutMs)
{
    m_timeoutMs = qMax(1000, timeoutMs);
}

// ═══════════════════════════════════════════════════════
//  API principale
// ═══════════════════════════════════════════════════════

void ClaudeAPI::sendMessage(const QString &userMessage)
{
    // Compat QML : appel simplifié sans contexte ni outils
    sendMessageFull(userMessage,
                    QStringLiteral("Vous êtes EXO, un assistant domotique français intelligent."),
                    {}, true);
}

void ClaudeAPI::sendMessageFull(const QString &userMessage,
                                const QString &systemPrompt,
                                const QJsonArray &tools,
                                bool stream)
{
    PIPELINE_EVENT(PipelineModule::Claude, EventType::RequestStarted,
                   {{"message_length", userMessage.length()},
                    {"tools_count", tools.size()},
                    {"stream", stream},
                    {"model", m_model}});
    PIPELINE_STATE(PipelineModule::Claude, ModuleState::Processing);

    MetricsManager::instance()->increment(QStringLiteral("claude.requests"));
    m_currentTraceId = TraceManager::instance()->startTrace(QStringLiteral("claude.request"));

    if (!m_isReady || m_apiKey.isEmpty()) {
        setError(QStringLiteral("API Claude non configurée — clé manquante"));
        return;
    }

    if (!checkRateLimit()) {
        setError(QStringLiteral("Rate limit interne atteint — réessayez dans quelques secondes"));
        return;
    }

    // Annuler toute requête en cours
    if (m_currentReply) {
        cancelCurrentRequest();
    }

    // Stocker pour tool_result et retry
    m_pendingSystemPrompt = systemPrompt;

    // v26.2 Latency: filter tools based on detected intent
    QJsonArray filteredTools = tools.isEmpty() ? tools : filterToolsForMessage(userMessage, tools);
    m_pendingTools = filteredTools;
    m_pendingStream = stream;

    // Ajouter le message utilisateur à l'historique
    QJsonObject userMsg;
    userMsg[QStringLiteral("role")] = QStringLiteral("user");
    userMsg[QStringLiteral("content")] = userMessage;
    m_conversationHistory.append(userMsg);

    // Construire et envoyer le payload
    QJsonObject payload = buildPayload(userMessage, systemPrompt, filteredTools, stream);
    QJsonDocument doc(payload);
    QByteArray payloadBytes = doc.toJson(QJsonDocument::Compact);

    resetRetryState();
    m_lastPayload = payloadBytes;
    m_lastStreamFlag = stream;

    startRequest(payloadBytes, stream);
}

void ClaudeAPI::sendToolResult(const QString &toolUseId,
                               const QJsonObject &result)
{
    hClaude() << "Envoi tool_result pour" << toolUseId;

    // Reconstruire le message assistant avec les content blocks précédents
    QJsonArray assistantContent;
    for (const auto &block : m_contentBlocks) {
        QJsonObject obj;
        if (block.type == QLatin1String("text") && !block.text.isEmpty()) {
            obj[QStringLiteral("type")] = QStringLiteral("text");
            obj[QStringLiteral("text")] = block.text;
            assistantContent.append(obj);
        } else if (block.type == QLatin1String("tool_use")) {
            obj[QStringLiteral("type")] = QStringLiteral("tool_use");
            obj[QStringLiteral("id")] = block.toolUseId;
            obj[QStringLiteral("name")] = block.toolName;
            // Parser le JSON accumulé
            QJsonParseError err;
            QJsonDocument inputDoc = QJsonDocument::fromJson(
                block.toolInputJson.toUtf8(), &err);
            if (err.error == QJsonParseError::NoError) {
                obj[QStringLiteral("input")] = inputDoc.object();
            } else {
                obj[QStringLiteral("input")] = QJsonObject();
            }
            assistantContent.append(obj);
        }
    }

    // Ajouter le message assistant à l'historique
    QJsonObject assistantMsg;
    assistantMsg[QStringLiteral("role")] = QStringLiteral("assistant");
    assistantMsg[QStringLiteral("content")] = assistantContent;
    m_conversationHistory.append(assistantMsg);

    // Ajouter le tool_result à l'historique
    QJsonArray toolResultContent;
    QJsonObject toolResultBlock;
    toolResultBlock[QStringLiteral("type")] = QStringLiteral("tool_result");
    toolResultBlock[QStringLiteral("tool_use_id")] = toolUseId;

    // Sérialiser le résultat comme texte
    QJsonDocument resultDoc(result);
    toolResultBlock[QStringLiteral("content")] = QString::fromUtf8(
        resultDoc.toJson(QJsonDocument::Compact));
    toolResultContent.append(toolResultBlock);

    QJsonObject userToolMsg;
    userToolMsg[QStringLiteral("role")] = QStringLiteral("user");
    userToolMsg[QStringLiteral("content")] = toolResultContent;
    m_conversationHistory.append(userToolMsg);

    // v26.2 Latency: use pre-built skeleton (strips top_p, top_k, empty fields)
    if (m_skeletonDirty)
        rebuildSkeleton();
    QJsonObject payload = m_payloadSkeleton;

    if (!m_pendingSystemPrompt.isEmpty())
        payload[QStringLiteral("system")] = m_pendingSystemPrompt;

    // v26.1 Latency: trim history for tool_result too
    QJsonArray trimmedHistory = m_conversationHistory;
    if (trimmedHistory.size() > MAX_HISTORY_TURNS) {
        QJsonArray trimmed;
        const int start = trimmedHistory.size() - MAX_HISTORY_TURNS;
        for (int i = start; i < trimmedHistory.size(); ++i)
            trimmed.append(trimmedHistory[i]);
        trimmedHistory = trimmed;
    }
    payload[QStringLiteral("messages")] = trimmedHistory;

    if (!m_pendingTools.isEmpty())
        payload[QStringLiteral("tools")] = m_pendingTools;

    payload[QStringLiteral("stream")] = m_pendingStream;

    QJsonDocument doc(payload);
    QByteArray payloadBytes = doc.toJson(QJsonDocument::Compact);

    resetRetryState();
    m_lastPayload = payloadBytes;
    m_lastStreamFlag = m_pendingStream;

    startRequest(payloadBytes, m_pendingStream);
}

void ClaudeAPI::cancelCurrentRequest()
{
    m_timeoutTimer->stop();
    m_retryTimer->stop();

    if (m_currentReply) {
        m_currentReply->blockSignals(true);
        m_currentReply->abort();
        m_currentReply->deleteLater();
        m_currentReply = nullptr;
    }

    setStreaming(false);
    hClaude() << "Requête annulée";
}

void ClaudeAPI::clearConversationHistory()
{
    m_conversationHistory = QJsonArray();
    hClaude() << "Historique conversation effacé";
}

int ClaudeAPI::conversationTurnCount() const
{
    return m_conversationHistory.size();
}

// ═══════════════════════════════════════════════════════
//  Construction du payload JSON
// ═══════════════════════════════════════════════════════

QJsonObject ClaudeAPI::buildPayload(const QString &userMessage,
                                    const QString &systemPrompt,
                                    const QJsonArray &tools,
                                    bool stream) const
{
    Q_UNUSED(userMessage) // déjà dans m_conversationHistory

    // v26.2 Latency: use pre-built skeleton (model, max_tokens, temperature)
    if (m_skeletonDirty)
        rebuildSkeleton();
    QJsonObject payload = m_payloadSkeleton;

    // System prompt (top-level dans Claude Messages v1)
    if (!systemPrompt.isEmpty())
        payload[QStringLiteral("system")] = systemPrompt;

    // v26.1 Latency: trim history to MAX_HISTORY_TURNS to reduce payload size
    // Keep the last N messages to stay within ~4KB payload budget
    QJsonArray trimmedHistory = m_conversationHistory;
    if (trimmedHistory.size() > MAX_HISTORY_TURNS) {
        QJsonArray trimmed;
        const int start = trimmedHistory.size() - MAX_HISTORY_TURNS;
        for (int i = start; i < trimmedHistory.size(); ++i)
            trimmed.append(trimmedHistory[i]);
        trimmedHistory = trimmed;
    }
    payload[QStringLiteral("messages")] = trimmedHistory;

    // Outils Function Calling
    if (!tools.isEmpty())
        payload[QStringLiteral("tools")] = tools;

    // Streaming
    if (stream)
        payload[QStringLiteral("stream")] = true;

    return payload;
}

QNetworkRequest ClaudeAPI::buildHttpRequest() const
{
    // v26.2 Latency: cache the request — only rebuild when API key changes
    if (m_requestDirty) {
        m_cachedRequest = QNetworkRequest();
        m_cachedRequest.setUrl(QUrl(QLatin1String(API_URL)));
        m_cachedRequest.setHeader(QNetworkRequest::ContentTypeHeader,
                                  QStringLiteral("application/json"));
        m_cachedRequest.setRawHeader("x-api-key", m_apiKey.toUtf8());
        m_cachedRequest.setRawHeader("anthropic-version", API_VERSION);
        m_requestDirty = false;
    }
    return m_cachedRequest;
}

// ═══════════════════════════════════════════════════════
//  Lancement de requête
// ═══════════════════════════════════════════════════════

void ClaudeAPI::startRequest(const QByteArray &payload, bool stream)
{
    ++m_totalRequests;
    m_requestTimestamps.append(QDateTime::currentMSecsSinceEpoch());

    LatencyMetrics::instance()->markLlmRequest();

    // Nettoyer l'ancienne reply si elle existe encore
    // (ex: sendToolResult pendant que la 1ère requête est encore ouverte)
    if (m_currentReply) {
        m_currentReply->blockSignals(true);
        m_currentReply->abort();
        m_currentReply->deleteLater();
        m_currentReply = nullptr;
    }

    // Reset des accumulateurs streaming
    m_sseBuffer.clear();
    m_currentEventType.clear();
    m_accumulatedText.clear();
    m_sentenceBuffer.clear();
    m_contentBlocks.clear();
    m_currentBlockIdx = -1;

    QNetworkRequest request = buildHttpRequest();
    m_currentReply = m_networkManager->post(request, payload);

    if (stream) {
        setStreaming(true);
        // Connexion streaming : lire les chunks progressivement
        connect(m_currentReply, &QIODevice::readyRead,
                this, &ClaudeAPI::onStreamDataReady);
    }

    connect(m_currentReply, &QNetworkReply::finished,
            this, &ClaudeAPI::onReplyFinished);
    connect(m_currentReply, &QNetworkReply::errorOccurred,
            this, &ClaudeAPI::onNetworkError);

    m_timeoutTimer->start(m_timeoutMs);
    emit requestStarted();

    hClaude() << "Requête envoyée —"
              << (stream ? "streaming" : "sync")
              << "— modèle:" << m_model
              << "— payload:" << (payload.size() / 1024) << "KB";

    // DEBUG LLM LOCK 2026-05-16 : dump systematique du payload sortant pour
    // pouvoir le rejouer via curl en cas de refus serveur (HTTP 4xx).
    QFile dumpReq(QStringLiteral("D:/EXO/logs/claude_last_request.json"));
    if (dumpReq.open(QIODevice::WriteOnly | QIODevice::Truncate)) {
        dumpReq.write(payload);
        dumpReq.close();
    }
}

// ═══════════════════════════════════════════════════════
//  Streaming SSE
// ═══════════════════════════════════════════════════════

void ClaudeAPI::onStreamDataReady()
{
    if (!m_currentReply) {
        hWarning(exoClaude) << "onStreamDataReady: m_currentReply est nullptr";
        return;
    }

    // Restart timeout à chaque chunk reçu
    m_timeoutTimer->start(m_timeoutMs);

    QByteArray newData = m_currentReply->readAll();
    if (newData.isEmpty()) return;
    processStreamChunk(newData);
}

void ClaudeAPI::processStreamChunk(const QByteArray &chunk)
{
    m_sseBuffer.append(chunk);

    // Découper en lignes SSE (séparées par \n)
    while (true) {
        int nlPos = m_sseBuffer.indexOf('\n');
        if (nlPos < 0) break;

        QByteArray lineBytes = m_sseBuffer.left(nlPos);
        m_sseBuffer.remove(0, nlPos + 1);

        // Supprimer \r éventuel
        if (lineBytes.endsWith('\r'))
            lineBytes.chop(1);

        // Perf: garde QByteArray, évite QString::fromUtf8 sur chaque ligne
        // (la majorité des lignes sont des deltas traités par le fast-path,
        // qui réopère sur les octets bruts).
        processSSELine(lineBytes);
    }
}

void ClaudeAPI::processSSELine(const QByteArray &line)
{
    // Ligne vide = fin d'un événement SSE (pas d'action ici,
    // on traite les données au fur et à mesure)
    if (line.isEmpty()) {
        m_currentEventType.clear();
        return;
    }

    // "event: xxx"
    if (line.startsWith("event: ")) {
        m_currentEventType = QString::fromUtf8(line.mid(7)).trimmed();
        return;
    }

    // "data: {...}"
    if (line.startsWith("data: ")) {
        // Perf P0-1: fast-path pour content_block_delta/text_delta — ~85%
        // des chunks SSE en streaming. Évite QJsonDocument::fromJson +
        // QJsonObject (~2–5 ms par chunk × ~50 chunks = 100–500 ms/réponse).
        const QByteArray dataBytes = line.mid(6);
        if (tryFastTextDelta(dataBytes))
            return;

        QJsonParseError err;
        QJsonDocument doc = QJsonDocument::fromJson(dataBytes, &err);

        if (err.error != QJsonParseError::NoError) {
            // Pas forcément une erreur — certains événements n'ont pas de JSON
            return;
        }

        processSSEEvent(m_currentEventType, doc.object());
    }
}

// ─────────────────────────────────────────────────────
//  Fast-path : extraction directe d'un content_block_delta
//  text_delta sans parser le JSON complet.
//
//  Forme attendue (générée par l'API Anthropic) :
//  {"type":"content_block_delta","index":N,
//   "delta":{"type":"text_delta","text":"..."}}
//
//  Toute déviation (input_json_delta, champs additionnels,
//  réordonnancement) → renvoie false → slow path JSON complet.
// ─────────────────────────────────────────────────────
bool ClaudeAPI::tryFastTextDelta(const QByteArray &data)
{
    static const QByteArray CBD_PREFIX =
        QByteArrayLiteral("{\"type\":\"content_block_delta\"");
    static const QByteArray DELTA_TEXT_PREFIX =
        QByteArrayLiteral("\"delta\":{\"type\":\"text_delta\",\"text\":\"");

    if (!data.startsWith(CBD_PREFIX))
        return false;

    // index
    int idxPos = data.indexOf("\"index\":", CBD_PREFIX.size());
    if (idxPos < 0) return false;
    int p = idxPos + 8;
    int idxEnd = data.indexOf(',', p);
    if (idxEnd < 0) return false;
    bool ok = false;
    int index = QByteArray::fromRawData(data.constData() + p, idxEnd - p)
                    .trimmed().toInt(&ok);
    if (!ok || index < 0 || index > 100) return false;

    // delta:{type:text_delta,text:"..."
    int dpos = data.indexOf(DELTA_TEXT_PREFIX, idxEnd);
    if (dpos < 0) return false;            // pas un text_delta
    p = dpos + DELTA_TEXT_PREFIX.size();

    const char *d = data.constData();
    const int n = data.size();

    QByteArray buf;
    buf.reserve(qMax(16, n - p));

    while (p < n) {
        unsigned char c = static_cast<unsigned char>(d[p]);
        if (c == '"') break;                // fin de la string text
        if (c == '\\') {
            if (p + 1 >= n) return false;
            char e = d[p + 1];
            switch (e) {
                case '"':  buf.append('"');  p += 2; break;
                case '\\': buf.append('\\'); p += 2; break;
                case '/':  buf.append('/');  p += 2; break;
                case 'b':  buf.append('\b'); p += 2; break;
                case 'f':  buf.append('\f'); p += 2; break;
                case 'n':  buf.append('\n'); p += 2; break;
                case 'r':  buf.append('\r'); p += 2; break;
                case 't':  buf.append('\t'); p += 2; break;
                case 'u': {
                    if (p + 6 > n) return false;
                    bool uok = false;
                    uint cp = QByteArray::fromRawData(d + p + 2, 4)
                                  .toUInt(&uok, 16);
                    if (!uok) return false;
                    p += 6;
                    // Paire de surrogates UTF-16
                    if (cp >= 0xD800 && cp <= 0xDBFF) {
                        if (p + 6 > n || d[p] != '\\' || d[p + 1] != 'u')
                            return false;
                        bool uok2 = false;
                        uint cp2 = QByteArray::fromRawData(d + p + 2, 4)
                                       .toUInt(&uok2, 16);
                        if (!uok2 || cp2 < 0xDC00 || cp2 > 0xDFFF)
                            return false;
                        cp = 0x10000 + ((cp - 0xD800) << 10) + (cp2 - 0xDC00);
                        p += 6;
                    } else if (cp >= 0xDC00 && cp <= 0xDFFF) {
                        return false;       // surrogate bas isolé
                    }
                    // Encodage UTF-8
                    if (cp < 0x80) {
                        buf.append(static_cast<char>(cp));
                    } else if (cp < 0x800) {
                        buf.append(static_cast<char>(0xC0 | (cp >> 6)));
                        buf.append(static_cast<char>(0x80 | (cp & 0x3F)));
                    } else if (cp < 0x10000) {
                        buf.append(static_cast<char>(0xE0 | (cp >> 12)));
                        buf.append(static_cast<char>(0x80 | ((cp >> 6) & 0x3F)));
                        buf.append(static_cast<char>(0x80 | (cp & 0x3F)));
                    } else {
                        buf.append(static_cast<char>(0xF0 | (cp >> 18)));
                        buf.append(static_cast<char>(0x80 | ((cp >> 12) & 0x3F)));
                        buf.append(static_cast<char>(0x80 | ((cp >> 6) & 0x3F)));
                        buf.append(static_cast<char>(0x80 | (cp & 0x3F)));
                    }
                    break;
                }
                default:
                    return false;           // séquence d'échappement inconnue
            }
        } else if (c < 0x20) {
            return false;                   // caractère de contrôle brut illégal
        } else {
            buf.append(static_cast<char>(c));
            ++p;
        }
    }

    if (p >= n) return false;               // string non terminée

    // Suffixe strict : `"` puis `}` (fin delta) puis `}` (fin envelope)
    if (p + 3 > n) return false;
    if (d[p] != '"' || d[p + 1] != '}' || d[p + 2] != '}') return false;

    QString text = QString::fromUtf8(buf);
    applyTextDelta(index, text);
    return true;
}

void ClaudeAPI::applyTextDelta(int index, const QString &text)
{
    if (index < 0 || index >= m_contentBlocks.size()) return;

    ContentBlock &block = m_contentBlocks[index];
    block.text += text;
    m_accumulatedText += text;
    m_sentenceBuffer += text;

    // First token event
    if (m_accumulatedText.length() == text.length()) {
        LatencyMetrics::instance()->markLlmFirstToken();
        PIPELINE_EVENT(PipelineModule::Claude, EventType::FirstToken,
                       {{"token", text.left(20)}});
    }

    // Émettre le token en temps réel
    emit partialResponse(text);

    // Sentence splitting : émettre les phrases complètes pour TTS
    trySplitSentences();
}

void ClaudeAPI::processSSEEvent(const QString &eventType,
                                const QJsonObject &data)
{
    QString type = data[QStringLiteral("type")].toString();

    if (type == QLatin1String("message_start")) {
        // Début du message — rien de spécial
        return;
    }

    if (type == QLatin1String("content_block_start")) {
        handleContentBlockStart(data);
        return;
    }

    if (type == QLatin1String("content_block_delta")) {
        handleContentBlockDelta(data);
        return;
    }

    if (type == QLatin1String("content_block_stop")) {
        handleContentBlockStop(data);
        return;
    }

    if (type == QLatin1String("message_delta")) {
        handleMessageDelta(data);
        return;
    }

    if (type == QLatin1String("message_stop")) {
        handleMessageStop();
        return;
    }

    if (type == QLatin1String("ping")) {
        return; // keepalive
    }

    if (type == QLatin1String("error")) {
        QJsonObject errObj = data[QStringLiteral("error")].toObject();
        QString errMsg = errObj[QStringLiteral("message")].toString();
        setError(QStringLiteral("Erreur streaming Claude: ") + errMsg);
        return;
    }

    Q_UNUSED(eventType)
}

void ClaudeAPI::handleContentBlockStart(const QJsonObject &data)
{
    int index = data[QStringLiteral("index")].toInt();
    QJsonObject blockObj = data[QStringLiteral("content_block")].toObject();
    QString blockType = blockObj[QStringLiteral("type")].toString();

    // Guard against unbounded growth from malformed index
    if (index < 0 || index > 100) {
        hWarning(exoClaude) << "handleContentBlockStart: index hors limites:" << index;
        return;
    }

    ContentBlock block;
    block.type = blockType;

    if (blockType == QLatin1String("tool_use")) {
        block.toolUseId = blockObj[QStringLiteral("id")].toString();
        block.toolName = blockObj[QStringLiteral("name")].toString();
        hClaude() << "Utilisation d'outil détectée :" << block.toolName
                  << "— id:" << block.toolUseId;
    }

    // S'assurer que la liste est assez grande
    while (m_contentBlocks.size() <= index) {
        m_contentBlocks.append(ContentBlock());
    }
    m_contentBlocks[index] = block;
    m_currentBlockIdx = index;
}

void ClaudeAPI::handleContentBlockDelta(const QJsonObject &data)
{
    int index = data[QStringLiteral("index")].toInt();
    QJsonObject delta = data[QStringLiteral("delta")].toObject();
    QString deltaType = delta[QStringLiteral("type")].toString();

    if (index < 0 || index >= m_contentBlocks.size()) return;

    ContentBlock &block = m_contentBlocks[index];

    if (deltaType == QLatin1String("text_delta")) {
        // Slow-path text_delta — mutualise la logique avec le fast-path.
        applyTextDelta(index, delta[QStringLiteral("text")].toString());

    } else if (deltaType == QLatin1String("input_json_delta")) {
        // Accumulation progressive du JSON pour tool_use
        QString partialJson = delta[QStringLiteral("partial_json")].toString();
        block.toolInputJson += partialJson;
    }
}

void ClaudeAPI::handleContentBlockStop(const QJsonObject &data)
{
    int index = data[QStringLiteral("index")].toInt();
    if (index < 0 || index >= m_contentBlocks.size()) return;

    const ContentBlock &block = m_contentBlocks[index];

    if (block.type == QLatin1String("tool_use")) {
        // Parser le JSON complet et émettre le signal
        QJsonParseError err;
        QJsonDocument doc = QJsonDocument::fromJson(
            block.toolInputJson.toUtf8(), &err);

        QJsonObject args;
        if (err.error == QJsonParseError::NoError) {
            args = doc.object();
        } else {
            hWarning(exoClaude) << "JSON tool_use invalide:"
                                  << err.errorString();
        }

        hClaude() << "Appel d'outil complet :" << block.toolName
                  << "— args:" << QString::fromUtf8(
                         QJsonDocument(args).toJson(QJsonDocument::Compact));

        emit toolCallDetected(block.toolUseId, block.toolName, args);
        PIPELINE_EVENT(PipelineModule::Claude, EventType::ToolCall,
                       {{"tool", block.toolName}, {"id", block.toolUseId}});
    }
}

void ClaudeAPI::handleMessageDelta(const QJsonObject &data)
{
    QJsonObject delta = data[QStringLiteral("delta")].toObject();
    QString stopReason = delta[QStringLiteral("stop_reason")].toString();

    if (!stopReason.isEmpty()) {
        hClaude() << "Raison d'arrêt :" << stopReason;
    }
}

void ClaudeAPI::handleMessageStop()
{
    hClaude() << "Message streaming terminé —"
              << m_accumulatedText.length() << "caractères";

    setStreaming(false);
    LatencyMetrics::instance()->markLlmComplete();

    MetricsManager::instance()->increment(QStringLiteral("claude.responses_completed"));
    MetricsManager::instance()->recordValue(QStringLiteral("claude.response_length"),
                                            m_accumulatedText.length());
    if (!m_currentTraceId.isEmpty()) {
        TraceManager::instance()->endSpan(m_currentTraceId);
        m_currentTraceId.clear();
    }

    // Flush remaining sentence buffer for TTS
    flushSentenceBuffer();

    // Si du texte a été accumulé, émettre la réponse finale
    if (!m_accumulatedText.isEmpty()) {
        // Ajouter la réponse assistant à l'historique (si pas de tool call)
        bool hasToolCalls = false;
        for (const auto &block : m_contentBlocks) {
            if (block.type == QLatin1String("tool_use")) {
                hasToolCalls = true;
                break;
            }
        }

        if (!hasToolCalls) {
            QJsonObject assistantMsg;
            assistantMsg[QStringLiteral("role")] = QStringLiteral("assistant");
            assistantMsg[QStringLiteral("content")] = m_accumulatedText;
            m_conversationHistory.append(assistantMsg);
        }

        emit finalResponse(m_accumulatedText);
        PIPELINE_EVENT(PipelineModule::Claude, EventType::FinalResponse,
                       {{"length", m_accumulatedText.length()}});
        PIPELINE_STATE(PipelineModule::Claude, ModuleState::Idle);
        emit responseReceived(m_accumulatedText); // compat QML
    }
}

// ═══════════════════════════════════════════════════════
//  Sentence splitting — émet sentenceReady() dès qu'une
//  phrase complète est détectée (. ! ? \n suivi d'espace)
// ═══════════════════════════════════════════════════════

void ClaudeAPI::trySplitSentences()
{
    // Chercher la dernière fin de phrase (.!?\n) suivie d'un espace ou fin
    // On garde au minimum 2 caractères après le délimiteur pour éviter
    // de couper "M. Dupont" ou "3.14"
    static const QRegularExpression sentenceEnd(
        QStringLiteral("(?<=[.!?\\n])\\s"));

    int lastSplit = -1;
    auto it = sentenceEnd.globalMatch(m_sentenceBuffer);
    while (it.hasNext()) {
        auto match = it.next();
        lastSplit = match.capturedStart();
    }

    // Fallback: split on ", " when buffer is long (reduces TTS first-chunk latency)
    if (lastSplit < 0 && m_sentenceBuffer.size() > 50) {
        static const QRegularExpression commaBreak(
            QStringLiteral(",\\s"));
        auto cit = commaBreak.globalMatch(m_sentenceBuffer);
        while (cit.hasNext()) {
            auto match = cit.next();
            // Only split if the left part is substantial (>30 chars)
            if (match.capturedEnd() > 30)
                lastSplit = match.capturedEnd();
        }
    }

    if (lastSplit < 0) return;

    // Extraire la phrase complète (tout avant le dernier split + le délimiteur)
    QString sentence = m_sentenceBuffer.left(lastSplit).trimmed();
    // Strip only leading whitespace (the split-point space) — preserve trailing
    // to avoid merging tokens (e.g. "fait " + "0°C" → "fait0°C")
    m_sentenceBuffer = m_sentenceBuffer.mid(lastSplit);
    int i = 0;
    while (i < m_sentenceBuffer.size() && m_sentenceBuffer.at(i).isSpace()) ++i;
    if (i > 0) m_sentenceBuffer = m_sentenceBuffer.mid(i);

    if (!sentence.isEmpty()) {
        hClaude() << "Phrase prête (streaming) :" << sentence.left(60);
        PIPELINE_EVENT(PipelineModule::Claude, EventType::SentenceReady,
                       {{"length", sentence.length()}, {"preview", sentence.left(60)}});
        emit sentenceReady(sentence);
    }
}

void ClaudeAPI::flushSentenceBuffer()
{
    QString remaining = m_sentenceBuffer.trimmed();
    m_sentenceBuffer.clear();
    if (!remaining.isEmpty()) {
        hClaude() << "Phrase finale (flush) :" << remaining.left(60);
        emit sentenceReady(remaining);
    }
}

// ═══════════════════════════════════════════════════════
//  Réponse non-streaming
// ═══════════════════════════════════════════════════════

void ClaudeAPI::processFullResponse(const QByteArray &data)
{
    QJsonParseError parseError;
    QJsonDocument doc = QJsonDocument::fromJson(data, &parseError);

    if (parseError.error != QJsonParseError::NoError) {
        setError(QStringLiteral("JSON invalide: ") + parseError.errorString());
        return;
    }

    QJsonObject obj = doc.object();

    if (!validateJsonResponse(obj)) return;

    // Vérifier si c'est une erreur API
    if (obj.contains(QStringLiteral("error"))) {
        QJsonObject errObj = obj[QStringLiteral("error")].toObject();
        QString errType = errObj[QStringLiteral("type")].toString();
        QString errMsg = errObj[QStringLiteral("message")].toString();
        setError(QStringLiteral("Erreur Claude [%1]: %2").arg(errType, errMsg));
        return;
    }

    QJsonArray content = obj[QStringLiteral("content")].toArray();
    QString fullText;
    bool hasToolCalls = false;

    for (const QJsonValue &val : content) {
        QJsonObject block = val.toObject();
        QString type = block[QStringLiteral("type")].toString();

        if (type == QLatin1String("text")) {
            fullText += block[QStringLiteral("text")].toString();

        } else if (type == QLatin1String("tool_use")) {
            hasToolCalls = true;

            ContentBlock cb;
            cb.type = QStringLiteral("tool_use");
            cb.toolUseId = block[QStringLiteral("id")].toString();
            cb.toolName = block[QStringLiteral("name")].toString();
            cb.toolInputJson = QString::fromUtf8(
                QJsonDocument(block[QStringLiteral("input")].toObject())
                    .toJson(QJsonDocument::Compact));
            m_contentBlocks.append(cb);

            hClaude() << "Appel d'outil (sync) :" << cb.toolName;
            emit toolCallDetected(cb.toolUseId, cb.toolName,
                                  block[QStringLiteral("input")].toObject());
        }
    }

    if (!fullText.isEmpty()) {
        m_accumulatedText = fullText;

        if (!hasToolCalls) {
            QJsonObject assistantMsg;
            assistantMsg[QStringLiteral("role")] = QStringLiteral("assistant");
            assistantMsg[QStringLiteral("content")] = fullText;
            m_conversationHistory.append(assistantMsg);
        }

        emit finalResponse(fullText);
        emit responseReceived(fullText); // compat QML
        hClaude() << "Réponse (sync):" << fullText.left(100) + "...";
    }
}

// ═══════════════════════════════════════════════════════
//  Callbacks réseau
// ═══════════════════════════════════════════════════════

void ClaudeAPI::onReplyFinished()
{
    if (!m_currentReply) return;

    m_timeoutTimer->stop();
    PIPELINE_EVENT(PipelineModule::Claude, EventType::ReplyFinished);
    PIPELINE_STATE(PipelineModule::Claude, ModuleState::Idle);

    int httpStatus = m_currentReply->attribute(
        QNetworkRequest::HttpStatusCodeAttribute).toInt();

    // Si streaming, les données ont déjà été traitées
    if (m_isStreaming || m_lastStreamFlag) {
        // Vérifier erreur HTTP même en streaming
        if (httpStatus != 200 && httpStatus != 0) {
            QByteArray errorData = m_currentReply->readAll();
            handleHttpError(httpStatus, errorData);
        }
        cleanup();
        emit requestFinished();
        return;
    }

    // Mode non-streaming : lire la réponse complète
    QByteArray responseData = m_currentReply->readAll();
    cleanup();

    if (httpStatus == 200) {
        processFullResponse(responseData);
    } else {
        handleHttpError(httpStatus, responseData);
    }

    emit requestFinished();
}

void ClaudeAPI::onNetworkError(QNetworkReply::NetworkError error)
{
    m_timeoutTimer->stop();

    if (error == QNetworkReply::OperationCanceledError) {
        return; // Annulation volontaire
    }

    ++m_totalErrors;
    MetricsManager::instance()->increment(QStringLiteral("claude.errors"));
    PIPELINE_EVENT(PipelineModule::Claude, EventType::NetworkError,
                   {{"error_code", static_cast<int>(error)},
                    {"total_errors", m_totalErrors}});
    PipelineEventBus::instance()->setModuleError(
        PipelineModule::Claude, QStringLiteral("Erreur réseau %1").arg(static_cast<int>(error)));

    // ── Lire HTTP status + body brut pour diagnostiquer (Qt expose souvent
    //    `errorString()` vide alors que le serveur a renvoyé un JSON utile,
    //    p.ex. {"error":{"type":"invalid_request_error","message":"Your credit
    //    balance is too low..."}} en HTTP 400).
    int httpStatus = 0;
    QByteArray body;
    QString anthropicType, anthropicMessage;
    if (m_currentReply) {
        httpStatus = m_currentReply->attribute(
            QNetworkRequest::HttpStatusCodeAttribute).toInt();
        body = m_currentReply->peek(8192); // ne pas consommer pour onReplyFinished
        if (!body.isEmpty()) {
            QJsonParseError pe;
            QJsonDocument doc = QJsonDocument::fromJson(body, &pe);
            if (pe.error == QJsonParseError::NoError && doc.isObject()) {
                QJsonObject errObj = doc.object().value(QStringLiteral("error")).toObject();
                anthropicType    = errObj.value(QStringLiteral("type")).toString();
                anthropicMessage = errObj.value(QStringLiteral("message")).toString();
            }
        }
    }

    // Log diagnostic complet (toujours)
    hClaude() << "Réseau KO — code Qt:" << static_cast<int>(error)
              << "HTTP:" << httpStatus
              << "errorString:" << (m_currentReply ? m_currentReply->errorString() : QString())
              << "body:" << QString::fromUtf8(body.left(512));

    // DEBUG LLM LOCK 2026-05-16 : si HTTP 4xx, dump payload + body bruts pour
    // diagnostiquer le refus Anthropic (souvent schema d'outil invalide).
    if (httpStatus >= 400 && httpStatus < 500) {
        QFile dumpReq(QStringLiteral("D:/EXO/logs/claude_last_request.json"));
        if (dumpReq.open(QIODevice::WriteOnly | QIODevice::Truncate)) {
            dumpReq.write(m_lastPayload);
            dumpReq.close();
        }
        QFile dumpResp(QStringLiteral("D:/EXO/logs/claude_last_response.txt"));
        if (dumpResp.open(QIODevice::WriteOnly | QIODevice::Truncate)) {
            dumpResp.write("HTTP " + QByteArray::number(httpStatus) + "\n");
            dumpResp.write(body);
            dumpResp.close();
        }
        hClaude() << "[LLM-DEBUG] payload+response dumped to D:/EXO/logs/claude_last_*";
    }

    QString errorString;

    // 1) Si Anthropic a renvoyé un message JSON, c'est lui le plus pertinent.
    if (!anthropicMessage.isEmpty()) {
        // Détection des cas critiques pour message TTS dédié
        const QString lowMsg = anthropicMessage.toLower();
        if (lowMsg.contains(QStringLiteral("credit balance"))
            || lowMsg.contains(QStringLiteral("billing"))
            || lowMsg.contains(QStringLiteral("insufficient"))) {
            errorString = QStringLiteral("Crédits Anthropic épuisés. "
                                         "Rechargez votre compte sur console.anthropic.com.");
        } else if (anthropicType == QStringLiteral("authentication_error")
                   || anthropicType == QStringLiteral("permission_error")) {
            errorString = QStringLiteral("Clé API Claude invalide ou expirée.");
        } else if (anthropicType == QStringLiteral("rate_limit_error")) {
            errorString = QStringLiteral("Limite de requêtes Claude atteinte. "
                                         "Réessayez dans un instant.");
        } else if (anthropicType == QStringLiteral("not_found_error")) {
            errorString = QStringLiteral("Modèle Claude introuvable. "
                                         "Vérifiez le nom du modèle.");
        } else {
            errorString = QStringLiteral("Erreur Claude (HTTP %1): %2")
                              .arg(httpStatus).arg(anthropicMessage);
        }
    } else {
        // 2) Sinon, message générique selon le code Qt
        switch (error) {
        case QNetworkReply::ConnectionRefusedError:
            errorString = QStringLiteral("Connexion refusée par l'API Claude");
            break;
        case QNetworkReply::RemoteHostClosedError:
            errorString = QStringLiteral("Connexion fermée par le serveur Claude");
            break;
        case QNetworkReply::HostNotFoundError:
            errorString = QStringLiteral("Serveur Claude introuvable (DNS)");
            break;
        case QNetworkReply::TimeoutError:
            errorString = QStringLiteral("Timeout de connexion Claude");
            break;
        case QNetworkReply::SslHandshakeFailedError:
            errorString = QStringLiteral("Erreur SSL avec l'API Claude");
            break;
        case QNetworkReply::AuthenticationRequiredError:
            errorString = QStringLiteral("Authentification requise — vérifiez la clé API");
            break;
        default:
            errorString = QStringLiteral("Erreur réseau Claude (HTTP %1): %2")
                              .arg(httpStatus)
                              .arg(m_currentReply ? m_currentReply->errorString()
                                                  : QStringLiteral("inconnue"));
        }
    }

    hClaude() << "Erreur réseau:" << errorString;

    // 3) Décision retry : seules les erreurs vraiment transitoires sont retentées.
    //    Surtout PAS pour 400/401/403/404 ou crédit épuisé (échec définitif).
    const bool isClientFatal =
        (httpStatus >= 400 && httpStatus < 500 && httpStatus != 429)
        || anthropicType == QStringLiteral("authentication_error")
        || anthropicType == QStringLiteral("permission_error")
        || anthropicType == QStringLiteral("invalid_request_error")
        || anthropicType == QStringLiteral("not_found_error");

    // Fallback automatique Opus → Sonnet sur 429/404/5xx (avant la décision finale)
    if ((httpStatus == 429 || httpStatus == 404
         || (httpStatus >= 500 && httpStatus < 600))
        && tryFallbackModel(httpStatus)) {
        return; // fallback déclenche un retry interne
    }

    if (!isClientFatal && m_retryCount < MAX_RETRIES) {
        retryWithBackoff();
    } else {
        setError(errorString);
        cleanup();
        emit requestFinished();
    }
}

void ClaudeAPI::onTimeout()
{
    hClaude() << "Timeout atteint (" << m_timeoutMs << "ms)";
    MetricsManager::instance()->increment(QStringLiteral("claude.timeouts"));
    if (m_retryCount < MAX_RETRIES) {
        cancelCurrentRequest();
        retryWithBackoff();
    } else {
        cancelCurrentRequest();
        setError(QStringLiteral("Timeout après %1 tentatives").arg(MAX_RETRIES));
        emit requestFinished();
    }
}

// ═══════════════════════════════════════════════════════
//  Gestion erreurs HTTP
// ═══════════════════════════════════════════════════════

void ClaudeAPI::handleHttpError(int httpStatus, const QByteArray &data)
{
    QString errorMsg = QStringLiteral("Erreur API Claude (HTTP %1)").arg(httpStatus);

    // Tenter de parser le corps d'erreur pour plus de détails
    QJsonParseError parseError;
    QJsonDocument doc = QJsonDocument::fromJson(data, &parseError);

    if (parseError.error == QJsonParseError::NoError) {
        QJsonObject obj = doc.object();
        if (obj.contains(QStringLiteral("error"))) {
            QJsonObject errObj = obj[QStringLiteral("error")].toObject();
            QString errType = errObj[QStringLiteral("type")].toString();
            QString errMessage = errObj[QStringLiteral("message")].toString();
            if (!errMessage.isEmpty()) {
                errorMsg += QStringLiteral(" [%1]: %2").arg(errType, errMessage);
            }
        }
    }

    // Retry pour erreurs transitoires (429, 500, 502, 503, 529)
    bool retryable = (httpStatus == 429 || httpStatus == 500
                      || httpStatus == 502 || httpStatus == 503
                      || httpStatus == 529);

    // Fallback automatique Opus → Sonnet sur erreurs critiques de chargement
    // (429 rate-limit, 404 modèle introuvable, 5xx surcharge serveur).
    if ((httpStatus == 429 || httpStatus == 404
         || (httpStatus >= 500 && httpStatus < 600))
        && tryFallbackModel(httpStatus)) {
        return; // fallback déclenche un retry interne
    }

    if (retryable && m_retryCount < MAX_RETRIES) {
        hClaude() << errorMsg << "— retry possible";
        retryWithBackoff();
    } else {
        setError(errorMsg);
    }
}

// ═══════════════════════════════════════════════════════
//  Robustesse : retry exponentiel
// ═══════════════════════════════════════════════════════

bool ClaudeAPI::tryFallbackModel(int httpStatus)
{
    // LLM LOCK 2026-05-16 : fallback automatique DESACTIVE. claude-opus-4.7
    // est le seul modele autorise -- on ne bascule jamais vers Sonnet/Haiku
    // meme en cas de 429/404/5xx. Le retry exponentiel sur le meme modele
    // reste actif (gere par retryWithBackoff()).
    Q_UNUSED(httpStatus);
    return false;
}
void ClaudeAPI::retryWithBackoff()
{
    ++m_retryCount;

    // Backoff exponentiel : 1s, 2s, 4s
    int delayMs = 1000 * (1 << (m_retryCount - 1));

    hClaude() << "Retry" << m_retryCount << "/" << MAX_RETRIES
              << "— délai:" << delayMs << "ms";

    // Nettoyer la connexion actuelle
    if (m_currentReply) {
        // R3 audit threads : disconnect explicite avant abort() pour éviter
        // le warning Qt "QNetworkReplyImplPrivate::error: Internal problem,
        // this method must only be called once." (re-déclenché par abort()
        // sur un reply déjà en erreur).
        disconnect(m_currentReply, nullptr, this, nullptr);
        m_currentReply->blockSignals(true);
        m_currentReply->abort();
        m_currentReply->deleteLater();
        m_currentReply = nullptr;
    }

    setStreaming(false);
    m_retryTimer->start(delayMs);
}

void ClaudeAPI::onRetryTimer()
{
    hClaude() << "Retry en cours...";
    startRequest(m_lastPayload, m_lastStreamFlag);
}

void ClaudeAPI::resetRetryState()
{
    m_retryCount = 0;
    m_retryTimer->stop();
}

// ═══════════════════════════════════════════════════════
//  Rate limiting
// ═══════════════════════════════════════════════════════

bool ClaudeAPI::checkRateLimit()
{
    qint64 now = QDateTime::currentMSecsSinceEpoch();
    qint64 oneMinuteAgo = now - 60000;

    // Purger les timestamps anciens
    while (!m_requestTimestamps.isEmpty()
           && m_requestTimestamps.first() < oneMinuteAgo) {
        m_requestTimestamps.removeFirst();
    }

    if (m_requestTimestamps.size() >= RATE_LIMIT_PER_MIN) {
        hWarning(exoClaude) << "Rate limit:"
                              << m_requestTimestamps.size()
                              << "requêtes dans la dernière minute";
        return false;
    }

    return true;
}

// ═══════════════════════════════════════════════════════
//  Validation JSON
// ═══════════════════════════════════════════════════════

bool ClaudeAPI::validateJsonResponse(const QJsonObject &obj) const
{
    // Vérifier la structure minimale d'une réponse Claude
    if (obj.isEmpty()) {
        return false;
    }

    // Si c'est une erreur, c'est un JSON valide (traitement en amont)
    if (obj.contains(QStringLiteral("error"))) {
        return true;
    }

    // Réponse normale : doit avoir "content" et "role"
    if (!obj.contains(QStringLiteral("content"))) {
        hWarning(exoClaude) << "Réponse sans champ 'content'";
        return false;
    }

    return true;
}

// ═══════════════════════════════════════════════════════
//  Outils EXO (Function Calling)
// ═══════════════════════════════════════════════════════

QJsonObject ClaudeAPI::buildToolSchema(const QString &name,
                                       const QString &description,
                                       const QJsonObject &inputSchema)
{
    QJsonObject tool;
    tool[QStringLiteral("name")] = name;
    tool[QStringLiteral("description")] = description;
    tool[QStringLiteral("input_schema")] = inputSchema;
    return tool;
}

QJsonArray ClaudeAPI::buildEXOTools()
{
    // v26.1 Latency: cache the tools array (it never changes at runtime)
    static QJsonArray cachedTools;
    static bool cached = false;
    if (cached)
        return cachedTools;

    QJsonArray tools;

    // ── ha_turn_on : allumer une entité HA ──────────
    {
        QJsonObject schema;
        schema[QStringLiteral("type")] = QStringLiteral("object");

        QJsonObject props;
        QJsonObject entityProp;
        entityProp[QStringLiteral("type")] = QStringLiteral("string");
        entityProp[QStringLiteral("description")] =
            QStringLiteral("L'entity_id Home Assistant (ex: light.salon, switch.tv)");
        props[QStringLiteral("entity_id")] = entityProp;
        schema[QStringLiteral("properties")] = props;

        QJsonArray required;
        required.append(QStringLiteral("entity_id"));
        schema[QStringLiteral("required")] = required;

        tools.append(buildToolSchema(
            QStringLiteral("ha_turn_on"),
            QStringLiteral("Allumer une entité Home Assistant (lumière, switch, prise, etc.)"),
            schema));
    }

    // ── ha_turn_off : éteindre une entité HA ────────
    {
        QJsonObject schema;
        schema[QStringLiteral("type")] = QStringLiteral("object");

        QJsonObject props;
        QJsonObject entityProp;
        entityProp[QStringLiteral("type")] = QStringLiteral("string");
        entityProp[QStringLiteral("description")] =
            QStringLiteral("L'entity_id Home Assistant à éteindre");
        props[QStringLiteral("entity_id")] = entityProp;
        schema[QStringLiteral("properties")] = props;

        QJsonArray required;
        required.append(QStringLiteral("entity_id"));
        schema[QStringLiteral("required")] = required;

        tools.append(buildToolSchema(
            QStringLiteral("ha_turn_off"),
            QStringLiteral("Éteindre une entité Home Assistant"),
            schema));
    }

    // ── ha_toggle : basculer une entité ─────────────
    {
        QJsonObject schema;
        schema[QStringLiteral("type")] = QStringLiteral("object");

        QJsonObject props;
        QJsonObject entityProp;
        entityProp[QStringLiteral("type")] = QStringLiteral("string");
        entityProp[QStringLiteral("description")] =
            QStringLiteral("L'entity_id Home Assistant à basculer");
        props[QStringLiteral("entity_id")] = entityProp;
        schema[QStringLiteral("properties")] = props;

        QJsonArray required;
        required.append(QStringLiteral("entity_id"));
        schema[QStringLiteral("required")] = required;

        tools.append(buildToolSchema(
            QStringLiteral("ha_toggle"),
            QStringLiteral("Basculer une entité Home Assistant (on↔off)"),
            schema));
    }

    // ── ha_set_brightness : régler luminosité ───────
    {
        QJsonObject schema;
        schema[QStringLiteral("type")] = QStringLiteral("object");

        QJsonObject props;
        QJsonObject entityProp;
        entityProp[QStringLiteral("type")] = QStringLiteral("string");
        entityProp[QStringLiteral("description")] =
            QStringLiteral("L'entity_id de la lumière");
        props[QStringLiteral("entity_id")] = entityProp;

        QJsonObject brightProp;
        brightProp[QStringLiteral("type")] = QStringLiteral("integer");
        brightProp[QStringLiteral("description")] =
            QStringLiteral("Luminosité entre 0 et 255");
        brightProp[QStringLiteral("minimum")] = 0;
        brightProp[QStringLiteral("maximum")] = 255;
        props[QStringLiteral("brightness")] = brightProp;

        schema[QStringLiteral("properties")] = props;

        QJsonArray required;
        required.append(QStringLiteral("entity_id"));
        required.append(QStringLiteral("brightness"));
        schema[QStringLiteral("required")] = required;

        tools.append(buildToolSchema(
            QStringLiteral("ha_set_brightness"),
            QStringLiteral("Régler la luminosité d'une lumière Home Assistant"),
            schema));
    }

    // ── ha_set_temperature : régler thermostat ──────
    {
        QJsonObject schema;
        schema[QStringLiteral("type")] = QStringLiteral("object");

        QJsonObject props;
        QJsonObject entityProp;
        entityProp[QStringLiteral("type")] = QStringLiteral("string");
        entityProp[QStringLiteral("description")] =
            QStringLiteral("L'entity_id du thermostat");
        props[QStringLiteral("entity_id")] = entityProp;

        QJsonObject tempProp;
        tempProp[QStringLiteral("type")] = QStringLiteral("number");
        tempProp[QStringLiteral("description")] =
            QStringLiteral("Température cible en °C");
        props[QStringLiteral("temperature")] = tempProp;

        schema[QStringLiteral("properties")] = props;

        QJsonArray required;
        required.append(QStringLiteral("entity_id"));
        required.append(QStringLiteral("temperature"));
        schema[QStringLiteral("required")] = required;

        tools.append(buildToolSchema(
            QStringLiteral("ha_set_temperature"),
            QStringLiteral("Régler la température d'un thermostat Home Assistant"),
            schema));
    }

    // ── ha_get_state : lire l'état d'une entité ─────
    {
        QJsonObject schema;
        schema[QStringLiteral("type")] = QStringLiteral("object");

        QJsonObject props;
        QJsonObject entityProp;
        entityProp[QStringLiteral("type")] = QStringLiteral("string");
        entityProp[QStringLiteral("description")] =
            QStringLiteral("L'entity_id dont on veut l'état");
        props[QStringLiteral("entity_id")] = entityProp;
        schema[QStringLiteral("properties")] = props;

        QJsonArray required;
        required.append(QStringLiteral("entity_id"));
        schema[QStringLiteral("required")] = required;

        tools.append(buildToolSchema(
            QStringLiteral("ha_get_state"),
            QStringLiteral("Obtenir l'état actuel d'une entité Home Assistant"),
            schema));
    }

    // ── get_weather : obtenir la météo ──────────────
    {
        QJsonObject schema;
        schema[QStringLiteral("type")] = QStringLiteral("object");

        QJsonObject props;
        QJsonObject cityProp;
        cityProp[QStringLiteral("type")] = QStringLiteral("string");
        cityProp[QStringLiteral("description")] =
            QStringLiteral("Nom de la ville (optionnel, défaut: Paris)");
        props[QStringLiteral("city")] = cityProp;
        schema[QStringLiteral("properties")] = props;

        tools.append(buildToolSchema(
            QStringLiteral("get_weather"),
            QStringLiteral("Obtenir la météo actuelle d'une ville"),
            schema));
    }

    // ── get_datetime : obtenir date et heure ────────
    {
        QJsonObject schema;
        schema[QStringLiteral("type")] = QStringLiteral("object");
        schema[QStringLiteral("properties")] = QJsonObject();
        schema[QStringLiteral("required")] = QJsonArray();

        tools.append(buildToolSchema(
            QStringLiteral("get_datetime"),
            QStringLiteral("Obtenir la date et l'heure actuelles"),
            schema));
    }

    // ── search_web : recherche web ──────────────────
    {
        QJsonObject schema;
        schema[QStringLiteral("type")] = QStringLiteral("object");

        QJsonObject props;
        QJsonObject queryProp;
        queryProp[QStringLiteral("type")] = QStringLiteral("string");
        queryProp[QStringLiteral("description")] =
            QStringLiteral("La requête de recherche web");
        props[QStringLiteral("query")] = queryProp;

        QJsonObject freshProp;
        freshProp[QStringLiteral("type")] = QStringLiteral("string");
        freshProp[QStringLiteral("description")] =
            QStringLiteral("Filtre temporel: day, week, month, year (optionnel)");
        QJsonArray freshEnum;
        freshEnum.append(QStringLiteral("day"));
        freshEnum.append(QStringLiteral("week"));
        freshEnum.append(QStringLiteral("month"));
        freshEnum.append(QStringLiteral("year"));
        freshProp[QStringLiteral("enum")] = freshEnum;
        props[QStringLiteral("freshness")] = freshProp;

        QJsonObject maxProp;
        maxProp[QStringLiteral("type")] = QStringLiteral("integer");
        maxProp[QStringLiteral("description")] =
            QStringLiteral("Nombre max de résultats (défaut: 5, max: 10)");
        maxProp[QStringLiteral("minimum")] = 1;
        maxProp[QStringLiteral("maximum")] = 10;
        props[QStringLiteral("max_results")] = maxProp;

        schema[QStringLiteral("properties")] = props;

        QJsonArray required;
        required.append(QStringLiteral("query"));
        schema[QStringLiteral("required")] = required;

        tools.append(buildToolSchema(
            QStringLiteral("search_web"),
            QStringLiteral("Rechercher des informations sur le web via DuckDuckGo. "
                           "Utiliser pour les questions d'actualité, faits récents, "
                           "ou quand tu as besoin de données à jour."),
            schema));
    }

    // ── get_news : actualités ───────────────────────
    {
        QJsonObject schema;
        schema[QStringLiteral("type")] = QStringLiteral("object");

        QJsonObject props;
        QJsonObject topicProp;
        topicProp[QStringLiteral("type")] = QStringLiteral("string");
        topicProp[QStringLiteral("description")] =
            QStringLiteral("Sujet des actualités: general, tech, science, world");
        QJsonArray topicEnum;
        topicEnum.append(QStringLiteral("general"));
        topicEnum.append(QStringLiteral("tech"));
        topicEnum.append(QStringLiteral("science"));
        topicEnum.append(QStringLiteral("world"));
        topicProp[QStringLiteral("enum")] = topicEnum;
        props[QStringLiteral("topic")] = topicProp;

        QJsonObject regionProp;
        regionProp[QStringLiteral("type")] = QStringLiteral("string");
        regionProp[QStringLiteral("description")] =
            QStringLiteral("Région: fr (français) ou en (anglais). Défaut: fr");
        props[QStringLiteral("region")] = regionProp;

        QJsonObject timeProp;
        timeProp[QStringLiteral("type")] = QStringLiteral("string");
        timeProp[QStringLiteral("description")] =
            QStringLiteral("Période: 24h ou 7d. Défaut: 24h");
        props[QStringLiteral("timeframe")] = timeProp;

        schema[QStringLiteral("properties")] = props;

        tools.append(buildToolSchema(
            QStringLiteral("get_news"),
            QStringLiteral("Obtenir les dernières actualités par sujet et région. "
                           "Utiliser quand l'utilisateur demande les news, l'actu, "
                           "ce qui se passe dans le monde."),
            schema));
    }

    // ── get_summary : encyclopédie Wikipedia ────────
    {
        QJsonObject schema;
        schema[QStringLiteral("type")] = QStringLiteral("object");

        QJsonObject props;
        QJsonObject topicProp;
        topicProp[QStringLiteral("type")] = QStringLiteral("string");
        topicProp[QStringLiteral("description")] =
            QStringLiteral("Le sujet à rechercher sur Wikipedia");
        props[QStringLiteral("topic")] = topicProp;

        QJsonObject langProp;
        langProp[QStringLiteral("type")] = QStringLiteral("string");
        langProp[QStringLiteral("description")] =
            QStringLiteral("Langue: fr ou en. Défaut: fr");
        props[QStringLiteral("lang")] = langProp;

        schema[QStringLiteral("properties")] = props;

        QJsonArray required;
        required.append(QStringLiteral("topic"));
        schema[QStringLiteral("required")] = required;

        tools.append(buildToolSchema(
            QStringLiteral("get_summary"),
            QStringLiteral("Obtenir un résumé encyclopédique depuis Wikipedia. "
                           "Utiliser pour les questions de culture générale, "
                           "histoire, science, biographies, géographie."),
            schema));
    }

    // ── calculate : calculatrice ────────────────────
    {
        QJsonObject schema;
        schema[QStringLiteral("type")] = QStringLiteral("object");

        QJsonObject props;
        QJsonObject exprProp;
        exprProp[QStringLiteral("type")] = QStringLiteral("string");
        exprProp[QStringLiteral("description")] =
            QStringLiteral("Expression mathématique (ex: sqrt(144), 2**10, sin(pi/4))");
        props[QStringLiteral("expression")] = exprProp;

        schema[QStringLiteral("properties")] = props;

        QJsonArray required;
        required.append(QStringLiteral("expression"));
        schema[QStringLiteral("required")] = required;

        tools.append(buildToolSchema(
            QStringLiteral("calculate"),
            QStringLiteral("Évaluer une expression mathématique. Supporte: "
                           "arithmétique, trigonométrie, logarithmes, puissances, factorielles."),
            schema));
    }

    // ── convert : convertisseur d'unités ────────────
    {
        QJsonObject schema;
        schema[QStringLiteral("type")] = QStringLiteral("object");

        QJsonObject props;
        QJsonObject valProp;
        valProp[QStringLiteral("type")] = QStringLiteral("number");
        valProp[QStringLiteral("description")] =
            QStringLiteral("La valeur numérique à convertir");
        props[QStringLiteral("value")] = valProp;

        QJsonObject fromProp;
        fromProp[QStringLiteral("type")] = QStringLiteral("string");
        fromProp[QStringLiteral("description")] =
            QStringLiteral("Unité source (ex: km, lb, °C, l, kwh)");
        props[QStringLiteral("from_unit")] = fromProp;

        QJsonObject toProp;
        toProp[QStringLiteral("type")] = QStringLiteral("string");
        toProp[QStringLiteral("description")] =
            QStringLiteral("Unité cible (ex: mi, kg, °F, gal, j)");
        props[QStringLiteral("to_unit")] = toProp;

        schema[QStringLiteral("properties")] = props;

        QJsonArray required;
        required.append(QStringLiteral("value"));
        required.append(QStringLiteral("from_unit"));
        required.append(QStringLiteral("to_unit"));
        schema[QStringLiteral("required")] = required;

        tools.append(buildToolSchema(
            QStringLiteral("convert"),
            QStringLiteral("Convertir une valeur entre unités. Supporte: "
                           "longueur, masse, vitesse, température, volume, "
                           "surface, temps, données, énergie."),
            schema));
    }

    // ═══════════════════════════════════════════════════
    //  Outils EXO v7 — Intelligence contextuelle + Agent
    // ═══════════════════════════════════════════════════

    // ── remember_info : stocker une information en mémoire ──
    {
        QJsonObject schema;
        schema[QStringLiteral("type")] = QStringLiteral("object");

        QJsonObject props;
        QJsonObject textProp;
        textProp[QStringLiteral("type")] = QStringLiteral("string");
        textProp[QStringLiteral("description")] =
            QStringLiteral("L'information à mémoriser (préférence, fait, souvenir)");
        props[QStringLiteral("text")] = textProp;

        QJsonObject tagsProp;
        tagsProp[QStringLiteral("type")] = QStringLiteral("string");
        tagsProp[QStringLiteral("description")] =
            QStringLiteral("Tags séparés par des virgules (ex: preference,food,alex)");
        props[QStringLiteral("tags")] = tagsProp;

        QJsonObject importanceProp;
        importanceProp[QStringLiteral("type")] = QStringLiteral("number");
        importanceProp[QStringLiteral("description")] =
            QStringLiteral("Importance de 0.0 à 1.0 (défaut: 0.5)");
        importanceProp[QStringLiteral("minimum")] = 0.0;
        importanceProp[QStringLiteral("maximum")] = 1.0;
        props[QStringLiteral("importance")] = importanceProp;

        schema[QStringLiteral("properties")] = props;

        QJsonArray required;
        required.append(QStringLiteral("text"));
        schema[QStringLiteral("required")] = required;

        tools.append(buildToolSchema(
            QStringLiteral("remember_info"),
            QStringLiteral("Mémoriser une information importante sur l'utilisateur "
                           "(préférences, faits personnels, souvenirs). Utiliser quand "
                           "l'utilisateur partage quelque chose à retenir."),
            schema));
    }

    // ── recall_info : rechercher dans la mémoire ────
    {
        QJsonObject schema;
        schema[QStringLiteral("type")] = QStringLiteral("object");

        QJsonObject props;
        QJsonObject queryProp;
        queryProp[QStringLiteral("type")] = QStringLiteral("string");
        queryProp[QStringLiteral("description")] =
            QStringLiteral("La requête pour rechercher dans les souvenirs");
        props[QStringLiteral("query")] = queryProp;

        QJsonObject topKProp;
        topKProp[QStringLiteral("type")] = QStringLiteral("integer");
        topKProp[QStringLiteral("description")] =
            QStringLiteral("Nombre de résultats (défaut: 3, max: 10)");
        topKProp[QStringLiteral("minimum")] = 1;
        topKProp[QStringLiteral("maximum")] = 10;
        props[QStringLiteral("top_k")] = topKProp;

        schema[QStringLiteral("properties")] = props;

        QJsonArray required;
        required.append(QStringLiteral("query"));
        schema[QStringLiteral("required")] = required;

        tools.append(buildToolSchema(
            QStringLiteral("recall_info"),
            QStringLiteral("Rechercher dans la mémoire sémantique. Utiliser quand "
                           "l'utilisateur fait référence à quelque chose de passé ou "
                           "quand tu as besoin de contexte personnalisé."),
            schema));
    }

    // ── get_context : obtenir le contexte actuel ────
    {
        QJsonObject schema;
        schema[QStringLiteral("type")] = QStringLiteral("object");
        schema[QStringLiteral("properties")] = QJsonObject();

        tools.append(buildToolSchema(
            QStringLiteral("get_context"),
            QStringLiteral("Obtenir le contexte actuel (heure, activité probable, "
                           "modules actifs, tâches en cours, interactions récentes). "
                           "Utiliser pour adapter la réponse au moment et à la situation."),
            schema));
    }

    // ── create_plan : créer un plan multi-étapes ────
    {
        QJsonObject schema;
        schema[QStringLiteral("type")] = QStringLiteral("object");

        QJsonObject props;
        QJsonObject goalProp;
        goalProp[QStringLiteral("type")] = QStringLiteral("string");
        goalProp[QStringLiteral("description")] =
            QStringLiteral("L'objectif à atteindre");
        props[QStringLiteral("goal")] = goalProp;

        QJsonObject stepsProp;
        stepsProp[QStringLiteral("type")] = QStringLiteral("array");
        stepsProp[QStringLiteral("description")] =
            QStringLiteral("Liste des étapes [{description, tool, params, depends_on}]");
        QJsonObject stepItemSchema;
        stepItemSchema[QStringLiteral("type")] = QStringLiteral("object");
        QJsonObject stepItemProps;
        QJsonObject descProp;
        descProp[QStringLiteral("type")] = QStringLiteral("string");
        stepItemProps[QStringLiteral("description")] = descProp;
        QJsonObject toolProp;
        toolProp[QStringLiteral("type")] = QStringLiteral("string");
        stepItemProps[QStringLiteral("tool")] = toolProp;
        stepItemSchema[QStringLiteral("properties")] = stepItemProps;
        stepsProp[QStringLiteral("items")] = stepItemSchema;
        props[QStringLiteral("steps")] = stepsProp;

        schema[QStringLiteral("properties")] = props;

        QJsonArray required;
        required.append(QStringLiteral("goal"));
        required.append(QStringLiteral("steps"));
        schema[QStringLiteral("required")] = required;

        tools.append(buildToolSchema(
            QStringLiteral("create_plan"),
            QStringLiteral("Créer un plan multi-étapes pour atteindre un objectif complexe. "
                           "Chaque étape spécifie un outil EXO et ses paramètres. "
                           "Utiliser pour des tâches nécessitant plusieurs actions séquentielles."),
            schema));
    }

    // ── v8: execute_plan : exécuter un plan ─────────
    {
        QJsonObject schema;
        schema[QStringLiteral("type")] = QStringLiteral("object");

        QJsonObject props;
        QJsonObject planIdProp;
        planIdProp[QStringLiteral("type")] = QStringLiteral("string");
        planIdProp[QStringLiteral("description")] =
            QStringLiteral("L'identifiant du plan à exécuter");
        props[QStringLiteral("plan_id")] = planIdProp;

        QJsonObject planProp;
        planProp[QStringLiteral("type")] = QStringLiteral("object");
        planProp[QStringLiteral("description")] =
            QStringLiteral("Le plan complet avec ses étapes");
        props[QStringLiteral("plan")] = planProp;

        schema[QStringLiteral("properties")] = props;
        QJsonArray required;
        required.append(QStringLiteral("plan_id"));
        required.append(QStringLiteral("plan"));
        schema[QStringLiteral("required")] = required;

        tools.append(buildToolSchema(
            QStringLiteral("execute_plan"),
            QStringLiteral("Exécuter un plan multi-étapes créé avec create_plan. "
                           "L'exécution est automatique avec gestion des erreurs et retries."),
            schema));
    }

    // ── v8: verify_result : vérifier un résultat ────
    {
        QJsonObject schema;
        schema[QStringLiteral("type")] = QStringLiteral("object");

        QJsonObject props;
        QJsonObject stepProp;
        stepProp[QStringLiteral("type")] = QStringLiteral("object");
        stepProp[QStringLiteral("description")] =
            QStringLiteral("L'étape dont on vérifie le résultat");
        props[QStringLiteral("step")] = stepProp;

        QJsonObject resultProp;
        resultProp[QStringLiteral("type")] = QStringLiteral("object");
        resultProp[QStringLiteral("description")] =
            QStringLiteral("Le résultat à vérifier");
        props[QStringLiteral("result")] = resultProp;

        QJsonObject goalProp;
        goalProp[QStringLiteral("type")] = QStringLiteral("string");
        goalProp[QStringLiteral("description")] =
            QStringLiteral("L'objectif attendu");
        props[QStringLiteral("goal")] = goalProp;

        schema[QStringLiteral("properties")] = props;
        QJsonArray required;
        required.append(QStringLiteral("step"));
        required.append(QStringLiteral("result"));
        schema[QStringLiteral("required")] = required;

        tools.append(buildToolSchema(
            QStringLiteral("verify_result"),
            QStringLiteral("Vérifier la validité et la cohérence d'un résultat d'exécution."),
            schema));
    }

    // ── v8: summarize_conversation : résumer ────────
    {
        QJsonObject schema;
        schema[QStringLiteral("type")] = QStringLiteral("object");

        QJsonObject props;
        QJsonObject msgsProp;
        msgsProp[QStringLiteral("type")] = QStringLiteral("array");
        msgsProp[QStringLiteral("description")] =
            QStringLiteral("Messages de la conversation [{role, content}]");
        props[QStringLiteral("messages")] = msgsProp;

        schema[QStringLiteral("properties")] = props;
        QJsonArray required;
        required.append(QStringLiteral("messages"));
        schema[QStringLiteral("required")] = required;

        tools.append(buildToolSchema(
            QStringLiteral("summarize_conversation"),
            QStringLiteral("Extraire et mémoriser les faits clés d'une conversation. "
                           "Les informations sont stockées en mémoire à moyen terme."),
            schema));
    }

    // ── v8: file_read : lire un fichier ─────────────
    {
        QJsonObject schema;
        schema[QStringLiteral("type")] = QStringLiteral("object");

        QJsonObject props;
        QJsonObject pathProp;
        pathProp[QStringLiteral("type")] = QStringLiteral("string");
        pathProp[QStringLiteral("description")] =
            QStringLiteral("Chemin relatif du fichier dans le dossier EXO_Files");
        props[QStringLiteral("path")] = pathProp;

        schema[QStringLiteral("properties")] = props;
        QJsonArray required;
        required.append(QStringLiteral("path"));
        schema[QStringLiteral("required")] = required;

        tools.append(buildToolSchema(
            QStringLiteral("file_read"),
            QStringLiteral("Lire le contenu d'un fichier dans le dossier sécurisé."),
            schema));
    }

    // ── v8: file_write : écrire un fichier ──────────
    {
        QJsonObject schema;
        schema[QStringLiteral("type")] = QStringLiteral("object");

        QJsonObject props;
        QJsonObject pathProp;
        pathProp[QStringLiteral("type")] = QStringLiteral("string");
        pathProp[QStringLiteral("description")] =
            QStringLiteral("Chemin relatif du fichier");
        props[QStringLiteral("path")] = pathProp;

        QJsonObject contentProp;
        contentProp[QStringLiteral("type")] = QStringLiteral("string");
        contentProp[QStringLiteral("description")] =
            QStringLiteral("Contenu à écrire dans le fichier");
        props[QStringLiteral("content")] = contentProp;

        schema[QStringLiteral("properties")] = props;
        QJsonArray required;
        required.append(QStringLiteral("path"));
        required.append(QStringLiteral("content"));
        schema[QStringLiteral("required")] = required;

        tools.append(buildToolSchema(
            QStringLiteral("file_write"),
            QStringLiteral("Écrire du contenu dans un fichier du dossier sécurisé."),
            schema));
    }

    // ── v8: file_list : lister des fichiers ─────────
    {
        QJsonObject schema;
        schema[QStringLiteral("type")] = QStringLiteral("object");

        QJsonObject props;
        QJsonObject pathProp;
        pathProp[QStringLiteral("type")] = QStringLiteral("string");
        pathProp[QStringLiteral("description")] =
            QStringLiteral("Chemin du répertoire à lister (vide = racine)");
        props[QStringLiteral("path")] = pathProp;

        QJsonObject patternProp;
        patternProp[QStringLiteral("type")] = QStringLiteral("string");
        patternProp[QStringLiteral("description")] =
            QStringLiteral("Pattern de filtrage (ex: *.txt)");
        props[QStringLiteral("pattern")] = patternProp;

        schema[QStringLiteral("properties")] = props;

        tools.append(buildToolSchema(
            QStringLiteral("file_list"),
            QStringLiteral("Lister les fichiers dans un répertoire du dossier sécurisé."),
            schema));
    }

    // ── v8: calendar_add : ajouter un événement ─────
    {
        QJsonObject schema;
        schema[QStringLiteral("type")] = QStringLiteral("object");

        QJsonObject props;
        QJsonObject titleProp;
        titleProp[QStringLiteral("type")] = QStringLiteral("string");
        titleProp[QStringLiteral("description")] =
            QStringLiteral("Titre de l'événement");
        props[QStringLiteral("title")] = titleProp;

        QJsonObject dateProp;
        dateProp[QStringLiteral("type")] = QStringLiteral("string");
        dateProp[QStringLiteral("description")] =
            QStringLiteral("Date au format YYYY-MM-DD");
        props[QStringLiteral("date")] = dateProp;

        QJsonObject timeProp;
        timeProp[QStringLiteral("type")] = QStringLiteral("string");
        timeProp[QStringLiteral("description")] =
            QStringLiteral("Heure au format HH:MM (optionnel)");
        props[QStringLiteral("time")] = timeProp;

        QJsonObject durProp;
        durProp[QStringLiteral("type")] = QStringLiteral("integer");
        durProp[QStringLiteral("description")] =
            QStringLiteral("Durée en minutes (défaut: 60)");
        props[QStringLiteral("duration_min")] = durProp;

        schema[QStringLiteral("properties")] = props;
        QJsonArray required;
        required.append(QStringLiteral("title"));
        required.append(QStringLiteral("date"));
        schema[QStringLiteral("required")] = required;

        tools.append(buildToolSchema(
            QStringLiteral("calendar_add"),
            QStringLiteral("Ajouter un événement au calendrier d'Alex."),
            schema));
    }

    // ── v8: calendar_list : lister les événements ───
    {
        QJsonObject schema;
        schema[QStringLiteral("type")] = QStringLiteral("object");

        QJsonObject props;
        QJsonObject fromProp;
        fromProp[QStringLiteral("type")] = QStringLiteral("string");
        fromProp[QStringLiteral("description")] =
            QStringLiteral("Date de début YYYY-MM-DD (optionnel)");
        props[QStringLiteral("from")] = fromProp;

        QJsonObject toProp;
        toProp[QStringLiteral("type")] = QStringLiteral("string");
        toProp[QStringLiteral("description")] =
            QStringLiteral("Date de fin YYYY-MM-DD (optionnel)");
        props[QStringLiteral("to")] = toProp;

        schema[QStringLiteral("properties")] = props;

        tools.append(buildToolSchema(
            QStringLiteral("calendar_list"),
            QStringLiteral("Lister les événements du calendrier d'Alex sur une période."),
            schema));
    }

    // ── v8: system_info : infos système ─────────────
    {
        QJsonObject schema;
        schema[QStringLiteral("type")] = QStringLiteral("object");
        schema[QStringLiteral("properties")] = QJsonObject();

        tools.append(buildToolSchema(
            QStringLiteral("system_info"),
            QStringLiteral("Obtenir les informations système (CPU, RAM, disque, réseau). "
                           "Utiliser quand Alex demande des infos sur son PC."),
            schema));
    }

    // ── Domotique v1: domotic_action ──────────────
    {
        QJsonObject schema;
        schema[QStringLiteral("type")] = QStringLiteral("object");
        QJsonObject props;
        props[QStringLiteral("device_name")] = QJsonObject{
            {QStringLiteral("type"), QStringLiteral("string")},
            {QStringLiteral("description"), QStringLiteral("Nom de l'appareil (ex: 'salon', 'caméra entrée', 'TV').")}
        };
        props[QStringLiteral("command")] = QJsonObject{
            {QStringLiteral("type"), QStringLiteral("string")},
            {QStringLiteral("description"), QStringLiteral("Action: turn_on, turn_off, set_volume, set_source, set_mode, tts, get_snapshot, set_brightness, set_color.")}
        };
        props[QStringLiteral("value")] = QJsonObject{
            {QStringLiteral("type"), QStringLiteral("string")},
            {QStringLiteral("description"), QStringLiteral("Valeur optionnelle (volume, source, mode, couleur, texte TTS).")}
        };
        schema[QStringLiteral("properties")] = props;
        schema[QStringLiteral("required")] = QJsonArray{QStringLiteral("device_name"), QStringLiteral("command")};

        tools.append(buildToolSchema(
            QStringLiteral("domotic_action"),
            QStringLiteral("Contrôler un appareil connecté (lumière, TV, radiateur, caméra, enceinte). "
                           "Utiliser quand Alex demande d'allumer, éteindre, régler un appareil."),
            schema));
    }

    // ── Domotique v1: domotic_query ──────────────────
    {
        QJsonObject schema;
        schema[QStringLiteral("type")] = QStringLiteral("object");
        QJsonObject props;
        props[QStringLiteral("query")] = QJsonObject{
            {QStringLiteral("type"), QStringLiteral("string")},
            {QStringLiteral("description"), QStringLiteral("Question sur la maison: 'quels appareils sont allumés ?', 'état du salon', 'consommation chauffage'.")}
        };
        props[QStringLiteral("room")] = QJsonObject{
            {QStringLiteral("type"), QStringLiteral("string")},
            {QStringLiteral("description"), QStringLiteral("Pièce optionnelle pour filtrer (salon, chambre, cuisine…).")}
        };
        schema[QStringLiteral("properties")] = props;
        schema[QStringLiteral("required")] = QJsonArray{QStringLiteral("query")};

        tools.append(buildToolSchema(
            QStringLiteral("domotic_query"),
            QStringLiteral("Interroger l'état de la maison connectée. "
                           "Utiliser quand Alex pose des questions sur ses appareils, pièces ou sa consommation."),
            schema));
    }

    // ── Domotique v1: network_scan ──────────────────
    {
        QJsonObject schema;
        schema[QStringLiteral("type")] = QStringLiteral("object");
        schema[QStringLiteral("properties")] = QJsonObject();

        tools.append(buildToolSchema(
            QStringLiteral("network_scan"),
            QStringLiteral("Scanner le réseau local pour détecter tous les appareils connectés. "
                           "Utiliser quand Alex demande la carte réseau ou les appareils connectés au WiFi."),
            schema));
    }

    hClaude() << "Outils EXO construits:" << tools.size() << "outils";

    // v26.1 Latency: cache for subsequent calls
    cachedTools = tools;
    cached = true;

    return tools;
}

// ═══════════════════════════════════════════════════════
//  Helpers
// ═══════════════════════════════════════════════════════

// ── v26.2 Latency: pre-build static payload fields ──

void ClaudeAPI::rebuildSkeleton() const
{
    m_payloadSkeleton = QJsonObject();
    m_payloadSkeleton[QStringLiteral("model")]       = anthropicWireModelId(m_model);
    m_payloadSkeleton[QStringLiteral("max_tokens")]   = m_maxTokens;
    // LLM LOCK 2026-05-16 : `temperature`, `top_p` et `top_k` sont DEPRECATED
    // pour claude-opus-4.7 (l'API renvoie HTTP 400 invalid_request_error si
    // l'un de ces champs est present). On les omet systematiquement.
    m_skeletonDirty = false;
    return;
}

// ── v26.2 Latency: contextual tool filtering ─────────

QJsonArray ClaudeAPI::filterToolsForMessage(const QString &message,
                                            const QJsonArray &allTools)
{
    QString low = message.toLower();

    // Base tools always included (context + memory + system)
    static const QSet<QString> baseTools = {
        QStringLiteral("get_context"),
        QStringLiteral("remember_info"),
        QStringLiteral("recall_info"),
        QStringLiteral("system_info")
    };

    // Detect intent category
    bool isWeather = low.contains(QLatin1String("météo"))
                  || low.contains(QLatin1String("quel temps"))
                  || low.contains(QLatin1String("température"))
                  || low.contains(QLatin1String("pluie"))
                  || low.contains(QLatin1String("soleil"))
                  || low.contains(QLatin1String("prévision"));

    bool isDomotic = low.contains(QLatin1String("allume"))
                  || low.contains(QLatin1String("éteins"))
                  || low.contains(QLatin1String("éteindre"))
                  || low.contains(QLatin1String("allumer"))
                  || low.contains(QLatin1String("lumière"))
                  || low.contains(QLatin1String("lampe"))
                  || low.contains(QLatin1String("volet"))
                  || low.contains(QLatin1String("chauffage"))
                  || low.contains(QLatin1String("radiateur"))
                  || low.contains(QLatin1String("appareil"));

    bool isTimer = low.contains(QLatin1String("minuteur"))
                || low.contains(QLatin1String("timer"))
                || low.contains(QLatin1String("chrono"))
                || low.contains(QLatin1String("compte à rebours"));

    bool isReminder = low.contains(QLatin1String("rappelle"))
                   || low.contains(QLatin1String("rappel"))
                   || low.contains(QLatin1String("n'oublie pas"))
                   || low.contains(QLatin1String("souviens"));

    bool isCalendar = low.contains(QLatin1String("calendrier"))
                   || low.contains(QLatin1String("rendez-vous"))
                   || low.contains(QLatin1String("événement"))
                   || low.contains(QLatin1String("agenda"));

    bool isDateTime = low.contains(QLatin1String("quelle heure"))
                   || low.contains(QLatin1String("quel jour"))
                   || low.contains(QLatin1String("quelle date"));

    // If no specific intent detected → send all tools (complex query)
    if (!isWeather && !isDomotic && !isTimer && !isReminder && !isCalendar && !isDateTime)
        return allTools;

    QSet<QString> allowed = baseTools;

    if (isWeather) {
        allowed.insert(QStringLiteral("get_weather"));
    }
    if (isDomotic) {
        allowed.insert(QStringLiteral("ha_turn_on"));
        allowed.insert(QStringLiteral("ha_turn_off"));
        allowed.insert(QStringLiteral("ha_toggle"));
        allowed.insert(QStringLiteral("ha_set_brightness"));
        allowed.insert(QStringLiteral("ha_set_temperature"));
        allowed.insert(QStringLiteral("ha_get_state"));
        allowed.insert(QStringLiteral("domotic_action"));
        allowed.insert(QStringLiteral("domotic_query"));
    }
    if (isTimer || isReminder) {
        allowed.insert(QStringLiteral("remember_info"));
        allowed.insert(QStringLiteral("recall_info"));
    }
    if (isCalendar) {
        allowed.insert(QStringLiteral("calendar_add"));
        allowed.insert(QStringLiteral("calendar_list"));
    }
    if (isDateTime) {
        allowed.insert(QStringLiteral("get_datetime"));
    }

    QJsonArray filtered;
    for (const auto &tool : allTools) {
        QString name = tool.toObject().value(QStringLiteral("name")).toString();
        if (allowed.contains(name))
            filtered.append(tool);
    }

    hClaude() << "[Latency] Tools filtrés:" << filtered.size()
              << "/" << allTools.size()
              << (isWeather ? "(météo)" : isDomotic ? "(domotique)"
                  : isTimer ? "(timer)" : isReminder ? "(rappel)"
                  : isCalendar ? "(calendrier)" : "(date/heure)");

    return filtered.isEmpty() ? allTools : filtered;
}

void ClaudeAPI::setError(const QString &error)
{
    ++m_totalErrors;
    m_lastError = error;
    hWarning(exoClaude) << error;
    emit errorOccurred(error);
}

void ClaudeAPI::cleanup()
{
    if (m_currentReply) {
        m_currentReply->blockSignals(true);
        m_currentReply->deleteLater();
        m_currentReply = nullptr;
    }
    setStreaming(false);
}

void ClaudeAPI::setStreaming(bool on)
{
    if (m_isStreaming != on) {
        m_isStreaming = on;
        emit streamingChanged();
    }
}

// ═══════════════════════════════════════════════════════
//  v8.1 ULL: Warmup & KeepAlive
// ═══════════════════════════════════════════════════════

void ClaudeAPI::initWarmup()
{
    if (m_warmupInProgress || m_warmedUp) return;
    if (!m_isReady || m_apiKey.isEmpty()) {
        hClaude() << "initWarmup: clé API manquante, abandon";
        return;
    }

    m_warmupInProgress = true;
    hClaude() << "Warmup LLM — envoi d'un ping léger à Claude…";

    // Construire un payload minimal (non-streaming, 1 token max)
    QJsonObject payload;
    payload[QStringLiteral("model")] = anthropicWireModelId(m_model);
    payload[QStringLiteral("max_tokens")] = 1;
    payload[QStringLiteral("stream")] = false;
    QJsonArray messages;
    QJsonObject msg;
    msg[QStringLiteral("role")] = QStringLiteral("user");
    msg[QStringLiteral("content")] = QStringLiteral("ping");
    messages.append(msg);
    payload[QStringLiteral("messages")] = messages;

    QByteArray data = QJsonDocument(payload).toJson(QJsonDocument::Compact);
    QNetworkRequest request = buildHttpRequest();

    QNetworkReply *reply = m_networkManager->post(request, data);
    connect(reply, &QNetworkReply::finished, this, [this, reply]() {
        reply->deleteLater();
        m_warmupInProgress = false;

        if (reply->error() == QNetworkReply::NoError) {
            m_warmedUp = true;
            hClaude() << "Warmup LLM terminé — connexion pré-chauffée";
        } else {
            hWarning(exoClaude) << "Warmup échoué:" << reply->errorString();
        }
    });
}

void ClaudeAPI::startKeepAlive(int intervalMs)
{
    if (!m_keepAliveTimer) {
        m_keepAliveTimer = new QTimer(this);
        m_keepAliveTimer->setTimerType(Qt::VeryCoarseTimer);
        connect(m_keepAliveTimer, &QTimer::timeout, this, [this]() {
            // Ne pas envoyer de keepalive pendant une requête active
            if (m_currentReply || !m_isReady) return;

            hClaude() << "KeepAlive ping…";
            initWarmup();
            m_warmedUp = false; // Force un vrai ping
        });
    }
    m_keepAliveTimer->start(qMax(30000, intervalMs));
    hClaude() << "KeepAlive activé — intervalle:" << intervalMs / 1000 << "s";
}

void ClaudeAPI::stopKeepAlive()
{
    if (m_keepAliveTimer) {
        m_keepAliveTimer->stop();
        hClaude() << "KeepAlive désactivé";
    }
}