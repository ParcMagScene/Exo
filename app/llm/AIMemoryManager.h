#ifndef AIMEMORYMANAGER_H
#define AIMEMORYMANAGER_H

#include <QObject>
#include <QStringList>
#include <QVariantMap>
#include <QVariantList>
#include <QJsonObject>
#include <QJsonArray>
#include <QJsonDocument>
#include <QUuid>
#include <QElapsedTimer>
#include <QTimer>
#include <QMutex>
#include <cmath>

#include "core/WebSocketClient.h"

// ═══════════════════════════════════════════════════════
//  AIMemoryManager — Mémoire intelligente 3 couches
//  + Bridge optionnel vers memory_server.py (FAISS)
//
//  1) Conversations : buffer circulaire historique
//  2) Préférences   : clé/valeur persistantes
//  3) Souvenirs     : mémoire sémantique avec importance,
//                     tags, récence, détection auto
//     → Si memory_server connecté : recherche vectorielle FAISS
//     → Sinon : recherche regex locale (fallback)
//
//  Persistance : JSON atomique dans $EXO_FAISS_DIR (D:/EXO/faiss/semantic_memory)
//  Format v2 : { version, conversations, preferences, memories }
// ═══════════════════════════════════════════════════════

// ─────────────────────────────────────────────────────
//  ConversationEntry — un échange user ↔ assistant
// ─────────────────────────────────────────────────────
struct ConversationEntry
{
    qint64  timestamp = 0;   // ms since epoch
    QString user;
    QString assistant;
};

// ─────────────────────────────────────────────────────
//  MemoryEntry — un souvenir sémantique
// ─────────────────────────────────────────────────────
struct MemoryEntry
{
    QString     id;                  // UUID
    QString     text;
    double      importance = 0.5;    // 0.0 – 1.0
    QStringList tags;
    qint64      timestamp  = 0;     // ms since epoch
    QString     source;              // "auto" / "user" / "system"
    QString     category;            // "identité", "préférence", …
};

// ─────────────────────────────────────────────────────
//  AIMemoryManager
// ─────────────────────────────────────────────────────
class AIMemoryManager : public QObject
{
    Q_OBJECT
    Q_PROPERTY(bool memoryEnabled READ isMemoryEnabled
               WRITE setMemoryEnabled NOTIFY memoryEnabledChanged)
    Q_PROPERTY(int conversationCount READ conversationCount
               NOTIFY conversationCountChanged)
    Q_PROPERTY(int memoryCount READ memoryCount
               NOTIFY memoryCountChanged)

public:
    explicit AIMemoryManager(QObject *parent = nullptr);
    ~AIMemoryManager() override;

    // ── Conversations ────────────────────────────────
    Q_INVOKABLE void addConversation(const QString &userMessage,
                                     const QString &assistantResponse);
    Q_INVOKABLE QString getConversationContext(int maxEntries = 5) const;
    Q_INVOKABLE QStringList getRecentConversations(int count = 10) const;

    // ── Préférences ──────────────────────────────────
    Q_INVOKABLE void updateUserPreference(const QString &key,
                                          const QVariant &value);
    Q_INVOKABLE QVariant getUserPreference(
        const QString &key,
        const QVariant &defaultValue = {}) const;

    // ── Mémoire sémantique ───────────────────────────
    Q_INVOKABLE void addMemory(const QString &text,
                               double importance,
                               const QStringList &tags,
                               const QString &category = {},
                               const QString &source = "auto");

    Q_INVOKABLE QVariantList searchMemories(const QString &query,
                                            int maxResults = 5) const;

    Q_INVOKABLE QVariantList getMemoriesByTag(const QString &tag,
                                              int maxResults = 20) const;

    Q_INVOKABLE QVariantList getAllMemories() const;

    Q_INVOKABLE bool removeMemory(const QString &id);

    // ── Contexte Claude ──────────────────────────────
    Q_INVOKABLE QString buildClaudeContext(int maxConversations = 5,
                                           int maxMemories = 5) const;

    // ── Détection automatique ────────────────────────
    void analyzeAndMaybeStore(const QString &userMessage);

    // ── Import / Export ──────────────────────────────
    Q_INVOKABLE bool exportToFile(const QString &path) const;
    Q_INVOKABLE bool importFromFile(const QString &path);

    // ── Stats ────────────────────────────────────────
    Q_INVOKABLE QVariantMap getStats() const;

    // ── Nettoyage ────────────────────────────────────
    Q_INVOKABLE void clearAllMemory();
    Q_INVOKABLE void clearConversationHistory();
    Q_INVOKABLE void clearMemories();

    // ── État ─────────────────────────────────────────
    bool isMemoryEnabled() const { return m_enabled; }
    void setMemoryEnabled(bool on);
    int  conversationCount() const { return m_conversations.size(); }
    int  memoryCount() const { return m_memories.size(); }

    // ── Config tuning ────────────────────────────────
    void setMaxConversations(int n);
    void setMaxMemories(int n);
    void setImportanceThreshold(double t);
    void setHalfLifeDays(double d);

    // ── Semantic memory server (FAISS) ───────────────
    void initSemanticServer(const QString &url = "ws://localhost:8771");
    bool isSemanticConnected() const { return m_semanticWs && m_semanticWs->isConnected(); }

signals:
    void memoryEnabledChanged();
    void conversationCountChanged();
    void memoryCountChanged();
    void conversationAdded(const QString &userMessage,
                           const QString &assistantResponse);
    void memoryAdded(const QString &id, const QString &text);
    void userPreferenceUpdated(const QString &key,
                               const QVariant &value);

private:
    // ── Persistance ──────────────────────────────────
    void loadFromFile();
    void scheduleSave();
    void saveToFile();
    QString memoryFilePath() const;

    // ── Helpers internes ─────────────────────────────
    double effectiveImportance(const MemoryEntry &m) const;
    bool   isDuplicate(const QString &text) const;
    static QJsonObject memoryToJson(const MemoryEntry &m);
    static MemoryEntry jsonToMemory(const QJsonObject &obj);
    void sendToSemanticServer(const QString &action, const QJsonObject &payload);

private slots:
    void onSemanticConnected();
    void onSemanticDisconnected();
    void onSemanticMessage(const QString &msg);

private:
    bool m_enabled = true;
    QList<ConversationEntry> m_conversations;
    QVariantMap              m_userPreferences;
    QList<MemoryEntry>       m_memories;

    // ── Limites ──────────────────────────────────────
    int    m_maxConversations    = 200;
    int    m_maxMemories         = 500;
    double m_importanceThreshold = 0.4;
    double m_halfLifeMs          = 30.0 * 24 * 3600 * 1000.0; // 30 jours

    // ── Save debounce ────────────────────────────────
    QTimer *m_saveTimer = nullptr;
    mutable QMutex m_mutex;

    // ── Semantic memory server (FAISS + SentenceTransformers) ─
    WebSocketClient *m_semanticWs = nullptr;
    QVariantList m_pendingSemanticResults; // last search results from server

    static constexpr int SAVE_DEBOUNCE_MS = 2000;
    static constexpr int JSON_VERSION     = 2;
};

#endif // AIMEMORYMANAGER_H