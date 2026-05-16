chcp 65001 | Out-Null
$OutputEncoding = [Text.Encoding]::UTF8
[Console]::OutputEncoding = [Text.Encoding]::UTF8
$utf8 = New-Object Text.UTF8Encoding $false
$n = 0
function _R($f, $o, $nv) {
    $full = Join-Path 'D:\EXO' $f
    $c = [IO.File]::ReadAllText($full, $utf8)
    $cnt = ([regex]::Matches($c, [regex]::Escape($o))).Count
    if ($cnt -eq 0) { Write-Host "  [SKIP] $f : $o"; return }
    [IO.File]::WriteAllText($full, $c.Replace($o, $nv), $utf8)
    Write-Host "  [OK x$cnt] $f"
    $script:n += $cnt
}

Write-Host "=== AIMemoryManager ==="
_R 'app\llm\AIMemoryManager.cpp' '"Connecting to semantic memory server:"' '"Connexion au serveur mémoire sémantique :"'
_R 'app\llm\AIMemoryManager.cpp' '"Semantic memory server connected"' '"Serveur mémoire sémantique connecté"'
_R 'app\llm\AIMemoryManager.cpp' '"Semantic server: memory added, id="' '"Serveur sémantique : souvenir ajouté, id="'

Write-Host "`n=== ClaudeAPI ==="
_R 'app\llm\ClaudeAPI.cpp' '"Tool use détecté:"' '"Utilisation d''outil détectée :"'
_R 'app\llm\ClaudeAPI.cpp' '"Tool call complet:"' '"Appel d''outil complet :"'
_R 'app\llm\ClaudeAPI.cpp' '"Stop reason:"' '"Raison d''arrêt :"'
_R 'app\llm\ClaudeAPI.cpp' '"Sentence ready (streaming):"' '"Phrase prête (streaming) :"'
_R 'app\llm\ClaudeAPI.cpp' '"Sentence flush (final):"' '"Phrase finale (flush) :"'
_R 'app\llm\ClaudeAPI.cpp' '"Tool call (sync):"' '"Appel d''outil (sync) :"'

Write-Host "`n=== AssistantToolDispatcher (GUI prefix) ==="
_R 'app\core\AssistantToolDispatcher.cpp' '"GUI network scan:"' '"Scan réseau GUI :"'
_R 'app\core\AssistantToolDispatcher.cpp' '"GUI HomeGraph state requested"' '"État HomeGraph demandé par GUI"'
_R 'app\core\AssistantToolDispatcher.cpp' '"GUI device command:"' '"Commande appareil GUI :"'
_R 'app\core\AssistantToolDispatcher.cpp' '"GUI run scenario:"' '"Exécution scénario GUI :"'
_R 'app\core\AssistantToolDispatcher.cpp' '"Tool socket"' '"Socket outil"'

Write-Host "`n=== AssistantComponentFactory (accents) ==="
_R 'app\core\AssistantComponentFactory.cpp' '"Claude API configure avec le modele:"' '"Claude API configurée avec le modèle :"'
_R 'app\core\AssistantComponentFactory.cpp' '"Memory Manager initialise - memoire EXO activee"' '"Gestionnaire mémoire initialisé — mémoire EXO activée"'
_R 'app\core\AssistantComponentFactory.cpp' '"PipelineTracer initialise - analyse post-interaction activee"' '"PipelineTracer initialisé — analyse post-interaction activée"'
_R 'app\core\AssistantComponentFactory.cpp' '"ContextCache initialise avec regles de rafraichissement"' '"ContextCache initialisé avec règles de rafraîchissement"'
_R 'app\core\AssistantComponentFactory.cpp' '"HealthCheck initialise - surveillance des microservices activee"' '"HealthCheck initialisé — surveillance des microservices activée"'

Write-Host "`n=== ContextCache ==="
_R 'app\core\ContextCache.cpp' '"ContextCache background refresh started — interval:"' '"Rafraîchissement ContextCache en arrière-plan démarré — intervalle :"'

Write-Host "`n=== HealthCheck (concat connected/disconnected) ==="
_R 'app\core\HealthCheck.cpp' '"[HealthCheck]" << name << "connected"' '"[HealthCheck]" << name << "connecté"'
_R 'app\core\HealthCheck.cpp' '"[HealthCheck]" << name << "disconnected"' '"[HealthCheck]" << name << "déconnecté"'

Write-Host "`n=== TestController ==="
_R 'app\test\TestController.cpp' '"[TestController]" << name << "connected"' '"[TestController]" << name << "connecté"'
_R 'app\test\TestController.cpp' '"disconnected while waiting for pong"' '"déconnecté pendant attente du pong"'

Write-Host "`n=== ServiceSupervisor ==="
_R 'app\core\ServiceSupervisor.cpp' '"[Supervisor] ✓" << name << "READY"' '"[Superviseur] ✓" << name << "PRÊT"'

Write-Host "`n=== TTSBackendXTTS ==="
_R 'app\audio\TTSBackendXTTS.cpp' '"[TTS] XTTS v2 ready message:"' '"[TTS] Message prêt XTTS v2 :"'

Write-Host "`n=== TTSAudioSinkRtAudio (accents + EN restant) ==="
_R 'app\audio\TTSAudioSinkRtAudio.cpp' '"TTSAudioSinkRtAudio: openStream FAIL"' '"TTSAudioSinkRtAudio : échec ouverture stream"'
_R 'app\audio\TTSAudioSinkRtAudio.cpp' '"TTSAudioSinkRtAudio: stream OUVERT (pas encore demarre), bufferFrames negociees:"' '"TTSAudioSinkRtAudio : stream ouvert (pas encore démarré), bufferFrames négociées :"'
_R 'app\audio\TTSAudioSinkRtAudio.cpp' '"TTSAudioSinkRtAudio::start() sans openStream prealable"' '"TTSAudioSinkRtAudio::start() sans openStream préalable"'
_R 'app\audio\TTSAudioSinkRtAudio.cpp' '"TTSAudioSinkRtAudio: startStream FAIL"' '"TTSAudioSinkRtAudio : échec démarrage stream"'
_R 'app\audio\TTSAudioSinkRtAudio.cpp' '"TTSAudioSinkRtAudio: stream DEMARRE"' '"TTSAudioSinkRtAudio : stream démarré"'

Write-Host "`n=== TOTAL: $n substitutions ==="
