#include "SpatialContext.h"

// ─────────────────────────────────────────────────────
//  RoomState
// ─────────────────────────────────────────────────────

QVariantMap RoomState::toVariantMap() const
{
    return {
        {"roomId",      roomId},
        {"occupied",    occupied},
        {"illuminated", illuminated},
        {"temperature", temperature},
        {"humidity",    humidity},
        {"noiseLevel",  noiseLevel},
        {"smokeLevel",  smokeLevel},
        {"co2Level",    co2Level},
        {"deviceCount", deviceCount},
        {"sensorCount", sensorCount},
        {"activeAlerts", QVariant::fromValue(activeAlerts)}
    };
}

// ─────────────────────────────────────────────────────
//  SpatialContext
// ─────────────────────────────────────────────────────

SpatialContext::SpatialContext(QObject *parent)
    : QObject(parent)
{
}

SpatialContext::~SpatialContext() = default;

// ── Mise à jour par source ──

void SpatialContext::updateRoomStates(const QVariantList &rooms)
{
    for (const auto &r : rooms) {
        const QVariantMap map = r.toMap();
        const QString id = map.value("roomId").toString();
        if (id.isEmpty())
            continue;

        RoomState &state = m_rooms[id];
        state.roomId      = id;
        state.occupied    = map.value("occupied", state.occupied).toBool();
        state.illuminated = map.value("illuminated", state.illuminated).toBool();
        state.temperature = map.value("temperature", state.temperature).toDouble();
        state.humidity    = map.value("humidity", state.humidity).toDouble();
        state.noiseLevel  = map.value("noiseLevel", state.noiseLevel).toDouble();
        state.smokeLevel  = map.value("smokeLevel", state.smokeLevel).toDouble();
        state.co2Level    = map.value("co2Level", state.co2Level).toDouble();

        emit roomStateChanged(id);
    }

    m_lastUpdate = QDateTime::currentDateTime();
    emit contextUpdated();
}

void SpatialContext::updateSensorStates(const QVariantMap &sensorData)
{
    for (auto it = sensorData.constBegin(); it != sensorData.constEnd(); ++it)
        m_sensors[it.key()] = it.value().toMap();

    m_lastUpdate = QDateTime::currentDateTime();
    emit contextUpdated();
}

void SpatialContext::updateDeviceStates(const QVariantMap &deviceData)
{
    for (auto it = deviceData.constBegin(); it != deviceData.constEnd(); ++it)
        m_devices[it.key()] = it.value().toMap();

    m_lastUpdate = QDateTime::currentDateTime();
    emit contextUpdated();
}

void SpatialContext::updateNetworkState(const QVariantMap &networkData)
{
    m_networkState = networkData;
    m_lastUpdate = QDateTime::currentDateTime();
    emit contextUpdated();
}

void SpatialContext::updateSimulationState(const QVariantMap &simState)
{
    m_simulationState = simState;
    m_lastUpdate = QDateTime::currentDateTime();
    emit contextUpdated();
}

void SpatialContext::updateCognitionState(const QVariantMap &cognitionData)
{
    m_cognitionState = cognitionData;
    m_lastUpdate = QDateTime::currentDateTime();
    emit contextUpdated();
}

// ── Accès à l'état ──

RoomState SpatialContext::roomState(const QString &roomId) const
{
    return m_rooms.value(roomId);
}

QVariantMap SpatialContext::sensorState(const QString &sensorId) const
{
    return m_sensors.value(sensorId);
}

QVariantMap SpatialContext::deviceState(const QString &deviceId) const
{
    return m_devices.value(deviceId);
}

// ── Snapshot / Diff ──

QVariantMap SpatialContext::snapshot() const
{
    QVariantList roomList;
    for (const auto &r : m_rooms)
        roomList.append(r.toVariantMap());

    QVariantMap sensorMap;
    for (auto it = m_sensors.constBegin(); it != m_sensors.constEnd(); ++it)
        sensorMap[it.key()] = it.value();

    QVariantMap deviceMap;
    for (auto it = m_devices.constBegin(); it != m_devices.constEnd(); ++it)
        deviceMap[it.key()] = it.value();

    return {
        {"rooms",       roomList},
        {"sensors",     sensorMap},
        {"devices",     deviceMap},
        {"network",     m_networkState},
        {"simulation",  m_simulationState},
        {"cognition",   m_cognitionState},
        {"timestamp",   m_lastUpdate.toString(Qt::ISODate)}
    };
}

QVariantMap SpatialContext::diff(const QVariantMap &previousSnapshot) const
{
    QVariantMap current = snapshot();
    QVariantMap result;

    // Comparer les clés top-level
    for (auto it = current.constBegin(); it != current.constEnd(); ++it) {
        const auto prev = previousSnapshot.value(it.key());
        if (prev != it.value())
            result[it.key()] = it.value();
    }

    return result;
}

void SpatialContext::update()
{
    m_lastUpdate = QDateTime::currentDateTime();
    emit contextUpdated();
}

// ── Requêtes ──

QStringList SpatialContext::occupiedRooms() const
{
    QStringList result;
    for (const auto &r : m_rooms) {
        if (r.occupied)
            result.append(r.roomId);
    }
    return result;
}

QStringList SpatialContext::alertRooms() const
{
    QStringList result;
    for (const auto &r : m_rooms) {
        if (!r.activeAlerts.isEmpty())
            result.append(r.roomId);
    }
    return result;
}

QStringList SpatialContext::offlineDevices() const
{
    QStringList result;
    for (auto it = m_devices.constBegin(); it != m_devices.constEnd(); ++it) {
        const auto state = it.value().value("state").toString();
        if (state == "offline" || state == "unavailable")
            result.append(it.key());
    }
    return result;
}

double SpatialContext::globalRiskLevel() const
{
    double maxRisk = 0.0;
    for (const auto &r : m_rooms) {
        double risk = 0.0;
        if (r.smokeLevel > 0.3)
            risk = qMax(risk, r.smokeLevel);
        if (r.temperature > 40.0)
            risk = qMax(risk, (r.temperature - 20.0) / 80.0);
        if (!r.activeAlerts.isEmpty())
            risk = qMax(risk, 0.7);
        maxRisk = qMax(maxRisk, risk);
    }
    return maxRisk;
}

void SpatialContext::clear()
{
    m_rooms.clear();
    m_sensors.clear();
    m_devices.clear();
    m_networkState.clear();
    m_simulationState.clear();
    m_cognitionState.clear();
    m_lastUpdate = QDateTime();
    emit contextUpdated();
}
