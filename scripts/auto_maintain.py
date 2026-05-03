#!/usr/bin/env python3
"""
EXO Auto-Maintain — Maintenance automatique du projet EXO.

Usage:
    python scripts/auto_maintain.py scan      # Fichiers modifiés (git diff)
    python scripts/auto_maintain.py docs      # Régénère la documentation auto
    python scripts/auto_maintain.py clean     # Supprime les fichiers orphelins
    python scripts/auto_maintain.py context   # Met à jour .exo_context/context.md
    python scripts/auto_maintain.py check     # Vérifie conventions + dépendances
    python scripts/auto_maintain.py all       # Exécute tout dans l'ordre
"""
from __future__ import annotations

import argparse
import datetime
import os
import re
import subprocess
import sys
from pathlib import Path

# ── Racine du projet ────────────────────────────────────────────
ROOT = Path(__file__).resolve().parent.parent
LOGS_DIR = ROOT / "logs"
DOCS_DIR = ROOT / "docs"
APP_DIR = ROOT / "app"
PYTHON_DIR = ROOT / "python"
TESTS_DIR = ROOT / "tests"
CONTEXT_DIR = ROOT / ".exo_context"

# ── ANSI couleurs (Windows ≥10 supporte via VT100) ─────────────
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
CYAN = "\033[96m"
BOLD = "\033[1m"
RESET = "\033[0m"

# ── Constantes services EXO ────────────────────────────────────
SERVICES = {
    "exo_server":    {"port": 8765, "lang": "Python", "proto": "WebSocket", "dir": "python/orchestrator"},
    "stt_server":    {"port": 8766, "lang": "Python", "proto": "WebSocket", "dir": "python/stt"},
    "tts_server":    {"port": 8767, "lang": "Python", "proto": "WebSocket", "dir": "python/tts"},
    "vad_server":    {"port": 8768, "lang": "Python", "proto": "WebSocket", "dir": "python/vad"},
    "wakeword_server": {"port": 8770, "lang": "Python", "proto": "WebSocket", "dir": "python/wakeword"},
    "memory_server": {"port": 8771, "lang": "Python", "proto": "WebSocket", "dir": "python/memory"},
    "nlu_server":    {"port": 8772, "lang": "Python", "proto": "WebSocket", "dir": "python/nlu"},
}

# ── Logging ─────────────────────────────────────────────────────
_log_lines: list[str] = []
_verbose = False
_dry_run = False
_json_output = False


def log(msg: str, level: str = "INFO") -> None:
    ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    raw = f"[{ts}] [{level}] {msg}"
    _log_lines.append(raw)
    if _json_output:
        return
    colour = {
        "INFO": GREEN, "WARN": YELLOW, "ERROR": RED, "SECTION": CYAN
    }.get(level, "")
    prefix = f"{BOLD}{colour}" if level == "SECTION" else colour
    print(f"{prefix}{raw}{RESET}")


def flush_log() -> None:
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    log_file = LOGS_DIR / "maintenance.log"
    with open(log_file, "a", encoding="utf-8") as f:
        f.write("\n".join(_log_lines) + "\n")
    log(f"Rapport écrit dans {log_file.relative_to(ROOT)}")


# ════════════════════════════════════════════════════════════════
#  1) SCAN — fichiers modifiés
# ════════════════════════════════════════════════════════════════
def git_modified_files() -> list[str]:
    """Retourne les fichiers modifiés par rapport à HEAD (staged + unstaged)."""
    try:
        out = subprocess.check_output(
            ["git", "diff", "--name-only", "HEAD"],
            cwd=str(ROOT), text=True, stderr=subprocess.DEVNULL
        )
        staged = subprocess.check_output(
            ["git", "diff", "--name-only", "--cached"],
            cwd=str(ROOT), text=True, stderr=subprocess.DEVNULL
        )
        files = set(out.strip().splitlines() + staged.strip().splitlines())
        return sorted(f for f in files if f)
    except (subprocess.CalledProcessError, FileNotFoundError):
        log("git non disponible — scan de tous les fichiers", "WARN")
        return []


def cmd_scan() -> int:
    log("═══ SCAN — Fichiers modifiés ═══", "SECTION")
    files = git_modified_files()
    if not files:
        log("Aucun fichier modifié détecté.")
        return 0

    cpp_files = [f for f in files if f.endswith((".cpp", ".h"))]
    py_files = [f for f in files if f.endswith(".py")]
    other = [f for f in files if f not in cpp_files and f not in py_files]

    log(f"Total: {len(files)} fichier(s) modifié(s)")
    if cpp_files:
        log(f"  C++ : {len(cpp_files)} — {', '.join(cpp_files[:5])}")
    if py_files:
        log(f"  Python : {len(py_files)} — {', '.join(py_files[:5])}")
    if other:
        log(f"  Autres : {len(other)} — {', '.join(other[:5])}")
    return 0


# ════════════════════════════════════════════════════════════════
#  2) DOCS — Génération documentation automatique
# ════════════════════════════════════════════════════════════════

def _scan_cpp_includes() -> dict[str, list[str]]:
    """Scan tous les .cpp/.h dans app/ et retourne {fichier: [includes locaux]}."""
    deps: dict[str, list[str]] = {}
    include_re = re.compile(r'#include\s+"([^"]+)"')
    for ext in ("*.cpp", "*.h"):
        for path in APP_DIR.rglob(ext):
            rel = str(path.relative_to(ROOT)).replace("\\", "/")
            includes = []
            try:
                text = path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            for m in include_re.finditer(text):
                inc = m.group(1)
                # Résoudre le chemin relatif
                resolved = path.parent / inc
                if resolved.exists():
                    includes.append(str(resolved.relative_to(ROOT)).replace("\\", "/"))
                else:
                    includes.append(inc)
            deps[rel] = includes
    return deps


def _scan_cpp_classes() -> list[dict[str, str]]:
    """Extrait les classes C++ (nom, fichier header, module)."""
    class_re = re.compile(r"class\s+(?:Q_\w+\s+)?(\w+)\s*(?::\s*public\s+[\w:]+)?")
    classes = []
    for header in APP_DIR.rglob("*.h"):
        rel = str(header.relative_to(ROOT)).replace("\\", "/")
        module = rel.split("/")[1] if "/" in rel else "root"
        try:
            text = header.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for m in class_re.finditer(text):
            name = m.group(1)
            # Filtrer les forward-declarations (ligne se terminant par ;)
            line = text[m.start():text.find("\n", m.start())]
            if line.rstrip().endswith(";"):
                continue
            classes.append({"name": name, "header": rel, "module": module})
    return classes


def _scan_python_modules() -> list[dict[str, str]]:
    """Retourne les modules Python dans python/."""
    modules = []
    if not PYTHON_DIR.exists():
        return modules
    for child in sorted(PYTHON_DIR.iterdir()):
        if child.is_dir() and not child.name.startswith(("_", ".")):
            py_files = list(child.rglob("*.py"))
            main_file = ""
            for pf in py_files:
                if pf.name.endswith("_server.py") or pf.name == "exo_server.py":
                    main_file = str(pf.relative_to(ROOT)).replace("\\", "/")
                    break
            modules.append({
                "name": child.name,
                "path": str(child.relative_to(ROOT)).replace("\\", "/"),
                "files": len(py_files),
                "main": main_file,
            })
    return modules


def _scan_pipeline_states() -> list[str]:
    """Extrait les EventType depuis pipelinetypes.h."""
    header = APP_DIR / "core" / "pipelinetypes.h"
    if not header.exists():
        return []
    text = header.read_text(encoding="utf-8", errors="replace")
    return re.findall(r"^\s+(\w+),?\s*//", text, re.MULTILINE)


def _scan_test_files() -> dict[str, list[str]]:
    """Retourne {catégorie: [fichiers test]}."""
    result: dict[str, list[str]] = {}
    for sub in ("cpp", "python", "integration", "performance"):
        d = TESTS_DIR / sub
        if d.exists():
            files = sorted(
                str(f.relative_to(ROOT)).replace("\\", "/")
                for f in d.rglob("test_*")
                if f.suffix in (".py", ".cpp")
            )
            if files:
                result[sub] = files
    return result


def generate_graph_md() -> str:
    """Génère docs/architecture/graph.md — graphe de dépendances C++."""
    deps = _scan_cpp_includes()
    lines = [
        "# Graphe de dépendances C++",
        "",
        f"> Auto-généré par `auto_maintain.py` — {datetime.date.today()}",
        "",
        "## Matrice d'inclusion",
        "",
        "```",
    ]
    for src, includes in sorted(deps.items()):
        if includes:
            short_src = src.split("/")[-1]
            for inc in includes:
                short_inc = inc.split("/")[-1]
                lines.append(f"  {short_src} -> {short_inc}")
    lines.append("```")
    lines.append("")

    # Par module
    modules: dict[str, list[str]] = {}
    for src in sorted(deps):
        parts = src.split("/")
        mod = parts[1] if len(parts) > 2 else "root"
        modules.setdefault(mod, []).append(src)

    lines.append("## Fichiers par module")
    lines.append("")
    for mod, files in sorted(modules.items()):
        lines.append(f"### {mod}/")
        lines.append("")
        for f in files:
            inc_count = len(deps.get(f, []))
            lines.append(f"- `{f}` ({inc_count} include(s))")
        lines.append("")
    return "\n".join(lines)


def generate_modules_md() -> str:
    """Génère docs/modules.md — index des modules Python + classes C++."""
    py_mods = _scan_python_modules()
    cpp_classes = _scan_cpp_classes()

    lines = [
        "# Index des modules EXO",
        "",
        f"> Auto-généré par `auto_maintain.py` — {datetime.date.today()}",
        "",
        "## Modules Python",
        "",
        "| Module | Dossier | Fichiers | Point d'entrée |",
        "|--------|---------|----------|----------------|",
    ]
    for m in py_mods:
        lines.append(f"| {m['name']} | `{m['path']}` | {m['files']} | `{m['main']}` |")

    lines.extend(["", "## Classes C++", "",
                   "| Classe | Header | Module |",
                   "|--------|--------|--------|"])
    for c in cpp_classes:
        lines.append(f"| `{c['name']}` | `{c['header']}` | {c['module']} |")
    lines.append("")
    return "\n".join(lines)


def generate_pipeline_md() -> str:
    """Génère docs/pipeline.md — synoptique pipeline avec les EventTypes."""
    states = _scan_pipeline_states()

    lines = [
        "# Pipeline EXO — Événements",
        "",
        f"> Auto-généré par `auto_maintain.py` — {datetime.date.today()}",
        "",
        "## Flux audio",
        "",
        "```",
        "Microphone ─→ VAD ─→ WakeWord ─→ STT ─→ NLU/Claude ─→ TTS ─→ Speaker",
        "```",
        "",
        "## EventTypes (pipelinetypes.h)",
        "",
        "| # | EventType | Catégorie |",
        "|---|-----------|-----------|",
    ]

    categories = {
        "Speech": "VAD", "WakeWord": "WakeWord", "Stream": "STT",
        "Partial": "STT", "Final": "STT/LLM", "Utterance": "STT",
        "STTError": "STT", "Request": "LLM", "First": "LLM",
        "Reply": "LLM", "Sentence": "LLM/TTS", "Tool": "LLM",
        "Network": "LLM", "Response": "LLM", "Synthesis": "TTS",
        "Speak": "TTS", "Worker": "TTS", "Pcm": "Audio",
        "Playback": "Audio", "TTSError": "TTS", "Transcript": "Orchestrator",
        "State": "Orchestrator", "Orphan": "Orchestrator",
    }

    for i, state in enumerate(states, 1):
        cat = "—"
        for prefix, c in categories.items():
            if state.startswith(prefix):
                cat = c
                break
        lines.append(f"| {i} | `{state}` | {cat} |")
    lines.append("")
    return "\n".join(lines)


def generate_services_md() -> str:
    """Génère docs/services.md — table des microservices."""
    lines = [
        "# Services EXO",
        "",
        f"> Auto-généré par `auto_maintain.py` — {datetime.date.today()}",
        "",
        "## Microservices",
        "",
        "| Service | Port | Langage | Protocole | Dossier |",
        "|---------|------|---------|-----------|---------|",
    ]
    for name, info in SERVICES.items():
        lines.append(
            f"| {name} | {info['port']} | {info['lang']} | "
            f"{info['proto']} | `{info['dir']}` |"
        )

    # Tests disponibles
    test_map = _scan_test_files()
    lines.extend(["", "## Tests disponibles", ""])
    total = 0
    for cat, files in sorted(test_map.items()):
        lines.append(f"### {cat}/ ({len(files)} fichier(s))")
        lines.append("")
        for f in files:
            lines.append(f"- `{f}`")
        lines.append("")
        total += len(files)
    lines.append(f"**Total : {total} fichier(s) de test**")
    lines.append("")
    return "\n".join(lines)


def cmd_docs() -> int:
    log("═══ DOCS — Génération documentation ═══", "SECTION")
    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    (DOCS_DIR / "architecture").mkdir(parents=True, exist_ok=True)

    generated = [
        (DOCS_DIR / "architecture" / "graph.md", generate_graph_md),
        (DOCS_DIR / "modules.md", generate_modules_md),
        (DOCS_DIR / "pipeline.md", generate_pipeline_md),
        (DOCS_DIR / "services.md", generate_services_md),
    ]

    for path, gen_fn in generated:
        content = gen_fn()
        rel = path.relative_to(ROOT)
        if _dry_run:
            log(f"  [dry-run] écrirait {rel}  ({len(content)} octets)")
        else:
            path.write_text(content, encoding="utf-8")
            log(f"  ✓ {rel}  ({len(content)} octets)")

    log(f"Documentation régénérée : {len(generated)} fichier(s)")
    return 0


# ════════════════════════════════════════════════════════════════
#  3) CLEAN — Suppression des fichiers orphelins
# ════════════════════════════════════════════════════════════════
CLEAN_PATTERNS = [
    "**/__pycache__",
    "**/*.pyc",
    "**/.pytest_cache",
    "**/.mypy_cache",
    "**/*.tmp",
    "**/*.bak",
]

CLEAN_EXCLUDE = {
    ".venv", ".venv_stt_tts", "node_modules", ".git",
    "build", "whisper.cpp", "rtaudio", "third_party", "models",
}


def cmd_clean() -> int:
    log("═══ CLEAN — Nettoyage fichiers orphelins ═══", "SECTION")
    removed = 0
    for pattern in CLEAN_PATTERNS:
        for path in ROOT.glob(pattern):
            # Ignorer les dossiers exclus
            parts = path.relative_to(ROOT).parts
            if any(p in CLEAN_EXCLUDE for p in parts):
                continue
            rel = path.relative_to(ROOT)
            if path.is_dir():
                if _dry_run:
                    log(f"  [dry-run] supprimerait {rel}/")
                else:
                    import shutil
                    shutil.rmtree(path, ignore_errors=True)
                    log(f"  🗑  {rel}/")
                removed += 1
            elif path.is_file():
                if _dry_run:
                    log(f"  [dry-run] supprimerait {rel}")
                else:
                    path.unlink(missing_ok=True)
                    log(f"  🗑  {rel}")
                removed += 1
    if removed == 0:
        log("  Rien à nettoyer.")
    else:
        prefix = "[dry-run] " if _dry_run else ""
        log(f"  {prefix}Supprimé : {removed} élément(s)")
    return 0


# ════════════════════════════════════════════════════════════════
#  4) CONTEXT — Mise à jour .exo_context/context.md
# ════════════════════════════════════════════════════════════════
def generate_context_md() -> str:
    """Génère le fichier context.md pour Copilot."""
    py_mods = _scan_python_modules()
    cpp_classes = _scan_cpp_classes()
    states = _scan_pipeline_states()
    test_files = _scan_test_files()
    total_tests = sum(len(v) for v in test_files.values())

    lines = [
        "# EXO — Contexte Projet (auto-généré)",
        "",
        f"> Dernière mise à jour : {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}",
        "",
        "## 1. Vue d'ensemble",
        "",
        "EXO est un assistant vocal intelligent composé de :",
        "- **Client C++ / Qt 6.9.3** (MSVC 2022, C++17) — GUI QML + pipeline audio",
        "- **7 microservices Python** (WebSocket) — STT, TTS, VAD, WakeWord, NLU, Memory, Orchestrator",
        "- **Claude API** (Anthropic) — LLM principal",
        "- **Home Assistant** — domotique",
        "- **React GUI** (Vite + Tailwind) — interface web",
        "",
        "## 2. Architecture des dossiers",
        "",
        "```",
        "EXO/",
        "├── app/              # C++ Qt (core, audio, llm, utils)",
        "├── python/           # Microservices Python",
        "│   ├── stt/          # Whisper.cpp Vulkan (port 8766)",
        "│   ├── tts/          # XTTS v2 (port 8767)",
        "│   ├── vad/          # Silero VAD (port 8768)",
        "│   ├── wakeword/     # OpenWakeWord (port 8770)",
        "│   ├── memory/       # FAISS (port 8771)",
        "│   ├── nlu/          # Intent classifier (port 8772)",
        "│   └── orchestrator/ # Backend + HA bridge (port 8765)",
        "├── gui/              # React 18 + Vite",
        "├── qml/              # Qt Quick UI (inactif)",
        "├── tests/            # cpp/ python/ integration/ performance/",
        "├── config/           # assistant.conf",
        "├── docs/             # Documentation technique",
        "├── scripts/          # Build, benchmark, maintenance",
        "└── resources/        # Fonts, icons",
        "```",
        "",
        "## 3. Services",
        "",
        "| Service | Port | Protocole |",
        "|---------|------|-----------|",
    ]
    for name, info in SERVICES.items():
        lines.append(f"| {name} | {info['port']} | {info['proto']} |")

    lines.extend(["", "## 4. Classes C++", "",
                   "| Classe | Module |",
                   "|--------|--------|"])
    for c in cpp_classes:
        lines.append(f"| `{c['name']}` | {c['module']} |")

    lines.extend(["", "## 5. Modules Python", "",
                   "| Module | Fichiers |",
                   "|--------|----------|"])
    for m in py_mods:
        lines.append(f"| {m['name']} | {m['files']} |")

    lines.extend([
        "",
        "## 6. Pipeline audio",
        "",
        "```",
        "Microphone → AudioPreprocessor → VAD → WakeWord → STT → NLU/Claude → TTS → DSP → Speaker",
        "```",
        "",
        f"**{len(states)} EventTypes** définis dans `pipelinetypes.h`",
        "",
        "## 7. Tests",
        "",
        f"**{total_tests} fichier(s) de test** :",
    ])
    for cat, files in sorted(test_files.items()):
        lines.append(f"- `tests/{cat}/` : {len(files)} fichier(s)")

    lines.extend([
        "",
        "## 8. Build",
        "",
        "```powershell",
        '# C++ (CMake + MSVC)',
        'cmake -B build -G "Visual Studio 17 2022" -DCMAKE_PREFIX_PATH="C:/Qt/6.9.3/msvc2022_64" -DBUILD_TESTS=ON',
        'cmake --build build --config Debug',
        'ctest --test-dir build -C Debug --output-on-failure',
        '# Python',
        '.venv\\Scripts\\python.exe -m pytest tests/ -v --tb=short',
        "```",
        "",
        "## 9. Conventions",
        "",
        "- **C++** : PascalCase (classes), camelCase (méthodes/variables), UPPER_CASE (constantes)",
        "- **Python** : snake_case (fonctions/variables), PascalCase (classes)",
        "- **Fichiers** : snake_case.py, PascalCase.cpp/.h (sauf main.cpp)",
        "- **Tests** : test_<module>.cpp/py, Test<Class> (classes de test)",
        "",
        "## 10. Dépendances clés",
        "",
        "- Qt 6.9.3 (Core, Quick, WebSockets, Multimedia, TextToSpeech)",
        "- MSVC 2022 / C++17",
        "- Python 3.13",
        "- Whisper.cpp (Vulkan GPU)",
        "- Coqui XTTS v2 (DirectML / CUDA)",
        "- Silero VAD, OpenWakeWord, FAISS, SentenceTransformers",
        "- Claude claude-sonnet-4-20250514 (Anthropic API)",
        "",
    ]
    )
    return "\n".join(lines)


def cmd_context() -> int:
    log("═══ CONTEXT — Mise à jour .exo_context/context.md ═══", "SECTION")
    CONTEXT_DIR.mkdir(parents=True, exist_ok=True)
    ctx_file = CONTEXT_DIR / "context.md"
    content = generate_context_md()
    rel = ctx_file.relative_to(ROOT)
    if _dry_run:
        log(f"  [dry-run] écrirait {rel}  ({len(content)} octets)")
    else:
        ctx_file.write_text(content, encoding="utf-8")
        log(f"  ✓ {rel}  ({len(content)} octets)")
    return 0


# ════════════════════════════════════════════════════════════════
#  5) CHECK — Vérification conventions + dépendances
# ════════════════════════════════════════════════════════════════

# Convention C++ : classes PascalCase
_CPP_CLASS_RE = re.compile(r"class\s+(?:Q_\w+\s+)?(\w+)\s*[:{]")
# Convention Python : fonctions snake_case
_PY_FUNC_RE = re.compile(r"^def\s+(\w+)\s*\(", re.MULTILINE)
_PY_CLASS_RE = re.compile(r"^class\s+(\w+)\s*[:(]", re.MULTILINE)


def _check_cpp_naming() -> list[str]:
    warnings = []
    for header in APP_DIR.rglob("*.h"):
        try:
            text = header.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        rel = str(header.relative_to(ROOT)).replace("\\", "/")
        for m in _CPP_CLASS_RE.finditer(text):
            name = m.group(1)
            if name[0].islower():
                warnings.append(f"{rel}: classe '{name}' devrait être PascalCase")
    return warnings


def _check_py_naming() -> list[str]:
    warnings = []
    for py_file in PYTHON_DIR.rglob("*.py"):
        try:
            text = py_file.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        rel = str(py_file.relative_to(ROOT)).replace("\\", "/")
        for m in _PY_CLASS_RE.finditer(text):
            name = m.group(1)
            if name[0].islower() and not name.startswith("_"):
                warnings.append(f"{rel}: classe '{name}' devrait être PascalCase")
        for m in _PY_FUNC_RE.finditer(text):
            name = m.group(1)
            if name.startswith("_"):
                continue
            if any(c.isupper() for c in name) and name != name.upper():
                # Autorise ALL_CAPS constantes-like
                if not re.match(r"^[a-z_][a-z0-9_]*$", name) and not re.match(r"^[A-Z_]+$", name):
                    warnings.append(f"{rel}: fonction '{name}' devrait être snake_case")
    return warnings


def _check_python_imports() -> list[str]:
    """Vérifie que les imports relatifs dans python/ sont résolubles."""
    warnings = []
    import_re = re.compile(r"^from\s+(\S+)\s+import|^import\s+(\S+)", re.MULTILINE)
    for py_file in PYTHON_DIR.rglob("*.py"):
        try:
            text = py_file.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        rel = str(py_file.relative_to(ROOT)).replace("\\", "/")
        for m in import_re.finditer(text):
            mod = m.group(1) or m.group(2)
            if mod.startswith("."):
                # Import relatif — vérifier que le fichier parent a un __init__.py
                pkg_dir = py_file.parent
                if not (pkg_dir / "__init__.py").exists():
                    warnings.append(f"{rel}: import relatif '{mod}' sans __init__.py dans {pkg_dir.name}/")
    return warnings


def _check_cpp_includes() -> list[str]:
    """Vérifie les includes C++ locaux non résolus."""
    warnings = []
    include_re = re.compile(r'#include\s+"([^"]+)"')
    for ext in ("*.cpp", "*.h"):
        for path in APP_DIR.rglob(ext):
            try:
                text = path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            rel = str(path.relative_to(ROOT)).replace("\\", "/")
            for m in include_re.finditer(text):
                inc = m.group(1)
                resolved = path.parent / inc
                if not resolved.exists():
                    # Chercher dans app/
                    alt = APP_DIR / inc
                    if not alt.exists():
                        warnings.append(f"{rel}: include manquant '{inc}'")
    return warnings


def cmd_check() -> int:
    log("═══ CHECK — Vérification conventions ═══", "SECTION")
    all_warnings: list[str] = []

    log("  Conventions C++...")
    all_warnings.extend(_check_cpp_naming())

    log("  Conventions Python...")
    all_warnings.extend(_check_py_naming())

    log("  Imports Python...")
    all_warnings.extend(_check_python_imports())

    log("  Includes C++...")
    all_warnings.extend(_check_cpp_includes())

    if all_warnings:
        for w in all_warnings:
            log(f"  ⚠ {w}", "WARN")
        log(f"  {len(all_warnings)} avertissement(s)")
        return 1
    else:
        log("  ✓ Aucun problème détecté")
        return 0


# ════════════════════════════════════════════════════════════════
#  ALL — Exécuter tout
# ════════════════════════════════════════════════════════════════
def cmd_all() -> int:
    log("═══ AUTO-MAINTAIN — Exécution complète ═══", "SECTION")
    log("")
    worst = 0
    for cmd_fn in (cmd_scan, cmd_docs, cmd_clean, cmd_context, cmd_check):
        ret = cmd_fn()
        worst = max(worst, ret)
        log("")
    flush_log()
    log(f"{'═' * 50}")
    log(f"  Maintenance terminée — code retour : {worst}")
    return worst


# ════════════════════════════════════════════════════════════════
#  CLI
# ════════════════════════════════════════════════════════════════
def main() -> int:
    # Activer VT100 sur Windows
    if sys.platform == "win32":
        os.system("")

    parser = argparse.ArgumentParser(
        description="EXO Auto-Maintain — Maintenance automatique du projet",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--dry-run", action="store_true",
                        help="Simuler sans modifier le disque")
    parser.add_argument("--verbose", action="store_true",
                        help="Afficher plus de détails")
    parser.add_argument("--json", action="store_true",
                        help="Sortie JSON machine-readable")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("scan", help="Scanner les fichiers modifiés")
    sub.add_parser("docs", help="Régénérer la documentation")
    sub.add_parser("clean", help="Nettoyer les fichiers orphelins")
    sub.add_parser("context", help="Mettre à jour .exo_context/context.md")
    sub.add_parser("check", help="Vérifier conventions et dépendances")
    sub.add_parser("all", help="Tout exécuter")

    args = parser.parse_args()

    global _dry_run, _verbose, _json_output
    _dry_run = args.dry_run
    _verbose = args.verbose
    _json_output = args.json

    commands = {
        "scan": cmd_scan,
        "docs": cmd_docs,
        "clean": cmd_clean,
        "context": cmd_context,
        "check": cmd_check,
        "all": cmd_all,
    }
    ret = commands[args.command]()
    if args.command != "all":
        flush_log()

    if _json_output:
        import json as json_mod
        print(json_mod.dumps({"command": args.command, "exit_code": ret,
                              "dry_run": _dry_run, "log": _log_lines}))

    return ret


if __name__ == "__main__":
    sys.exit(main())
