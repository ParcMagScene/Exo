pragma Singleton
import QtQuick
import "../core"

// ═══════════════════════════════════════════════════════════════
//  MenuStructure v2.0 — Structure dynamique Normal/Expert
//  Adapte le menu selon le mode d'affichage
// ═══════════════════════════════════════════════════════════════

QtObject {
    id: menuStructure

    // ══════════════════════════════════════════════════════
    //  MODE NORMAL — 5 pages simples
    // ══════════════════════════════════════════════════════
    readonly property var normalCategories: [
        {
            id: "accueil",
            label: "ACCUEIL",
            icon: "icons/chat.svg",
            items: [
                { name: "home", icon: "icons/chat.svg", label: "Accueil" }
            ]
        },
        {
            id: "maison",
            label: "MAISON",
            icon: "icons/maison.svg",
            items: [
                { name: "maison", icon: "icons/maison.svg", label: "Appareils" },
                { name: "floorplan", icon: "icons/maison.svg", label: "Plan 2D" }
            ]
        },
        {
            id: "reseau",
            label: "RÉSEAU",
            icon: "icons/reseau.svg",
            items: [
                { name: "reseau", icon: "icons/reseau.svg", label: "Réseau" }
            ]
        },
        {
            id: "historique",
            label: "HISTORIQUE",
            icon: "icons/history.svg",
            items: [
                { name: "history", icon: "icons/history.svg", label: "Historique" }
            ]
        },
        {
            id: "logs",
            label: "LOGS",
            icon: "icons/logs.svg",
            items: [
                { name: "logsFull", icon: "icons/logs.svg", label: "Logs runtime" }
            ]
        },
        {
            id: "parametres",
            label: "PARAMÈTRES",
            icon: "icons/settings.svg",
            items: [
                { name: "settings", icon: "icons/settings.svg", label: "Paramètres" }
            ]
        }
    ]

    // ══════════════════════════════════════════════════════
    //  MODE EXPERT — 8 catégories complètes
    // ══════════════════════════════════════════════════════
    readonly property var expertCategories: [
        {
            id: "pipeline",
            label: "PIPELINE",
            icon: "icons/pipeline.svg",
            items: [
                { name: "voicePipeline", icon: "icons/pipeline.svg", label: "Voice Pipeline" },
                { name: "observability", icon: "icons/logs.svg", label: "Logs + Metrics" },
                { name: "logsFull", icon: "icons/logs.svg", label: "Logs runtime" }
            ]
        },
        {
            id: "vision",
            label: "VISION",
            icon: "icons/heatmap.svg",
            items: [
                { name: "vision", icon: "icons/heatmap.svg", label: "Vision" }
            ]
        },
        {
            id: "cognition",
            label: "COGNITION",
            icon: "icons/cognition.svg",
            items: [
                { name: "spatialCognition", icon: "icons/cognition.svg", label: "Spatial" }
            ]
        },
        {
            id: "securite",
            label: "SÉCURITÉ",
            icon: "icons/securite.svg",
            items: [
                { name: "security", icon: "icons/securite.svg", label: "Sécurité" }
            ]
        },
        {
            id: "simulation",
            label: "SIMULATION",
            icon: "icons/simulation.svg",
            items: [
                { name: "simulation", icon: "icons/simulation.svg", label: "Simulation" }
            ]
        },
        {
            id: "maison",
            label: "MAISON + RÉSEAU",
            icon: "icons/maison.svg",
            items: [
                { name: "maison", icon: "icons/maison.svg", label: "Maison & Réseau" }
            ]
        },
        {
            id: "dev",
            label: "DÉVELOPPEMENT",
            icon: "icons/debug.svg",
            items: [
                { name: "development", icon: "icons/debug.svg", label: "Services" }
            ]
        },
        {
            id: "parametres",
            label: "PARAMÈTRES",
            icon: "icons/settings.svg",
            items: [
                { name: "settings", icon: "icons/settings.svg", label: "Paramètres" }
            ]
        }
    ]

    // ══════════════════════════════════════════════════════
    //  API publique — getCategories() adapté au mode
    // ══════════════════════════════════════════════════════
    function getCategories() {
        if (typeof UIState !== 'undefined' && UIState.expertMode) {
            return expertCategories
        } else {
            return normalCategories
        }
    }

    // ── Lookup rapide : panelName → catégorie ──
    function categoryOf(panelName) {
        var cats = getCategories()
        for (var i = 0; i < cats.length; i++) {
            var cat = cats[i]
            for (var j = 0; j < cat.items.length; j++) {
                if (cat.items[j].name === panelName)
                    return cat.id
            }
        }
        return ""
    }

    // ── Refresh du menu lors du changement de mode ──
    property bool forceRefresh: false
    function refreshMenu() {
        forceRefresh = !forceRefresh
        console.log("[MenuStructure] Menu refreshé — Mode expert:", UIState.expertMode)
    }
}
