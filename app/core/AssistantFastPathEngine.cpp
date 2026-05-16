#include "AssistantFastPathEngine.h"

#include "ConfigManager.h"
#include "LogManager.h"
#include "MetricsManager.h"
#include "PipelineEvent.h"
#include "LatencyMetrics.h"
#include "audio/VoicePipeline.h"
#include "utils/WeatherManager.h"

#include <QJsonDocument>
#include <QJsonObject>
#include <QDate>
#include <QElapsedTimer>
#include <QLocale>
#include <QRegularExpression>
#include <QTime>

AssistantFastPathEngine::AssistantFastPathEngine(QObject *parent)
    : QObject(parent)
{
}

void AssistantFastPathEngine::configure(ConfigManager *configManager,
                                        WeatherManager *weatherManager,
                                        VoicePipeline *voicePipeline)
{
    m_configManager = configManager;
    m_weatherManager = weatherManager;
    m_voicePipeline = voicePipeline;
}

bool AssistantFastPathEngine::tryHandleMessage(const QString &message, QString *responseOut)
{
    if (!responseOut) {
        return false;
    }

    const QString low = message.toLower();
    QElapsedTimer fpTimer;
    fpTimer.start();

    QString response;

    bool isTime = low.contains(QLatin1String("quelle heure"))
               || (low.contains(QLatin1String("heure")) && low.contains(QLatin1String("il est")));
    bool isDate = low.contains(QLatin1String("quel jour"))
               || low.contains(QLatin1String("quelle date"))
               || low.contains(QLatin1String("on est quel"));

    if (isTime && !isDate) {
        QString t = QTime::currentTime().toString(QStringLiteral("H 'heures' mm"));
        response = QStringLiteral("Il est %1.").arg(t);
    } else if (isDate && !isTime) {
        QLocale fr(QStringLiteral("fr_FR"));
        QDate today = QDate::currentDate();
        response = QStringLiteral("Nous sommes le %1.").arg(
            fr.toString(today, QStringLiteral("dddd d MMMM yyyy")));
    } else if (isDate && isTime) {
        QLocale fr(QStringLiteral("fr_FR"));
        QDate today = QDate::currentDate();
        QString t = QTime::currentTime().toString(QStringLiteral("H 'heures' mm"));
        response = QStringLiteral("Nous sommes le %1, il est %2.")
            .arg(fr.toString(today, QStringLiteral("dddd d MMMM yyyy")), t);
    }

    if (response.isEmpty()) {
        bool isWeather = low.contains(QLatin1String("météo"))
                      || low.contains(QLatin1String("quel temps"))
                      || (low.contains(QLatin1String("température")) && low.contains(QLatin1String("dehors")))
                      || (low.contains(QLatin1String("fait")) && low.contains(QLatin1String("dehors")));

        // Si l'utilisateur cite explicitement une ville (à/de/pour/sur/en X),
        // on laisse le LLM appeler get_weather(city=...) au lieu de servir
        // la météo cachée pour la ville par défaut.
        static const QRegularExpression reExplicitCity(
            QStringLiteral("\\b(?:à|a|de|du|pour|sur|en|vers)\\s+([A-ZÀ-Ý][\\wÀ-ÿ'’\\-]{1,})"),
            QRegularExpression::UseUnicodePropertiesOption);
        const bool mentionsExplicitCity = isWeather && reExplicitCity.match(message).hasMatch();

        if (isWeather && !mentionsExplicitCity && m_weatherManager
            && !m_weatherManager->description().isEmpty()) {
            QString city = m_configManager ? m_configManager->getWeatherCity()
                                           : QStringLiteral("ici");
            response = QStringLiteral("À %1, il fait %2 degrés, %3.")
                .arg(city)
                .arg(m_weatherManager->temperature())
                .arg(m_weatherManager->description().toLower());
        }
    }

    if (response.isEmpty()) {
        bool turnOn = low.contains(QLatin1String("allume"));
        bool turnOff = low.contains(QLatin1String("éteins"))
                    || low.contains(QLatin1String("éteindre"));

        if (turnOn || turnOff) {
            static const QRegularExpression reOn(
                QStringLiteral("allume\\s+(?:la |le |les |l')?(.+)"),
                QRegularExpression::CaseInsensitiveOption);
            static const QRegularExpression reOff(
                QStringLiteral("(?:éteins|éteindre)\\s+(?:la |le |les |l')?(.+)"),
                QRegularExpression::CaseInsensitiveOption);

            QRegularExpressionMatch m = turnOn ? reOn.match(low) : reOff.match(low);
            if (m.hasMatch()) {
                QString entity = m.captured(1).trimmed();
                while (!entity.isEmpty() && (entity.endsWith('.') || entity.endsWith('!')))
                    entity.chop(1);

                QJsonObject haCommand;
                haCommand[QStringLiteral("type")] = QStringLiteral("ha_command");
                haCommand[QStringLiteral("tool")] = turnOn
                    ? QStringLiteral("ha_turn_on") : QStringLiteral("ha_turn_off");
                QJsonObject args;
                args[QStringLiteral("entity_id")] = entity;
                haCommand[QStringLiteral("arguments")] = args;

                if (m_voicePipeline) {
                    m_voicePipeline->sendWebSocketMessage(
                        QString::fromUtf8(QJsonDocument(haCommand).toJson(
                            QJsonDocument::Compact)));
                }

                response = turnOn
                    ? QStringLiteral("J'allume %1.").arg(entity)
                    : QStringLiteral("J'éteins %1.").arg(entity);
            }
        }
    }

    if (response.isEmpty()) {
        return false;
    }

    qint64 fpMs = fpTimer.elapsed();
    hAssistant() << "[FastPath]" << fpMs << "ms ->" << response.left(60);
    MetricsManager::instance()->increment(QStringLiteral("assistant.fast_path_hits"));
    MetricsManager::instance()->recordValue(QStringLiteral("assistant.fast_path_latency_ms"), fpMs);

    PIPELINE_EVENT(PipelineModule::Orchestrator, EventType::ResponseReceived,
                   QJsonObject{{QStringLiteral("fast_path"), true},
                               {QStringLiteral("latency_ms"), fpMs}});

    auto *lm = LatencyMetrics::instance();
    lm->markLlmRequest();
    lm->markLlmFirstToken();
    lm->markLlmComplete();

    *responseOut = response;
    return true;
}
