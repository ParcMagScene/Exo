#!/usr/bin/env python3
"""verify_installation.py - Vérification de l'installation complète."""

import os
import sys
from pathlib import Path

def check_file(path: str, description: str) -> bool:
    """Vérifie qu'un fichier existe."""
    exists = Path(path).exists()
    symbol = "✅" if exists else "❌"
    print(f"{symbol} {description:50} {'(OK)' if exists else f'(MANQUANT: {path})'}")
    return exists

def check_directory(path: str, description: str) -> bool:
    """Vérifie qu'un répertoire existe."""
    exists = Path(path).is_dir()
    symbol = "✅" if exists else "❌"
    print(f"{symbol} {description:50} {'(OK)' if exists else f'(MANQUANT: {path})'}")
    return exists

def check_module(module: str) -> bool:
    """Vérifie qu'un module Python est installé."""
    try:
        __import__(module)
        print(f"✅ {f'Module: {module}':50} (OK)")
        return True
    except ImportError:
        print(f"❌ {f'Module: {module}':50} (MANQUANT)")
        return False

def main():
    """Lance toutes les vérifications."""
    print("=" * 80)
    print("🔍 VÉRIFICATION DE L'INSTALLATION")
    print("=" * 80)
    
    results = []
    
    # ==================== Fichiers Principaux ====================
    print("\n📄 Fichiers Principaux")
    print("-" * 80)
    results.append(check_file("main.py", "Point d'entrée principal"))
    results.append(check_file("requirements.txt", "Dépendances"))
    results.append(check_file(".env.example", "Template variables d'env"))
    
    # ==================== Répertoires ====================
    print("\n📁 Répertoires Core")
    print("-" * 80)
    
    results.append(check_directory("src", "Package principal"))
    results.append(check_directory("src/core", "Module Core"))
    results.append(check_directory("src/brain", "Module Brain"))
    results.append(check_directory("src/hardware", "Module Hardware"))
    results.append(check_directory("src/integrations", "Module Intégrations"))
    results.append(check_directory("src/gui", "Module GUI"))
    results.append(check_directory("src/protocols", "Module Protocoles"))
    results.append(check_directory("examples", "Exemples"))
    results.append(check_directory("data/chroma", "ChromaDB storage"))
    
    # ==================== Fichiers Source ====================
    print("\n📝 Fichiers Source Python")
    print("-" * 80)
    
    results.append(check_file("src/__init__.py", "Package init"))
    results.append(check_file("src/config.py", "Configuration centralisée"))
    results.append(check_file("src/utils.py", "Utilitaires"))
    results.append(check_file("src/core/core.py", "Orchestrateur principal"))
    results.append(check_file("src/brain/brain_engine.py", "Moteur IA (GPT-4o)"))
    results.append(check_file("src/hardware/hardware_accel.py", "Accélération matérielle"))
    results.append(check_file("src/integrations/home_bridge.py", "Bridge Home Assistant"))
    results.append(check_file("src/gui/visage_gui.py", "Interface Pygame"))
    results.append(check_file("src/protocols/wyoming.py", "Serveur Wyoming"))
    
    # ==================== Exemples ====================
    print("\n📚 Exemples & Tests")
    print("-" * 80)
    
    results.append(check_file("examples/pi_satellite.py", "Client Pi satellite"))
    results.append(check_file("examples/test_performance.py", "Benchmark performance"))
    
    # ==================== Documentation ====================
    print("\n📖 Documentation")
    print("-" * 80)
    
    results.append(check_file("README.md", "README principal"))
    results.append(check_file("QUICKSTART.md", "Démarrage rapide"))
    results.append(check_file("SETUP.md", "Guide d'installation"))
    results.append(check_file("ARCHITECTURE.md", "Architecture détaillée"))
    results.append(check_file("ENV_REFERENCE.md", "Référence env vars"))
    results.append(check_file("PROJECT_STRUCTURE.txt", "Structure du projet"))
    results.append(check_file("SUMMARY.md", "Résumé complet"))
    
    # ==================== Docker ====================
    print("\n🐳 Docker")
    print("-" * 80)
    
    results.append(check_file("Dockerfile", "Dockerfile"))
    results.append(check_file("docker-compose.yml", "Docker Compose"))
    
    # ==================== Dépendances Python ====================
    print("\n📦 Dépendances Python (optionnel si pas installé)")
    print("-" * 80)
    
    deps = [
        "aiohttp",
        "azure.ai.openai",
        "chromadb",
        "websockets",
        "numpy",
    ]
    
    deps_ok = True
    for dep in deps:
        if not check_module(dep):
            deps_ok = False
    
    # ==================== Fichiers de Config ====================
    print("\n⚙️ Configuration")
    print("-" * 80)
    
    env_exists = check_file(".env", "Fichier .env (création requise)")
    results.append(env_exists)
    
    # ==================== Résumé ====================
    print("\n" + "=" * 80)
    
    total = len(results)
    passed = sum(results)
    
    if all(results[:-1]):  # Ignorer .env qui n'existe pas encore
        print(f"✅ INSTALLATION COMPLÈTE ({passed}/{total})")
        print("\n🚀 Prêt à démarrer!")
        print("\nProchaines étapes:")
        print("1. cp .env.example .env")
        print("2. Éditer .env avec vos clés API")
        print("3. python main.py")
        return 0
    else:
        print(f"⚠️ VÉRIFICATION INCOMPLÈTE ({passed}/{total})")
        print("\nManquements détectés - voir ci-dessus")
        print("\nRelancer après correction:")
        print("pip install -r requirements.txt")
        return 1

if __name__ == "__main__":
    sys.exit(main())
