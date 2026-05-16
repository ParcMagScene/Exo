pragma Singleton
import QtQuick

// ═══════════════════════════════════════════════════════
//  EXO Theme — Design System centralisé
//  Inspiré VS Code + Fluent Design + Standards 2026
// ═══════════════════════════════════════════════════════

QtObject {
    id: theme

    // ── Mode ──
    readonly property bool isDark: true

    // ══════════════════════════════════════════════
    //  COULEURS
    // ══════════════════════════════════════════════

    // Fond
    readonly property color bgPrimary:    "#1E1E1E"
    readonly property color bgSecondary:  "#252526"
    readonly property color bgElevated:   "#2D2D2D"
    readonly property color bgHover:      "#2A2D2E"
    readonly property color bgActive:     "#37373D"
    readonly property color bgInput:      "#3C3C3C"

    // Accent
    readonly property color accent:       "#0078D4"
    readonly property color accentLight:  "#3A96DD"
    readonly property color accentDark:   "#005A9E"
    readonly property color accentHover:  "#1A86D9"
    readonly property color accentActive: "#094771"

    // Texte
    readonly property color textPrimary:   "#E0E0E0"
    readonly property color textSecondary: "#A0A0A0"
    readonly property color textMuted:     "#5A5A5A"
    readonly property color textDisabled:  "#4A4A4A"
    readonly property color textAccent:    "#007ACC"
    readonly property color textLink:      "#3A96DD"

    // Bordures
    readonly property color border:       "#3C3C3C"
    readonly property color borderLight:  "#505050"
    readonly property color borderFocus:  "#007ACC"
    readonly property color borderHover:  "#505050"

    // Sémantique
    readonly property color success:      "#4EC9B0"
    readonly property color successHover: "#5FD4BC"
    readonly property color successDim:   "#2E7A68"
    readonly property color warning:      "#DCDCAA"
    readonly property color warningHover: "#E5E5BB"
    readonly property color warningDim:   "#8A8A5A"
    readonly property color error:        "#F44747"
    readonly property color errorHover:   "#F66A6A"
    readonly property color errorDim:     "#8B2020"
    readonly property color info:         "#569CD6"
    readonly property color infoHover:    "#6BADE0"
    readonly property color infoDim:      "#2D5273"

    // Pipeline
    readonly property color pipelineIdle:       "#3C3C3C"
    readonly property color pipelineActive:     "#4EC9B0"
    readonly property color pipelineProcessing: "#DCDCAA"
    readonly property color pipelineError:      "#F44747"
    readonly property color pipelineUnavail:    "#5A5A5A"

    // États (Listening, Speaking, etc.)
    readonly property color stateListening:    "#007ACC"
    readonly property color stateTranscribing: "#DCDCAA"
    readonly property color stateThinking:     "#C586C0"
    readonly property color stateSpeaking:     "#4EC9B0"
    readonly property color stateIdle:         "#5A5A5A"

    // Overlay / Splash
    readonly property color splashBg:     "#1A1A2E"
    readonly property color splashAccent: "#E94560"
    readonly property color splashPanel:  "#16213E"

    // ══════════════════════════════════════════════
    //  TYPOGRAPHIE
    // ══════════════════════════════════════════════

    readonly property string fontFamily:     "Inter, Segoe UI, Roboto, sans-serif"
    readonly property string fontMono:       "Cascadia Code, Fira Code, JetBrains Mono, Consolas"

    // Tailles
    readonly property int fontH1:      24
    readonly property int fontH2:      20
    readonly property int fontH3:      16
    readonly property int fontBody:    14
    readonly property int fontSmall:   13
    readonly property int fontLabel:   12
    readonly property int fontCaption: 12
    readonly property int fontMicro:   11
    readonly property int fontTiny:    10

    // Alias de commodité (utilisés par MaisonPage, ScenariosPage, etc.)
    readonly property int fontXL: fontH1       // 24
    readonly property int fontMD: fontH3       // 16
    readonly property int fontSM: fontSmall    // 13
    readonly property int fontXS: fontCaption  // 12

    // Poids
    readonly property int weightLight:    300
    readonly property int weightRegular:  400
    readonly property int weightMedium:   500
    readonly property int weightSemiBold: 600
    readonly property int weightBold:     700

    // ══════════════════════════════════════════════
    //  ESPACEMENT (Grille 8px)
    // ══════════════════════════════════════════════

    readonly property int spacing2:   2
    readonly property int spacing4:   4
    readonly property int spacing6:   6
    readonly property int spacing8:   8
    readonly property int spacing10:  10
    readonly property int spacing12:  12
    readonly property int spacing16:  16
    readonly property int spacing20:  20
    readonly property int spacing24:  24
    readonly property int spacing32:  32

    // Marges de layout
    readonly property int marginH:    24    // marge horizontale globale
    readonly property int marginV:    20    // marge verticale globale
    readonly property int paddingBtn: 12    // padding boutons
    readonly property int paddingCard: 16   // padding cards
    readonly property int paddingSection: 24 // padding sections

    // ══════════════════════════════════════════════
    //  RAYONS DE BORD
    // ══════════════════════════════════════════════

    readonly property int radiusSmall:  4
    readonly property int radiusMedium: 6
    readonly property int radiusLarge:  8
    readonly property int radiusXL:     12
    readonly property int radiusRound:  999

    // Alias de commodité
    readonly property int radius8:  radiusLarge  // 8
    readonly property int radius12: radiusXL     // 12

    // ══════════════════════════════════════════════
    //  OMBRES (valeurs pour DropShadow / layer.effect)
    // ══════════════════════════════════════════════

    readonly property int shadowSmallRadius:  4
    readonly property real shadowSmallOpacity: 0.15

    readonly property int shadowMediumRadius: 8
    readonly property real shadowMediumOpacity: 0.20

    readonly property int shadowLargeRadius:  16
    readonly property real shadowLargeOpacity: 0.30

    // ══════════════════════════════════════════════
    //  ANIMATIONS
    // ══════════════════════════════════════════════

    readonly property int animFast:    80
    readonly property int animNormal:  120
    readonly property int animSlow:    200
    readonly property int animPage:    150

    // Easing types are used directly in Behavior/NumberAnimation

    // ══════════════════════════════════════════════
    //  DIMENSIONS COMPOSANTS
    // ══════════════════════════════════════════════

    readonly property int sidebarWidth:  260
    readonly property int headerHeight:  40
    readonly property int bottomBarHeight: 36
    readonly property int inputHeight:   36
    readonly property int buttonHeight:  32
    readonly property int navItemHeight: 38
    readonly property int iconSize:      18
    readonly property int iconSizeLarge: 24

    // Indicateurs
    readonly property int badgeSize:     20
    readonly property int dotSize:       8
    readonly property int progressHeight: 4
    readonly property int tabHeight:     36
    readonly property int sheetWidth:    360

    // ══════════════════════════════════════════════
    //  HELPERS
    // ══════════════════════════════════════════════

    function stateColor(state) {
        switch (state) {
        case "Listening":    return stateListening
        case "Transcribing": return stateTranscribing
        case "Thinking":     return stateThinking
        case "Speaking":     return stateSpeaking
        default:             return stateIdle
        }
    }

    function pipelineStateColor(state) {
        switch (state) {
        case "active":      return pipelineActive
        case "processing":  return pipelineProcessing
        case "error":       return pipelineError
        case "unavailable": return pipelineUnavail
        default:            return pipelineIdle
        }
    }

    function healthColor(status) {
        // v6 — vocabulaire normalisé EXO (4 états canoniques) :
        //   ready    → vert  (service opérationnel)
        //   starting → jaune (en cours de démarrage / dégradé)
        //   error    → rouge (en panne / planté / injoignable)
        //   disabled → gris  (non géré / non configuré / arrêté volontairement)
        if (status === "ready")    return success
        if (status === "starting") return warning
        if (status === "error")    return error
        if (status === "disabled") return textMuted

        // Compat ascendante — anciennes valeurs HealthCheck/ServiceSupervisor
        if (status === "healthy")  return success
        if (status === "degraded") return warning
        if (status === "down" || status === "failed" || status === "crashed") return error
        if (status === "waiting_ready" || status === "restarting") return warning
        return textMuted
    }

    // Normalise n'importe quelle valeur d'état brute vers les 4 états canoniques.
    // Utilisé par BottomBar (et autres consommateurs) pour garantir une vue
    // cohérente quelle que soit la source (HealthCheck / ServiceSupervisor / WS).
    function normalizeServiceState(raw) {
        if (!raw) return "disabled"
        var s = String(raw).toLowerCase()
        if (s === "ready" || s === "healthy")
            return "ready"
        if (s === "starting" || s === "waiting_ready" || s === "restarting" || s === "degraded")
            return "starting"
        if (s === "error" || s === "failed" || s === "crashed" || s === "down" || s === "stopped")
            return "error"
        // unknown, disabled, "" → service non géré / non configuré
        return "disabled"
    }

    // Lookup de couleur par nom de token
    function color(name) {
        var map = {
            "background": bgPrimary, "surface": bgSecondary,
            "surfaceElevated": bgElevated, "accent": accent,
            "accentSecondary": accentLight, "success": success,
            "warning": warning, "error": error, "info": info,
            "textPrimary": textPrimary, "textSecondary": textSecondary,
            "textDisabled": textDisabled, "border": border
        }
        return map[name] || textPrimary
    }

    // Couleur sémantique avec variante
    function semanticColor(level, variant) {
        var base = { "success": success, "warning": warning, "error": error, "info": info }
        if (variant === "hover") {
            var h = { "success": successHover, "warning": warningHover, "error": errorHover, "info": infoHover }
            return h[level] || base[level] || textMuted
        }
        if (variant === "dim") {
            var d = { "success": successDim, "warning": warningDim, "error": errorDim, "info": infoDim }
            return d[level] || base[level] || textMuted
        }
        return base[level] || textMuted
    }
}
