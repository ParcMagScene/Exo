pragma Singleton
import QtQuick

// ═══════════════════════════════════════════════════════════════════════════
//  SettingsLabels — Dictionnaire centralisé des libellés (FR) de la page
//  Paramètres et de tout panneau de configuration.
//
//  Source unique de vérité pour le mapping clé technique → libellé humain.
//  Les noms techniques (CPU, GPU, WebSocket, TTS, STT, LLM, pipeline,
//  benchmark, cache, log, buffer, stream, token, quant, model, GGUF,
//  Orpheus, Whisper) ne sont jamais traduits — ils restent verbatim.
//
//  Usage QML :
//      import "qrc:/qt/qml/RaspberryAssistant/qml/core"
//      Text { text: SettingsLabels.t("audio.inputDevice") }
//      // ou
//      Text { text: SettingsLabels.labels[key] || key }
// ═══════════════════════════════════════════════════════════════════════════

QtObject {
    id: root

    // ── Dictionnaire principal (clé technique → libellé FR) ──
    // Conservé tel quel ; ne pas modifier les clés sans mettre à jour
    // les fichiers QML qui les consomment.
    readonly property var labels: ({
        // ── Audio (entrée micro) ──
        "audio.inputDevice":      "Périphérique d'entrée audio",
        "audio.backend":          "Moteur audio (backend)",
        "audio.level":            "Niveau du microphone",
        "audio.testMic":          "Tester le microphone",
        "audio.windowsSource":    "Source audio Windows",

        // ── VAD / DSP ──
        "vad.engine":             "Moteur de détection vocale (VAD)",
        "vad.threshold":          "Seuil de détection vocale",
        "noise.gate":             "Porte de bruit (noise gate)",
        "agc.enabled":            "Gain automatique (AGC)",
        "dsp.noiseReduction":     "Réduction de bruit (DSP)",
        "dsp.noiseStrength":      "Intensité de réduction de bruit",

        // ── STT / Wakeword ──
        "stt.language":           "Langue de reconnaissance vocale (Whisper)",
        "assistant.wakeWord":     "Mot d'activation",
        "wakeword.neural":        "Détection neuronale du mot-clé (OpenWakeWord)",

        // ── Mémoire ──
        "memory.semantic":        "Mémoire sémantique (FAISS)",
        "memory.conversations":   "Conversations enregistrées",
        "memory.souvenirs":       "Souvenirs persistants",

        // ── Claude / LLM ──
        "claude.model":           "Modèle Claude actif",

        // ── TTS ──
        "tts.engine":             "Moteur de synthèse vocale",
        "tts.voice":              "Voix",
        "tts.pitch":              "Tonalité",
        "tts.rate":               "Vitesse de parole",
        "tts.style":              "Style vocal",
        "tts.language":           "Langue de synthèse vocale",
        "tts.testPhrase":         "Phrase de test",
        "tts.speak":              "Parler",

        // ── Météo / contexte ──
        "weather.city":           "Ville (pour la météo)",
        "weather.detect":         "Détecter",

        // ── Interface / mode expert ──
        "ui.expertMode":          "Mode expert",
        "ui.expertModeHint":      "Afficher tous les panneaux avancés",

        // ── Tests & diagnostics ──
        "diag.stability":         "Ouvrir les tests de stabilité",
        "diag.chatTest":          "Test conversationnel (envoyer un message à EXO)",
        "diag.chatPlaceholder":   "Tapez un message…",
        "tts.testPlaceholder":    "Entrez une phrase à tester…",

        // ════════════════════════════════════════════════════════════════
        //  Pages générales — Titres, onglets, en-têtes (Phase 3)
        // ════════════════════════════════════════════════════════════════

        // ── MainWindow / chat global ──
        "app.title":                  "EXO Assistant",
        "app.openSettings":           "Ouvrir paramètres ›",
        "app.chatPlaceholder":        "Tapez votre message ici…",
        "app.send":                   "Envoyer",
        "app.safeMode":               "Interface en mode secours",
        "app.safeModeDescription":    "L'interface principale n'est pas visible alors que la fenêtre est lancée.",
        "app.showInterface":          "Réafficher l'interface",
        "app.openServices":           "Ouvrir les services",
        "app.settingsTitle":          "PARAMÈTRES",

        // ── Common / boutons communs ──
        "common.close":               "Fermer",
        "common.clear":               "Effacer",
        "common.refresh":             "Rafraîchir",
        "common.copy":                "Copier",
        "common.copyAll":             "Copier tout",
        "common.copyLine":            "Copier la ligne",
        "common.execute":             "Exécuter",
        "common.confirm":             "Confirmer",
        "common.launch":              "Lancer",
        "common.search":              "Rechercher…",
        "common.filter":              "Filtrer…",
        "common.all":                 "Tout",
        "common.empty":               "(aucun)",
        "common.waiting":             "En attente",
        "common.total":               "TOTAL",
        "common.module":              "Module :",
        "common.state":               "État :",
        "common.lastEvent":           "Dernier évènement :",
        "common.error":               "Erreur :",
        "common.streaming":           "diffusion en cours",
        "common.detect":              "Détecter",

        // ── Page Historique ──
        "history.title":              "Historique",
        "history.clear":              "Effacer",

        // ── Page Journaux ──
        "logs.title":                 "Journaux runtime",
        "logs.filterPlaceholder":     "Filtrer (texte, catégorie, message)…",
        "logs.autoScroll":            "Défilement auto",
        "logs.copyAll":               "Copier tout",
        "logs.clear":                 "Vider",
        "logs.refresh":               "Rafraîchir",
        "logs.colTimestamp":          "HORODATAGE",
        "logs.colLevel":              "NIVEAU",
        "logs.colCategory":           "CATÉGORIE",
        "logs.colMessage":            "MESSAGE",
        "logs.copyRow":               "Copier la ligne",
        "logs.filterCategory":        "Filtrer sur cette catégorie",
        "logs.help":                  "Double-clic = copier la ligne · Clic droit = menu · Clic en-tête = trier",

        // ── Page Observabilité ──
        "observability.title":        "OBSERVABILITÉ",
        "observability.subtitle":     "Journaux, métriques, traces & santé des services",
        "observability.tabLogs":      "Journaux",
        "observability.tabMetrics":   "Métriques",
        "observability.tabTraces":    "Traces",
        "observability.tabHealth":    "Santé",
        "observability.filterLogs":   "Filtrer les journaux…",
        "observability.cpu":          "CPU",
        "observability.memory":       "Mémoire",
        "observability.latencySTT":   "Latence STT",
        "observability.latencyLLM":   "Latence LLM",
        "observability.latencyVAD":   "Latence VAD",
        "observability.latencyTTS":   "Latence TTS",
        "observability.timeline":     "Chronologie du Pipeline",
        "observability.servicesHealth":"État des services",
        "observability.sttServer":    "Serveur STT",
        "observability.wakewordServer":"Serveur Wakeword",
        "observability.memoryService":"Service Mémoire",
        "observability.timeout":      "Délai dépassé",

        // ── Page Pipeline (monitor + expert) ──
        "pipeline.title":             "MONITEUR PIPELINE",
        "pipeline.titleExpert":       "PIPELINE",
        "pipeline.subtitleExpert":    "Pipeline vocal + chronologie cognitive",
        "pipeline.tabVoice":          "Voix",
        "pipeline.tabCognitive":      "Cognitif",
        "pipeline.tabMetrics":        "Métriques",
        "pipeline.audio":             "Audio",
        "pipeline.micLevel":          "Niveau micro :",
        "pipeline.partialTranscript": "Transcription partielle :",
        "pipeline.cognitiveSteps":    "Étapes cognitives",
        "pipeline.eventsTimeline":    "CHRONOLOGIE DES ÉVÉNEMENTS",
        "pipeline.clickHint":         "Cliquer sur un module\npour l'inspecter",
        "pipeline.recentEvents":      "Évènements récents",
        "pipeline.serviceLogs":       "Journaux du service",
        "pipeline.copyModuleLogs":    "Copier tous les logs du module",
        "pipeline.vocal":             "PIPELINE VOCAL",
        "pipeline.transitions":       "TRANSITIONS FSM",

        // ── Page Vision (expert) ──
        "vision.title":               "VISION",
        "vision.subtitle":            "Flux caméra, carte thermique, détections & risques",
        "vision.tabCamera":           "Caméra",
        "vision.tabHeatmap":          "Carte thermique",
        "vision.tabDetections":       "Détections",
        "vision.tabRisks":            "Risques",
        "vision.tabEvents":           "Événements",
        "vision.heatmapTitle":        "Carte thermique d'activité",
        "vision.detectedObjects":     "Objets détectés",
        "vision.person":              "Personne",
        "vision.car":                 "Voiture",
        "vision.fire":                "Incendie",
        "vision.intrusion":           "Intrusion",
        "vision.low":                 "Faible",
        "vision.critical":            "Critique",
        "vision.videoEvents":         "Évènements vidéo",

        // ── Page Simulation (expert) ──
        "simulation.title":           "SIMULATION",
        "simulation.subtitle":        "Scénarios, propagation & analyse causale",
        "simulation.tabScenarios":    "Scénarios",
        "simulation.tabPropagation":  "Propagation",
        "simulation.tabTimeline":     "Chronologie",
        "simulation.tabCausality":    "Causalité",
        "simulation.scenarios":       "Scénarios de simulation",
        "simulation.propagation":     "Visualisation propagation",
        "simulation.overlay":         "Superposition simulation (zones affectées)",
        "simulation.timeline":        "Chronologie d'évolution",
        "simulation.causalGraph":     "Graphe causal",
        "simulation.rootCause":       "Cause racine",

        // ── Page Cognition spatiale (expert) ──
        "cognition.title":            "COGNITION",
        "cognition.subtitle":         "Intelligence spatiale & décisions",
        "cognition.tabSpatial":       "Spatial",
        "cognition.tabDecisions":     "Décisions",
        "cognition.tabExplanations":  "Explications",
        "cognition.tabPredictions":   "Prédictions",
        "cognition.spaceRepresentation":"Représentation de l'espace",
        "cognition.decisionTree":     "Arbre de décisions",
        "cognition.explanations":     "Explications du raisonnement",
        "cognition.predictions":      "Prédictions futures",

        // ── Page Sécurité spatiale (expert) ──
        "security.title":             "SÉCURITÉ SPATIALE",
        "security.subtitle":          "Risques, décisions & causalité",
        "security.tabOverview":       "Vue globale",
        "security.tabRisks":          "Risques",
        "security.tabCausality":      "Causalité",
        "security.tabDecisions":      "Décisions",
        "security.summary":           "Synthèse sécurité",
        "security.riskCategories":    "Catégories de risques",
        "security.causalGraph":       "Graphe causal des risques",
        "security.recommendations":   "Recommandations & actions",
        "security.priorityCritical":  "Priorité CRITIQUE",

        // ── Page Développement (expert) ──
        "dev.title":                  "DÉVELOPPEMENT",
        "dev.subtitle":               "Services, stabilité & configuration",
        "dev.tabServices":            "Services",
        "dev.tabStability":           "Stabilité",
        "dev.tabConfig":              "Configuration",
        "dev.tabDebug":               "Debug",
        "dev.ready":                  "PRÊTS",
        "dev.failed":                 "ÉCHOUÉS",
        "dev.degraded":               "DÉGRADÉS",
        "dev.detailedState":          "État détaillé",
        "dev.stabilityTests":         "Tests de stabilité",
        "dev.configFile":             "Fichier de configuration",
        "dev.debugTools":             "Outils de débogage",
        "dev.qmlMemoryState":         "État mémoire QML (synthétique)",
        "dev.expertMode":             "Mode expert",
        "dev.expertModeDescription":  "Afficher tous les panneaux avancés",
        "dev.lastTestPassed":         "Résultats du dernier test :\n✓ RÉUSSI (12,3 s)",
        "dev.cfgAudioBackend":        "Sortie audio : Qt Multimedia",
        "dev.cfgAgcEnabled":          "Contrôle automatique du gain : activé",
        "dev.cfgExpertMode":          "Mode expert : activé",

        // ── Composants ──
        "comp.observability":         "OBSERVABILITÉ",
        "comp.observabilityAvg":      "Moy. :",
        "comp.observabilityReq":      "Req. :",
        "comp.observabilityErr":      "Err. :",
        "comp.governance":            "GOUVERNANCE",
        "comp.governanceNoValidation":"Aucune validation enregistrée",
        "comp.governanceNoAudit":     "Aucune entrée d'audit",
        "comp.memoryInspector":       "INSPECTEUR MÉMOIRE",
        "comp.memoryNoInteractions":  "Aucune interaction récente",
        "comp.memoryNoLongTerm":      "Aucune mémoire long terme",
        "comp.memoryNoVector":        "Aucune recherche vectorielle récente",
        "comp.transcript":            "TRANSCRIPTION",
        "comp.response":              "RÉPONSE",
        "comp.mic":                   "MICRO",
        "comp.status":                "ÉTAT",
        "comp.cognitiveTimeline":     "CHRONOLOGIE COGNITIVE",
        "comp.engineHeatmap":         "CARTE THERMIQUE DU MOTEUR",
        "comp.engineFast":            "■ Rapide",
        "comp.engineModerate":        "■ Modéré",
        "comp.engineSlow":            "■ Lent",
        "comp.furniture":             "Mobilier",

        // ── Plan / Mobilier / Périphériques ──
        "floorplan.selectElement":    "Sélectionnez un élément\npour voir ses propriétés.",
        "floorplan.unlinkDevice":     "Délier l'appareil",
        "floorplan.selectDevice":     "Sélectionner un appareil"
    })

    // ── Fonction d'accès tolérante ──
    // Retourne le libellé associé à `key`, ou `fallback` (ou la clé brute) sinon.
    // Évite d'afficher `undefined` si une clé n'est pas (encore) référencée.
    function t(key, fallback) {
        var v = labels[key]
        if (v !== undefined && v !== null && v !== "")
            return v
        if (fallback !== undefined && fallback !== null)
            return fallback
        return key
    }

    // ── Vérifie si une clé est connue (utile pour les composants génériques) ──
    function has(key) {
        return labels[key] !== undefined
    }
}
