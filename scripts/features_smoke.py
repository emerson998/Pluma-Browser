"""Exercise lifecycle, restoration, privacy cleanup and native management panels."""
import os
import sys
import tempfile
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
temp = tempfile.TemporaryDirectory()
os.environ['XDG_DATA_HOME'] = temp.name
os.environ['XDG_CACHE_HOME'] = temp.name
from PySide6.QtCore import QSettings, QTimer, QEvent, QCoreApplication, Qt
from PySide6.QtWidgets import QApplication
QSettings.setDefaultFormat(QSettings.Format.IniFormat)
QSettings.setPath(QSettings.Format.IniFormat, QSettings.Scope.UserScope, temp.name)
from pluma.app import Window
from pluma.dialogs import SettingsDialog, BookmarksDialog, DownloadsDialog
from pluma.storage import atomic_json
app = QApplication([])
app.setApplicationName('PlumaFeatureSmoke')
window = Window()
window.root = Path(temp.name) / 'state'
window.show()
try:
    assert window.current().view is None
    second = window.add_tab('https://example.org', lazy=True)
    third = window.add_tab('https://example.net', lazy=True)
    assert second.view is None and third.view is None
    window.save_session()
    assert (window.root / 'session.json').exists()
    window.close_tab(window.tabs.indexOf(third))
    assert len(window.closed_tabs) == 1
    # Reopening intentionally activates the tab, so test URL/state policy via saved data.
    assert window.closed_tabs[-1]['url'] == 'https://example.net'
    settings = SettingsDialog(window)
    assert settings.values()['freeze'] >= 15
    assert settings.values()['discard'] > settings.values()['freeze']
    assert settings.values()['pip_auto'] is False, 'Automatic popup must be opt-in'
    favorites = BookmarksDialog(window)
    favorites.append({'url': 'https://example.org', 'title': 'Example', 'folder': 'Work'})
    favorites.save()
    assert window.bookmark_data[0]['folder'] == 'Work'
    DownloadsDialog(window.downloads, window).close()
    from pluma.video import SCRIPT_NAME
    assert window.profile.scripts().find(SCRIPT_NAME), 'YouTube ad script must be installed'
    window.blocker.allowed = frozenset({'youtube.com'})
    window.sync_video_blocking()
    assert not window.profile.scripts().find(SCRIPT_NAME), 'Exception must disable the ad script'
    window.blocker.allowed = frozenset()
    window.sync_video_blocking()
    window.open_floating('https://www.youtube.com/watch?v=dQw4w9WgXcQ', 42)
    floating = window.floating
    assert floating.isVisible() and floating.url.endswith('&t=42s')
    assert floating.windowFlags() & Qt.WindowType.WindowStaysOnTopHint
    floating.top.setChecked(False)
    assert not floating.windowFlags() & Qt.WindowType.WindowStaysOnTopHint
    floating.close()
    assert window.floating is None
    window.toggle_ai()
    assert not window.ai_panel.flush_timer.isActive(), 'Hidden/idle AI must not poll'
    window.new_private()
    child = window.child_windows[-1]
    profile = child.profile
    assert profile.isOffTheRecord()
    child.close()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    import shiboken6
    assert not shiboken6.isValid(profile), 'Private profile must die on window close'
    assert not window.child_windows, 'Closed private windows must be released'
    QTimer.singleShot(100, lambda: QApplication.activeModalWidget().accept())
    window.performance()
    QTimer.singleShot(100, lambda: QApplication.activeModalWidget().accept())
    window.about()
    window.close()
    print('PASS: lazy tabs, atomic session, preferences, bookmarks, idle AI and private teardown')
finally:
    window.close()
