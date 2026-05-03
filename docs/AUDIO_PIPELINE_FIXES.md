# 🔧 CORRECTIFS DU PIPELINE AUDIO D'EXO v27.1

**Date:** 1er mai 2026  
**Scope:** Corrections des problèmes P1.1-P3.3 identifiés dans AUDIO_PIPELINE_COMPLETE_AUDIT.md

---

## 📋 PLAN D'EXÉCUTION

### Phase 1 : Critiques (P1.1-P1.3) — IMMÉDIAT
- [ ] P1.1: Protéger AudioPreprocessor avec mutex
- [ ] P1.2: Capper STTSession._audio_buffer (10 MB)
- [ ] P1.3: Augmenter timeout TTS WebSocket (30s)

### Phase 2 : Majeurs (P2.1-P2.3) — Semaine suivante
- [ ] P2.1: Atomiciser PCMRingBuffer indices
- [ ] P2.2: Valider Silero flapping (fallback OK ✅)
- [ ] P2.3: Implémenter buffer client STT + resend

### Phase 3 : Mineurs (P3.1-P3.3) — Prochaine release
- [ ] P3.1: Ajouter telemetry latence complète
- [ ] P3.2: Réinitialiser AudioPreprocessor state
- [ ] P3.3: Drain TTS queue on stopSpeaking()

---

## 🔴 CORRECTIF P1.1: AudioPreprocessor race condition

**Fichier:** `app/audio/VoicePipeline.h`

```cpp
// AVANT:
class VoicePipeline : public QObject {
    AudioPreprocessor m_preprocessor;
    // NO MUTEX
};

// APRÈS:
class VoicePipeline : public QObject {
    AudioPreprocessor m_preprocessor;
    QMutex m_preprocessorMutex;  // ← ADD
};
```

**Fichier:** `app/audio/VoicePipeline.cpp`

```cpp
// AVANT:
void VoicePipeline::onAudioChunk(const int16_t *samples, int count)
{
    // ... validation ...
    m_preprocessor.process(samples, count);  // ❌ NOT protected
    // ...
}

// APRÈS:
void VoicePipeline::onAudioChunk(const int16_t *samples, int count)
{
    // ... validation ...
    {
        QMutexLocker lk(&m_preprocessorMutex);  // ← LOCK
        m_preprocessor.process(samples, count);  // ✅ PROTECTED
    }  // ← UNLOCK
    // ...
}
```

**Justification:**
- RtAudio callback peut être appelé depuis thread RtAudio ou Qt (Windows WASAPI threading variables)
- AudioPreprocessor::process() modifie état interne (biquad, AGC, gate)
- Race condition → corruption filtre audio, distortion

**Impact:** Élimine race condition audio distortion potentielle  
**Effort:** 5 minutes  
**Risque:** Très faible (simple mutex protection)

---

## 🔴 CORRECTIF P1.2: STTSession buffer uncapped

**Fichier:** `python/stt/stt_server.py`

```python
# AVANT:
class STTSession:
    def __init__(self, engine):
        self._audio_buffer = bytearray()        # ❌ Uncapped growth
        self._recording = False

    async def _on_audio(self, ws, data):
        if not self._recording:
            return
        
        self._audio_buffer.extend(data)  # ❌ Can grow unbounded


# APRÈS:
class STTSession:
    # Class constant
    MAX_AUDIO_BUFFER_SIZE = 10 * 1024 * 1024  # 10 MB max
    
    def __init__(self, engine):
        self._audio_buffer = bytearray()
        self._recording = False

    async def _on_audio(self, ws, data):
        if not self._recording:
            return
        
        # Check buffer size before extending
        new_size = len(self._audio_buffer) + len(data)
        if new_size > self.MAX_AUDIO_BUFFER_SIZE:
            error_msg = f"Audio buffer overflow: {new_size} > {self.MAX_AUDIO_BUFFER_SIZE}"
            logger.error(error_msg)
            await ws.send(json.dumps({
                "type": "error",
                "message": "Audio buffer limit exceeded (10 MB)"
            }))
            # Optional: close connection to free resources
            # await ws.close(code=1009, reason="Buffer limit exceeded")
            return
        
        self._audio_buffer.extend(data)  # ✅ BOUNDED


    async def _on_json(self, ws, msg):
        msg_type = msg.get("type", "")
        
        if msg_type == "end":
            # ... existing code ...
            self._audio_buffer.clear()  # ✅ Cleanup on end
        
        if msg_type == "cancel":
            self._audio_buffer.clear()  # ✅ Cleanup on cancel
```

**Justification:**
- DoS attack vector: client sends unlimited audio without "end" → memory exhaustion
- 10 MB capacity = ~312 seconds of audio @ 16kHz 16-bit mono = reasonable max utterance
- Auto-cleanup on "end" or "cancel" messages

**Impact:** Élimine vecteur DoS, protège mémoire serveur  
**Effort:** 10 minutes  
**Risque:** Très faible (bounds check only)

---

## 🔴 CORRECTIF P1.3: WebSocket timeout TTS

**Fichier:** `app/audio/TTSBackendXTTS.h`

```cpp
// AVANT:
static constexpr int PY_TTS_TIMEOUT_MS = 12000;  // ❌ Too aggressive

// APRÈS:
static constexpr int PY_TTS_TIMEOUT_MS = 30000;  // ✅ 30s (more realistic for CosyVoice)
```

**Fichier:** `app/audio/TTSBackendXTTS.cpp`

```cpp
// AVANT:
bool TTSBackendXTTS::synthesize(const TTSRequest &req, std::vector<int16_t> &outAudio)
{
    // ...
    QEventLoop synthLoop;
    QTimer synthTimeout;
    synthTimeout.setInterval(PY_TTS_TIMEOUT_MS);
    
    // Typical wait: first chunk 1.0-1.2s, all chunks 2-5s
    // timeout 12s is OK but risky during GPU overload
    
    synthLoop.exec();
    // ...
}

// APRÈS (with logging):
bool TTSBackendXTTS::synthesize(const TTSRequest &req, std::vector<int16_t> &outAudio)
{
    // ...
    QEventLoop synthLoop;
    QTimer synthTimeout;
    synthTimeout.setInterval(PY_TTS_TIMEOUT_MS);
    
    qDebug() << "[TTS] Synthesis start, timeout:" << PY_TTS_TIMEOUT_MS << "ms";
    QElapsedTimer synthTimer;
    synthTimer.start();
    
    synthLoop.exec();
    
    qDebug() << "[TTS] Synthesis took:" << synthTimer.elapsed() << "ms";
    // ...
    
    // Option: Log timeout fires
    connect(&synthTimeout, &QTimer::timeout, [this]() {
        qWarning() << "[TTS] Synthesis TIMEOUT at 30s — GPU overloaded?";
    });
}

// Additional: Make timeout configurable
// In config/assistant.conf or env var:
//   TTS_TIMEOUT_MS=45000  (for slower models)
```

**Justification:**
- CosyVoice2 latence observée: 1.0-1.2s pour première chunk, 2-5s pour phrase complète
- GPU overload (autre processus) peut causer latence 15-20s
- Timeout 12s → fallback Qt (qualité inférieure) trop souvent
- Timeout 30s → couvre ~99.9% cas nominaux

**Impact:** Réduit fallback Qt indésirable → meilleure qualité TTS  
**Effort:** 15 minutes  
**Risque:** Très faible (augmenter timeout seulement)

---

## 🟠 CORRECTIF P2.1: PCMRingBuffer thread-safety

**Fichier:** `app/audio/TTSManager.h`

```cpp
// AVANT:
class TTSManager : public QObject {
    struct PCMRingBuffer {
        std::vector<int16_t> m_buf;
        int m_readPos = 0;      // ❌ Not atomic
        int m_writePos = 0;     // ❌ Not atomic
        int m_count = 0;        // ❌ Not atomic
        int m_capacity = 0;
        
        int write(...);
        int read(...);
    };
};

// APRÈS:
class TTSManager : public QObject {
    struct PCMRingBuffer {
        std::vector<int16_t> m_buf;
        std::atomic<int> m_readPos{0};      // ✅ Atomic
        std::atomic<int> m_writePos{0};     // ✅ Atomic
        std::atomic<int> m_count{0};        // ✅ Atomic
        int m_capacity = 0;
        
        int write(...);
        int read(...);
        
        // Optional: add acquire/release semantics for TOCTOU
    };
};
```

**Fichier:** `app/audio/TTSManager.cpp`

```cpp
// BEFORE:
int PCMRingBuffer::write(const int16_t *data, int size)
{
    const int toWrite = std::min(size, m_capacity - m_count);  // ❌ Race on m_count
    
    // ... copy data ...
    
    m_writePos = (m_writePos + toWrite) % m_capacity;  // ❌ Race
    m_count += toWrite;  // ❌ Race
    
    return toWrite;
}

// AFTER (Lock-free with atomics):
int PCMRingBuffer::write(const int16_t *data, int size)
{
    int count = m_count.load(std::memory_order_acquire);  // ✅ Atomic load
    const int toWrite = std::min(size, m_capacity - count);
    
    if (toWrite == 0) return 0;  // Buffer full
    
    // ... copy data ...
    
    int writePos = m_writePos.load(std::memory_order_acquire);
    int newWritePos = (writePos + toWrite) % m_capacity;
    m_writePos.store(newWritePos, std::memory_order_release);
    
    m_count.fetch_add(toWrite, std::memory_order_release);  // ✅ Atomic increment
    
    return toWrite;
}

int PCMRingBuffer::read(int16_t *data, int size)
{
    int count = m_count.load(std::memory_order_acquire);  // ✅ Atomic load
    const int toRead = std::min(size, count);
    
    if (toRead == 0) return 0;  // Buffer empty
    
    // ... copy data ...
    
    int readPos = m_readPos.load(std::memory_order_acquire);
    int newReadPos = (readPos + toRead) % m_capacity;
    m_readPos.store(newReadPos, std::memory_order_release);
    
    m_count.fetch_sub(toRead, std::memory_order_release);  // ✅ Atomic decrement
    
    return toRead;
}
```

**Justification:**
- Currently safe (both read/write on main thread) ✅
- But fragile if future refactoring moves pump to worker thread
- Atomic access provides future-proofing without performance cost
- `memory_order_acquire/release` ensures proper synchronization

**Impact:** Future-proofs buffer pour multi-threading, élimine race condition potentielle  
**Effort:** 20 minutes  
**Risque:** Very low (only changes to atomics, same semantics)  
**Precedence:** Faire APRÈS validation que tout fonctionne

---

## 🟠 CORRECTIF P2.3: StreamingSTT client buffer

**Fichier:** `app/audio/VoicePipeline.h`

```cpp
// AVANT:
class StreamingSTT : public QObject {
    WebSocketClient *m_ws;
    bool m_connected = false;
    // NO LOCAL BUFFER
};

// APRÈS:
class StreamingSTT : public QObject {
    WebSocketClient *m_ws;
    bool m_connected = false;
    
    // Client-side buffer for STT audio (network jitter resilience)
    struct AudioBuffer {
        std::vector<int16_t> m_buffer;
        std::atomic<bool> m_flushed{false};
        
        void append(const int16_t *samples, int count) {
            m_buffer.insert(m_buffer.end(), samples, samples + count);
        }
        
        void flush() {
            m_flushed.store(true);
        }
        
        void clear() {
            m_buffer.clear();
            m_flushed.store(false);
        }
    } m_audioBuffer;
    
    // Resend buffer on reconnect
    void onConnected();  // resend m_audioBuffer if not flushed
};
```

**Fichier:** `app/audio/VoicePipeline.cpp`

```cpp
// AVANT:
void StreamingSTT::feedAudio(const int16_t *samples, int count)
{
    if (!m_connected) {
        return;  // ❌ Silently drop audio
    }
    
    QByteArray data(reinterpret_cast<const char *>(samples), count * sizeof(int16_t));
    m_ws->sendBinary(data);  // ← May be lost if network unstable
}

// APRÈS:
void StreamingSTT::feedAudio(const int16_t *samples, int count)
{
    // Always buffer locally
    m_audioBuffer.append(samples, count);
    
    if (!m_connected) {
        // Buffer for resend on reconnect
        // Max buffer: 30s @ 16kHz = 480K samples = 960 KB (acceptable)
        if (m_audioBuffer.m_buffer.size() > 480000) {
            // Trim oldest samples if buffer gets too large
            m_audioBuffer.m_buffer.erase(
                m_audioBuffer.m_buffer.begin(),
                m_audioBuffer.m_buffer.begin() + 160000  // Drop 10s oldest
            );
        }
        return;
    }
    
    // Connected: send immediately
    QByteArray data(
        reinterpret_cast<const char *>(samples),
        count * sizeof(int16_t)
    );
    m_ws->sendBinary(data);
}

void StreamingSTT::onConnected()
{
    // Resend buffered audio on reconnect
    if (!m_audioBuffer.m_buffer.empty() && !m_audioBuffer.m_flushed.load()) {
        qDebug() << "[STT] Resending buffered audio:" << m_audioBuffer.m_buffer.size() << "samples";
        
        QByteArray data(
            reinterpret_cast<const char *>(m_audioBuffer.m_buffer.data()),
            m_audioBuffer.m_buffer.size() * sizeof(int16_t)
        );
        m_ws->sendBinary(data);
        m_audioBuffer.m_flushed.store(true);
    }
}

void StreamingSTT::endUtterance()
{
    // ... existing code ...
    m_audioBuffer.clear();  // Clear buffer after utterance completes
}
```

**Justification:**
- Network transient (5-10s down) = lost audio at utterance start
- Client-side buffer allows resend on reconnect
- Max 30s buffer = ~1 MB RAM (acceptable)
- Automatic trim if buffer exceeds 30s

**Impact:** Améliore résilience réseau, meilleure qualité transcription lors réseau instable  
**Effort:** 45 minutes  
**Risque:** Medium (buffer management, requires testing)

---

## 🟡 CORRECTIF P3.2: AudioPreprocessor state reset

**Fichier:** `app/audio/AudioPreprocessor.h`

```cpp
// AVANT:
class AudioPreprocessor {
    // State persists between utterances
    float m_x1 = 0, m_x2 = 0, m_y1 = 0, m_y2 = 0;  // Biquad state
    float m_agcGain = 1.0f;
    bool m_gateOpen = false;
    
    void process(const int16_t *in, int count);
    // NO reset() method
};

// APRÈS:
class AudioPreprocessor {
    // ...same state...
    
    void reset() {  // ← ADD
        m_x1 = m_x2 = m_y1 = m_y2 = 0.0f;
        m_agcGain = 1.0f;
        m_gateOpen = false;
    }
};
```

**Fichier:** `app/audio/VoicePipeline.cpp`

```cpp
// AVANT:
void VoicePipeline::onListeningStart()
{
    m_isListening = true;
    m_circularBuffer.clear();  // ✅ Clear buffer
    // ❌ But don't reset preprocessor state
    
    startSpeechDetection();
}

// APRÈS:
void VoicePipeline::onListeningStart()
{
    m_isListening = true;
    m_circularBuffer.clear();
    m_preprocessor.reset();  // ✅ Reset DSP state
    
    startSpeechDetection();
}
```

**Justification:**
- AGC state (m_agcGain) persists from previous utterance
- Consecutive loud utterances → gain already high → clipping risk
- Reset ensures clean state for each utterance

**Impact:** Élimine clipping occasionnel sur utterances consécutives  
**Effort:** 5 minutes  
**Risque:** Very low (simple reset)

---

## 🟡 CORRECTIF P3.3: Drain TTS queue on stop

**Fichier:** `app/audio/TTSManager.h`

```cpp
// AVANT:
class TTSManager : public QObject {
public slots:
    void speak(const QString &text, ...);
    void cancelCurrent();
    // NO stopSpeaking() or queue clear
};

// APRÈS:
class TTSManager : public QObject {
public slots:
    void speak(const QString &text, ...);
    void cancelCurrent();
    void stopSpeaking();  // ← ADD: cancel + drain queue
};
```

**Fichier:** `app/audio/TTSManager.cpp`

```cpp
// BEFORE:
void TTSManager::cancelCurrent()
{
    m_cancelled.store(true);
    // ❌ But queued requests still pending
}

// AFTER:
void TTSManager::stopSpeaking()
{
    m_cancelled.store(true);
    
    // Drain pending requests
    while (!m_speechQueue.empty()) {
        m_speechQueue.dequeue();
    }
    
    qDebug() << "[TTS] Drained queue, stopped speaking";
}

// Alternatively: modify cancelCurrent() to also drain
void TTSManager::cancelCurrent()
{
    m_cancelled.store(true);
    m_speechQueue.clear();  // ← Add this line
    emit _doCancelWorker();
}
```

**Fichier:** `app/audio/VoicePipeline.cpp`

```cpp
// Update stopListening() to call TTSManager::stopSpeaking()

void VoicePipeline::stopListening()
{
    m_isListening = false;
    m_circularBuffer.clear();
    
    // Cancel current TTS AND drain queue
    m_ttsManager->stopSpeaking();  // ← Use new method instead of cancelCurrent()
    
    stopSpeechDetection();
}
```

**Justification:**
- User presses "stop" → multiple TTS requests may be queued
- Without drain → audio continues playing after stop
- Poor UX: user expects immediate silence

**Impact:** Améliore responsivité "stop" button, meilleure UX  
**Effort:** 10 minutes  
**Risque:** Very low (simple queue drain)

---

## 📊 SUMMARY DE CORRECTIFS

| ID | Problème | Fichiers | Effort | Risque | Status |
|----|----------|----------|--------|--------|--------|
| P1.1 | AudioPreprocessor race | VoicePipeline.h/cpp | 5min | ✅ VL | Critical |
| P1.2 | STT buffer uncapped | stt_server.py | 10min | ✅ VL | High |
| P1.3 | TTS timeout | TTSBackendXTTS.h/cpp | 15min | ✅ VL | High |
| P2.1 | PCMRingBuffer atomics | TTSManager.h/cpp | 20min | ✅ VL | Medium |
| P2.3 | STT resend buffer | VoicePipeline.h/cpp | 45min | ⚠️ M | Medium |
| P3.2 | Preprocessor reset | AudioPreprocessor.h/cpp | 5min | ✅ VL | Minor |
| P3.3 | TTS queue drain | TTSManager.h/cpp | 10min | ✅ VL | Minor |

**Effort total:** ~2-3 heures  
**Recommandation:** Faire P1.x immédiatement, P2.1/P2.3 la semaine suivante, P3.x en prochaine release

---

## 🚀 PLAN D'INTÉGRATION

### Sprint 1 (cette semaine) — Critical fixes
```bash
# 1. Cherry-pick P1.1, P1.2, P1.3
git checkout -b audio-critical-fixes

# 2. Appliquer les patches (voir sections ci-dessus)
# 3. Rebuild C++
cmake --build build --config Release --target RaspberryAssistant

# 4. Test Python STT
pytest tests/python/test_stt_server.py -v

# 5. Test audio E2E
# - Parler: "Hello" → micro capture
# - Vérifier: no distortion, clear transcription
# - Parler rapide 2x: Vérifier pas de clipping

# 6. Merge to main
```

### Sprint 2 (semaine suivante) — Major fixes
```bash
git checkout -b audio-major-fixes

# P2.1: Atomiciser buffer (validation que code fonctionne d'abord)
# P2.3: Implémenter resend buffer

# Test intensif réseau instable:
# - Kill tts_server, vérifier reconnect + resend
# - Network latency emulation (tc qdisc)
```

### Sprint 3 (release future) — Minor improvements
```bash
# P3.1: Telemetry latence
# P3.3: Queue drain
```

---

**Fin du document de correctifs**
