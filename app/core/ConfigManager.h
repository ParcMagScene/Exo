#pragma once

#include <QObject>
#include <QSettings>
#include <QString>
#include <QStringList>
#include <QVariantMap>
#include <QNetworkAccessManager>
#include <QNetworkReply>
#include <QHash>

// ═══════════════════════════════════════════════════════
//  ConfigManager v4 — Gestionnaire de configuration EXO
//
//  Couches de priorité (haute → basse) :
//    1. Variables d'environnement (.env chargé au démarrage)
//    2. Préférences utilisateur (user_config.ini)
//    3. Configuration par défaut (assistant.conf)
//
//  API unifiée :
//    getString / getInt / getDouble / getBool
//    setUserValue  (écrit toujours dans user_config)
//
//  Fonctions spécialisées :
//    Géolocalisation IP, thèmes UI, clés API
// ═══════════════════════════════════════════════════════

class ConfigManager : public QObject
{
    Q_OBJECT
    Q_PROPERTY(bool loaded READ isLoaded NOTIFY configurationLoaded)
    Q_PROPERTY(QString currentTheme READ getCurrentTheme
               WRITE setCurrentTheme NOTIFY themeChanged)

public:
    explicit ConfigManager(QObject *parent = nullptr);
    ~ConfigManager() override;

    // ── Initialisation ───────────────────────────────
    bool loadConfiguration(const QString &configPath = "config/assistant.conf");
    bool isLoaded() const { return m_isLoaded; }

    // ── API générique (priorité .env > user > conf) ──
    Q_INVOKABLE QString getString(const QString &section,
                                  const QString &key,
                                  const QString &defaultValue = {}) const;
    Q_INVOKABLE int     getInt(const QString &section,
                               const QString &key,
                               int defaultValue = 0) const;
    Q_INVOKABLE double  getDouble(const QString &section,
                                  const QString &key,
                                  double defaultValue = 0.0) const;
    Q_INVOKABLE bool    getBool(const QString &section,
                                const QString &key,
                                bool defaultValue = false) const;

    // Écriture (toujours dans user_config)
    Q_INVOKABLE void setUserValue(const QString &section,
                                  const QString &key,
                                  const QVariant &value);

    // ── Raccourcis API Keys ──────────────────────────
    Q_INVOKABLE QString getClaudeApiKey() const;
    Q_INVOKABLE QString getClaudeModel() const;
    Q_INVOKABLE QString getClaudeFallbackModel() const;
    Q_INVOKABLE QString getWeatherApiKey() const;

    // ── Raccourcis paramètres courants ────────────────
    Q_INVOKABLE QString getWeatherCity() const;
    Q_INVOKABLE QString getWakeWord() const;
    Q_INVOKABLE int     getWeatherUpdateInterval() const;
    double  getVoiceRate() const;
    double  getVoicePitch() const;
    double  getVoiceVolume() const;
    QString getVoiceLanguage() const;
    QString getLogLevel() const;
    bool    isDebugEnabled() const;

    // ── Setters (délèguent à setUserValue) ───────────
    Q_INVOKABLE void setClaudeApiKey(const QString &key);
    Q_INVOKABLE void setClaudeModel(const QString &model);
    Q_INVOKABLE void setWeatherApiKey(const QString &key);
    Q_INVOKABLE void setWeatherCity(const QString &city);
    Q_INVOKABLE void setWakeWord(const QString &word);
    Q_INVOKABLE void setWeatherUpdateInterval(int minutes);

    // ── Géolocalisation ──────────────────────────────
    Q_INVOKABLE void detectLocation();
    Q_INVOKABLE bool isLocationDetectionEnabled() const;
    Q_INVOKABLE void setLocationDetectionEnabled(bool enabled);
    Q_INVOKABLE QString getCurrentLocation() const;

    // ── Thèmes ───────────────────────────────────────
    Q_INVOKABLE QStringList  getAvailableThemes() const;
    Q_INVOKABLE QString      getCurrentTheme() const;
    Q_INVOKABLE void         setCurrentTheme(const QString &themeName);
    Q_INVOKABLE QVariantMap  getThemeColors(const QString &themeName) const;
    Q_INVOKABLE void         saveCustomTheme(const QString &themeName,
                                             const QVariantMap &colors);
    Q_INVOKABLE void         deleteCustomTheme(const QString &themeName);
    Q_INVOKABLE bool         isCustomTheme(const QString &themeName) const;
    // ── Paramètres STT / TTS / VAD ──────────────────
    Q_INVOKABLE QString getSTTServerUrl() const;
    Q_INVOKABLE QString getTTSServerUrl() const;
    Q_INVOKABLE QString getGUIServerUrl() const;
    Q_INVOKABLE QString getSTTModel() const;
    Q_INVOKABLE QString getSTTLanguage() const;
    Q_INVOKABLE int     getSTTBeamSize() const;
    Q_INVOKABLE QString getTTSVoice() const;
    Q_INVOKABLE QString getTTSLanguage() const;
    Q_INVOKABLE QString getTTSStyle() const;
    Q_INVOKABLE QString getVADBackend() const;
    Q_INVOKABLE double  getVADThreshold() const;

    Q_INVOKABLE void setSTTServerUrl(const QString &url);
    Q_INVOKABLE void setTTSServerUrl(const QString &url);
    Q_INVOKABLE void setTTSVoice(const QString &voice);
    Q_INVOKABLE QString getTTSEngine() const;
    Q_INVOKABLE void    setTTSEngine(const QString &engine);
    // ── Sauvegarde ───────────────────────────────────
    Q_INVOKABLE bool saveConfiguration();

signals:
    void configurationLoaded();
    void configurationError(const QString &error);
    void weatherConfigChanged(const QString &city, const QString &apiKey);
    void locationDetected(const QString &city, const QString &country);
    void locationDetectionError(const QString &error);
    void themeChanged(const QString &themeName, const QVariantMap &colors);

private:
    // ── .env ─────────────────────────────────────────
    void loadDotEnv(const QString &path);
    QString envLookup(const QString &section, const QString &key) const;

    // ── Thèmes ───────────────────────────────────────
    void initializeDefaultThemes();
    QVariantMap createTheme(const QString &primary,
                            const QString &secondary,
                            const QString &accent,
                            const QString &background,
                            const QString &surface,
                            const QString &text) const;

    // ── Helpers internes ─────────────────────────────
    void setDefaultValues();

    // ── Stockage ─────────────────────────────────────
    QSettings *m_settings     = nullptr;  // assistant.conf
    QSettings *m_userSettings = nullptr;  // user_config.ini
    QHash<QString, QString> m_envVars;    // .env chargées
    bool m_isLoaded = false;
    QString m_configPath;

    // ── Géolocalisation ──────────────────────────────
    QNetworkAccessManager *m_networkManager = nullptr;
    QString m_detectedLocation;

    // ── Thèmes ───────────────────────────────────────
    QVariantMap m_defaultThemes;

    // ── Constantes ───────────────────────────────────
    static constexpr const char *DEFAULT_WAKE_WORD       = "Exo";
    static constexpr const char *DEFAULT_WEATHER_CITY    = "Paris";
    static constexpr const char *DEFAULT_CLAUDE_MODEL    = "claude-opus-4.7";
    // LLM LOCK 2026-05-16 : pas de fallback. Constante alignee sur le modele
    // canonique pour qu'un eventuel appel residuel a setFallbackModel(...) ne
    // puisse pas introduire de divergence.
    static constexpr const char *FALLBACK_CLAUDE_MODEL   = "claude-opus-4.7";
    static constexpr const char *CLAUDE_DEPRECATION_NOTICE = "claude-opus-4.7 only — no fallback";
    static constexpr const char *DEFAULT_VOICE_LANGUAGE  = "fr-FR";
    static constexpr const char *DEFAULT_LOG_LEVEL       = "Info";
    static constexpr double      DEFAULT_VOICE_RATE      = -0.3;
    static constexpr double      DEFAULT_VOICE_PITCH     = -0.1;
    static constexpr double      DEFAULT_VOICE_VOLUME    = 0.9;
    static constexpr int         DEFAULT_WEATHER_INTERVAL = 600000;

    // ── STT / TTS / VAD defaults ─────────────────────
    static constexpr const char *DEFAULT_STT_SERVER_URL  = "ws://localhost:8766";
    static constexpr const char *DEFAULT_TTS_SERVER_URL  = "ws://localhost:8767";
    static constexpr const char *DEFAULT_GUI_SERVER_URL  = "ws://localhost:8765";
    static constexpr const char *DEFAULT_STT_MODEL       = "small";
    static constexpr const char *DEFAULT_STT_LANGUAGE    = "fr";
    static constexpr int         DEFAULT_STT_BEAM_SIZE   = 1;
    static constexpr const char *DEFAULT_TTS_VOICE       = "fr_denise";
    static constexpr const char *DEFAULT_TTS_ENGINE      = "orpheus_fr_cuda";
    static constexpr const char *DEFAULT_VAD_BACKEND     = "hybrid";
    static constexpr double      DEFAULT_VAD_THRESHOLD   = 0.45;
};