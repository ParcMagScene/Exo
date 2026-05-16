#!/usr/bin/env python3
"""
EXO v8 — FileService (WebSocket)
Port 8781 — Opérations fichiers sécurisées pour l'agent autonome

Permet à Claude de lire, écrire et lister des fichiers dans un
périmètre sécurisé (sandbox). Aucun accès hors du répertoire autorisé.

Protocol WebSocket :
  → {"action":"file_read","params":{"path":"notes/todo.txt"}}
  ← {"ok":true,"data":{"path":"...","content":"...","size":123}}

  → {"action":"file_write","params":{"path":"notes/todo.txt","content":"..."}}
  ← {"ok":true,"data":{"path":"...","written":true,"size":45}}

  → {"action":"file_list","params":{"path":"notes/","pattern":"*.txt"}}
  ← {"ok":true,"data":{"path":"...","files":[...]}}

  → {"action":"file_delete","params":{"path":"notes/old.txt"}}
  ← {"ok":true,"data":{"path":"...","deleted":true}}
"""

import asyncio
import fnmatch
import json
import logging
import os
import sys
from pathlib import Path

try:
    import websockets
except ImportError:
    raise SystemExit("pip install websockets")

from shared.singleton_guard import ensure_single_instance
from shared.base_service import init_v9

logging.basicConfig(level=logging.INFO, format="%(asctime)s [FileService] %(message)s")
log = logging.getLogger("file_service")

PORT = 8781
MAX_FILE_SIZE = 1_000_000  # 1 MB max read/write
project_root = Path(__file__).resolve().parent.parent.parent
SANDBOX_DIR = Path(os.environ.get("EXO_FILES_DIR", str(project_root / "files")))

# Forbidden extensions (security)
FORBIDDEN_EXTENSIONS = {".exe", ".bat", ".cmd", ".ps1", ".vbs", ".js",
                         ".msi", ".dll", ".sys", ".com", ".scr"}


class FileService:
    """Sandboxed file operations for the EXO agent."""

    def __init__(self, sandbox: Path) -> None:
        self._sandbox = sandbox.resolve()
        self._sandbox.mkdir(parents=True, exist_ok=True)
        log.info("Sandbox directory: %s", self._sandbox)

    def _safe_path(self, user_path: str) -> Path:
        """Resolve user path within sandbox, preventing traversal."""
        # Normalize and resolve
        clean = user_path.replace("\\", "/").lstrip("/")
        resolved = (self._sandbox / clean).resolve()

        # Security: must stay within sandbox
        if not str(resolved).startswith(str(self._sandbox)):
            raise PermissionError(f"Path traversal blocked: {user_path}")

        # Check forbidden extensions
        if resolved.suffix.lower() in FORBIDDEN_EXTENSIONS:
            raise PermissionError(f"Forbidden file type: {resolved.suffix}")

        return resolved

    def read(self, path: str) -> dict:
        resolved = self._safe_path(path)
        if not resolved.is_file():
            raise FileNotFoundError(f"File not found: {path}")
        if resolved.stat().st_size > MAX_FILE_SIZE:
            raise ValueError(f"File too large: {resolved.stat().st_size} bytes")

        content = resolved.read_text(encoding="utf-8", errors="replace")
        return {
            "path": str(resolved.relative_to(self._sandbox)),
            "content": content,
            "size": len(content),
        }

    def write(self, path: str, content: str) -> dict:
        if len(content) > MAX_FILE_SIZE:
            raise ValueError(f"Content too large: {len(content)} bytes")

        resolved = self._safe_path(path)
        resolved.parent.mkdir(parents=True, exist_ok=True)
        resolved.write_text(content, encoding="utf-8")
        return {
            "path": str(resolved.relative_to(self._sandbox)),
            "written": True,
            "size": len(content),
        }

    def list_files(self, path: str = "", pattern: str = "*") -> dict:
        resolved = self._safe_path(path) if path else self._sandbox
        if not resolved.is_dir():
            raise FileNotFoundError(f"Directory not found: {path}")

        files = []
        for entry in sorted(resolved.iterdir()):
            if not fnmatch.fnmatch(entry.name, pattern):
                continue
            rel = str(entry.relative_to(self._sandbox))
            files.append({
                "name": entry.name,
                "path": rel,
                "is_dir": entry.is_dir(),
                "size": entry.stat().st_size if entry.is_file() else 0,
            })

        return {
            "path": str(resolved.relative_to(self._sandbox)) if path else ".",
            "files": files[:100],  # Limit results
            "count": len(files),
        }

    def delete(self, path: str) -> dict:
        resolved = self._safe_path(path)
        if not resolved.exists():
            raise FileNotFoundError(f"File not found: {path}")
        if resolved.is_dir():
            raise PermissionError("Cannot delete directories")

        resolved.unlink()
        return {
            "path": str(resolved.relative_to(self._sandbox)),
            "deleted": True,
        }


# ─────────────────────────────────────────────────────
#  WebSocket Handler
# ─────────────────────────────────────────────────────

async def handle_client(ws, service: FileService) -> None:
    log.info("FileService client connected")
    await ws.send(json.dumps({
        "type": "ready", "service": "file_service", "version": "v8",
        "sandbox": str(service._sandbox),
    }))

    try:
        async for raw in ws:
            if not isinstance(raw, str):
                continue
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                continue

            action = msg.get("action", msg.get("type", ""))
            params = msg.get("params", {})

            if action == "ping":
                await ws.send(json.dumps({"type": "pong"}))
                continue

            try:
                if action == "file_read":
                    data = service.read(params.get("path", ""))
                    await ws.send(json.dumps({"ok": True, "data": data}))

                elif action == "file_write":
                    data = service.write(
                        params.get("path", ""),
                        params.get("content", ""),
                    )
                    await ws.send(json.dumps({"ok": True, "data": data}))

                elif action == "file_list":
                    data = service.list_files(
                        params.get("path", ""),
                        params.get("pattern", "*"),
                    )
                    await ws.send(json.dumps({"ok": True, "data": data}))

                elif action == "file_delete":
                    data = service.delete(params.get("path", ""))
                    await ws.send(json.dumps({"ok": True, "data": data}))

                else:
                    await ws.send(json.dumps({
                        "ok": False,
                        "error": f"Unknown action: {action}",
                    }))

            except (PermissionError, FileNotFoundError, ValueError) as e:
                log.warning("FileService client error: %s", e)
                await ws.send(json.dumps({"ok": False, "error": "Opération refusée ou fichier introuvable"}))
            except Exception as e:
                log.error("FileService error: %s", e, exc_info=True)
                await ws.send(json.dumps({"ok": False, "error": "Erreur interne du service fichier"}))

    except Exception as e:
        log.error("FileService session error: %s", e)
    finally:
        log.info("FileService client disconnected")


async def main() -> None:
    import argparse
    parser = argparse.ArgumentParser(description="EXO v8 File Service")
    parser.add_argument("--host", default="localhost")
    parser.add_argument("--port", type=int, default=PORT)
    parser.add_argument("--sandbox", default=str(SANDBOX_DIR))
    args = parser.parse_args()

    ensure_single_instance(args.port, "file_service")
    _v9 = init_v9("file_service", args.port)

    service = FileService(Path(args.sandbox))
    log.info("FileService initialized")

    async def handler(ws):
        await handle_client(ws, service)

    server = await websockets.serve(
        handler, args.host, args.port,
        ping_interval=None, ping_timeout=None,
    )
    log.info("File Service running on ws://%s:%d", args.host, args.port)

    try:
        await asyncio.Future()
    except KeyboardInterrupt:
        pass
    finally:
        server.close()
        await server.wait_closed()


if __name__ == "__main__":
    asyncio.run(main())
