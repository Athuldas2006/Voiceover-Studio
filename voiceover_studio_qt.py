"""PySide6 desktop interface for Voiceover Studio."""

import json
import os
import shutil
import struct
import subprocess
import sys
import tempfile
import threading
import urllib.request
import wave
from datetime import datetime
from pathlib import Path

import pygame
from PySide6.QtCore import QByteArray, QBuffer, QIODevice, QTimer, Qt, QSettings, Signal, Slot
from PySide6.QtGui import QColor, QIcon, QImage, QKeySequence, QPainter, QPixmap, QShortcut
from PySide6.QtWidgets import (
    QApplication, QCheckBox, QComboBox, QDialog, QFileDialog, QFrame,
    QHBoxLayout, QHeaderView, QLabel, QLineEdit, QMainWindow, QMessageBox,
    QProgressBar, QPushButton, QScrollArea, QSlider, QSplitter, QStackedWidget, QStyle,
    QTableWidget, QTableWidgetItem, QTextEdit, QVBoxLayout, QWidget,
)

import voiceover_studio as core


class VoiceoverStudio(QMainWindow):
    """Qt window that keeps Voiceover Studio's existing local workflows."""

    worker_event = Signal(object)

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Voiceover Studio")
        self.setWindowIcon(QIcon(self._brand_pixmap(64)))
        self.resize(1240, 860)
        self.setMinimumSize(980, 700)
        self.setObjectName("MainWindow")

        self.voices = {}
        self.history = core.read_history()
        self.segments = []
        self.selected_index = None
        self.busy = False
        self.previewing = False
        self.cancel_preview = False
        self.closing = False
        self.process = None
        self.process_lock = threading.Lock()
        self.piper_voice_cache = {}
        self.current_preview_file = None
        self.voice_downloads = {}
        self.voice_download_controls = {}
        self.voice_model_sizes = {}
        self.settings = QSettings("VoiceoverStudio", "VoiceoverStudio")
        saved_geometry = self.settings.value("window_geometry")
        if saved_geometry:
            self.restoreGeometry(saved_geometry)
        self.speed = float(self.settings.value("speed", 1.0))
        self.pause = float(self.settings.value("pause", 0.30))
        self.preset = str(self.settings.value("preset", "Narration"))
        self.audio_available = False

        core.BASE_DIR.mkdir(parents=True, exist_ok=True)
        core.VOICES_DIR.mkdir(parents=True, exist_ok=True)
        core.HISTORY_DIR.mkdir(parents=True, exist_ok=True)
        try:
            pygame.mixer.init()
            self.audio_available = True
        except Exception as exc:
            print("Audio initialization error:", exc)

        self._build_ui()
        self.worker_event.connect(self.handle_worker_event)
        self._bind_shortcuts()
        self.refresh_voices()
        self.refresh_history()
        self.update_counter()
        self.preview_cleanup_timer = QTimer(self)
        self.preview_cleanup_timer.setInterval(250)
        self.preview_cleanup_timer.timeout.connect(self._cleanup_finished_preview)

    def _build_ui(self):
        self.setStyleSheet("""
            QMainWindow, QWidget#Root { background: #0D0F14; color: #F3F6FF; }
            QWidget { color: #F3F6FF; font-family: 'Segoe UI'; font-size: 10pt; }
            QFrame#Card { background: #171B24; border: 1px solid #292F3B; border-radius: 12px; }
            QFrame#Inset { background: #11141B; border: 1px solid #292F3B; border-radius: 9px; }
            QLabel#Muted { color: #94A3B8; }
            QLabel#Title { font-size: 15pt; font-weight: 700; }
            QLabel#BrandMark { background: #8B5CF6; color: white; border-radius: 9px; font-size: 16pt; font-weight: 800; }
            QTabBar::tab { background: #171B24; color: #94A3B8; padding: 12px 20px; margin-right: 5px; border-top-left-radius: 8px; border-top-right-radius: 8px; }
            QTabBar::tab:selected { background: #8B5CF6; color: white; }
            QPushButton { background: #1D222D; color: #F3F6FF; border: 1px solid #292F3B; border-radius: 8px; padding: 9px 14px; font-weight: 600; }
            QPushButton:!disabled:hover { background: #2B3953; border-color: #8B5CF6; }
            QPushButton:pressed { background: #8B5CF6; }
            QPushButton:disabled { color: #748099; background: #151C2A; border-color: #222D40; }
            QPushButton#Primary { background: #8B5CF6; border-color: #A78BFA; color: white; }
            QPushButton#Primary:!disabled:hover { background: #A78BFA; border-color: #DDD6FE; }
            QPushButton#Success { background: #176B54; border-color: #238879; }
            QPushButton#Success:!disabled:hover { background: #238879; border-color: #34D399; }
            QPushButton#Success:pressed { background: #10534B; }
            QPushButton#Danger { background: #713B50; border-color: #8A4A62; }
            QPushButton#Danger:!disabled:hover { background: #8A4A62; border-color: #FF8CA0; }
            QPushButton#Danger:pressed { background: #5D3042; }
            QPushButton:checked { background: #38295F; border-color: #8B5CF6; color: #F1F5F9; }
            QLineEdit, QTextEdit, QComboBox, QTableWidget { background: #11141B; color: #F3F6FF; border: 1px solid #292F3B; border-radius: 8px; padding: 8px; selection-background-color: #8B5CF6; }
            QComboBox QAbstractItemView { background: #171B24; color: #F3F6FF; selection-background-color: #8B5CF6; }
            QHeaderView::section { background: #1D222D; color: #DCE3F2; border: 0; padding: 10px; font-weight: 700; }
            QTableWidget { gridline-color: #1D222D; alternate-background-color: #141D2D; }
            QSlider::groove:horizontal { height: 6px; background: #1D222D; border-radius: 3px; }
            QSlider::handle:horizontal { background: #8B5CF6; width: 16px; margin: -5px 0; border-radius: 8px; }
            QProgressBar { background: #1D222D; border: 0; border-radius: 5px; text-align: center; color: #F3F6FF; height: 10px; }
            QProgressBar::chunk { background: #8B5CF6; border-radius: 5px; }
            QCheckBox::indicator { width: 17px; height: 17px; }
            QCheckBox::indicator:unchecked { background: white; border: 1px solid #8390A8; border-radius: 4px; }
            QCheckBox::indicator:checked { background: white; color: #111217; border: 1px solid #8390A8; border-radius: 4px; }
            QScrollBar:vertical { width: 12px; background: #11141B; margin: 2px; }
            QScrollBar::handle:vertical { background: #34425C; min-height: 28px; border-radius: 5px; }
            QScrollBar::handle:vertical:hover { background: #8B5CF6; }
        """)

        root = QWidget()
        root.setObjectName("Root")
        self.setCentralWidget(root)
        shell = QHBoxLayout(root)
        shell.setContentsMargins(12, 12, 12, 12)
        shell.setSpacing(12)

        sidebar = QFrame()
        sidebar.setObjectName("Card")
        sidebar.setFixedWidth(218)
        nav = QVBoxLayout(sidebar)
        nav.setContentsMargins(14, 18, 14, 14)
        nav.setSpacing(8)
        mark = QLabel()
        mark.setObjectName("BrandMark")
        mark.setAlignment(Qt.AlignmentFlag.AlignCenter)
        mark.setFixedSize(38, 38)
        mark.setPixmap(self._brand_pixmap(34))
        brand = QLabel("Voiceover\nStudio")
        brand.setStyleSheet("font-size: 15pt; font-weight: 750;")
        brand_row = QHBoxLayout()
        brand_row.addWidget(mark)
        brand_row.addWidget(brand, 1)
        nav.addLayout(brand_row)
        nav.addSpacing(12)
        nav.addWidget(self._button("New Project", self.new_project, "Primary"))
        nav.addSpacing(10)
        nav.addWidget(self._muted("WORKSPACE"))

        self.pages = QStackedWidget()
        self.nav_buttons = {}
        self.editor_page = self._editor_tab()
        self.timeline_page = self._timeline_tab()
        self.voice_library_page = self._voice_library_page()
        self.history_page = self._history_tab()
        self.help_page = self._help_tab()
        self.settings_page = self._settings_page()
        for key, title, page, icon in (
            ("editor", "Editor", self.editor_page, "edit"),
            ("timeline", "Sentence Timeline", self.timeline_page, "timeline"),
            ("voices", "Voice Library", self.voice_library_page, "voices"),
            ("history", "Generation History", self.history_page, "history"),
            ("help", "Help & Shortcuts", self.help_page, "help"),
            ("settings", "Settings", self.settings_page, "settings"),
        ):
            self.pages.addWidget(page)
            button = self._button(title, lambda k=key: self.show_page(k), icon=icon)
            button.setCheckable(True)
            self.nav_buttons[key] = button
            nav.addWidget(button)
        nav.addStretch(1)
        nav.addWidget(self._muted("Voiceover Studio"))
        shell.addWidget(sidebar)

        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(8, 4, 4, 4)
        content_layout.setSpacing(10)
        header = QHBoxLayout()
        self.page_title = QLabel("Editor")
        self.page_title.setObjectName("Title")
        header.addWidget(self.page_title)
        header.addStretch(1)
        header.addWidget(self._muted("Offline voice generation"))
        header.addWidget(self._button("Settings", lambda: self.show_page("settings")))
        content_layout.addLayout(header)
        content_layout.addWidget(self.pages, 1)

        footer = QVBoxLayout()
        self.progress = QProgressBar()
        self.progress.setTextVisible(False)
        self.progress.setRange(0, 100)
        self.progress_text = QLabel("Ready")
        self.progress_text.setObjectName("Muted")
        footer.addWidget(self.progress)
        footer.addWidget(self.progress_text)
        actions = QHBoxLayout()
        self.timeline_button = self._button("Build Sentence Timeline", self.build_timeline_from_script, "Primary")
        self.preview_button = self._button("Preview Voice   Ctrl+P", self.preview_voice)
        actions.addWidget(self.timeline_button, 1)
        actions.addWidget(self.preview_button, 1)
        actions.addWidget(self._button("Play   Ctrl+Space", self.play_output, "Success"))
        actions.addWidget(self._button("Stop   Esc", self.shortcut_stop, "Danger"))
        footer.addLayout(actions)
        self.status_label = QLabel("Ready")
        self.status_label.setObjectName("Muted")
        footer.addWidget(self.status_label)
        content_layout.addLayout(footer)
        shell.addWidget(content, 1)
        self.show_page(str(self.settings.value("page", "editor")))
    def show_page(self, key):
        if key not in self.nav_buttons:
            key = "editor"
        self.pages.setCurrentWidget({
            "editor": self.editor_page, "timeline": self.timeline_page,
            "voices": self.voice_library_page, "history": self.history_page,
            "help": self.help_page, "settings": self.settings_page,
        }[key])
        for name, button in self.nav_buttons.items():
            button.setChecked(name == key)
        self.page_title.setText({
            "editor": "Editor", "timeline": "Sentence Timeline",
            "voices": "Voice Library", "history": "Generation History",
            "help": "Help & Shortcuts", "settings": "Settings",
        }[key])
        self.settings.setValue("page", key)

    def new_project(self):
        if self.script_text.toPlainText().strip():
            answer = QMessageBox.question(
                self, "New project", "Clear the current script and start a new project?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if answer != QMessageBox.StandardButton.Yes:
                return
        self.script_text.clear()
        self.segments = []
        self.selected_index = None
        self.refresh_timeline()
        self.update_counter()
        self.show_page("editor")
        self.set_status("New project ready")

    def _voice_library_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(4, 10, 4, 8)
        head = QHBoxLayout()
        head.addWidget(self._muted("Installed local Piper voice models"))
        head.addStretch(1)
        head.addWidget(self._button("Refresh", self.refresh_voices))
        head.addWidget(self._button("Browse and Download", self.show_voice_catalog, "Primary"))
        layout.addLayout(head)
        card_layout = QVBoxLayout()
        card_layout.setContentsMargins(14, 14, 14, 14)
        card = self._card(card_layout)
        self.voice_library_table = QTableWidget(0, 2)
        self.voice_library_table.setHorizontalHeaderLabels(["Voice model", "Status"])
        self.voice_library_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.voice_library_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.voice_library_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.voice_library_table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        card_layout.addWidget(self.voice_library_table, 1)
        row = QHBoxLayout()
        row.addWidget(self._button("Preview selected", self.preview_voice))
        row.addWidget(self._button("Delete voice models", self.show_delete_voices_dialog, "Danger"))
        card_layout.addLayout(row)
        layout.addWidget(card, 1)
        return page

    def _settings_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(4, 10, 4, 8)
        card_layout = QVBoxLayout()
        card_layout.setContentsMargins(20, 20, 20, 20)
        card = self._card(card_layout)
        card_layout.addWidget(self._heading("Generation defaults"))
        card_layout.addWidget(self._muted("Choose the preset used for new voiceovers. Changes are saved automatically."))
        card_layout.addWidget(self._muted("Default style preset"))
        self.settings_preset = QComboBox()
        self.settings_preset.addItems(core.PRESETS.keys())
        self.settings_preset.setCurrentText(self.preset if self.preset in core.PRESETS else "Narration")
        self.settings_preset.currentTextChanged.connect(self._settings_preset_changed)
        card_layout.addWidget(self.settings_preset)
        card_layout.addSpacing(12)
        card_layout.addWidget(self._heading("Storage locations"))
        for label, path in (("Voice models", core.VOICES_DIR), ("History and audio", core.HISTORY_DIR)):
            row = QHBoxLayout()
            row.addWidget(QLabel(label))
            location = QLineEdit(str(path))
            location.setReadOnly(True)
            row.addWidget(location, 1)
            card_layout.addLayout(row)
        card_layout.addStretch(1)
        layout.addWidget(card, 1)
        return page

    def _settings_preset_changed(self, name):
        if hasattr(self, "preset_dropdown"):
            self.preset_dropdown.setCurrentText(name)
        else:
            self.apply_preset(name)
        self.settings.setValue("preset", name)

    def _card(self, layout=None):
        card = QFrame()
        card.setObjectName("Card")
        if layout is not None:
            card.setLayout(layout)
        return card

    def _button(self, text, callback, role="", icon=None):
        button = QPushButton(text)
        if role:
            button.setObjectName(role)
        icon_name = self._button_icon_name(icon or text)
        if icon_name:
            button.setIcon(self.style().standardIcon(icon_name))
        button.clicked.connect(lambda _checked=False: callback())
        return button

    @staticmethod
    def _button_icon_name(text):
        label = text.lower()
        if "new project" in label or label == "new":
            return QStyle.StandardPixmap.SP_FileDialogNewFolder
        if "editor" in label or label == "edit" or "open" in label:
            return QStyle.StandardPixmap.SP_DialogOpenButton
        if "timeline" in label:
            return QStyle.StandardPixmap.SP_MediaPlay
        if "download" in label:
            return QStyle.StandardPixmap.SP_DialogSaveButton
        if "delete" in label or "clear" in label or "remove" in label:
            return QStyle.StandardPixmap.SP_DialogCancelButton
        if "voice" in label or "preview" in label:
            return QStyle.StandardPixmap.SP_ComputerIcon if "library" in label or label == "voices" else QStyle.StandardPixmap.SP_MediaPlay
        if "history" in label:
            return QStyle.StandardPixmap.SP_FileIcon
        if "help" in label:
            return QStyle.StandardPixmap.SP_MessageBoxQuestion
        if "setting" in label:
            return QStyle.StandardPixmap.SP_DialogApplyButton
        if "save" in label:
            return QStyle.StandardPixmap.SP_DialogSaveButton
        if "undo" in label:
            return QStyle.StandardPixmap.SP_ArrowBack
        if "redo" in label:
            return QStyle.StandardPixmap.SP_ArrowForward
        if "up" in label:
            return QStyle.StandardPixmap.SP_ArrowUp
        if "down" in label:
            return QStyle.StandardPixmap.SP_ArrowDown
        if "play" in label:
            return QStyle.StandardPixmap.SP_MediaPlay
        if "generate" in label:
            return QStyle.StandardPixmap.SP_MediaPlay
        if "stop" in label:
            return QStyle.StandardPixmap.SP_MediaStop
        if "refresh" in label:
            return QStyle.StandardPixmap.SP_BrowserReload
        if "add" in label or "browse" in label:
            return QStyle.StandardPixmap.SP_FileDialogNewFolder
        return None

    @staticmethod
    def _brand_pixmap(size):
        pixmap = QPixmap(size, size)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor("#8B5CF6"))
        inset = size * 0.04
        painter.drawRoundedRect(inset, inset, size - 2 * inset, size - 2 * inset, size * 0.24, size * 0.24)
        painter.setBrush(QColor("#FFFFFF"))
        bar_width = size * 0.12
        for x, height in ((0.28, 0.30), (0.47, 0.58), (0.66, 0.40)):
            bar_height = size * height
            painter.drawRoundedRect(size * x, (size - bar_height) / 2, bar_width, bar_height, bar_width / 2, bar_width / 2)
        painter.end()
        return pixmap

    @staticmethod
    def _set_native_windows_icon(hwnd, pixmap):
        """Set WM_SETICON directly so Windows uses the app mark in the taskbar."""
        if sys.platform != "win32":
            return None
        import ctypes
        from ctypes import wintypes

        class IconInfo(ctypes.Structure):
            _fields_ = [
                ("fIcon", wintypes.BOOL),
                ("xHotspot", wintypes.DWORD),
                ("yHotspot", wintypes.DWORD),
                ("hbmMask", wintypes.HANDLE),
                ("hbmColor", wintypes.HANDLE),
            ]

        image = pixmap.toImage().convertToFormat(QImage.Format.Format_ARGB32)
        pixel_data = image.bits().tobytes()[:image.sizeInBytes()]
        gdi32 = ctypes.windll.gdi32
        user32 = ctypes.windll.user32
        gdi32.CreateBitmap.argtypes = [ctypes.c_int, ctypes.c_int, wintypes.UINT, wintypes.UINT, ctypes.c_void_p]
        gdi32.CreateBitmap.restype = wintypes.HANDLE
        gdi32.DeleteObject.argtypes = [wintypes.HANDLE]
        user32.CreateIconIndirect.argtypes = [ctypes.POINTER(IconInfo)]
        user32.CreateIconIndirect.restype = wintypes.HANDLE
        user32.SendMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
        set_class_icon = user32.SetClassLongPtrW
        set_class_icon.argtypes = [wintypes.HWND, ctypes.c_int, ctypes.c_void_p]
        set_class_icon.restype = ctypes.c_void_p

        color_bitmap = gdi32.CreateBitmap(image.width(), image.height(), 1, 32, ctypes.c_char_p(pixel_data))
        mask_bitmap = gdi32.CreateBitmap(image.width(), image.height(), 1, 1, None)
        if not color_bitmap or not mask_bitmap:
            if color_bitmap:
                gdi32.DeleteObject(color_bitmap)
            if mask_bitmap:
                gdi32.DeleteObject(mask_bitmap)
            return None
        info = IconInfo(True, 0, 0, mask_bitmap, color_bitmap)
        icon_handle = user32.CreateIconIndirect(ctypes.byref(info))
        gdi32.DeleteObject(color_bitmap)
        gdi32.DeleteObject(mask_bitmap)
        if not icon_handle:
            return None
        user32.SendMessageW(hwnd, 0x0080, 1, icon_handle)  # WM_SETICON / ICON_BIG
        user32.SendMessageW(hwnd, 0x0080, 0, icon_handle)  # WM_SETICON / ICON_SMALL
        set_class_icon(hwnd, -14, icon_handle)  # GCLP_HICON
        set_class_icon(hwnd, -34, icon_handle)  # GCLP_HICONSM
        return icon_handle

    @staticmethod
    def _write_windows_ico(path, pixmap):
        png_buffer = QBuffer()
        png_buffer.open(QIODevice.OpenModeFlag.WriteOnly)
        if not pixmap.save(png_buffer, "PNG"):
            png_buffer.close()
            raise OSError("Could not encode the Voiceover Studio icon.")
        png_data = bytes(png_buffer.data())
        png_buffer.close()
        icon_header = struct.pack("<HHH", 0, 1, 1)
        icon_entry = struct.pack(
            "<BBBBHHII",
            pixmap.width() % 256, pixmap.height() % 256, 0, 0,
            1, 32, len(png_data), 22,
        )
        Path(path).write_bytes(icon_header + icon_entry + png_data)

    @staticmethod
    def _set_windows_window_app_identity(hwnd, app_id, icon_path, relaunch_command):
        """Give Explorer this window's name, relaunch command, and icon."""
        if sys.platform != "win32":
            return
        import ctypes
        import uuid
        from ctypes import wintypes

        class GUID(ctypes.Structure):
            _fields_ = [
                ("Data1", wintypes.DWORD),
                ("Data2", wintypes.WORD),
                ("Data3", wintypes.WORD),
                ("Data4", ctypes.c_ubyte * 8),
            ]

            def __init__(self, value):
                parsed = uuid.UUID(value)
                raw = parsed.bytes_le
                super().__init__(
                    int.from_bytes(raw[0:4], "little"),
                    int.from_bytes(raw[4:6], "little"),
                    int.from_bytes(raw[6:8], "little"),
                    (ctypes.c_ubyte * 8).from_buffer_copy(raw[8:16]),
                )

        class PropertyKey(ctypes.Structure):
            _fields_ = [("fmtid", GUID), ("pid", wintypes.DWORD)]

        class VariantValue(ctypes.Union):
            _fields_ = [("pointer", ctypes.c_void_p), ("integer", ctypes.c_longlong)]

        class PropVariant(ctypes.Structure):
            _fields_ = [
                ("vt", wintypes.WORD),
                ("wReserved1", wintypes.WORD),
                ("wReserved2", wintypes.WORD),
                ("wReserved3", wintypes.WORD),
                ("value", VariantValue),
            ]

        property_store_iid = GUID("886D8EEB-8CF2-4446-8D02-CDBA1DBDCF99")
        app_model_fmtid = "9F4C2855-9F79-4B39-A8D0-E1D42DE1D5F3"
        store = ctypes.c_void_p()
        shell32 = ctypes.windll.shell32
        get_store = shell32.SHGetPropertyStoreForWindow
        get_store.argtypes = [wintypes.HWND, ctypes.POINTER(GUID), ctypes.POINTER(ctypes.c_void_p)]
        get_store.restype = ctypes.c_long
        result = get_store(hwnd, ctypes.byref(property_store_iid), ctypes.byref(store))
        if result < 0 or not store.value:
            raise OSError(f"Could not set the Voiceover Studio taskbar identity (HRESULT {result:#x}).")

        vtable = ctypes.cast(store, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p))).contents
        set_value = ctypes.WINFUNCTYPE(
            ctypes.c_long, ctypes.c_void_p, ctypes.POINTER(PropertyKey), ctypes.POINTER(PropVariant)
        )(vtable[6])
        commit = ctypes.WINFUNCTYPE(ctypes.c_long, ctypes.c_void_p)(vtable[7])
        release = ctypes.WINFUNCTYPE(ctypes.c_ulong, ctypes.c_void_p)(vtable[2])

        def set_string_property(property_id, value):
            key = PropertyKey(GUID(app_model_fmtid), property_id)
            text_value = ctypes.c_wchar_p(value)
            variant = PropVariant()
            variant.vt = 31  # VT_LPWSTR
            variant.value.pointer = ctypes.cast(text_value, ctypes.c_void_p)
            result = set_value(store, ctypes.byref(key), ctypes.byref(variant))
            if result < 0:
                raise OSError(f"Could not set a Voiceover Studio taskbar property (HRESULT {result:#x}).")

        try:
            # Windows requires relaunch command and display name together, and
            # recommends setting relaunch properties before the AppUserModelID.
            set_string_property(2, relaunch_command)  # PKEY_AppUserModel_RelaunchCommand
            set_string_property(4, "Voiceover Studio")  # PKEY_AppUserModel_RelaunchDisplayNameResource
            set_string_property(3, f"{icon_path},0")  # PKEY_AppUserModel_RelaunchIconResource
            set_string_property(5, app_id)  # PKEY_AppUserModel_ID
            result = commit(store)
            if result < 0:
                raise OSError(f"Could not commit Voiceover Studio taskbar properties (HRESULT {result:#x}).")
        finally:
            release(store)

    def _heading(self, text):
        label = QLabel(text)
        label.setObjectName("Title")
        return label

    def _editor_tab(self):
        page = QWidget()
        layout = QHBoxLayout(page)
        layout.setContentsMargins(4, 10, 4, 8)
        layout.setSpacing(12)
        splitter = QSplitter(Qt.Orientation.Horizontal)

        left_layout = QVBoxLayout()
        left_layout.setContentsMargins(18, 18, 18, 18)
        left_layout.setSpacing(10)
        left = self._card(left_layout)
        left_layout.addWidget(self._heading("Script Editor"))
        left_layout.addWidget(self._muted("Write or paste your script"))
        toolbar = QHBoxLayout()
        toolbar.addWidget(self._button("Open", self.open_script))
        toolbar.addWidget(self._button("Save", self.save_script))
        toolbar.addWidget(self._button("Undo", lambda: self.script_text.undo()))
        toolbar.addWidget(self._button("Redo", lambda: self.script_text.redo()))
        toolbar.addStretch(1)
        left_layout.addLayout(toolbar)
        self.script_text = QTextEdit()
        self.script_text.setPlaceholderText("Start writing your voiceover script…")
        self.script_text.textChanged.connect(self.update_counter)
        left_layout.addWidget(self.script_text, 1)
        self.counter_label = self._muted("0 words · 0 characters")
        self.counter_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        left_layout.addWidget(self.counter_label)
        edit_buttons = QHBoxLayout()
        self.generate_button = self._button("Generate Voiceover   Ctrl+Enter", self.generate_voiceover, "Primary")
        edit_buttons.addWidget(self.generate_button, 1)
        edit_buttons.addWidget(self._button("Clear Script", self.clear_script, "Danger"))
        left_layout.addLayout(edit_buttons)
        splitter.addWidget(left)

        right_layout = QVBoxLayout()
        right_layout.setContentsMargins(18, 18, 18, 18)
        right_layout.setSpacing(14)
        right = self._card(right_layout)
        right_layout.addWidget(self._heading("Voice Settings"))
        right_layout.addWidget(self._muted("Voice model"))
        voice_row = QHBoxLayout()
        self.voice_dropdown = QComboBox()
        self.voice_dropdown.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        self.voice_dropdown.setMinimumContentsLength(12)
        voice_row.addWidget(self.voice_dropdown, 1)
        voice_row.addWidget(self._button("Refresh", self.refresh_voices))
        right_layout.addLayout(voice_row)
        right_layout.addWidget(self._button("Browse and Download More Voices", self.show_voice_catalog))
        self.delete_multiple_button = self._button("Delete Multiple Voice Models", self.show_delete_voices_dialog, "Danger")
        right_layout.addWidget(self.delete_multiple_button)
        right_layout.addSpacing(6)
        right_layout.addWidget(self._muted("Style preset"))
        self.preset_dropdown = QComboBox()
        self.preset_dropdown.addItems(core.PRESETS.keys())
        self.preset_dropdown.setCurrentText(self.preset if self.preset in core.PRESETS else "Narration")
        self.preset_dropdown.currentTextChanged.connect(self.apply_preset)
        right_layout.addWidget(self.preset_dropdown)
        self.preset_description = QLabel(core.PRESETS["Narration"][2])
        self.preset_description.setWordWrap(True)
        self.preset_description.setStyleSheet("color: #AFA5FF;")
        right_layout.addWidget(self.preset_description)
        self.speed_label = QLabel()
        right_layout.addWidget(self._slider_row("Speaking speed", 70, 130, round(self.speed * 100), self._speed_changed, self.speed_label))
        self.pause_label = QLabel()
        right_layout.addWidget(self._slider_row("Default sentence pause", 0, 100, round(self.pause * 100), self._pause_changed, self.pause_label))
        tip = self._muted("Tip: Set individual pauses in Sentence Timeline.")
        tip.setWordWrap(True)
        right_layout.addSpacing(8)
        right_layout.addWidget(tip)
        right_layout.addStretch(1)
        settings_scroll = QScrollArea()
        settings_scroll.setWidgetResizable(True)
        settings_scroll.setFrameShape(QFrame.Shape.NoFrame)
        settings_scroll.setWidget(right)
        settings_scroll.setMinimumWidth(320)
        splitter.addWidget(settings_scroll)
        splitter.setSizes([620, 380])
        layout.addWidget(splitter)
        return page

    def _slider_row(self, title, low, high, initial, callback, value_label):
        wrap = QWidget()
        box = QVBoxLayout(wrap)
        box.setContentsMargins(0, 8, 0, 2)
        box.setSpacing(8)
        head = QHBoxLayout()
        head.addWidget(self._muted(title))
        head.addStretch(1)
        head.addWidget(value_label)
        box.addLayout(head)
        slider = QSlider(Qt.Orientation.Horizontal)
        slider.setRange(low, high)
        slider.setValue(initial)
        slider.valueChanged.connect(callback)
        box.addWidget(slider)
        callback(initial)
        return wrap

    def _timeline_tab(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(4, 10, 4, 8)
        header = QHBoxLayout()
        header.addWidget(self._heading("Sentence Timeline"))
        header.addStretch(1)
        self.timeline_info = self._muted("0 sentences")
        header.addWidget(self.timeline_info)
        layout.addLayout(header)
        splitter = QSplitter(Qt.Orientation.Horizontal)

        left_layout = QVBoxLayout()
        left_layout.setContentsMargins(16, 16, 16, 16)
        left = self._card(left_layout)
        left_layout.addWidget(self._heading("Sentences and pauses"))
        self.timeline_table = QTableWidget(0, 3)
        self.timeline_table.setHorizontalHeaderLabels(["#", "Sentence", "Pause"])
        self.timeline_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.timeline_table.setColumnWidth(0, 52)
        self.timeline_table.setColumnWidth(2, 85)
        self.timeline_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.timeline_table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.timeline_table.itemSelectionChanged.connect(self.select_segment)
        left_layout.addWidget(self.timeline_table, 1)
        row = QHBoxLayout()
        row.addWidget(self._button("Add", self.add_segment))
        row.addWidget(self._button("Delete Sentence", self.remove_segment, "Danger"))
        row.addWidget(self._button("↑ Up", lambda: self.move_segment(-1)))
        row.addWidget(self._button("↓ Down", lambda: self.move_segment(1)))
        left_layout.addLayout(row)
        splitter.addWidget(left)

        edit_layout = QVBoxLayout()
        edit_layout.setContentsMargins(18, 18, 18, 18)
        right = self._card(edit_layout)
        edit_layout.addWidget(self._heading("Edit selected sentence"))
        edit_layout.addWidget(self._muted("Edit the text, then apply your changes."))
        self.segment_editor = QTextEdit()
        self.segment_editor.setPlaceholderText("Select a sentence to edit it")
        edit_layout.addWidget(self.segment_editor, 1)
        edit_layout.addWidget(self._button("Apply Sentence Edit", self.apply_segment_edit, "Primary"))
        pause_head = QHBoxLayout()
        pause_head.addWidget(self._muted("Pause after this sentence"))
        pause_head.addStretch(1)
        self.segment_pause_label = QLabel("0.30 seconds")
        pause_head.addWidget(self.segment_pause_label)
        edit_layout.addLayout(pause_head)
        self.segment_pause_slider = QSlider(Qt.Orientation.Horizontal)
        self.segment_pause_slider.setRange(0, 200)
        self.segment_pause_slider.setValue(30)
        self.segment_pause_slider.valueChanged.connect(self.segment_pause_changed)
        edit_layout.addWidget(self.segment_pause_slider)
        edit_layout.addWidget(self._button("Apply Pause", self.apply_segment_pause))
        splitter.addWidget(right)
        splitter.setSizes([700, 420])
        layout.addWidget(splitter, 1)
        return page

    def _history_tab(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(4, 10, 4, 8)
        head = QHBoxLayout()
        head.addWidget(self._heading("Generation History"))
        head.addStretch(1)
        head.addWidget(self._button("Refresh", self.refresh_history))
        layout.addLayout(head)
        card_layout = QVBoxLayout()
        card_layout.setContentsMargins(16, 16, 16, 16)
        card = self._card(card_layout)
        self.history_table = QTableWidget(0, 4)
        self.history_table.setHorizontalHeaderLabels(["Created", "Voice", "Preset", "Sentences"])
        self.history_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.history_table.setColumnWidth(0, 190)
        self.history_table.setColumnWidth(2, 120)
        self.history_table.setColumnWidth(3, 100)
        self.history_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.history_table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.history_table.setAlternatingRowColors(True)
        card_layout.addWidget(self.history_table, 1)
        row = QHBoxLayout()
        row.addWidget(self._button("Load Script", self.load_history_script))
        row.addWidget(self._button("Restore Audio", self.restore_history_audio, "Success"))
        row.addWidget(self._button("Delete Entry", self.delete_history_entry, "Danger"))
        card_layout.addLayout(row)
        layout.addWidget(card, 1)
        return page

    def _help_tab(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(4, 10, 4, 8)
        layout.addWidget(self._heading("Help & Documentation"))
        layout.addWidget(self._muted("Search the guide or select a topic"))
        search = QHBoxLayout()
        self.help_search = QLineEdit()
        self.help_search.setPlaceholderText("Search help topics…   Ctrl+F")
        self.help_search.textChanged.connect(self.filter_help_topics)
        search.addWidget(self.help_search, 1)
        search.addWidget(self._button("Clear", self.clear_help_search))
        layout.addLayout(search)
        splitter = QSplitter(Qt.Orientation.Horizontal)
        self.help_list = QTableWidget(0, 1)
        self.help_list.horizontalHeader().hide()
        self.help_list.verticalHeader().hide()
        self.help_list.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.help_list.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.help_list.itemSelectionChanged.connect(self.select_help_topic)
        splitter.addWidget(self.help_list)
        article_layout = QVBoxLayout()
        article_layout.setContentsMargins(16, 16, 16, 16)
        article = self._card(article_layout)
        self.help_topic_title = self._heading("Getting Started")
        article_layout.addWidget(self.help_topic_title)
        self.help_text = QTextEdit()
        self.help_text.setReadOnly(True)
        self.help_text.setLineWrapMode(QTextEdit.LineWrapMode.WidgetWidth)
        article_layout.addWidget(self.help_text, 1)
        splitter.addWidget(article)
        splitter.setSizes([260, 850])
        layout.addWidget(splitter, 1)
        self.help_topics = list(core.HELP_DOCUMENTATION)
        self.visible_help_topics = self.help_topics[:]
        self.refresh_help_list()
        if self.help_topics:
            self.show_help_topic(self.help_topics[0])
        return page

    @staticmethod
    def _muted(text):
        label = QLabel(text)
        label.setObjectName("Muted")
        return label

    # Script, timeline and voice selection
    def _speed_changed(self, value):
        self.speed = value / 100
        self.settings.setValue("speed", self.speed)
        self.speed_label.setText(f"{self.speed:.2f}×")

    def _pause_changed(self, value):
        self.pause = value / 100
        self.settings.setValue("pause", self.pause)
        self.pause_label.setText(f"{self.pause:.2f}s")

    def apply_preset(self, name):
        preset = core.PRESETS.get(name)
        if not preset:
            return
        speed, pause, description = preset
        self.preset = name
        self.settings.setValue("preset", name)
        self.speed = speed
        self.pause = pause
        self.preset_description.setText(description)
        self._set_slider(self.speed_label, speed, self._speed_changed)
        self._set_slider(self.pause_label, pause, self._pause_changed)
        self.set_status(f"{name} preset selected")

    def _set_slider(self, label, value, callback):
        slider = label.parentWidget().findChild(QSlider)
        if slider:
            slider.blockSignals(True)
            slider.setValue(round(value * 100))
            slider.blockSignals(False)
        callback(round(value * 100))

    def get_script(self):
        return self.script_text.toPlainText().strip()

    def update_counter(self):
        text = self.script_text.toPlainText()
        words = len(text.split())
        sentences = len(core.split_sentences(text)) if text.strip() else 0
        duration = words / max(1, round(150 * self.speed)) * 60
        self.counter_label.setText(
            f"{words} words  |  {len(text)} characters  |  {sentences} sentences  |  about {duration:.0f}s"
        )

    def build_timeline_from_script(self, navigate=True):
        self.segments = [{"text": item, "pause": self.pause} for item in core.split_sentences(self.get_script())]
        self.selected_index = None
        self.refresh_timeline()
        if self.segments:
            if navigate:
                self.show_page("timeline")
            self.timeline_table.selectRow(0)
        self.set_status(f"Timeline created: {len(self.segments)} sentences")

    def refresh_timeline(self):
        self.timeline_table.setRowCount(len(self.segments))
        for index, segment in enumerate(self.segments):
            values = (str(index + 1), segment["text"], f'{segment["pause"]:.2f}s')
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                if column != 1:
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.timeline_table.setItem(index, column, item)
        self.timeline_info.setText(f"{len(self.segments)} sentences")

    def select_segment(self):
        row = self.timeline_table.currentRow()
        if row < 0 or row >= len(self.segments):
            return
        self.selected_index = row
        segment = self.segments[row]
        self.segment_editor.setPlainText(segment["text"])
        self.segment_pause_slider.blockSignals(True)
        self.segment_pause_slider.setValue(round(segment["pause"] * 100))
        self.segment_pause_slider.blockSignals(False)
        self.segment_pause_label.setText(f'{segment["pause"]:.2f} seconds')

    def apply_segment_edit(self):
        index = self.selected_index
        if index is None or not 0 <= index < len(self.segments):
            return
        text = self.segment_editor.toPlainText().strip()
        if not text:
            QMessageBox.warning(self, "Empty sentence", "A sentence cannot be empty.")
            return
        self.segments[index]["text"] = text
        self.refresh_timeline()
        self.timeline_table.selectRow(index)
        self.sync_script()
        self.set_status("Sentence updated")

    def segment_pause_changed(self, value):
        self.segment_pause_label.setText(f"{value / 100:.2f} seconds")

    def apply_segment_pause(self):
        index = self.selected_index
        if index is None or not 0 <= index < len(self.segments):
            return
        self.segments[index]["pause"] = self.segment_pause_slider.value() / 100
        self.refresh_timeline()
        self.timeline_table.selectRow(index)
        self.set_status("Sentence pause updated")

    def add_segment(self):
        row = self.selected_index + 1 if self.selected_index is not None else len(self.segments)
        self.segments.insert(row, {"text": "New sentence", "pause": self.pause})
        self.refresh_timeline()
        self.timeline_table.selectRow(row)
        self.segment_editor.selectAll()
        self.segment_editor.setFocus()
        self.sync_script()

    def remove_segment(self):
        row = self.timeline_table.currentRow()
        if not 0 <= row < len(self.segments):
            row = self.selected_index
        if row is None or not 0 <= row < len(self.segments):
            QMessageBox.information(self, "Delete sentence", "Select a sentence in the timeline first.")
            return
        del self.segments[row]
        self.selected_index = None
        self.refresh_timeline()
        self.segment_editor.clear()
        if self.segments:
            next_row = min(row, len(self.segments) - 1)
            self.timeline_table.setCurrentCell(-1, -1)
            self.timeline_table.selectRow(next_row)
            self.select_segment()
        self.sync_script()
        self.set_status("Sentence deleted from the timeline and script")

    def move_segment(self, direction):
        index = self.selected_index
        target = index + direction if index is not None else -1
        if index is None or not 0 <= target < len(self.segments):
            return
        self.segments[index], self.segments[target] = self.segments[target], self.segments[index]
        self.refresh_timeline()
        self.timeline_table.selectRow(target)
        self.sync_script()

    def sync_script(self):
        text = " ".join(part["text"] for part in self.segments)
        self.script_text.blockSignals(True)
        self.script_text.setPlainText(text)
        self.script_text.blockSignals(False)
        self.update_counter()

    def clear_script(self):
        if not self.script_text.toPlainText():
            return
        if QMessageBox.question(self, "Clear script", "Clear the script and sentence timeline?") != QMessageBox.StandardButton.Yes:
            return
        self.script_text.clear()
        self.segments = []
        self.selected_index = None
        self.refresh_timeline()
        self.update_counter()
        self.set_status("Script cleared")

    def refresh_voices(self):
        previous = self.voice_dropdown.currentText() if hasattr(self, "voice_dropdown") else ""
        self.voices = {
            model.stem: model for model in core.VOICES_DIR.glob("*.onnx")
            if Path(str(model) + ".json").is_file()
        }
        names = sorted(self.voices)
        self.voice_dropdown.clear()
        self.voice_dropdown.addItems(names)
        if previous in self.voices:
            self.voice_dropdown.setCurrentText(previous)
        elif names:
            self.voice_dropdown.setCurrentIndex(0)
        self.delete_multiple_button.setEnabled(bool(names) and not self.busy and not self.previewing)
        if hasattr(self, "voice_library_table"):
            self.voice_library_table.setRowCount(len(names))
            for row, name in enumerate(names):
                self.voice_library_table.setItem(row, 0, QTableWidgetItem(name))
                self.voice_library_table.setItem(row, 1, QTableWidgetItem("Installed"))
        self.set_status(f"Found {len(names)} voice model(s)" if names else "No voice models found")

    def selected_voice(self):
        model = self.voices.get(self.voice_dropdown.currentText())
        if not model or not model.is_file():
            raise ValueError("Select a valid voice model. Both .onnx and matching .onnx.json files must be installed.")
        return model

    def save_script(self):
        path, _ = QFileDialog.getSaveFileName(self, "Save Script", "", "Text files (*.txt);;All files (*)")
        if not path:
            return
        try:
            Path(path).write_text(self.get_script(), encoding="utf-8")
            self.set_status("Script saved")
        except Exception as exc:
            self.show_error("Save error", str(exc))

    def open_script(self):
        path, _ = QFileDialog.getOpenFileName(self, "Open Script", "", "Text files (*.txt);;All files (*)")
        if not path:
            return
        try:
            self.script_text.setPlainText(Path(path).read_text(encoding="utf-8"))
            self.build_timeline_from_script()
            self.set_status("Script loaded and timeline built")
        except Exception as exc:
            self.show_error("Open error", str(exc))

    # Voice model management
    def show_delete_voices_dialog(self):
        names = sorted(self.voices)
        if not names:
            return
        dialog = QDialog(self)
        dialog.setWindowTitle("Delete Voice Models")
        dialog.resize(540, 540)
        layout = QVBoxLayout(dialog)
        layout.addWidget(self._heading("Select voice models to delete"))
        select_all = QCheckBox("Select all models")
        layout.addWidget(select_all)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        inner = QWidget()
        inner_layout = QVBoxLayout(inner)
        checks = {}
        for name in names:
            checkbox = QCheckBox(name)
            checkbox.setProperty("model_name", name)
            checks[name] = checkbox
            inner_layout.addWidget(checkbox)
        inner_layout.addStretch(1)
        scroll.setWidget(inner)
        layout.addWidget(scroll, 1)
        count_label = self._muted("0 selected")
        layout.addWidget(count_label)
        delete = self._button("Delete Selected Voice Models", lambda _checked=False: self._delete_selected_voices(dialog, checks), "Danger")
        cancel = self._button("Cancel", dialog.reject)
        buttons = QHBoxLayout()
        buttons.addWidget(delete)
        buttons.addWidget(cancel)
        layout.addLayout(buttons)

        def update_count():
            selected = sum(box.isChecked() for box in checks.values())
            count_label.setText(f"{selected} selected")
            delete.setEnabled(selected > 0)
            select_all.blockSignals(True)
            select_all.setChecked(selected == len(checks))
            select_all.blockSignals(False)

        def set_all(state):
            for checkbox in checks.values():
                checkbox.setChecked(state)

        for checkbox in checks.values():
            checkbox.stateChanged.connect(update_count)
        select_all.stateChanged.connect(lambda state: set_all(state == Qt.CheckState.Checked.value))
        dialog.exec()

    def _delete_selected_voices(self, dialog, checkboxes):
        selected = [name for name, box in checkboxes.items() if box.isChecked()]
        if not selected:
            return
        if QMessageBox.question(dialog, "Confirm deletion", f"Delete {len(selected)} voice model(s)? This removes their .onnx and .json files.") != QMessageBox.StandardButton.Yes:
            return
        errors = []
        for name in selected:
            model = self.voices.get(name)
            if not model:
                continue
            try:
                self.piper_voice_cache.pop(str(model), None)
                if self.voice_dropdown.currentText() == name:
                    self.voice_dropdown.setCurrentIndex(-1)
                model.unlink(missing_ok=True)
                Path(str(model) + ".json").unlink(missing_ok=True)
            except OSError as exc:
                errors.append(f"{name}: {exc}")
        dialog.accept()
        self.refresh_voices()
        self.set_status(f"Deleted {len(selected) - len(errors)} voice model(s)")
        if errors:
            self.show_error("Some models could not be deleted", "\n".join(errors))

    @staticmethod
    def estimated_voice_size(name):
        quality = name.rsplit("-", 1)[-1]
        estimates = {"x_low": "about 20.6 MB (estimated)", "low": "about 63.1 MB (estimated)", "medium": "about 63.2 MB (estimated)", "high": "about 114 MB (estimated)"}
        if name.startswith("en_US-libritts-high"):
            return "about 137 MB (estimated)"
        if name.startswith("en_US-libritts_r-medium"):
            return "about 151 MB (estimated)"
        return estimates.get(quality, "about 63 MB (estimated)")

    def show_voice_catalog(self):
        if hasattr(self, "catalog_dialog") and self.catalog_dialog.isVisible():
            self.catalog_dialog.raise_()
            self.catalog_dialog.activateWindow()
            return
        dialog = QDialog(self)
        self.catalog_dialog = dialog
        dialog.setWindowTitle("Browse Piper Voice Models")
        dialog.resize(900, 700)
        layout = QVBoxLayout(dialog)
        layout.addWidget(self._heading(f"Browse {len(core.VOICE_CATALOG)} Piper voice models"))
        layout.addWidget(self._muted("Compare model quality and download size, then install the voices you want to use."))
        filter_row = QHBoxLayout()
        filter_row.addWidget(self._muted("Quality"))
        quality = QComboBox()
        quality.addItems(["All qualities", "High", "Medium", "Low"])
        filter_row.addWidget(quality)
        search = QLineEdit()
        search.setPlaceholderText("Search models or languages…")
        filter_row.addWidget(search, 1)
        count = self._muted(f"{len(core.VOICE_CATALOG)} models")
        filter_row.addWidget(count)
        layout.addLayout(filter_row)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        body = QWidget()
        rows_layout = QVBoxLayout(body)
        rows_layout.setSpacing(8)
        controls_by_name = {}
        for model_name, details in core.VOICE_CATALOG.items():
            row = QFrame()
            row.setObjectName("Card")
            row_layout = QHBoxLayout(row)
            info = QVBoxLayout()
            name_label = QLabel(model_name)
            name_label.setStyleSheet("font-size: 11pt; font-weight: 700;")
            info.addWidget(name_label)
            description = QLabel(details.get("description", "Piper voice model"))
            description.setObjectName("Muted")
            info.addWidget(description)
            known_size = self.voice_model_sizes.get(model_name)
            if isinstance(known_size, (int, float)):
                initial_size = self.format_voice_size(known_size)
            else:
                initial_size = known_size or self.estimated_voice_size(model_name)
            size = QLabel(initial_size)
            size.setObjectName("Muted")
            info.addWidget(size)
            row_layout.addLayout(info, 1)
            actions = QVBoxLayout()
            button = self._button("Installed" if model_name in self.voices else "Download", lambda: None, "Primary")
            if model_name in self.voices:
                button.setEnabled(False)
            bar = QProgressBar()
            bar.setTextVisible(False)
            bar.setRange(0, 100)
            bar.hide()
            progress_text = self._muted("")
            progress_text.hide()
            action_row = QHBoxLayout()
            pause_button = self._button("Pause", lambda _checked=False, name=model_name: self.toggle_voice_download_pause(name))
            pause_button.hide()
            cancel_button = self._button("Cancel", lambda _checked=False, name=model_name: self.cancel_voice_download(name), "Danger")
            cancel_button.hide()
            action_row.addWidget(pause_button)
            action_row.addWidget(cancel_button)
            actions.addWidget(button)
            actions.addWidget(bar)
            actions.addWidget(progress_text)
            actions.addLayout(action_row)
            row_layout.addLayout(actions)
            rows_layout.addWidget(row)
            controls_by_name[model_name] = {"button": button, "progress": bar, "progress_text": progress_text, "pause": pause_button, "cancel": cancel_button, "row": row, "description": details.get("description", "")}
            controls_by_name[model_name]["size"] = size
            active_download = self.voice_downloads.get(model_name)
            if active_download:
                button.setText("Downloading…")
                button.setEnabled(False)
                bar.show()
                progress_text.setText("Download in progress")
                progress_text.show()
                pause_button.setText("Resume" if not active_download["paused"].is_set() else "Pause")
                pause_button.show()
                cancel_button.show()
            button.clicked.connect(lambda _checked=False, name=model_name: self.download_voice_model(name))
        rows_layout.addStretch(1)
        scroll.setWidget(body)
        layout.addWidget(scroll, 1)
        footer = QHBoxLayout()
        footer.addStretch(1)
        footer.addWidget(self._button("Close", dialog.accept))
        layout.addLayout(footer)
        self.voice_download_controls = controls_by_name

        def filter_rows(*_args):
            selected_quality = quality.currentText().lower()
            query = search.text().strip().lower()
            visible = 0
            for name, controls in controls_by_name.items():
                model_quality = name.rsplit("-", 1)[-1].lower()
                quality_match = selected_quality == "all qualities" or model_quality == selected_quality
                query_match = not query or query in name.lower() or query in controls["description"].lower()
                show = quality_match and query_match
                controls["row"].setVisible(show)
                visible += int(show)
            count.setText(f"{visible} models")

        quality.currentTextChanged.connect(filter_rows)
        search.textChanged.connect(filter_rows)
        def catalog_closed(_result):
            self.catalog_dialog = None
            self.voice_download_controls = {}

        dialog.finished.connect(catalog_closed)
        threading.Thread(target=self.load_voice_model_sizes, args=(tuple(controls_by_name),), daemon=True).start()
        dialog.exec()

    def load_voice_model_sizes(self, model_names):
        url = "https://raw.githubusercontent.com/rhasspy/piper/master/src/python_run/piper/voices.json"
        try:
            request = urllib.request.Request(url, headers={"User-Agent": "VoiceoverStudio/1.0"})
            with urllib.request.urlopen(request, timeout=15) as response:
                manifest = json.loads(response.read().decode("utf-8"))
            for name in model_names:
                info = manifest.get(name, {})
                total = sum(file.get("size_bytes", 0) for filename, file in info.get("files", {}).items() if filename.endswith((".onnx", ".onnx.json")))
                if total:
                    self.voice_model_sizes[name] = total
                    self.worker_event.emit(("voice_size_info", (name, total)))
        except Exception:
            pass

    @staticmethod
    def format_voice_size(size_bytes):
        return f"{size_bytes / 1_000_000:.1f} MB total download"

    def download_voice_model(self, model_name):
        if model_name in self.voice_downloads:
            return
        details = core.VOICE_CATALOG.get(model_name)
        controls = self.voice_download_controls.get(model_name)
        if not details or not controls:
            return
        state = {"paused": threading.Event(), "cancelled": threading.Event()}
        state["paused"].set()
        self.voice_downloads[model_name] = state
        controls["button"].setText("Downloading…")
        controls["button"].setEnabled(False)
        controls["progress"].setValue(0)
        controls["progress"].show()
        controls["progress_text"].setText("Starting download")
        controls["progress_text"].show()
        controls["pause"].show()
        controls["cancel"].show()
        threading.Thread(target=self._download_voice_files, args=(model_name, details["path"], state), daemon=True).start()

    def toggle_voice_download_pause(self, model_name):
        state = self.voice_downloads.get(model_name)
        controls = self.voice_download_controls.get(model_name)
        if not state or not controls:
            return
        if state["paused"].is_set():
            state["paused"].clear()
            controls["pause"].setText("Resume")
            self.set_status(f"Paused download: {model_name}")
        else:
            state["paused"].set()
            controls["pause"].setText("Pause")
            self.set_status(f"Resumed download: {model_name}")

    def cancel_voice_download(self, model_name):
        state = self.voice_downloads.get(model_name)
        if state:
            state["cancelled"].set()
            state["paused"].set()

    def _download_voice_files(self, model_name, model_path, state):
        model = core.VOICES_DIR / f"{model_name}.onnx"
        config = Path(str(model) + ".json")
        temps = [Path(str(model) + ".download"), Path(str(config) + ".download")]
        try:
            core.VOICES_DIR.mkdir(parents=True, exist_ok=True)
            for index, (filename, temp) in enumerate(zip((model.name, config.name), temps)):
                if state["cancelled"].is_set():
                    raise InterruptedError("Download cancelled")
                url = f"https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/{model_path}/{filename}"
                request = urllib.request.Request(url, headers={"User-Agent": "VoiceoverStudio/1.0"})
                with urllib.request.urlopen(request, timeout=60) as response, temp.open("wb") as output:
                    total = int(response.headers.get("Content-Length", 0) or 0)
                    received = 0
                    stage = "Model" if index == 0 else "Config"
                    self.worker_event.emit(("voice_download_progress", (model_name, stage, 0, total)))
                    while True:
                        while not state["paused"].wait(timeout=0.1):
                            if state["cancelled"].is_set():
                                raise InterruptedError("Download cancelled")
                        if state["cancelled"].is_set():
                            raise InterruptedError("Download cancelled")
                        chunk = response.read(16 * 1024)
                        if not chunk:
                            break
                        output.write(chunk)
                        received += len(chunk)
                        self.worker_event.emit(("voice_download_progress", (model_name, stage, received, total)))
                if temp.stat().st_size < 1024 or (total and received != total):
                    raise RuntimeError(f"Download was incomplete: {filename}")
            if state["cancelled"].is_set():
                raise InterruptedError("Download cancelled")
            os.replace(temps[1], config)
            os.replace(temps[0], model)
            self.worker_event.emit(("voice_download_done", (model_name, None)))
        except Exception as exc:
            for temp in temps:
                try:
                    temp.unlink(missing_ok=True)
                except OSError:
                    pass
            error = "__cancelled__" if state["cancelled"].is_set() else str(exc)
            self.worker_event.emit(("voice_download_done", (model_name, error)))

    def _voice_download_finished(self, name, error):
        self.voice_downloads.pop(name, None)
        controls = self.voice_download_controls.get(name)
        if not controls:
            if error is None:
                self.refresh_voices()
            return
        controls["progress"].hide()
        controls["pause"].hide()
        controls["cancel"].hide()
        if error == "__cancelled__":
            controls["button"].setText("Download")
            controls["button"].setEnabled(True)
            controls["progress_text"].setText("Download cancelled")
            self.set_status(f"Download cancelled: {name}")
        elif error:
            controls["button"].setText("Retry")
            controls["button"].setEnabled(True)
            controls["progress_text"].setText("Download failed")
            self.show_error("Voice download failed", error)
        else:
            self.refresh_voices()
            self.voice_dropdown.setCurrentText(name)
            controls["button"].setText("Installed")
            controls["button"].setEnabled(False)
            controls["progress_text"].setText("Download complete")
            self.set_status(f"Installed {name}")

    def _update_voice_download_progress(self, name, stage, received, total):
        controls = self.voice_download_controls.get(name)
        if not controls:
            return
        bar = controls["progress"]
        if total:
            bar.setRange(0, 100)
            bar.setValue(min(100, round(received * 100 / total)))
            size_text = f"{received / 1_000_000:.1f} / {total / 1_000_000:.1f} MB"
        else:
            bar.setRange(0, 0)
            size_text = f"{received / 1_000_000:.1f} MB"
        controls["progress_text"].setText(f"{stage}: {size_text}")

    # Piper generation, preview and playback
    def generate_to_file(self, text, output_path, model, speed, pause):
        if getattr(sys, "frozen", False):
            from piper import PiperVoice, SynthesisConfig

            model_path = Path(model)
            voice = self.piper_voice_cache.get(str(model_path))
            if voice is None:
                voice = PiperVoice.load(str(model_path))
                self.piper_voice_cache[str(model_path)] = voice
            with wave.open(str(output_path), "wb") as wav_file:
                voice.synthesize_wav(
                    text,
                    wav_file,
                    syn_config=SynthesisConfig(length_scale=1.0 / speed),
                )
                if pause > 0 and wav_file.getnframes() > 0:
                    silence_frames = int(voice.config.sample_rate * pause)
                    wav_file.writeframes(b"\x00\x00" * silence_frames)
            if not Path(output_path).exists() or Path(output_path).stat().st_size == 0:
                raise RuntimeError("Piper did not create a valid WAV file.")
            return

        command = [sys.executable, "-m", "piper", "--model", str(model), "--output_file", str(output_path), "--length_scale", f"{1.0 / speed:.4f}", "--sentence_silence", f"{pause:.2f}"]
        with self.process_lock:
            if self.closing:
                raise RuntimeError("The app is closing.")
            process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding="utf-8", errors="replace")
            self.process = process
        try:
            _stdout, stderr = process.communicate(input=text)
        finally:
            with self.process_lock:
                if self.process is process:
                    self.process = None
        if process.returncode != 0:
            raise RuntimeError(stderr.strip() or "Piper generation failed.")
        if not Path(output_path).exists() or Path(output_path).stat().st_size == 0:
            raise RuntimeError("Piper did not create a valid WAV file.")

    def generate_voiceover(self):
        if self.busy or self.previewing:
            return
        if not self.get_script():
            QMessageBox.warning(self, "Empty script", "Write a script first.")
            return
        try:
            model = self.selected_voice()
        except Exception as exc:
            self.show_error("Voice model", str(exc))
            return
        if not self.segments:
            self.build_timeline_from_script(navigate=False)
        segments = [{"text": part["text"].strip(), "pause": float(part["pause"])} for part in self.segments if part["text"].strip()]
        if not segments:
            QMessageBox.warning(self, "No sentences", "Build a sentence timeline first.")
            return
        snapshot = {"segments": segments, "script": " ".join(part["text"] for part in segments), "model": str(model), "voice": self.voice_dropdown.currentText(), "speed": self.speed, "preset": self.preset}
        self.busy = True
        self.delete_multiple_button.setEnabled(False)
        self.generate_button.setEnabled(False)
        self.progress.setRange(0, len(segments))
        self.progress.setValue(0)
        self.progress_text.setText(f"Preparing {len(segments)} sentences…")
        self.set_status("Generating sentence by sentence…")
        threading.Thread(target=self.generation_worker, args=(snapshot,), daemon=True).start()

    def generation_worker(self, snapshot):
        temp_output = None
        work_dir = None
        try:
            work_dir = Path(tempfile.mkdtemp(prefix="voiceover_work_", dir=str(core.BASE_DIR)))
            wav_parts = []
            for index, segment in enumerate(snapshot["segments"]):
                if self.closing:
                    raise RuntimeError("Generation cancelled because the app is closing.")
                wav_path = work_dir / f"sentence_{index:04d}.wav"
                self.generate_to_file(segment["text"], wav_path, Path(snapshot["model"]), snapshot["speed"], 0.0)
                wav_parts.append(wav_path)
                self.worker_event.emit(("progress", {"done": index + 1, "total": len(snapshot["segments"])}))
            fd, name = tempfile.mkstemp(suffix=".wav", prefix="voiceover_result_", dir=str(core.BASE_DIR))
            os.close(fd)
            temp_output = Path(name)
            self.combine_wavs(wav_parts, snapshot["segments"], temp_output)
            if not self.closing:
                self.worker_event.emit(("generation_done", {"temp_path": str(temp_output), "snapshot": snapshot}))
                temp_output = None
        except Exception as exc:
            if not self.closing:
                self.worker_event.emit(("generation_error", str(exc)))
        finally:
            if temp_output:
                temp_output.unlink(missing_ok=True)
            if work_dir:
                shutil.rmtree(work_dir, ignore_errors=True)

    @staticmethod
    def combine_wavs(wav_paths, segments, output_path):
        if not wav_paths:
            raise RuntimeError("There are no sentence audio files.")
        with wave.open(str(wav_paths[0]), "rb") as first:
            params = first.getparams()
            sample_rate, sample_width, channels = first.getframerate(), first.getsampwidth(), first.getnchannels()
        silence_unit = b"\x00" * sample_width * channels
        with wave.open(str(output_path), "wb") as output:
            output.setparams(params)
            for index, path in enumerate(wav_paths):
                with wave.open(str(path), "rb") as wav:
                    current = wav.getparams()
                    if current.nchannels != channels or current.sampwidth != sample_width or current.framerate != sample_rate or current.comptype != "NONE":
                        raise RuntimeError("Sentence WAV files have incompatible formats.")
                    output.writeframes(wav.readframes(wav.getnframes()))
                pause = max(0.0, min(2.0, segments[index]["pause"]))
                if pause and index < len(wav_paths) - 1:
                    output.writeframes(silence_unit * int(sample_rate * pause))

    def preview_voice(self):
        if self.busy or self.previewing:
            return
        if self.current_preview_file:
            self.stop_audio()
        try:
            model = self.selected_voice()
        except Exception as exc:
            self.show_error("Voice model", str(exc))
            return
        self.previewing = True
        self.cancel_preview = False
        self.delete_multiple_button.setEnabled(False)
        self.preview_button.setEnabled(False)
        self.progress_text.setText("Generating voice preview…")
        self.set_status("Generating preview…")
        snapshot = (str(model), self.speed, self.pause)
        threading.Thread(target=self.preview_worker, args=(snapshot,), daemon=True).start()

    def preview_worker(self, snapshot):
        path = None
        try:
            fd, name = tempfile.mkstemp(suffix=".wav", prefix="voice_preview_")
            os.close(fd)
            path = Path(name)
            self.generate_to_file(core.PREVIEW_TEXT, path, Path(snapshot[0]), snapshot[1], snapshot[2])
            if not self.cancel_preview and not self.closing:
                self.worker_event.emit(("preview_done", str(path)))
                path = None
        except Exception as exc:
            if not self.cancel_preview and not self.closing:
                self.worker_event.emit(("preview_error", str(exc)))
        finally:
            if path:
                path.unlink(missing_ok=True)

    def stop_preview(self):
        self.cancel_preview = True
        with self.process_lock:
            process = self.process
        if process and process.poll() is None:
            process.terminate()
        self.stop_audio()
        self.previewing = False
        if not self.closing:
            self.preview_button.setEnabled(True)
            self.delete_multiple_button.setEnabled(bool(self.voices) and not self.busy)
            self.set_status("Preview stopped")

    def play_file(self, path):
        if not self.audio_available:
            QMessageBox.information(self, "Audio unavailable", "Audio playback is not available on this computer.")
            self._delete_current_preview()
            return
        if self.current_preview_file and Path(path) != self.current_preview_file:
            self.stop_audio()
        try:
            pygame.mixer.music.load(str(path))
            pygame.mixer.music.play()
            if self.current_preview_file and Path(path) == self.current_preview_file:
                self.preview_cleanup_timer.start()
            self.set_status(f"Playing {Path(path).name}")
        except Exception as exc:
            self._delete_current_preview()
            self.show_error("Playback error", str(exc))

    def play_output(self):
        if not core.OUTPUT_FILE.is_file():
            QMessageBox.information(self, "No voiceover", "Generate a voiceover before playing it.")
            return
        self.play_file(core.OUTPUT_FILE)

    def stop_audio(self):
        try:
            if self.audio_available:
                pygame.mixer.music.stop()
                try:
                    pygame.mixer.music.unload()
                except pygame.error:
                    # Nothing may be loaded; stopping is still successful.
                    pass
            self._delete_current_preview()
            self.set_status("Playback stopped")
        except Exception as exc:
            self.show_error("Playback error", str(exc))

    def _delete_current_preview(self):
        self.preview_cleanup_timer.stop()
        path = self.current_preview_file
        self.current_preview_file = None
        if path:
            if self.audio_available:
                try:
                    pygame.mixer.music.unload()
                except pygame.error:
                    pass
            try:
                path.unlink(missing_ok=True)
            except OSError as exc:
                print(f"Could not remove temporary voice preview {path}: {exc}")

    def _cleanup_finished_preview(self):
        if not self.current_preview_file:
            self.preview_cleanup_timer.stop()
            return
        try:
            if not self.audio_available or not pygame.mixer.music.get_busy():
                self._delete_current_preview()
        except pygame.error:
            self._delete_current_preview()

    # History
    def refresh_history(self):
        self.history = core.read_history()
        if not hasattr(self, "history_table"):
            return
        self.history_table.setRowCount(len(self.history))
        for index, entry in enumerate(self.history):
            values = (entry.get("created", ""), entry.get("voice", ""), entry.get("preset", ""), str(len(entry.get("segments", []))))
            for col, value in enumerate(values):
                self.history_table.setItem(index, col, QTableWidgetItem(value))

    def _selected_history(self):
        row = self.history_table.currentRow()
        if row < 0 or row >= len(self.history):
            QMessageBox.information(self, "Select history", "Select a history entry first.")
            return None
        return row, self.history[row]

    def load_history_script(self):
        selected = self._selected_history()
        if not selected:
            return
        _row, entry = selected
        self.script_text.setPlainText(entry.get("script", ""))
        self.segments = [{"text": part.get("text", ""), "pause": float(part.get("pause", 0.30))} for part in entry.get("segments", [])]
        self.selected_index = None
        self.refresh_timeline()
        self.show_page("editor")
        self.update_counter()
        self.set_status("History script loaded")

    def restore_history_audio(self):
        selected = self._selected_history()
        if not selected:
            return
        _row, entry = selected
        audio = Path(entry.get("audio", ""))
        if not audio.is_file():
            QMessageBox.critical(self, "Audio missing", "The saved history audio file cannot be found.")
            return
        try:
            self.stop_audio()
            shutil.copy2(audio, core.OUTPUT_FILE)
            self.play_output()
            self.set_status("Previous voiceover restored")
        except Exception as exc:
            self.show_error("Restore error", str(exc))

    def delete_history_entry(self):
        selected = self._selected_history()
        if not selected:
            return
        index, entry = selected
        answer = QMessageBox.question(self, "Delete history", "Delete this history entry and its stored audio file?")
        if answer != QMessageBox.StandardButton.Yes:
            return
        audio = Path(entry.get("audio", ""))
        try:
            if audio.is_file() and audio.parent == core.HISTORY_DIR:
                audio.unlink()
        except OSError:
            pass
        del self.history[index]
        try:
            core.write_history(self.history)
        except Exception as exc:
            self.show_error("History error", str(exc))
            self.history = core.read_history()
        self.refresh_history()
        self.set_status("History entry deleted")

    def save_generation_to_history(self, snapshot):
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        filename = datetime.now().strftime("%Y%m%d_%H%M%S_%f") + ".wav"
        history_audio = core.HISTORY_DIR / filename
        shutil.copy2(core.OUTPUT_FILE, history_audio)
        self.history.insert(0, {"created": timestamp, "voice": snapshot["voice"], "preset": snapshot["preset"], "speed": snapshot["speed"], "script": snapshot["script"], "segments": snapshot["segments"], "audio": str(history_audio)})
        try:
            core.write_history(self.history)
        except Exception:
            self.history = core.read_history()
        self.refresh_history()

    # Help, status, shortcuts and event delivery
    def refresh_help_list(self):
        self.help_list.setRowCount(len(self.visible_help_topics))
        for index, topic in enumerate(self.visible_help_topics):
            self.help_list.setItem(index, 0, QTableWidgetItem(topic))

    def filter_help_topics(self, query):
        query = query.strip().lower()
        self.visible_help_topics = [topic for topic, body in core.HELP_DOCUMENTATION.items() if not query or query in topic.lower() or query in body.lower()]
        self.refresh_help_list()
        if self.visible_help_topics:
            self.help_list.selectRow(0)
            self.show_help_topic(self.visible_help_topics[0])
        else:
            self.help_topic_title.setText("No matching topics")
            self.help_text.setPlainText("No documentation topics matched your search. Try another keyword, such as pause, Piper, history, shortcut or playback.")

    def select_help_topic(self):
        row = self.help_list.currentRow()
        if 0 <= row < len(self.visible_help_topics):
            self.show_help_topic(self.visible_help_topics[row])

    def show_help_topic(self, topic):
        body = core.HELP_DOCUMENTATION.get(topic)
        if body is not None:
            self.help_topic_title.setText(topic)
            self.help_text.setPlainText(body.strip())

    def clear_help_search(self):
        self.help_search.clear()
        self.help_search.setFocus()

    def show_history(self):
        self.show_page("history")
        self.refresh_history()

    def show_help(self):
        self.show_page("help")

    def _bind_shortcuts(self):
        shortcuts = [
            ("Ctrl+Return", self.generate_voiceover), ("Ctrl+Enter", self.generate_voiceover),
            ("Ctrl+P", self.preview_voice), ("Ctrl+Space", self._toggle_playback),
            ("Ctrl+S", self.save_script), ("Ctrl+O", self.open_script),
            ("Ctrl+H", self.show_history), ("Ctrl+F", self._focus_help_search),
            ("F1", self.show_help), ("Escape", self.shortcut_stop),
        ]
        self.shortcuts = []
        for sequence, callback in shortcuts:
            shortcut = QShortcut(QKeySequence(sequence), self)
            shortcut.activated.connect(callback)
            self.shortcuts.append(shortcut)

    def _toggle_playback(self):
        if self.audio_available and pygame.mixer.music.get_busy():
            self.stop_audio()
        else:
            self.play_output()

    def _focus_help_search(self):
        self.show_help()
        self.help_search.setFocus()
        self.help_search.selectAll()

    def shortcut_stop(self):
        self.stop_audio()
        if self.previewing:
            self.stop_preview()

    def set_status(self, text):
        if not self.closing and hasattr(self, "status_label"):
            self.status_label.setText(text)

    def show_error(self, title, text):
        if not self.closing:
            QMessageBox.critical(self, title, text)

    @Slot(object)
    def handle_worker_event(self, payload):
        if self.closing:
            return
        event, data = payload
        if event == "progress":
            self.progress.setRange(0, data["total"])
            self.progress.setValue(data["done"])
            self.progress_text.setText(f"Generating sentence {data['done']}/{data['total']}")
        elif event == "generation_done":
            temp_path = Path(data["temp_path"])
            try:
                self.stop_audio()
                os.replace(temp_path, core.OUTPUT_FILE)
                self.save_generation_to_history(data["snapshot"])
                self.progress.setValue(self.progress.maximum())
                self.progress_text.setText("Generation complete")
                self.set_status("Voiceover generated and saved to history")
                self.play_output()
            except Exception as exc:
                self.show_error("Output error", str(exc))
            finally:
                temp_path.unlink(missing_ok=True)
                self.busy = False
                self.generate_button.setEnabled(True)
                self.delete_multiple_button.setEnabled(bool(self.voices) and not self.previewing)
        elif event == "generation_error":
            self.busy = False
            self.generate_button.setEnabled(True)
            self.delete_multiple_button.setEnabled(bool(self.voices) and not self.previewing)
            self.progress_text.setText("Generation failed")
            self.set_status("Generation failed")
            self.show_error("Generation error", data)
        elif event == "preview_done":
            path = Path(data)
            self.previewing = False
            self.preview_button.setEnabled(True)
            self.delete_multiple_button.setEnabled(bool(self.voices) and not self.busy)
            if self.cancel_preview or not path.exists():
                path.unlink(missing_ok=True)
            else:
                self.current_preview_file = path
                self.play_file(path)
        elif event == "preview_error":
            self.previewing = False
            self.preview_button.setEnabled(True)
            self.delete_multiple_button.setEnabled(bool(self.voices) and not self.busy)
            self.progress_text.setText("Preview failed")
            self.show_error("Preview error", data)
        elif event == "voice_download_done":
            self._voice_download_finished(*data)
        elif event == "voice_download_progress":
            self._update_voice_download_progress(*data)
        elif event == "voice_size_info":
            model_name, size_bytes = data
            controls = self.voice_download_controls.get(model_name)
            if controls:
                controls["size"].setText(self.format_voice_size(size_bytes))


    def closeEvent(self, event):
        self.closing = True
        self.settings.setValue("window_geometry", self.saveGeometry())
        self.cancel_preview = True
        for state in self.voice_downloads.values():
            state["cancelled"].set()
            state["paused"].set()
        try:
            if self.audio_available:
                pygame.mixer.music.stop()
                try:
                    pygame.mixer.music.unload()
                except pygame.error:
                    pass
                pygame.mixer.quit()
        except Exception:
            pass
        self._delete_current_preview()
        with self.process_lock:
            process = self.process
        if process and process.poll() is None:
            process.terminate()
        event.accept()


def main():
    if sys.platform == "win32":
        try:
            import ctypes
            set_app_id = ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID
            set_app_id.argtypes = [ctypes.c_wchar_p]
            set_app_id.restype = ctypes.c_long
            set_app_id("VoiceoverStudio.Desktop")
        except (AttributeError, OSError):
            pass
    app = QApplication(sys.argv)
    app.setApplicationName("Voiceover Studio")
    app.setApplicationDisplayName("Voiceover Studio")
    app.setWindowIcon(QIcon(VoiceoverStudio._brand_pixmap(64)))
    app.setStyle("Fusion")
    window = VoiceoverStudio()
    window.show()
    taskbar_pixmap = VoiceoverStudio._brand_pixmap(64)
    window.setWindowIcon(QIcon(taskbar_pixmap))
    try:
        window._native_taskbar_icon = window._set_native_windows_icon(window.winId(), taskbar_pixmap)
        if sys.platform == "win32":
            icon_path = core.BASE_DIR / "assets" / "voiceover_studio.ico"
            icon_path.parent.mkdir(parents=True, exist_ok=True)
            window._write_windows_ico(icon_path, taskbar_pixmap)
            window._set_windows_window_app_identity(
                window.winId(),
                "VoiceoverStudio.Desktop",
                icon_path,
                subprocess.list2cmdline([sys.executable, *sys.argv]),
            )
    except Exception as exc:
        # The native taskbar icon is an enhancement; it must not block startup.
        print("Could not set the Voiceover Studio taskbar identity:", exc)
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())





