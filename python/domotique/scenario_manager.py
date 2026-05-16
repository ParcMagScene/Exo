"""
EXO Domotique v2 — ScenarioManager

Moteur de scénarios domotiques intelligents.
Scénarios prédéfinis (cinéma, nuit, absence, réveil, sécurité, éco)
+ scénarios personnalisés.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Awaitable

log = logging.getLogger("scenario_manager")


class StepType(str, Enum):
    ACTION = "action"         # commande sur un device
    WAIT = "wait"             # délai en secondes
    CONDITION = "condition"   # vérification d'état
    PARALLEL = "parallel"     # actions en parallèle


@dataclass
class ScenarioStep:
    """Étape d'un scénario."""
    type: StepType
    target: str = ""           # device_id ou ""
    command: str = ""          # commande appliquée
    params: dict = field(default_factory=dict)
    delay_s: float = 0.0      # pour WAIT
    children: list["ScenarioStep"] = field(default_factory=list)  # pour PARALLEL

    def to_dict(self) -> dict:
        d: dict[str, Any] = {"type": self.type.value}
        if self.target:
            d["target"] = self.target
        if self.command:
            d["command"] = self.command
        if self.params:
            d["params"] = self.params
        if self.delay_s:
            d["delay_s"] = self.delay_s
        if self.children:
            d["children"] = [c.to_dict() for c in self.children]
        return d


@dataclass
class Scenario:
    """Scénario domotique complet."""
    name: str
    description: str = ""
    steps: list[ScenarioStep] = field(default_factory=list)
    builtin: bool = False
    last_run: float = 0.0
    run_count: int = 0

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "steps": [s.to_dict() for s in self.steps],
            "builtin": self.builtin,
            "last_run": self.last_run,
            "run_count": self.run_count,
        }


# Type pour la fonction d'exécution de commandes
CommandExecutor = Callable[[str, str, dict], Awaitable[dict]]
# async fn(device_id, command, params) -> result


class ScenarioManager:
    """Moteur de scénarios domotiques."""

    def __init__(self):
        self._scenarios: dict[str, Scenario] = {}
        self._executor: CommandExecutor | None = None
        self._state_fn: Callable[[str], Awaitable[dict | None]] | None = None
        self._running_scenarios: set[str] = set()
        self._init_builtins()

    def set_executor(self, fn: CommandExecutor) -> None:
        """Définir la fonction d'exécution de commandes."""
        self._executor = fn

    def set_state_function(self, fn: Callable[[str], Awaitable[dict | None]]) -> None:
        """Définir la fonction de lecture d'état."""
        self._state_fn = fn

    # ── Built-in scenarios ────────────────────────────

    def _init_builtins(self) -> None:
        """Créer les scénarios prédéfinis."""
        self._scenarios["cinema"] = Scenario(
            name="cinema",
            description="Mode cinéma : lumières tamisées, TV allumée",
            builtin=True,
            steps=[
                ScenarioStep(type=StepType.PARALLEL, children=[
                    ScenarioStep(type=StepType.ACTION, target="*light*",
                                 command="set_brightness", params={"value": 10}),
                    ScenarioStep(type=StepType.ACTION, target="*tv*",
                                 command="turn_on"),
                ]),
            ],
        )

        self._scenarios["nuit"] = Scenario(
            name="nuit",
            description="Mode nuit : tout éteindre sauf veilleuses",
            builtin=True,
            steps=[
                ScenarioStep(type=StepType.ACTION, target="*light*",
                             command="turn_off"),
                ScenarioStep(type=StepType.ACTION, target="*tv*",
                             command="turn_off"),
                ScenarioStep(type=StepType.ACTION, target="*heater*",
                             command="set_mode", params={"value": "eco"}),
            ],
        )

        self._scenarios["absence"] = Scenario(
            name="absence",
            description="Mode absence : tout éteindre, éco, sécurité",
            builtin=True,
            steps=[
                ScenarioStep(type=StepType.ACTION, target="*light*",
                             command="turn_off"),
                ScenarioStep(type=StepType.ACTION, target="*tv*",
                             command="turn_off"),
                ScenarioStep(type=StepType.ACTION, target="*heater*",
                             command="set_mode", params={"value": "anti_freeze"}),
            ],
        )

        self._scenarios["reveil"] = Scenario(
            name="reveil",
            description="Mode réveil : lumières progressives, chauffage confort",
            builtin=True,
            steps=[
                ScenarioStep(type=StepType.ACTION, target="*heater*",
                             command="set_mode", params={"value": "comfort"}),
                ScenarioStep(type=StepType.ACTION, target="*light*",
                             command="set_brightness", params={"value": 30}),
                ScenarioStep(type=StepType.WAIT, delay_s=5.0),
                ScenarioStep(type=StepType.ACTION, target="*light*",
                             command="set_brightness", params={"value": 70}),
                ScenarioStep(type=StepType.WAIT, delay_s=5.0),
                ScenarioStep(type=StepType.ACTION, target="*light*",
                             command="set_brightness", params={"value": 100}),
            ],
        )

        self._scenarios["securite"] = Scenario(
            name="securite",
            description="Mode sécurité : caméras actives, lumières extérieures ON",
            builtin=True,
            steps=[
                ScenarioStep(type=StepType.ACTION, target="*camera*",
                             command="turn_on"),
                ScenarioStep(type=StepType.ACTION, target="*light*",
                             command="turn_on"),
            ],
        )

        self._scenarios["eco"] = Scenario(
            name="eco",
            description="Mode économie d'énergie : éco partout",
            builtin=True,
            steps=[
                ScenarioStep(type=StepType.ACTION, target="*heater*",
                             command="set_mode", params={"value": "eco"}),
                ScenarioStep(type=StepType.ACTION, target="*light*",
                             command="set_brightness", params={"value": 50}),
            ],
        )

    # ── API ───────────────────────────────────────────

    def list_scenarios(self) -> list[dict]:
        return [s.to_dict() for s in self._scenarios.values()]

    def get_scenario(self, name: str) -> dict | None:
        s = self._scenarios.get(name)
        return s.to_dict() if s else None

    def add_scenario(self, name: str, steps: list[dict],
                     description: str = "") -> dict:
        """Ajouter un scénario personnalisé."""
        parsed_steps = [self._parse_step(s) for s in steps]
        scenario = Scenario(
            name=name,
            description=description,
            steps=parsed_steps,
            builtin=False,
        )
        self._scenarios[name] = scenario
        return scenario.to_dict()

    def remove_scenario(self, name: str) -> bool:
        """Supprimer un scénario (sauf built-ins)."""
        s = self._scenarios.get(name)
        if not s:
            return False
        if s.builtin:
            return False
        del self._scenarios[name]
        return True

    async def run_scenario(self, name: str,
                           devices: list[dict] | None = None) -> dict:
        """Exécuter un scénario.

        devices: liste de devices du HomeGraph pour résoudre les wildcards.
        """
        scenario = self._scenarios.get(name)
        if not scenario:
            return {"ok": False, "error": f"Scenario not found: {name}"}

        if name in self._running_scenarios:
            return {"ok": False, "error": f"Scenario already running: {name}"}

        self._running_scenarios.add(name)
        results: list[dict] = []
        errors: list[str] = []

        try:
            for step in scenario.steps:
                step_result = await self._execute_step(step, devices or [])
                results.append(step_result)
                if not step_result.get("ok", True):
                    errors.append(step_result.get("error", "unknown"))

            scenario.last_run = time.time()
            scenario.run_count += 1

        finally:
            self._running_scenarios.discard(name)

        return {
            "ok": len(errors) == 0,
            "scenario": name,
            "steps_executed": len(results),
            "results": results,
            "errors": errors if errors else None,
        }

    # ── Step execution ────────────────────────────────

    async def _execute_step(self, step: ScenarioStep,
                            devices: list[dict]) -> dict:
        if step.type == StepType.WAIT:
            await asyncio.sleep(step.delay_s)
            return {"ok": True, "type": "wait", "delay_s": step.delay_s}

        if step.type == StepType.CONDITION:
            return await self._check_condition(step, devices)

        if step.type == StepType.PARALLEL:
            tasks = [self._execute_step(child, devices)
                     for child in step.children]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            return {
                "ok": all(
                    r.get("ok", False) if isinstance(r, dict) else False
                    for r in results
                ),
                "type": "parallel",
                "results": [
                    r if isinstance(r, dict) else {"ok": False, "error": str(r)}
                    for r in results
                ],
            }

        if step.type == StepType.ACTION:
            return await self._execute_action(step, devices)

        return {"ok": False, "error": f"Unknown step type: {step.type}"}

    async def _execute_action(self, step: ScenarioStep,
                              devices: list[dict]) -> dict:
        """Exécuter une action, en résolvant les wildcards de target."""
        if not self._executor:
            return {"ok": False, "error": "Aucun exécuteur configuré"}

        target = step.target
        # Resolve wildcard targets
        matched_ids = self._resolve_target(target, devices)

        if not matched_ids:
            return {"ok": True, "type": "action", "target": target,
                    "matched": 0, "note": "No matching devices"}

        results = []
        for device_id in matched_ids:
            try:
                r = await self._executor(device_id, step.command, step.params)
                results.append(r)
            except Exception as e:
                log.error("Scenario step executor error: %s", e)
                results.append({"ok": False, "error": "Erreur lors de l'exécution de l'action"})

        return {
            "ok": all(r.get("ok", False) for r in results),
            "type": "action",
            "target": target,
            "matched": len(matched_ids),
            "results": results,
        }

    async def _check_condition(self, step: ScenarioStep,
                               devices: list[dict]) -> dict:
        """Vérifier une condition avant de continuer."""
        if not self._state_fn:
            return {"ok": True, "type": "condition", "note": "No state_fn"}
        state = await self._state_fn(step.target)
        if state is None:
            return {"ok": False, "type": "condition", "error": "Appareil introuvable"}
        # Simple check: all params keys must match state
        ok = all(state.get(k) == v for k, v in step.params.items())
        return {"ok": ok, "type": "condition", "target": step.target}

    def _resolve_target(self, target: str, devices: list[dict]) -> list[str]:
        """Résoudre wildcards dans le target.

        "*light*" → tous les devices de type light
        "hue_abc123" → device exact
        """
        if "*" in target:
            # Extract type pattern between *...*
            pattern = target.strip("*").lower()
            return [
                d.get("id_exo", "")
                for d in devices
                if pattern in d.get("type", "").lower()
                or pattern in d.get("name", "").lower()
            ]
        return [target]

    def _parse_step(self, raw: dict) -> ScenarioStep:
        """Parse un step dict en ScenarioStep."""
        stype = StepType(raw.get("type", "action"))
        children = []
        if "children" in raw:
            children = [self._parse_step(c) for c in raw["children"]]
        return ScenarioStep(
            type=stype,
            target=raw.get("target", ""),
            command=raw.get("command", ""),
            params=raw.get("params", {}),
            delay_s=raw.get("delay_s", 0.0),
            children=children,
        )

    def save_to_file(self, path: str) -> None:
        """Sauvegarder les scénarios personnalisés."""
        custom = {
            name: s.to_dict()
            for name, s in self._scenarios.items()
            if not s.builtin
        }
        Path(path).write_text(json.dumps(custom, indent=2, ensure_ascii=False),
                              encoding="utf-8")

    def load_from_file(self, path: str) -> int:
        """Charger des scénarios personnalisés."""
        p = Path(path)
        if not p.exists():
            return 0
        data = json.loads(p.read_text(encoding="utf-8"))
        count = 0
        for name, raw in data.items():
            steps = [self._parse_step(s) for s in raw.get("steps", [])]
            self._scenarios[name] = Scenario(
                name=name,
                description=raw.get("description", ""),
                steps=steps,
                builtin=False,
            )
            count += 1
        return count
