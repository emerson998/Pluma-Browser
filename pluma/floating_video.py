"""Resizable video window reusing the tab's existing Chromium page."""
import time
import weakref
from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import QMainWindow, QToolBar
from PySide6.QtWebEngineCore import QWebEnginePage, QWebEngineScript

WORLD = QWebEngineScript.ScriptWorldId.ApplicationWorld.value

# Presentation changes run in an isolated JS world. No embed reload or second
# player. The event listener covers playlist changes without DOM polling.
FOCUS_VIDEO = r"""
(()=>{
    const key='__plumaFloatingVideo';
    if(window[key]) window[key].restore();
    const videos=[...document.querySelectorAll('video')].filter(v=>{
        const r=v.getBoundingClientRect();
        return r.width>0 && r.height>0;
    });
    videos.sort((a,b)=>Number(!b.paused)-Number(!a.paused) ||
        b.getBoundingClientRect().width*b.getBoundingClientRect().height-
        a.getBoundingClientRect().width*a.getBoundingClientRect().height);
    if(!videos.length) return false;
    const state={video:null, marks:[], controls:false, style:null};
    function clearMarks(){
        for(const [node,name,value] of state.marks){
            if(value===null) node.removeAttribute(name);
            else node.setAttribute(name,value);
        }
        state.marks=[];
        if(state.video) state.video.controls=state.controls;
    }
    function mark(node,name){
        state.marks.push([node,name,node.getAttribute(name)]);
        node.setAttribute(name,'');
    }
    function select(video){
        clearMarks();
        state.video=video;
        state.controls=video.controls;
        video.controls=true;
        mark(video,'data-pluma-floating-video');
        for(let node=video.parentElement;node;node=node.parentElement)
            mark(node,'data-pluma-floating-path');
    }
    select(videos[0]);
    state.style=document.createElement('style');
    state.style.textContent=[
        'html,body{margin:0!important;overflow:hidden!important;background:#000!important}',
        'body *:not([data-pluma-floating-path]):not([data-pluma-floating-video]){visibility:hidden!important}',
        '[data-pluma-floating-path]{transform:none!important;filter:none!important;perspective:none!important;',
        'contain:none!important;clip-path:none!important;opacity:1!important;',
        'overflow:visible!important;will-change:auto!important}',
        '[data-pluma-floating-video]{visibility:visible!important;position:fixed!important;inset:0!important;',
        'width:100vw!important;height:100vh!important;max-width:none!important;',
        'max-height:none!important;min-width:0!important;min-height:0!important;',
        'margin:0!important;padding:0!important;object-fit:contain!important;',
        'background:#000!important;z-index:2147483647!important;pointer-events:auto!important}'
    ].join('');
    document.documentElement.append(state.style);
    function metadata(event){
        if(event.target instanceof HTMLVideoElement && event.target!==state.video){
            const v=event.target,r=v.getBoundingClientRect();
            if(r.width>0 && r.height>0 &&
               (!state.video.isConnected || (!v.paused && state.video.paused))) select(v);
        }
    }
    document.addEventListener('loadedmetadata',metadata,true);
    state.restore=()=>{
        document.removeEventListener('loadedmetadata',metadata,true);
        clearMarks();
        state.style.remove();
        if(window[key]===state) delete window[key];
    };
    window[key]=state;
    return true;
})()
"""

RESTORE_VIDEO = "(()=>{const s=window.__plumaFloatingVideo;if(s)s.restore();})()"


def media_command(command):
    actions = {
        'play': "if(v.paused)v.play().catch(()=>{});else v.pause();",
        'mute': "v.muted=!v.muted;",
        'back': "v.currentTime=Math.max(0,v.currentTime-10);",
        'forward': "if(Number.isFinite(v.duration))v.currentTime=Math.min(v.duration,v.currentTime+10);",
    }
    return ("(()=>{const s=window.__plumaFloatingVideo;const v=s&&s.video;"
            "if(v&&v.isConnected){" + actions[command] + "}})()")


class FloatingVideoWindow(QMainWindow):
    def __init__(self, tab):
        # No native owner: minimizing the browser must not minimize this frame.
        super().__init__(None, Qt.WindowType.Window | Qt.WindowType.WindowStaysOnTopHint)
        self.tab_ref = weakref.ref(tab)
        self.view = tab.view
        self.restoring = False
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
        self.setWindowTitle('Vídeo flutuante — Pluma')
        self.setMinimumSize(320, 220)
        self.resize(640, 400)
        self.setStyleSheet(tab.window.styleSheet())
        toolbar = QToolBar('Controles do vídeo')
        toolbar.setMovable(False)
        toolbar.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
        self.addToolBar(toolbar)
        for title, command in [('Play/Pausa', 'play'), ('Som', 'mute'), ('−10s', 'back'), ('+10s', 'forward')]:
            action = toolbar.addAction(title, lambda checked=False, c=command: self.command(c))
            action.setToolTip({'play': 'Reproduzir ou pausar', 'mute': 'Ativar ou silenciar áudio',
                               'back': 'Voltar 10 segundos', 'forward': 'Avançar 10 segundos'}[command])
        self.on_top = toolbar.addAction('Fixar')
        self.on_top.setToolTip('Manter por cima das outras janelas')
        self.on_top.setCheckable(True)
        self.on_top.setChecked(True)
        self.on_top.toggled.connect(self.set_on_top)
        toolbar.addAction('Voltar à aba', self.return_to_tab)
        restore = QAction(self)
        restore.setShortcut(QKeySequence('Escape'))
        restore.triggered.connect(self.escape)
        self.addAction(restore)
        tab.layout.removeWidget(self.view)
        self.setCentralWidget(self.view)
        tab.floating_window = self
        tab.floating_placeholder.show()
        self.view.page().setLifecycleState(QWebEnginePage.LifecycleState.Active)
        self.view.show()

    def command(self, value):
        if self.view:
            self.view.page().runJavaScript(media_command(value), WORLD)

    def set_on_top(self, value):
        geometry = self.geometry()
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, value)
        self.setGeometry(geometry)
        self.show()

    def fullscreen(self, request):
        request.accept()
        self.showFullScreen() if request.toggleOn() else self.showNormal()

    def escape(self):
        if self.isFullScreen() and self.view:
            self.view.page().runJavaScript(
                "if(document.fullscreenElement)document.exitFullscreen();", WORLD)
            self.showNormal()
        else:
            self.return_to_tab()

    def return_to_tab(self):
        tab = self.tab_ref()
        self.close()
        import shiboken6
        if tab is not None and shiboken6.isValid(tab):
            tab.window.tabs.setCurrentWidget(tab)
            tab.window.showNormal()
            tab.window.raise_()
            tab.window.activateWindow()

    def restore(self):
        if self.restoring:
            return
        self.restoring = True
        tab = self.tab_ref()
        import shiboken6
        if self.view is not None and shiboken6.isValid(self.view):
            view = self.takeCentralWidget()
            view.page().runJavaScript(RESTORE_VIDEO, WORLD)
            if tab is not None and shiboken6.isValid(tab):
                view.setParent(tab)
                tab.layout.addWidget(view)
                tab.floating_window = None
                tab.floating_placeholder.hide()
                view.show()
                tab.last_active = time.monotonic()
            else:
                view.deleteLater()
        self.view = None

    def closeEvent(self, event):
        self.restore()
        event.accept()
