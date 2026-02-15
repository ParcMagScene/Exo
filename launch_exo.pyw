"""launch_exo.pyw — Lanceur silencieux EXO (sans console).

Double-cliquer ce fichier ou le raccourci bureau pour démarrer EXO
avec son interface graphique.
"""

import subprocess
import sys
import os

# Aller dans le dossier du projet
os.chdir(os.path.dirname(os.path.abspath(__file__)))

# Utiliser le Python du venv
venv_python = os.path.join(os.path.dirname(__file__), ".venv", "Scripts", "pythonw.exe")
if not os.path.exists(venv_python):
    venv_python = os.path.join(os.path.dirname(__file__), ".venv", "Scripts", "python.exe")

# Lancer main.py avec --gui
subprocess.Popen(
    [venv_python, "main.py", "--gui"],
    cwd=os.path.dirname(os.path.abspath(__file__)),
    creationflags=0x00000008,  # DETACHED_PROCESS
)
