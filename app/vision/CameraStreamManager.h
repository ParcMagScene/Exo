#ifndef CAMERASTREAMMANAGER_H
#define CAMERASTREAMMANAGER_H

#include <QObject>
#include <QTimer>
#include <QImage>
#include <QMap>
#include <QVector>
#include <QVariantMap>
#include <QVariantList>
#include <qqml.h>

#include "VisionEnums.h"

// ─────────────────────────────────────────────────────
//  CameraStreamInfo — État d'un flux caméra
// ─────────────────────────────────────────────────────
struct CameraStreamInfo {
    QString cameraId;
    QString url;
    Vision::CameraState state = Vision::CameraState::Disconnected;
    int     width             = 0;
    int     height            = 0;
    double  fps               = 0.0;
    qint64  frameCount        = 0;
    qint64  errorCount        = 0;
    QString roomId;
    QString lastError;

    QVariantMap toVariant() const;
};

// ─────────────────────────────────────────────────────
//  CameraStreamManager — Gestion des flux vidéo
//  Abstraction : RTSP/RTMP/HTTP/fichier
//  Buffer circulaire, gestion FPS, reconnexion
// ─────────────────────────────────────────────────────

class CameraStreamManager : public QObject
{
    Q_OBJECT

    Q_PROPERTY(int activeCameras READ activeCameraCount NOTIFY cameraCountChanged)
    Q_PROPERTY(QVariantList cameraList READ cameraList NOTIFY cameraCountChanged)

public:
    explicit CameraStreamManager(QObject *parent = nullptr);
    ~CameraStreamManager() override;

    // ── Gestion caméras ──
    Q_INVOKABLE bool registerCamera(const QString &cameraId, const QString &url,
                                     const QString &roomId = QString());
    Q_INVOKABLE bool unregisterCamera(const QString &cameraId);
    Q_INVOKABLE bool openStream(const QString &cameraId);
    Q_INVOKABLE void closeStream(const QString &cameraId);
    Q_INVOKABLE void closeAllStreams();

    // ── Lecture frames ──
    QImage readFrame(const QString &cameraId);
    QImage lastFrame(const QString &cameraId) const;

    // ── Configuration ──
    Q_INVOKABLE void setTargetFps(const QString &cameraId, int fps);
    Q_INVOKABLE void setBufferSize(int frames);

    // ── État ──
    int activeCameraCount() const;
    QVariantList cameraList() const;
    Q_INVOKABLE QVariantMap getCameraInfo(const QString &cameraId) const;
    Q_INVOKABLE QStringList registeredCameraIds() const;
    Q_INVOKABLE bool isCameraActive(const QString &cameraId) const;

signals:
    void cameraCountChanged();
    void cameraStateChanged(const QString &cameraId, int state);
    void frameReady(const QString &cameraId, qint64 frameIndex);
    void cameraError(const QString &cameraId, const QString &error);
    void cameraConnected(const QString &cameraId);
    void cameraDisconnected(const QString &cameraId);

private:
    struct CameraStream {
        CameraStreamInfo info;
        QImage           lastFrame;
        QVector<QImage>  frameBuffer;
        int              bufferPos    = 0;
        int              targetFps    = Vision::kDefaultFps;
        QTimer          *captureTimer = nullptr;
    };

    void startCapture(const QString &cameraId);
    void stopCapture(const QString &cameraId);
    void simulateFrameCapture(const QString &cameraId);

    QMap<QString, CameraStream> m_streams;
    int m_bufferSize = Vision::kFrameBufferSize;
};

#endif // CAMERASTREAMMANAGER_H
