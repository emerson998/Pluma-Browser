"""Pluma look: moss-and-sand tokens, bundled type and Lucide icons, one stylesheet per mode."""
import tempfile
from pathlib import Path
from string import Template

DATA = Path(__file__).parent / 'data'

# Dealt by tasteskill (palette moss-sand, pairing Host Grotesk + JetBrains Mono, radius soft).
# chrome: toolbar, tab strip and panels · page: the active tab and new-tab page.
TOKENS = {
    'Claro': dict(
        chrome='#d2cab8', page='#ddd6c6', field='#ebe6da', raised='#e6e0d3', line='#bdb4a0',
        ink='#2a2a26', muted='#55534b', faint='#86826f',
        accent='#4f6238', accent_ink='#ffffff', accent_hover='#5d7243', accent_press='#435330',
        accent_soft='#c2c7a5', button='#e4ded1', button_hover='#d8d1c0', button_press='#cbc3b0',
        hover='rgba(42, 42, 38, 0.08)', press='rgba(42, 42, 38, 0.15)', handle='#b2a994',
    ),
    'Escuro': dict(
        chrome='#2a2a26', page='#1f1f1c', field='#353430', raised='#353430', line='#4a4842',
        ink='#ece6d8', muted='#a39e92', faint='#77736a',
        accent='#a9bd87', accent_ink='#1f1f1c', accent_hover='#b9cb99', accent_press='#97ab75',
        accent_soft='#3d4531', button='#353430', button_hover='#403f3a', button_press='#4b4943',
        hover='rgba(236, 230, 216, 0.08)', press='rgba(236, 230, 216, 0.15)', handle='#55534b',
    ),
}
FONT, MONO = 'Host Grotesk', 'JetBrains Mono'
current = 'Escuro'
_fonts_loaded = False
_files = None

STYLE = Template("""
* { font-family: "$font"; }
QWidget { background: $chrome; color: $ink; font-size: 13px; }
QLabel, QCheckBox, QRadioButton { background: transparent; }
QMainWindow::separator { background: $line; width: 1px; height: 1px; }

QToolBar#nav { background: $chrome; border: none; padding: 8px 10px 6px 10px; spacing: 2px; }
QToolBar#nav QToolButton { background: transparent; border: none; border-radius: 8px; padding: 7px; margin: 0 1px; }
QToolButton { background: transparent; border: none; border-radius: 8px; padding: 6px; }
QToolButton:hover { background: $hover; }
QToolButton:pressed { background: $press; }
QToolButton:checked { background: $accent_soft; }
QToolButton::menu-indicator { image: none; width: 0; }
QLineEdit#address { background: $field; border: 1px solid transparent; border-radius: 10px;
    padding: 7px 10px; margin: 0 6px; min-height: 20px; }
QLineEdit#address:hover { border: 1px solid $line; }
QLineEdit#address:focus { border: 1px solid $accent; background: $page; }

QTabWidget::pane { border: 0; background: $page; }
QTabWidget::tab-bar { left: 8px; }
QTabBar { background: $chrome; }
QTabBar::tab { background: transparent; color: $muted; padding: 8px 10px 8px 14px; margin: 0 2px 0 0;
    border-top-left-radius: 9px; border-top-right-radius: 9px; min-width: 110px; max-width: 220px; }
QTabBar::tab:hover { background: $hover; color: $ink; }
QTabBar::tab:selected { background: $page; color: $ink; }
QTabBar::close-button { image: url("$x"); subcontrol-position: right; border-radius: 5px; margin: 2px; }
QTabBar::close-button:hover { background: $press; }
QTabBar QToolButton { background: $chrome; border-radius: 6px; }

QWidget#home { background: $page; }
QLabel#hero { font-size: 60px; font-weight: 500; color: $ink; }
QLabel#muted { color: $muted; font-size: 15px; }
QLabel#fact { color: $muted; font-size: 13px; }
QLabel#kbd { color: $muted; font-family: "$mono"; font-size: 12px; }
QLabel#section { color: $muted; font-size: 11px; font-weight: 600; }
QLineEdit#homeSearch { background: $field; border: 1px solid $line; border-radius: 14px;
    padding: 13px 18px; font-size: 16px; }
QLineEdit#homeSearch:hover { border: 1px solid $muted; }
QLineEdit#homeSearch:focus { border: 1px solid $accent; }
QPushButton#tile { background: $field; border: 1px solid $line; border-radius: 12px;
    padding: 12px 14px; text-align: left; }
QPushButton#tile:hover { border: 1px solid $accent; background: $raised; }
QPushButton#tile:pressed { background: $button_press; }

QLineEdit, QPlainTextEdit, QTextEdit, QComboBox, QSpinBox { background: $field; border: 1px solid $line;
    border-radius: 8px; padding: 7px 10px; selection-background-color: $accent; selection-color: $accent_ink; }
QLineEdit:hover, QPlainTextEdit:hover, QTextEdit:hover, QComboBox:hover, QSpinBox:hover { border: 1px solid $muted; }
QLineEdit:focus, QPlainTextEdit:focus, QTextEdit:focus, QComboBox:focus, QSpinBox:focus { border: 1px solid $accent; }
QLineEdit:disabled, QComboBox:disabled, QPlainTextEdit:disabled { color: $faint; }
QComboBox::drop-down { border: none; width: 26px; }
QComboBox::down-arrow { image: url("$down"); width: 14px; height: 14px; }
QComboBox QAbstractItemView { background: $raised; border: 1px solid $line; padding: 4px; outline: 0;
    selection-background-color: $accent_soft; selection-color: $ink; }
QSpinBox { padding-right: 24px; }
QSpinBox::up-button, QSpinBox::down-button { subcontrol-origin: border; width: 22px; border: none; background: transparent; }
QSpinBox::up-button { subcontrol-position: top right; }
QSpinBox::down-button { subcontrol-position: bottom right; }
QSpinBox::up-button:hover, QSpinBox::down-button:hover { background: $hover; }
QSpinBox::up-arrow { image: url("$up"); width: 11px; height: 11px; }
QSpinBox::down-arrow { image: url("$down"); width: 11px; height: 11px; }

QPushButton { background: $button; color: $ink; border: 1px solid $line; border-radius: 8px; padding: 7px 14px; }
QPushButton:hover { background: $button_hover; }
QPushButton:pressed { background: $button_press; padding: 8px 14px 6px 14px; }
QPushButton:default, QPushButton#primary { background: $accent; color: $accent_ink; border: 1px solid $accent; font-weight: 500; }
QPushButton:default:hover, QPushButton#primary:hover { background: $accent_hover; border: 1px solid $accent_hover; }
QPushButton:default:pressed, QPushButton#primary:pressed { background: $accent_press; border: 1px solid $accent_press; }
QPushButton:disabled, QPushButton#primary:disabled { background: $chrome; color: $faint; border: 1px solid $line; }
QPushButton#chip { border-radius: 14px; padding: 5px 12px; font-size: 12px; }
QPushButton#chip:pressed { padding: 6px 12px 4px 12px; }
QPushButton#icon { background: transparent; border: none; border-radius: 6px; padding: 4px; }
QPushButton#icon:hover { background: $hover; }
QPushButton#icon:pressed, QPushButton#icon:checked { background: $press; }

QCheckBox { spacing: 8px; }
QCheckBox::indicator { width: 16px; height: 16px; border: 1px solid $muted; border-radius: 4px; background: $field; }
QCheckBox::indicator:hover { border: 1px solid $accent; }
QCheckBox::indicator:checked { image: url("$check"); background: $accent; border: 1px solid $accent; }

QMenu { background: $raised; border: 1px solid $line; padding: 6px; }
QMenu::item { padding: 7px 28px 7px 12px; border-radius: 6px; background: transparent; }
QMenu::item:selected { background: $accent_soft; color: $ink; }
QMenu::item:disabled { color: $faint; }
QMenu::separator { height: 1px; background: $line; margin: 5px 8px; }
QToolTip { background: $ink; color: $page; border: none; padding: 5px 8px; }

QStatusBar { background: $chrome; color: $muted; font-size: 12px; }
QStatusBar::item { border: none; }
QDockWidget { color: $ink; titlebar-close-icon: url("$x"); titlebar-normal-icon: url("$up"); }
QDockWidget::title { background: $chrome; padding: 10px 14px; text-align: left; }
QDockWidget::close-button, QDockWidget::float-button { border: none; border-radius: 5px; padding: 2px; }
QDockWidget::close-button:hover, QDockWidget::float-button:hover { background: $press; }
QWidget#aiPanel, QWidget#pipbar, QDialog { background: $chrome; }

QScrollBar:vertical { background: transparent; width: 10px; margin: 2px; }
QScrollBar:horizontal { background: transparent; height: 10px; margin: 2px; }
QScrollBar::handle { background: $handle; border-radius: 3px; min-height: 28px; min-width: 28px; }
QScrollBar::handle:hover { background: $muted; }
QScrollBar::add-line, QScrollBar::sub-line { width: 0; height: 0; }
QScrollBar::add-page, QScrollBar::sub-page { background: none; }

QTableWidget, QListWidget { background: $field; border: 1px solid $line; border-radius: 8px; gridline-color: $line;
    selection-background-color: $accent_soft; selection-color: $ink; outline: 0; }
QTableWidget::item, QListWidget::item { padding: 6px; }
QListWidget::item:hover, QTableWidget::item:hover { background: $hover; }
QHeaderView::section { background: $chrome; color: $muted; border: none; border-bottom: 1px solid $line;
    padding: 6px 8px; font-weight: 500; }
QTableCornerButton::section { background: $chrome; border: none; }
""")


def align_form(form):
    """Centre each form label on its field (QFormLayout top-aligns them)."""
    from PySide6.QtCore import Qt
    for row in range(form.rowCount()):
        label = form.itemAt(row, form.ItemRole.LabelRole)
        field = form.itemAt(row, form.ItemRole.FieldRole)
        if label and field and label.widget() and field.widget():
            label.widget().setMinimumHeight(38)
            label.widget().setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)


def tokens(mode=None):
    return TOKENS.get(mode or current, TOKENS['Escuro'])


def load_fonts():
    """Register the bundled fonts once; keep the system font if they are missing."""
    global _fonts_loaded, FONT, MONO
    if _fonts_loaded:
        return
    _fonts_loaded = True
    from PySide6.QtGui import QFontDatabase, QFont
    from PySide6.QtWidgets import QApplication
    families = {}
    for file in sorted((DATA / 'fonts').glob('*.ttf')):
        ident = QFontDatabase.addApplicationFont(str(file))
        if ident >= 0:
            families[file.stem.split('[')[0]] = QFontDatabase.applicationFontFamilies(ident)[0]
    FONT = families.get('HostGrotesk', 'Segoe UI')
    MONO = families.get('JetBrainsMono', 'Consolas')
    app = QApplication.instance()
    if app:
        font = QFont(FONT, 10)
        font.setHintingPreference(QFont.HintingPreference.PreferNoHinting)
        app.setFont(font)


def svg(name, color):
    return (DATA / 'icons' / f'{name}.svg').read_text(encoding='utf-8').replace('currentColor', color)


def icon(name, color=None, size=18):
    """Lucide icon tinted with a token; a dimmed copy serves the disabled state."""
    from PySide6.QtCore import QByteArray, QRectF, Qt
    from PySide6.QtGui import QIcon, QPainter, QPixmap
    from PySide6.QtSvg import QSvgRenderer
    values = tokens()
    result = QIcon()
    for mode, tint in ((QIcon.Mode.Normal, color or values['ink']), (QIcon.Mode.Disabled, values['faint'])):
        renderer = QSvgRenderer(QByteArray(svg(name, tint).encode()))
        pixmap = QPixmap(size * 2, size * 2)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        renderer.render(painter, QRectF(0, 0, size * 2, size * 2))
        painter.end()
        pixmap.setDevicePixelRatio(2)
        result.addPixmap(pixmap, mode)
    return result


APP_ICON_SIZES = (16, 24, 32, 48, 64, 128, 256)


def app_image(size):
    """The Pluma logo (data/icons/pluma.svg) rendered as a square QImage."""
    from PySide6.QtCore import QRectF, Qt
    from PySide6.QtGui import QImage, QPainter
    from PySide6.QtSvg import QSvgRenderer
    image = QImage(size, size, QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(Qt.GlobalColor.transparent)
    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    QSvgRenderer(str(DATA / 'icons' / 'pluma.svg')).render(painter, QRectF(0, 0, size, size))
    painter.end()
    return image


def app_icon():
    from PySide6.QtGui import QIcon, QPixmap
    result = QIcon()
    for size in APP_ICON_SIZES:
        result.addPixmap(QPixmap.fromImage(app_image(size)))
    return result


def write_app_icons(folder):
    """Writes pluma.ico (multi-size, PNG entries) and pluma.png (256 px) for installers."""
    import struct
    from PySide6.QtCore import QBuffer, QIODevice
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    blobs = []
    for size in APP_ICON_SIZES:
        buffer = QBuffer()
        buffer.open(QIODevice.OpenModeFlag.WriteOnly)
        app_image(size).save(buffer, 'PNG')
        blobs.append((size, bytes(buffer.data())))
    offset = 6 + 16 * len(blobs)
    header, body = struct.pack('<HHH', 0, 1, len(blobs)), b''
    for size, data in blobs:
        side = 0 if size >= 256 else size
        header += struct.pack('<BBBBHHII', side, side, 0, 0, 1, 32, len(data), offset + len(body))
        body += data
    (folder / 'pluma.ico').write_bytes(header + body)
    (folder / 'pluma.png').write_bytes(blobs[-1][1])
    return folder / 'pluma.ico', folder / 'pluma.png'


def _image_files(mode):
    """Tinted SVGs the stylesheet points at (close, check, arrows), written once per mode."""
    global _files
    if _files is None:
        _files = Path(tempfile.mkdtemp(prefix='pluma-theme-'))
    values, paths = tokens(mode), {}
    for key, name, colour in (('x', 'x', values['muted']), ('check', 'check', values['accent_ink']),
                              ('down', 'chevron-down', values['muted']), ('up', 'chevron-up', values['muted'])):
        path = _files / f'{mode}-{name}.svg'
        if not path.exists():
            path.write_text(svg(name, colour), encoding='utf-8')
        paths[key] = path.as_posix()
    return paths


def stylesheet(mode='Escuro'):
    mode = mode if mode in TOKENS else 'Escuro'
    return STYLE.substitute(tokens(mode), font=FONT, mono=MONO, **_image_files(mode))


def apply(mode):
    """Set the app-wide stylesheet; callers then retint their icons."""
    global current
    from PySide6.QtWidgets import QApplication
    current = mode if mode in TOKENS else 'Escuro'
    load_fonts()
    app = QApplication.instance()
    if app:
        app.setStyleSheet(stylesheet(current))
