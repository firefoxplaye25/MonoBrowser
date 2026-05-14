import sys
import os
import time
import threading
import urllib.request
import json
import zipfile
import subprocess
from PyQt5.QtCore import *
from PyQt5.QtWidgets import *
from PyQt5.QtGui import *
from PyQt5.QtWebEngineWidgets import *
from PyQt5.QtWebEngineCore import QWebEngineUrlRequestInterceptor

from mlh_manager import save_mlhjson, load_mlhjson

# --- AdBlocker & Tracker Shield ---
class AdBlockerInterceptor(QWebEngineUrlRequestInterceptor):
    def __init__(self, parent_browser=None):
        super().__init__(parent_browser)
        self.parent_browser = parent_browser
        self.blocked_count = 0
        self.blocked_domains = [
            "doubleclick.net", "google-analytics.com", "googlesyndication.com",
            "facebook.net", "connect.facebook.net", "pixel.facebook.com",
            "taboola.com", "outbrain.com", "criteo.com", "adnxs.com",
            "amazon-adsystem.com", "scorecardresearch.com", "quantserve.com",
            "adform.net", "rubiconproject.com", "advertising.com",
            "adtech.de", "moatads.com", "hotjar.com", "clarity.ms",
            "adition.com", "adzerk.net", "yieldmanager.com", "ads-twitter.com",
            "analytics.twitter.com"
        ]

    def interceptRequest(self, info):
        if self.parent_browser and not getattr(self.parent_browser, 'adblock_enabled', True):
            return

        url = info.requestUrl()
        host = url.host()
        
        for domain in self.blocked_domains:
            if host == domain or host.endswith('.' + domain):
                info.block(True)
                self.blocked_count += 1
                if self.parent_browser:
                    QMetaObject.invokeMethod(self.parent_browser, "update_shield_count", Qt.QueuedConnection)
                return

class CustomWebEnginePage(QWebEnginePage):
    def certificateError(self, error):
        error.ignoreCertificateError()
        return True

class BrowserTab(QWebEngineView):
    def __init__(self, parent_browser, profile):
        super().__init__()
        self.parent_browser = parent_browser
        page = CustomWebEnginePage(profile, self)
        self.setPage(page)
        page.featurePermissionRequested.connect(self.on_feature_permission_requested)
        page.linkHovered.connect(self.parent_browser.show_status_message)
        
        self.urlChanged.connect(self.update_urlbar)
        self.titleChanged.connect(self.update_title)
        self.loadStarted.connect(self.on_load_started)
        self.loadProgress.connect(self.update_progress)
        self.loadFinished.connect(self.on_load_finished)

    def on_feature_permission_requested(self, url, feature):
        self.page().setFeaturePermission(url, feature, QWebEnginePage.PermissionGrantedByUser)

    def createWindow(self, webWindowType):
        new_browser = self.parent_browser.add_new_tab(QUrl(""), "Carregando...")
        return new_browser

    def update_urlbar(self, q):
        if self.parent_browser.tabs.currentWidget() == self:
            self.parent_browser.urlbar.setText(q.toString())
            self.parent_browser.urlbar.setCursorPosition(0)
            self.parent_browser.update_secure_indicator(q)

    def update_title(self, title):
        index = self.parent_browser.tabs.indexOf(self)
        if index != -1:
            if len(title) > 25:
                title = title[:22] + "..."
            self.parent_browser.tabs.setTabText(index, title)

    def on_load_started(self):
        if self.parent_browser.tabs.currentWidget() == self:
            self.parent_browser.show_status_message(f"Carregando: {self.url().host()}...")

    def update_progress(self, progress):
        if self.parent_browser.tabs.currentWidget() == self:
            self.parent_browser.progress_bar.setValue(progress)
            self.parent_browser.progress_bar.setVisible(progress < 100)

    def on_load_finished(self, ok):
        if self.parent_browser.tabs.currentWidget() == self:
            self.parent_browser.progress_bar.setVisible(False)
            if ok:
                self.parent_browser.show_status_message("Concluído")
            else:
                self.parent_browser.show_status_message("Erro de conexão. Carregando modo offline.")
                offline_path = QUrl.fromLocalFile(os.path.join(os.path.dirname(__file__), "offline_game.html"))
                if self.url() != offline_path:
                    self.setUrl(offline_path)

class MonoLithiiunExplorer(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("MonoLithiiun Explorer")
        
        def get_icon(name):
            path = os.path.join(os.path.dirname(__file__), name)
            if os.path.exists(path):
                return QIcon(path)
            return QIcon()

        self.setWindowIcon(get_icon("Principalappico.ico"))
        self.icon_obj = get_icon("Principalappico.ico")
        
        self.config_path = os.path.join(os.path.dirname(__file__), 'config.mlhjson')
        self.history_path = os.path.join(os.path.dirname(__file__), 'history.mlhjson')
        self.account_path = os.path.join(os.path.dirname(__file__), 'account.mlhjson')
        self.bookmarks_path = os.path.join(os.path.dirname(__file__), 'bookmarks.mlhjson')
        self.downloads_path = os.path.join(os.path.dirname(__file__), 'downloads.mlhjson')
        
        self.config = load_mlhjson(self.config_path, default_data={
            "homepage": "https://www.google.com",
            "search_engine": "https://www.google.com/search?q=",
            "first_run": True,
            "adblock_enabled": True,
            "js_enabled": True,
            "multi_user_mode": False,
            "run_in_background": True,
            "auto_update": True,
            "run_on_startup": False
        })
        self.history = load_mlhjson(self.history_path, default_data={"urls": []})
        self.account = load_mlhjson(self.account_path, default_data={"email": "", "synced": False})
        self.bookmarks = load_mlhjson(self.bookmarks_path, default_data={"items": []})
        self.downloads = load_mlhjson(self.downloads_path, default_data={"items": []})

        self.adblock_enabled = self.config.get("adblock_enabled", True)

        self.profile = QWebEngineProfile.defaultProfile()
        self.profile.setHttpUserAgent("Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:115.0) Gecko/20100101 Firefox/115.0")
        
        settings = self.profile.settings()
        settings.setAttribute(QWebEngineSettings.PluginsEnabled, True)
        settings.setAttribute(QWebEngineSettings.JavascriptEnabled, self.config.get("js_enabled", True))
        settings.setAttribute(QWebEngineSettings.JavascriptCanAccessClipboard, True)
        settings.setAttribute(QWebEngineSettings.LocalStorageEnabled, True)
        settings.setAttribute(QWebEngineSettings.WebGLEnabled, True)
        settings.setAttribute(QWebEngineSettings.FullScreenSupportEnabled, True)
        settings.setAttribute(QWebEngineSettings.AllowRunningInsecureContent, True)
        settings.setAttribute(QWebEngineSettings.LocalContentCanAccessRemoteUrls, True)
        settings.setAttribute(QWebEngineSettings.LocalContentCanAccessFileUrls, True)
        settings.setAttribute(QWebEngineSettings.Accelerated2dCanvasEnabled, True)
        settings.setAttribute(QWebEngineSettings.PlaybackRequiresUserGesture, False)
        settings.setAttribute(QWebEngineSettings.AllowWindowActivationFromJavaScript, True)

        self.profile.downloadRequested.connect(self.on_download_requested)
        
        self.adblocker = AdBlockerInterceptor(self)
        self.profile.setRequestInterceptor(self.adblocker)

        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)
        self.tabs.tabBarDoubleClicked.connect(self.tab_open_doubleclick)
        self.tabs.currentChanged.connect(self.current_tab_changed)
        self.tabs.setTabsClosable(True)
        self.tabs.tabCloseRequested.connect(self.close_current_tab)
        
        navtb = QToolBar("Navigation")
        navtb.setIconSize(QSize(18, 18))
        self.addToolBar(navtb)

        back_btn = QAction("Back", self)
        back_btn.triggered.connect(lambda: self.tabs.currentWidget().back() if self.tabs.currentWidget() else None)
        navtb.addAction(back_btn)

        next_btn = QAction("Forward", self)
        next_btn.triggered.connect(lambda: self.tabs.currentWidget().forward() if self.tabs.currentWidget() else None)
        navtb.addAction(next_btn)

        reload_btn = QAction("Reload", self)
        reload_btn.triggered.connect(lambda: self.tabs.currentWidget().reload() if self.tabs.currentWidget() else None)
        navtb.addAction(reload_btn)

        home_btn = QAction("Home", self)
        home_btn.triggered.connect(self.navigate_home)
        navtb.addAction(home_btn)

        navtb.addSeparator()

        self.secure_label = QLabel("")
        navtb.addWidget(self.secure_label)

        self.urlbar = QLineEdit()
        self.urlbar.setPlaceholderText("Search or type URL")
        self.urlbar.returnPressed.connect(self.navigate_to_url)
        navtb.addWidget(self.urlbar)
        
        star_btn = QAction("⭐", self)
        star_btn.triggered.connect(self.add_bookmark)
        navtb.addAction(star_btn)
        
        self.mute_btn = QAction("🔊 Som", self)
        self.mute_btn.triggered.connect(self.toggle_mute)
        navtb.addAction(self.mute_btn)
        
        self.shield_label = QLabel(f"🛡️ 0 {'(ON)' if self.adblock_enabled else '(OFF)'}")
        self.shield_label.setStyleSheet("color: #FF9800; font-weight: bold; font-size: 13px; padding-left: 8px;")
        navtb.addWidget(self.shield_label)

        new_tab_btn = QAction("New Tab", self)
        new_tab_btn.triggered.connect(lambda: self.add_new_tab(QUrl(self.config.get("homepage")), "New Tab"))
        navtb.addAction(new_tab_btn)
        
        menu_btn = QToolButton()
        menu_btn.setText("Menu")
        menu = QMenu()
        
        bm_action = QAction("Marcadores / Favoritos", self)
        bm_action.triggered.connect(self.show_bookmarks)
        menu.addAction(bm_action)

        dl_action = QAction("Downloads", self)
        dl_action.triggered.connect(self.show_downloads)
        menu.addAction(dl_action)
        
        menu.addSeparator()

        history_action = QAction(get_icon("history.png"), "History", self)
        history_action.triggered.connect(self.show_history)
        menu.addAction(history_action)
        
        source_action = QAction(get_icon("Sourcecodewindow.ico"), "View Source", self)
        source_action.triggered.connect(self.view_source)
        menu.addAction(source_action)
        
        inspect_action = QAction(get_icon("devtools.png"), "Inspect Element", self)
        inspect_action.triggered.connect(self.inspect_element)
        menu.addAction(inspect_action)
        
        sync_action = QAction(get_icon("accountsync.png"), "Account & Sync", self)
        sync_action.triggered.connect(self.account_sync)
        menu.addAction(sync_action)
        
        menu.addSeparator()

        self.js_action = QAction("JavaScript Habilitado", self, checkable=True)
        self.js_action.setChecked(self.config.get("js_enabled", True))
        self.js_action.triggered.connect(self.toggle_js)
        menu.addAction(self.js_action)
        
        toggle_adblock_action = QAction("Ativar/Desativar AdBlock", self)
        toggle_adblock_action.triggered.connect(self.toggle_adblock)
        menu.addAction(toggle_adblock_action)

        search_menu = QMenu("Buscador Padrão", self)
        google_action = QAction("Google", self)
        google_action.triggered.connect(lambda: self.set_search_engine("https://www.google.com/search?q="))
        duck_action = QAction("DuckDuckGo", self)
        duck_action.triggered.connect(lambda: self.set_search_engine("https://duckduckgo.com/?q="))
        bing_action = QAction("Bing", self)
        bing_action.triggered.connect(lambda: self.set_search_engine("https://www.bing.com/search?q="))
        search_menu.addAction(google_action)
        search_menu.addAction(duck_action)
        search_menu.addAction(bing_action)
        menu.addMenu(search_menu)

        menu.addSeparator()

        self.bg_action = QAction("Segundo Plano (Abertura Rápida)", self, checkable=True)
        self.bg_action.setChecked(self.config.get("run_in_background", True))
        self.bg_action.triggered.connect(self.toggle_bg)
        menu.addAction(self.bg_action)

        self.update_toggle_action = QAction("Auto-Atualizações", self, checkable=True)
        self.update_toggle_action.setChecked(self.config.get("auto_update", True))
        self.update_toggle_action.triggered.connect(self.toggle_auto_update)
        menu.addAction(self.update_toggle_action)

        self.startup_action = QAction("Iniciar com o Windows (Fundo)", self, checkable=True)
        self.startup_action.setChecked(self.config.get("run_on_startup", False))
        self.startup_action.triggered.connect(self.toggle_startup)
        menu.addAction(self.startup_action)

        update_action = QAction("Forçar Busca de Updates", self)
        update_action.triggered.connect(lambda: self.perform_background_update_check(manual=True))
        menu.addAction(update_action)
        
        menu_btn.setMenu(menu)
        menu_btn.setPopupMode(QToolButton.InstantPopup)
        navtb.addWidget(menu_btn)

        central_widget = QWidget()
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setMaximumHeight(4)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setVisible(False)
        self.progress_bar.setStyleSheet("QProgressBar { border: none; background-color: transparent; } QProgressBar::chunk { background-color: #007acc; }")
        
        layout.addWidget(self.progress_bar)
        layout.addWidget(self.tabs)
        central_widget.setLayout(layout)
        self.setCentralWidget(central_widget)

        self.statusBar = QStatusBar()
        self.setStatusBar(self.statusBar)

        self.setStyleSheet("""
            QMainWindow { background-color: #1e1e1e; color: #ffffff; }
            QToolBar { background-color: #252526; border: none; padding: 6px; }
            QLineEdit { background-color: #333333; color: #ffffff; border: 1px solid #555555; border-radius: 14px; padding: 6px 14px; font-size: 14px; }
            QLineEdit:focus { border: 1px solid #007acc; }
            QTabBar::tab { background-color: #2d2d30; color: #aaaaaa; padding: 10px 24px; border-top-left-radius: 6px; border-top-right-radius: 6px; margin-right: 2px; }
            QTabBar::tab:selected { background-color: #1e1e1e; color: #ffffff; border-bottom: 2px solid #007acc; }
            QPushButton, QToolButton { background-color: transparent; color: #ffffff; padding: 6px; border-radius: 6px; font-size: 13px; }
            QPushButton:hover, QToolButton:hover { background-color: #3e3e42; }
            QMenu { background-color: #2d2d30; color: #ffffff; border: 1px solid #3e3e42; }
            QMenu::item:selected { background-color: #007acc; }
            QStatusBar { background-color: #1e1e1e; color: #aaaaaa; }
            QMessageBox { background-color: #2d2d30; color: #ffffff; }
            QMessageBox QLabel { color: #ffffff; }
            QMessageBox QPushButton { background-color: #007acc; border-radius: 4px; padding: 6px 15px; color: white; min-width: 80px; }
            QMessageBox QPushButton:hover { background-color: #005999; }
        """)

        # System Tray for Background Play
        self.tray_icon = QSystemTrayIcon(self.icon_obj, self)
        tray_menu = QMenu()
        restore_action = QAction("Restaurar MonoLithiiun", self)
        restore_action.triggered.connect(self.showMaximized)
        quit_action = QAction("Sair Totalmente", self)
        quit_action.triggered.connect(qApp.quit)
        tray_menu.addAction(restore_action)
        tray_menu.addAction(quit_action)
        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.activated.connect(self.tray_activated)
        self.tray_icon.show()

        self.fullscreen_shortcut = QShortcut(QKeySequence("F11"), self)
        self.fullscreen_shortcut.activated.connect(self.toggle_fullscreen)
        self.esc_shortcut = QShortcut(QKeySequence("Esc"), self)
        self.esc_shortcut.activated.connect(self.exit_fullscreen)
        self.fs_popup = QLabel("Você está em tela cheia.\nAperte F11 ou ESC para sair.", self)
        self.fs_popup.setStyleSheet("background-color: rgba(0, 0, 0, 200); color: white; padding: 20px; border-radius: 10px; font-size: 18px; font-weight: bold;")
        self.fs_popup.setAlignment(Qt.AlignCenter)
        self.fs_popup.hide()

        # Keyboard Shortcuts
        QShortcut(QKeySequence("Ctrl+T"), self).activated.connect(lambda: self.add_new_tab(QUrl(self.config.get("homepage")), "New Tab"))
        QShortcut(QKeySequence("Ctrl+W"), self).activated.connect(lambda: self.close_current_tab(self.tabs.currentIndex()))
        QShortcut(QKeySequence("Ctrl+R"), self).activated.connect(lambda: self.tabs.currentWidget().reload() if self.tabs.currentWidget() else None)
        QShortcut(QKeySequence("F5"), self).activated.connect(lambda: self.tabs.currentWidget().reload() if self.tabs.currentWidget() else None)
        QShortcut(QKeySequence("Ctrl+Shift+I"), self).activated.connect(self.inspect_element)
        QShortcut(QKeySequence("Ctrl+H"), self).activated.connect(self.show_history)
        QShortcut(QKeySequence("Ctrl+D"), self).activated.connect(self.add_bookmark)
        QShortcut(QKeySequence("Ctrl+J"), self).activated.connect(self.show_downloads)

        self.inspector_windows = []
        self.add_new_tab(QUrl(self.config.get("homepage")), "Home")
        
        if "--background" in sys.argv:
            self.tray_icon.showMessage("MonoLithiiun Explorer", "Iniciado com o Windows. Procurando atualizações...", QSystemTrayIcon.Information, 3000)
        else:
            self.showMaximized()
        
        if self.config.get("first_run", True):
            QTimer.singleShot(1000, self.run_first_time_setup)
            
        if self.config.get("auto_update", True):
            QTimer.singleShot(8000, self.perform_background_update_check)
            
        if "--just-updated" in sys.argv:
            QTimer.singleShot(2000, lambda: QMessageBox.information(self, "Sucesso", "Navegador atualizado com sucesso para a versão mais recente! Bem-vindo de volta."))

    def tray_activated(self, reason):
        if reason == QSystemTrayIcon.DoubleClick:
            self.showMaximized()

    def run_first_time_setup(self):
        msg = QMessageBox(self)
        msg.setWindowTitle("Bem-vindo ao MonoLithiiun Explorer!")
        msg.setIcon(QMessageBox.Information)
        msg.setText("Bem-vindo ao seu novo navegador ultra rápido!\n\n"
                    "Dicas de Ouro:\n"
                    "1. Para fixar na sua barra de tarefas, clique com o botão direito no ícone abaixo e selecione 'Fixar'.\n"
                    "2. Configure-o como padrão nas configurações do Windows.\n\n"
                    "Por fim, escolha como deseja o sistema de contas:")
        btn_users = msg.addButton("Usuários Separados (Exige Login)", QMessageBox.ActionRole)
        btn_direct = msg.addButton("Modo Direto (Atual)", QMessageBox.ActionRole)
        msg.exec_()
        
        if msg.clickedButton() == btn_users:
            self.config["multi_user_mode"] = True
            QMessageBox.information(self, "Modo Ativado", "Modo de usuários ativado! O sistema pedirá perfil nas próximas sessões.")
        else:
            self.config["multi_user_mode"] = False
            
        self.config["first_run"] = False
        save_mlhjson(self.config_path, self.config)

    def toggle_mute(self):
        current_page = self.tabs.currentWidget().page()
        is_muted = not current_page.isAudioMuted()
        current_page.setAudioMuted(is_muted)
        self.mute_btn.setText("🔇 Muted" if is_muted else "🔊 Som")
        self.show_status_message("Aba silenciada!" if is_muted else "Aba com som!")

    def toggle_adblock(self):
        self.adblock_enabled = not self.adblock_enabled
        self.config["adblock_enabled"] = self.adblock_enabled
        save_mlhjson(self.config_path, self.config)
        status = "ATIVADO" if self.adblock_enabled else "DESATIVADO"
        self.shield_label.setText(f"🛡️ {self.adblocker.blocked_count} {'(ON)' if self.adblock_enabled else '(OFF)'}")
        QMessageBox.information(self, "AdBlock", f"Bloqueador de Anúncios e Rastreadores {status}!\nRecarregue a aba para aplicar.")

    def toggle_bg(self):
        bg = not self.config.get("run_in_background", True)
        self.config["run_in_background"] = bg
        save_mlhjson(self.config_path, self.config)
        self.bg_action.setChecked(bg)

    def set_search_engine(self, engine_url):
        self.config["search_engine"] = engine_url
        save_mlhjson(self.config_path, self.config)
        QMessageBox.information(self, "Buscador", "Mecanismo de busca atualizado com sucesso!")

    def toggle_startup(self):
        import subprocess
        en = not self.config.get("run_on_startup", False)
        self.config["run_on_startup"] = en
        save_mlhjson(self.config_path, self.config)
        self.startup_action.setChecked(en)
        
        startup_folder = os.path.join(os.environ["APPDATA"], "Microsoft\\Windows\\Start Menu\\Programs\\Startup")
        shortcut_path = os.path.join(startup_folder, "MonoLithiiun Explorer.lnk")
        
        if en:
            try:
                ps_script = f'$WshShell = New-Object -comObject WScript.Shell; $Shortcut = $WshShell.CreateShortcut("{shortcut_path}"); $Shortcut.TargetPath = "{sys.executable}"; $Shortcut.Arguments = "--background"; $Shortcut.WorkingDirectory = "{os.path.dirname(sys.executable)}"; $Shortcut.Save()'
                subprocess.run(["powershell", "-Command", ps_script], creationflags=subprocess.CREATE_NO_WINDOW)
                QMessageBox.information(self, "Windows", "Configurado para iniciar (minimizado) junto com o PC!")
            except Exception as e:
                print("Erro", e)
        else:
            if os.path.exists(shortcut_path):
                try: os.remove(shortcut_path)
                except: pass
            QMessageBox.information(self, "Windows", "Removido da inicialização do sistema.")

    def toggle_auto_update(self):
        au = not self.config.get("auto_update", True)
        self.config["auto_update"] = au
        save_mlhjson(self.config_path, self.config)
        self.update_toggle_action.setChecked(au)

    def toggle_js(self):
        js = not self.config.get("js_enabled", True)
        self.config["js_enabled"] = js
        self.profile.settings().setAttribute(QWebEngineSettings.JavascriptEnabled, js)
        save_mlhjson(self.config_path, self.config)
        self.js_action.setChecked(js)
        QMessageBox.information(self, "JavaScript", f"JavaScript {'ativado' if js else 'desativado'}!\nRecarregue a página.")

    def toggle_fullscreen(self):
        if self.isFullScreen():
            self.exit_fullscreen()
        else:
            self.showFullScreen()
            self.show_fullscreen_popup()

    def exit_fullscreen(self):
        if self.isFullScreen():
            self.showMaximized()
            self.fs_popup.hide()

    def show_fullscreen_popup(self):
        self.fs_popup.adjustSize()
        self.fs_popup.move(self.width() // 2 - self.fs_popup.width() // 2, 50)
        self.fs_popup.show()
        self.fs_popup.raise_()
        QTimer.singleShot(3500, self.fs_popup.hide)

    @pyqtSlot()
    def update_shield_count(self):
        if self.adblock_enabled:
            self.shield_label.setText(f"🛡️ {self.adblocker.blocked_count} (ON)")

    def update_secure_indicator(self, qurl):
        scheme = qurl.scheme()
        host = qurl.host().lower()
        
        # Antivírus Hardcoded Básico (Lista de domínios exatos e extensões suspeitas)
        known_malicious_domains = [
            "free-robux-hack-now.com", "update-your-flash-player.net", "win-iphone-now.xyz",
            "fake-bank-login.biz", "download-more-ram.com", "your-pc-is-infected.info"
        ]
        
        # Bloqueia se for um domínio da lista ou TLDs notórios de spam que não usam https
        if host in known_malicious_domains or (scheme == "http" and (host.endswith(".tk") or host.endswith(".ml") or host.endswith(".ga"))):
            self.secure_label.setText("⚠️ PERIGOSO ")
            self.secure_label.setStyleSheet("color: #F44336; font-weight: bold; font-size: 13px; padding: 0px 5px;")
            return

        if scheme == "https":
            self.secure_label.setText("Segura ")
            self.secure_label.setStyleSheet("color: #4CAF50; font-weight: bold; font-size: 12px; padding: 0px 5px;")
        elif scheme == "http":
            self.secure_label.setText("Não Segura ")
            self.secure_label.setStyleSheet("color: #F44336; font-weight: bold; font-size: 12px; padding: 0px 5px;")
        elif scheme == "file":
            self.secure_label.setText("Local ")
            self.secure_label.setStyleSheet("color: #2196F3; font-weight: bold; font-size: 12px; padding: 0px 5px;")
        else:
            self.secure_label.setText("")

    def show_status_message(self, text):
        if text:
            self.statusBar.showMessage(text)
        else:
            self.statusBar.clearMessage()

    def on_download_requested(self, download_item):
        path, _ = QFileDialog.getSaveFileName(self, "Salvar Arquivo", download_item.suggestedFileName())
        if path:
            download_item.setPath(path)
            download_item.accept()
            self.downloads["items"].append(path)
            save_mlhjson(self.downloads_path, self.downloads)
            
            # Popup menor e fixo no canto inferior direito
            progress_dialog = QProgressDialog("Iniciando...", "Ocultar", 0, 100, self)
            progress_dialog.setWindowTitle("Baixando...")
            progress_dialog.setWindowModality(Qt.NonModal)
            progress_dialog.setMinimumDuration(0)
            progress_dialog.setValue(0)
            progress_dialog.setFixedSize(300, 100)
            progress_dialog.start_time = time.time()
            
            # Posiciona no canto inferior direito
            geo = self.geometry()
            progress_dialog.move(geo.right() - 320, geo.bottom() - 120)
            progress_dialog.show()
            self.inspector_windows.append(progress_dialog)

            def update_download_progress(received, total):
                if total > 0:
                    percent = int((received / total) * 100)
                    progress_dialog.setValue(percent)
                    elapsed = time.time() - progress_dialog.start_time
                    if elapsed > 0:
                        speed = received / elapsed
                        if speed > 0:
                            eta_seconds = (total - received) / speed
                            mb_speed = speed / (1024 * 1024)
                            progress_dialog.setLabelText(f"Arquivo: {download_item.suggestedFileName()}\nVelocidade: {mb_speed:.2f} MB/s | Restante: {int(eta_seconds)}s")
            
            download_item.downloadProgress.connect(update_download_progress)
            
            def download_finished():
                progress_dialog.setValue(100)
                progress_dialog.close()
                self.on_download_finished(path)
                
            download_item.finished.connect(download_finished)

    def on_download_finished(self, path):
        self.show_status_message(f"Download concluído: {path}")
        QMessageBox.information(self, "Download Concluído", f"O arquivo foi salvo em:\n{path}")

    def add_bookmark(self):
        current_browser = self.tabs.currentWidget()
        if not current_browser: return
        url = current_browser.url().toString()
        title = current_browser.title()
        urls = [b.get("url") for b in self.bookmarks["items"]]
        if url not in urls:
            self.bookmarks["items"].append({"title": title, "url": url})
            save_mlhjson(self.bookmarks_path, self.bookmarks)
            self.show_status_message("Adicionado aos favoritos! ⭐")
            QMessageBox.information(self, "Favoritos", f"A página '{title}' foi salva nos marcadores com sucesso!")
        else:
            self.show_status_message("Já está nos favoritos.")
            QMessageBox.warning(self, "Favoritos", "Esta página já está salva nos seus favoritos.")

    def show_bookmarks(self):
        dialog = QDialog(self)
        dialog.setWindowTitle("Marcadores")
        dialog.resize(500, 400)
        layout = QVBoxLayout(dialog)
        list_widget = QListWidget()
        for item in self.bookmarks["items"]:
            list_widget.addItem(f"{item['title']} - {item['url']}")
            
        list_widget.itemDoubleClicked.connect(lambda i: self.add_new_tab(QUrl(i.text().split(" - ")[-1])))
        
        layout.addWidget(QLabel("Favoritos Salvos:"))
        layout.addWidget(list_widget)
        dialog.exec_()

    def show_downloads(self):
        dialog = QDialog(self)
        dialog.setWindowTitle("Downloads Recentes")
        dialog.resize(600, 300)
        layout = QVBoxLayout(dialog)
        list_widget = QListWidget()
        for item in reversed(self.downloads["items"]):
            list_widget.addItem(item)
            
        layout.addWidget(QLabel("Arquivos Baixados:"))
        layout.addWidget(list_widget)
        dialog.exec_()

    def add_new_tab(self, qurl=None, label="Blank"):
        if qurl is None:
            qurl = QUrl(self.config.get("homepage"))
        browser = BrowserTab(self, self.profile)
        browser.setUrl(qurl)
        browser.urlChanged.connect(self.add_to_history)
        i = self.tabs.addTab(browser, label)
        self.tabs.setCurrentIndex(i)
        return browser

    def tab_open_doubleclick(self, i):
        if i == -1:
            self.add_new_tab()

    def current_tab_changed(self, i):
        if self.tabs.currentWidget():
            qurl = self.tabs.currentWidget().url()
            self.update_urlbar(qurl, self.tabs.currentWidget())
            is_muted = self.tabs.currentWidget().page().isAudioMuted()
            self.mute_btn.setText("🔇 Muted" if is_muted else "🔊 Som")

    def close_current_tab(self, i):
        if self.tabs.count() < 2:
            return
        self.tabs.removeTab(i)

    def update_urlbar(self, q, browser=None):
        if browser != self.tabs.currentWidget():
            return
        self.urlbar.setText(q.toString())
        self.urlbar.setCursorPosition(0)
        self.update_secure_indicator(q)

    def navigate_home(self):
        self.tabs.currentWidget().setUrl(QUrl(self.config.get("homepage")))

    def navigate_to_url(self):
        text = self.urlbar.text().strip()
        if text.startswith("file:///"):
            q = QUrl(text)
        elif os.path.exists(text) or (len(text) > 2 and text[1] == ":" and text[2] in ["\\", "/"]):
            q = QUrl.fromLocalFile(text)
        elif "." in text and " " not in text:
            q = QUrl.fromUserInput(text)
        else:
            search_url = self.config.get("search_engine") + text.replace(" ", "+")
            q = QUrl(search_url)
        self.tabs.currentWidget().setUrl(q)
        
    def add_to_history(self, qurl):
        url_str = qurl.toString()
        if url_str not in self.history["urls"]:
            self.history["urls"].append(url_str)
            if len(self.history["urls"]) > 300:
                self.history["urls"] = self.history["urls"][-300:]
            save_mlhjson(self.history_path, self.history)

    def get_icon_obj(self, name):
        path = os.path.join(os.path.dirname(__file__), name)
        if os.path.exists(path):
            return QIcon(path)
        return QIcon()

    def show_history(self):
        dialog = QDialog(self)
        dialog.setWindowTitle("History")
        dialog.setWindowIcon(self.get_icon_obj("history.png"))
        dialog.resize(500, 400)
        layout = QVBoxLayout(dialog)
        
        self.history_list_widget = QListWidget()
        self.populate_history_list()
            
        self.history_list_widget.itemDoubleClicked.connect(lambda item: self.add_new_tab(QUrl(item.text())))
        
        layout.addWidget(QLabel("Dê duplo clique para abrir a página:"))
        layout.addWidget(self.history_list_widget)
        
        clear_btn = QPushButton("Limpar Histórico")
        clear_btn.setStyleSheet("background-color: #F44336; color: white;")
        clear_btn.clicked.connect(self.clear_history)
        layout.addWidget(clear_btn)
        
        dialog.exec_()

    def populate_history_list(self):
        self.history_list_widget.clear()
        for url in reversed(self.history["urls"]):
            self.history_list_widget.addItem(url)

    def clear_history(self):
        reply = QMessageBox.question(self, 'Limpar Histórico', 'Tem certeza que deseja apagar todo o histórico de navegação?', QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply == QMessageBox.Yes:
            self.history["urls"] = []
            save_mlhjson(self.history_path, self.history)
            self.populate_history_list()
            self.show_status_message("Histórico apagado com sucesso.")
            QMessageBox.information(self, "Histórico", "O histórico foi limpo com sucesso.")

    def view_source(self):
        current_browser = self.tabs.currentWidget()
        if current_browser:
            current_browser.page().toHtml(self.show_source_code)

    def show_source_code(self, html):
        source_window = QMainWindow(self)
        source_window.setWindowTitle("Source Code")
        source_window.setWindowIcon(self.get_icon_obj("Sourcecodewindow.ico"))
        source_window.resize(800, 600)
        text_edit = QTextEdit()
        text_edit.setReadOnly(True)
        text_edit.setPlainText(html)
        text_edit.setStyleSheet("background-color: #1e1e1e; color: #d4d4d4; font-family: Consolas, monospace;")
        source_window.setCentralWidget(text_edit)
        source_window.show()
        self.inspector_windows.append(source_window)

    def inspect_element(self):
        current_browser = self.tabs.currentWidget()
        if current_browser:
            inspector = QWebEngineView()
            inspector.setWindowTitle("Developer Tools - Inspect")
            inspector.setWindowIcon(self.get_icon_obj("devtools.png"))
            inspector.resize(900, 600)
            current_browser.page().setDevToolsPage(inspector.page())
            inspector.show()
            self.inspector_windows.append(inspector)

    def account_sync(self):
        dialog = QDialog(self)
        dialog.setWindowTitle("Account Sync")
        dialog.setWindowIcon(self.get_icon_obj("accountsync.png"))
        dialog.resize(300, 150)
        layout = QVBoxLayout(dialog)
        
        if self.account.get("synced"):
            status_label = QLabel(f"Sincronizado via: {self.account.get('email', '')}")
            status_label.setStyleSheet("font-size: 14px; color: #4CAF50;")
            layout.addWidget(status_label)
            logout_btn = QPushButton("Logout / Unsync")
            def do_logout():
                self.account["synced"] = False
                self.account["email"] = ""
                save_mlhjson(self.account_path, self.account)
                dialog.accept()
                QMessageBox.information(self, "Sync", "Conta desvinculada com sucesso.")
            logout_btn.clicked.connect(do_logout)
            layout.addWidget(logout_btn)
        else:
            label = QLabel("Digite seu Email para habilitar o MonoLithiiun Sync:")
            label.setWordWrap(True)
            layout.addWidget(label)
            email_input = QLineEdit()
            email_input.setPlaceholderText("exemplo@email.com")
            layout.addWidget(email_input)
            login_btn = QPushButton("Conectar")
            def do_login():
                email = email_input.text().strip()
                if email and "@" in email:
                    self.account["synced"] = True
                    self.account["email"] = email
                    save_mlhjson(self.account_path, self.account)
                    dialog.accept()
                    QMessageBox.information(self, "Sync", f"Sincronização ativada para {email}!")
            login_btn.clicked.connect(do_login)
            layout.addWidget(login_btn)
        dialog.exec_()
        
    def perform_background_update_check(self, manual=False):
        def check():
            try:
                # Carrega info do repositório
                repo_info_path = os.path.join(os.path.dirname(__file__), "repo_info.json")
                if not os.path.exists(repo_info_path):
                    return # Sem config, sem update

                with open(repo_info_path, "r") as f:
                    info = json.load(f)
                    user = info["user"]
                    repo = info["repo"]

                repo_url = f"https://api.github.com/repos/{user}/{repo}/releases/latest"
                
                req = urllib.request.Request(repo_url)
                req.add_header('Accept', 'application/vnd.github.v3+json')
                
                with urllib.request.urlopen(req, timeout=5) as response:
                    data = json.loads(response.read().decode())
                    tag_name = data.get("tag_name", "v1.0.0")
                    download_url = data['assets'][0]['browser_download_url']
                    
                    if tag_name != "v1.0.0":
                        QMetaObject.invokeMethod(self, "prompt_update", Qt.QueuedConnection, Q_ARG(str, download_url))
                    elif manual:
                        QMetaObject.invokeMethod(self, "notify_up_to_date", Qt.QueuedConnection)
            except Exception as e:
                if manual:
                    QMetaObject.invokeMethod(self, "notify_up_to_date", Qt.QueuedConnection)
        threading.Thread(target=check, daemon=True).start()

    @pyqtSlot()
    def notify_up_to_date(self):
        QMessageBox.information(self, "Atualização", "Você já está usando a versão mais recente (v1.0.0) ou o servidor está offline.")

    @pyqtSlot(str)
    def prompt_update(self, download_url):
        reply = QMessageBox.question(self, "Nova Atualização", "Uma nova versão do MonoLithiiun Explorer está disponível!\nDeseja baixar e instalar silenciosamente agora?", QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            threading.Thread(target=self.apply_update, args=(download_url,), daemon=True).start()

    def apply_update(self, download_url):
        try:
            # Baixa o ZIP
            zip_path = os.path.join(os.environ["TEMP"], "monolithiiun_update.zip")
            urllib.request.urlretrieve(download_url, zip_path)
            
            # Extrai pra temp
            extract_dir = os.path.join(os.environ["TEMP"], "monolithiiun_extracted")
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                zip_ref.extractall(extract_dir)
                
            # Cria updater.bat que mata esse processo, substitui arquivos e abre o novo
            current_exe = sys.executable
            current_dir = os.path.dirname(current_exe)
            
            bat_path = os.path.join(os.environ["TEMP"], "updater.bat")
            bat_content = f"""@echo off
timeout /t 2 /nobreak > NUL
xcopy /s /y "{extract_dir}\\*" "{current_dir}\\"
start "" "{current_exe}" --just-updated
del "%~f0"
"""
            with open(bat_path, "w") as f:
                f.write(bat_content)
                
            subprocess.Popen([bat_path], shell=True)
            QMetaObject.invokeMethod(qApp, "quit", Qt.QueuedConnection)
        except Exception as e:
            print("Erro ao atualizar:", e)
            
    def check_for_updates(self):
        self.perform_background_update_check(manual=True)
            
    def closeEvent(self, event):
        if self.config.get("run_in_background", True):
            event.ignore()
            self.hide()
            self.tray_icon.showMessage("MonoLithiiun Explorer", "Abertura Rápida: Rodando levemente no fundo.", QSystemTrayIcon.Information, 2500)
        else:
            event.accept()
            QApplication.quit()

if __name__ == "__main__":
    QCoreApplication.setAttribute(Qt.AA_EnableHighDpiScaling)
    QCoreApplication.setAttribute(Qt.AA_UseHighDpiPixmaps)
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    font = QFont("Segoe UI", 10)
    app.setFont(font)
    QApplication.setApplicationName("MonoLithiiun Explorer")
    window = MonoLithiiunExplorer()
    app.exec_()
