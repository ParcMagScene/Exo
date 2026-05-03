#include "SpatialReasoner.h"

#include <QUuid>

// ─────────────────────────────────────────────────────
//  SpatialRule
// ─────────────────────────────────────────────────────

QVariantMap SpatialRule::toVariantMap() const
{
    return {
        {"id",          id},
        {"name",        name},
        {"description", description},
        {"type",        static_cast<int>(type)},
        {"priority",    priority},
        {"enabled",     enabled},
        {"conditions",  conditions},
        {"conclusions", conclusions}
    };
}

// ─────────────────────────────────────────────────────
//  Inference
// ─────────────────────────────────────────────────────

QVariantMap Inference::toVariantMap() const
{
    return {
        {"id",          id},
        {"ruleId",      ruleId},
        {"description", description},
        {"type",        static_cast<int>(type)},
        {"severity",    static_cast<int>(severity)},
        {"confidence",  confidence},
        {"roomId",      roomId},
        {"data",        data},
        {"evidence",    evidence},
        {"explanation", explanation}
    };
}

// ─────────────────────────────────────────────────────
//  SpatialReasoner
// ─────────────────────────────────────────────────────

SpatialReasoner::SpatialReasoner(QObject *parent)
    : QObject(parent)
{
}

SpatialReasoner::~SpatialReasoner() = default;

// ── Configuration ──

void SpatialReasoner::setKnowledgeGraph(SpatialKnowledgeGraph *graph)
{
    m_graph = graph;
}

void SpatialReasoner::setContext(SpatialContext *context)
{
    m_context = context;
}

void SpatialReasoner::addRule(const SpatialRule &rule)
{
    m_rules.append(rule);
}

void SpatialReasoner::removeRule(const QString &ruleId)
{
    m_rules.erase(std::remove_if(m_rules.begin(), m_rules.end(),
                                  [&](const SpatialRule &r) { return r.id == ruleId; }),
                   m_rules.end());
}

void SpatialReasoner::setRuleEnabled(const QString &ruleId, bool enabled)
{
    for (auto &r : m_rules) {
        if (r.id == ruleId) {
            r.enabled = enabled;
            return;
        }
    }
}

// ── Inférence ──

QVector<Inference> SpatialReasoner::infer()
{
    m_lastInferences.clear();

    // Trier les règles par priorité décroissante
    auto sorted = m_rules;
    std::sort(sorted.begin(), sorted.end(), [](const SpatialRule &a, const SpatialRule &b) {
        return a.priority > b.priority;
    });

    for (const auto &rule : sorted) {
        if (!rule.enabled)
            continue;

        if (evaluateConditions(rule)) {
            QVariantList evidence = gatherEvidence(rule);
            Inference inf = buildInference(rule, evidence);
            m_lastInferences.append(inf);

            if (inf.type == SpatialCognition::InferenceType::Anomaly)
                emit anomalyDetected(inf.toVariantMap());
            else if (inf.type == SpatialCognition::InferenceType::Risk)
                emit riskDetected(inf.toVariantMap());
        }
    }

    emit inferenceCompleted(m_lastInferences.size());
    return m_lastInferences;
}

QVector<Inference> SpatialReasoner::detectAnomalies()
{
    QVector<Inference> anomalies;
    if (!m_context)
        return anomalies;

    // Anomalie 1 : appareil offline dans pièce occupée
    const auto occupied = m_context->occupiedRooms();
    const auto offline  = m_context->offlineDevices();
    if (m_graph) {
        for (const auto &devId : offline) {
            const auto *devNode = m_graph->node(devId);
            if (!devNode)
                continue;
            if (occupied.contains(devNode->roomId)) {
                Inference inf;
                inf.id          = QUuid::createUuid().toString(QUuid::WithoutBraces);
                inf.description = QStringLiteral("Appareil '%1' offline dans pièce occupée '%2'")
                                      .arg(devNode->label, devNode->roomId);
                inf.type        = SpatialCognition::InferenceType::Anomaly;
                inf.severity    = SpatialCognition::CognitiveSeverity::Medium;
                inf.confidence  = 0.8;
                inf.roomId      = devNode->roomId;
                inf.data        = {{"deviceId", devId}, {"deviceLabel", devNode->label}};
                inf.explanation = QStringLiteral("L'appareil '%1' est offline alors que la pièce '%2' est occupée")
                                      .arg(devNode->label, devNode->roomId);
                anomalies.append(inf);
                emit anomalyDetected(inf.toVariantMap());
            }
        }
    }

    // Anomalie 2 : pièce éclairée mais non occupée
    for (auto it = m_context->snapshot().value("rooms").toList().constBegin();
         it != m_context->snapshot().value("rooms").toList().constEnd(); ++it) {
        const QVariantMap rm = it->toMap();
        if (rm.value("illuminated").toBool() && !rm.value("occupied").toBool()) {
            Inference inf;
            inf.id          = QUuid::createUuid().toString(QUuid::WithoutBraces);
            inf.description = QStringLiteral("Pièce '%1' éclairée mais non occupée")
                                  .arg(rm.value("roomId").toString());
            inf.type        = SpatialCognition::InferenceType::Anomaly;
            inf.severity    = SpatialCognition::CognitiveSeverity::Low;
            inf.confidence  = 0.9;
            inf.roomId      = rm.value("roomId").toString();
            inf.explanation = QStringLiteral("Gaspillage d'énergie : lumière allumée dans une pièce vide");
            anomalies.append(inf);
            emit anomalyDetected(inf.toVariantMap());
        }
    }

    return anomalies;
}

QVector<Inference> SpatialReasoner::detectRisks()
{
    QVector<Inference> risks;
    if (!m_context)
        return risks;

    const auto snap = m_context->snapshot();
    const auto rooms = snap.value("rooms").toList();

    for (const auto &r : rooms) {
        const QVariantMap rm = r.toMap();
        const QString roomId = rm.value("roomId").toString();

        // Risque incendie : fumée > 0.3 ou température > 50
        const double smoke = rm.value("smokeLevel").toDouble();
        const double temp  = rm.value("temperature").toDouble();
        if (smoke > 0.3 || temp > 50.0) {
            Inference inf;
            inf.id          = QUuid::createUuid().toString(QUuid::WithoutBraces);
            inf.description = QStringLiteral("Risque incendie dans '%1'").arg(roomId);
            inf.type        = SpatialCognition::InferenceType::Risk;
            inf.severity    = (smoke > 0.6 || temp > 70.0)
                                  ? SpatialCognition::CognitiveSeverity::Critical
                                  : SpatialCognition::CognitiveSeverity::High;
            inf.confidence  = qMin(1.0, smoke + (temp - 30.0) / 100.0);
            inf.roomId      = roomId;
            inf.data        = {{"smokeLevel", smoke}, {"temperature", temp}};
            inf.explanation = QStringLiteral("Fumée=%.1f, Température=%.1f°C dans '%2'")
                                  .arg(smoke).arg(temp).arg(roomId);
            risks.append(inf);
            emit riskDetected(inf.toVariantMap());
        }

        // Risque intrusion : mouvement dans pièce à horaire inhabituel
        if (rm.value("occupied").toBool() && rm.value("noiseLevel").toDouble() > 0.7) {
            Inference inf;
            inf.id          = QUuid::createUuid().toString(QUuid::WithoutBraces);
            inf.description = QStringLiteral("Activité suspecte dans '%1'").arg(roomId);
            inf.type        = SpatialCognition::InferenceType::Risk;
            inf.severity    = SpatialCognition::CognitiveSeverity::High;
            inf.confidence  = 0.6;
            inf.roomId      = roomId;
            inf.data        = {{"noiseLevel", rm.value("noiseLevel")}};
            inf.explanation = QStringLiteral("Niveau de bruit élevé (%.1f) dans '%1'")
                                  .arg(rm.value("noiseLevel").toDouble()).arg(roomId);
            risks.append(inf);
            emit riskDetected(inf.toVariantMap());
        }

        // Risque inondation : eau > 0.2
        const double water = rm.value("waterLevel", 0.0).toDouble();
        if (water > 0.2) {
            Inference inf;
            inf.id          = QUuid::createUuid().toString(QUuid::WithoutBraces);
            inf.description = QStringLiteral("Risque inondation dans '%1'").arg(roomId);
            inf.type        = SpatialCognition::InferenceType::Risk;
            inf.severity    = (water > 0.5) ? SpatialCognition::CognitiveSeverity::Critical
                                             : SpatialCognition::CognitiveSeverity::High;
            inf.confidence  = qMin(1.0, water * 2.0);
            inf.roomId      = roomId;
            inf.data        = {{"waterLevel", water}};
            inf.explanation = QStringLiteral("Niveau d'eau=%.2f dans '%1'").arg(water).arg(roomId);
            risks.append(inf);
            emit riskDetected(inf.toVariantMap());
        }
    }

    // Risque réseau : appareils offline
    const auto offline = m_context->offlineDevices();
    if (offline.size() > 2) {
        Inference inf;
        inf.id          = QUuid::createUuid().toString(QUuid::WithoutBraces);
        inf.description = QStringLiteral("%1 appareils offline — risque panne réseau").arg(offline.size());
        inf.type        = SpatialCognition::InferenceType::Risk;
        inf.severity    = SpatialCognition::CognitiveSeverity::High;
        inf.confidence  = 0.7;
        inf.data        = {{"offlineDevices", QVariant::fromValue(offline)}, {"count", offline.size()}};
        inf.explanation = QStringLiteral("Plusieurs appareils ne répondent plus : possible panne réseau");
        risks.append(inf);
        emit riskDetected(inf.toVariantMap());
    }

    return risks;
}

// ── Explication ──

QString SpatialReasoner::explain(const QString &eventId) const
{
    for (const auto &inf : m_lastInferences) {
        if (inf.id == eventId)
            return inf.explanation;
    }
    return QStringLiteral("Aucune explication disponible pour '%1'").arg(eventId);
}

QString SpatialReasoner::explain(const Inference &inference) const
{
    return inference.explanation;
}

// ── Export QML ──

QVariantList SpatialReasoner::inferencesToVariantList() const
{
    QVariantList list;
    for (const auto &inf : m_lastInferences)
        list.append(inf.toVariantMap());
    return list;
}

QVariantList SpatialReasoner::rulesToVariantList() const
{
    QVariantList list;
    for (const auto &r : m_rules)
        list.append(r.toVariantMap());
    return list;
}

// ── Règles par défaut ──

void SpatialReasoner::loadDefaultRules()
{
    // Règle 1 — Porte ouverte + mouvement adjacent → intrusion possible
    {
        SpatialRule rule;
        rule.id          = "rule_intrusion_door";
        rule.name        = "Intrusion par porte ouverte";
        rule.description = "Si une porte est ouverte et qu'un mouvement est détecté dans la pièce adjacente → intrusion possible";
        rule.type        = SpatialCognition::InferenceType::Risk;
        rule.priority    = 9.0;
        rule.conditions  = {
            QVariantMap{{"field", "door.state"}, {"operator", "=="}, {"value", "open"}},
            QVariantMap{{"field", "adjacent_room.occupied"}, {"operator", "=="}, {"value", true}}
        };
        rule.conclusions = {
            QVariantMap{{"action", "alert"}, {"severity", "high"}, {"message", "Intrusion possible"}}
        };
        addRule(rule);
    }

    // Règle 2 — Température élevée en pièce fermée → risque incendie
    {
        SpatialRule rule;
        rule.id          = "rule_fire_closed_room";
        rule.name        = "Risque incendie pièce fermée";
        rule.description = "Si la température augmente dans une pièce fermée → risque incendie";
        rule.type        = SpatialCognition::InferenceType::Risk;
        rule.priority    = 10.0;
        rule.conditions  = {
            QVariantMap{{"field", "room.temperature"}, {"operator", ">"}, {"value", 45}},
            QVariantMap{{"field", "room.doors_closed"}, {"operator", "=="}, {"value", true}}
        };
        rule.conclusions = {
            QVariantMap{{"action", "alert"}, {"severity", "critical"}, {"message", "Risque incendie"}}
        };
        addRule(rule);
    }

    // Règle 3 — Appareil offline loin du routeur → zone morte WiFi
    {
        SpatialRule rule;
        rule.id          = "rule_wifi_deadzone";
        rule.name        = "Zone morte WiFi";
        rule.description = "Si un appareil est offline et éloigné du routeur → zone morte WiFi";
        rule.type        = SpatialCognition::InferenceType::Anomaly;
        rule.priority    = 5.0;
        rule.conditions  = {
            QVariantMap{{"field", "device.state"}, {"operator", "=="}, {"value", "offline"}},
            QVariantMap{{"field", "device.distance_to_router"}, {"operator", ">"}, {"value", 15.0}}
        };
        rule.conclusions = {
            QVariantMap{{"action", "suggest"}, {"message", "Zone morte WiFi détectée"}}
        };
        addRule(rule);
    }

    // Règle 4 — CO2 élevé → ventilation nécessaire
    {
        SpatialRule rule;
        rule.id          = "rule_co2_ventilation";
        rule.name        = "Ventilation nécessaire";
        rule.description = "Si le CO2 dépasse 1000 ppm → ouvrir la ventilation";
        rule.type        = SpatialCognition::InferenceType::RuleBased;
        rule.priority    = 6.0;
        rule.conditions  = {
            QVariantMap{{"field", "room.co2Level"}, {"operator", ">"}, {"value", 1000}}
        };
        rule.conclusions = {
            QVariantMap{{"action", "ventilate"}, {"message", "CO2 élevé, ventilation recommandée"}}
        };
        addRule(rule);
    }

    // Règle 5 — Lumière allumée + pièce vide > 10 min → économie énergie
    {
        SpatialRule rule;
        rule.id          = "rule_energy_light";
        rule.name        = "Économie lumière";
        rule.description = "Si la lumière est allumée dans une pièce vide → éteindre";
        rule.type        = SpatialCognition::InferenceType::RuleBased;
        rule.priority    = 3.0;
        rule.conditions  = {
            QVariantMap{{"field", "room.illuminated"}, {"operator", "=="}, {"value", true}},
            QVariantMap{{"field", "room.occupied"}, {"operator", "=="}, {"value", false}}
        };
        rule.conclusions = {
            QVariantMap{{"action", "turn_off_light"}, {"message", "Lumière inutile, extinction recommandée"}}
        };
        addRule(rule);
    }
}

// ── Clear ──

void SpatialReasoner::clearRules()
{
    m_rules.clear();
}

void SpatialReasoner::clearInferences()
{
    m_lastInferences.clear();
}

// ── Private ──

bool SpatialReasoner::evaluateConditions(const SpatialRule &rule) const
{
    if (!m_context)
        return false;

    for (const auto &cond : rule.conditions) {
        if (!evaluateCondition(cond.toMap()))
            return false;
    }
    return true;
}

bool SpatialReasoner::evaluateCondition(const QVariantMap &condition) const
{
    const QString field = condition.value("field").toString();
    const QString op    = condition.value("operator").toString();
    const QVariant expected = condition.value("value");

    // Résolution du field dans le contexte
    QVariant actual;
    const auto parts = field.split('.');
    if (parts.size() == 2) {
        const QString scope = parts[0];
        const QString key   = parts[1];

        if (scope == "room") {
            // Évaluer sur toutes les pièces — retourne true si au moins une match
            const auto snap = m_context->snapshot();
            const auto rooms = snap.value("rooms").toList();
            for (const auto &r : rooms) {
                actual = r.toMap().value(key);
                if (op == "==" && actual == expected) return true;
                if (op == "!=" && actual != expected) return true;
                if (op == ">"  && actual.toDouble() > expected.toDouble()) return true;
                if (op == "<"  && actual.toDouble() < expected.toDouble()) return true;
                if (op == ">=" && actual.toDouble() >= expected.toDouble()) return true;
                if (op == "<=" && actual.toDouble() <= expected.toDouble()) return true;
            }
            return false;
        }

        if (scope == "device") {
            const auto snap = m_context->snapshot();
            const auto devices = snap.value("devices").toMap();
            for (auto it = devices.constBegin(); it != devices.constEnd(); ++it) {
                actual = it.value().toMap().value(key);
                if (op == "==" && actual == expected) return true;
                if (op == "!=" && actual != expected) return true;
                if (op == ">"  && actual.toDouble() > expected.toDouble()) return true;
                if (op == "<"  && actual.toDouble() < expected.toDouble()) return true;
            }
            return false;
        }
    }

    return false;
}

Inference SpatialReasoner::buildInference(const SpatialRule &rule, const QVariantList &evidence) const
{
    Inference inf;
    inf.id          = QUuid::createUuid().toString(QUuid::WithoutBraces);
    inf.ruleId      = rule.id;
    inf.description = rule.description;
    inf.type        = rule.type;
    inf.evidence    = evidence;

    // Sévérité depuis les conclusions
    for (const auto &c : rule.conclusions) {
        const auto cm = c.toMap();
        const QString sev = cm.value("severity").toString();
        if (sev == "critical")
            inf.severity = SpatialCognition::CognitiveSeverity::Critical;
        else if (sev == "high")
            inf.severity = SpatialCognition::CognitiveSeverity::High;
        else if (sev == "medium")
            inf.severity = SpatialCognition::CognitiveSeverity::Medium;
        else if (sev == "low")
            inf.severity = SpatialCognition::CognitiveSeverity::Low;

        inf.explanation = cm.value("message").toString();
    }

    inf.confidence = 0.7; // confiance par défaut pour les règles
    return inf;
}

QVariantList SpatialReasoner::gatherEvidence(const SpatialRule &rule) const
{
    // Retourne les conditions comme evidence
    return rule.conditions;
}
