import os
import random
import subprocess
import sys
from datetime import date

from PySide6.QtCore import QFileSystemWatcher, QTimer
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtMultimedia import QMediaPlayer
from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from core import storage
from core.cover import extract_cover, first_cover
from core.files import collect_audio_files, split_dropped
from core.library import Library
from core.media import PlayerEngine
from core.playlist import Playlist
from core.stats import Stats
from core.summary_image import save_summary_card
from core.tags import display_name
from ui.add_playlist_view import AddPlaylistView
from ui.download_view import DownloadView
from ui.home_view import HomeView, pluralize
from ui.library_view import LibraryView, build_library_playlist
from ui.player_bar import PlayerBar
from ui.sidebar import Sidebar
from ui.stats_view import StatsView
from ui.track_list import TrackList

DROP_HINT = "Upuść pliki mp3, playlisty m3u, CSV lub foldery"
REPEAT_ALL = "all"
REPEAT_ONE = "one"
REPEAT_OFF = "off"


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("MusicBox")
        self.resize(980, 600)
        self.setAcceptDrops(True)

        self.library = Library()
        self.engine = PlayerEngine(self)
        self._add_mode = False
        self._pending_playlist = None
        self._add_return_view = None
        self._shuffle_on = False
        self._repeat_mode = REPEAT_ALL
        self._shuffle_queue = []
        self._history = []
        self._played_this_round = set()
        self._library_playlist = None
        self._view_playlist = None
        self._resume_source = None
        self._resume_position_ms = 0
        self._resume_ticks = 0
        self._restoring_session = False
        self._pending_seek = None
        self._seek_pending_connected = False
        self._suppress_persist = False
        self._restored_view = False

        self.stats = Stats(storage.stats_path())
        self._stats_ticks = 0
        self._stats_timer = QTimer(self)
        self._stats_timer.setInterval(1000)
        self._stats_timer.timeout.connect(self._on_stats_tick)
        self._stats_timer.start()

        settings = storage.load_settings()
        self._settings = settings

        self._apply_theme()
        self._apply_icon()
        storage.ensure()
        self._load_saved_playlists()
        self._view_playlist = self.library.current()
        self._setup_playlist_watcher()
        self._build_ui()
        self._connect_signals()
        self._suppress_persist = True
        self._restore_settings(settings)
        self._restored_view = False
        self._restore_last_session()
        self._suppress_persist = False
        if not self._restored_view:
            QTimer.singleShot(0, self._initial_refresh)
        created = self.stats.maybe_create_year_summary(date.today())
        if created:
            self._set_status("Utworzono podsumowanie roku: " + ", ".join(str(y) for y in created))

    # ---------- UI ----------
    def _apply_theme(self):
        if getattr(sys, "frozen", False):
            base = sys._MEIPASS
            path = os.path.join(base, "ui", "theme.qss")
        else:
            path = os.path.join(os.path.dirname(__file__), "theme.qss")
        with open(path, "r", encoding="utf-8") as f:
            self.setStyleSheet(f.read())

    def _icon_paths(self):
        if getattr(sys, "frozen", False):
            base = sys._MEIPASS
        else:
            base = os.path.join(os.path.dirname(os.path.dirname(__file__)))
        return [
            os.path.join(base, "assets", "icon.ico"),
            os.path.join(base, "assets", "icon.png"),
        ]

    def _apply_icon(self):
        for path in self._icon_paths():
            if os.path.isfile(path):
                self.setWindowIcon(QIcon(path))
                return

    def _restore_settings(self, settings):
        try:
            volume = int(settings.get("volume", 80))
        except (TypeError, ValueError):
            volume = 80
        self.engine.set_volume(volume)
        self.player_bar.set_volume(volume)
        self._set_shuffle(settings.get("shuffle", False) is True)
        repeat = settings.get("repeat", REPEAT_ALL)
        if repeat not in (REPEAT_ALL, REPEAT_ONE, REPEAT_OFF):
            repeat = REPEAT_ALL
        self._set_repeat(repeat)

    def _persist_settings(self):
        if self._suppress_persist:
            return
        storage.save_settings(
            {
                "volume": int(self.engine.volume),
                "shuffle": self._shuffle_on,
                "repeat": self._repeat_mode,
                "resume": self._build_resume_payload(),
            }
        )

    # ---------- zapamiętywanie pozycji odtwarzania ----------
    def _build_resume_payload(self):
        source = self._resume_source
        if not source or not source.get("path"):
            return None
        if not os.path.isfile(source["path"]):
            return None
        return {
            "path": source["path"],
            "position_ms": max(0, int(self._resume_position_ms)),
            "playlist": source.get("playlist"),
            "library": bool(source.get("library")),
        }

    def _update_resume_source(self, path):
        if self._restoring_session:
            return
        playlist = self._current_playlist()
        self._resume_source = {
            "path": path,
            "playlist": playlist.name if playlist else None,
            "library": self.stack.currentWidget() is self.library_view,
        }
        self._resume_position_ms = 0
        self._persist_settings()

    def _clear_resume(self):
        self._resume_source = None
        self._resume_position_ms = 0
        self._persist_settings()

    def _find_playlist_by_path(self, path):
        target = os.path.normcase(os.path.abspath(path))
        for p in self.library.playlists:
            for t in p.tracks:
                if os.path.normcase(os.path.abspath(t.path)) == target:
                    return p
        return None

    @staticmethod
    def _index_of_path(playlist, path):
        target = os.path.normcase(os.path.abspath(path))
        for i, t in enumerate(playlist.tracks):
            if os.path.normcase(os.path.abspath(t.path)) == target:
                return i
        return -1

    def _seek_pending(self, status):
        if status != QMediaPlayer.MediaStatus.LoadedMedia:
            return
        if self._seek_pending_connected:
            self.engine.media.mediaStatusChanged.disconnect(self._seek_pending)
            self._seek_pending_connected = False
        if self._pending_seek is not None:
            self.engine.seek(self._pending_seek)
            self._pending_seek = None

    def _do_seek_after_load(self, position_ms):
        self._pending_seek = max(0, int(position_ms))
        if not self._seek_pending_connected:
            self.engine.media.mediaStatusChanged.connect(self._seek_pending)
            self._seek_pending_connected = True
        if self.engine.media.mediaStatus() == QMediaPlayer.MediaStatus.LoadedMedia:
            self._seek_pending(QMediaPlayer.MediaStatus.LoadedMedia)

    def _restore_last_session(self):
        resume = self._settings.get("resume")
        if not isinstance(resume, dict):
            return
        path = resume.get("path")
        if not isinstance(path, str) or not path or not os.path.isfile(path):
            return
        try:
            position_ms = max(0, int(resume.get("position_ms", 0)))
        except (TypeError, ValueError):
            position_ms = 0

        try:
            self._restore_last_session_impl(path, position_ms, resume)
        except Exception:
            self._clear_resume()

    def _restore_last_session_impl(self, path, position_ms, resume):
        if resume.get("library"):
            self._library_playlist = build_library_playlist(self.library.playlists)
            playlist = self._library_playlist
        else:
            playlist = None
            name = resume.get("playlist")
            if name:
                for p in self.library.playlists:
                    if p.name == name:
                        playlist = p
                        break
            if playlist is None:
                playlist = self._find_playlist_by_path(path)
        if playlist is None:
            return

        index = self._index_of_path(playlist, path)
        if index < 0:
            return
        playlist.current_index = index
        self._view_playlist = playlist
        self._restored_view = True

        if resume.get("library"):
            self.sidebar.show()
            self.library_view.set_library(self._library_playlist)
            self.library_view.track_list.highlight_current(index)
            self.stack.setCurrentWidget(self.library_view)
            self._refresh_sidebar()
            self._set_status("Biblioteka · " + pluralize(len(self._library_playlist.tracks)))
        else:
            pl_index = -1
            for i, p in enumerate(self.library.playlists):
                if p is playlist:
                    pl_index = i
                    break
            if pl_index >= 0:
                self.library.switch_to(pl_index)
            self._show_playlist_view()
            self.track_list.highlight_current(index)
            self._set_status(f"Przywrócono: {os.path.basename(path)}")
        self._ensure_shuffle_queue()

        self._resume_source = {
            "path": path,
            "playlist": playlist.name if playlist else None,
            "library": bool(resume.get("library")),
        }
        self._resume_position_ms = position_ms

        self._restoring_session = True
        self.engine.set_track(path)
        self.engine.pause()
        self._restoring_session = False
        self.player_bar.set_playing(False)
        self._do_seek_after_load(position_ms)

    def _initial_refresh(self):
        self._refresh_sidebar()
        self._refresh_playlist_view()
        if not self._restored_view:
            self._show_home()

    def _load_saved_playlists(self):
        for playlist in storage.load_saved_playlists():
            self.library.add_playlist(playlist)

    def _setup_playlist_watcher(self):
        self._fs_watcher = QFileSystemWatcher(self)
        self._fs_watcher.directoryChanged.connect(self._on_playlists_dir_changed)
        self._fs_watcher.addPath(storage.playlists_dir())

    def _on_playlists_dir_changed(self, path):
        self._reload_playlists_from_disk()

    def _reload_playlists_from_disk(self):
        d = storage.playlists_dir()
        files = []
        if os.path.isdir(d):
            for fn in os.listdir(d):
                if fn.lower().endswith((".m3u", ".m3u8")):
                    files.append(os.path.join(d, fn))
        by_name = {p.name: p for p in self.library.playlists}
        loaded = set()
        added = []
        updated = []
        for fp in files:
            pl = Playlist()
            try:
                count = pl.load_m3u(fp)
            except OSError:
                continue
            name = pl.name
            if count == 0:
                continue
            loaded.add(name)
            if name not in by_name:
                self.library.playlists.append(pl)
                added.append(name)
            else:
                existing = by_name[name]
                old_paths = [t.path for t in existing.tracks]
                new_paths = [t.path for t in pl.tracks]
                if old_paths != new_paths:
                    current_path = existing.current().path if existing.current() else None
                    existing.tracks = pl.tracks
                    if current_path and current_path in new_paths:
                        existing.current_index = new_paths.index(current_path)
                    elif new_paths:
                        fallback = existing.current_index
                        if current_path:
                            old_name = os.path.basename(current_path)
                            for ni, t in enumerate(pl.tracks):
                                if os.path.basename(t.path) == old_name:
                                    fallback = ni
                                    break
                        existing.current_index = min(max(fallback, 0), len(new_paths) - 1)
                    else:
                        existing.current_index = -1
                    updated.append(name)

        removed = []
        for name in list(by_name):
            if name not in loaded:
                pl = by_name[name]
                if self.engine.current_source in (t.path for t in pl.tracks):
                    self.engine.stop()
                    self.player_bar.set_playing(False)
                    self.player_bar.set_track("Brak utworu")
                self.library.playlists.remove(pl)
                removed.append(name)

        if removed:
            self._view_playlist = self.library.current()

        if added or updated or removed:
            self._refresh_sidebar()
            self._refresh_home()
            self._refresh_library_view_if_visible()
            parts = []
            if added:
                parts.append("dodano: " + ", ".join(added))
            if updated:
                parts.append("zaktualizowano: " + ", ".join(updated))
            if removed:
                parts.append("usunięto: " + ", ".join(removed))
            self._set_status("Odświeżono (" + "; ".join(parts) + ")")
            return True
        return False

    def _on_refresh_clicked(self):
        if not self._reload_playlists_from_disk():
            self._refresh_home()
            self._set_status("Brak zmian")

    def _build_ui(self):
        central = QWidget()
        central.setObjectName("central")
        self.setCentralWidget(central)

        root = QHBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self.sidebar = Sidebar(self)
        root.addWidget(self.sidebar)

        right = QWidget()
        right.setObjectName("central")
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(0)

        self.stack = QStackedWidget()
        self.home_view = HomeView()
        self.stack.addWidget(self.home_view)
        self.playlist_page = self._build_playlist_view()
        self.stack.addWidget(self.playlist_page)
        self.library_view = LibraryView()
        self.stack.addWidget(self.library_view)
        self.stats_view = StatsView()
        self.stack.addWidget(self.stats_view)
        self.download_view = DownloadView()
        self.stack.addWidget(self.download_view)
        self.add_view = AddPlaylistView()
        self.stack.addWidget(self.add_view)
        right_layout.addWidget(self.stack, 1)

        self.player_bar = PlayerBar()
        right_layout.addWidget(self.player_bar)

        root.addWidget(right, 1)

        self.status_bar = self.statusBar()
        self.status_bar.showMessage(DROP_HINT)

    def _build_playlist_view(self):
        page = QWidget()
        page.setObjectName("central")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(24, 20, 24, 12)
        layout.setSpacing(12)

        self.playlist_header = QLabel("")
        self.playlist_header.setStyleSheet(
            "font-size: 20px; font-weight: 700; color: #ffffff;"
        )
        layout.addWidget(self.playlist_header)

        self.search_box = QLineEdit()
        self.search_box.setObjectName("searchBox")
        self.search_box.setPlaceholderText("Szukaj w playliście…")
        self.search_box.setClearButtonEnabled(True)
        layout.addWidget(self.search_box)

        self.track_list = TrackList()
        layout.addWidget(self.track_list, 1)
        return page

    def _connect_signals(self):
        self.sidebar.playlistClicked.connect(self._on_playlist_clicked)
        self.sidebar.removeRequested.connect(self._remove_playlist)
        self.sidebar.homeRequested.connect(self._show_home)
        self.sidebar.libraryRequested.connect(self._show_library_view)
        self.sidebar.statsRequested.connect(self._show_stats_view)
        self.sidebar.addRequested.connect(self._enter_add_mode)
        self.sidebar.downloadRequested.connect(self._show_download_view)
        self.home_view.playlistClicked.connect(self._open_playlist_from_home)
        self.home_view.addRequested.connect(self._enter_add_mode)
        self.home_view.downloadRequested.connect(self._show_download_view)
        self.home_view.libraryRequested.connect(self._show_library_view)
        self.home_view.statsRequested.connect(self._show_stats_view)
        self.home_view.removeRequested.connect(self._remove_playlist)
        self.home_view.refreshRequested.connect(self._on_refresh_clicked)
        self.library_view.playRequested.connect(self._on_library_play)
        self.library_view.revealRequested.connect(self._on_library_reveal)
        self.stats_view.createRequested.connect(self._on_stats_create)
        self.stats_view.renameRequested.connect(self._on_stats_rename)
        self.stats_view.resetRequested.connect(self._on_stats_reset)
        self.stats_view.exportRequested.connect(self._on_stats_export)
        self.stats_view.importRequested.connect(self._on_stats_import)
        self.stats_view.imageRequested.connect(self._on_stats_image)
        self.download_view.backRequested.connect(self._show_home)
        self.download_view.playlistSaved.connect(self._on_download_playlist_saved)
        self.add_view.confirmRequested.connect(self._confirm_add)
        self.add_view.cancelRequested.connect(self._cancel_add)
        self.track_list.playRequested.connect(self._play_at)
        self.track_list.removeRequested.connect(self._remove_track_at)
        self.track_list.revealRequested.connect(self._reveal_file)
        self.search_box.textChanged.connect(self._on_search_changed)
        self.player_bar.playClicked.connect(self.toggle_play)
        self.player_bar.nextClicked.connect(self.play_next)
        self.player_bar.prevClicked.connect(self.play_prev)
        self.player_bar.stopClicked.connect(self._on_stop_clicked)
        self.player_bar.shuffleToggled.connect(self._set_shuffle)
        self.player_bar.repeatCycled.connect(self._cycle_repeat)
        self.player_bar.seekRequested.connect(self.engine.seek)
        self.player_bar.volumeChanged.connect(self._on_volume_changed)

        self.engine.trackChanged.connect(self._on_track_changed)
        self.engine.trackStarted.connect(self._on_track_started)
        self.engine.positionChanged.connect(self._on_position_changed)
        self.engine.positionChanged.connect(self.player_bar.set_position)
        self.engine.durationChanged.connect(self.player_bar.set_duration)
        self.engine.playbackEnded.connect(self._on_playback_ended)
        self.engine.errorOccurred.connect(self._on_error)

    # ---------- sidebar ----------
    def _refresh_sidebar(self):
        self.sidebar.set_playlists(self.library.playlists, self.library.current_index)

    def _on_playlist_clicked(self, index):
        self._exit_add_mode()
        self.library.switch_to(index)
        self._view_playlist = self.library.current()
        self._ensure_shuffle_queue()
        self._show_playlist_view()
        self._set_status(DROP_HINT)

    # ---------- nawigacja: ekran główny / widok playlisty ----------
    def _show_home(self):
        self._exit_add_mode()
        self.sidebar.hide()
        self.stack.setCurrentWidget(self.home_view)
        self._refresh_home()
        self._set_status(DROP_HINT)

    def _show_playlist_view(self):
        self.sidebar.show()
        self.stack.setCurrentWidget(self.playlist_page)
        self._refresh_sidebar()
        self._refresh_playlist_view()

    def _open_playlist_from_home(self, index):
        self._exit_add_mode()
        self.library.switch_to(index)
        self._view_playlist = self.library.current()
        self._ensure_shuffle_queue()
        self._show_playlist_view()
        self._set_status(DROP_HINT)

    def _show_library_view(self):
        self._exit_add_mode()
        self.sidebar.show()
        self._library_playlist = build_library_playlist(self.library.playlists)
        self._view_playlist = self._library_playlist
        self.library_view.set_library(self._library_playlist)
        self.stack.setCurrentWidget(self.library_view)
        self._refresh_sidebar()
        if self._library_playlist.tracks and self._library_playlist.current_index >= 0:
            self.library_view.track_list.highlight_current(self._library_playlist.current_index)
        self._set_status("Biblioteka · " + pluralize(len(self._library_playlist.tracks)))

    def _show_stats_view(self):
        self._exit_add_mode()
        self.stats.maybe_create_year_summary(date.today())
        self.sidebar.show()
        self.stack.setCurrentWidget(self.stats_view)
        self._refresh_sidebar()
        self.stats_view.refresh(self.stats)
        self._set_status("Statystyki")

    def _on_stats_tick(self):
        if self.engine.is_playing:
            self._resume_ticks += 1
            if self._resume_ticks >= 10:
                self._resume_ticks = 0
                self._persist_settings()
        if self.stats.has_profile and self.engine.is_playing:
            self.stats.add_listening(1)
            self._stats_ticks += 1
            if self._stats_ticks >= 10:
                self._stats_ticks = 0
                self.stats.save()
            if self.stack.currentWidget() is self.stats_view:
                self.stats_view.refresh(self.stats)

    def _on_stats_create(self, name):
        if self.stats.create_profile(name):
            self._set_status(f"Utworzono profil: {name}")
            self.stats_view.refresh(self.stats)

    def _on_stats_rename(self, name):
        if self.stats.rename_profile(name):
            self._set_status(f"Zapisano profil: {name}")
            self.stats_view.refresh(self.stats)

    def _on_stats_reset(self):
        if self.stats.reset():
            self._set_status("Zresetowano statystyki")
            self.stats_view.refresh(self.stats)

    def _on_stats_export(self):
        if not self.stats.has_profile:
            return
        default = os.path.join(os.path.expanduser("~"), "profil.json")
        path, _ = QFileDialog.getSaveFileName(
            self, "Pobierz profil", default, "JSON (*.json)"
        )
        if path:
            if self.stats.export(path):
                self._set_status(f"Zapisano profil do: {path}")
            else:
                self._set_status("Nie udało się zapisać profilu")

    def _on_stats_import(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Wczytaj profil", "", "JSON (*.json)"
        )
        if path:
            if self.stats.import_(path):
                self._set_status(f"Wczytano profil: {self.stats.profile_name}")
                self.stats_view.refresh(self.stats)
            else:
                self._set_status("Nie udało się wczytać profilu")

    def _on_stats_image(self, label, summary):
        slug = "".join(c if c.isalnum() else "_" for c in label.lower()).strip("_")
        default = os.path.join(os.path.expanduser("~"), f"statystyki_{slug}.png")
        path, _ = QFileDialog.getSaveFileName(
            self, "Wygeneruj obraz ze statystyk", default, "Obraz PNG (*.png)"
        )
        if not path:
            return
        ok = save_summary_card(self.stats.profile_name, label, summary, path)
        if ok:
            self._set_status(f"Zapisano obraz: {path}")
        else:
            self._set_status("Nie udało się zapisać obrazu")

    def _refresh_home(self):
        self.home_view.refresh(self.library.playlists, self.library.current_index)

    def _refresh_library_view_if_visible(self):
        if self.stack.currentWidget() is not self.library_view:
            return
        self._library_playlist = build_library_playlist(self.library.playlists)
        self._view_playlist = self._library_playlist
        self.library_view.set_library(self._library_playlist)

    def _show_download_view(self):
        self._exit_add_mode()
        self.sidebar.hide()
        self.stack.setCurrentWidget(self.download_view)
        self._set_status("Pobierz playlistę z pliku m3u/csv")

    def _on_download_playlist_saved(self, path):
        playlist = Playlist()
        if playlist.load_m3u(path) > 0:
            self.library.add_playlist(playlist)
            self._refresh_sidebar()
            self._refresh_home()
            self._refresh_library_view_if_visible()
            self._set_status(f"Dodano playlistę: {playlist.name}")
        else:
            self._set_status("Playlista nie zawiera pobranych utworów")

    # ---------- widok playlisty ----------
    def _refresh_playlist_view(self):
        playlist = self._current_playlist()
        self.track_list.set_playlist(playlist)
        self.track_list.set_filter(self.search_box.text())
        if playlist:
            self.playlist_header.setText(f"{playlist.name} · {pluralize(len(playlist.tracks))}")
            if playlist.current_index >= 0:
                self.track_list.highlight_current(playlist.current_index)
        else:
            self.playlist_header.setText("Brak playlisty")
            self._set_status(DROP_HINT)

    # ---------- przepływ dodawania playlisty ----------
    def _enter_add_mode(self):
        self._add_mode = True
        self._pending_playlist = None
        self._add_return_view = self.stack.currentWidget()
        self.sidebar.set_waiting_state(True)
        self.home_view.set_waiting_state(True)
        self.add_view.set_waiting_state()
        self.stack.setCurrentWidget(self.add_view)
        self._set_status("Czekam na upuszczenie plików")

    def _exit_add_mode(self):
        if not self._add_mode:
            return
        self._add_mode = False
        self._pending_playlist = None
        self.sidebar.set_waiting_state(False)
        self.home_view.set_waiting_state(False)
        target = self._add_return_view or self.stack.widget(0)
        self._add_return_view = None
        self.stack.setCurrentWidget(target)
        self.sidebar.setVisible(target is self.playlist_page or target is self.library_view or target is self.stats_view)

    def _handle_m3u_drop(self, m3u_path):
        playlist = Playlist()
        try:
            playlist.load_m3u(m3u_path)
        except OSError:
            self._set_status("Nie udało się odczytać pliku playlisty")
            return
        self._start_add_flow(playlist)

    def _start_add_flow(self, playlist):
        if not playlist.tracks:
            self._set_status("Nie udało się znaleźć żadnych utworów")
            return False
        self._add_mode = True
        self._pending_playlist = playlist
        self.sidebar.set_waiting_state(True)
        self.home_view.set_waiting_state(True)
        cover = first_cover([t.path for t in playlist.tracks])
        pixmap = None
        if cover:
            pm = QPixmap()
            if pm.loadFromData(cover):
                pixmap = pm
        self.add_view.show_preview(playlist, pixmap)
        self.stack.setCurrentWidget(self.add_view)
        self._set_status(f"Podgląd playlisty: {playlist.name}")
        return True

    def _confirm_add(self):
        if self._pending_playlist is None:
            return
        playlist = self._pending_playlist
        self.library.add_playlist(playlist)
        self._view_playlist = playlist
        storage.save_playlist(playlist)
        self._exit_add_mode()
        self._ensure_shuffle_queue()
        self._show_playlist_view()
        self._refresh_home()
        self._refresh_library_view_if_visible()
        self._set_status(f"Zapisano playlistę: {playlist.name}")
        if playlist.tracks:
            self._play_at(0)

    def _cancel_add(self):
        self._exit_add_mode()
        self._refresh_sidebar()
        self._set_status("Anulowano dodawanie playlisty")

    # ---------- odtwarzanie ----------
    def _current_playlist(self):
        return self._view_playlist or self.library.current()

    def _active_track_list(self):
        if self.stack.currentWidget() is self.library_view:
            return self.library_view.track_list
        return self.track_list

    def _play_at(self, index, record=True):
        playlist = self._current_playlist()
        if not playlist or not (0 <= index < len(playlist.tracks)):
            return
        previous = playlist.current_index
        if record and self._shuffle_on and previous >= 0 and previous != index:
            self._history.append(previous)
        playlist.current_index = index
        if self._shuffle_on:
            self._shuffle_queue = [i for i in self._shuffle_queue if i != index]
            self._played_this_round.add(index)
        self._active_track_list().highlight_current(index)
        self.engine.set_track(playlist.tracks[index].path)

    def toggle_play(self):
        playlist = self._current_playlist()
        if not playlist:
            return
        if playlist.current() is None and playlist.tracks:
            self._play_at(0)
            return
        if self.engine.is_playing:
            self.engine.pause()
        else:
            if self._shuffle_on and len(self._played_this_round) >= len(playlist.tracks):
                self._refill_shuffle()
                nxt = self._shuffle_next()
                if nxt >= 0:
                    self._play_at(nxt)
                    self.player_bar.set_playing(True)
                    return
            self.engine.play()
        self.player_bar.set_playing(self.engine.is_playing)

    def _refill_shuffle(self):
        playlist = self._current_playlist()
        if not playlist:
            return
        current = playlist.current_index
        indices = [i for i in range(len(playlist.tracks)) if i != current]
        random.shuffle(indices)
        self._shuffle_queue = indices
        self._played_this_round = set()

    def _ensure_shuffle_queue(self):
        if self._shuffle_on:
            self._refill_shuffle()

    def _shuffle_next(self):
        playlist = self._current_playlist()
        for _ in range(2):
            if not self._shuffle_queue:
                self._refill_shuffle()
            while self._shuffle_queue:
                index = self._shuffle_queue.pop(0)
                if playlist and 0 <= index < len(playlist.tracks):
                    return index
        return -1

    def play_next(self):
        playlist = self._current_playlist()
        if not playlist or not playlist.tracks:
            return
        if self._shuffle_on:
            nxt = self._shuffle_next()
        else:
            nxt = playlist.next_index()
        if nxt >= 0:
            self._play_at(nxt)

    def play_prev(self):
        playlist = self._current_playlist()
        if not playlist:
            return
        if self._shuffle_on and self._history:
            self._play_at(self._history.pop(), record=False)
            return
        prev = playlist.prev_index()
        if prev >= 0:
            self._play_at(prev)

    def _on_playback_ended(self):
        if self._repeat_mode == REPEAT_ONE:
            self.engine.replay()
            return
        playlist = self._current_playlist()
        if not playlist or not playlist.tracks:
            return
        if self._repeat_mode == REPEAT_OFF:
            if self._shuffle_on:
                if len(self._played_this_round) >= len(playlist.tracks):
                    self.engine.stop()
                    self.player_bar.set_playing(False)
                    self._clear_resume()
                    return
            elif playlist.current_index >= len(playlist.tracks) - 1:
                self.engine.stop()
                self.player_bar.set_playing(False)
                self._clear_resume()
                return
        self.play_next()

    def _set_shuffle(self, on):
        self._shuffle_on = bool(on)
        if self._shuffle_on:
            self._shuffle_queue = []
            self._history = []
            self._refill_shuffle()
        self.player_bar.set_shuffle(self._shuffle_on)
        self._persist_settings()

    def _set_repeat(self, mode):
        self._repeat_mode = mode
        self.player_bar.set_repeat(mode)

    def _cycle_repeat(self):
        modes = [REPEAT_ALL, REPEAT_ONE, REPEAT_OFF]
        current = self._repeat_mode
        if current not in modes:
            current = REPEAT_ALL
        self._set_repeat(modes[(modes.index(current) + 1) % 3])
        self._persist_settings()

    def _on_volume_changed(self, value):
        self.engine.set_volume(value)
        self._persist_settings()

    def _on_search_changed(self, text):
        self.track_list.set_filter(text)

    def _remove_track_at(self, index):
        playlist = self._current_playlist()
        if not playlist:
            return
        removed = playlist.remove_track(index)
        if removed is None:
            return
        if self.engine.current_source == removed.path:
            self.engine.stop()
            self.player_bar.set_playing(False)
            self.player_bar.set_track("Brak utworu")
            self._clear_resume()
        storage.save_playlist(playlist)
        self._refresh_playlist_view()
        self._refresh_library_view_if_visible()
        self._set_status(f"Usunięto: {removed.title}")

    def _reveal_file(self, index):
        playlist = self._current_playlist()
        if not playlist or not (0 <= index < len(playlist.tracks)):
            return
        self._reveal_path(playlist.tracks[index].path)

    def _reveal_path(self, path):
        try:
            if sys.platform == "win32":
                subprocess.Popen(["explorer", f"/select,{path}"])
            elif sys.platform == "darwin":
                subprocess.Popen(["open", "-R", path])
            else:
                subprocess.Popen(["xdg-open", os.path.dirname(path)])
        except OSError:
            self._set_status("Nie udało się otworzyć lokalizacji pliku")

    def _on_library_play(self, index):
        if self._library_playlist is None:
            self._show_library_view()
        self._view_playlist = self._library_playlist
        self._play_at(index)

    def _on_library_reveal(self, index):
        playlist = self._library_playlist
        if not playlist or not (0 <= index < len(playlist.tracks)):
            return
        self._reveal_path(playlist.tracks[index].path)

    # ---------- sygnały silnika ----------
    def _on_position_changed(self, ms):
        if self._restoring_session:
            return
        self._resume_position_ms = int(ms)

    def _on_track_started(self, path):
        if self._restoring_session:
            return
        if self.stats.has_profile:
            self.stats.increment_play(path)
            self.stats.save()
            if self.stack.currentWidget() is self.stats_view:
                self.stats_view.refresh(self.stats)

    def _on_track_changed(self, path):
        playlist = self._current_playlist()
        track = playlist.current() if playlist else None
        title = display_name(track.path, track.title) if track else os.path.basename(path)
        cover = None
        if track:
            data = extract_cover(track.path)
            if data:
                pm = QPixmap()
                if pm.loadFromData(data):
                    cover = pm
        self.player_bar.set_track(title, cover)
        self.player_bar.set_playing(not self._restoring_session)
        if playlist and playlist.current_index >= 0:
            self._active_track_list().highlight_current(playlist.current_index)
        self._set_status(f"Odtwarzam: {title}")
        self._update_resume_source(path)

    def _on_error(self, message):
        self._set_status(f"Błąd: {message}")
        self.player_bar.set_playing(False)

    def _on_stop_clicked(self):
        self.engine.stop()
        self.player_bar.set_playing(False)
        self.player_bar.set_track("Brak utworu")
        self._clear_resume()

    def _set_status(self, text):
        self.status_bar.showMessage(text)

    # ---------- drag & drop ----------
    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dragMoveEvent(self, event):
        event.acceptProposedAction()

    def dropEvent(self, event):
        paths = [url.toLocalFile() for url in event.mimeData().urls() if url.isLocalFile()]
        if not paths:
            return
        self._handle_dropped_paths(paths)
        event.acceptProposedAction()

    def _handle_dropped_paths(self, paths):
        csv_files = [p for p in paths if p.lower().endswith(".csv")]
        if csv_files:
            self._exit_add_mode()
            self._show_download_view()
            self.download_view.load_csv(csv_files[0])
            return

        playlists, audio, folders = split_dropped(paths)
        if not self._add_mode:
            self._set_status("Kliknij '＋ Dodaj playlistę', żeby dodać pliki")
            return

        if playlists:
            self._handle_m3u_drop(playlists[0])
            return

        added = list(audio)
        for folder in folders:
            added.extend(collect_audio_files(folder))
        if not added:
            return

        parent = os.path.basename(os.path.dirname(os.path.abspath(added[0])))
        playlist = Playlist(parent or "Moja playlista")
        playlist.add_tracks(added)
        self._start_add_flow(playlist)

    def closeEvent(self, event):
        self.stats.save()
        self._persist_settings()
        worker = getattr(self.download_view, "_worker", None)
        if worker is not None and worker.isRunning():
            worker.stop()
            if not worker.wait(10000):
                worker.terminate()
                worker.wait(2000)
        event.accept()

    def _remove_playlist(self, index):
        playlist = self.library.playlists[index]
        if self.engine.current_source in (t.path for t in playlist.tracks):
            self.engine.stop()
            self.player_bar.set_playing(False)
            self.player_bar.set_track("Brak utworu")
            self._clear_resume()
        self.library.remove(index)
        self._view_playlist = self.library.current()
        storage.delete_playlist(playlist.name)
        self._shuffle_queue = []
        self._history = []
        self._played_this_round = set()
        self._refresh_sidebar()
        self._refresh_home()
        self._refresh_playlist_view()
        self._refresh_library_view_if_visible()
        self._set_status(f"Usunięto playlistę: {playlist.name}")
