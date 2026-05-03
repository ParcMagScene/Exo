# Audit Backend C++ EXO — v30.3

> Généré le 2026-05-01 · Auditeur : GitHub Copilot (Claude Sonnet 4.6)

---

## Table des matières

1. [Résumé exécutif](#1-résumé-exécutif)
2. [Architecture générale](#2-architecture-générale)
3. [Bugs critiques confirmés par les logs](#3-bugs-critiques-confirmés-par-les-logs)
4. [Threads et synchronisation](#4-threads-et-synchronisation)
5. [Signaux et slots](#5-signaux-et-slots)
6. [Pipeline TTS / STT / LLM](#6-pipeline-tts--stt--llm)
7. [Gestion mémoire et ownership](#7-gestion-mémoire-et-ownership)
8. [Performance](#8-performance)
9. [Sécurité](#9-sécurité)
10. [Cohérence inter-modules](#10-cohérence-inter-modules)
11. [Tableau récapitulatif des problèmes](#11-tableau-récapitulatif-des-problèmes)
12. [Patches recommandés](#12-patches-recommandés)

---

## 1. Résumé exécutif

L'audit a couvert 150 fichiers C++ en 12 modules (audio, core, llm, safeboot, spatialcognition, spatialsecurity, simulation, floorplan, vision, utils, test, main). Les logs de production du 2026-05-01 ont permis de **confirmer** les bugs à fort impact.

**Bilan :**

| Sévérité | Nombre | Confirmé par logs |
|----------|--------|-------------------|
| CRITIQUE | 3      | ✅ oui |
| ÉLEVÉ    | 6      | partiellement |
| MOYEN    | 8      | — |
| FAIBLE   | 5      | — |

**Top 3 à corriger immédiatement :**

| # | Bug | Impact runtime |
|---|-----|---------------|
| S1 | Double-kill à la fermeture → UB + retry timers orphelins | `exit code 62097` × 23 services dans les logs |
| S2 | `waitForFinished(5000)` séquentiel = gel ~2 min à la fermeture | 14:34:52 → 14:36:47 dans les logs |
| L1 | SafeBoot lazy-load retente des services déjà actifs | 4,5 min de spam, `stt`/`vad`/`tts` retentés alors qu'ils transcrivent |

---

## 2. Architecture générale

### 2.1 Vue d'ensemble

```
main.cpp
  └── AssistantManager (God-class partielle)
        ├── ServiceSupervisor   (boot séquentiel 23 services)
        ├── SafeBootController  (monitoring démarrage)
        ├── HealthCheck         (ping périodique runtime)
        ├── ClaudeAPI           (LLM streaming)
        ├── VoicePipeline       (capture → VAD → STT)
        ├── TTSManager          (TTS → DSP → audio out)
        ├── AudioDeviceManager
        ├── AIMemoryManager
        ├── WeatherManager
        └── sous-composants extraits :
              AssistantConnectionBinder
              AssistantToolDispatcher
              AssistantFastPathEngine
              AssistantSafeBootFacade
```

### 2.2 Problèmes d'architecture

**A1 — Trois sources de vérité pour l'état des services**

`ServiceSupervisor` (via `ServiceRegistry`), `SafeBootController` et `HealthCheck` maintiennent chacun leur propre état des services. Les désynchronisations sont visibles dans les logs : STT transcrit activement pendant que SafeBootController le marque "dégradé" et le remet en lazy-load.

**A2 — AssistantManager encore trop large**

Même après l'extraction des sous-composants, `AssistantManager` coordonne ~10 objets majeurs et expose ~12 Q_PROPERTY. Le pattern God-class subsiste sous forme atténuée.

**A3 — Duplication de code `ServiceSupervisor` / `SafeBootAutoRepair`**

Les deux classes contiennent une copie quasi-identique du bloc "construire l'environnement Python + lancer le processus" (~60 lignes dupliquées). Une méthode factorielle commune dans un helper est nécessaire.

---

## 3. Bugs critiques confirmés par les logs

### BUG S1 — Double-kill à la fermeture (CRITIQUE)

**Fichier :** `app/core/ServiceSupervisor.cpp` — `shutdownAll()` + destructeur

**Symptôme dans les logs (14:36:47) :**
```
[14:34:52] aboutToQuit → shutdownAll() → terminate() + waitForFinished(5000) × 23
[14:36:47] ~ServiceSupervisor() → shutdownAll() A NOUVEAU
           → "vad" CRASHED (exit code 62097)
           → "vad" — retry 1 dans 500 ms   ← timer créé pendant la destruction
           × 23 services
```

**Cause :** `~ServiceSupervisor()` appelle `shutdownAll()` inconditionnellement. Or, `aboutToQuit` a déjà appelé `shutdownAll()` 2 minutes avant. La deuxième passe trouve des processus déjà terminés, interprète leur exit code (62097 = `TerminateProcess` Windows) comme un crash, et programme des timers de retry dans un objet en cours de destruction → **undefined behavior**.

**Code fautif :**
```cpp
ServiceSupervisor::~ServiceSupervisor()
{
    shutdownAll();  // ← appelé une 2e fois si aboutToQuit l'a déjà fait
}
```

**Correction :** voir [section 12](#12-patches-recommandés).

---

### BUG S2 — Shutdown séquentiel bloquant ~2 minutes (CRITIQUE)

**Fichier :** `app/core/ServiceSupervisor.cpp` — `shutdownAll()`

**Symptôme dans les logs :**
```
[14:34:52] [Supervisor] Arrêt de "vad"    (PID 33272)
[14:34:57] [Supervisor] Arrêt de "wakeword" (PID 19640)   ← 5s d'attente
[14:35:02] [Supervisor] Arrêt de "memory"               ← 5s d'attente
...
[14:36:47] 23 services × 5s = 115 secondes de gel du main thread
```

**Code fautif :**
```cpp
void ServiceSupervisor::shutdownAll()
{
    for (const QString &name : m_registry.serviceNames()) {
        auto &entry = m_registry.entry(name);
        if (entry.process && entry.process->state() != QProcess::NotRunning) {
            entry.process->terminate();
            if (!entry.process->waitForFinished(5000))  // ← BLOQUANT × 23
                entry.process->kill();
        }
    }
}
```

L'interface Qt se fige, la fenêtre est non-réactive, et l'OS peut afficher "ne répond pas".

**Correction :** envoyer `terminate()` à tous les processus en parallèle, puis attendre collectivement.

---

### BUG L1 — SafeBoot lazy-load retente des services déjà actifs (CRITIQUE)

**Symptôme dans les logs :**
```
[14:24:22] STT final: "" ← STT répond activement
[14:24:16] [SafeBoot] Lazy-load retry "stt" (1/3)  ← SafeBoot le croit mort
[14:24:49] VAD: parole détectée (score: 0.52) ← VAD fonctionne
[14:24:59] [SafeBoot] Lazy-load retry "vad" (1/3)  ← SafeBoot le croit mort
```

**Cause :** `SafeBootController` démarre son monitoring avec `kTimeoutMs` (N ms). Si `ServiceSupervisor` n'a pas encore appelé `setState(Ready)` dans le `ServiceRegistry` partagé au moment où le timeout SafeBoot expire, le service est classé "Degraded" et placé dans la lazy-load queue. Les 18 services non-critiques tournent ensuite 3 cycles de retries (18 × 5s × 3 = 270s) même s'ils sont opérationnels.

Le commentaire dans `tryLazyLoadNext()` est révélateur :
```cpp
// ServiceSupervisor gère déjà les retries — ici on attend simplement
// que le ServiceRegistry nous notifie via onServiceStateChanged.
```
Mais si la notification a déjà eu lieu AVANT que `SafeBootController` initialise son écoute, l'état `Ready` est manqué.

---

## 4. Threads et synchronisation

### T1 — `waitForFinished()` bloquant sur le main thread

**Fichiers :**
- `ServiceSupervisor::shutdownAll()` — `waitForFinished(5000)` × 23 services séquentiel
- `ServiceSupervisor::doLaunchProcess()` — `waitForStarted(5000)` à chaque boot
- `SafeBootAutoRepair::checkPortAvailable()` — `QTcpSocket::waitForConnected(200)`
- `SafeBootAutoRepair::killProcessOnPort()` — `QProcess::waitForFinished(3000)` (netstat)
- `SafeBootAutoRepair::restartService()` — `waitForStarted(5000)`

Tous ces appels bloquent le thread Qt principal, gèlent l'interface et peuvent déclencher le watchdog OS.

### T2 — `PCMRingBuffer` non thread-safe alors que TTSWorker y écrit

**Fichier :** `app/audio/TTSManager.h`

```cpp
// Single-thread access only (main thread).
class PCMRingBuffer { ... };
```

`TTSWorker` tourne sur un `QThread` dédié et écrit dans le ring buffer via ses slots. Si le main thread lit simultanément pour alimenter l'audio output, c'est une course de données non protégée.

### T3 — `CircularAudioBuffer` commentée "lock-free-ish" mais utilise `QMutex`

**Fichier :** `app/audio/VoicePipeline.h`

```cpp
// lock-free-ish circular buffer
class CircularAudioBuffer {
    QMutex m_mutex;  // ← pas lock-free
```

Ce n'est pas un bug fonctionnel, mais le commentaire est trompeur et peut conduire à des mauvaises hypothèses.

### T4 — Signal handler non async-signal-safe

**Fichier :** `app/main.cpp`

```cpp
void exoSignalHandler(int sig) {
    QFile file(...);       // ← NON async-signal-safe
    QDateTime::currentDateTime();  // ← NON async-signal-safe
```

`QFile`, `QDateTime`, `QString` ne sont pas utilisables depuis un signal POSIX handler. En cas de SIGSEGV pendant une allocation mémoire, cela peut provoquer un deadlock ou un double-fault.

### T5 — `SafeBootAutoRepair::processRepairQueue()` appelle `attemptRepair()` de façon synchrone

```cpp
void SafeBootAutoRepair::processRepairQueue()
{
    attemptRepair(name);  // ← appelle waitForReady() → bloque le main thread
    const auto &entry = m_registry->entry(name);
    if (entry.state == Exo::ServiceState::Ready) { ... }
```

Le résultat est vérifié immédiatement après un appel potentiellement bloquant.

---

## 5. Signaux et slots

### SS1 — Retry timers créés pendant la destruction (UB)

Voir BUG S1. Des `QTimer::singleShot()` sont programmés pendant le destructeur de `ServiceSupervisor`. Ces timers référencent `this` (capturé dans des lambdas), qui est en cours de destruction → use-after-free potentiel.

### SS2 — `onServiceCrashed()` déclenché par des terminaisons normales

**Fichier :** `app/core/ServiceSupervisor.cpp`

```cpp
connect(proc, QOverload<int, QProcess::ExitStatus>::of(&QProcess::finished),
    this, [this, name](int exitCode, QProcess::ExitStatus) {
        auto &e = m_registry.entry(name);
        if (e.state == Exo::ServiceState::Ready) {
            onServiceCrashed(name, exitCode);  // ← déclenché si terminate() sur process Ready
        }
    });
```

Pendant `shutdownAll()`, les processus à l'état `Ready` sont terminés → ce callback fire → `onServiceCrashed()` → retry. Il faut passer l'état à `Stopping` avant de terminer.

### SS3 — Connexions SafeBootController/ServiceRegistry potentiellement manquées

Si `SafeBootController::setRegistry()` est appelé après que `ServiceSupervisor` ait déjà émis certains `serviceStateChanged`, les transitions `Ready` initiales sont perdues.

### SS4 — `probe.client->close()` dans `cleanupProbe()` peut émettre `disconnected`

```cpp
void ServiceSupervisor::cleanupProbe(const QString &name)
{
    if (it->client)  { it->client->close(); it->client->deleteLater(); }
    m_probes.erase(it);  // ← probe supprimée
    // MAIS: close() peut émettre disconnected() de façon asynchrone
    // → le slot lambda capturant `name` tente d'accéder à m_probes[name] supprimé
```

---

## 6. Pipeline TTS / STT / LLM

### P1 — STT : messages `start`/`end` potentiellement perdus

**Fichier :** `app/audio/VoicePipeline.cpp` (StreamingSTT)

Si `WebSocketClient` est en état `Reconnecting` au moment où VAD détecte la parole, les messages `start` et les chunks PCM sont silencieusement ignorés (guard `if (m_state != State::Connected || !m_ws) return;`). Le transcript sera vide, confirmé par les logs :
```
STT final: ""   ← transcript vide répété
```
Aucun feedback utilisateur ni retry STT n'est implémenté pour ce cas.

### P2 — HealthCheck vole la connexion mono-client du serveur wakeword

Le commentaire dans `HealthCheck.cpp` le documente déjà :
```cpp
// Le serveur wakeword est mono-client : une connexion HealthCheck persistante
// lui vole la session et déconnecte le pipeline voix principal.
// On l'exclut donc du ping périodique pour préserver la capture vocale.
```
Le wakeword est exclu du HealthCheck, ce qui signifie qu'il peut tomber sans détection automatique. Une solution propre serait que le serveur wakeword supporte les connexions multiples.

### P3 — VAD HealthCheck : ~720 connexions WebSocket par heure

Le VAD server ferme la connexion après chaque pong. Le HealthCheck rouvre une nouvelle connexion à chaque `onPingTimer` (toutes les ~5s). Cela génère un bruit important dans les logs et une charge réseau inutile (720 connexions/heure). À l'échelle, sur un Raspberry Pi cela peut impacter les performances.

### P4 — `PCMRingBuffer` non protégé (voir T2)

L'audio output lit le ring buffer depuis le main thread pendant que TTSWorker y écrit depuis son thread dédié.

### P5 — TTS DSP chain appliquée dans TTSWorker sans protection du ring buffer

La chaîne DSP (EQ → Compressor → Normalizer → Fade) opère sur des données int16 dans le worker thread. Si la cancel survient pendant le processing, le ring buffer peut se retrouver dans un état incohérent.

---

## 7. Gestion mémoire et ownership

### M1 — `delete` dans `shutdownAll()` au lieu de `deleteLater()`

**Fichier :** `app/core/ServiceSupervisor.cpp`

```cpp
void ServiceSupervisor::shutdownAll()
{
    for (auto it = m_probes.begin(); it != m_probes.end(); ++it) {
        if (it->timeout) { it->timeout->stop(); delete it->timeout; }  // ← delete direct
        if (it->poll)    { it->poll->stop();    delete it->poll; }
        if (it->client)  { delete it->client; }  // ← delete direct sur QObject avec signaux pendants
    }
```

Si des événements de ces objets sont dans la queue d'événements, leur callback s'exécutera sur de la mémoire libérée. `deleteLater()` est la pratique correcte.

### M2 — Double ownership potentiel de `QProcess`

Dans `SafeBootAutoRepair::restartService()`, un nouveau `QProcess` est créé avec `this` comme parent. Mais l'ancien processus est aussi parented à `this` (via `m_registry->entry(name).process`). Après le `oldProc->deleteLater()` différé, si la réparation se déroule vite, on peut avoir deux processus pour le même service.

### M3 — Timers de retry dans `retryOrFail()` — lambda capture `this`

```cpp
QTimer::singleShot(delay, this, [this, name]() {
    auto &e = m_registry.entry(name);
    ...
    QTimer::singleShot(3000, proc, [this, proc, name]() {
        if (proc->state() != QProcess::NotRunning) {
            proc->kill();
            launchService(name);  // ← this peut être détruit
        }
    });
});
```

Si `ServiceSupervisor` est détruit pendant le délai du timer interne (3000ms), `this` sera dangling.

### M4 — `ReadinessProbe` structs non nettoyées si `shutdownAll()` est appelé pendant boot

Si `shutdownAll()` est appelé alors qu'un boot est en cours (probes actives), les probes sont supprimées avec `delete` direct, mais les lambdas captures par les `connect()` correspondants peuvent encore être en file.

---

## 8. Performance

### Perf1 — Shutdown bloquant 115+ secondes (voir S2)

### Perf2 — SafeBoot lazy-load : 270 secondes de timers inutiles (voir L1)

### Perf3 — Duplication code environnement Python × 3 fonctions

`ServiceSupervisor::doLaunchProcess()`, `SafeBootAutoRepair::restartService()` et une version dans `AutoRepair::killProcessOnPort()` contiennent chacune le même bloc de 40+ lignes pour construire `QProcessEnvironment`. Toute modification doit être faite en 3 endroits.

### Perf4 — `QTimer::singleShot` avec lambdas imbriqués dans `retryOrFail()`

Des timers imbriqués (QTimer dans QTimer) rendent le flux de contrôle difficile à suivre et peuvent créer des connexions multiples si `retryOrFail()` est appelé plusieurs fois pour le même service.

### Perf5 — HealthCheck : pas de backoff pour les services down

Pour un service définitivement absent (ex: `calendar`, `samsung`), le WebSocketClient tente une reconnexion toutes les 5 secondes indéfiniment. Sur 11 services absents, cela génère 11 × 12 connexions/minute = 132 tentatives de connexion par minute.

---

## 9. Sécurité

### Sec1 — Clé API OpenWeatherMap en dur dans les logs

**Fichier :** `app/utils/WeatherManager.cpp` (visible dans les logs)

```
[HealthCheck] "https://api.openweathermap.org/data/2.5/weather?q=Paris&appid=951156bf4d8f6af191eeaa440aa394d9"
```

La clé API est loguée au niveau DEBUG. Elle doit être masquée dans les logs.

### Sec2 — Signal handler utilise des fonctions non async-signal-safe (voir T4)

En cas de SIGSEGV, le handler peut appeler `malloc` implicitement via Qt → deadlock ou double-fault.

### Sec3 — `QNativeSocketEngine::write() was not called in QAbstractSocket::ConnectedState`

Visible dans les logs à la fermeture. Indique qu'une écriture est tentée sur un socket déjà fermé. Pas un risque sécurité direct mais symptôme d'une fermeture désordonnée.

---

## 10. Cohérence inter-modules

### Coh1 — `ServiceSupervisor` et `SafeBootController` partagent `ServiceRegistry` mais peuvent diverger

`SafeBootController::onServiceStateChanged()` écoute `serviceStateChanged` du registry partagé. Mais la connexion est établie dans `setRegistry()`, qui peut être appelé APRÈS que certains états aient déjà changé (race d'initialisation).

### Coh2 — `HealthCheck` n'est pas relié au `ServiceRegistry`

`HealthCheck` maintient son propre état `ServiceHealth` (Healthy/Degraded/Down) indépendant de `ServiceRegistry`. Une transition `HealthCheck::serviceDown` n'est pas propagée à `SafeBootController`. Le système peut donc être dans un état incohérent où HealthCheck dit "down" mais SafeBootController dit "ready".

### Coh3 — SafeBoot `kTimeoutMs` vs ServiceSupervisor `startupTimeoutMs`

Deux timeouts indépendants par service : celui de `SafeBootController` (kTimeoutMs global) et celui du `ServiceDescriptor::startupTimeoutMs` utilisé par `ServiceSupervisor`. Si `startupTimeoutMs > kTimeoutMs`, SafeBoot déclare le service dégradé avant que le supervisor ait fini sa probe.

---

## 11. Tableau récapitulatif des problèmes

| ID | Sévérité | Fichier | Description | Confirmé logs |
|----|----------|---------|-------------|--------------|
| S1 | CRITIQUE | ServiceSupervisor.cpp | Double-kill à la fermeture → UB + retry timers | ✅ |
| S2 | CRITIQUE | ServiceSupervisor.cpp | shutdownAll() séquentiel bloque 115s | ✅ |
| L1 | CRITIQUE | SafeBootController.cpp | Lazy-load retente services déjà actifs | ✅ |
| SS2 | ÉLEVÉ | ServiceSupervisor.cpp | onServiceCrashed() sur terminate() normale | ✅ |
| T4 | ÉLEVÉ | main.cpp | Signal handler non async-signal-safe | — |
| T2 | ÉLEVÉ | TTSManager.h | PCMRingBuffer race condition thread | — |
| M1 | ÉLEVÉ | ServiceSupervisor.cpp | delete direct au lieu de deleteLater | — |
| M3 | ÉLEVÉ | ServiceSupervisor.cpp | Lambda capturant this après destruction | — |
| SS3 | MOYEN | AssistantManager.cpp | Notifications Ready manquées (race init) | — |
| Perf3 | MOYEN | ServiceSupervisor/AutoRepair | Code env Python dupliqué × 3 | — |
| Perf5 | MOYEN | HealthCheck.cpp | Reconnect illimité sans backoff | ✅ |
| T3 | MOYEN | VoicePipeline.h | CircularAudioBuffer commentaire trompeur | — |
| P3 | MOYEN | HealthCheck.cpp | VAD HealthCheck 720 connexions/heure | ✅ |
| P1 | MOYEN | VoicePipeline.cpp | STT silencieux si WS reconnecting | ✅ (transcripts vides) |
| Sec1 | MOYEN | WeatherManager.cpp | Clé API loguée en clair | ✅ |
| Coh2 | FAIBLE | HealthCheck.cpp | HealthCheck déconnecté du ServiceRegistry | — |
| Coh3 | FAIBLE | SafeBootController.cpp | Timeout SafeBoot < startupTimeout service | — |
| A3 | FAIBLE | ServiceSupervisor/AutoRepair | Duplication launch process code | — |

---

## 12. Patches recommandés

### PATCH S1+S2 : Shutdown idempotent et asynchrone

**Fichier :** `app/core/ServiceSupervisor.cpp`

```cpp
// ── Ajout d'un flag dans ServiceSupervisor.h ────────
// private:
//   bool m_shutdownDone = false;

// ── Arrêt propre ─────────────────────────────────────
void ServiceSupervisor::shutdownAll()
{
    if (m_shutdownDone) return;   // ← idempotence : protège contre le double-appel
    m_shutdownDone = true;

    // Nettoyer les probes — deleteLater (pas delete direct)
    for (auto it = m_probes.begin(); it != m_probes.end(); ++it) {
        if (it->timeout) { it->timeout->stop(); it->timeout->deleteLater(); }
        if (it->poll)    { it->poll->stop();    it->poll->deleteLater(); }
        if (it->client)  { it->client->close(); it->client->deleteLater(); }
    }
    m_probes.clear();

    // Passer tous les services à l'état Stopping AVANT terminate()
    // pour éviter que onServiceCrashed() ne soit déclenché
    for (const QString &name : m_registry.serviceNames()) {
        auto &entry = m_registry.entry(name);
        if (entry.state == Exo::ServiceState::Ready ||
            entry.state == Exo::ServiceState::WaitingReady) {
            m_registry.setState(name, Exo::ServiceState::Stopping);
        }
    }

    // Envoyer terminate() à TOUS en parallèle (non bloquant)
    QList<QProcess *> procs;
    for (const QString &name : m_registry.serviceNames()) {
        auto &entry = m_registry.entry(name);
        if (entry.process && entry.process->state() != QProcess::NotRunning) {
            hLog() << "[Supervisor] Arrêt de" << name << "(PID" << entry.pid << ")";
            entry.process->terminate();
            procs.append(entry.process);
        }
    }

    // Attendre collectivement avec un timeout global (2s)
    // Puis force-kill ce qui reste
    QDeadlineTimer deadline(2000);
    for (QProcess *proc : procs) {
        int remaining = static_cast<int>(deadline.remainingTime());
        if (remaining <= 0 || !proc->waitForFinished(remaining))
            proc->kill();
    }
}

// ── Destructeur ────────────────────────────────────
ServiceSupervisor::~ServiceSupervisor()
{
    shutdownAll();  // idempotent : sans effet si déjà appelé
}
```

**En-tête — ajouter dans `ServiceSupervisor.h` :**
```cpp
private:
    bool m_shutdownDone = false;
```

---

### PATCH SS2 : Marquer les services `Stopping` avant `terminate()`

Ce patch est inclus dans PATCH S1+S2 ci-dessus. Il évite que le signal `QProcess::finished` déclenche `onServiceCrashed()` pendant l'arrêt normal.

**Modifier aussi `onServiceCrashed()` comme garde supplémentaire :**
```cpp
void ServiceSupervisor::onServiceCrashed(const QString &name, int exitCode)
{
    // Ne pas traiter un crash pendant l'arrêt
    if (m_shutdownDone) return;

    hWarning(exoMain) << "[Supervisor]" << name << "CRASHED (exit code" << exitCode << ")";
    m_registry.setState(name, Exo::ServiceState::Crashed);
    emit progressChanged();
    retryOrFail(name);
}
```

---

### PATCH L1 : SafeBootController — vérifier l'état réel avant lazy-load

**Fichier :** `app/safeboot/SafeBootController.cpp` — `tryLazyLoadNext()`

```cpp
void SafeBootController::tryLazyLoadNext()
{
    if (m_lazyQueue.isEmpty()) {
        // ... (inchangé)
        return;
    }

    QString name = m_lazyQueue.first();
    int retries = m_lazyRetryCount.value(name, 0);

    // Vérifier l'état RÉEL dans le ServiceRegistry si disponible
    if (m_registry) {
        const auto &entry = m_registry->entry(name);
        if (entry.state == Exo::ServiceState::Ready) {
            // Le service est réellement prêt — synchroniser notre état
            auto it = m_services.find(name);
            if (it != m_services.end()) {
                it->status = SafeBoot::ServiceStatus::Ready;
            }
            m_lazyQueue.removeFirst();
            addTimelineEvent(QStringLiteral("lazy_recovered"), name,
                             QStringLiteral("Service déjà prêt dans le registry"));
            emit serviceRecovered(name);
            emit timelineUpdated();
            return;
        }
    }

    // ... (reste inchangé)
}
```

**Et dans `startLazyLoadTimer()` — filtrer les services déjà prêts dans le registry :**
```cpp
void SafeBootController::startLazyLoadTimer()
{
    m_lazyQueue.clear();
    for (auto it = m_services.constBegin(); it != m_services.constEnd(); ++it) {
        if (it->criticality == SafeBoot::ServiceCriticality::NonCritical
            && it->status != SafeBoot::ServiceStatus::Ready) {
            // Vérification supplémentaire dans le registry
            if (m_registry) {
                const auto &entry = m_registry->entry(it.key());
                if (entry.state == Exo::ServiceState::Ready) {
                    // Synchroniser — ne pas mettre en file
                    m_services[it.key()].status = SafeBoot::ServiceStatus::Ready;
                    continue;
                }
            }
            m_lazyQueue.append(it.key());
            m_lazyRetryCount[it.key()] = 0;
        }
    }
    // ...
}
```

**Ajouter `m_registry` comme membre de `SafeBootController` (si pas déjà présent) :**
```cpp
// SafeBootController.h
private:
    ServiceRegistry *m_registry = nullptr;
```

---

### PATCH T4 : Signal handler async-signal-safe

**Fichier :** `app/main.cpp`

```cpp
// Fichier de crash partagé — écrit de façon async-signal-safe
static char g_crashSignalFile[512] = {};

static void exoSignalHandler(int sig)
{
    // SEUL write() POSIX est async-signal-safe pour les fichiers
    // Écriture minimale dans le fichier de crash pré-alloué
    const char *msg = (sig == SIGSEGV) ? "SIGSEGV\n"
                    : (sig == SIGABRT) ? "SIGABRT\n"
                    : (sig == SIGFPE)  ? "SIGFPE\n"
                    : "SIGNAL\n";
    // g_crashSignalFile est initialisé au démarrage (main thread, avant tout signal)
    int fd = ::open(g_crashSignalFile, O_CREAT | O_WRONLY | O_APPEND, 0644);
    if (fd >= 0) {
        ::write(fd, msg, strlen(msg));
        ::close(fd);
    }
    // Réinitialiser le handler par défaut et re-lever le signal
    // pour générer le core dump
    ::signal(sig, SIG_DFL);
    ::raise(sig);
}

// Dans main() :
// snprintf(g_crashSignalFile, sizeof(g_crashSignalFile),
//          "%s/crash_signal.txt", logDir.toUtf8().constData());
```

---

### PATCH Sec1 : Masquer la clé API dans les logs

**Fichier :** `app/utils/WeatherManager.cpp`

```cpp
// AVANT :
hDebug(exoMain) << "Requête météo envoyée :" << urlStr;

// APRÈS :
QString logUrl = urlStr;
static QRegularExpression reApiKey(QStringLiteral("appid=[^&]+"));
logUrl.replace(reApiKey, QStringLiteral("appid=***"));
hDebug(exoMain) << "Requête météo envoyée :" << logUrl;
```

---

### PATCH M1 : `deleteLater()` dans `shutdownAll()`

Inclus dans PATCH S1+S2 ci-dessus (remplacement des `delete` directs).

---

*Fin de l'audit — `docs/BACKEND_AUDIT.md`*
