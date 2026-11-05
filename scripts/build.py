"""Run on the target OS: python scripts/build.py"""
import os
from pathlib import Path
import shutil
import subprocess
import sys

root = Path(__file__).resolve().parents[1]
# Ship full filter lists with release bundles; startup remains offline.
sys.path.insert(0, str(root))
from pluma.blocking import FilterEngine
filter_directory = root / 'pluma/data/filters'
FilterEngine(filter_directory).update()
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from PySide6.QtGui import QGuiApplication
from pluma import theme
qt_app = QGuiApplication([])
icon_file, _ = theme.write_app_icons(root / 'build/icons')
subprocess.run([
    sys.executable, '-m', 'PyInstaller', '--noconfirm', '--clean',
    '--windowed', '--onedir', '--exclude-module', 'numpy', '--exclude-module', 'PIL', '--name', 'Pluma',
    '--icon', str(icon_file),
    '--collect-all', 'keyring.backends',
    '--collect-all', 'adblock',
    '--hidden-import', 'PySide6.QtPrintSupport',
    '--hidden-import', 'PySide6.QtSvg',
    '--add-data', str(filter_directory) + ':pluma/data/filters',
    '--add-data', str(root / 'pluma/data/fonts') + ':pluma/data/fonts',
    '--add-data', str(root / 'pluma/data/icons') + ':pluma/data/icons', str(root / 'run_pluma.py'),
], cwd=root, check=True)
for name in ('LICENSE', 'THIRD_PARTY.md', 'README.md'):
    shutil.copy2(root / name, root / 'dist' / 'Pluma' / name)
# PyInstaller keeps Qt libraries dynamically linked; keep their license notices.
import PySide6
qt_root = Path(PySide6.__file__).parent
for folder in ('Qt/licenses', 'Qt/resources', 'licenses'):
    source = qt_root / folder
    if source.exists() and 'licenses' in folder:
        shutil.copytree(source, root / 'dist' / 'Pluma' / 'licenses' / folder.replace('/', '_'), dirs_exist_ok=True)
print('Portable bundle:', root / 'dist' / 'Pluma')
