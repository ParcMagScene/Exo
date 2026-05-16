"""
copy_exo_logs.py — Copie tous les fichiers .log et .err.log du dossier courant et sous-dossiers vers D:/EXO/logs/
Usage : python copy_exo_logs.py
"""
import os
import shutil
from pathlib import Path

def main():
    src = Path.cwd()
    target = Path(os.environ.get("EXO_LOGS_DIR", r"D:/EXO/logs"))
    target = Path('D:/EXO/logs')
    target.mkdir(parents=True, exist_ok=True)
    for path in src.rglob("*.log"):
        if target in path.parents:
            continue
        dest = target / path.name
        shutil.copy2(path, dest)
    for path in src.rglob("*.err.log"):
        if target in path.parents:
            continue
        dest = target / path.name
        shutil.copy2(path, dest)
    print(f"Tous les logs ont été copiés dans {target}")

if __name__ == "__main__":
    main()
