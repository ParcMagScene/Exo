#pragma once

#include <QObject>
#include <QNetworkAccessManager>
#include <QNetworkReply>
#include <QJsonObject>
#include <QJsonArray>
#include <QTimer>
#include <QElapsedTimer>
#include <QMutex>

// ═══════════════════════════════════════════════════════
//  ClaudeAPI — Client Anthropic Messages v1
//
//  Streaming SSE, Function Calling, retry exponentiel,
//  rate limiting, intégration mémoire AIMemoryManager.
//
//  Signaux principaux :
//    partialResponse(text)     — token par token (streaming)
//    finalResponse(fullText)   — réponse complète
//    toolCallDetected(id,name,args) — function calling
//    errorOccurred(msg)        — erreur réseau / API / JSON
// ═══════════════════════════════════════════════════════

// ─────────────────────────────────────────────────────
//  ContentBlock — bloc de contenu accumulé pendant le streaming
// ─────────────────────────────────────────────────────
struct ContentBlock
{
    QString type;           // "text" ou "tool_use"
    QString text;           // pour type "text"
    QString toolUseId;      // pour type "tool_use"
    QString toolName;       // pour type "tool_use"
    QString toolInputJson;  // JSON accumulé progressivement
};

class ClaudeAPI : public QObject
{
    Q_OBJECT
    Q_PROPERTY(bool ready READ isReady NOTIFY readyChanged)
    Q_PROPERTY(bool streaming READ isStreaming NOTIFY streamingChanged)
    Q_PROPERTY(QString model READ model WRITE setModel NOTIFY modelChanged)

public:
    explicit ClaudeAPI(QObject *parent = nullptr);
    ~ClaudeAPI() override;

    // ── Configuration ────────────────────────────────
    void setApiKey(const QString &apiKey);
    void setModel(const QString &model);
    void setTemperature(double temp);
    void setMaxTokens(int tokens);
    void setTopP(double topP);
    void setTopK(int topK);
    void setTimeout(int timeoutMs);

    // ── v8.1 ULL: Warmup & KeepAlive ─────────────────
    void initWarmup();
    void startKeepAlive(int intervalMs = 240000);
    void stopKeepAlive();
    bool isWarmedUp() const { return m_warmedUp; }

    // ── État ─────────────────────────────────────────
    bool isReady() const { return m_isReady; }
    bool isStreaming() const { return m_isStreaming; }
    QString model() const { return m_model; }
    QString lastError() const { return m_lastError; }

    // ── API principale ───────────────────────────────

    // Envoi simple (compatibilité QML)
    Q_INVOKABLE void sendMessage(const QString &userMessage);

    // Envoi complet avec contexte, outils, streaming
    void sendMessageFull(const QString &userMessage,
                         const QString &systemPrompt,
                         const QJsonArray &tools = {},
                         bool stream = true);

    // Envoi du résultat d'un tool call à Claude
    void sendToolResult(const QString &toolUseId,
                        const QJsonObject &result);

    // Annulation
    Q_INVOKABLE void cancelCurrentRequest();

    // ── Outils EXO (schémas Function Calling) ────────
    static QJsonObject buildToolSchema(const QString &name,
                                       const QString &description,
                                       const QJsonObject &inputSchema);
    static QJsonArray  buildEXOTools();

    // ── Conversation multi-tour ──────────────────────
    void clearConversationHistory();
    int  conversationTurnCount() const;

signals:
    // Streaming
    void partialResponse(const QString &text);
    void finalResponse(const QString &fullText);

    // Sentence-level streaming (for TTS pipelining)
    void sentenceReady(const QString &sentence);

    // Compatibilité QML (alias de finalResponse)
    void responseReceived(const QString &response);

    // Function Calling
    void toolCallDetected(const QString &toolUseId,
                          const QString &toolName,
                          const QJsonObject &arguments);

    // Lifecycle
    void errorOccurred(const QString &error);
    void requestStarted();
    void requestFinished();

    // Property change
    void readyChanged();
    void streamingChanged();
    void modelChanged();

private slots:
    void onStreamDataReady();
    void onReplyFinished();
    void onNetworkError(QNetworkReply::NetworkError error);
    void onTimeout();
    void onRetryTimer();

private:
    // ── Construction requête ─────────────────────────
    QJsonObject buildPayload(const QString &userMessage,
                             const QString &systemPrompt,
                             const QJsonArray &tools,
                             bool stream) const;
    QNetworkRequest buildHttpRequest() const;

    // ── Streaming SSE ────────────────────────────────
    void processStreamChunk(const QByteArray &chunk);
    void processSSELine(const QByteArray &line);
    // Perf: fast-path tente d'extraire {index,text} d'un content_block_delta
    // text_delta sans construire QJsonDocument/QJsonObject. Renvoie true si
    // le delta a été appliqué; false → fallback parsing JSON complet.
    bool tryFastTextDelta(const QByteArray &dataBytes);
    void applyTextDelta(int index, const QString &text);
    void processSSEEvent(const QString &eventType,
                         const QJsonObject &data);
    void handleContentBlockStart(const QJsonObject &data);
    void handleContentBlockDelta(const QJsonObject &data);
    void handleContentBlockStop(const QJsonObject &data);
    void handleMessageDelta(const QJsonObject &data);
    void handleMessageStop();
    void finalizeToolCalls();

    // ── Sentence splitting ───────────────────────────
    void trySplitSentences();
    void flushSentenceBuffer();

    // ── Réponse non-streaming ────────────────────────
    void processFullResponse(const QByteArray &data);
    void handleHttpError(int httpStatus, const QByteArray &data);

    // ── Robustesse ───────────────────────────────────
    bool validateJsonResponse(const QJsonObject &obj) const;
    void retryWithBackoff();
    void resetRetryState();
    void startRequest(const QByteArray &payload, bool stream);
    bool checkRateLimit();

    // ── Helpers ──────────────────────────────────────
    void setError(const QString &error);
    void cleanup();
    void setStreaming(bool on);
    void rebuildSkeleton() const;
    static QJsonArray filterToolsForMessage(const QString &message, const QJsonArray &allTools);

    // ── Réseau ───────────────────────────────────────
    QNetworkAccessManager *m_networkManager = nullptr;
    QNetworkReply         *m_currentReply   = nullptr;
    QTimer                *m_timeoutTimer   = nullptr;
    QTimer                *m_retryTimer     = nullptr;

    // ── Configuration ────────────────────────────────
    QString m_apiKey;
    QString m_model;
    double  m_temperature;
    int     m_maxTokens;
    double  m_topP;
    int     m_topK;
    int     m_timeoutMs;

    // ── État ─────────────────────────────────────────
    bool    m_isReady     = false;
    bool    m_isStreaming  = false;
    QString m_lastError;

    // ── Streaming accumulateurs ──────────────────────
    QByteArray          m_sseBuffer;       // buffer brut SSE
    QString             m_currentEventType;
    QString             m_accumulatedText;  // texte complet accumulé
    QString             m_sentenceBuffer;   // buffer phrase en cours (sentence splitting)
    QList<ContentBlock> m_contentBlocks;   // blocs en cours
    int                 m_currentBlockIdx = -1;

    // ── Conversation multi-tour ──────────────────────
    QJsonArray m_conversationHistory;
    QString    m_pendingSystemPrompt;
    QJsonArray m_pendingTools;
    bool       m_pendingStream = true;

    // ── Retry ────────────────────────────────────────
    int        m_retryCount    = 0;
    QByteArray m_lastPayload;
    bool       m_lastStreamFlag = true;

    // ── v8.1 ULL: Warmup & KeepAlive ─────────────────
    QTimer    *m_keepAliveTimer = nullptr;
    bool       m_warmedUp = false;
    bool       m_warmupInProgress = false;

    // ── Rate limiting ────────────────────────────────
    QList<qint64> m_requestTimestamps;

    // ── Stats ────────────────────────────────────────
    int m_totalRequests = 0;
    int m_totalErrors   = 0;

    // ── Trace (MetricsManager/TraceManager) ──────────
    QString m_currentTraceId;

    // ── v26.2 Latency: pre-built skeleton & cached request ──
    mutable QJsonObject     m_payloadSkeleton;
    mutable bool            m_skeletonDirty  = true;
    mutable QNetworkRequest m_cachedRequest;
    mutable bool            m_requestDirty   = true;

    // ── Constantes ───────────────────────────────────
    static constexpr const char *API_URL       = "https://api.anthropic.com/v1/messages";
    static constexpr const char *API_VERSION   = "2023-06-01";
    static constexpr int    DEFAULT_TIMEOUT    = 15000;  // v5.2: 15s (was 30s)
    static constexpr int    DEFAULT_MAX_TOKENS = 1024;   // v5.2: 1024 (was 4096) — voice responses are short
    static constexpr double DEFAULT_TEMP       = 0.7;
    static constexpr int    MAX_RETRIES        = 3;
    static constexpr int    RATE_LIMIT_PER_MIN = 50;
    static constexpr int    MAX_HISTORY_TURNS  = 10;     // v26.1: cap history to reduce payload size
};