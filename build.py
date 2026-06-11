"""Build a standalone desktop executable with PyInstaller.

Usage:
    python build.py

Output:
    - Windows: dist/GenshinInstrumentPlayer.exe
    - macOS:   dist/GenshinInstrumentPlayer.app
    - Linux:   dist/GenshinInstrumentPlayer (binary)
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
        "--noconfirm",
        "--clean",
    ]

    # Platform-specific config
    if sys.platform == "win32":
        args += [
            "--onefile",
            "--windowed",
            "--uac-admin",
        ]

    raise SystemExit(subprocess.call(args))


if __name__ == "__main__":
    main()