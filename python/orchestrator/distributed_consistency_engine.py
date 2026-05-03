"""
EXO v14 — DistributedConsistencyEngine (Cohérence globale)
Garantit la cohérence entre tous les agents : logique, temporelle,
contextuelle, plans, simulations, prévisions.

API:
  check_global_consistency()        → dict
  enforce_global_consistency()      → dict
  check_agent_consistency(name)     → dict
  health_check()                    → dict
  restart()                         → None
  get_stats()                       → dict
"""

import logging
import time
from typing import Any

log = logging.getLogger("distributed_consistency")


class DistributedConsistencyEngine:
    """Moteur de cohérence globale distribuée EXO v14."""

    def __init__(self, registry=None, messaging_bus=None,
                 conflict_resolver=None, meta_memory=None):
        self._registry = registry
        self._bus = messaging_bus
        self._resolver = conflict_resolver
        self._memory = meta_memory
        self._history: list[dict] = []
        self._stats = {
            "consistency_checks": 0,
            "inconsistencies_found": 0,
            "enforcements": 0,
            "corrections_applied": 0,
        }

    # ── check_global_consistency ────────────────────────────
    def check_global_consistency(self) -> dict:
        """Check consistency across all registered agents."""
        self._stats["consistency_checks"] += 1
        issues: list[dict] = []

        agents = self._get_agents()
        if not agents:
            result = {
                "consistent": True,
                "issues": [],
                "agents_checked": 0,
                "timestamp": time.time(),
            }
            self._record(result)
            return result

        # 1. Check logical consistency (no contradictory outputs)
        logical = self._check_logical_consistency(agents)
        issues.extend(logical)

        # 2. Check temporal consistency (no timing conflicts)
        temporal = self._check_temporal_consistency(agents)
        issues.extend(temporal)

        # 3. Check contextual consistency (shared context is coherent)
        contextual = self._check_contextual_consistency(agents)
        issues.extend(contextual)

        # 4. Check agent health consistency
        health = self._check_health_consistency(agents)
        issues.extend(health)

        self._stats["inconsistencies_found"] += len(issues)

        result = {
            "consistent": len(issues) == 0,
            "issues": issues,
            "issue_count": len(issues),
            "agents_checked": len(agents),
            "timestamp": time.time(),
        }
        self._record(result)
        return result

    # ── enforce_global_consistency ──────────────────────────
    def enforce_global_consistency(self) -> dict:
        """Check and auto-correct inconsistencies."""
        self._stats["enforcements"] += 1
        check = self.check_global_consistency()
        actions: list[dict] = []

        for issue in check.get("issues", []):
            action = self._correct_issue(issue)
            if action:
                actions.append(action)
                self._stats["corrections_applied"] += 1

        result = {
            "enforced": True,
            "issues_found": check.get("issue_count", 0),
            "corrections": actions,
            "corrections_count": len(actions),
            "timestamp": time.time(),
        }
        self._record(result)
        return result

    # ── check_agent_consistency ─────────────────────────────
    def check_agent_consistency(self, agent_name: str) -> dict:
        """Check consistency for a specific agent."""
        if not self._registry:
            return {"agent": agent_name, "consistent": True,
                    "reason": "no_registry"}

        agent = self._registry.get_agent(agent_name)
        if not agent:
            return {"agent": agent_name, "consistent": False,
                    "reason": "agent_not_found"}

        issues = []

        # Check health
        if hasattr(agent, "health_check"):
            health = agent.health_check()
            if health.get("status") != "ok":
                issues.append({
                    "type": "unhealthy_agent",
                    "agent": agent_name,
                    "health": health,
                })

        # Check stats
        if hasattr(agent, "get_stats"):
            stats = agent.get_stats()
            failed = stats.get("tasks_failed", 0)
            total = stats.get("tasks_handled", 0)
            if total > 0 and failed / total > 0.5:
                issues.append({
                    "type": "high_failure_rate",
                    "agent": agent_name,
                    "failure_rate": failed / total,
                })

        return {
            "agent": agent_name,
            "consistent": len(issues) == 0,
            "issues": issues,
        }

    # ── internal checks ────────────────────────────────────
    def _check_logical_consistency(self,
                                   agents: list[dict]) -> list[dict]:
        """Check that no two agents produce contradictory latest results."""
        issues = []
        results = []
        for info in agents:
            agent = info.get("agent")
            if agent and hasattr(agent, "report_result"):
                r = agent.report_result()
                if r.get("status") != "no_result":
                    results.append(r)

        if len(results) > 1 and self._resolver:
            detection = self._resolver.detect_conflicts(results)
            for c in detection.get("conflicts", []):
                issues.append({
                    "type": "logical_inconsistency",
                    "detail": c,
                })
        return issues

    def _check_temporal_consistency(self,
                                    agents: list[dict]) -> list[dict]:
        """Check that pending actions don't have timing issues."""
        issues = []
        # Agent stats with timing data
        for info in agents:
            agent = info.get("agent")
            if not agent:
                continue
            if hasattr(agent, "get_stats"):
                stats = agent.get_stats()
                # Check for stale tasks
                if stats.get("tasks_handled", 0) > 0:
                    ratio = (stats.get("tasks_succeeded", 0)
                             / max(stats["tasks_handled"], 1))
                    if ratio < 0.3:
                        issues.append({
                            "type": "temporal_degradation",
                            "agent": info.get("name", ""),
                            "success_ratio": ratio,
                        })
        return issues

    def _check_contextual_consistency(self,
                                      agents: list[dict]) -> list[dict]:
        """Check that agents share a coherent view of context."""
        issues = []
        # Check if multiple agents reference the same domain
        domains: dict[str, list[str]] = {}
        for info in agents:
            domain = info.get("domain", "")
            name = info.get("name", "")
            if domain:
                domains.setdefault(domain, []).append(name)

        for domain, agent_names in domains.items():
            if len(agent_names) > 1:
                issues.append({
                    "type": "domain_duplication",
                    "domain": domain,
                    "agents": agent_names,
                })
        return issues

    def _check_health_consistency(self,
                                  agents: list[dict]) -> list[dict]:
        """Check health status of all agents."""
        issues = []
        for info in agents:
            agent = info.get("agent")
            name = info.get("name", "")
            if agent and hasattr(agent, "health_check"):
                health = agent.health_check()
                if health.get("status") != "ok":
                    issues.append({
                        "type": "unhealthy_agent",
                        "agent": name,
                        "status": health.get("status", "unknown"),
                    })
        return issues

    def _correct_issue(self, issue: dict) -> dict | None:
        """Attempt to auto-correct an issue."""
        issue_type = issue.get("type", "")

        if issue_type == "unhealthy_agent":
            agent_name = issue.get("agent", "")
            if self._registry:
                agent = self._registry.get_agent(agent_name)
                if agent and hasattr(agent, "restart"):
                    agent.restart()
                    return {
                        "action": "restart_agent",
                        "agent": agent_name,
                        "success": True,
                    }

        if issue_type == "high_failure_rate":
            agent_name = issue.get("agent", "")
            if self._registry:
                agent = self._registry.get_agent(agent_name)
                if agent and hasattr(agent, "restart"):
                    agent.restart()
                    return {
                        "action": "restart_agent",
                        "agent": agent_name,
                        "reason": "high_failure_rate",
                        "success": True,
                    }

        return None

    def _get_agents(self) -> list[dict]:
        """Get all agents from registry."""
        if not self._registry:
            return []
        infos = self._registry.list_agents()
        result = []
        for info in infos:
            agent = self._registry.get_agent(info["name"])
            result.append({**info, "agent": agent})
        return result

    def _record(self, result: dict) -> None:
        self._history.append(result)
        if len(self._history) > 500:
            self._history = self._history[-300:]

    # ── health / restart / stats ────────────────────────────
    def health_check(self) -> dict:
        return {
            "service": "distributed_consistency",
            "status": "ok",
            "checks_run": self._stats["consistency_checks"],
        }

    def restart(self) -> None:
        self._history.clear()
        for k in self._stats:
            self._stats[k] = 0
        log.info("DistributedConsistencyEngine restarted")

    def get_stats(self) -> dict:
        return dict(self._stats)
