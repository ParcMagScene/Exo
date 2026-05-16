# MIGRATION — Refactor R0.1 — 2026-05-08

## Contexte
Audit de cohérence EXO : 14 fichiers `explainability_engine_v*.py` + 4 `meta_supervisor*.py`
+ 2 `meta_planner*.py` à la racine de `python/orchestrator/`. Approche B retenue
(équilibrée) : conservation du code historique sous `_archived/`, exposition d'une
**façade unifiée** dans le module parent. Aucun comportement modifié.

## Fichiers déménagés (10)

| Ancien chemin                                     | Nouveau chemin                                           | Façade unifiée            |
|---------------------------------------------------|----------------------------------------------------------|---------------------------|
| `orchestrator/meta_supervisor.py`                 | `orchestrator/_archived/meta_supervisor.py`              | `UnifiedMetaSupervisor`   |
| `orchestrator/meta_supervisor_v2.py`              | `orchestrator/_archived/meta_supervisor_v2.py`           | `UnifiedMetaSupervisor`   |
| `orchestrator/meta_supervisor_v3.py`              | `orchestrator/_archived/meta_supervisor_v3.py`           | `UnifiedMetaSupervisor`   |
| `orchestrator/meta_supervisor_v4.py`              | `orchestrator/_archived/meta_supervisor_v4.py`           | `UnifiedMetaSupervisor`   |
| `orchestrator/meta_planner.py`                    | `orchestrator/_archived/meta_planner.py`                 | `UnifiedMetaPlanner`      |
| `orchestrator/meta_planner_v2.py`                 | `orchestrator/_archived/meta_planner_v2.py`              | `UnifiedMetaPlanner`      |
| `orchestrator/explainability_engine_v2.py`        | `orchestrator/_archived/explainability_engine_v2.py`     | `ExplainabilityEngine`    |
| `orchestrator/explainability_engine_v3.py`        | `orchestrator/_archived/explainability_engine_v3.py`     | `ExplainabilityEngine`    |
| `orchestrator/explainability_engine_v4.py`        | `orchestrator/_archived/explainability_engine_v4.py`     | `ExplainabilityEngine`    |
| `orchestrator/explainability_engine_v6.py`        | `orchestrator/_archived/explainability_engine_v6.py`     | `ExplainabilityEngine`    |

`explainability_engine_v5.py` reste à la racine (base de la façade ; sera renommé
`explainability_engine.py` après stabilisation Phase 1).

## Façades unifiées

### `UnifiedMetaSupervisor` (`unified_meta_supervisor.py`)
Composition interne : v1 → v2 → v3 → v4. Expose toutes les méthodes publiques
des 4 versions (les surcharges sont déléguées à la version la plus haute qui
les définit).

### `UnifiedMetaPlanner` (`unified_meta_planner.py`)
Composition interne : v1 → v2. Mêmes principes.

### `ExplainabilityEngine` (`explainability_engine.py`)
Composition interne : v5 (base) + v2/v3/v4/v6 quand les collaborateurs sont
fournis. Méthodes uniques (explain_plan, explain_emergence, etc.) déléguées
directement. Conflits (`get_stats`, `health_check`, `restart`, `explain_future`)
résolus par agrégation : v5 prime, complété par les versions historiques.

## Politique
- Les fichiers `_archived/` ne doivent PAS être importés par du code applicatif
  nouveau. Ils sont réservés aux façades unifiées.
- Suppression définitive prévue après validation runtime étendue (≥ 2 sem.).
- Tests historiques (`tests/python/archive/`) déjà neutralisés, donc pas
  d'impact CI.
