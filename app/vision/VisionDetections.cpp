#include "VisionDetections.h"
#include <QUuid>
#include <algorithm>

// ═════════════════════════════════════════════════════
//  BoundingBox
// ═════════════════════════════════════════════════════

QVariantMap BoundingBox::toVariant() const
{
    return {
        {"x", x}, {"y", y}, {"width", width}, {"height", height},
        {"confidence", confidence}, {"label", label}
    };
}

BoundingBox BoundingBox::fromVariant(const QVariantMap &v)
{
    BoundingBox bb;
    bb.x          = v.value("x").toDouble();
    bb.y          = v.value("y").toDouble();
    bb.width      = v.value("width").toDouble();
    bb.height     = v.value("height").toDouble();
    bb.confidence = v.value("confidence").toDouble();
    bb.label      = v.value("label").toString();
    return bb;
}

// ═════════════════════════════════════════════════════
//  VisionDetection
// ═════════════════════════════════════════════════════

QVariantMap VisionDetection::toVariant() const
{
    QVariantMap v;
    v["id"]         = id;
    v["type"]       = static_cast<int>(type);
    v["bbox"]       = bbox.toVariant();
    v["confidence"] = confidence;
    v["className"]  = className;
    v["posture"]    = static_cast<int>(posture);
    v["behavior"]   = static_cast<int>(behavior);
    v["directionX"] = direction.x();
    v["directionY"] = direction.y();
    v["speed"]      = speed;
    v["crossedLine"]= crossedLine;
    v["roomId"]     = roomId;
    v["zoneId"]     = zoneId;
    return v;
}

VisionDetection VisionDetection::fromVariant(const QVariantMap &v)
{
    VisionDetection d;
    d.id         = v.value("id").toString();
    d.type       = static_cast<Vision::DetectionType>(v.value("type").toInt());
    d.bbox       = BoundingBox::fromVariant(v.value("bbox").toMap());
    d.confidence = v.value("confidence").toDouble();
    d.className  = v.value("className").toString();
    d.posture    = static_cast<Vision::Posture>(v.value("posture").toInt());
    d.behavior   = static_cast<Vision::Behavior>(v.value("behavior").toInt());
    d.direction  = QPointF(v.value("directionX").toDouble(), v.value("directionY").toDouble());
    d.speed      = v.value("speed").toDouble();
    d.crossedLine= v.value("crossedLine").toBool();
    d.roomId     = v.value("roomId").toString();
    d.zoneId     = v.value("zoneId").toString();
    return d;
}

// ═════════════════════════════════════════════════════
//  FrameDetections
// ═════════════════════════════════════════════════════

int FrameDetections::personCount() const
{
    int count = 0;
    for (const auto &d : detections)
        if (d.type == Vision::DetectionType::Person) ++count;
    return count;
}

int FrameDetections::animalCount() const
{
    int count = 0;
    for (const auto &d : detections)
        if (d.type == Vision::DetectionType::Animal) ++count;
    return count;
}

int FrameDetections::vehicleCount() const
{
    int count = 0;
    for (const auto &d : detections)
        if (d.type == Vision::DetectionType::Vehicle) ++count;
    return count;
}

bool FrameDetections::hasAnomalies() const
{
    if (obstructionDetected || fireDetected || smokeDetected)
        return true;
    for (const auto &d : detections) {
        if (d.type == Vision::DetectionType::Fall ||
            d.type == Vision::DetectionType::Intrusion ||
            d.type == Vision::DetectionType::Agitation ||
            d.type == Vision::DetectionType::AbnormalMovement)
            return true;
    }
    return false;
}

QVariantMap FrameDetections::toVariant() const
{
    QVariantMap v;
    v["cameraId"]             = cameraId;
    v["frameIndex"]           = static_cast<qlonglong>(frameIndex);
    v["timestamp"]            = timestamp.toString(Qt::ISODateWithMs);
    v["frameWidth"]           = frameWidth;
    v["frameHeight"]          = frameHeight;
    v["personCount"]          = personCount();
    v["animalCount"]          = animalCount();
    v["vehicleCount"]         = vehicleCount();
    v["obstructionDetected"]  = obstructionDetected;
    v["obstructionLevel"]     = obstructionLevel;
    v["fireDetected"]         = fireDetected;
    v["smokeDetected"]        = smokeDetected;
    v["detections"]           = detectionsToVariantList();
    return v;
}

QVariantList FrameDetections::detectionsToVariantList() const
{
    QVariantList list;
    for (const auto &d : detections)
        list.append(d.toVariant());
    return list;
}

FrameDetections FrameDetections::fromVariant(const QVariantMap &v)
{
    FrameDetections fd;
    fd.cameraId             = v.value("cameraId").toString();
    fd.frameIndex           = v.value("frameIndex").toLongLong();
    fd.timestamp            = QDateTime::fromString(v.value("timestamp").toString(), Qt::ISODateWithMs);
    fd.frameWidth           = v.value("frameWidth").toInt();
    fd.frameHeight          = v.value("frameHeight").toInt();
    fd.obstructionDetected  = v.value("obstructionDetected").toBool();
    fd.obstructionLevel     = v.value("obstructionLevel").toDouble();
    fd.fireDetected         = v.value("fireDetected").toBool();
    fd.smokeDetected        = v.value("smokeDetected").toBool();
    const auto dList = v.value("detections").toList();
    for (const auto &item : dList)
        fd.detections.append(VisionDetection::fromVariant(item.toMap()));
    return fd;
}

// ═════════════════════════════════════════════════════
//  VisionEvent
// ═════════════════════════════════════════════════════

QVariantMap VisionEvent::toVariant() const
{
    return {
        {"id", id}, {"cameraId", cameraId},
        {"type", static_cast<int>(type)},
        {"severity", static_cast<int>(severity)},
        {"description", description}, {"roomId", roomId},
        {"confidence", confidence}, {"details", details},
        {"timestamp", timestamp.toString(Qt::ISODateWithMs)}
    };
}

VisionEvent VisionEvent::fromVariant(const QVariantMap &v)
{
    VisionEvent ev;
    ev.id          = v.value("id").toString();
    ev.cameraId    = v.value("cameraId").toString();
    ev.type        = static_cast<Vision::DetectionType>(v.value("type").toInt());
    ev.severity    = static_cast<Vision::VisionSeverity>(v.value("severity").toInt());
    ev.description = v.value("description").toString();
    ev.roomId      = v.value("roomId").toString();
    ev.confidence  = v.value("confidence").toDouble();
    ev.details     = v.value("details").toMap();
    ev.timestamp   = QDateTime::fromString(v.value("timestamp").toString(), Qt::ISODateWithMs);
    return ev;
}

// ═════════════════════════════════════════════════════
//  VisionDetections — Gestionnaire QML
// ═════════════════════════════════════════════════════

VisionDetections::VisionDetections(QObject *parent)
    : QObject(parent)
{}

void VisionDetections::addFrameDetections(const FrameDetections &fd)
{
    m_currentByCamera[fd.cameraId] = fd;
    emit detectionsChanged();
}

void VisionDetections::addEvent(const VisionEvent &event)
{
    m_events.append(event);
    if (m_events.size() > Vision::kMaxVisionEvents)
        m_events.remove(0, m_events.size() - Vision::kMaxVisionEvents);
    emit eventsChanged();

    if (static_cast<int>(event.severity) >= static_cast<int>(Vision::VisionSeverity::Critical))
        emit criticalEventDetected(event.toVariant());
}

int VisionDetections::totalDetections() const
{
    int total = 0;
    for (auto it = m_currentByCamera.cbegin(); it != m_currentByCamera.cend(); ++it)
        total += it.value().detections.size();
    return total;
}

int VisionDetections::personCount() const
{
    int count = 0;
    for (auto it = m_currentByCamera.cbegin(); it != m_currentByCamera.cend(); ++it)
        count += it.value().personCount();
    return count;
}

QVariantList VisionDetections::currentDetections() const
{
    QVariantList all;
    for (auto it = m_currentByCamera.cbegin(); it != m_currentByCamera.cend(); ++it) {
        const auto &fd = it.value();
        for (const auto &d : fd.detections)
            all.append(d.toVariant());
    }
    return all;
}

QVariantList VisionDetections::recentEvents() const
{
    QVariantList list;
    int start = std::max(0, static_cast<int>(m_events.size()) - 100);
    for (int i = m_events.size() - 1; i >= start; --i)
        list.append(m_events[i].toVariant());
    return list;
}

QVariantList VisionDetections::getDetectionsByCamera(const QString &cameraId) const
{
    QVariantList list;
    auto it = m_currentByCamera.find(cameraId);
    if (it != m_currentByCamera.end()) {
        for (const auto &d : it.value().detections)
            list.append(d.toVariant());
    }
    return list;
}

QVariantList VisionDetections::getDetectionsByType(int type) const
{
    QVariantList list;
    auto dt = static_cast<Vision::DetectionType>(type);
    for (auto it = m_currentByCamera.cbegin(); it != m_currentByCamera.cend(); ++it)
        for (const auto &d : it.value().detections)
            if (d.type == dt) list.append(d.toVariant());
    return list;
}

QVariantList VisionDetections::getDetectionsByRoom(const QString &roomId) const
{
    QVariantList list;
    for (auto it = m_currentByCamera.cbegin(); it != m_currentByCamera.cend(); ++it)
        for (const auto &d : it.value().detections)
            if (d.roomId == roomId) list.append(d.toVariant());
    return list;
}

QVariantList VisionDetections::getEventsByType(int type) const
{
    QVariantList list;
    auto dt = static_cast<Vision::DetectionType>(type);
    for (const auto &ev : m_events)
        if (ev.type == dt) list.append(ev.toVariant());
    return list;
}

QVariantList VisionDetections::getEventsBySeverity(int minSeverity) const
{
    QVariantList list;
    for (const auto &ev : m_events)
        if (static_cast<int>(ev.severity) >= minSeverity)
            list.append(ev.toVariant());
    return list;
}

void VisionDetections::clearDetections()
{
    m_currentByCamera.clear();
    emit detectionsChanged();
}

void VisionDetections::clearEvents()
{
    m_events.clear();
    emit eventsChanged();
}
