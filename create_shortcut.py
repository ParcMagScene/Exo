"""create_shortcut.py — Crée un raccourci EXO sur le bureau Windows."""

import os
import sys


def create_desktop_shortcut():
    """Crée un raccourci .lnk sur le bureau avec l'icône EXO."""
    try:
        import win32com.client  # type: ignore
    except ImportError:
        # Fallback: utiliser PowerShell
        _create_shortcut_powershell()
        return

    desktop = os.path.join(os.environ["USERPROFILE"], "Desktop")
    shortcut_path = os.path.join(desktop, "EXO.lnk")

    project_dir = os.path.dirname(os.path.abspath(__file__))
    target = os.path.join(project_dir, ".venv", "Scripts", "pythonw.exe")
    icon = os.path.join(project_dir, "assets", "exo_icon.ico")
    launcher = os.path.join(project_dir, "main.py")

    shell = win32com.client.Dispatch("WScript.Shell")
    shortcut = shell.CreateShortCut(shortcut_path)
    shortcut.TargetPath = target
    shortcut.Arguments = f'"{launcher}" --gui'
    shortcut.WorkingDirectory = project_dir
    shortcut.IconLocation = icon
    shortcut.Description = "EXO — Assistant vocal intelligent"
    shortcut.save()

    print(f"✅ Raccourci créé : {shortcut_path}")


def _create_shortcut_powershell():
    """Fallback : crée le raccourci via PowerShell."""
    import subprocess

    project_dir = os.path.dirname(os.path.abspath(__file__)).replace("\\", "/")
    desktop = os.path.join(os.environ["USERPROFILE"], "Desktop").replace("\\", "/")
    shortcut_path = f"{desktop}/EXO.lnk"
    target = f"{project_dir}/.venv/Scripts/pythonw.exe"
    icon = f"{project_dir}/assets/exo_icon.ico"
    launcher = f"{project_dir}/main.py"

    ps_script = f'''
$ws = New-Object -ComObject WScript.Shell
$sc = $ws.CreateShortcut("{shortcut_path}")
$sc.TargetPath = "{target}"
$sc.Arguments = '"{launcher}" --gui'
$sc.WorkingDirectory = "{project_dir}"
$sc.IconLocation = "{icon}"
$sc.Description = "EXO - Assistant vocal intelligent"
$sc.Save()
'''

    subprocess.run(["powershell", "-Command", ps_script], check=True)
    print(f"✅ Raccourci créé : {shortcut_path}")


if __name__ == "__main__":
    create_desktop_shortcut()
