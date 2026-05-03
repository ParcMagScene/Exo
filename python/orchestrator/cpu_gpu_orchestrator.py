"""
EXO v8.2 — Orchestration CPU/GPU

Gestion intelligente des ressources :
- Priorité de threads pour les tâches critiques (audio, LLM)
- Affinité CPU configurable pour éviter la contention
- Détection contention GPU (CUDA/Vulkan)
- Métriques d'utilisation CPU/mémoire

Windows uniquement (ctypes + psutil optionnel).
"""

from __future__ import annotations

import ctypes
import logging
import os
import sys
import threading
import time
from dataclasses import dataclass
from enum import IntEnum
from typing import Any, Optional

log = logging.getLogger("pipeline.cpu_gpu")


class ThreadPriority(IntEnum):
    """Niveaux de priorité Windows."""
    IDLE = -15
    LOWEST = -2
    BELOW_NORMAL = -1
    NORMAL = 0
    ABOVE_NORMAL = 1
    HIGHEST = 2
    TIME_CRITICAL = 15


# Priorités recommandées par composant
COMPONENT_PRIORITY: dict[str, ThreadPriority] = {
    "audio_capture": ThreadPriority.TIME_CRITICAL,
    "audio_playback": ThreadPriority.HIGHEST,
    "vad": ThreadPriority.ABOVE_NORMAL,
    "stt": ThreadPriority.ABOVE_NORMAL,
    "llm": ThreadPriority.NORMAL,
    "tts": ThreadPriority.ABOVE_NORMAL,
    "gui": ThreadPriority.BELOW_NORMAL,
    "cache": ThreadPriority.NORMAL,
    "profiler": ThreadPriority.LOWEST,
}


def set_thread_priority(priority: ThreadPriority) -> bool:
    """Configure la priorité du thread courant (Windows)."""
    if sys.platform != "win32":
        log.debug("set_thread_priority: non-Windows, ignoré")
        return False
    try:
        handle = ctypes.windll.kernel32.GetCurrentThread()
        result = ctypes.windll.kernel32.SetThreadPriority(handle, int(priority))
        if result:
            log.debug(f"Thread priority set to {priority.name} ({priority.value})")
        else:
            log.warning(f"SetThreadPriority failed (error {ctypes.GetLastError()})")
        return bool(result)
    except Exception as exc:
        log.warning(f"set_thread_priority erreur: {exc}")
        return False


def set_process_priority(high: bool = False) -> bool:
    """Configure la priorité du processus (Windows).

    Args:
        high: True pour ABOVE_NORMAL, False pour NORMAL.
    """
    if sys.platform != "win32":
        return False
    try:
        handle = ctypes.windll.kernel32.GetCurrentProcess()
        # ABOVE_NORMAL_PRIORITY_CLASS = 0x00008000
        # NORMAL_PRIORITY_CLASS = 0x00000020
        priority_class = 0x00008000 if high else 0x00000020
        result = ctypes.windll.kernel32.SetPriorityClass(handle, priority_class)
        label = "ABOVE_NORMAL" if high else "NORMAL"
        if result:
            log.info(f"Process priority set to {label}")
        return bool(result)
    except Exception as exc:
        log.warning(f"set_process_priority erreur: {exc}")
        return False


def set_cpu_affinity(cores: list[int]) -> bool:
    """Configure l'affinité CPU du processus (Windows).

    Args:
        cores: Liste des indices de cœurs CPU à utiliser.
    """
    if sys.platform != "win32" or not cores:
        return False
    try:
        mask = sum(1 << c for c in cores)
        handle = ctypes.windll.kernel32.GetCurrentProcess()
        result = ctypes.windll.kernel32.SetProcessAffinityMask(handle, mask)
        if result:
            log.info(f"CPU affinity set to cores {cores} (mask=0x{mask:X})")
        return bool(result)
    except Exception as exc:
        log.warning(f"set_cpu_affinity erreur: {exc}")
        return False


@dataclass
class ResourceSnapshot:
    """Instantané des ressources système."""
    timestamp: float
    cpu_percent: float
    memory_rss_mb: float
    thread_count: int
    gpu_available: bool
    gpu_memory_used_mb: float
    gpu_memory_total_mb: float


class CPUGPUOrchestrator:
    """Orchestrateur de ressources CPU/GPU pour le pipeline.

    - Applique les priorités de threads par composant
    - Monitore l'utilisation CPU/mémoire
    - Détecte la contention GPU
    """

    def __init__(self):
        self._snapshots: list[ResourceSnapshot] = []
        self._max_snapshots = 100
        self._component_threads: dict[str, int] = {}  # component → thread_id
        self._gpu_available = False
        self._monitoring = False
        self._monitor_task: Optional[asyncio.Task] = None

    def apply_component_priority(self, component: str) -> bool:
        """Applique la priorité recommandée pour un composant.

        Doit être appelé depuis le thread du composant concerné.
        """
        priority = COMPONENT_PRIORITY.get(component)
        if priority is None:
            log.debug(f"Pas de priorité définie pour '{component}'")
            return False
        self._component_threads[component] = threading.current_thread().ident or 0
        return set_thread_priority(priority)

    def init_process(self, high_priority: bool = True) -> None:
        """Initialise les paramètres process-level au démarrage."""
        set_process_priority(high_priority)
        cpu_count = os.cpu_count() or 4
        log.info(f"CPU cores disponibles: {cpu_count}")

    def probe_gpu(self) -> dict[str, Any]:
        """Détecte le GPU disponible (CUDA ou Vulkan)."""
        result: dict[str, Any] = {
            "cuda_available": False,
            "vulkan_available": False,
            "gpu_name": "",
            "gpu_memory_total_mb": 0,
        }

        # Tester CUDA via torch
        try:
            import torch
            if torch.cuda.is_available():
                result["cuda_available"] = True
                result["gpu_name"] = torch.cuda.get_device_name(0)
                mem = torch.cuda.get_device_properties(0).total_mem
                result["gpu_memory_total_mb"] = round(mem / 1024 / 1024, 0)
                self._gpu_available = True
        except ImportError:
            pass

        # Vulkan est détecté au niveau native (whisper.cpp)
        # On vérifie juste si whispercpp est configuré pour Vulkan
        if os.environ.get("EXO_WHISPERCPP_BIN"):
            result["vulkan_available"] = True

        log.info(f"GPU probe: {result}")
        return result

    def snapshot(self) -> ResourceSnapshot:
        """Prend un instantané des ressources courantes."""
        cpu_pct = 0.0
        mem_mb = 0.0
        thread_count = threading.active_count()
        gpu_used_mb = 0.0
        gpu_total_mb = 0.0

        try:
            import psutil
            proc = psutil.Process()
            cpu_pct = proc.cpu_percent(interval=0)
            mem_mb = proc.memory_info().rss / 1024 / 1024
        except ImportError:
            pass

        if self._gpu_available:
            try:
                import torch
                if torch.cuda.is_available():
                    gpu_used_mb = torch.cuda.memory_allocated(0) / 1024 / 1024
                    gpu_total_mb = torch.cuda.get_device_properties(0).total_mem / 1024 / 1024
            except Exception:
                pass

        snap = ResourceSnapshot(
            timestamp=time.monotonic(),
            cpu_percent=round(cpu_pct, 1),
            memory_rss_mb=round(mem_mb, 1),
            thread_count=thread_count,
            gpu_available=self._gpu_available,
            gpu_memory_used_mb=round(gpu_used_mb, 1),
            gpu_memory_total_mb=round(gpu_total_mb, 0),
        )
        self._snapshots.append(snap)
        if len(self._snapshots) > self._max_snapshots:
            self._snapshots = self._snapshots[-self._max_snapshots:]
        return snap

    def metrics(self) -> dict[str, Any]:
        """Métriques de l'orchestrateur CPU/GPU."""
        last = self._snapshots[-1] if self._snapshots else None
        return {
            "cpu_percent": last.cpu_percent if last else 0.0,
            "memory_rss_mb": last.memory_rss_mb if last else 0.0,
            "thread_count": last.thread_count if last else 0,
            "gpu_available": self._gpu_available,
            "gpu_memory_used_mb": last.gpu_memory_used_mb if last else 0.0,
            "gpu_memory_total_mb": last.gpu_memory_total_mb if last else 0.0,
            "components": list(self._component_threads.keys()),
            "snapshots_count": len(self._snapshots),
        }


# Import asyncio ici pour éviter problèmes circulaires
import asyncio
