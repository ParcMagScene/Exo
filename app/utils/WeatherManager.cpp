#include "WeatherManager.h"
#include <QNetworkRequest>
#include <QNetworkReply>
#include <QUrl>
#include <QUrlQuery>
#include <QJsonArray>
#include <QJsonValue>
#include <QDebug>
#include <QLocale>

WeatherManager::WeatherManager(QObject *parent)
    : QObject(parent)
    , m_networkManager(new QNetworkAccessManager(this))
    , m_updateTimer(new QTimer(this))
    , m_city("Paris") // Ville par défaut
    , m_isLoading(false)
{
    // Configuration du timer de mise à jour automatique
    m_updateTimer->setInterval(UPDATE_INTERVAL_MS);
    m_updateTimer->setSingleShot(false);
    connect(m_updateTimer, &QTimer::timeout, this, &WeatherManager::updateWeatherAutomatically);
    
    qDebug() << "🌤️ WeatherManager initialisé pour" << m_city;
}

WeatherManager::~WeatherManager()
{
    if (m_updateTimer->isActive()) {
        m_updateTimer->stop();
    }
}

void WeatherManager::setApiKey(const QString &apiKey)
{
    m_apiKey = apiKey;
    qDebug() << "🔑 Clé API météo configurée";
}

void WeatherManager::setCity(const QString &city)
{
    if (m_city != city) {
        m_city = city;
        emit cityChanged();
        qDebug() << "🏙️ Ville changée pour :" << m_city;
        
        // Mise à jour immédiate avec la nouvelle ville
        updateWeather();
    }
}

void WeatherManager::initialize()
{
    if (m_apiKey.isEmpty()) {
        qWarning() << "⚠️ Clé API OpenWeatherMap manquante !";
        emit weatherError("Clé API météo manquante. Configurez-la dans assistant.conf");
        return;
    }
    
    qDebug() << "🌍 Initialisation WeatherManager pour" << m_city;
    
    // Première mise à jour
    updateWeather();
    
    // Démarrage des mises à jour automatiques
    m_updateTimer->start();
    
    qDebug() << "⏰ Mises à jour météo automatiques activées (toutes les" << (UPDATE_INTERVAL_MS/60000) << "min)";
}

void WeatherManager::updateWeather()
{
    if (m_apiKey.isEmpty()) {
        emit weatherError("Clé API météo manquante");
        return;
    }
    
    if (m_isLoading) {
        qDebug() << "🔄 Mise à jour météo déjà en cours...";
        return;
    }
    
    m_isLoading = true;
    emit loadingStateChanged();
    
    qDebug() << "🌤️ Récupération météo actuelle pour" << m_city;
    makeWeatherRequest("weather");
}

void WeatherManager::getForecast()
{
    if (m_apiKey.isEmpty()) {
        emit weatherError("Clé API météo manquante");
        return;
    }
    
    qDebug() << "📅 Récupération prévisions météo pour" << m_city;
    makeWeatherRequest("forecast");
}

QString WeatherManager::getWeatherSummary()
{
    if (m_currentWeather.isEmpty()) {
        return "Données météo non disponibles. Vérifiez votre connexion internet.";
    }
    
    QString summary = QString("À %1, il fait actuellement %2 avec %3. ")
                        .arg(m_city, m_temperature, m_description);
    
    if (!m_windSpeed.isEmpty()) {
        summary += QString("Le vent souffle à %1. ").arg(m_windSpeed);
    }
    
    if (!m_humidity.isEmpty()) {
        summary += QString("L'humidité est de %1. ").arg(m_humidity);
    }
    
    // Ajout des conseils vestimentaires
    if (!m_clothingAdvice.isEmpty()) {
        summary += m_clothingAdvice;
    }
    
    return summary;
}

QString WeatherManager::getClothingAdvice()
{
    return m_clothingAdvice;
}

void WeatherManager::makeWeatherRequest(const QString &endpoint)
{
    QString url = buildApiUrl(endpoint);
    QNetworkRequest request;
    request.setUrl(QUrl(url));
    request.setRawHeader("User-Agent", "EXO Assistant v4.2");
    
    QNetworkReply *reply = m_networkManager->get(request);
    
    if (endpoint == "weather") {
        connect(reply, &QNetworkReply::finished, this, &WeatherManager::onWeatherReplyFinished);
    } else if (endpoint == "forecast") {
        connect(reply, &QNetworkReply::finished, this, &WeatherManager::onForecastReplyFinished);
    }
    
    qDebug() << "🌐 Requête météo envoyée :" << url;
}

QString WeatherManager::buildApiUrl(const QString &endpoint) const
{
    QUrl url(QString("%1/%2").arg(API_BASE_URL, endpoint));
    QUrlQuery query;
    
    query.addQueryItem("q", m_city);
    query.addQueryItem("appid", m_apiKey);
    query.addQueryItem("units", "metric"); // Celsius
    query.addQueryItem("lang", "fr"); // Descriptions en français
    
    url.setQuery(query);
    return url.toString();
}

void WeatherManager::fetchWeatherFor(const QString &city,
                                     std::function<void(const QJsonObject &)> callback)
{
    if (!callback) {
        return;
    }
    if (city.trimmed().isEmpty()) {
        callback(QJsonObject{
            {QStringLiteral("status"),  QStringLiteral("error")},
            {QStringLiteral("message"), QStringLiteral("Ville non spécifiée")}});
        return;
    }
    if (m_apiKey.isEmpty()) {
        callback(QJsonObject{
            {QStringLiteral("status"),  QStringLiteral("error")},
            {QStringLiteral("message"), QStringLiteral("Clé API météo manquante")}});
        return;
    }

    QUrl url(QString("%1/weather").arg(API_BASE_URL));
    QUrlQuery query;
    query.addQueryItem(QStringLiteral("q"), city);
    query.addQueryItem(QStringLiteral("appid"), m_apiKey);
    query.addQueryItem(QStringLiteral("units"), QStringLiteral("metric"));
    query.addQueryItem(QStringLiteral("lang"), QStringLiteral("fr"));
    url.setQuery(query);

    QNetworkRequest request;
    request.setUrl(url);
    request.setRawHeader("User-Agent", "EXO Assistant v4.2");

    QNetworkReply *reply = m_networkManager->get(request);
    QString cityCopy = city;
    connect(reply, &QNetworkReply::finished, this,
            [reply, cityCopy, callback]() {
        QJsonObject out;
        if (reply->error() == QNetworkReply::NoError) {
            const QByteArray data = reply->readAll();
            const QJsonDocument doc = QJsonDocument::fromJson(data);
            if (!doc.isNull() && doc.isObject()) {
                const QJsonObject json = doc.object();
                const QJsonObject main = json.value(QStringLiteral("main")).toObject();
                const QJsonArray  weatherArr = json.value(QStringLiteral("weather")).toArray();
                const QJsonObject weather0 = weatherArr.isEmpty()
                    ? QJsonObject() : weatherArr.first().toObject();
                const QJsonObject wind = json.value(QStringLiteral("wind")).toObject();

                out[QStringLiteral("status")]      = QStringLiteral("success");
                out[QStringLiteral("city")]        = json.value(QStringLiteral("name")).toString(cityCopy);
                out[QStringLiteral("temperature")] = QString::number(main.value(QStringLiteral("temp")).toDouble(), 'f', 1);
                out[QStringLiteral("description")] = weather0.value(QStringLiteral("description")).toString();
                out[QStringLiteral("humidity")]    = QString::number(main.value(QStringLiteral("humidity")).toInt());
                out[QStringLiteral("wind_speed")]  = QString::number(wind.value(QStringLiteral("speed")).toDouble(), 'f', 1);
            } else {
                out[QStringLiteral("status")]  = QStringLiteral("error");
                out[QStringLiteral("message")] = QStringLiteral("Réponse météo invalide");
            }
        } else {
            out[QStringLiteral("status")]  = QStringLiteral("error");
            out[QStringLiteral("message")] = QStringLiteral("Erreur réseau météo : %1")
                                                .arg(reply->errorString());
        }
        callback(out);
        reply->deleteLater();
    });
}

void WeatherManager::onWeatherReplyFinished()
{
    QNetworkReply *reply = qobject_cast<QNetworkReply*>(sender());
    if (!reply) return;
    
    m_isLoading = false;
    emit loadingStateChanged();
    
    if (reply->error() == QNetworkReply::NoError) {
        QByteArray data = reply->readAll();
        QJsonDocument doc = QJsonDocument::fromJson(data);
        
        if (!doc.isNull() && doc.isObject()) {
            QJsonObject json = doc.object();
            parseWeatherData(json);
            emit weatherUpdated();
            
            QString response = getWeatherSummary();
            emit weatherResponse(response);
            
            qDebug() << "✅ Météo mise à jour avec succès";
        } else {
            qWarning() << "❌ Erreur parsing JSON météo";
            emit weatherError("Erreur de format des données météo");
        }
    } else {
        QString error = QString("Erreur réseau météo : %1").arg(reply->errorString());
        qWarning() << "❌" << error;
        emit weatherError(error);
    }
    
    reply->deleteLater();
}

void WeatherManager::onForecastReplyFinished()
{
    QNetworkReply *reply = qobject_cast<QNetworkReply*>(sender());
    if (!reply) return;
    
    if (reply->error() == QNetworkReply::NoError) {
        QByteArray data = reply->readAll();
        QJsonDocument doc = QJsonDocument::fromJson(data);
        
        if (!doc.isNull() && doc.isObject()) {
            QJsonObject json = doc.object();
            parseForecastData(json);
            emit forecastReceived(json);
            
            qDebug() << "✅ Prévisions météo récupérées";
        }
    } else {
        qWarning() << "❌ Erreur prévisions météo :" << reply->errorString();
    }
    
    reply->deleteLater();
}

void WeatherManager::parseWeatherData(const QJsonObject &data)
{
    m_currentData = data;
    
    // Température
    QJsonObject main = data["main"].toObject();
    double temp = main["temp"].toDouble();
    int humidity = main["humidity"].toInt();
    
    m_temperature = formatTemperature(temp);
    m_humidity = QString("%1%").arg(humidity);
    
    // Conditions météo
    QJsonArray weather = data["weather"].toArray();
    if (!weather.isEmpty()) {
        QJsonObject weatherObj = weather[0].toObject();
        QString condition = weatherObj["main"].toString();
        QString description = weatherObj["description"].toString();
        
        m_description = translateWeatherCondition(description);
        m_currentWeather = QString("%1 - %2").arg(condition, m_description);
    }
    
    // Vent
    QJsonObject wind = data["wind"].toObject();
    if (wind.contains("speed")) {
        double windSpeed = wind["speed"].toDouble() * 3.6; // m/s vers km/h
        m_windSpeed = QString("%1 km/h").arg(qRound(windSpeed));
    }
    
    // Génération des conseils vestimentaires
    m_clothingAdvice = generateClothingAdvice(temp, m_description, 
                                             wind["speed"].toDouble() * 3.6, humidity);
    
    qDebug() << "🌡️ Température :" << m_temperature;
    qDebug() << "🌤️ Conditions :" << m_description;
    qDebug() << "👔 Conseils :" << m_clothingAdvice;
}

void WeatherManager::parseForecastData(const QJsonObject &data)
{
    m_forecastData = data;
    // Pour l'instant, on stocke juste les données
    // L'interface QML pourra les utiliser plus tard
}

QString WeatherManager::generateClothingAdvice(double temp, const QString &condition, double windSpeed, int humidity)
{
    QString advice;
    
    // Conseils basés sur la température
    if (temp < 0) {
        advice = "Il fait très froid ! Portez une doudoune, bonnet, écharpe et gants.";
    } else if (temp < 10) {
        advice = "Il fait froid. Un manteau chaud et une écharpe sont recommandés.";
    } else if (temp < 15) {
        advice = "Il fait frais. Une veste ou un pull seront parfaits.";
    } else if (temp < 20) {
        advice = "Température agréable. Un pull léger ou une veste fine suffisent.";
    } else if (temp < 25) {
        advice = "Il fait bon ! Un t-shirt ou une chemise légère sont idéaux.";
    } else if (temp < 30) {
        advice = "Il fait chaud. Privilégiez des vêtements légers et respirants.";
    } else {
        advice = "Il fait très chaud ! Portez des vêtements très légers et restez hydraté.";
    }
    
    // Conseils spécifiques aux conditions météo
    if (condition.contains("pluie") || condition.contains("orage")) {
        advice += " N'oubliez pas votre parapluie !";
    } else if (condition.contains("neige")) {
        advice += " Attention à la neige, chaussures antidérapantes recommandées.";
    } else if (condition.contains("soleil") || condition.contains("clair")) {
        if (temp > 20) {
            advice += " Pensez aux lunettes de soleil et à la crème solaire.";
        }
    }
    
    // Conseils sur le vent
    if (windSpeed > 20) {
        advice += " Vent fort, évitez les parapluies fragiles.";
    }
    
    // Conseils sur l'humidité
    if (humidity > 80) {
        advice += " Humidité élevée, privilégiez des tissus respirants.";
    }
    
    return advice;
}

QString WeatherManager::translateWeatherCondition(const QString &condition)
{
    // OpenWeatherMap renvoie déjà en français avec lang=fr
    // Mais on peut ajouter des traductions personnalisées si nécessaire
    return condition;
}

QString WeatherManager::formatTemperature(double temp)
{
    return QString("%1°C").arg(qRound(temp));
}

QString WeatherManager::getWeatherIcon(const QString &condition)
{
    // Retourne des emojis ou des noms d'icônes basés sur les conditions
    if (condition.contains("soleil") || condition.contains("clear")) return "☀️";
    if (condition.contains("nuage")) return "☁️";
    if (condition.contains("pluie")) return "🌧️";
    if (condition.contains("orage")) return "⛈️";
    if (condition.contains("neige")) return "❄️";
    if (condition.contains("brouillard")) return "🌫️";
    
    return "🌤️"; // Par défaut
}

void WeatherManager::updateWeatherAutomatically()
{
    qDebug() << "⏰ Mise à jour automatique de la météo";
    updateWeather();
}