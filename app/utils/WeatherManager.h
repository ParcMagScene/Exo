#pragma once

#include <QObject>
#include <QNetworkAccessManager>
#include <QNetworkReply>
#include <QJsonObject>
#include <QJsonDocument>
#include <QTimer>
#include <QDateTime>

/**
 * @brief Gestionnaire météorologique intégré
 * 
 * Fournit des données météorologiques en temps réel via OpenWeatherMap API :
 * - Conditions météorologiques actuelles
 * - Prévisions sur 5 jours
 * - Conseils vestimentaires automatiques
 * - Alertes météorologiques
 */
class WeatherManager : public QObject
{
    Q_OBJECT
    Q_PROPERTY(QString currentWeather READ currentWeather NOTIFY weatherUpdated)
    Q_PROPERTY(QString temperature READ temperature NOTIFY weatherUpdated)
    Q_PROPERTY(QString humidity READ humidity NOTIFY weatherUpdated)
    Q_PROPERTY(QString windSpeed READ windSpeed NOTIFY weatherUpdated)
    Q_PROPERTY(QString description READ description NOTIFY weatherUpdated)
    Q_PROPERTY(QString clothingAdvice READ clothingAdvice NOTIFY weatherUpdated)
    Q_PROPERTY(bool isLoading READ isLoading NOTIFY loadingStateChanged)
    Q_PROPERTY(QString city READ city WRITE setCity NOTIFY cityChanged)

public:
    explicit WeatherManager(QObject *parent = nullptr);
    ~WeatherManager();

    // Getters pour les propriétés QML
    QString currentWeather() const { return m_currentWeather; }
    QString temperature() const { return m_temperature; }
    QString humidity() const { return m_humidity; }
    QString windSpeed() const { return m_windSpeed; }
    QString description() const { return m_description; }
    QString clothingAdvice() const { return m_clothingAdvice; }
    bool isLoading() const { return m_isLoading; }
    QString city() const { return m_city; }

    void setCity(const QString &city);

    // Configuration
    void setApiKey(const QString &apiKey);
    void initialize();

public slots:
    // Méthodes appelables depuis QML et VoicePipeline
    Q_INVOKABLE void updateWeather();
    Q_INVOKABLE void getForecast();
    Q_INVOKABLE QString getWeatherSummary();
    Q_INVOKABLE QString getClothingAdvice();

signals:
    void weatherUpdated();
    void forecastReceived(const QJsonObject &forecast);
    void loadingStateChanged();
    void cityChanged();
    void weatherError(const QString &error);
    void weatherResponse(const QString &response);

private slots:
    void onWeatherReplyFinished();
    void onForecastReplyFinished();
    void updateWeatherAutomatically();

private:
    // Méthodes utilitaires
    void parseWeatherData(const QJsonObject &data);
    void parseForecastData(const QJsonObject &data);
    QString generateClothingAdvice(double temp, const QString &condition, double windSpeed, int humidity);
    QString translateWeatherCondition(const QString &condition);
    QString formatTemperature(double temp);
    QString getWeatherIcon(const QString &condition);
    
    // Gestion des requêtes réseau
    void makeWeatherRequest(const QString &endpoint);
    QString buildApiUrl(const QString &endpoint) const;

    // Membres de données
    QNetworkAccessManager *m_networkManager;
    QTimer *m_updateTimer;
    
    QString m_apiKey;
    QString m_city;
    QString m_currentWeather;
    QString m_temperature;
    QString m_humidity;
    QString m_windSpeed;
    QString m_description;
    QString m_clothingAdvice;
    bool m_isLoading;
    
    // Données météo complètes
    QJsonObject m_currentData;
    QJsonObject m_forecastData;
    
    // Configuration
    static constexpr int UPDATE_INTERVAL_MS = 600000; // 10 minutes
    static constexpr const char* API_BASE_URL = "https://api.openweathermap.org/data/2.5";
};