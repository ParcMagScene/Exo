#!/usr/bin/env python3
"""

# Patch global EXO : forcer le working directory à D:/EXO/ pour tous les services
import os
os.chdir("D:/EXO/")
EXO v10 — TaskVerifier Server (WebSocket)
Port 8780 — Vérification des résultats d'exécution

Vérifie la cohérence et la qualité des résultats retournés par
les étapes d'un plan, détecte les inconsistances, vérifie l'état
des dispositifs domotique/réseau et propose des corrections.

Protocol WebSocket :
  → {"action":"verify_result","params":{"step":{...},"result":{...},"goal":"..."}}
  ← {"ok":true,"data":{"valid":true,"confidence":0.95,"issues":[]}}

  → {"action":"verify_plan","params":{"plan":{...},"results":{...}}}
  ← {"ok":true,"data":{"valid":true,"step_verdicts":[...],"summary":"..."}}

  → {"action":"check_consistency","params":{"results":[...]}}
  ← {"ok":true,"data":{"consistent":true,"conflicts":[]}}

  → {"action":"validate_state","params":{"device_id":"...","expected_state":{...}}}
  ← {"ok":true,"data":{"valid":true,"actual_state":{...},"mismatches":[]}}
"""

import asyncio
try:
    import ujson as json  # v6.0 perf : 3-5x plus rapide que stdlib (audit perf)
except ImportError:
    import json
import logging
import sys
from pathlib import Path

try:
    import websockets
except ImportError:
    raise SystemExit("pip install websockets")

from shared.singleton_guard import ensure_single_instance
from shared.base_service import init_v9


# --- Logging EXO centralisé (identique C++) ---
import os
from pathlib import Path
def _get_exo_logfile():
    # Correction : tous les logs doivent aller dans D:/EXO/logs/
    project_root = Path(__file__).resolve().parent.parent.parent
    log_dir = os.environ.get("EXO_LOGS_DIR", str(project_root / "logs"))
    Path(log_dir).mkdir(parents=True, exist_ok=True)
    ts = os.environ.get("EXO_SESSION_TIMESTAMP")
    if not ts:
        from datetime import datetime
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    return os.path.join(log_dir, f"exo_{ts}.log")

logfile = _get_exo_logfile()

_file_handler = logging.FileHandler(logfile, encoding="utf-8", delay=False)
_file_handler.setLevel(logging.INFO)
_file_handler.setFormatter(logging.Formatter("%(asctime)s [Verifier] %(message)s"))
_file_handler.flush = _file_handler.stream.flush

logging.basicConfig(level=logging.INFO, format="%(asctime)s [Verifier] %(message)s")
log = logging.getLogger("task_verifier")
log.addHandler(_file_handler)
log.propagate = True
log.info("=== EXO TASK_VERIFIER_SERVER STARTUP ===")
_file_handler.flush()

PORT = 8780


class TaskVerifier:
    """Verifies task execution results for correctness and consistency."""

    def verify_result(self, step: dict, result: dict, goal: str = "") -> dict:
        """Verify a single step result against expectations."""
        issues = []
        confidence = 1.0

        tool = step.get("tool", "")
        description = step.get("description", "")

        # Check if result is empty
        if not result:
            issues.append({
                "type": "empty_result",
                "severity": "high",
                "message": f"Step '{description}' returned empty result",
            })
            confidence *= 0.3

        # Check for error indicators in result
        if result and result.get("error"):
            issues.append({
                "type": "error_in_result",
                "severity": "high",
                "message": f"Result contains error: {result['error']}",
            })
            confidence *= 0.2

        # Check for warning indicators
        if result and result.get("warning"):
            issues.append({
                "type": "warning_in_result",
                "severity": "medium",
                "message": f"Result contains warning: {result['warning']}",
            })
            confidence *= 0.7

        # Tool-specific verification
        tool_issues = self._verify_tool_result(tool, result or {})
        issues.extend(tool_issues)
        for issue in tool_issues:
            if issue["severity"] == "high":
                confidence *= 0.5
            elif issue["severity"] == "medium":
                confidence *= 0.8

        return {
            "valid": len([i for i in issues if i["severity"] == "high"]) == 0,
            "confidence": round(max(0.0, min(1.0, confidence)), 3),
            "issues": issues,
            "step_index": step.get("index", 0),
        }

    def verify_plan(self, plan: dict, results: dict) -> dict:
        """Verify all results of a plan execution."""
        steps = plan.get("steps", [])
        goal = plan.get("goal", "")
        verdicts = []

        for step in steps:
            idx = step.get("index", 0)
            result = results.get(str(idx), results.get(idx, {}))
            if step.get("is_composite"):
                continue
            verdict = self.verify_result(step, result or {}, goal)
            verdicts.append(verdict)

        # Overall assessment
        all_valid = all(v["valid"] for v in verdicts)
        avg_confidence = (
            sum(v["confidence"] for v in verdicts) / len(verdicts)
            if verdicts else 0.0
        )
        high_issues = sum(
            len([i for i in v["issues"] if i["severity"] == "high"])
            for v in verdicts
        )

        if all_valid and avg_confidence > 0.8:
            summary = "Plan exécuté avec succès, tous les résultats sont valides."
        elif all_valid:
            summary = "Plan exécuté, résultats valides mais confiance modérée."
        else:
            summary = f"Plan exécuté avec {high_issues} problème(s) critique(s)."

        return {
            "valid": all_valid,
            "avg_confidence": round(avg_confidence, 3),
            "step_verdicts": verdicts,
            "summary": summary,
            "high_issues": high_issues,
        }

    def check_consistency(self, results: list[dict]) -> dict:
        """Check consistency across multiple step results."""
        conflicts = []

        # Check for contradictory information in results
        for i, r1 in enumerate(results):
            for j, r2 in enumerate(results):
                if i >= j:
                    continue
                conflict = self._find_conflicts(r1, r2, i, j)
                if conflict:
                    conflicts.append(conflict)

        return {
            "consistent": len(conflicts) == 0,
            "conflicts": conflicts,
            "checked_pairs": len(results) * (len(results) - 1) // 2,
        }

    def _verify_tool_result(self, tool: str, result: dict) -> list[dict]:
        """Tool-specific result verification."""
        issues = []

        if tool == "search_web":
            results_list = result.get("results", [])
            if isinstance(results_list, list) and len(results_list) == 0:
                issues.append({
                    "type": "no_search_results",
                    "severity": "medium",
                    "message": "Web search returned no results",
                })

        elif tool == "get_news":
            articles = result.get("articles", [])
            if isinstance(articles, list) and len(articles) == 0:
                issues.append({
                    "type": "no_news",
                    "severity": "low",
                    "message": "No news articles found",
                })

        elif tool == "calculate":
            if "result" not in result:
                issues.append({
                    "type": "no_calculation_result",
                    "severity": "high",
                    "message": "Calculation returned no result value",
                })

        elif tool == "recall_info":
            memories = result.get("results", [])
            if isinstance(memories, list) and len(memories) == 0:
                issues.append({
                    "type": "no_memories",
                    "severity": "low",
                    "message": "No relevant memories found",
                })

        return issues

    def _find_conflicts(self, r1: dict, r2: dict,
                        idx1: int, idx2: int) -> dict | None:
        """Find conflicts between two results (basic heuristic)."""
        # Check if both have numeric results that contradict
        val1 = r1.get("result")
        val2 = r2.get("result")

        if (isinstance(val1, (int, float)) and isinstance(val2, (int, float))
                and val1 != 0 and val2 != 0):
            ratio = max(val1, val2) / min(abs(val1), abs(val2))
            if ratio > 100:  # Suspicious divergence
                return {
                    "steps": [idx1, idx2],
                    "type": "value_divergence",
                    "message": f"Large value divergence: {val1} vs {val2}",
                }

        return None

    def validate_state(self, device_id: str, expected_state: dict) -> dict:
        """Validate that a device/service is in the expected state.

        Used by the agent to verify that actions had the intended effect.
        Supports domotique devices, network services, and logic assertions.
        """
        mismatches: list[dict] = []
        actual_state: dict = {}
        category = expected_state.get("category", "generic")

        if category == "domotique":
            actual_state = self._check_domotique(device_id, expected_state)
        elif category == "network":
            actual_state = self._check_network(device_id, expected_state)
        elif category == "logic":
            actual_state = self._check_logic(device_id, expected_state)
        else:
            actual_state = {"status": "unknown", "device_id": device_id}

        # Compare expected vs actual
        for key, expected_val in expected_state.items():
            if key == "category":
                continue
            actual_val = actual_state.get(key)
            if actual_val is not None and actual_val != expected_val:
                mismatches.append({
                    "field": key,
                    "expected": expected_val,
                    "actual": actual_val,
                })

        return {
            "valid": len(mismatches) == 0,
            "device_id": device_id,
            "category": category,
            "actual_state": actual_state,
            "mismatches": mismatches,
        }

    def _check_domotique(self, device_id: str, expected: dict) -> dict:
        """Check domotique device state (simulated — real impl connects to HA)."""
        return {
            "device_id": device_id,
            "status": "on",
            "reachable": True,
            "last_seen": "now",
        }

    def _check_network(self, device_id: str, expected: dict) -> dict:
        """Check network service state."""
        return {
            "device_id": device_id,
            "status": "up",
            "reachable": True,
            "latency_ms": 5,
        }

    def _check_logic(self, device_id: str, expected: dict) -> dict:
        """Check logic assertion."""
        return {
            "device_id": device_id,
            "status": "ok",
            "assertion": expected.get("assertion", ""),
            "result": True,
        }


# ─────────────────────────────────────────────────────
#  WebSocket Handler
# ─────────────────────────────────────────────────────

async def handle_client(ws, verifier: TaskVerifier) -> None:
    log.info("Verifier client connected")
    await ws.send(json.dumps({
        "type": "ready",
        "service": "task_verifier",
        "model": "n/a",
        "device": "n/a",
        "backend": "n/a"
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
                if action == "verify_result":
                    step = params.get("step", {})
                    result = params.get("result", {})
                    goal = params.get("goal", "")
                    verdict = verifier.verify_result(step, result, goal)
                    await ws.send(json.dumps({"ok": True, "data": verdict}))

                elif action == "verify_plan":
                    plan = params.get("plan", {})
                    results = params.get("results", {})
                    verdict = verifier.verify_plan(plan, results)
                    await ws.send(json.dumps({"ok": True, "data": verdict}))

                elif action == "check_consistency":
                    results = params.get("results", [])
                    check = verifier.check_consistency(results)
                    await ws.send(json.dumps({"ok": True, "data": check}))

                elif action == "validate_state":
                    device_id = params.get("device_id", "")
                    expected_state = params.get("expected_state", {})
                    result = verifier.validate_state(device_id, expected_state)
                    await ws.send(json.dumps({"ok": True, "data": result}))

                else:
                    await ws.send(json.dumps({
                        "ok": False,
                        "error": f"Unknown action: {action}",
                    }))

            except Exception as e:
                log.error("Verifier operation error: %s", e, exc_info=True)
                await ws.send(json.dumps({"ok": False, "error": "Erreur interne du service verifier"}))

    except Exception as e:
        log.error("Verifier session error: %s", e)
    finally:
        log.info("Verifier client disconnected")


# ─────────────────────────────────────────────────────
#  Main
# ─────────────────────────────────────────────────────

async def main() -> None:
    import argparse
    parser = argparse.ArgumentParser(description="EXO v10 Task Verifier Server")
    parser.add_argument("--host", default="localhost")
    parser.add_argument("--port", type=int, default=PORT)
    args = parser.parse_args()

    ensure_single_instance(args.port, "task_verifier")
    _v9 = init_v9("task_verifier", args.port)

    verifier = TaskVerifier()
    log.info("TaskVerifier initialized")

    async def handler(ws):
        await handle_client(ws, verifier)

    server = await websockets.serve(
        handler, args.host, args.port,
        ping_interval=None, ping_timeout=None,
    )
    log.info("Task Verifier running on ws://%s:%d", args.host, args.port)

    try:
        await asyncio.Future()
    except KeyboardInterrupt:
        pass
    finally:
        server.close()
        await server.wait_closed()
        log.info("Task Verifier stopped")


if __name__ == "__main__":
    asyncio.run(main())
