"""Build a standalone desktop executable with PyInstaller.

Usage:
    python build.py

Output lands in dist/ (GenshinInstrumentPlayer.exe on Windows). Build on
the OS you want to target — PyInstaller does not cross-compile.
"""

import shutil
import subprocess
import sys


def main():
    if shutil.which("pyinstaller") is None:
        try:
            import PyInstaller  # noqa: F401
        except ImportError:
            sys.exit("PyInstaller is not installed. Run: pip install pyinstaller")

    args = [
        sys.executable, "-m", "PyInstaller",
        "app.py",
        "--name", "GenshinInstrumentPlayer",
        "--onefile",
        "--windowed",
        "--noconfirm",
        "--clean",
    ]
    if sys.platform == "win32":
        # Genshin runs elevated; without elevation our key presses are
        # ignored, so make the exe request admin on launch.
        args.append("--uac-admin")

    raise SystemExit(subprocess.call(args))


if __name__ == "__main__":
    main()
