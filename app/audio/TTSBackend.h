#ifndef TTSBACKEND_H
#define TTSBACKEND_H

#include <QObject>
#include <QString>
#include <QByteArray>
#include <atomic>

struct TTSRequest;

// ─────────────────────────────────────────────────────
//  TTSBackend — abstract TTS engine interface
//
//  Each backend encapsulates one synthesis engine.
//  TTSWorker iterates backends in priority order.
// ─────────────────────────────────────────────────────
class TTSBackend : public QObject
{
    Q_OBJECT
public:
    explicit TTSBackend(QObject *parent = nullptr) : QObject(parent) {}
    ~TTSBackend() override = default;

    virtual QString name() const = 0;
    virtual bool isAvailable() const = 0;
    virtual bool synthesize(const TTSRequest &req) = 0;
    virtual void cancel() = 0;
    virtual void init() {}
    virtual void resetConnection() {}

    void setCancelled(std::atomic<bool> *flag) { m_cancelledRef = flag; }

protected:
    bool isCancelled() const { return m_cancelledRef && m_cancelledRef->load(); }

signals:
    void started(const QString &text);
    void chunk(const QByteArray &pcm);
    void finished();
    void error(const QString &msg);

private:
    std::atomic<bool> *m_cancelledRef = nullptr;
};

#endif // TTSBACKEND_H
