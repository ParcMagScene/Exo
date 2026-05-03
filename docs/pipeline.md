# Pipeline EXO — Événements

> Auto-généré par `auto_maintain.py` — 2026-04-12

## Flux audio

```
Microphone ─→ VAD ─→ WakeWord ─→ STT ─→ NLU/Claude ─→ TTS ─→ Speaker
```

## EventTypes (pipelinetypes.h)

| # | EventType | Catégorie |
|---|-----------|-----------|
| 1 | `SpeechStarted` | VAD |
| 2 | `SpeechEnded` | VAD |
| 3 | `WakeWordDetected` | WakeWord |
| 4 | `StreamStarted` | STT |
| 5 | `PartialTranscript` | STT |
| 6 | `FinalTranscript` | STT/LLM |
| 7 | `UtteranceFinished` | STT |
| 8 | `STTError` | STT |
| 9 | `RequestStarted` | LLM |
| 10 | `FirstToken` | LLM |
| 11 | `PartialResponse` | STT |
| 12 | `FinalResponse` | STT/LLM |
| 13 | `SentenceReady` | LLM/TTS |
| 14 | `ReplyFinished` | LLM |
| 15 | `ToolCall` | LLM |
| 16 | `ToolCallDispatched` | LLM |
| 17 | `NetworkError` | LLM |
| 18 | `ResponseReceived` | LLM |
| 19 | `SynthesisRequested` | TTS |
| 20 | `SentenceQueued` | LLM/TTS |
| 21 | `SpeechCancelled` | VAD |
| 22 | `WorkerStarted` | TTS |
| 23 | `WorkerError` | TTS |
| 24 | `SpeechFinalized` | VAD |
| 25 | `SpeakRequested` | TTS |
| 26 | `SentenceEnqueued` | LLM/TTS |
| 27 | `PcmChunk` | Audio |
| 28 | `PlaybackStarted` | Audio |
| 29 | `PlaybackFinished` | Audio |
| 30 | `TTSError` | TTS |
| 31 | `TranscriptDispatched` | Orchestrator |
| 32 | `SpeechTranscribed` | VAD |
| 33 | `StateChanged` | Orchestrator |
| 34 | `OrphanInteractionClosed` | Orchestrator |
