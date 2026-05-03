"""Smoke test du serveur Orpheus.

Usage : python test_client.py "Bonjour, ceci est un test."
"""
from __future__ import annotations

import argparse
import base64
import json
import sys
import urllib.request


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("text", nargs="?", default="Bonjour, je suis Orphee. Comment vas-tu aujourd'hui ?")
    p.add_argument("--voice", default="pierre")
    p.add_argument("--speed", type=float, default=1.0)
    p.add_argument("--url", default="http://127.0.0.1:8899/tts")
    p.add_argument("--out", default="orpheus_out.wav")
    args = p.parse_args()

    payload = json.dumps({"text": args.text, "voice": args.voice, "speed": args.speed}).encode("utf-8")
    req = urllib.request.Request(args.url, data=payload, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=180) as r:
            data = json.loads(r.read())
    except Exception as e:
        print(f"[err] requete echouee : {e}", file=sys.stderr)
        return 1

    wav = base64.b64decode(data["audio_b64"])
    with open(args.out, "wb") as f:
        f.write(wav)
    print(f"[ok] sample_rate={data['sample_rate']} duration={data['duration_s']:.2f}s "
          f"rtf={data['rtf']:.2f} voice={data['voice']} -> {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
