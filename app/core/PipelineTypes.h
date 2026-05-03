#pragma once

#include <QString>

// ─────────────────────────────────────────────────────
//  EventType — identifiant typé de chaque événement pipeline
//
//  Remplace les chaînes de caractères brutes "speech_started",
//  "final_transcript", etc. par un enum vérifié à la compilation.
// ─────────────────────────────────────────────────────
enum class EventType {
    // ── VAD ──
    SpeechStarted,          // "speech_started"
    SpeechEnded,            // "speech_ended"

    // ── WakeWord ──
    WakeWordDetected,       // "wakeword_detected"

    // ── STT ──
    StreamStarted,          // "stream_started"
    PartialTranscript,      // "partial_transcript"
    FinalTranscript,        // "final_transcript"
    UtteranceFinished,      // "utterance_finished"
    STTError,               // "error" (STT)

    // ── Claude / LLM ──
    RequestStarted,         // "request_started"
    FirstToken,             // "first_token"
    PartialResponse,        // "partial_response"
    FinalResponse,          // "final_response"
    SentenceReady,          // "sentence_ready"
    ReplyFinished,          // "reply_finished"
    ToolCall,               // "tool_call"
    ToolCallDispatched,     // "tool_call_dispatched"
    NetworkError,           // "network_error"
    ResponseReceived,       // "response_received"

    // ── TTS ──
    SynthesisRequested,     // "synthesis_requested"
    SentenceQueued,         // "sentence_queued"
    SpeechCancelled,        // "speech_cancelled"
    WorkerStarted,          // "worker_started"
    WorkerError,            // "worker_error"
    SpeechFinalized,        // "speech_finalized"
    SpeakRequested,         // "speak_requested"
    SentenceEnqueued,       // "sentence_enqueued"

    // ── AudioOutput ──
    PcmChunk,               // "pcm_chunk"
    PlaybackStarted,        // "playback_started"
    PlaybackFinished,       // "playback_finished"
    TTSError,               // "error" (TTS)

    // ── Orchestrator ──
    TranscriptDispatched,   // "transcript_dispatched"
    SpeechTranscribed,      // "speech_transcribed"
    StateChanged,           // "state_changed"
    OrphanInteractionClosed // "orphan_interaction_closed"
};

// ─────────────────────────────────────────────────────
//  Conversion enum → string pour JSON / logging
// ─────────────────────────────────────────────────────
inline QString eventTypeToString(EventType t)
{
    switch (t) {
    // VAD
    case EventType::SpeechStarted:          return QStringLiteral("speech_started");
    case EventType::SpeechEnded:            return QStringLiteral("speech_ended");
    // WakeWord
    case EventType::WakeWordDetected:       return QStringLiteral("wakeword_detected");
    // STT
    case EventType::StreamStarted:          return QStringLiteral("stream_started");
    case EventType::PartialTranscript:      return QStringLiteral("partial_transcript");
    case EventType::FinalTranscript:        return QStringLiteral("final_transcript");
    case EventType::UtteranceFinished:      return QStringLiteral("utterance_finished");
    case EventType::STTError:               return QStringLiteral("error");
    // Claude
    case EventType::RequestStarted:         return QStringLiteral("request_started");
    case EventType::FirstToken:             return QStringLiteral("first_token");
    case EventType::PartialResponse:        return QStringLiteral("partial_response");
    case EventType::FinalResponse:          return QStringLiteral("final_response");
    case EventType::SentenceReady:          return QStringLiteral("sentence_ready");
    case EventType::ReplyFinished:          return QStringLiteral("reply_finished");
    case EventType::ToolCall:               return QStringLiteral("tool_call");
    case EventType::ToolCallDispatched:     return QStringLiteral("tool_call_dispatched");
    case EventType::NetworkError:           return QStringLiteral("network_error");
    case EventType::ResponseReceived:       return QStringLiteral("response_received");
    // TTS
    case EventType::SynthesisRequested:     return QStringLiteral("synthesis_requested");
    case EventType::SentenceQueued:         return QStringLiteral("sentence_queued");
    case EventType::SpeechCancelled:        return QStringLiteral("speech_cancelled");
    case EventType::WorkerStarted:          return QStringLiteral("worker_started");
    case EventType::WorkerError:            return QStringLiteral("worker_error");
    case EventType::SpeechFinalized:        return QStringLiteral("speech_finalized");
    case EventType::SpeakRequested:         return QStringLiteral("speak_requested");
    case EventType::SentenceEnqueued:       return QStringLiteral("sentence_enqueued");
    // AudioOutput
    case EventType::PcmChunk:               return QStringLiteral("pcm_chunk");
    case EventType::PlaybackStarted:        return QStringLiteral("playback_started");
    case EventType::PlaybackFinished:       return QStringLiteral("playback_finished");
    case EventType::TTSError:               return QStringLiteral("error");
    // Orchestrator
    case EventType::TranscriptDispatched:   return QStringLiteral("transcript_dispatched");
    case EventType::SpeechTranscribed:      return QStringLiteral("speech_transcribed");
    case EventType::StateChanged:           return QStringLiteral("state_changed");
    case EventType::OrphanInteractionClosed:return QStringLiteral("orphan_interaction_closed");
    }
    return QStringLiteral("unknown");
}
