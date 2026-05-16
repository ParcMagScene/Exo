#include "AIMemoryManager.h"
#include "core/LogManager.h"
#include "utils/SafeIO.h"

#include <QStandardPaths>
#include <QDir>
#include <QFile>
#include <QFileInfo>
#include <QRegularExpression>
#include <QDateTime>
#include <algorithm>

// ═══════════════════════════════════════════════════════
//  Construction / Destruction
// ═══════════════════════════════════════════════════════

AIMemoryManager::AIMemoryManager(QObject *parent)
    : QObject(parent)
{
    // Debounce saves : on attend 2 s d'inactivité avant d'écrire
    m_saveTimer = new QTimer(this);
    m_saveTimer->setSingleShot(true);
    m_saveTimer->setInterval(SAVE_DEBOUNCE_MS);
    connect(m_saveTimer, &QTimer::timeout, this, &AIMemoryManager::saveToFile);

    loadFromFile();
    hAssistant() << "AIMemoryManager v2 initialisé —"
                 << m_conversations.size() << "conversations,"
                 << m_memories.size() << "souvenirs,"
                 << m_userPreferences.size() << "prefs";
}

AIMemoryManager::~AIMemoryManager()
{
    // Force save si un save était en attente
    if (m_saveTimer->isActive()) {
        m_saveTimer->stop();
        saveToFile();
    }
}

void AIMemoryManager::setMemoryEnabled(bool on)
{
    if (m_enabled != on) {
        m_enabled = on;
        emit memoryEnabledChanged();
    }
}

// ═══════════════════════════════════════════════════════
//  Conversations — buffer circulaire
// ═══════════════════════════════════════════════════════

void AIMemoryManager::addConversation(const QString &userMessage,
                                       const QString &assistantResponse)
{
    if (!m_enabled || userMessage.isEmpty()) return;

    ConversationEntry entry;
    entry.timestamp = QDateTime::currentMSecsSinceEpoch();
    entry.user      = userMessage;
    entry.assistant  = assistantResponse;

    {
        QMutexLocker lk(&m_mutex);
        m_conversations.append(entry);
        while (m_conversations.size() > m_maxConversations)
            m_conversations.removeFirst();
    }

    // Analyse automatique du message utilisateur
    analyzeAndMaybeStore(userMessage);

    scheduleSave();
    emit conversationAdded(userMessage, assistantResponse);
    emit conversationCountChanged();
}

QString AIMemoryManager::getConversationContext(int maxEntries) const
{
    QMutexLocker lk(&m_mutex);
    if (!m_enabled || m_conversations.isEmpty()) return {};

    QStringList ctx;
    int start = qMax(0, m_conversations.size() - maxEntries);
    for (int i = start; i < m_conversations.size(); ++i) {
        const auto &e = m_conversations.at(i);
        ctx << QStringLiteral("Utilisateur: %1").arg(e.user);
        ctx << QStringLiteral("Assistant: %1").arg(e.assistant);
    }
    return ctx.join('\n');
}

QStringList AIMemoryManager::getRecentConversations(int count) const
{
    QMutexLocker lk(&m_mutex);
    QStringList list;
    if (!m_enabled || m_conversations.isEmpty()) return list;

    int start = qMax(0, m_conversations.size() - count);
    for (int i = start; i < m_conversations.size(); ++i) {
        const auto &e = m_conversations.at(i);
        QString ts = QDateTime::fromMSecsSinceEpoch(e.timestamp)
                         .toString("hh:mm");
        list << QStringLiteral("[%1] %2 → %3")
                    .arg(ts, e.user.left(50), e.assistant.left(50));
    }
    return list;
}

// ═══════════════════════════════════════════════════════
//  Préférences — clé/valeur persistantes
// ═══════════════════════════════════════════════════════

void AIMemoryManager::updateUserPreference(const QString &key,
                                            const QVariant &value)
{
    if (!m_enabled || key.isEmpty()) return;
    m_userPreferences[key] = value;
    scheduleSave();
    emit userPreferenceUpdated(key, value);
}

QVariant AIMemoryManager::getUserPreference(const QString &key,
                                             const QVariant &defaultValue) const
{
    return m_userPreferences.value(key, defaultValue);
}

// ═══════════════════════════════════════════════════════
//  Mémoire sémantique — CRUD
// ═══════════════════════════════════════════════════════

void AIMemoryManager::addMemory(const QString &text, double importance,
                                 const QStringList &tags,
                                 const QString &category,
                                 const QString &source)
{
    if (!m_enabled || text.isEmpty()) return;

    // Anti-doublon
    if (isDuplicate(text)) return;

    MemoryEntry m;
    m.id         = QUuid::createUuid().toString(QUuid::WithoutBraces);
    m.text       = text;
    m.importance = qBound(0.0, importance, 1.0);
    m.tags       = tags;
    m.timestamp  = QDateTime::currentMSecsSinceEpoch();
    m.source     = source;
    m.category   = category;

    {
        QMutexLocker lk(&m_mutex);
        m_memories.append(m);
        // Rotation : supprimer les plus anciens et les moins importants
        while (m_memories.size() > m_maxMemories) {
            // Trouver le souvenir avec l'importance effective la plus basse
            int worst = 0;
            double worstScore = effectiveImportance(m_memories[0]);
            for (int i = 1; i < m_memories.size(); ++i) {
                double s = effectiveImportance(m_memories[i]);
                if (s < worstScore) {
                    worstScore = s;
                    worst = i;
                }
            }
            m_memories.removeAt(worst);
        }
    }

    scheduleSave();
    emit memoryAdded(m.id, text);
    emit memoryCountChanged();
    hAssistant() << "Souvenir ajouté [" << category << "]:"
                 << text.left(60) << "(importance:" << importance << ")";

    // Forward to FAISS semantic server if connected
    if (m_semanticWs && m_semanticWs->isConnected()) {
        QJsonObject payload;
        payload["text"]       = text;
        payload["importance"] = importance;
        payload["category"]   = category;
        payload["source"]     = source;
        QJsonArray tagsArr;
        for (const QString &t : tags) tagsArr.append(t);
        payload["tags"] = tagsArr;
        sendToSemanticServer("add", payload);
    }
}

QVariantList AIMemoryManager::searchMemories(const QString &query,
                                              int maxResults) const
{
    QVariantList results;
    if (query.isEmpty()) return results;

    // If semantic server is connected, use FAISS vector search
    if (m_semanticWs && m_semanticWs->isConnected()) {
        QJsonObject payload;
        payload["query"] = query;
        payload["top_k"] = maxResults;
        const_cast<AIMemoryManager*>(this)->sendToSemanticServer("search", payload);
        // Return any pending results from previous search (async model)
        if (!m_pendingSemanticResults.isEmpty())
            return m_pendingSemanticResults;
    }

    // Fallback: local regex-based search
    QMutexLocker lk(&m_mutex);

    QString low = query.toLower();
    QStringList keywords = low.split(QRegularExpression("\\s+"),
                                     Qt::SkipEmptyParts);

    // Score chaque souvenir par pertinence (nombre de mots matchés + importance effective)
    struct Scored { int idx; double score; };
    QList<Scored> scored;

    for (int i = 0; i < m_memories.size(); ++i) {
        const auto &mem = m_memories[i];
        QString mLow = mem.text.toLower();
        int hits = 0;
        for (const QString &kw : keywords) {
            if (mLow.contains(kw)) ++hits;
            for (const QString &tag : mem.tags)
                if (tag.toLower().contains(kw)) { ++hits; break; }
            if (mem.category.toLower().contains(kw)) ++hits;
        }
        if (hits > 0) {
            double relevance = static_cast<double>(hits) / keywords.size();
            double eff = effectiveImportance(mem);
            scored.append({i, relevance * 0.6 + eff * 0.4});
        }
    }

    std::sort(scored.begin(), scored.end(),
              [](const Scored &a, const Scored &b) { return a.score > b.score; });

    int n = qMin(maxResults, scored.size());
    for (int i = 0; i < n; ++i) {
        const auto &mem = m_memories[scored[i].idx];
        QVariantMap vm;
        vm["id"]         = mem.id;
        vm["text"]       = mem.text;
        vm["importance"] = mem.importance;
        vm["tags"]       = QVariant(mem.tags);
        vm["timestamp"]  = mem.timestamp;
        vm["source"]     = mem.source;
        vm["category"]   = mem.category;
        vm["score"]      = scored[i].score;
        results.append(vm);
    }
    return results;
}

QVariantList AIMemoryManager::getMemoriesByTag(const QString &tag,
                                                int maxResults) const
{
    QMutexLocker lk(&m_mutex);
    QVariantList results;
    QString lowTag = tag.toLower();

    for (const auto &mem : m_memories) {
        bool found = false;
        for (const QString &t : mem.tags) {
            if (t.toLower() == lowTag) { found = true; break; }
        }
        if (!found) continue;

        QVariantMap vm;
        vm["id"]         = mem.id;
        vm["text"]       = mem.text;
        vm["importance"] = mem.importance;
        vm["tags"]       = QVariant(mem.tags);
        vm["timestamp"]  = mem.timestamp;
        vm["source"]     = mem.source;
        vm["category"]   = mem.category;
        results.append(vm);

        if (results.size() >= maxResults) break;
    }
    return results;
}

QVariantList AIMemoryManager::getAllMemories() const
{
    QMutexLocker lk(&m_mutex);
    QVariantList all;
    for (const auto &mem : m_memories) {
        QVariantMap vm;
        vm["id"]         = mem.id;
        vm["text"]       = mem.text;
        vm["importance"] = mem.importance;
        vm["tags"]       = QVariant(mem.tags);
        vm["timestamp"]  = mem.timestamp;
        vm["source"]     = mem.source;
        vm["category"]   = mem.category;
        vm["effective"]  = effectiveImportance(mem);
        all.append(vm);
    }
    return all;
}

bool AIMemoryManager::removeMemory(const QString &id)
{
    QMutexLocker lk(&m_mutex);
    for (int i = 0; i < m_memories.size(); ++i) {
        if (m_memories[i].id == id) {
            m_memories.removeAt(i);
            lk.unlock();
            scheduleSave();
            emit memoryCountChanged();
            return true;
        }
    }
    return false;
}

// ═══════════════════════════════════════════════════════
//  Contexte Claude — mémoire + conversations compactes
// ═══════════════════════════════════════════════════════

QString AIMemoryManager::buildClaudeContext(int maxConversations,
                                             int maxMemories) const
{
    QMutexLocker lk(&m_mutex);
    QString ctx;

    // ── Souvenirs pertinents (triés par importance effective) ──
    if (!m_memories.isEmpty()) {
        struct Ranked { int idx; double eff; };
        QList<Ranked> ranked;
        for (int i = 0; i < m_memories.size(); ++i)
            ranked.append({i, effectiveImportance(m_memories[i])});

        std::sort(ranked.begin(), ranked.end(),
                  [](const Ranked &a, const Ranked &b) { return a.eff > b.eff; });

        int n = qMin(maxMemories, ranked.size());
        if (n > 0) {
            ctx += "[Mémoire utilisateur]\n";
            for (int i = 0; i < n; ++i) {
                const auto &mem = m_memories[ranked[i].idx];
                ctx += QStringLiteral("- %1 [%2] (importance: %3)\n")
                           .arg(mem.text, mem.category)
                           .arg(mem.importance, 0, 'f', 1);
            }
            ctx += '\n';
        }
    }

    // ── Préférences connues ──
    if (!m_userPreferences.isEmpty()) {
        ctx += "[Préférences]\n";
        for (auto it = m_userPreferences.cbegin();
             it != m_userPreferences.cend(); ++it) {
            ctx += QStringLiteral("- %1: %2\n")
                       .arg(it.key(), it.value().toString());
        }
        ctx += '\n';
    }

    // ── Dernières conversations ──
    if (!m_conversations.isEmpty()) {
        ctx += "[Dernières conversations]\n";
        int start = qMax(0, m_conversations.size() - maxConversations);
        for (int i = start; i < m_conversations.size(); ++i) {
            const auto &e = m_conversations.at(i);
            ctx += QStringLiteral("Utilisateur: %1\nAssistant: %2\n")
                       .arg(e.user, e.assistant);
        }
    }

    return ctx;
}

// ═══════════════════════════════════════════════════════
//  Détection automatique — patterns français
// ═══════════════════════════════════════════════════════

void AIMemoryManager::analyzeAndMaybeStore(const QString &userMessage)
{
    if (!m_enabled || userMessage.size() < 5) return;

    QString low = userMessage.toLower();

    // Chaque pattern : { regex, importance, tags, category }
    struct Pattern {
        const char *regex;
        double importance;
        QStringList tags;
        QString category;
    };

    static const Pattern patterns[] = {
        // Identité
        {"je\\s+m'appelle\\s+",          0.9, {"identité", "nom"},       "identité"},
        {"je\\s+suis\\s+",               0.85, {"identité"},              "identité"},
        {"mon\\s+nom\\s+(est|c'est)\\s+", 0.9, {"identité", "nom"},      "identité"},
        {"j'ai\\s+\\d+\\s+ans",          0.8, {"identité", "âge"},       "identité"},

        // Préférences
        {"j'aime\\s+(bien\\s+)?",         0.7, {"préférence"},            "préférence"},
        {"j'adore\\s+",                   0.75, {"préférence"},           "préférence"},
        {"je\\s+préfère\\s+",            0.7, {"préférence"},            "préférence"},
        {"je\\s+(n'aime|déteste)\\s+(pas\\s+)?", 0.7, {"préférence"},    "préférence"},
        {"ma\\s+couleur\\s+(préférée|favorite)", 0.65, {"préférence"},    "préférence"},
        {"mon\\s+(plat|film|jeu|livre|artiste|chanteur|groupe)\\s+(préféré|favori)", 0.7, {"préférence"}, "préférence"},

        // Famille / relations
        {"(ma|mon)\\s+(mère|père|maman|papa|frère|sœur|soeur|copine|copain|femme|mari|fils|fille|grand-?mère|grand-?père)", 0.8, {"famille", "relation"}, "famille"},

        // Animaux
        {"(mon|ma|mes)\\s+(chien|chat|calopsitte|perruche|perroquet|lapin|hamster|poisson|tortue|animal)", 0.75, {"animaux"}, "animaux"},
        {"(il|elle)\\s+s'appelle\\s+",    0.7, {"animaux", "nom"},       "animaux"},

        // Maison / domotique
        {"(ma|mon|mes)\\s+(cuisine|salon|chambre|bureau|jardin|garage|salle\\s+de\\s+bain|terrasse)", 0.6, {"maison"}, "maison"},

        // Travail / projets
        {"je\\s+(travaille|bosse)\\s+(chez|à|au|dans)", 0.7, {"travail"}, "travail"},
        {"je\\s+(vais|prévois|compte|planifie|veux)\\s+", 0.6, {"projet"}, "projet"},
        {"mon\\s+(stage|emploi|job|boulot|entreprise|poste)", 0.65, {"travail"}, "travail"},

        // Faits personnels
        {"mon\\s+anniversaire",           0.8, {"identité", "anniversaire"}, "identité"},
        {"(mon|ma)\\s+adresse",           0.7, {"identité", "adresse"},      "identité"},
        {"je\\s+vis\\s+(à|au|en|chez)",   0.6, {"identité", "lieu"},         "identité"},
        {"je\\s+suis\\s+(né|née)\\s+",    0.75, {"identité", "naissance"},   "identité"},

        // Santé
        {"je\\s+suis\\s+(allergique|intolérant|diabétique)", 0.85, {"santé"}, "santé"},
        {"(mon|ma)\\s+(allergie|régime|traitement|médecin)", 0.7, {"santé"},  "santé"},

        // Loisirs
        {"je\\s+(joue|fais|pratique)\\s+(du|de\\s+la|au|à\\s+la|des)", 0.55, {"loisirs"}, "loisirs"},
    };

    for (const auto &p : patterns) {
        QRegularExpression rx(p.regex, QRegularExpression::CaseInsensitiveOption);
        auto match = rx.match(low);
        if (match.hasMatch()) {
            if (p.importance >= m_importanceThreshold) {
                addMemory(userMessage, p.importance, p.tags, p.category, "auto");
            }
            return; // Un seul pattern par message
        }
    }
}

// ═══════════════════════════════════════════════════════
//  Import / Export
// ═══════════════════════════════════════════════════════

bool AIMemoryManager::exportToFile(const QString &path) const
{
    QMutexLocker lk(&m_mutex);

    QJsonObject root;
    root["version"] = JSON_VERSION;

    // Conversations
    QJsonArray convArr;
    for (const auto &e : m_conversations) {
        QJsonObject o;
        o["timestamp"] = e.timestamp;
        o["user"]      = e.user;
        o["assistant"] = e.assistant;
        convArr.append(o);
    }
    root["conversations"] = convArr;

    // Preferences
    QJsonObject prefsObj;
    for (auto it = m_userPreferences.cbegin(); it != m_userPreferences.cend(); ++it)
        prefsObj[it.key()] = QJsonValue::fromVariant(it.value());
    root["preferences"] = prefsObj;

    // Memories
    QJsonArray memArr;
    for (const auto &m : m_memories)
        memArr.append(memoryToJson(m));
    root["memories"] = memArr;

    QFile file(path);
    if (!file.open(QIODevice::WriteOnly)) return false;
    file.write(QJsonDocument(root).toJson());
    file.close();
    hAssistant() << "Mémoire exportée vers:" << path;
    return true;
}

bool AIMemoryManager::importFromFile(const QString &path)
{
    QFile file(path);
    if (!file.open(QIODevice::ReadOnly)) return false;

    QJsonParseError err;
    QJsonDocument doc = QJsonDocument::fromJson(file.readAll(), &err);
    file.close();

    if (err.error != QJsonParseError::NoError) {
        hWarning(exoAssistant) << "Import JSON erreur:" << err.errorString();
        return false;
    }

    QJsonObject root = doc.object();

    QMutexLocker lk(&m_mutex);

    // Merge conversations
    for (const auto &v : root["conversations"].toArray()) {
        QJsonObject o = v.toObject();
        ConversationEntry e;
        e.timestamp = o["timestamp"].toInteger();
        e.user      = o["user"].toString();
        e.assistant = o["assistant"].toString();
        if (!e.user.isEmpty())
            m_conversations.append(e);
    }
    while (m_conversations.size() > m_maxConversations)
        m_conversations.removeFirst();

    // Merge preferences (import wins)
    QJsonObject prefsObj = root["preferences"].toObject();
    for (auto it = prefsObj.begin(); it != prefsObj.end(); ++it)
        m_userPreferences[it.key()] = it.value().toVariant();

    // Merge memories (skip duplicates)
    for (const auto &v : root["memories"].toArray()) {
        MemoryEntry m = jsonToMemory(v.toObject());
        if (!m.text.isEmpty() && !isDuplicate(m.text)) {
            m_memories.append(m);
        }
    }
    while (m_memories.size() > m_maxMemories)
        m_memories.removeFirst();

    lk.unlock();
    scheduleSave();
    emit conversationCountChanged();
    emit memoryCountChanged();
    hAssistant() << "Mémoire importée depuis:" << path;
    return true;
}

// ═══════════════════════════════════════════════════════
//  Stats
// ═══════════════════════════════════════════════════════

QVariantMap AIMemoryManager::getStats() const
{
    QMutexLocker lk(&m_mutex);
    QVariantMap stats;
    stats["conversations"]     = m_conversations.size();
    stats["memories"]          = m_memories.size();
    stats["preferences"]       = m_userPreferences.size();
    stats["maxConversations"]  = m_maxConversations;
    stats["maxMemories"]       = m_maxMemories;
    stats["importanceThreshold"] = m_importanceThreshold;

    // Top tags
    QMap<QString, int> tagCount;
    double totalImportance = 0;
    for (const auto &mem : m_memories) {
        totalImportance += mem.importance;
        for (const QString &t : mem.tags)
            tagCount[t]++;
    }

    QVariantMap topTags;
    for (auto it = tagCount.cbegin(); it != tagCount.cend(); ++it)
        topTags[it.key()] = it.value();
    stats["topTags"] = topTags;

    stats["averageImportance"] = m_memories.isEmpty()
        ? 0.0 : totalImportance / m_memories.size();

    // Catégories
    QMap<QString, int> catCount;
    for (const auto &mem : m_memories)
        if (!mem.category.isEmpty()) catCount[mem.category]++;
    QVariantMap categories;
    for (auto it = catCount.cbegin(); it != catCount.cend(); ++it)
        categories[it.key()] = it.value();
    stats["categories"] = categories;

    return stats;
}

// ═══════════════════════════════════════════════════════
//  Nettoyage
// ═══════════════════════════════════════════════════════

void AIMemoryManager::clearAllMemory()
{
    {
        QMutexLocker lk(&m_mutex);
        m_conversations.clear();
        m_userPreferences.clear();
        m_memories.clear();
    }
    scheduleSave();
    emit conversationCountChanged();
    emit memoryCountChanged();
    hAssistant() << "Mémoire complète effacée";
}

void AIMemoryManager::clearConversationHistory()
{
    {
        QMutexLocker lk(&m_mutex);
        m_conversations.clear();
    }
    scheduleSave();
    emit conversationCountChanged();
    hAssistant() << "Historique conversations effacé";
}

void AIMemoryManager::clearMemories()
{
    {
        QMutexLocker lk(&m_mutex);
        m_memories.clear();
    }
    scheduleSave();
    emit memoryCountChanged();
    hAssistant() << "Souvenirs sémantiques effacés";
}

// ═══════════════════════════════════════════════════════
//  Config tuning
// ═══════════════════════════════════════════════════════

void AIMemoryManager::setMaxConversations(int n)  { m_maxConversations = qMax(10, n); }
void AIMemoryManager::setMaxMemories(int n)       { m_maxMemories = qMax(10, n); }
void AIMemoryManager::setImportanceThreshold(double t) { m_importanceThreshold = qBound(0.0, t, 1.0); }
void AIMemoryManager::setHalfLifeDays(double d)   { m_halfLifeMs = qMax(1.0, d) * 24.0 * 3600.0 * 1000.0; }

// ═══════════════════════════════════════════════════════
//  Semantic memory server (FAISS) — WebSocket bridge
// ═══════════════════════════════════════════════════════

void AIMemoryManager::initSemanticServer(const QString &url)
{
    if (m_semanticWs) {
        m_semanticWs->close();
        m_semanticWs->deleteLater();
    }
    m_semanticWs = new WebSocketClient("Memory", this);
    m_semanticWs->setReconnectParams(5000, 0, false);  // 5s fixed, infinite
    connect(m_semanticWs, &WebSocketClient::connected,
            this, &AIMemoryManager::onSemanticConnected);
    connect(m_semanticWs, &WebSocketClient::disconnected,
            this, &AIMemoryManager::onSemanticDisconnected);
    connect(m_semanticWs, &WebSocketClient::textReceived,
            this, &AIMemoryManager::onSemanticMessage);
    m_semanticWs->open(QUrl(url));
    hAssistant() << "Connecting to semantic memory server:" << url;
}

void AIMemoryManager::onSemanticConnected()
{
    hAssistant() << "Semantic memory server connected";
}

void AIMemoryManager::onSemanticDisconnected()
{
    hWarning(exoAssistant) << "Semantic memory server disconnected — fallback regex";
    // Reconnection automatique gérée par WebSocketClient
}

void AIMemoryManager::onSemanticMessage(const QString &msg)
{
    QJsonParseError jerr{};
    QJsonDocument doc = QJsonDocument::fromJson(msg.toUtf8(), &jerr);
    if (jerr.error != QJsonParseError::NoError) {
        hWarning(exoAssistant) << "AIMemoryManager: semantic JSON parse error"
                               << jerr.errorString() << "offset=" << jerr.offset
                               << "raw=" << msg.left(120);
        return;
    }
    if (!doc.isObject()) {
        hWarning(exoAssistant) << "AIMemoryManager: semantic payload not an object: " << msg.left(120);
        return;
    }
    QJsonObject obj = doc.object();
    QString type = obj["type"].toString();

    if (type == "search_result") {
        // Store results for synchronous retrieval
        m_pendingSemanticResults.clear();
        for (const auto &r : obj["results"].toArray()) {
            QJsonObject entry = r.toObject();
            QVariantMap vm;
            vm["id"]         = entry["id"].toString();
            vm["text"]       = entry["text"].toString();
            vm["importance"] = entry["importance"].toDouble();
            vm["score"]      = entry["similarity"].toDouble();
            vm["category"]   = entry["category"].toString();
            vm["source"]     = entry["source"].toString();
            // Convert tags
            QStringList tags;
            for (const auto &t : entry["tags"].toArray())
                tags << t.toString();
            vm["tags"] = QVariant(tags);
            m_pendingSemanticResults.append(vm);
        }
    } else if (type == "add_result") {
        hAssistant() << "Semantic server: memory added, id=" << obj["id"].toString();
    } else if (type == "error") {
        hWarning(exoAssistant) << "Semantic server error:" << obj["message"].toString();
    }
}

void AIMemoryManager::sendToSemanticServer(const QString &action, const QJsonObject &payload)
{
    if (!m_semanticWs || !m_semanticWs->isConnected()) return;
    QJsonObject msg;
    msg["action"] = action;
    for (auto it = payload.begin(); it != payload.end(); ++it)
        msg[it.key()] = it.value();
    m_semanticWs->sendJson(msg);
}

// ═══════════════════════════════════════════════════════
//  Persistance JSON — lecture / écriture atomique
// ═══════════════════════════════════════════════════════

void AIMemoryManager::loadFromFile()
{
    QString path = memoryFilePath();
    QFile file(path);

    if (!file.exists()) {
        hAssistant() << "Pas de fichier mémoire existant — démarrage à vide";
        return;
    }

    if (!file.open(QIODevice::ReadOnly)) {
        hWarning(exoAssistant) << "Impossible d'ouvrir:" << path;
        return;
    }

    QJsonParseError err;
    QJsonDocument doc = QJsonDocument::fromJson(file.readAll(), &err);
    file.close();

    if (err.error != QJsonParseError::NoError) {
        hWarning(exoAssistant) << "JSON corrompu, fallback vide —" << err.errorString();
        return;
    }

    QJsonObject root = doc.object();
    int version = root["version"].toInt(1);

    // ── Conversations ──
    m_conversations.clear();
    for (const auto &v : root["conversations"].toArray()) {
        QJsonObject o = v.toObject();
        ConversationEntry e;
        if (version >= 2) {
            e.timestamp = o["timestamp"].toInteger();
            e.user      = o["user"].toString();
            e.assistant = o["assistant"].toString();
        } else {
            // v1 compatibility
            e.user      = o["userMessage"].toString();
            e.assistant = o["assistantResponse"].toString();
            e.timestamp = QDateTime::fromString(
                              o["timestamp"].toString(), Qt::ISODate)
                              .toMSecsSinceEpoch();
        }
        if (!e.user.isEmpty())
            m_conversations.append(e);
    }

    // ── Preferences ──
    m_userPreferences.clear();
    QJsonObject prefsObj = root["preferences"].toObject();
    for (auto it = prefsObj.begin(); it != prefsObj.end(); ++it)
        m_userPreferences[it.key()] = it.value().toVariant();

    // ── Memories ──
    m_memories.clear();
    for (const auto &v : root["memories"].toArray())
        m_memories.append(jsonToMemory(v.toObject()));
}

void AIMemoryManager::scheduleSave()
{
    // Redémarre le timer (debounce)
    m_saveTimer->start();
}

void AIMemoryManager::saveToFile()
{
    QMutexLocker lk(&m_mutex);

    QString path = memoryFilePath();
    exo::safeio::ensureParentDir(path, "AIMemoryManager::saveToFile");

    // Écriture atomique : tmp → rename
    QString tmpPath = path + ".tmp";
    QFile tmpFile(tmpPath);
    if (!tmpFile.open(QIODevice::WriteOnly)) {
        hWarning(exoAssistant) << "Impossible d'écrire:" << tmpPath;
        return;
    }

    QJsonObject root;
    root["version"] = JSON_VERSION;

    // Conversations
    QJsonArray convArr;
    for (const auto &e : m_conversations) {
        QJsonObject o;
        o["timestamp"] = e.timestamp;
        o["user"]      = e.user;
        o["assistant"] = e.assistant;
        convArr.append(o);
    }
    root["conversations"] = convArr;

    // Preferences
    QJsonObject prefsObj;
    for (auto it = m_userPreferences.cbegin(); it != m_userPreferences.cend(); ++it)
        prefsObj[it.key()] = QJsonValue::fromVariant(it.value());
    root["preferences"] = prefsObj;

    // Memories
    QJsonArray memArr;
    for (const auto &m : m_memories)
        memArr.append(memoryToJson(m));
    root["memories"] = memArr;

    tmpFile.write(QJsonDocument(root).toJson());
    tmpFile.close();

    QFile::remove(path);
    if (!QFile::rename(tmpPath, path)) {
        hWarning(exoAssistant) << "Rename atomique échoué";
        QFile::remove(tmpPath);
    }
}

QString AIMemoryManager::memoryFilePath() const
{
    QString dataPath = qEnvironmentVariable("EXO_FAISS_DIR", QStringLiteral("D:/EXO/faiss/semantic_memory"));
    exo::safeio::ensureDir(dataPath, "AIMemoryManager::memoryFilePath");
    return dataPath + "/exa_memory.json";
}

// ═══════════════════════════════════════════════════════
//  Helpers internes
// ═══════════════════════════════════════════════════════

double AIMemoryManager::effectiveImportance(const MemoryEntry &m) const
{
    // Decay exponentiel : importance × exp(-Δt / demi-vie)
    qint64 now = QDateTime::currentMSecsSinceEpoch();
    double dt  = static_cast<double>(now - m.timestamp);
    double decay = std::exp(-dt * 0.693147 / m_halfLifeMs); // ln(2) ≈ 0.693147
    return m.importance * decay;
}

bool AIMemoryManager::isDuplicate(const QString &text) const
{
    // Comparaison insensible à la casse, seuil de similarité simple
    QString low = text.toLower().trimmed();
    for (const auto &mem : m_memories) {
        if (mem.text.toLower().trimmed() == low)
            return true;
    }
    return false;
}

QJsonObject AIMemoryManager::memoryToJson(const MemoryEntry &m)
{
    QJsonObject o;
    o["id"]         = m.id;
    o["text"]       = m.text;
    o["importance"] = m.importance;
    o["tags"]       = QJsonArray::fromStringList(m.tags);
    o["timestamp"]  = m.timestamp;
    o["source"]     = m.source;
    o["category"]   = m.category;
    return o;
}

MemoryEntry AIMemoryManager::jsonToMemory(const QJsonObject &obj)
{
    MemoryEntry m;
    m.id         = obj["id"].toString();
    m.text       = obj["text"].toString();
    m.importance = obj["importance"].toDouble(0.5);
    m.timestamp  = obj["timestamp"].toInteger();
    m.source     = obj["source"].toString("auto");
    m.category   = obj["category"].toString();

    for (const auto &t : obj["tags"].toArray())
        m.tags.append(t.toString());

    if (m.id.isEmpty())
        m.id = QUuid::createUuid().toString(QUuid::WithoutBraces);

    return m;
}