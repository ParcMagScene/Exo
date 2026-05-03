#include "CameraStreamManager.h"
#include <QDebug>
#include <QRandomGenerator>
#include <QPainter>

// ═════════════════════════════════════════════════════
//  CameraStreamInfo
// ═════════════════════════════════════════════════════

QVariantMap CameraStreamInfo::toVariant() const
{
    return {
        {"cameraId", cameraId}, {"url", url},
        {"state", static_cast<int>(state)},
        {"width", width}, {"height", height},
        {"fps", fps}, {"frameCount", static_cast<qlonglong>(frameCount)},
        {"errorCount", static_cast<qlonglong>(errorCount)},
        {"roomId", roomId}, {"lastError", lastError}
    };
}

// ═════════════════════════════════════════════════════
//  CameraStreamManager
// ═════════════════════════════════════════════════════

CameraStreamManager::CameraStreamManager(QObject *parent)
    : QObject(parent)
{}

CameraStreamManager::~CameraStreamManager()
{
    closeAllStreams();
}

bool CameraStreamManager::registerCamera(const QString &cameraId, const QString &url,
                                           const QString &roomId)
{
    if (cameraId.isEmpty() || url.isEmpty()) return false;
    if (m_streams.contains(cameraId)) return false;

    CameraStream cs;
    cs.info.cameraId = cameraId;
    cs.info.url      = url;
    cs.info.roomId   = roomId;
    cs.info.state    = Vision::CameraState::Disconnected;
    cs.frameBuffer.resize(m_bufferSize);
    m_streams.insert(cameraId, cs);

    emit cameraCountChanged();
    qDebug() << "[CameraStreamManager] Caméra enregistrée:" << cameraId << "→" << url;
    return true;
}

bool CameraStreamManager::unregisterCamera(const QString &cameraId)
{
    if (!m_streams.contains(cameraId)) return false;
    closeStream(cameraId);
    m_streams.remove(cameraId);
    emit cameraCountChanged();
    return true;
}

bool CameraStreamManager::openStream(const QString &cameraId)
{
    auto it = m_streams.find(cameraId);
    if (it == m_streams.end()) return false;

    auto &cs = it.value();
    if (cs.info.state == Vision::CameraState::Streaming) return true;

    cs.info.state = Vision::CameraState::Connecting;
    emit cameraStateChanged(cameraId, static_cast<int>(cs.info.state));

    // Simulation : ouverture réussie immédiate
    // En production : FFmpeg avformat_open_input / avformat_find_stream_info
    cs.info.width  = 1920;
    cs.info.height = 1080;
    cs.info.fps    = cs.targetFps;
    cs.info.state  = Vision::CameraState::Streaming;

    emit cameraStateChanged(cameraId, static_cast<int>(cs.info.state));
    emit cameraConnected(cameraId);

    startCapture(cameraId);
    qDebug() << "[CameraStreamManager] Stream ouvert:" << cameraId;
    return true;
}

void CameraStreamManager::closeStream(const QString &cameraId)
{
    auto it = m_streams.find(cameraId);
    if (it == m_streams.end()) return;

    auto &cs = it.value();
    stopCapture(cameraId);
    cs.info.state = Vision::CameraState::Disconnected;
    emit cameraStateChanged(cameraId, static_cast<int>(cs.info.state));
    emit cameraDisconnected(cameraId);
}

void CameraStreamManager::closeAllStreams()
{
    for (auto it = m_streams.begin(); it != m_streams.end(); ++it)
        closeStream(it.key());
}

QImage CameraStreamManager::readFrame(const QString &cameraId)
{
    auto it = m_streams.find(cameraId);
    if (it == m_streams.end()) return {};
    return it.value().lastFrame;
}

QImage CameraStreamManager::lastFrame(const QString &cameraId) const
{
    auto it = m_streams.find(cameraId);
    if (it == m_streams.end()) return {};
    return it.value().lastFrame;
}

void CameraStreamManager::setTargetFps(const QString &cameraId, int fps)
{
    auto it = m_streams.find(cameraId);
    if (it == m_streams.end()) return;
    it.value().targetFps = qBound(1, fps, 60);
    if (it.value().captureTimer && it.value().captureTimer->isActive())
        it.value().captureTimer->setInterval(1000 / it.value().targetFps);
}

void CameraStreamManager::setBufferSize(int frames)
{
    m_bufferSize = qBound(1, frames, 300);
}

int CameraStreamManager::activeCameraCount() const
{
    int count = 0;
    for (auto it = m_streams.cbegin(); it != m_streams.cend(); ++it)
        if (it.value().info.state == Vision::CameraState::Streaming) ++count;
    return count;
}

QVariantList CameraStreamManager::cameraList() const
{
    QVariantList list;
    for (auto it = m_streams.cbegin(); it != m_streams.cend(); ++it)
        list.append(it.value().info.toVariant());
    return list;
}

QVariantMap CameraStreamManager::getCameraInfo(const QString &cameraId) const
{
    auto it = m_streams.find(cameraId);
    if (it == m_streams.end()) return {};
    return it.value().info.toVariant();
}

QStringList CameraStreamManager::registeredCameraIds() const
{
    return m_streams.keys();
}

bool CameraStreamManager::isCameraActive(const QString &cameraId) const
{
    auto it = m_streams.find(cameraId);
    if (it == m_streams.end()) return false;
    return it.value().info.state == Vision::CameraState::Streaming;
}

// ── Capture timer ──

void CameraStreamManager::startCapture(const QString &cameraId)
{
    auto it = m_streams.find(cameraId);
    if (it == m_streams.end()) return;

    auto &cs = it.value();
    if (!cs.captureTimer) {
        cs.captureTimer = new QTimer(this);
        connect(cs.captureTimer, &QTimer::timeout, this, [this, cameraId]() {
            simulateFrameCapture(cameraId);
        });
    }
    cs.captureTimer->start(1000 / cs.targetFps);
}

void CameraStreamManager::stopCapture(const QString &cameraId)
{
    auto it = m_streams.find(cameraId);
    if (it == m_streams.end()) return;
    if (it.value().captureTimer) {
        it.value().captureTimer->stop();
    }
}

void CameraStreamManager::simulateFrameCapture(const QString &cameraId)
{
    auto it = m_streams.find(cameraId);
    if (it == m_streams.end()) return;

    auto &cs = it.value();
    if (cs.info.state != Vision::CameraState::Streaming) return;

    // En production : av_read_frame → sws_scale → QImage
    // Simulation : image noire avec ID caméra
    QImage frame(cs.info.width / 4, cs.info.height / 4, QImage::Format_RGB888);
    frame.fill(Qt::black);

    QPainter painter(&frame);
    painter.setPen(Qt::white);
    painter.setFont(QFont("Cascadia Code", 10));
    painter.drawText(10, 20, QString("[%1] Frame #%2").arg(cameraId).arg(cs.info.frameCount));
    painter.end();

    // Buffer circulaire
    cs.frameBuffer[cs.bufferPos % m_bufferSize] = frame;
    cs.bufferPos++;
    cs.lastFrame = frame;
    cs.info.frameCount++;

    emit frameReady(cameraId, cs.info.frameCount);
}
