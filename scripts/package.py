"""Native installer/package + portable archive, SHA256 manifest. Run after build."""
import hashlib
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root))
from pluma import __version__
release = root / 'release'
release.mkdir(exist_ok=True)
bundle = root / 'dist/Pluma'
system = platform.system()
base = f'Pluma-{__version__}-{system}-x64'
if system == 'Windows':
    shutil.make_archive(str(release / base), 'zip', root_dir=root / 'dist', base_dir='Pluma')
    compiler = shutil.which('ISCC.exe') or str(Path(os.environ.get('ProgramFiles(x86)', 'C:/Program Files (x86)')) / 'Inno Setup 6/ISCC.exe')
    subprocess.run([compiler, '/DAppVersion=' + __version__, str(root / 'packaging/windows.iss')], check=True)
else:
    shutil.make_archive(str(release / base), 'gztar', root_dir=root / 'dist', base_dir='Pluma')
    deb = root / 'build/debian'
    shutil.rmtree(deb, ignore_errors=True)
    (deb / 'DEBIAN').mkdir(parents=True)
    (deb / 'opt').mkdir(parents=True)
    shutil.copytree(bundle, deb / 'opt/pluma')
    (deb / 'DEBIAN/control').write_text(
        f'Package: pluma-browser\nVersion: {__version__}\nSection: web\nPriority: optional\nArchitecture: amd64\n'
        'Maintainer: Emerson Oliveira\n'
        'Depends: libnss3, libxtst6, libxkbfile1, libasound2t64, libegl1, libopengl0, libgl1, libxkbcommon-x11-0, libxcb-cursor0, libxcb-icccm4, libxcb-keysyms1, libxcb-shape0, libxcb-xinerama0\n'
        'Description: Minimal Chromium browser with native blocking and optional AI\n')
    applications = deb / 'usr/share/applications'
    applications.mkdir(parents=True)
    shutil.copy2(root / 'packaging/pluma.desktop', applications)
    subprocess.run(['dpkg-deb', '--root-owner-group', '--build', str(deb),
                    str(release / (base + '.deb'))], check=True)
files = [p for p in release.iterdir() if p.is_file() and p.name != 'SHA256SUMS.txt']
(release / 'SHA256SUMS.txt').write_text('\n'.join(
    hashlib.file_digest(p.open('rb'), 'sha256').hexdigest() + '  ' + p.name for p in sorted(files)) + '\n')
print('Packages:', [p.name for p in release.iterdir()])
