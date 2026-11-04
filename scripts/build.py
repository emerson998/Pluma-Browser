"""Run on the target OS: python scripts/build.py"""
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
subprocess.run([
    sys.executable, '-m', 'PyInstaller', '--noconfirm', '--clean',
    '--windowed', '--onedir', '--exclude-module', 'numpy', '--exclude-module', 'PIL', '--name', 'Pluma',
    '--collect-all', 'keyring.backends',
    '--collect-all', 'adblock',
    '--hidden-import', 'PySide6.QtPrintSupport',
    '--add-data', str(filter_directory) + ':pluma/data/filters', str(root / 'run_pluma.py'),
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
