# Third-party components

The Pluma application source is MIT licensed. Dependencies retain their own licenses.

- PySide6 / Qt: LGPLv3, GPLv3 or commercial licensing depending on component.
  Pluma uses the dynamically linked distribution; do not remove bundled notices.
  https://doc.qt.io/qtforpython-6/licenses.html
- Qt WebEngine / Chromium: Qt and multiple third-party licenses.
  https://doc.qt.io/qt-6/qtwebengine-licensing.html
  Qt sources: https://download.qt.io/official_releases/qt/
  PySide sources: https://download.qt.io/official_releases/QtForPython/
- HTTPX: BSD-3-Clause. https://github.com/encode/httpx
- keyring: MIT. https://github.com/jaraco/keyring
- PyInstaller (build tool): GPL with distribution exception.
  https://pyinstaller.org/en/stable/license.html

Before distributing binaries, preserve component copyright/license notices,
satisfy corresponding-source and relinking obligations for LGPL components,
and review the exact versions bundled. The portable directory layout is intentional
and must not be converted into a sealed executable that prevents replacing Qt libraries.
The starter host list is maintained in Pluma's source and has no external list dependency.

## Filtering and measurement (0.2)

- python-adblock / Brave adblock-rust: MIT/Apache-2.0.
  https://github.com/ArniDagur/python-adblock
  https://github.com/brave/adblock-rust
- EasyList and EasyPrivacy are downloaded from their official project and bundled
  as filter data in binary distributions. Their copyright and license headers are
  preserved unmodified, alongside metadata recording the download source/date/hash.
  EasyList project licensing: https://easylist.to/pages/licence.html
- psutil: BSD-3-Clause. https://github.com/giampaolo/psutil
- packaging: Apache-2.0/BSD-2-Clause. https://github.com/pypa/packaging
- Inno Setup: build tool with its own license. https://jrsoftware.org/isinfo.php
