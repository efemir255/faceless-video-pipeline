import os
import subprocess
from pathlib import Path

def create_shortcut():
    """Create a Desktop shortcut for the Faceless Video Pipeline on Windows."""
    if os.name != 'nt':
        print("Shortcut creation is only supported on Windows.")
        return

    desktop = Path(os.environ["USERPROFILE"]) / "Desktop"
    shortcut_path = desktop / "Faceless Video Pipeline.lnk"

    # Path to the run.bat in the current directory
    current_dir = Path(__file__).parent.absolute()
    target_path = current_dir / "run.bat"
    icon_path = current_dir / "assets" / "icon.ico" # Fallback if no icon exists

    # PowerShell script to create the shortcut
    # Using 'cmd /c' ensures it stays in its own window
    powershell_cmd = f"$s=(New-Object -COM WScript.Shell).CreateShortcut('{shortcut_path}'); $s.TargetPath='{target_path}'; $s.WorkingDirectory='{current_dir}'; $s.Description='Launch Faceless Video Pipeline'; $s.Save()"

    try:
        subprocess.run(["powershell", "-Command", powershell_cmd], check=True)
        print(f"✅ Shortcut created on Desktop: {shortcut_path}")
    except Exception as e:
        print(f"❌ Failed to create shortcut: {e}")

if __name__ == "__main__":
    create_shortcut()
