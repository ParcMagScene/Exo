#include "ConfigManager.h"
#include "LogManager.h"
#include "utils/SafeIO.h"

#include <QCoreApplication>
#include <QDir>
#include <QFile>
#include <QFileInfo>
#include <QStandardPaths>
#include <QTextStream>
#include <QNetworkRequest>
#include <QNetworkReply>
#include <QJsonDocument>
#include <QJsonObject>
#include <QUrl>
#include <QSet>
#include <QTimer>
#include <QRegularExpression>

// ═══════════════════════════════════════════════════════
//  Construction / Destruction
// ═══════════════════════════════════════════════════════

ConfigManager::ConfigManager(QObject *parent)
    : QObject(parent)
{
    initializeDefaultThemes();

    // Force user settings into D:/EXO/config (no AppData leak)
    const QString ssdRoot = qEnvironmentVariable("EXO_SSD_ROOT", QStringLiteral("D:/EXO"));
    const QString cfgDir  = QStringLiteral("D:/EXO/config");
    exo::safeio::ensureDir(cfgDir, "ConfigManager::ctor");
    m_userSettings = new QSettings(cfgDir + QStringLiteral("/user_config.ini"),
                                   QSettings::IniFormat, this);
    m_networkManager = new QNetworkAccessManager(this);

    hConfig() << "ConfigManager v4 créé — user settings:"
              << m_userSettings->fileName();
}

ConfigManager::~ConfigManager() = default;

// ═══════════════════════════════════════════════════════
//  Chargement .env
// ═══════════════════════════════════════════════════════

void ConfigManager::loadDotEnv(const QString &path)
{
    QFile file(path);
    if (!file.open(QIODevice::ReadOnly | QIODevice::Text)) return;

    hConfig() << "Chargement .env:" << path;

    QTextStream in(&file);
    while (!in.atEnd()) {
        QString line = in.readLine().trimmed();
        if (line.isEmpty() || line.startsWith('#')) continue;

        int eq = line.indexOf('=');
        if (eq <= 0) continue;

        QString key   = line.left(eq).trimmed();
        QString value = line.mid(eq + 1).trimmed();

        // Supprimer les guillemets englobants
        if ((value.startsWith('"') && value.endsWith('"'))
            || (value.startsWith('\'') && value.endsWith('\''))) {
            value = value.mid(1, value.length() - 2);
        }

        m_envVars.insert(key, value);
    }
    file.close();

    hConfig() << m_envVars.size() << "variables .env chargées";
}

QString ConfigManager::envLookup(const QString &section, const QString &key) const
{
    // Mapping section/key → variable d'environnement
    static const QHash<QString, QString> envMap = {
        {"Claude/api_key",           "CLAUDE_API_KEY"},
        {"Claude/model",             "CLAUDE_MODEL"},
        {"OpenWeatherMap/api_key",   "OWM_API_KEY"},
        {"OpenWeatherMap/city",      "OWM_CITY"},
        {"Voice/wake_word",          "EXO_WAKE_WORD"},
        {"Logging/level",            "EXO_LOG_LEVEL"},
    };

    QString compound = section + "/" + key;
    QString envName = envMap.value(compound);

    if (envName.isEmpty()) return {};

    // 1. .env chargé
    QString val = m_envVars.value(envName);
    if (!val.isEmpty()) return val;

    // 2. Variable d'environnement système
    val = qEnvironmentVariable(envName.toUtf8().constData());
    return val;
}

// ═══════════════════════════════════════════════════════
//  Initialisation
// ═══════════════════════════════════════════════════════

bool ConfigManager::loadConfiguration(const QString &configPath)
{
    m_configPath = configPath;

    // Charger .env depuis la racine du projet
    QDir appDir(QCoreApplication::applicationDirPath());
    loadDotEnv(appDir.absoluteFilePath(".env"));
    // Chercher aussi 2 niveaux au-dessus (build/Debug → racine)
    loadDotEnv(appDir.absoluteFilePath("../../.env"));

    // Charger assistant.conf
    QString fullPath = appDir.absoluteFilePath(configPath);

    // Resolve config path robustly across run modes (build folder vs project root).
    if (!QFileInfo(configPath).isAbsolute() && !QFile::exists(fullPath)) {
        const QString exeDir = QCoreApplication::applicationDirPath();
        const QString cwd = QDir::currentPath();
        const QStringList candidates = {
            QDir(exeDir).absoluteFilePath(configPath),
            QDir(exeDir).absoluteFilePath("../" + configPath),
            QDir(exeDir).absoluteFilePath("../../" + configPath),
            QDir(exeDir).absoluteFilePath("../../../" + configPath),
            QDir(cwd).absoluteFilePath(configPath),
            QStringLiteral("D:/EXO/config/assistant.conf")
        };
        for (const QString &candidate : candidates) {
            if (QFile::exists(candidate)) {
                fullPath = candidate;
                break;
            }
        }
    }

    if (!QFile::exists(fullPath)) {
        hWarning(exoConfig) << "Config introuvable:" << fullPath
                              << "— valeurs par défaut";
        setDefaultValues();
        // Ne pas return false — on peut fonctionner avec les defaults
    } else {
        if (m_settings) {
            m_settings->deleteLater();
            m_settings = nullptr;
        }

        m_settings = new QSettings(fullPath, QSettings::IniFormat, this);

        if (m_settings->status() != QSettings::NoError) {
            hWarning(exoConfig) << "Erreur lecture config:" << fullPath;
            emit configurationError("Impossible de charger le fichier de configuration");
            return false;
        }
    }

    m_isLoaded = true;

    // Diagnostic clés essentielles
    if (getClaudeApiKey().isEmpty())
        hWarning(exoConfig) << "Clé API Claude manquante";
    if (getWeatherApiKey().isEmpty())
        hWarning(exoConfig) << "Clé API météo manquante";

    hConfig() << "Configuration chargée — modèle Claude:" << getClaudeModel()
              << "— ville:" << getWeatherCity();

    // Géolocalisation automatique
    if (isLocationDetectionEnabled()) {
        hConfig() << "Géolocalisation automatique activée";
        QTimer::singleShot(1500, this, &ConfigManager::detectLocation);
    }

    emit configurationLoaded();
    return true;
}

void ConfigManager::setDefaultValues()
{
    if (m_settings) {
        m_settings->deleteLater();
        m_settings = nullptr;
    }
    // Force default settings into D:/EXO/config (no AppData leak)
    const QString ssdRoot2 = qEnvironmentVariable("EXO_SSD_ROOT", QStringLiteral("D:/EXO"));
    const QString cfgDir2  = ssdRoot2 + QStringLiteral("/config");
    exo::safeio::ensureDir(cfgDir2, "ConfigManager::setDefaultValues");
    m_settings = new QSettings(cfgDir2 + QStringLiteral("/default.ini"),
                               QSettings::IniFormat, this);
    m_isLoaded = true;
}

// ═══════════════════════════════════════════════════════
//  API générique — priorité .env > user > conf
// ═══════════════════════════════════════════════════════

QString ConfigManager::getString(const QString &section,
                                  const QString &key,
                                  const QString &defaultValue) const
{
    // 1. .env / variables d'environnement
    QString env = envLookup(section, key);
    if (!env.isEmpty()) return env;

    // 2. Préférences utilisateur
    QString compound = section + "/" + key;
    if (m_userSettings && m_userSettings->contains(compound))
        return m_userSettings->value(compound).toString();

    // 3. Config par défaut (assistant.conf)
    if (m_settings)
        return m_settings->value(compound, defaultValue).toString();

    return defaultValue;
}

int ConfigManager::getInt(const QString &section, const QString &key,
                           int defaultValue) const
{
    QString val = getString(section, key);
    if (val.isEmpty()) return defaultValue;
    bool ok;
    int result = val.toInt(&ok);
    return ok ? result : defaultValue;
}

double ConfigManager::getDouble(const QString &section, const QString &key,
                                 double defaultValue) const
{
    QString val = getString(section, key);
    if (val.isEmpty()) return defaultValue;
    bool ok;
    double result = val.toDouble(&ok);
    return ok ? result : defaultValue;
}

bool ConfigManager::getBool(const QString &section, const QString &key,
                             bool defaultValue) const
{
    QString val = getString(section, key).toLower();
    if (val.isEmpty()) return defaultValue;
    if (val == "true" || val == "1" || val == "yes" || val == "on") return true;
    if (val == "false" || val == "0" || val == "no" || val == "off") return false;
    return defaultValue;
}

void ConfigManager::setUserValue(const QString &section,
                                  const QString &key,
                                  const QVariant &value)
{
    if (!m_userSettings) return;
    m_userSettings->setValue(section + "/" + key, value);
    m_userSettings->sync();
    hConfig() << "User value:" << section << "/" << key << "=" << value.toString();
}

// ═══════════════════════════════════════════════════════
//  Raccourcis API Keys
// ═══════════════════════════════════════════════════════

QString ConfigManager::getClaudeApiKey() const
{
    QString key = getString("Claude", "api_key");
    if (key.startsWith("${")) return {};
    return key;
}

QString ConfigManager::getClaudeModel() const
{
    // LLM LOCK 2026-05-16 : retourne toujours le modele canonique, peu importe
    // ce que le fichier utilisateur contient. Refus loggue UNE seule fois par
    // valeur invalide pour eviter le spam.
    const QString fromConfig = getString("Claude", "model", DEFAULT_CLAUDE_MODEL);
    if (fromConfig != QLatin1String(DEFAULT_CLAUDE_MODEL)) {
        static QSet<QString> s_warned;
        if (!s_warned.contains(fromConfig)) {
            s_warned.insert(fromConfig);
            hConfig() << "[LLM] Refus : seul claude-opus-4.7 est autorisé (config:" << fromConfig << ")";
        }
    }
    return QString::fromLatin1(DEFAULT_CLAUDE_MODEL);
}

QString ConfigManager::getClaudeFallbackModel() const
{
    // LLM LOCK 2026-05-16 : pas de fallback, on retourne le canonique.
    return QString::fromLatin1(DEFAULT_CLAUDE_MODEL);
}

QString ConfigManager::getWeatherApiKey() const
{
    QString key = getString("OpenWeatherMap", "api_key");
    if (key.startsWith("${")) return {};
    return key;
}

// ═══════════════════════════════════════════════════════
//  Raccourcis paramètres courants
// ═══════════════════════════════════════════════════════

QString ConfigManager::getWeatherCity() const
{
    return getString("OpenWeatherMap", "city", DEFAULT_WEATHER_CITY);
}

int ConfigManager::getWeatherUpdateInterval() const
{
    return getInt("OpenWeatherMap", "update_interval", DEFAULT_WEATHER_INTERVAL);
}

QString ConfigManager::getWakeWord() const
{
    return getString("Voice", "wake_word", DEFAULT_WAKE_WORD);
}

double ConfigManager::getVoiceRate() const
{
    return getDouble("Voice", "voice_rate", DEFAULT_VOICE_RATE);
}

double ConfigManager::getVoicePitch() const
{
    return getDouble("Voice", "voice_pitch", DEFAULT_VOICE_PITCH);
}

double ConfigManager::getVoiceVolume() const
{
    return getDouble("Voice", "voice_volume", DEFAULT_VOICE_VOLUME);
}

QString ConfigManager::getVoiceLanguage() const
{
    return getString("Voice", "language", DEFAULT_VOICE_LANGUAGE);
}

QString ConfigManager::getLogLevel() const
{
    return getString("Logging", "level", DEFAULT_LOG_LEVEL);
}

bool ConfigManager::isDebugEnabled() const
{
    return getBool("Logging", "debug_enabled", true);
}

// ═══════════════════════════════════════════════════════
//  Setters (délèguent à setUserValue)
// ═══════════════════════════════════════════════════════

void ConfigManager::setClaudeApiKey(const QString &key)
{
    setUserValue("Claude", "api_key", key);
}

void ConfigManager::setClaudeModel(const QString &model)
{
    // LLM LOCK 2026-05-16 : on force la valeur canonique au stockage. Si l'UI
    // ou un service tente d'ecrire autre chose, on remplace silencieusement.
    if (model != QLatin1String(DEFAULT_CLAUDE_MODEL)) {
        hConfig() << "[LLM] Refus : seul claude-opus-4.7 est autorisé (setClaudeModel:" << model << ")";
    }
    setUserValue("Claude", "model", QString::fromLatin1(DEFAULT_CLAUDE_MODEL));
}

void ConfigManager::setWeatherApiKey(const QString &key)
{
    setUserValue("OpenWeatherMap", "api_key", key);
    emit weatherConfigChanged(getWeatherCity(), key);
}

void ConfigManager::setWeatherCity(const QString &city)
{
    setUserValue("OpenWeatherMap", "city", city);
    emit weatherConfigChanged(city, getWeatherApiKey());
}

void ConfigManager::setWakeWord(const QString &word)
{
    setUserValue("Voice", "wake_word", word);
}

void ConfigManager::setWeatherUpdateInterval(int minutes)
{
    setUserValue("OpenWeatherMap", "update_interval",
                 QString::number(minutes * 60000));
}

// ═══════════════════════════════════════════════════════
//  STT / TTS / VAD params
// ═══════════════════════════════════════════════════════

QString ConfigManager::getSTTServerUrl() const
{
    return getString("STT", "server_url", DEFAULT_STT_SERVER_URL);
}

QString ConfigManager::getTTSServerUrl() const
{
    return getString("TTS", "server_url", DEFAULT_TTS_SERVER_URL);
}

QString ConfigManager::getGUIServerUrl() const
{
    return getString("Server", "websocket_url", DEFAULT_GUI_SERVER_URL);
}

QString ConfigManager::getSTTModel() const
{
    return getString("STT", "model", DEFAULT_STT_MODEL);
}

QString ConfigManager::getSTTLanguage() const
{
    return getString("STT", "language", DEFAULT_STT_LANGUAGE);
}

int ConfigManager::getSTTBeamSize() const
{
    return getInt("STT", "beam_size", DEFAULT_STT_BEAM_SIZE);
}

QString ConfigManager::getTTSVoice() const
{
    const QString raw = getString("TTS", "voice", DEFAULT_TTS_VOICE).trimmed().toLower();
    // Patch anti-XTTS : toute voix XTTS heritee est remappee vers "orpheus".
    if (raw == QLatin1String("pierre") || raw == QLatin1String("amelie")
        || raw == QLatin1String("marie")) {
        return QStringLiteral("orpheus");
    }
    return raw.isEmpty() ? QStringLiteral("orpheus") : raw;
}

QString ConfigManager::getTTSLanguage() const
{
    return getString("TTS", "language", "fr");
}

QString ConfigManager::getTTSStyle() const
{
    return getString("TTS", "style", "neutral");
}

QString ConfigManager::getVADBackend() const
{
    return getString("VAD", "backend", DEFAULT_VAD_BACKEND);
}

double ConfigManager::getVADThreshold() const
{
    return getDouble("VAD", "threshold", DEFAULT_VAD_THRESHOLD);
}

void ConfigManager::setSTTServerUrl(const QString &url)
{
    setUserValue("STT", "server_url", url);
}

void ConfigManager::setTTSServerUrl(const QString &url)
{
    setUserValue("TTS", "server_url", url);
}

void ConfigManager::setTTSVoice(const QString &voice)
{
    QString safe = voice.trimmed().toLower();
    // Patch anti-XTTS : on n'autorise jamais la persistance d'une voix XTTS.
    if (safe == QLatin1String("pierre") || safe == QLatin1String("amelie")
        || safe == QLatin1String("marie") || safe.isEmpty()) {
        safe = QStringLiteral("orpheus");
    }
    setUserValue("TTS", "voice", safe);
}

QString ConfigManager::getTTSEngine() const
{
    return getString("TTS", "engine", DEFAULT_TTS_ENGINE);
}

void ConfigManager::setTTSEngine(const QString &engine)
{
    setUserValue("TTS", "engine", engine);
    hConfig() << "TTS engine changé:" << engine;
}

// ═══════════════════════════════════════════════════════
//  Sauvegarde
// ═══════════════════════════════════════════════════════

bool ConfigManager::saveConfiguration()
{
    if (!m_userSettings) {
        hWarning(exoConfig) << "Aucune configuration utilisateur à sauvegarder";
        return false;
    }

    m_userSettings->sync();

    if (m_userSettings->status() != QSettings::NoError) {
        hWarning(exoConfig) << "Erreur sauvegarde préférences utilisateur";
        return false;
    }

    hConfig() << "Préférences utilisateur sauvegardées:"
              << m_userSettings->fileName();
    return true;
}

// ═══════════════════════════════════════════════════════
//  Géolocalisation
// ═══════════════════════════════════════════════════════

void ConfigManager::detectLocation()
{
    if (!m_networkManager) {
        emit locationDetectionError("Service de géolocalisation non disponible");
        return;
    }

    hConfig() << "Détection de localisation en cours...";

    QUrl url("https://ipapi.co/json/");
    QNetworkRequest request(url);
    request.setHeader(QNetworkRequest::UserAgentHeader, "EXO-Assistant/4.0");

    QNetworkReply *reply = m_networkManager->get(request);

    connect(reply, &QNetworkReply::finished, this, [this, reply]() {
        reply->deleteLater();

        if (reply->error() != QNetworkReply::NoError) {
            hWarning(exoConfig) << "Erreur géolocalisation:"
                                  << reply->errorString();
            emit locationDetectionError(reply->errorString());
            return;
        }

        QJsonParseError parseErr;
        QJsonDocument doc = QJsonDocument::fromJson(reply->readAll(), &parseErr);

        if (parseErr.error != QJsonParseError::NoError) {
            emit locationDetectionError(parseErr.errorString());
            return;
        }

        QJsonObject obj = doc.object();

        if (obj.contains("error")) {
            emit locationDetectionError(obj["reason"].toString());
            return;
        }

        QString city    = obj["city"].toString();
        QString region  = obj["region"].toString();
        QString country = obj["country_name"].toString();

        m_detectedLocation = city;
        if (!region.isEmpty() && region != city)
            m_detectedLocation += ", " + region;

        hConfig() << "Localisation détectée:" << m_detectedLocation
                  << "— pays:" << country;

        if (isLocationDetectionEnabled()) {
            // Ne pas écraser une ville configurée manuellement par l'utilisateur
            QString currentCity = getWeatherCity();
            if (currentCity.isEmpty() || currentCity == DEFAULT_WEATHER_CITY)
                setWeatherCity(city);
        }

        emit locationDetected(city, country);
    });
}

bool ConfigManager::isLocationDetectionEnabled() const
{
    if (m_userSettings)
        return m_userSettings->value("Location/auto_detection", false).toBool();
    return false;
}

void ConfigManager::setLocationDetectionEnabled(bool enabled)
{
    setUserValue("Location", "auto_detection", enabled);
    if (enabled) detectLocation();
}

QString ConfigManager::getCurrentLocation() const
{
    return m_detectedLocation;
}

// ═══════════════════════════════════════════════════════
//  Thèmes
// ═══════════════════════════════════════════════════════

void ConfigManager::initializeDefaultThemes()
{
    m_defaultThemes["EXO Original"] = createTheme(
        "#00BCD4", "#0097A7", "#FF9800", "#121212", "#1E1E1E", "#FFFFFF");
    m_defaultThemes["Neon Gaming"] = createTheme(
        "#E91E63", "#9C27B0", "#00E676", "#0D0D0D", "#1A1A1A", "#00E676");
    m_defaultThemes["Ocean Blue"] = createTheme(
        "#2196F3", "#1976D2", "#FFC107", "#0F1419", "#1A2332", "#E3F2FD");
    m_defaultThemes["Sunset Orange"] = createTheme(
        "#FF5722", "#D84315", "#FFEB3B", "#1C0A00", "#2D1B0E", "#FFF3E0");
    m_defaultThemes["Forest Green"] = createTheme(
        "#4CAF50", "#388E3C", "#FF9800", "#0D1B0F", "#1B2F1D", "#E8F5E8");
    m_defaultThemes["Purple Night"] = createTheme(
        "#9C27B0", "#7B1FA2", "#E91E63", "#190A1F", "#2D1B3D", "#F3E5F5");
}

QVariantMap ConfigManager::createTheme(const QString &primary,
                                       const QString &secondary,
                                       const QString &accent,
                                       const QString &background,
                                       const QString &surface,
                                       const QString &text) const
{
    return {
        {"primary", primary}, {"secondary", secondary},
        {"accent", accent},   {"background", background},
        {"surface", surface}, {"text", text}
    };
}

QStringList ConfigManager::getAvailableThemes() const
{
    QStringList themes = m_defaultThemes.keys();

    if (m_userSettings) {
        m_userSettings->beginGroup("CustomThemes");
        const QStringList custom = m_userSettings->childGroups();
        m_userSettings->endGroup();
        for (const QString &t : custom)
            themes.append(t + " (Personnalisé)");
    }

    return themes;
}

QString ConfigManager::getCurrentTheme() const
{
    if (m_userSettings)
        return m_userSettings->value("Appearance/current_theme", "EXO Original").toString();
    return QStringLiteral("EXO Original");
}

void ConfigManager::setCurrentTheme(const QString &themeName)
{
    if (!m_userSettings) return;
    m_userSettings->setValue("Appearance/current_theme", themeName);
    m_userSettings->sync();

    QVariantMap colors = getThemeColors(themeName);
    emit themeChanged(themeName, colors);

    hConfig() << "Thème changé:" << themeName;
}

QVariantMap ConfigManager::getThemeColors(const QString &themeName) const
{
    QString clean = themeName;
    clean.remove(" (Personnalisé)");

    if (m_defaultThemes.contains(clean))
        return m_defaultThemes[clean].toMap();

    if (m_userSettings) {
        m_userSettings->beginGroup("CustomThemes/" + clean);
        QVariantMap c;
        c["primary"]    = m_userSettings->value("primary",    "#00BCD4").toString();
        c["secondary"]  = m_userSettings->value("secondary",  "#0097A7").toString();
        c["accent"]     = m_userSettings->value("accent",     "#FF9800").toString();
        c["background"] = m_userSettings->value("background", "#121212").toString();
        c["surface"]    = m_userSettings->value("surface",    "#1E1E1E").toString();
        c["text"]       = m_userSettings->value("text",       "#FFFFFF").toString();
        m_userSettings->endGroup();
        return c;
    }

    return m_defaultThemes.value("EXO Original").toMap();
}

void ConfigManager::saveCustomTheme(const QString &themeName,
                                     const QVariantMap &colors)
{
    if (!m_userSettings || themeName.isEmpty()) return;

    m_userSettings->beginGroup("CustomThemes/" + themeName);
    for (const QString &k : {"primary","secondary","accent","background","surface","text"})
        m_userSettings->setValue(k, colors.value(k, "#000000").toString());
    m_userSettings->endGroup();
    m_userSettings->sync();

    hConfig() << "Thème personnalisé sauvegardé:" << themeName;
}

void ConfigManager::deleteCustomTheme(const QString &themeName)
{
    if (!m_userSettings || themeName.isEmpty()) return;

    QString clean = themeName;
    clean.remove(" (Personnalisé)");

    m_userSettings->beginGroup("CustomThemes");
    m_userSettings->remove(clean);
    m_userSettings->endGroup();
    m_userSettings->sync();

    hConfig() << "Thème supprimé:" << clean;
}

bool ConfigManager::isCustomTheme(const QString &themeName) const
{
    return themeName.contains("(Personnalisé)")
        || (!m_defaultThemes.contains(themeName) && !themeName.isEmpty());
}