pragma Singleton
import QtQuick

// ═══════════════════════════════════════════════════════════════
//  UIState — Singleton pour gérer le mode Normal/Expert
//  Persiste le choix de l'utilisateur dans ConfigManager
// ═══════════════════════════════════════════════════════════════

QtObject {
    id: uiState
    
    // ── Propriété mode d'affichage ──
    property bool expertMode: false
    
    // ── API publique ──
    function setExpertMode(isExpert) {
        expertMode = isExpert
        // Sauvegarder dans ConfigManager si disponible
        if (typeof configManager !== 'undefined') {
            configManager.setUserValue("ui", "expertMode", isExpert ? "true" : "false")
        }
        console.log("[UIState] Mode Expert basculé à:", isExpert)
    }
    
    // ── Initialisation au démarrage ──
    Component.onCompleted: {
        // Charger la préférence sauvegardée
        if (typeof configManager !== 'undefined') {
            var saved = configManager.getString("ui", "expertMode", "false")
            expertMode = (saved === "true" || saved === true)
            console.log("[UIState] Mode expert chargé:", expertMode)
        } else {
            console.warn("[UIState] ConfigManager non disponible")
        }
    }
}
