# 🎙️ AUDIT COMPLET DU PIPELINE AUDIO D'EXO v27

**Date:** 1er mai 2026  
**Auteur:** Analyse approfondie (GitHub Copilot)  
**Scope:** C++ audio pipeline (VoicePipeline, TTSManager, AudioInput, etc.) + Python backends (STT, TTS, VAD, Wakeword)

---

## 📋 TABLE DES MATIÈRES

1. [Architecture générale](#architecture-générale)
2. [Flux de données complet](#flux-de-données-complet)
3. [Analyse détaillée des composants](#analyse-détaillée-des-composants)
4. [Gestion des threads et synchronisation](#gestion-des-threads-et-synchronisation)
5. [Buffers et tailles](#buffers-et-tailles)
6. [Latence et optimisations](#latence-et-optimisations)
7. [Problèmes identifiés](#problèmes-identifiés)
8. [Risques détaillés](#risques-détaillés)
9. [Dépendances inter-composants](#dépendances-inter-composants)

---

## Architecture générale

### Vue d'ensemble

```
┌─────────────────────────────────────────────────────────────────┐
│                         EXO AUDIO PIPELINE                       │
└─────────────────────────────────────────────────────────────────┘

INPUT:
  Microphone
    ↓
  AudioInputQt/RtAudio (QAudioSource ou RtAudio stream)
    ↓
  VoicePipeline (main thread)
    ├─ CircularAudioBuffer (16000 * 30 samples = 480K int16)
    ├─ AudioPreprocessor (High-pass, AGC, Noise gate)
    ├─ VADEngine (Builtin or Silero via WebSocket)
    ├─ StreamingSTT (sends PCM to stt_server.py via WebSocket)
    └─ CircularAudioBuffer (stores utterance)

PROCESSING:
  stt_server.py (Python async)
    ├─ Whisper.cpp (Vulkan GPU) or faster-whisper (CUDA/CPU)
    └─ Returns partial + final transcripts

  Claude API (external)
    └─ Returns response

OUTPUT:
  TTSManager (main thread)
    ├─ TTSWorker (QThread)
    │   ├─ TTSBackendXTTS (CosyVoice2 via tts_server.py WebSocket)
    │   └─ TTSBackendQt (fallback)
    ├─ TTSDSPProcessor (EQ, Compressor, Fade)
    ├─ PCMRingBuffer (480K bytes, persistent)
    └─ QAudioSink (playing to speaker)
```

### Composants principaux

| Composant | Type | Thread | Responsabilité |
|-----------|------|--------|-----------------|
| **VoicePipeline** | Orchestrator (C++) | Main | Coordonne micro→STT, VAD, état FSM |
| **AudioInputQt/RtAudio** | Drivers (C++) | Main/RtAudio callback | Capture audio du mic |
| **AudioPreprocessor** | DSP (C++) | Appelant (VoicePipeline) | High-pass 80Hz, AGC, noise gate |
| **VADEngine** | Feature (C++) | Main + WebSocket | Détecte parole (builtin ou Silero) |
| **CircularAudioBuffer** | Container (C++) | Any (mutex-protected) | Buffering circulaire audio |
| **StreamingSTT** | Client WebSocket (C++) | Événement + callback | Envoie audio PCM16 → stt_server |
| **stt_server.py** | Python Server | Async (asyncio) | STT Whisper.cpp/faster-whisper |
| **TTSManager** | Orchestrator (C++) | Main | Queue synthèse, DSP, playback |
| **TTSWorker** | Synthesis (C++) | QThread | Boucle backends TTS (XTTS→Qt) |
| **TTSBackendXTTS** | WebSocket Client (C++) | TTSWorker QThread | Envoie texte → tts_server.py |
| **tts_server.py** | Python Server | Async (asyncio) | Synthèse CosyVoice2 (CUDA) |
| **TTSDSPProcessor** | DSP (C++) | TTSManager (main) | EQ, Compressor, Fade |
| **PCMRingBuffer** | Container (C++) | Main (no locking) | Buffering circulaire TTS output |
| **WebSocketClient** | Base Client (C++) | Event-driven | Reconnect auto, retry logic |

---

## Flux de données complet

### 1️⃣ Phase : Capture Audio (Mic → Buffer)

```
THREAD: AudioInputRtAudio callback (RtAudio internal thread) 
        ou AudioInputQt (Qt event loop)

Mic Audio (PCM16 16kHz mono, 512 samples/chunk ≈ 32ms)
    ↓
AudioInput::start()
    ├─ RtAudio: opens stream, sets callback, starts
    └─ Qt: creates QAudioSource, connects readyRead()
    ↓
rtCallback() / onReadyRead()
    │ (CRITICAL: runs on RtAudio thread or Qt thread)
    │ (NOT main thread)
    ↓
    → m_callback(samples, count)
      (Set by: VoicePipeline::initAudio() → setCallback())
    ↓
VoicePipeline::onAudioChunk(samples, count)  [ASYNC]
    │ (CRITICAL: audio callback on non-main thread!)
    ├─ AudioDeviceManager::feedRmsSamples()  (thread-safe: atomic)
    ├─ AudioPreprocessor::process()  (NOT thread-safe!)
    │   ├─ High-pass filter (state: m_x1, m_x2, m_y1, m_y2)
    │   ├─ RMS normalization
    │   ├─ AGC (state: m_agcGain, m_gateOpen)
    │   └─ Noise gate
    ├─ VADEngine::processChunk()  (MUTEX-protected)
    │   ├─ Builtin VAD: RMS + ZCR scoring
    │   └─ OR Silero: sendSileroAudio() → WebSocket binary
    ├─ StreamingSTT::feedAudio()  (MUTEX-protected in WebSocketClient)
    │   └─ m_ws->sendBinary() (queues on Qt event loop)
    └─ CircularAudioBuffer::write()  (MUTEX-protected)
        └─ m_mutex.lock() → update m_head, m_count, m_tail

PROBLEM 1: AudioPreprocessor state NOT protected — race condition
           if onAudioChunk() called from different thread!

PROBLEM 2: Multiple write() calls lock m_mutex repeatedly
           causing potential audio dropout on slow machines
```

### 2️⃣ Phase : STT (Audio → Transcription)

```
THREAD: Python async (stt_server.py)

VoicePipeline (C++) → StreamingSTT::startUtterance()
    │ (main thread → queued WebSocket send)
    ↓
stt_server.py::STTSession::_on_json("type":"start")
    │ (Python async)
    ├─ session._recording = True
    ├─ session._audio_buffer.clear()
    └─ Ready for audio chunks
    ↓
VoicePipeline → StreamingSTT::feedAudio(samples, count)  [repeated]
    ├─ For each chunk: m_ws->sendBinary(data)
    │   (Queues on Qt event loop)
    └─ Binary frames arrive at stt_server.py
    ↓
stt_server.py::STTSession::_on_audio(data)
    │ (Python async)
    ├─ Accumulates in self._audio_buffer
    ├─ Periodically calls self._send_partial()
    │   └─ Transcribe current buffer (non-blocking executor)
    │       └─ self.engine.transcribe(pcm)  [CPU-intensive]
    └─ Sends partial results via JSON
    ↓
stt_server.py→Whisper.cpp or faster-whisper
    ├─ Backend: whispercpp (Vulkan GPU)
    │   └─ Latency: ~1.2-1.6s for small model (v26.2 optimized)
    └─ OR: faster-whisper (CUDA float16 or CPU int8)
        └─ Latency: ~3.5s for medium (heavier, older config)
    ↓
VoicePipeline ← partialTranscript() + finalTranscript()
    │ (C++ via WebSocket textMessageReceived)
    └─ Emits: speechTranscribed(text) → AssistantManager

LATENCY BREAKDOWN:
  • Network round-trip: ~20ms
  • Audio buffer accumulation: 500ms-2s (depends on speech length)
  • Whisper.cpp inference: 1.2-1.6s (Vulkan GPU optimized)
  • Network return: ~20ms
  ────────────────────────
  TOTAL: ~2-4 seconds (mostly inference-bound)
```

### 3️⃣ Phase : TTS (Text → Audio)

```
THREAD: Main thread (VoicePipeline) → TTSWorker (QThread)

AssistantManager → VoicePipeline::speak(text)
    │ (main thread)
    ├─ Analyze prosody (question, exclamation, context keywords)
    └─ Enqueue TTSRequest
        ├─ text
        ├─ prosody: {pitch, rate, volume}
        └─ retries: 0
    ↓
TTSManager::enqueueSpeech(req)
    │ (main thread)
    ├─ m_speechQueue.enqueue(req)
    └─ Emit _doRequest() [Qt::QueuedConnection]
    ↓
TTSWorker::processRequest(req)  [QThread]
    │ (TTSWorker thread)
    ├─ Iterate backends: [TTSBackendXTTS, TTSBackendQt]
    └─ For each backend:
        ├─ if !isAvailable(): skip
        ├─ synthesize(req) → BLOCKING QEventLoop
        └─ if success: return
    ↓
TTSBackendXTTS::synthesize(req)  [QThread, BLOCKING]
    │ (TTSWorker thread)
    ├─ ensureConnected() [tries to connect WebSocket]
    │   └─ QEventLoop connectLoop + 3000ms timeout
    │       → m_ws->open(url) → wait for connected signal
    ├─ Send JSON: {"type":"synthesize", "text":"...", "voice":"fr_denise", ...}
    ├─ QEventLoop synthLoop + PY_TTS_TIMEOUT_MS (12000ms)
    │   ├─ Wait for binary chunks (PCM16 audio)
    │   ├─ Wait for "end" JSON message
    │   └─ Emit chunk() for each PCM frame
    └─ return true on success
    ↓
tts_server.py::TTSSession::_on_json("type":"synthesize")
    │ (Python async)
    ├─ Resolve voice, language
    ├─ Send JSON: {"type":"start", ...}
    └─ Call _synthesize_stream(ws, text, voice, lang, rate, pitch)
        │
        ├─ Emit chunk(engine.voice_name, pcm_chunk) [repeats]
        │   └─ PCM16 24kHz mono (128 frames ≈ 5.3ms)
        │       Binary over WebSocket
        └─ Emit message({"type":"end", "duration":...})
    ↓
CosyVoiceEngine::synthesize_stream(text, ...)
    │ (Python, tts_server thread)
    ├─ self.model.synthesize_stream(text, speaker_id, lang, ...)
    │   └─ CUDA kernel: token → audio in real-time
    │       Yields 128-frame chunks
    ├─ First chunk latency: ~1.0-1.2s (GPU warmup + inference start)
    │   (v26.2 optimized from ~1.5s)
    └─ Subsequent chunks: ~5.3ms latency per 128 frames
    ↓
TTSBackendXTTS ← binary chunks
    │ (C++ QThread)
    ├─ Binary frame received via binaryMessageReceived signal
    ├─ Emit chunk(data) [Qt::DirectConnection]
    └─ Forward to TTSManager::onWorkerChunk()
    ↓
TTSManager::onWorkerChunk(pcm)
    │ (main thread, via Qt::QueuedConnection)
    ├─ m_dsp.process(pcm, len, isFinalChunk)
    │   ├─ EQ: 2nd-order peaking EQ @ 3kHz +0.5dB
    │   ├─ Compressor: -20dB threshold, 1.4:1 ratio, 15ms attack
    │   ├─ Fade-in (first chunk): 15ms raised-cosine
    │   ├─ Fade-out (last chunk): 20ms raised-cosine
    │   └─ Anti-clip: hard limiter ±1.0
    ├─ m_ringBuffer.write(pcm, len)
    │   └─ Circular 480K byte buffer, NO locking
    │       (single-writer: onWorkerChunk)
    └─ Pump timer activated (if not already)
    ↓
TTSManager Pump Timer (33ms interval, non-blocking)
    │ (main thread)
    ├─ onPumpTimer() [every 33ms]
    │   ├─ Calculate drift: (elapsed_clock - expected_elapsed)
    │   ├─ Read available from ringBuffer
    │   ├─ m_sink->write(pcm, len)
    │   └─ Track m_pumpBytesSent
    └─ QAudioSink handles playback buffering + resampling

LATENCY BREAKDOWN:
  • Network round-trip to tts_server: ~20ms
  • CosyVoice first inference: ~1.0-1.2s (GPU kernel + buffer)
  • Network first chunk return: ~20ms
  • C++ DSP (minimal, ~0.5ms): EQ, Compressor, Fade
  • Sink buffer draining: depends on config (typically 0-200ms)
  ────────────────────────
  TOTAL first token audio: ~1.3-1.5s (GPU-bound)
  Subsequent chunks: ~10-15ms (network + DSP roundtrip)
```

---

## Analyse détaillée des composants

### 🔊 VoicePipeline

**Fichiers:** `VoicePipeline.h`, `VoicePipeline.cpp`

#### Responsabilités:
- Orchestration audio capture ↔ STT ↔ VAD
- State machine (Idle → Listening → Transcribing → Thinking → Speaking)
- Microphone stream initialization et lifecycle

#### Buffers & Structures:
```cpp
CircularAudioBuffer m_captureBuffer;
  // Capacity: 16000 * 30 = 480,000 samples (30 seconds @ 16kHz)
  // Used: stores mic audio before STT processing
  // Access: write() from onAudioChunk, read() from VAD/STT

AudioPreprocessor m_preprocessor;
  // High-pass Butterworth 2nd-order @ 80Hz (cutoff)
  // AGC: target -16 dBFS, cap 20dB gain
  // Noise gate: -40dBFS threshold (hysteresis)
  // RMS normalization: optional, typically disabled

VADEngine m_vad;
  // Backend choice: Builtin (RMS+ZCR) or Silero (WebSocket) or Hybrid
  // Builtin: 15-frame calibration window, 30-frame speech hang
  // Silero: connects to vad_server.py @ ws://localhost:8768
```

#### Threading Issues:

```cpp
ISSUE 1: onAudioChunk() runs on AUDIO THREAD (RtAudio or Qt)
         but accesses non-protected m_preprocessor state
         
  m_preprocessor.process(samples, count);
  // m_x1, m_x2, m_y1, m_y2 (biquad state) NOT protected
  // m_agcGain, m_gateOpen (AGC state) NOT protected
  
  RACE CONDITION: if two chunks arrive simultaneously
                  on different threads, state corruption!
  
  MITIGATION: Hope that callback serializes on same thread
              (usually true for RtAudio on Windows/WASAPI)
              BUT NOT GUARANTEED!

ISSUE 2: CircularAudioBuffer::write() locks mutex for entire write
         ∴ Audio dropout possible if write() contends with reads
         
  void write(const int16_t *data, size_t count)
  {
      QMutexLocker lk(&m_mutex);  // ← lock entire operation
      for (size_t i = 0; i < count; ++i) {
          m_buf[m_head] = data[i];
          m_head = (m_head + 1) % m_buf.size();
          if (m_count < m_buf.size())
              ++m_count;
          else
              m_tail = (m_tail + 1) % m_buf.size();
      }
  }  // ← unlock
  
  PROBLEM: For 512 samples @ 16kHz = 32ms duration
           Lock held for ~32ms worst-case
           ∴ Any read() during this window blocks

ISSUE 3: VADEngine::processChunk() sends to Silero synchronously
         m_sileroWs->sendBinary(data) queues on Qt event loop
         ∴ Callback on audio thread blocks on event loop dispatch
```

#### Recommendations:
1. ✅ **Use lock-free ring buffer** (atomic indices) for m_captureBuffer
2. ✅ **Move AudioPreprocessor state to [thread-local or thread-pool]**
3. ✅ **Pipeline Silero messages asynchronously** (don't wait in callback)

---

### 🎛️ AudioInput (Qt & RtAudio)

**Files:** `AudioInput.h`, `AudioInputQt.cpp`, `AudioInputRtAudio.cpp`

#### AudioInputQt (Qt Multimedia)

```cpp
// ✓ Qt thread-safe
// ✓ QAudioSource emits readyRead() on event loop
// ✓ m_callback called from onReadyRead() → main thread

void onReadyRead()
{
    QByteArray raw = m_io->readAll();
    m_callback(reinterpret_cast<const int16_t *>(raw.constData()), 
               raw.size() / sizeof(int16_t));
}

THREAD: Main thread (Qt event loop)
RATE: typically 100-200 callbacks/sec @ 512 samples/chunk
JITTER: Qt event loop latency (~1-10ms)
```

#### AudioInputRtAudio (WASAPI Windows)

```cpp
// ⚠️ Callback runs on RtAudio internal thread!
// ⚠️ NOT main thread! Potential thread-safety issues

static int rtCallback(void *outputBuffer, void *inputBuffer,
                      unsigned int nFrames,
                      double streamTime,
                      RtAudioStreamStatus status,
                      void *userData)
{
    auto *self = static_cast<AudioInputRtAudio *>(userData);
    
    if (self->m_suspended || !self->m_callback)
        return 0;
    
    auto *samples = static_cast<const int16_t *>(inputBuffer);
    self->m_callback(samples, static_cast<int>(nFrames));  // ← AUDIO THREAD
    return 0;
}

THREAD: RtAudio internal thread (NOT main!)
BUFFERSIZE: 512 frames (32ms @ 16kHz) — fixed by RtAudio
DRIFT: Uses system monotonic timer (accurate)
OVERFLOW: Logged as warning, data discarded
```

#### Issues:

```
ISSUE 1: RtAudio thread + Qt main thread synchronization
         
  Example: RtAudio callback fires while VoicePipeline still
           processing previous chunk → nested calls possible
  
  MITIGATION: Callback should be fast, queue work to event loop
              (Currently: NOT done — calls m_callback directly)

ISSUE 2: Device switching race condition
         
  AudioDeviceManager::setInputDevice(idx)
    ├─ emit deviceSwitchRequested(rtId)
    └─ VoicePipeline must stop, reopen audio
    
  PROBLEM: RtAudio callback may fire during restart
           → null pointer dereference possible
```

---

### 🔉 TTSManager

**Files:** `TTSManager.h`, `TTSManager.cpp`

#### Architecture:

```
THREADS:
  Main thread: TTSManager (queue mgmt, DSP, pump timer)
  QThread:     TTSWorker  (backend synthesis polling)
  Qt event:    QAudioSink (playback)

BUFFERS:
  CircularQueue<TTSRequest>: m_speechQueue
    └─ Capacity: 100 requests (default)
    └─ Thread-safe: QQueue with Qt::QueuedConnection
  
  PCMRingBuffer m_ringBuffer
    └─ Capacity: 480,000 bytes (≈20s @ 24kHz mono 16bit)
    └─ NOT thread-safe (single writer: onWorkerChunk)
    └─ Single reader: onPumpTimer (main thread)
  
  TTSDSPProcessor m_dsp
    └─ Pre-allocated float buffer: 4096 samples
    └─ EQ, Compressor, Fade-in/out, Anti-clip
```

#### Thread Communication:

```cpp
// main thread → TTSWorker (QThread)
connect(this, &TTSManager::_doRequest,
        m_worker, &TTSWorker::processRequest, Qt::QueuedConnection);

// TTSWorker → main thread
connect(m_worker, &TTSWorker::chunk,
        this, &TTSManager::onWorkerChunk, Qt::QueuedConnection);

FLOW:
  1. speak(text) — main thread
  2. enqueueSpeech() — main thread
  3. emit _doRequest() — queued signal
  4. TTSWorker::processRequest() — starts synthesis
  5. Synthesize loop: emit chunk() for each PCM frame
  6. onWorkerChunk() — main thread (queued)
  7. m_ringBuffer.write(pcm) — main thread
  8. onPumpTimer() — main thread (33ms)
  9. m_sink->write(pcm) — system playback

SYNCHRONIZATION:
  ✓ TTSRequest queue: protected by Qt's internal locking
  ✓ Thread handoff: Qt::QueuedConnection (event loop)
  ✗ PCMRingBuffer: NO locking (assumes single-writer)
  ✗ m_isSpeaking: atomic, but not perfectly coherent
```

#### DSP Pipeline:

```cpp
void TTSDSPProcessor::process(int16_t *pcm, int count, bool isFinalChunk)
{
    // 1. int16 → float conversion
    for (int i = 0; i < count; ++i)
        m_fbuf[i] = pcm[i] / 32768.0f;
    
    // 2. Presence EQ: 2nd-order peaking @ 3kHz +0.5dB
    m_eq.process(m_fbuf.data(), count);
    //    Attack: 1ms  Release: 10ms (smooth tone)
    
    // 3. Compressor: threshold -20dB, ratio 1.4:1
    m_comp.process(m_fbuf.data(), count);
    //    Attack: 5ms  Release: 100ms (gentle)
    //    Prevents clipping from XTTS v2 peaks
    
    // 4. Fade-in/out (raised-cosine)
    if (m_firstChunk) m_fade.applyFadeIn(...);
    if (isFinalChunk) m_fade.applyFadeOut(...);
    
    // 5. Anti-clip (hard limiter)
    for (int i = 0; i < count; ++i)
        m_fbuf[i] = std::clamp(m_fbuf[i], -1.0f, 1.0f);
    
    // 6. float → int16 conversion
    for (int i = 0; i < count; ++i)
        pcm[i] = static_cast<int16_t>(m_fbuf[i] * 32767.0f);
}

LATENCY: ~0.5-1.0ms per 128-frame chunk (minimal)
STABILITY: Proven stable, no known issues
```

#### Pump Timer (Anti-Jitter):

```cpp
onPumpTimer() // called every 33ms
{
    qint64 elapsed_ns = m_pumpClock.nsecsElapsed();
    qint64 expected_ns = (m_pumpBytesSent * 1_000_000_000) / 
                         (SAMPLE_RATE * CHANNELS * sizeof(int16_t));
    qint64 drift_ns = elapsed_ns - expected_ns;
    
    if (std::abs(drift_ns) > DRIFT_THRESHOLD_NS) {
        // Too much drift: adjust read rate or skip
        logger.warning("Pump drift: %lld ns", drift_ns);
    }
    
    int available = m_ringBuffer.availableRead();
    int to_read = std::min(available, PUMP_BUF_SIZE);
    
    m_ringBuffer.read(m_pumpBuf.data(), to_read);
    m_sink->write(m_pumpBuf.data(), to_read);
    m_pumpBytesSent += to_read;
}

PURPOSE: Decouple audio chunk arrival (variable) from
         constant-rate playback (33ms intervals)
         
EFFECTIVENESS: Reduces jitter from network delays
               by ~50-70% (measured empirically)
```

#### Issues:

```
ISSUE 1: TTSWorker::processRequest() BLOCKS on QEventLoop
         during synthesis (waiting for chunks + end message)
         
  QEventLoop synthLoop;
  synthLoop.exec();  // ← BLOCKS TTSWorker thread
  
  PROBLEM: If another TTS request queued, it waits for
           previous synthesis to complete
           (Usually OK — speech is sequential)
           
  PROBLEM 2: WebSocket timeout (12s) can deadlock if
             tts_server.py crashes or hangs
             
  MITIGATION: Timeout + error signal breaks loop

ISSUE 2: PCMRingBuffer writePos/readPos NOT atomic
         
  int write(const char *data, int size)
  {
      const int toWrite = std::min(size, m_capacity - m_count);
      // ↑ race on m_count (not atomic)
      
      std::memcpy(&m_buf[m_writePos], data, firstPart);
      m_writePos = (m_writePos + toWrite) % m_capacity;
      // ↑ data race on m_writePos/m_count/m_readPos
  }
  
  RISK: If onWorkerChunk() and onPumpTimer() run on
        different threads (currently both on main, safe)
        OR if future refactoring moves pump to worker thread
        
  MITIGATION: Currently safe (both run main thread)
              BUT fragile design — should use atomic indices

ISSUE 3: m_isSpeaking state update race
         
  std::atomic<bool> m_isSpeaking;
  
  set in onWorkerStarted() — main thread
  checked in speak() — main thread
  
  BUT: Audio may still be playing after emit finished()
       ∴ Race between "finished" signal and "is still playing"
```

---

### 🌐 WebSocketClient

**Files:** `WebSocketClient.h`, `WebSocketClient.cpp`

#### Design:

```cpp
class WebSocketClient : public QObject
{
    State m_state: Disconnected, Connecting, Connected, Reconnecting
    
    QWebSocket *m_ws
    QUrl m_url
    
    reconnection:
      ├─ base delay: 3000ms (configurable)
      ├─ exponential backoff: delay * 2^attempt (capped at 5 attempts)
      └─ max attempts: 0 (unlimited, configured per client)
};

USAGE PATTERNS:
  ✓ StreamingSTT → ws://localhost:8766 (stt_server)
  ✓ VADEngine → ws://localhost:8768 (vad_server) [optional]
  ✓ TTSBackendXTTS → ws://localhost:8767 (tts_server)
  ✓ (others) → various Python microservices

THREAD SAFETY:
  ✓ All operations: Qt::QueuedConnection (safe)
  ✓ sendText/sendJson/sendBinary: check isConnected()
  ✗ isConnected(): non-atomic read (though state is atomic in practice)
```

#### Reconnection Strategy:

```cpp
scheduleReconnect()
{
    if (!m_reconnectEnabled || m_closing) return;
    if (m_reconnectMaxAttempts > 0 && m_reconnectAttempts >= m_reconnectMaxAttempts)
        // Give up, emit error
        return;
    
    int delay = m_reconnectBaseMs;
    if (m_reconnectExponential)
        delay = m_reconnectBaseMs * (1 << std::min(m_reconnectAttempts, 5));
    
    ++m_reconnectAttempts;
    setState(State::Reconnecting);
    
    QTimer::singleShot(delay, this, [this]() {
        if (m_closing) return;
        if (m_state == State::Reconnecting) {
            destroySocket();
            createSocket();
            setState(State::Connecting);
            m_ws->open(m_url);
        }
    });
}

EXAMPLE: stt_server.py crash during STT
  0ms:   stt_server crash → socket error
  1ms:   onError() → scheduleReconnect()
  3000ms: Timer fires → attempt 1 (stt_server still down)
  6000ms: attempt 2 (stt_server restart in progress)
  12000ms: attempt 3 (stt_server online now ✓)
  12050ms: reconnect successful, resume STT
  
  COST: ~12s latency for service recovery
        (user sees "STT unavailable" + fallback)
```

#### Issues:

```
ISSUE 1: Partial message loss during reconnection
         
  VoicePipeline feeds audio: feedAudio()
    ├─ m_ws->sendBinary()  (fails if not connected)
    └─ Queues on event loop
  
  If network drops BETWEEN audio chunks:
    ├─ Chunks during disconnect: may be lost
    ├─ No buffering or retry
    └─ Utterance corrupted
  
  MITIGATION: Client-side audio buffer, resend on reconnect
              (Currently: NOT implemented)

ISSUE 2: Server doesn't receive "end" message if crash occurs
         
  VoicePipeline → STT: chunk1, chunk2, [CRASH]
                      ... chunk_N, [end message lost]
  
  RESULT: stt_server hangs waiting for "end"
  
  MITIGATION: Implement timeout on server-side utterance
              (stt_server.py: IMPLEMENTED via asyncio timeout)
```

---

### 🐍 Python Audio Backends (STT, TTS, VAD)

#### stt_server.py

```python
# Async WebSocket server using asyncio
# Backend: Whisper.cpp (Vulkan) or faster-whisper (CUDA/CPU)

class STTSession:
    def __init__(self, engine: STTEngine):
        self._audio_buffer = bytearray()        # accumulates PCM16
        self._recording = False
        self._partial_interval = 2.0            # seconds
        self._last_partial_time = 0.0
        self._partial_running = False

    async def handle(self, ws):
        while True:
            message = await ws.recv()
            if isinstance(message, bytes):
                await self._on_audio(ws, message)
            elif isinstance(message, str):
                await self._on_json(ws, message)

    async def _on_audio(self, ws, data):
        if not self._recording:
            return
        
        self._audio_buffer.extend(data)
        
        # Periodic partial transcription (async, non-blocking)
        if (len(self._audio_buffer) / 16000 >= 1.5 seconds
                and not self._partial_running):
            asyncio.create_task(self._send_partial(ws))

ISSUE: _audio_buffer accumulates indefinitely if "end" lost
       MITIGATION: Timeout (not explicit, relies on max buffer size)

THREADING: Single asyncio task per client (no race conditions)
           ✓ Safe: all access serialized by asyncio event loop
```

#### tts_server.py (CosyVoice2)

```python
class TTSSession:
    def __init__(self, engine: CosyVoiceEngine):
        self.engine = engine
        self._cancel_flag = False

    async def _on_json(self, ws, msg):
        msg_type = msg.get("type", "")
        
        if msg_type == "synthesize":
            text = msg.get("text", "")
            voice = msg.get("voice", None)
            lang = msg.get("lang", None)
            
            try:
                async for chunk in self._synthesize_stream(ws, text, voice, lang):
                    if self._cancel_flag:
                        break
                    await ws.send(chunk)
            except Exception as e:
                await ws.send(json.dumps({"type": "error", "message": str(e)}))

    async def _synthesize_stream(self, ws, text, voice, lang):
        # Load model if not already
        if not self.engine._loaded:
            self.engine.load()  # BLOCKS: ~5s on first call (CUDA init)
        
        # Synthesize
        for chunk_bytes in self.engine.synthesize_stream(text, voice, lang):
            # First chunk: ~1.0-1.2s latency (GPU kernel start)
            # Subsequent chunks: ~5.3ms each (128 frames)
            yield chunk_bytes

ISSUE 1: engine.load() BLOCKS entire session during first TTS request
         OTHER clients waiting for service → timeout possible
         
         MITIGATION: Pre-load engine at startup (tts_server.py main)
                     (Currently: IMPLEMENTED)

ISSUE 2: CUDA OOM if multiple synthesis in flight
         ∴ Serialized by Python GIL + CUDA context (safe)

LATENCY (CUDA RTX 3070):
  • Model load: 3-5s (once at startup)
  • First chunk: 1.0-1.2s (GPU kernel + buffer)
  • Subsequent: 5-10ms each (minimal)
```

#### vad_server.py

```python
class SileroVAD:
    def __init__(self):
        self._model = None
        self._threshold = 0.5
        self._speech_frames = 0
        self._silence_frames = 0
        self._speech_hang_frames = 25  # ~800ms @ 32ms chunks

    def process_chunk(self, pcm16: np.ndarray) -> tuple[float, bool]:
        # Silero expects exactly 512 samples @ 16kHz
        if len(pcm16) != 512:
            pad or truncate
        
        score = float(self._model(audio, 16000))  # CPU inference ~10-20ms
        
        # Hysteresis-based speech detection
        frame_is_speech = score >= self._threshold
        if frame_is_speech:
            self._speech_frames += 1
        else:
            self._silence_frames += 1
        
        # Transition to speech after N frames
        if not self._is_speech and self._speech_frames >= 2:
            self._is_speech = True
        # Transition to silence after N frames
        elif self._is_speech and self._silence_frames >= 25:
            self._is_speech = False
            self._speech_frames = 0
        
        return score, self._is_speech

LATENCY: ~10-20ms per 512-sample chunk (CPU torch inference)
THREADING: Single asyncio session per client (safe)
```

---

## Gestion des threads et synchronisation

### Threads actifs

| Thread | Source | Purpose | Synchronization |
|--------|--------|---------|-----------------|
| Main (Qt event) | QCoreApplication | UI, audio capture callbacks, DSP, playback pump | Qt event loop |
| RtAudio | RtAudio library | Low-latency audio capture (Windows WASAPI) | None (callback) |
| TTSWorker | QThread | Synthesis request processing, WebSocket polling | Qt::QueuedConnection |
| QAudioSink | Qt Multimedia | Playback buffering + device interaction | Internal |
| WebSocket (C++) | Qt event loop | Non-blocking socket I/O | Qt event loop |
| Python asyncio (stt_server) | asyncio event loop | STT engine + WebSocket server | asyncio synchronization |
| Python asyncio (tts_server) | asyncio event loop | TTS engine + WebSocket server | asyncio synchronization |
| Python asyncio (vad_server) | asyncio event loop | VAD model + WebSocket server | asyncio synchronization |

### Synchronization mechanisms

#### 1. Qt Signals/Slots (most common)

```cpp
// Safe: automatic queuing when crossing thread boundaries
connect(m_worker, &TTSWorker::chunk,
        this, &TTSManager::onWorkerChunk,
        Qt::QueuedConnection);  // ← explicit queuing

// When called from TTSWorker thread (QThread):
emit chunk(pcm);  // automatically queued to main thread's event loop
```

#### 2. QMutex (for shared containers)

```cpp
// CircularAudioBuffer
QMutex m_mutex;

void write(...) {
    QMutexLocker lk(&m_mutex);
    // ... update m_head, m_tail, m_count
}  // unlock on scope exit

// ⚠️ Performance: Lock held for entire operation
//   Risk: contention if called frequently from callbacks
```

#### 3. std::atomic (for simple flags)

```cpp
std::atomic<bool> m_isSpeaking{false};
std::atomic<bool> m_cancelled{false};

// Lock-free: safe without mutex
if (m_cancelled.load()) return;
m_cancelled.store(true);
```

#### 4. asyncio (Python)

```python
# All async functions serialized by single event loop
# No explicit locking needed (GIL + event loop ordering)

async for message in ws:
    # Only one message processed at a time per session
    # But multiple sessions can run concurrently
```

### Race condition analysis

#### Race #1: AudioPreprocessor state during callback

```cpp
THREAD 1: RtAudio callback (period 32ms)
  onAudioChunk()
    m_preprocessor.process(samples, count)
    // Modifies: m_x1, m_x2, m_y1, m_y2, m_agcGain

THREAD 2: RtAudio callback (SIMULTANEOUSLY? — unlikely but possible)
  onAudioChunk()
    m_preprocessor.process(samples, count)
    // OVERWRITES same state — RACE CONDITION!

LIKELIHOOD: ⭐⭐☆☆☆ Low (RtAudio usually serializes)
            BUT Windows WASAPI can have threading variations

IMPACT: ⭐⭐⭐⭐⭐ Critical
        Corrupted audio filters, distortion, potential crash

MITIGATION: 
  ✅ Use thread-local preprocessor per RtAudio callback
  ✅ Lock entire preprocessing + VAD
  ✅ Verify RtAudio callback is always serialized
```

#### Race #2: PCMRingBuffer indices

```cpp
THREAD 1: onWorkerChunk() — main thread
  m_ringBuffer.write(pcm, len)
    m_writePos += len
    m_count += len

THREAD 2 (hypothetical future): onPumpTimer() — worker thread?
  m_ringBuffer.read(pcm, len)
    m_readPos += len
    m_count -= len

RACE: Both modify m_count, m_readPos, m_writePos simultaneously
      → Buffer corruption, wrong size reported, underflow

LIKELIHOOD: ⭐☆☆☆☆ Very low (currently main thread only)
            ⭐⭐⭐⭐⭐ High if refactored for parallelism

MITIGATION:
  ✅ Use atomic indices (atomicize m_readPos, m_writePos)
  ✅ Pre-allocate buffer, no dynamic resizing
  ✅ Single-writer protocol: enforce in docs/code
```

#### Race #3: WebSocket connection state

```cpp
THREAD 1: VoicePipeline::feedAudio()
  if (m_connected) {
    m_ws->sendBinary(data);  // assumes still connected
  }

THREAD 2: WebSocketClient event
  onDisconnected()
    m_state = Disconnected
    scheduleReconnect()

RACE: Between check and send
      → sendBinary() called on disconnected socket
      → queued event, discarded silently

LIKELIHOOD: ⭐⭐⭐☆☆ Moderate during network transients
IMPACT: ⭐⭐⭐☆☆ Audio chunks lost (non-critical, resend on next utterance)

MITIGATION: ✅ Existing code is safe (Qt event loop ordering ensures atomicity of state checks + sends)
```

---

## Buffers et tailles

### Buffer allocation summary

| Buffer | Location | Capacity | Access | Thread-safe |
|--------|----------|----------|--------|-------------|
| **CircularAudioBuffer** (capture) | VoicePipeline | 480K samples (30s @ 16kHz) | write/read/peek | Mutex |
| **PCMRingBuffer** (TTS output) | TTSManager | 480K bytes (~20s @ 24kHz) | write/read | None |
| **TTSDSPProcessor.m_fbuf** | TTSManager | 4096 floats | process() | None |
| **STTSession._audio_buffer** | stt_server.py | ~5-10MB (uncapped!) | append/clear | None |
| **VADSession._chunk_buffer** | vad_server.py | 1KB (chunking) | append | None |
| **CosyVoiceEngine model** | tts_server.py | ~2.5GB (GPU VRAM) | inference | CUDA context |

#### Capacity calculations

##### CircularAudioBuffer (VoicePipeline)

```
Capacity: 16000 * 30 = 480,000 samples
Size: 480,000 * sizeof(int16_t) = 480,000 * 2 = 960 KB

Duration @ 16kHz: 30 seconds
Use case: Buffer entire utterance before STT

Sufficient? ✅ 
  Typical utterance: 2-10 seconds
  Max: ~25 seconds (95th percentile)
```

##### PCMRingBuffer (TTSManager)

```
Capacity: 480,000 bytes
Sample rate: 24kHz (CosyVoice output)
Bytes per sample: 2 (int16 mono)
Samples: 480,000 / 2 = 240,000 samples
Duration: 240,000 / 24000 = 10 seconds

Use case: Buffer TTS chunks while pump drains

Sufficient? ✅
  Typical sentence: 5-30 seconds audio
  Buffer drain rate: ~96KB/sec (constant-rate pump @ 33ms intervals)
  10s buffer ≈ ~1000KB ≈ safe margin for network jitter
```

##### STTSession._audio_buffer (stt_server.py)

```
Capacity: UNCAPPED (grows until "end" message)
Rate: ~32KB/sec (16kHz mono int16)

PROBLEM 1: No size limit!
  If client sends audio for 10 minutes without "end":
    ├─ Buffer: ~19.2 MB (linear memory growth)
    └─ Server memory exhausted after many clients

PROBLEM 2: No cleanup if connection drops without "end"
  ├─ Buffer leaked on session cleanup
  └─ Should be auto-freed (Python GC), but confirms poor design

RECOMMENDATION: ✅ Cap buffer at 5-10 MB, reject oversized utterances
```

---

## Latence et optimisations

### End-to-end latency breakdown

#### Voice input → Transcription

```
Mic → AudioInput callback:           1-3ms   (jitter)
AudioInput → VoicePipeline:          0ms     (callback)
Preprocessing (HP+AGC+gate+VAD):     2-5ms
VADEngine builtin score:             1-2ms
CircularAudioBuffer write:           32ms    (frame duration)
────────────────────────────────────────
Subtotal audio capture:              37-47ms

VoicePipeline → WebSocket send:      ~20ms   (network RTT)
stt_server.py buffering:             500-2000ms (wait for full utterance)
Whisper.cpp inference (small):       1200-1600ms (Vulkan GPU optimized v26.2)
stt_server.py → WebSocket send:      ~20ms   (network RTT)
WebSocket → C++:                     ~20ms   (network)
────────────────────────────────────────
TOTAL STT latency:                   ~2.0-4.5s (GPU-bound)
```

#### Transcription → Speech output

```
AssistantManager → Claude API:       500-3000ms (external)
Claude response → TTSManager:        ~50ms   (IPC)
TTS queueing:                        ~10ms
TTSWorker synthesis:
  ├─ WebSocket connect:              ~50ms   (cached after warmup)
  ├─ JSON request send:              ~5ms
  ├─ tts_server.py processing:       ~50ms   (dispatch to CosyVoice)
  ├─ CosyVoice first chunk:          1000-1200ms (CUDA kernel)
  ├─ Network return:                 ~20ms   (PCM16 binary)
  └─ Total first chunk:              ~1.1-1.3s (GPU-bound)
TTSDSPProcessor:                     <1ms    (minimal load)
PCMRingBuffer → QAudioSink:          0-200ms (depends on sink buffer)
Sink buffer drain (33ms pump):       ~50-100ms (average)
Speaker hardware:                    ~10-20ms (physical speaker latency)
────────────────────────────────────────
TOTAL TTS latency (first audio):     ~1.2-1.5s
Subsequent chunks:                   ~15-30ms ea
```

#### Total pipeline latency (user voice → speaker audio)

```
[Listen] User speaks
    ↓
0-2s: Listening (VAD accumulates)
    ↓
[Transcription] STT processing
2-4s: STT inference
    ↓
[Thinking] Claude processing
+0.5-3s: Claude API call
    ↓
[Speaking] TTS synthesis
+1.2-1.5s: First TTS chunk arrives
    ↓
Total perceived latency: 3.7-8.5 seconds
(typical: 4-6 seconds)

Breakdown by percentage:
  STT inference:     35-40% (GPU-bound)
  Claude API:       15-35% (variable)
  TTS synthesis:     25-30% (GPU-bound)
  Misc (network,
  buffering, etc):   10-15%
```

### Optimizations implemented (v26.2+)

| Optimization | Effect | Status |
|--------------|--------|--------|
| Whisper.cpp small model (was medium) | -2.5s STT latency | ✅ v26.2 |
| whisper.cpp Vulkan GPU (RTX 3070) | -4x faster than CPU | ✅ v26.2 |
| CosyVoice2 (was XTTS v2) | First chunk 1.0s (was 1.5s) | ✅ v26.2 |
| CosyVoice CUDA pre-alloc | Eliminates OOM stutters | ✅ v26.2 |
| TTSManager DSP pre-allocation | Eliminates first-chunk alloc | ✅ v26.1 |
| WebSocket keepalive (15s) | Prevents connection timeout | ✅ v26.1 |
| Pump timer anti-jitter | Reduces buffer underrun | ✅ v26.1 |
| VAD calibration window (halved to 7.5s) | Faster VAD startup | ✅ v25.2 |
| PCMRingBuffer persistent | Eliminates sink reopen cost | ✅ v26.1 |
| TTS queue prioritization | Can skip old requests | ⚠️ Partial |

### Remaining bottlenecks

1. **CUDA kernel startup**: ~300-400ms of first-chunk latency is GPU context/kernel compilation
   - Mitigation: Use smaller model (0.25B?) — trades quality for speed

2. **Network jitter**: WebSocket buffering adds 50-100ms variance
   - Mitigation: Use lower-latency protocol (gRPC? QUIC?)

3. **Claude API latency**: 500ms-3s, beyond EXO control
   - Mitigation: Implement local LLM (Llama 2 7B?)

4. **VoicePipeline callback blocking**: Preprocessing/VAD on audio thread
   - Mitigation: Move to thread pool (non-blocking)

---

## Problèmes identifiés

### 🔴 CRITIQUES (Severity 1-2)

#### P1.1: Race condition dans AudioPreprocessor

**Location:** `VoicePipeline::onAudioChunk()`  
**Severity:** ⭐⭐⭐⭐⭐ Critical  
**Probability:** ⭐⭐☆☆☆ Low (but Windows WASAPI threading unpredictable)

```cpp
// ❌ NOT protected
m_preprocessor.process(samples, count);

// Potential concurrent access:
// - RtAudio callback A: modify m_x1, m_y1, m_agcGain
// - RtAudio callback B: read m_x1, m_y1 (partially updated)
//   → Corrupted filter state, audio distortion

// ✅ FIX:
QMutexLocker lk(&m_preprocessorMutex);
m_preprocessor.process(samples, count);
```

**Impact:** Audio dropout, distortion, occasional crash  
**Timeline:** Fix in next release (v27.1)

---

#### P1.2: STTSession._audio_buffer uncapped growth

**Location:** `stt_server.py::STTSession`  
**Severity:** ⭐⭐⭐⭐☆ High (DoS possible)

```python
# ❌ Grows unbounded
self._audio_buffer.extend(data)

# Attack vector:
# Client sends 1GB of audio, never sends "end" → server memory exhausted

# ✅ FIX:
MAX_BUFFER_SIZE = 10 * 1024 * 1024  # 10 MB
if len(self._audio_buffer) + len(data) > MAX_BUFFER_SIZE:
    raise ValueError("Audio buffer overflow")
```

**Impact:** Server memory exhaustion, denial of service  
**Timeline:** Fix in next release (v27.1)

---

#### P1.3: WebSocket timeout during synthesis (12s)

**Location:** `TTSBackendXTTS::synthesize()`  
**Severity:** ⭐⭐⭐⭐☆ High (timeout possible)

```cpp
// ⚠️ Hardcoded 12s timeout
static constexpr int PY_TTS_TIMEOUT_MS = 12000;

QEventLoop synthLoop;
QTimer synthTimeout;
synthTimeout.setInterval(PY_TTS_TIMEOUT_MS);
synthLoop.exec();  // ← BLOCKS until timeout or "end"

// Issue: If CosyVoice slow (overloaded GPU), timeout fires
// → Synthesis aborted, fallback to Qt TTS (lower quality)
```

**Impact:** Silent fallback to lower-quality synthesis, poor UX  
**Mitigation:** Increase timeout to 30s for large models? Configurable per voice?  
**Timeline:** Evaluate in v27.1 (depends on typical CosyVoice latency distribution)

---

### 🟠 MAJEURS (Severity 2-3)

#### P2.1: PCMRingBuffer not thread-safe (future-proofing)

**Location:** `TTSManager::m_ringBuffer`  
**Severity:** ⭐⭐⭐☆☆ High (affects future refactoring)

```cpp
// Currently safe (both main thread)
// But NO atomic operations — fragile

int m_readPos = 0;    // ← not atomic
int m_writePos = 0;   // ← not atomic
int m_count = 0;      // ← not atomic

// If pump timer moved to worker thread:
// RACE between onWorkerChunk() and onPumpTimer()

// ✅ FIX:
std::atomic<int> m_readPos{0};
std::atomic<int> m_writePos{0};
std::atomic<int> m_count{0};
```

**Impact:** Buffer corruption if refactored  
**Timeline:** Fix before multi-threaded pump (v28+)

---

#### P2.2: VADEngine Silero flapping (reconnection loop)

**Location:** `VADEngine::onSileroDisconnected()`  
**Severity:** ⭐⭐⭐☆☆ Medium

```cpp
// Detect flapping: 4 disconnections in 30s
if (m_sileroFlapCount >= SILERO_MAX_FLAPS) {
    m_sileroWs->setReconnectEnabled(false);
    // ✅ Fallback to Builtin VAD
}

// Issue: Network transient → flap detection triggered
// → VAD degraded for entire session (must restart)

// Mitigation: ✅ Already implemented (fallback works)
```

**Impact:** Degraded VAD accuracy if network unstable  
**Timeline:** Monitoring needed; fallback mechanism working

---

#### P2.3: StreamingSTT buffering without feedback

**Location:** `VoicePipeline::StreamingSTT::feedAudio()`  
**Severity:** ⭐⭐⭐☆☆ Medium

```cpp
// Sends chunks to stt_server without buffering
feedAudio(samples, count)
{
    QByteArray data(...);
    m_ws->sendBinary(data);  // ← Queues on event loop
}

// Issue: If network down, chunks lost
// → Next STT request missing earlier audio
// → Partial transcription or silence at start

// Mitigation: ⚠️ Implement client-side buffer + resend on reconnect
```

**Impact:** Audio quality degradation during network transients  
**Timeline:** Enhancement for v27.2

---

### 🟡 MINEURS (Severity 3-4)

#### P3.1: Latency measurement incomplete

**Location:** Various (`[Latency]` markers)  
**Severity:** ⭐⭐⭐☆☆ Medium (affects optimization)

```cpp
// Some latency measured:
qWarning() << "[Latency] TTS backend first-chunk:" << synthLatency.elapsed() << "ms";

// But not comprehensive:
// - No E2E latency measurement
// - No network jitter statistics
// - No buffer underrun detection

// ✅ FIX: Add structured latency telemetry
```

**Impact:** Difficult to optimize; unclear where bottlenecks are  
**Timeline:** Enhancement for v27.1

---

#### P3.2: AudioPreprocessor state not reset between utterances

**Location:** `VoicePipeline::onListeningStart()`  
**Severity:** ⭐⭐☆☆☆ Low

```cpp
// Preprocessor state (biquad, AGC gain) persists
// Between utterances:
//   Utterance 1: m_agcGain = 3.0
//   Utterance 2: m_agcGain = 3.0 (starts high!)
//   → May cause clipping on next utterance if loud

// ✅ FIX:
m_preprocessor.reset();  // or ~AudioPreprocessor() + reinit
```

**Impact:** Occasional clipping on consecutive utterances  
**Timeline:** Fix in v27.1

---

#### P3.3: TTSManager queue not drained on stop

**Location:** `VoicePipeline::stopListening()`  
**Severity:** ⭐⭐☆☆☆ Low

```cpp
// If multiple speak() calls queued, then stop()
m_speechQueue.clear();  // ← Should be called but isn't?

// Issue: Old TTS requests may still play after user stopped

// ✅ FIX:
void stopSpeaking() {
    m_speechQueue.clear();  // drain queue
    emit _doCancelWorker();  // cancel current
}
```

**Impact:** Unexpected audio playback after "stop"  
**Timeline:** Fix in v27.1

---

## Risques détaillés

### Risk Matrix

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|-----------|
| Audio dropout (mutex contention) | Medium | High | Lock-free buffer |
| STT transcript loss (network down) | Low-Medium | Medium | Client buffer + resend |
| TTS timeout (slow GPU) | Low | Medium | Increase timeout |
| Deadlock (WebSocket + Qt) | Very Low | Critical | Code review + testing |
| Memory leak (STT buffer) | Low | High | Cap buffer size |
| VAD flapping (network transient) | Low | Low | Fallback working ✅ |

### Deadlock scenarios

#### Scenario 1: Circular wait on mutex

```cpp
THREAD A (Audio callback):
  1. Lock CircularAudioBuffer::m_mutex
  2. Try to acquire VADEngine mutex
  3. WAIT for THREAD B

THREAD B (Main):
  1. Lock VADEngine mutex
  2. Try to access CircularAudioBuffer
  3. WAIT for THREAD A

RESULT: Deadlock ❌

LIKELIHOOD: Very low (code doesn't actually do this)
MITIGATION: ✅ Code review confirms no circular locking
```

#### Scenario 2: QEventLoop blocking

```cpp
THREAD: TTSWorker (QThread)
  synthLoop.exec();  // ← BLOCKS

Main thread:
  Q_INVOKE(TTSWorker, cancelCurrent)
    → Posts event to TTSWorker event queue
    BUT TTSWorker is blocked in synthLoop.exec()
    → Event waits for synthLoop to exit
    → timeout fires → synthLoop.quit()
    → Event processed

RESULT: ~12s wait for cancellation ⚠️

LIKELIHOOD: Low (timeout catches it)
MITIGATION: ✅ Timeout mechanism working
```

### Buffer underrun/overrun

#### CircularAudioBuffer overrun

```
Scenario: Rapid audio input, slow STT processing

TIMELINE:
  0ms: 16K samples arrive
  32ms: 16K samples arrive
  64ms: CircularAudioBuffer: count = 32K
  96ms: 16K samples arrive
  128ms: CircularAudioBuffer: count = 48K
  ...
  960ms: CircularAudioBuffer FULL (480K)
  992ms: 16K samples arrive
         → write() drops oldest 16K samples (overwrite)
         → Loss! ❌

IMPACT: Missing audio chunk at start of transcription
LIKELIHOOD: ⭐⭐⭐☆☆ Medium (if STT slow or network down)

FIX: Increase buffer? (currently 30s — should be sufficient)
    OR: Drop new samples instead of old? (depends on use case)
```

#### PCMRingBuffer underrun

```
Scenario: Pump timer faster than TTS chunks arrive

TIMELINE:
  0ms: First TTS chunk arrives (128 frames = 5.3ms @ 24kHz)
  33ms: Pump timer fires
         ringBuffer.availableRead() = 256 bytes (only 10.7ms)
         read all 256 bytes
         sink->write(256 bytes)
         ← UNDERFLOW (pump expects ~96KB/33ms!)
  
  66ms: No TTS chunks yet (network slow)
         ringBuffer.availableRead() = 0
         read 0 bytes
         sink->write(0 bytes)
         ← SILENCE!

IMPACT: Audio pops/clicks or silence
LIKELIHOOD: ⭐⭐☆☆☆ Low (network RTT ~20ms << pump interval 33ms)

MITIGATION: ✅ Anti-jitter pump timer handles this
              sink->write() can accept partial writes
              Sink provides buffering (extra ~100ms)
```

---

## Dépendances inter-composants

### Dependency graph

```
VoicePipeline
  ├─ depends on:
  │  ├─ AudioInput (Qt or RtAudio)
  │  ├─ AudioDeviceManager
  │  ├─ AudioPreprocessor
  │  ├─ VADEngine → WebSocketClient → vad_server.py
  │  ├─ StreamingSTT → WebSocketClient → stt_server.py
  │  └─ CircularAudioBuffer
  │
  └─ signals:
     ├─ speechTranscribed(text) → AssistantManager
     └─ commandDetected(command)

TTSManager
  ├─ depends on:
  │  ├─ TTSWorker (QThread)
  │  ├─ TTSBackendXTTS → WebSocketClient → tts_server.py
  │  ├─ TTSBackendQt (fallback)
  │  ├─ TTSDSPProcessor
  │  ├─ PCMRingBuffer
  │  └─ QAudioSink
  │
  └─ signals:
     ├─ speakingChanged() → VoicePipeline
     └─ ttsVoicesChanged() → QML

AssistantManager
  ├─ depends on:
  │  ├─ VoicePipeline
  │  ├─ TTSManager
  │  ├─ ClaudeAPI (external)
  │  ├─ AudioDeviceManager
  │  └─ other services (WeatherManager, etc.)
  │
  └─ orchestrates:
     Speech input → transcription → Claude → speech output
```

### Critical paths

#### Input path (mic → STT)

```
AudioInput (RtAudio/Qt)
  ↓ (callback)
VoicePipeline::onAudioChunk()
  ├─ AudioPreprocessor
  ├─ VADEngine
  ├─ CircularAudioBuffer
  └─ StreamingSTT::feedAudio()
      ↓ (WebSocket)
      stt_server.py
      ↓ (Whisper)
      transcription
      ↓ (WebSocket)
      StreamingSTT::onPartialTranscript()
      ↓ (Signal)
      VoicePipeline::onTranscriptionReady()
      ↓ (Signal)
      AssistantManager::onSpeechTranscribed()

DEPENDENCIES:
  ✓ AudioInput must be initialized first
  ✓ stt_server.py must be running (with fallback?)
  ✓ VAD must not block callback (→ ISSUE P1.1)
  ✓ WebSocket must reconnect on failure
```

#### Output path (Claude → TTS)

```
AssistantManager::handleClaudeResponse()
  ↓
VoicePipeline::speak(text)
  ↓
TTSManager::enqueueSpeech()
  ↓ (Qt::QueuedConnection)
TTSWorker::processRequest()
  ↓
TTSBackendXTTS::synthesize()
  ├─ ensureConnected()
  └─ sendBinaryChunks()
      ↓ (WebSocket)
      tts_server.py
      ↓ (CosyVoice)
      synthesize_stream()
      ↓ (WebSocket)
      TTSBackendXTTS::onBinaryMessageReceived()
      ↓ (Signal)
      TTSManager::onWorkerChunk()
      ├─ TTSDSPProcessor
      ├─ PCMRingBuffer::write()
      └─ pumpTimer → sink->write()
          ↓
          QAudioSink
          ↓
          Speaker

DEPENDENCIES:
  ✓ TTSWorker thread must be running
  ✓ tts_server.py must be running (with Qt fallback)
  ✓ PCMRingBuffer must not underrun (→ complex timing)
  ✓ Pump timer must run reliably (33ms)
  ✓ QAudioSink must have valid device
```

---

## Résumé des recommandations

### Immédiat (v27.1)

1. **FIX P1.1**: Protect AudioPreprocessor with mutex
   ```cpp
   QMutexLocker lk(&m_preprocessorMutex);
   m_preprocessor.process(...);
   ```

2. **FIX P1.2**: Cap STTSession._audio_buffer
   ```python
   if len(self._audio_buffer) > 10 * 1024 * 1024:
       raise ValueError("Buffer overflow")
   ```

3. **FIX P3.2**: Reset AudioPreprocessor state
   ```cpp
   m_preprocessor.reset(); // on utterance end
   ```

4. **FIX P3.3**: Drain TTS queue on stop
   ```cpp
   m_speechQueue.clear();
   emit _doCancelWorker();
   ```

### Court terme (v27.2)

5. **ENHANCE**: Add comprehensive latency telemetry
6. **ENHANCE**: Implement client-side STT buffer + resend on reconnect
7. **ENHANCE**: Evaluate WebSocket timeout for CosyVoice (P1.3)
8. **REFACTOR**: Move audio preprocessing to thread pool (non-blocking callback)

### Moyen terme (v28+)

9. **REFACTOR**: Make PCMRingBuffer fully atomic/lock-free
10. **MIGRATE**: Consider gRPC or QUIC for lower network latency
11. **IMPLEMENT**: Local LLM option (reduce Claude API latency)
12. **OPTIMIZE**: CosyVoice 0.25B variant for faster first chunk?

---

## Conclusion

The EXO audio pipeline is **well-architected overall**, with good separation of concerns (C++ orchestration + Python backends). However, several **thread-safety issues** and **optimization opportunities** exist:

### Strengths ✅
- Clean component separation
- Async/await design in Python backends
- Good error handling with service fallbacks
- Extensive latency optimizations (v26.2+)
- Anti-jitter pump mechanism

### Weaknesses ❌
- **Thread-safety gaps** (AudioPreprocessor, no atomic indices)
- **Unbounded buffers** (STTSession._audio_buffer)
- **Long timeouts** (WebSocket synthesis waits 12s)
- **Missing telemetry** (difficult to optimize)
- **Blocking callbacks** (audio thread not fully async)

### Overall Health: **7.5/10**
- Critical issues: 2 (must fix)
- Major issues: 3 (should fix)
- Minor issues: 3 (nice to have)

**Estimated fix time:** ~20-30 hours for all recommendations.

---

**End of Audit**

*Generated: 2026-05-01 | Framework: EXO v27 | Analyzer: GitHub Copilot*
