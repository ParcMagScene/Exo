"""
EXO v18 — MacroAgentLayer (couche macro-agents)
Regroupe les agents spécialisés en macro-agents thématiques :
domotique, réseau, cognition, simulation, prévision, sécurité, mémoire.

API:
  macro_handle(intent)      → dict
  macro_delegate(task)      → dict
  macro_collect(results)    → dict
  register_macro(name, cfg) → dict
  list_macros()             → list[dict]
  health_check()            → dict
  restart()                 → None
  get_stats()               → dict
"""

import logging
import time
import uuid
from typing import Any

log = logging.getLogger("macro_agent_layer")

DEFAULT_MACROS = [
    {"name": "domotique", "domain": "home_automation",
     "description": "Contrôle domotique, appareils, scènes"},
    {"name": "reseau", "domain": "network",
     "description": "Scan réseau, diagnostic, connectivité"},
    {"name": "cognition", "domain": "cognition",
     "description": "Raisonnement, inférence, mémoire cognitive"},
    {"name": "simulation", "domain": "simulation",
     "description": "Simulation de scénarios, prédiction"},
    {"name": "prevision", "domain": "forecasting",
     "description": "Prévision, anticipation, planification"},
    {"name": "securite", "domain": "security",
     "description": "Sécurité, validation, gouvernance"},
    {"name": "memoire", "domain": "memory",
     "description": "Mémoire sémantique, épisodique, rappel"},
]


class MacroAgentLayer:
    """Couche de macro-agents thématiques EXO v18."""

    def __init__(self, meta_memory=None, governance=None,
                 registry=None, micro_layer=None):
        self._memory = meta_memory
        self._governance = governance
        self._registry = registry
        self._micro = micro_layer
        self._macros: dict[str, dict] = {}
        self._history: list[dict] = []
        self._stats = {
            "intents_handled": 0,
            "tasks_delegated": 0,
            "results_collected": 0,
            "macros_registered": 0,
        }

        # Enregistrer les macro-agents par défaut
        for m in DEFAULT_MACROS:
            self._macros[m["name"]] = {
                "name": m["name"],
                "domain": m["domain"],
                "description": m["description"],
                "active": True,
                "tasks_handled": 0,
                "created_at": time.time(),
            }
            self._stats["macros_registered"] += 1

    # ── macro_handle ────────────────────────────────────────
    def macro_handle(self, intent: dict) -> dict:
        """Traiter un intent en le routant vers le bon macro-agent."""
        self._stats["intents_handled"] += 1

        domain = intent.get("domain", "general")
        text = intent.get("text", "")
        context = intent.get("context", {})

        # Trouver le macro-agent le plus adapté
        target = self._route_intent(domain, text)
        macro = self._macros.get(target)

        if not macro or not macro["active"]:
            result = {
                "id": f"mh_{uuid.uuid4().hex[:8]}",
                "handled": False,
                "reason": "no_macro_found",
                "domain": domain,
                "timestamp": time.time(),
            }
            self._history.append(result)
            self._trim()
            return result

        macro["tasks_handled"] += 1

        # Déléguer aux micro-agents si disponible
        sub_results = []
        if self._micro:
            try:
                sub = self._micro.micro_execute({
                    "macro": target,
                    "text": text,
                    "domain": domain,
                    "context": context,
                })
                sub_results.append(sub)
            except Exception:
                pass

        # Gouvernance
        governed = True
        if self._governance:
            try:
                g = self._governance.check_action(
                    f"macro_handle:{target}", context)
                governed = g.get("allowed", True)
            except Exception:
                pass

        result = {
            "id": f"mh_{uuid.uuid4().hex[:8]}",
            "handled": True,
            "macro_agent": target,
            "domain": domain,
            "governed": governed,
            "sub_results": sub_results,
            "timestamp": time.time(),
        }

        self._history.append(result)
        self._trim()

        log.info("Intent handled by macro '%s': domain=%s", target, domain)
        return result

    # ── macro_delegate ──────────────────────────────────────
    def macro_delegate(self, task: dict) -> dict:
        """Déléguer une tâche à un macro-agent spécifique."""
        self._stats["tasks_delegated"] += 1

        target = task.get("macro", task.get("target", ""))
        action = task.get("action", "")
        params = task.get("params", {})

        macro = self._macros.get(target)
        if not macro or not macro["active"]:
            return {
                "id": f"md_{uuid.uuid4().hex[:8]}",
                "delegated": False,
                "reason": "macro_not_found",
                "target": target,
                "timestamp": time.time(),
            }

        macro["tasks_handled"] += 1

        # Coordonner l'exécution
        sub_results = []
        if self._micro:
            try:
                sub = self._micro.micro_execute({
                    "macro": target,
                    "action": action,
                    "params": params,
                })
                sub_results.append(sub)
            except Exception:
                pass

        result = {
            "id": f"md_{uuid.uuid4().hex[:8]}",
            "delegated": True,
            "macro_agent": target,
            "action": action,
            "sub_results": sub_results,
            "timestamp": time.time(),
        }

        self._history.append(result)
        self._trim()

        log.info("Task delegated to macro '%s': action=%s", target, action)
        return result

    # ── macro_collect ───────────────────────────────────────
    def macro_collect(self, results: list[dict]) -> dict:
        """Consolider les résultats de plusieurs macro-agents."""
        self._stats["results_collected"] += 1

        consolidated = []
        by_macro: dict[str, list] = {}

        for r in results:
            macro = r.get("macro_agent", r.get("macro", "unknown"))
            by_macro.setdefault(macro, []).append(r)

        for macro_name, macro_results in by_macro.items():
            consolidated.append({
                "macro": macro_name,
                "count": len(macro_results),
                "success": sum(1 for r in macro_results
                               if r.get("handled", r.get("delegated", False))),
            })

        result = {
            "id": f"mc_{uuid.uuid4().hex[:8]}",
            "consolidated": consolidated,
            "total_results": len(results),
            "unique_macros": len(by_macro),
            "timestamp": time.time(),
        }

        self._history.append(result)
        self._trim()

        log.info("Collected %d results from %d macros",
                 len(results), len(by_macro))
        return result

    # ── register_macro ──────────────────────────────────────
    def register_macro(self, name: str, config: dict) -> dict:
        """Enregistrer un nouveau macro-agent."""
        self._stats["macros_registered"] += 1
        self._macros[name] = {
            "name": name,
            "domain": config.get("domain", "general"),
            "description": config.get("description", ""),
            "active": True,
            "tasks_handled": 0,
            "created_at": time.time(),
        }
        return {"registered": True, "name": name}

    # ── list_macros ─────────────────────────────────────────
    def list_macros(self) -> list[dict]:
        return list(self._macros.values())

    # ── health / restart / stats ────────────────────────────
    def health_check(self) -> dict:
        return {
            "service": "macro_agent_layer",
            "status": "ok",
            "macros_count": len(self._macros),
            "active_macros": sum(1 for m in self._macros.values()
                                 if m["active"]),
            "stats": dict(self._stats),
        }

    def restart(self) -> None:
        self._history.clear()
        for k in self._stats:
            self._stats[k] = 0
        # Reset task counts but keep macros
        for m in self._macros.values():
            m["tasks_handled"] = 0
        log.info("MacroAgentLayer restarted")

    def get_stats(self) -> dict:
        return dict(self._stats)

    # ── Internal ────────────────────────────────────────────
    def _route_intent(self, domain: str, text: str) -> str:
        """Router un intent vers le meilleur macro-agent."""
        # Match exact par domaine
        for name, m in self._macros.items():
            if m["domain"] == domain:
                return name

        # Match par mots-clés dans le texte
        text_lower = text.lower()
        keywords = {
            "domotique": ["lumière", "lampe", "volet", "chauffage",
                          "thermostat", "scène", "appareil"],
            "reseau": ["réseau", "wifi", "ping", "scan", "ip",
                       "connexion", "routeur"],
            "cognition": ["penser", "raisonner", "comprendre",
                          "inférer", "analyser"],
            "simulation": ["simuler", "scénario", "modèle",
                           "hypothèse"],
            "prevision": ["prévoir", "anticiper", "planifier",
                          "futur", "prédire"],
            "securite": ["sécurité", "alerte", "intrusion",
                         "alarme", "protéger"],
            "memoire": ["souvenir", "rappeler", "mémoire",
                        "historique", "contexte"],
        }
        for name, kw_list in keywords.items():
            if any(kw in text_lower for kw in kw_list):
                return name

        return "cognition"  # fallback

    def _trim(self) -> None:
        if len(self._history) > 5000:
            self._history = self._history[-5000:]
