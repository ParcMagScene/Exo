"""
tts_client.py — client Python pour le serveur EXO TTS streaming.

Usage CLI:
    python -m tts.tts_client --text "Bonjour" --out out.wav
    python -m tts.tts_client --text "Bonjour" --no-save  # juste mesurer

Usage librairie:
    from tts.tts_client import TTSClient
    async with TTSClient() as cli:
        async for chunk in cli.synthesize("Bonjour"):
            ...

Protocole identique au serveur:
    → JSON  {"type":"synthesize","text":"...","voice":"exo_default"}
    ← JSON  {"type":"start","text":"..."}
    ← bytes PCM16 24 kHz mono LE (chunks)
    ← JSON  {"type":"end","duration":..,"first_chunk_ms":..,"total_ms":..}
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import time
import urllib.request
import wave
from dataclasses import dataclass
from typing import AsyncIterator, Optional

import websockets

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8767
DEFAULT_VOICE = "exo_default"
DEFAULT_LANG = "fr"
SAMPLE_RATE = 24000

logger = logging.getLogger("exo.tts.client")


@dataclass
class SynthesisResult:
    pcm: bytes
    first_chunk_ms: int
    total_ms: int
    duration_s: float
    chunks: int
    rtf: float


class TTSClient:
    """Client WebSocket stateless pour le serveur Orpheus (services/orpheus/server_ws.py)."""

    def __init__(
        self,
        host: str = DEFAULT_HOST,
        port: int = DEFAULT_PORT,
        voice: str = DEFAULT_VOICE,
        lang: str = DEFAULT_LANG,
        connect_timeout: float = 10.0,
        # Timeout *par chunk* (réinitialisé à chaque message reçu).
        chunk_timeout: float = 30.0,
    ) -> None:
        self.host = host
        self.port = port
        self.voice = voice
        self.lang = lang
        self.connect_timeout = connect_timeout
        self.chunk_timeout = chunk_timeout
        self._ws: Optional[websockets.WebSocketClientProtocol] = None

    @property
    def url(self) -> str:
        return f"ws://{self.host}:{self.port}"

    @property
    def health_url(self) -> str:
        return f"http://{self.host}:{self.port}/health"

    # ------------------------------------------------------------------ ctx
    async def __aenter__(self) -> "TTSClient":
        await self.connect()
        return self

    async def __aexit__(self, *exc) -> None:
        await self.close()

    async def connect(self) -> None:
        logger.info("[TTSClient] Connecting to %s", self.url)
        self._ws = await asyncio.wait_for(
            websockets.connect(self.url, max_size=None, ping_interval=20),
            timeout=self.connect_timeout,
        )
        # Attente du message "ready" envoyé par le serveur.
        ready_raw = await asyncio.wait_for(self._ws.recv(), timeout=self.connect_timeout)
        try:
            ready = json.loads(ready_raw)
        except (TypeError, ValueError):
            ready = {}
        if ready.get("type") != "ready":
            raise RuntimeError(f"Unexpected handshake: {ready_raw!r}")
        logger.info("[TTSClient] Server ready (sample_rate=%s)", ready.get("sample_rate"))

    async def close(self) -> None:
        if self._ws is not None:
            try:
                await self._ws.close()
            finally:
                self._ws = None

    # ------------------------------------------------------------------ health
    def health_sync(self, timeout: float = 2.0) -> dict:
        """Synchronous health check (utile pour monitoring)."""
        with urllib.request.urlopen(self.health_url, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))

    # ------------------------------------------------------------------ synth
    async def stream(
        self,
        text: str,
        *,
        rate: float = 1.0,
    ) -> AsyncIterator[bytes]:
        """Yield les chunks PCM16 au fil de l'eau. Lève RuntimeError sur 'error'."""
        if self._ws is None:
            raise RuntimeError("TTSClient not connected — use 'async with' or .connect()")
        if not text.strip():
            raise ValueError("text is empty")

        await self._ws.send(json.dumps({
            "type": "synthesize",
            "text": text,
            "voice": self.voice,
            "lang": self.lang,
            "rate": float(rate),
        }))

        while True:
            msg = await asyncio.wait_for(self._ws.recv(), timeout=self.chunk_timeout)
            if isinstance(msg, (bytes, bytearray)):
                yield bytes(msg)
                continue
            try:
                obj = json.loads(msg)
            except (TypeError, ValueError):
                continue
            t = obj.get("type")
            if t == "start":
                continue
            if t == "end":
                # On attache la métrique au générateur via un attribut.
                self.last_metrics = obj
                return
            if t == "error":
                raise RuntimeError(f"Server error: {obj.get('message')}")

    async def synthesize(self, text: str, *, rate: float = 1.0) -> SynthesisResult:
        """Helper qui collecte tous les chunks + retourne les métriques."""
        t0 = time.monotonic()
        first_chunk_ms = -1
        chunks_list: list[bytes] = []
        async for chunk in self.stream(text, rate=rate):
            if first_chunk_ms < 0:
                first_chunk_ms = int((time.monotonic() - t0) * 1000)
                logger.info("[TTSClient] First chunk received in %d ms", first_chunk_ms)
            chunks_list.append(chunk)
        end = getattr(self, "last_metrics", {}) or {}
        pcm = b"".join(chunks_list)
        total_ms = int(end.get("total_ms") or (time.monotonic() - t0) * 1000)
        duration_s = float(end.get("duration") or (len(pcm) / 2.0 / SAMPLE_RATE))
        rtf = float(end.get("rtf") or (total_ms / 1000.0 / duration_s if duration_s > 0 else 0.0))
        logger.info(
            "[TTSClient] Total audio duration: %d ms (chunks=%d, first=%d ms, RTF=%.2f)",
            int(duration_s * 1000), len(chunks_list), first_chunk_ms, rtf,
        )
        return SynthesisResult(
            pcm=pcm,
            first_chunk_ms=first_chunk_ms,
            total_ms=total_ms,
            duration_s=duration_s,
            chunks=len(chunks_list),
            rtf=rtf,
        )


def _save_wav(path: str, pcm: bytes) -> None:
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SAMPLE_RATE)
        w.writeframes(pcm)


async def _amain(args: argparse.Namespace) -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [TTS-CLIENT] %(levelname)s %(message)s",
        datefmt="%H:%M:%S",
    )
    cli = TTSClient(host=args.host, port=args.port, voice=args.voice)

    if args.health_only:
        print(json.dumps(cli.health_sync(), indent=2))
        return 0

    async with cli:
        result = await cli.synthesize(args.text, rate=args.rate)
        if args.out and not args.no_save:
            _save_wav(args.out, result.pcm)
            print(f"WAV écrit: {args.out}")
        print(json.dumps({
            "first_chunk_ms": result.first_chunk_ms,
            "total_ms": result.total_ms,
            "duration_s": round(result.duration_s, 3),
            "chunks": result.chunks,
            "rtf": round(result.rtf, 3),
        }, indent=2))
    return 0


def main() -> None:
    ap = argparse.ArgumentParser(description="EXO TTS streaming client")
    ap.add_argument("--host", default=DEFAULT_HOST)
    ap.add_argument("--port", type=int, default=DEFAULT_PORT)
    ap.add_argument("--voice", default=DEFAULT_VOICE)
    ap.add_argument("--text", default="Bonjour, je suis EXO.")
    ap.add_argument("--rate", type=float, default=1.0)
    ap.add_argument("--out", default="tts_client_out.wav")
    ap.add_argument("--no-save", action="store_true")
    ap.add_argument("--health-only", action="store_true",
                    help="Affiche /health et quitte.")
    args = ap.parse_args()
    raise SystemExit(asyncio.run(_amain(args)))


if __name__ == "__main__":
    main()
