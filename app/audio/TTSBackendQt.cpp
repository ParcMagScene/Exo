#include "TTSBackendQt.h"
#include "TTSManager.h"

#include <QTextToSpeech>
#include <QEventLoop>
#include <QElapsedTimer>
#include <QTimer>

TTSBackendQt::TTSBackendQt(QObject *parent)
    : TTSBackend(parent)
{}

TTSBackendQt::~TTSBackendQt()
{
    if (m_tts) {
        // v5.2 memory audit : QTextToSpeech a des callbacks asynchrones du moteur
        // de synthèse. Un delete synchrone peut courir avec un stateChanged en vol.
        m_tts->stop();
        m_tts->disconnect(this);
        m_tts->deleteLater();
        m_tts = nullptr;
    }
}

void TTSBackendQt::init()
{
    m_tts = new QTextToSpeech(this);

    QVoice selected;
    int bestScore = -100000;
    int voiceCount = 0;
    for (const QVoice &v : m_tts->availableVoices()) {
        ++voiceCount;
        if (v.locale().language() != QLocale::French)
            continue;

        int score = 0;
        if (v.locale().territory() == QLocale::France) score += 40;
        const QString name = v.name();
        if (name.contains("French", Qt::CaseInsensitive)) score += 30;
        if (name.contains("fr-FR", Qt::CaseInsensitive)) score += 30;
        if (name.contains("Julie", Qt::CaseInsensitive)
            || name.contains("Hortense", Qt::CaseInsensitive)
            || name.contains("Denise", Qt::CaseInsensitive)
            || name.contains("Henri", Qt::CaseInsensitive)
            || name.contains("Eloise", Qt::CaseInsensitive)
            || name.contains("Remy", Qt::CaseInsensitive)) {
            score += 20;
        }
        if (name.contains("Multilingual", Qt::CaseInsensitive)) score -= 20;

        if (score > bestScore) {
            bestScore = score;
            selected = v;
        }
    }
    if (!selected.name().isEmpty())
        m_tts->setVoice(selected);

    emit voiceInfo(selected.name().isEmpty() ? "default" : selected.name(),
                   voiceCount);
}

bool TTSBackendQt::isAvailable() const
{
    return m_tts != nullptr;
}

bool TTSBackendQt::synthesize(const TTSRequest &req)
{
    if (!m_tts) return false;

    // Qt voices sound more natural with a conservative prosody range.
    const double qtPitch = std::clamp(static_cast<double>(req.prosody.pitch) * 0.25, -0.25, 0.20);
    const double qtRate  = std::clamp(static_cast<double>(req.prosody.rate)  * 0.35, -0.30, 0.20);

    m_tts->setPitch(qtPitch);
    m_tts->setRate(qtRate);
    m_tts->setVolume(1.0);

    emit started(req.text);

    m_tts->say(req.text);

    // Wait for completion via QEventLoop — no busy-wait, no processEvents
    QEventLoop loop;
    bool wasSpeaking = false;
    bool success = false;

    QTimer timeout;
    timeout.setSingleShot(true);
    timeout.setInterval(QT_TTS_TIMEOUT_MS);
    connect(&timeout, &QTimer::timeout, &loop, &QEventLoop::quit);

    QMetaObject::Connection stateConn = connect(
        m_tts, &QTextToSpeech::stateChanged,
        &loop, [&](QTextToSpeech::State state) {
            if (state == QTextToSpeech::Speaking) {
                wasSpeaking = true;
            } else if (wasSpeaking && state == QTextToSpeech::Ready) {
                success = true;
                loop.quit();
            } else if (state == QTextToSpeech::Error) {
                loop.quit();
            }
        });

    timeout.start();
    loop.exec();
    disconnect(stateConn);

    if (isCancelled()) {
        m_tts->stop();
        emit finished();
        return true;
    }

    if (success) {
        emit finished();
        return true;
    }

    m_tts->stop();
    return false;
}

void TTSBackendQt::cancel()
{
    if (m_tts)
        m_tts->stop();
}

void TTSBackendQt::setVoice(const QString &name)
{
    if (!m_tts) return;
    for (const QVoice &v : m_tts->availableVoices()) {
        if (v.name().compare(name, Qt::CaseInsensitive) == 0) {
            m_tts->setVoice(v);
            return;
        }
    }
}
