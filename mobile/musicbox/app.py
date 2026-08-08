"""Aplikacja mobilna MusicBox (Kivy + KivyMD).

Zakres v1: odtwarzanie lokalnych utworow, playlisty (import .m3u),
biblioteka i podstawowe statystyki. Pobieranie z YouTube jest swiadomie
pominiete (wymaga yt-dlp/ffmpeg — niedostepne na Androidzie).
"""
import json
import os
import queue
import random
import threading
import time
from datetime import date

from kivy.clock import Clock
from kivy.core.window import Window
from kivy.factory import Factory
from kivy.lang import Builder
from kivy.metrics import dp
from kivy.properties import NumericProperty, StringProperty
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.image import AsyncImage
from kivy.uix.screenmanager import ScreenManager
from kivy.uix.spinner import Spinner
from kivymd.app import MDApp
from kivymd.uix.boxlayout import MDBoxLayout
from kivymd.uix.button import MDRectangleFlatButton
from kivymd.uix.card import MDCard
from kivymd.uix.label import MDLabel
from kivymd.uix.list import OneLineListItem
from kivymd.uix.textfield import MDTextField

from core import storage
from core.cover import extract_cover
from core.library import Library
from core.playlist import Playlist, Track
from core.stats import Stats, format_listening
from core.tags import combine_name, display_artist, display_name, display_title

from musicbox import android_io
from musicbox.audio import (
    AudioPlayer,
    STATE_CHANGED,
    STATE_POSITION,
)
from musicbox.controller import PlaybackController, REPEAT_ALL, REPEAT_OFF, REPEAT_ONE


class TrackRow(MDCard):
    """Wiersz utworu dla RecycleView (lazy): tytul i okładka laduja sie w tle."""

    path = StringProperty("")
    title = StringProperty("")
    index = NumericProperty(-1)

    def __init__(self, **kwargs):
        super(TrackRow, self).__init__(**kwargs)
        self._title_label = None
        self._artist_label = None
        self._cover_box = None
        self._down_pos = None
        self._build_row()
        self.bind(path=self._on_row_path)

    def _build_row(self):
        self.orientation = "horizontal"
        self.size_hint_y = None
        self.height = dp(64)
        self.radius = [dp(10)]
        self.elevation = 1
        self.md_bg_color = (0.07, 0.1, 0.22, 1)
        self.padding = dp(8)
        self.spacing = dp(10)
        cover = MDBoxLayout(
            size_hint_x=None,
            width=dp(48),
            md_bg_color=(0.05, 0.07, 0.16, 1),
            padding=dp(2),
        )
        cover.add_widget(self._note_label("20sp"))
        self.add_widget(cover)
        self._cover_box = cover
        meta = MDBoxLayout(orientation="vertical", spacing=dp(0), size_hint_x=1)
        self._title_label = MDLabel(
            text="",
            theme_text_color="Custom",
            text_color=(1, 1, 1, 1),
            halign="left",
            valign="middle",
            shorten=True,
            shorten_from="right",
            size_hint_y=None,
            height=dp(26),
        )
        self._artist_label = MDLabel(
            text="",
            theme_text_color="Custom",
            text_color=(0.55, 0.65, 0.85, 1),
            halign="left",
            valign="top",
            shorten=True,
            shorten_from="right",
            font_size="12sp",
            size_hint_y=None,
            height=dp(20),
        )
        meta.add_widget(self._title_label)
        meta.add_widget(self._artist_label)
        self.add_widget(meta)

    @staticmethod
    def _note_label(size):
        return MDLabel(
            text="♪",
            font_size=size,
            halign="center",
            valign="middle",
            theme_text_color="Custom",
            text_color=(0.35, 0.55, 0.9, 1),
        )

    def _on_row_path(self, *a):
        if self._title_label is not None:
            self._title_label.text = self.title
        if self._artist_label is not None:
            self._artist_label.text = ""
        if self._cover_box is not None:
            self._cover_box.clear_widgets()
            self._cover_box.add_widget(self._note_label("20sp"))
        app = MDApp.get_running_app()
        if app is None:
            return
        app.enqueue_track(self.path, self.title, self)
        app.enqueue_cover(self, self.path)

    def apply_meta(self, title, artist, path):
        if self.path != path or self._title_label is None:
            return
        self._title_label.text = title or self.title
        if self._artist_label is not None:
            self._artist_label.text = artist or ""

    def apply_cover(self, cover, path):
        if self.path != path or self._cover_box is None:
            return
        self._cover_box.clear_widgets()
        if cover:
            self._cover_box.add_widget(
                AsyncImage(source=cover, allow_stretch=True, keep_ratio=True)
            )
        else:
            self._cover_box.add_widget(self._note_label("20sp"))

    def on_touch_down(self, touch):
        if self.collide_point(*touch.pos):
            self._down_pos = (touch.x, touch.y)
        return super(TrackRow, self).on_touch_down(touch)

    def on_touch_up(self, touch):
        if self.collide_point(*touch.pos) and self._down_pos is not None:
            dx = abs(touch.x - self._down_pos[0])
            dy = abs(touch.y - self._down_pos[1])
            if dx < dp(10) and dy < dp(10):
                app = MDApp.get_running_app()
                if app is not None and self.index >= 0:
                    app._on_track_clicked(self.index)
        return super(TrackRow, self).on_touch_up(touch)


Factory.register("TrackRow", cls=TrackRow)

KV = """
#:import C kivy.utils.get_color_from_hex
#:import MDBoxLayout kivymd.uix.boxlayout.MDBoxLayout
#:import MDLabel kivymd.uix.label.MDLabel
#:import MDIconButton kivymd.uix.button.MDIconButton
#:import MDRectangleFlatButton kivymd.uix.button.MDRectangleFlatButton
#:import MDList kivymd.uix.list.MDList
#:import OneLineListItem kivymd.uix.list.OneLineListItem
#:import MDScreen kivymd.uix.screen.MDScreen
#:import MDTextField kivymd.uix.textfield.MDTextField
#:import MarqueeLabel musicbox.marquee.MarqueeLabel

<PlayerBar@BoxLayout>:
    orientation: "vertical"
    size_hint_y: None
    height: dp(140)
    padding: dp(12), dp(4)
    spacing: dp(2)
    canvas.before:
        Color:
            rgba: C("#101827")
        Rectangle:
            pos: self.pos
            size: self.size
    MarqueeLabel:
        id: track_label
        text: "Brak utworu"
        text_color: 1, 1, 1, 1
        bold: True
        font_size: sp(15)
        size_hint_y: None
        height: dp(26)
    MarqueeLabel:
        id: artist_label
        text: ""
        text_color: 0.6, 0.68, 0.83, 1
        font_size: sp(12)
        size_hint_y: None
        height: dp(18)
    BoxLayout:
        orientation: "horizontal"
        spacing: dp(8)
        size_hint_y: None
        height: dp(30)
        MDLabel:
            id: time_pos
            text: "0:00"
            theme_text_color: "Custom"
            text_color: 0.6, 0.68, 0.83, 1
            size_hint_x: None
            width: dp(46)
            font_size: "12sp"
        Slider:
            id: progress_slider
            min: 0
            max: 1
            value: 0
        MDLabel:
            id: time_total
            text: "0:00"
            theme_text_color: "Custom"
            text_color: 0.6, 0.68, 0.83, 1
            size_hint_x: None
            width: dp(46)
            font_size: "12sp"
            halign: "right"
    BoxLayout:
        orientation: "horizontal"
        size_hint_y: None
        height: dp(50)
        spacing: dp(2)
        MDIconButton:
            id: shuffle_btn
            icon: "shuffle"
            size_hint_x: 1
            theme_icon_color: "Custom"
            icon_color: 0.6, 0.68, 0.83, 1
        MDIconButton:
            id: prev_btn
            icon: "skip-previous"
            size_hint_x: 1
            theme_icon_color: "Custom"
            icon_color: 1, 1, 1, 1
        MDIconButton:
            id: play_btn
            icon: "play-circle"
            icon_size: "46sp"
            size_hint_x: 1
            theme_icon_color: "Custom"
            icon_color: 1, 1, 1, 1
        MDIconButton:
            id: next_btn
            icon: "skip-next"
            size_hint_x: 1
            theme_icon_color: "Custom"
            icon_color: 1, 1, 1, 1
        MDIconButton:
            id: repeat_btn
            icon: "repeat"
            size_hint_x: 1
            theme_icon_color: "Custom"
            icon_color: 0.6, 0.68, 0.83, 1

<HomeScreen@MDScreen>:
    name: "home"
    MDBoxLayout:
        orientation: "vertical"
        spacing: dp(8)
        md_bg_color: C("#0a0f1e")
        padding: dp(16)
        MDBoxLayout:
            orientation: "horizontal"
            size_hint_y: None
            height: dp(48)
            spacing: dp(8)
            MDLabel:
                text: "MusicBox"
                font_style: "H5"
                bold: True
                theme_text_color: "Custom"
                text_color: 1, 1, 1, 1
                size_hint_y: None
                height: dp(48)
                valign: "middle"
            MDIconButton:
                id: refresh_btn
                icon: "refresh"
                theme_icon_color: "Custom"
                icon_color: 0.6, 0.68, 0.83, 1
                size_hint_y: None
                on_release: app.refresh_playlists()
        MDBoxLayout:
            orientation: "horizontal"
            size_hint_y: None
            height: dp(44)
            spacing: dp(8)
            MDRectangleFlatButton:
                id: import_btn
                text: "Importuj"
                size_hint_x: 1
                on_release: app.on_import_playlist()
            MDRectangleFlatButton:
                id: library_btn
                text: "Biblioteka"
                size_hint_x: 1
                on_release: app.show_library()
            MDRectangleFlatButton:
                id: stats_btn
                text: "Statystyki"
                size_hint_x: 1
                on_release: app.show_stats()
        MDLabel:
            id: empty_label
            text: "Brak playlist. Zaimportuj plik .m3u."
            theme_text_color: "Custom"
            text_color: 0.6, 0.68, 0.83, 1
            size_hint_y: None
            height: dp(34)
        MDLabel:
            id: folder_label
            text: ""
            font_size: "11sp"
            theme_text_color: "Custom"
            text_color: 0.45, 0.55, 0.75, 1
            size_hint_y: None
            height: dp(26)
            shorten: True
            shorten_from: "center"
        MDRectangleFlatButton:
            id: grant_btn
            text: "Nadaj dostęp do plików"
            size_hint_y: None
            height: 0
            opacity: 0
            disabled: True
            on_release: app.grant_all_files_access()
        ScrollView:
            GridLayout:
                id: playlist_list
                cols: 2
                spacing: dp(8)
                padding: dp(2)
                size_hint_y: None
                height: self.minimum_height

<PlaylistScreen@MDScreen>:
    name: "playlist"
    MDBoxLayout:
        orientation: "vertical"
        spacing: dp(8)
        md_bg_color: C("#0a0f1e")
        MDBoxLayout:
            orientation: "horizontal"
            size_hint_y: None
            height: dp(56)
            padding: dp(8), 0
            spacing: dp(8)
            MDIconButton:
                icon: "arrow-left"
                on_release: app.show_home()
            MDLabel:
                id: playlist_header
                text: ""
                bold: True
                theme_text_color: "Custom"
                text_color: 1, 1, 1, 1
                size_hint_x: 1
                shorten: True
                shorten_from: "right"
        RecycleView:
            id: playlist_rv
            viewclass: "TrackRow"
            RecycleBoxLayout:
                orientation: "vertical"
                default_size: None, dp(64)
                default_size_hint: 1, None
                size_hint_y: None
                height: self.minimum_height
                spacing: dp(6)
                padding: dp(10), dp(6)

<LibraryScreen@MDScreen>:
    name: "library"
    MDBoxLayout:
        orientation: "vertical"
        spacing: dp(8)
        md_bg_color: C("#0a0f1e")
        MDBoxLayout:
            orientation: "horizontal"
            size_hint_y: None
            height: dp(56)
            padding: dp(8), 0
            spacing: dp(8)
            MDIconButton:
                icon: "arrow-left"
                on_release: app.show_home()
            MDLabel:
                text: "Biblioteka"
                bold: True
                theme_text_color: "Custom"
                text_color: 1, 1, 1, 1
        RecycleView:
            id: library_rv
            viewclass: "TrackRow"
            RecycleBoxLayout:
                orientation: "vertical"
                default_size: None, dp(64)
                default_size_hint: 1, None
                size_hint_y: None
                height: self.minimum_height
                spacing: dp(6)
                padding: dp(10), dp(6)

<StatsScreen@MDScreen>:
    name: "stats"
    MDBoxLayout:
        orientation: "vertical"
        spacing: dp(8)
        md_bg_color: C("#0a0f1e")
        MDBoxLayout:
            orientation: "horizontal"
            size_hint_y: None
            height: dp(56)
            padding: dp(8), 0
            spacing: dp(8)
            MDIconButton:
                icon: "arrow-left"
                on_release: app.show_home()
            MDLabel:
                text: "Statystyki"
                bold: True
                theme_text_color: "Custom"
                text_color: 1, 1, 1, 1
        ScrollView:
            MDBoxLayout:
                id: stats_content
                orientation: "vertical"
                size_hint_y: None
                height: self.minimum_height
                spacing: dp(8)
                padding: dp(16)

BoxLayout:
    orientation: "vertical"
    canvas.before:
        Color:
            rgba: C("#0a0f1e")
        Rectangle:
            pos: self.pos
            size: self.size
    ScreenManager:
        id: manager
        HomeScreen:
            id: home_screen
        PlaylistScreen:
            id: playlist_screen
        LibraryScreen:
            id: library_screen
        StatsScreen:
            id: stats_screen
    PlayerBar:
        id: player_bar
"""


def build_library_playlist(playlists):
    pl = Playlist("Biblioteka")
    seen = set()
    for p in playlists:
        for t in p.tracks:
            if t.path in seen:
                continue
            seen.add(t.path)
            pl.tracks.append(Track(path=t.path, title=t.title))
    pl.current_index = 0 if pl.tracks else -1
    return pl


def _fmt_time(seconds):
    seconds = max(0, int(seconds))
    return f"{seconds // 60}:{seconds % 60:02d}"


class MusicBoxApp(MDApp):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.theme_cls.theme_style = "Dark"
        self.theme_cls.primary_palette = "Blue"
        self.library = Library()
        self.controller = PlaybackController()
        self.audio = AudioPlayer(on_ended=self._on_ended, on_tick=self._on_audio_tick)
        self.stats = Stats(storage.stats_path())
        self._suppress = False
        self._tick_count = 0
        self._stats_tick = 0
        self._updating_slider = False
        self._renaming = False
        self._stats_period_kind = None
        self._stats_period_key = None
        self._month_selection = None
        self._year_selection = None
        self._summary_card_btn = None
        self._summary_generating = False
        self._m3u_last = None
        self._tags_lock = threading.Lock()
        self._scan_lock = threading.Lock()
        self._scanning = False
        self._cache_dirty = False
        self._resume_settings = None
        self._tag_queue = queue.Queue()
        self._cover_queue = queue.Queue()
        self._tick_debug = 0
        self._provider_logged = False
        self._last_state_path = None
        self._play_order = []
        self._tags_cache = self._load_tags_cache()
        self._scrubbing = False

    def build(self):
        t0 = time.time()
        root = Builder.load_string(KV)
        Window.clearcolor = (0.039, 0.059, 0.118, 1)  # po motywie KivyMD, zeby nie zostalo #121212
        self.root = root
        if android_io.is_android():
            android_io.set_system_bar_colors()
        android_io.set_debug_logger(self._debug_log)
        self._wire_player_bar()
        self._start_workers()
        self._setup_media_receiver()
        self.library.playlists = []
        self._restore_prefs()
        self._log_env()
        if android_io.is_android():
            Clock.schedule_once(lambda dt: self._request_permissions(), 1.0)
            if android_io.all_files_access():
                android_io.musicbox_dir()
            else:
                self._schedule_access_prompt()
        Clock.schedule_interval(self._on_tick, 1.0)
        Clock.schedule_interval(self._check_refresh, 10.0)
        Clock.schedule_interval(self._flush_cache, 5.0)
        self._refresh_home()
        self._startup_async()
        self._debug_log("perf: build=%.2fs" % (time.time() - t0))
        return root

    def on_pause(self):
        self._debug_log(
            "on_pause: playing=%s pos=%.1f" % (self.audio.is_playing, self.audio.position())
        )
        return True

    def on_resume(self):
        self._debug_log("on_resume")
        return True

    def on_stop(self):
        try:
            android_io.unregister_media_receiver()
        except Exception:
            pass

    def _schedule_access_prompt(self):
        Clock.schedule_once(lambda dt: self._prompt_all_files_access(), 1.5)

    def _request_permissions(self):
        try:
            android_io.request_storage_permissions(
                lambda permissions, grants: self._debug_log(
                    "perms: %s -> %s" % (permissions, grants)
                )
            )
        except Exception:
            pass

    def _prompt_all_files_access(self):
        if android_io.is_android() and not android_io.all_files_access():
            self._flash_status(
                "MusicBox działa bez 'Wszystkich plików'. Nadaj dostęp, by mieć widoczny folder MusicBox."
            )
            android_io.open_all_files_settings()

    def grant_all_files_access(self):
        if android_io.is_android():
            if android_io.open_all_files_settings():
                self._flash_status(
                    "Nadaj MusicBox dostęp do 'Wszystkich plików' i wróć (opcjonalne)."
                )
            else:
                self._flash_status(
                    "Otwórz ustawienia i nadaj MusicBox 'Wszystkie pliki' (opcjonalne)."
                )

    def _debug_log(self, msg):
        """Zapisuje zdarzenie do widocznego logu (zawsze aktywne)."""
        try:
            print("[MusicBox]", msg)
            target = None
            if android_io.is_android():
                base = android_io.external_log_dir()
                if base:
                    target = os.path.join(base, "MusicBox", "musicbox_debug.log")
            if target is None:
                target = os.path.join(storage.get_data_dir(), "musicbox_debug.log")
            os.makedirs(os.path.dirname(target), exist_ok=True)
            if os.path.isfile(target) and os.path.getsize(target) > 1024 * 1024:
                with open(target, "w", encoding="utf-8") as f:
                    f.write("")
            with open(target, "a", encoding="utf-8") as f:
                f.write(msg + "\n")
        except Exception:
            pass

    def _log_env(self):
        self._debug_log("=== MusicBox start (0.6.1) ===")
        self._debug_log("api_level=%s android=%s" % (android_io.android_api_level(), android_io.is_android()))
        if android_io.is_android():
            self._debug_log("all_files_access=%s" % android_io.all_files_access())
            self._debug_log("musicbox_dir=%s" % android_io.musicbox_dir())
            self._debug_log("external_log_dir=%s" % android_io.external_log_dir())
        self._debug_log("playlists_loaded=%d" % len(self.library.playlists))

    def _playlist_folders(self):
        folders = [storage.playlists_dir()]
        if android_io.is_android():
            m = android_io.musicbox_dir()
            if m:
                folders.append(m)
        return folders

    def _startup_async(self):
        """W watku tla laduje zapisane playlisty + skanuje nowe .m3u."""

        def work():
            playlists = []
            try:
                t0 = time.time()
                playlists = storage.load_saved_playlists()
                self._debug_log("perf: load_saved=%ds pl=%d" % (time.time() - t0, len(playlists)))
            except Exception as e:
                self._debug_log("startup: blad load_saved " + repr(e))
            try:
                new, removed = self._scan_new_playlists(
                    set(p.name for p in playlists), playlists
                )
                playlists.extend(new)
                for name in removed:
                    storage.delete_playlist(name)
                    self._debug_log("skan: usunieto " + name)
            except Exception as e:
                self._debug_log("startup: blad skan " + repr(e))
            Clock.schedule_once(lambda dt: self._startup_applied(playlists), 0)

        threading.Thread(target=work, daemon=True).start()

    def _startup_applied(self, playlists):
        known = {p.name for p in self.library.playlists}
        for pl in playlists:
            if pl.name not in known:
                self.library.playlists.append(pl)
                known.add(pl.name)
        self._restore_resume()
        self._refresh_home()
        self._sync_profile_in()
        self._log_fuse_latency()

    def _scan_playlists_async(self):
        """Skanuje foldery z .m3u w watku tla i dodaje nieznane playlisty."""

        def work():
            try:
                new, removed = self._scan_new_playlists(
                    {p.name for p in self.library.playlists},
                    list(self.library.playlists),
                )
            except Exception:
                new, removed = [], []
            finally:
                with self._scan_lock:
                    self._scanning = False
            Clock.schedule_once(lambda dt: self._apply_scan(new, removed), 0)

        with self._scan_lock:
            if self._scanning:
                return
            self._scanning = True
        threading.Thread(target=work, daemon=True).start()

    def _scan_new_playlists(self, known, playlists):
        new = []
        for folder in self._playlist_folders():
            if not folder or not os.path.isdir(folder):
                self._debug_log("skan: brak folderu " + str(folder))
                continue
            m3u = [n for n in sorted(os.listdir(folder)) if n.lower().endswith(".m3u")]
            self._debug_log("skan: folder=%s, pliki_m3u=%d" % (folder, len(m3u)))
            for name in m3u:
                base = os.path.splitext(name)[0]
                if base in known:
                    continue
                path = os.path.join(folder, name)
                pl = Playlist()
                loaded = 0
                try:
                    loaded = pl.load_m3u(path)
                except OSError as e:
                    self._debug_log("skan: blad load_m3u " + str(path) + " " + repr(e))
                    loaded = 0
                if loaded == 0:
                    self._debug_log("skan: load_m3u=0 dla " + str(path))
                    self._try_materialized_m3u(pl, path)
                if pl.tracks:
                    storage.save_playlist(pl)
                    known.add(pl.name)
                    new.append(pl)
                    self._debug_log("skan: dodano " + pl.name)
        external = android_io.musicbox_dir() if android_io.is_android() else None
        _, removed = storage.prune_missing(playlists, external)
        if removed:
            self._debug_log("skan: %d playlist bez zrodla: %s" % (len(removed), removed))
        if new:
            self._debug_log("skan: %d nowych playlist" % len(new))
        return new, removed

    def _apply_scan(self, new, removed):
        changed = False
        for name in removed:
            self._remove_playlist_by_name(name)
            changed = True
        if new:
            known = {p.name for p in self.library.playlists}
            for pl in new:
                if pl.name in known:
                    continue
                self.library.add_playlist(pl)
                known.add(pl.name)
                changed = True
        if changed:
            self._refresh_home()

    def _remove_playlist_by_name(self, name):
        for pl in list(self.library.playlists):
            if pl.name != name:
                continue
            if self.controller.playlist is pl:
                try:
                    self.audio.stop()
                except Exception:
                    pass
                android_io.stop_playback_service()
                self._clear_resume()
            self.library.playlists.remove(pl)
            external = android_io.musicbox_dir() if android_io.is_android() else None
            storage.delete_source_file(name, external)
            storage.delete_playlist(name)
            self._flash_status("Usunięto playlistę: " + name)
            self._debug_log("usunieto " + name)
            return

    def _log_fuse_latency(self):
        paths = []
        for p in self.library.playlists:
            for t in p.tracks[:12]:
                paths.append(t.path)
        if not paths:
            return
        t0 = time.time()
        for p in paths:
            try:
                os.path.getmtime(p)
            except OSError:
                pass
        dt = time.time() - t0
        self._debug_log(
            "perf: stat_latency=%.1fms/op (%d ops)" % (dt / len(paths) * 1000, len(paths))
        )

    # ---------- UI: nawigacja ----------
    def _screen_ids(self, name):
        return self.root.ids.manager.get_screen(name).ids

    def show_home(self):
        self.root.ids.manager.current = "home"
        self._scan_playlists_async()
        self._refresh_home()

    def show_library(self):
        pl = build_library_playlist(self.library.playlists)
        self.controller.set_playlist(pl)
        self._set_track_data(self._screen_ids("library").library_rv, pl)
        self.root.ids.manager.current = "library"

    def show_stats(self):
        self.stats.maybe_create_year_summary(date.today())
        self.root.ids.manager.current = "stats"
        self._refresh_stats()

    def _refresh_home(self):
        ids = self._screen_ids("home")
        lst = ids.playlist_list
        lst.clear_widgets()
        for i, p in enumerate(self.library.playlists):
            lst.add_widget(self._playlist_tile(i, p))
        ids.empty_label.opacity = 0 if self.library.playlists else 1
        self._debug_log("refresh_home: %d playlist" % len(self.library.playlists))
        grant = android_io.is_android() and not android_io.all_files_access()
        ids.grant_btn.height = dp(40) if grant else 0
        ids.grant_btn.opacity = 1 if grant else 0
        ids.grant_btn.disabled = not grant
        if android_io.is_android():
            mdir = android_io.musicbox_dir()
            if mdir:
                ids.folder_label.text = f"Folder: {mdir}"
            elif not android_io.storage_permission_granted():
                ids.folder_label.text = (
                    "Brak dostępu do multimediów — nadaj uprawnienie w ustawieniach"
                )
            else:
                ids.folder_label.text = "Dostęp do multimediów: ✓"
        else:
            ids.folder_label.text = ""

    def refresh_playlists(self):
        self._scan_playlists_async()
        self._refresh_home()
        self._flash_status("Odświeżono")

    def _check_refresh(self, dt):
        """Okresowe sprawdzenie, czy pojawily sie nowe pliki .m3u."""
        try:
            current = tuple(
                sorted(
                    os.path.basename(f)
                    for folder in self._playlist_folders()
                    if os.path.isdir(folder)
                    for f in os.listdir(folder)
                    if f.lower().endswith(".m3u")
                )
            )
            if current != self._m3u_last and self._m3u_last is not None:
                self._scan_playlists_async()
                self._refresh_home()
            self._m3u_last = current
        except Exception:
            pass

    # ---------- okładki i karty ----------
    def _cover_cache_dir(self):
        d = os.path.join(storage.get_data_dir(), "covers_v2")
        try:
            os.makedirs(d, exist_ok=True)
        except OSError:
            pass
        return d

    def _cover_path(self, path):
        """Zwraca sciezke znormalizowanej okładki (kwadrat 512x512) z cache."""
        try:
            import hashlib

            key = hashlib.md5(str(path).encode("utf-8", "replace")).hexdigest()
            out = os.path.join(self._cover_cache_dir(), key + ".png")
            if os.path.isfile(out):
                return out
            data = extract_cover(path)
            if not data:
                return None
            try:
                from io import BytesIO
                from PIL import Image as PilImage

                img = PilImage.open(BytesIO(data))
                img = img.convert("RGB")
                w, h = img.size
                side = min(w, h)
                left = (w - side) // 2
                top = (h - side) // 2
                img = img.crop((left, top, left + side, top + side))
                img = img.resize((512, 512), PilImage.LANCZOS)
                img.save(out, "PNG")
                return out if os.path.isfile(out) else None
            except Exception:
                out_raw = os.path.join(self._cover_cache_dir(), key + ".img")
                if not os.path.isfile(out_raw):
                    with open(out_raw, "wb") as f:
                        f.write(data)
                return out_raw if os.path.isfile(out_raw) else None
        except Exception:
            return None

    def _tags_cache_path(self):
        return os.path.join(storage.get_data_dir(), "tags_cache.json")

    def _load_tags_cache(self):
        try:
            with open(self._tags_cache_path(), "r", encoding="utf-8") as f:
                data = json.load(f)
            return data if isinstance(data, dict) else {}
        except Exception:
            return {}

    def _save_tags_cache(self):
        try:
            with self._tags_lock:
                with open(self._tags_cache_path(), "w", encoding="utf-8") as f:
                    json.dump(self._tags_cache, f, ensure_ascii=False)
        except Exception:
            pass

    def _flush_cache(self, dt):
        if not self._cache_dirty:
            return
        self._cache_dirty = False
        self._save_tags_cache()

    def _display_meta_cached(self, path):
        """(tytul, artysta) z cache albo None."""
        try:
            mtime = os.path.getmtime(path)
        except OSError:
            mtime = 0
        with self._tags_lock:
            cached = self._tags_cache.get(path)
            if cached and isinstance(cached, list) and len(cached) == 3 and cached[0] == mtime:
                return cached[1], cached[2]
        return None

    def _display_in_worker(self, path, fallback):
        meta = self._display_meta_cached(path)
        if meta is not None:
            return meta
        title = display_title(path, fallback)
        artist = display_artist(path, "")
        mtime = 0
        try:
            mtime = os.path.getmtime(path)
        except OSError:
            pass
        with self._tags_lock:
            if len(self._tags_cache) > 1500:
                self._tags_cache.clear()
            self._tags_cache[path] = [mtime, title, artist]
        self._cache_dirty = True
        return title, artist

    def _display(self, path, fallback):
        """Tytul/wykonawca z trwalym cache (szybkie budowanie list)."""
        meta = self._display_meta_cached(path)
        if meta is not None:
            return combine_name(meta[0], meta[1], fallback)
        name = display_name(path, fallback)
        title = display_title(path, fallback)
        artist = display_artist(path, "")
        mtime = 0
        try:
            mtime = os.path.getmtime(path)
        except OSError:
            pass
        with self._tags_lock:
            if len(self._tags_cache) > 1500:
                self._tags_cache.clear()
            self._tags_cache[path] = [mtime, title, artist]
        self._cache_dirty = True
        return name

    def _start_workers(self):
        for _ in range(4):
            threading.Thread(target=self._tag_worker, daemon=True).start()
        for _ in range(2):
            threading.Thread(target=self._cover_worker, daemon=True).start()

    def enqueue_track(self, path, title, row):
        self._tag_queue.put((path, title, row))

    def enqueue_cover(self, row, path):
        self._cover_queue.put(("row", row, path, None))

    def _tag_worker(self):
        while True:
            item = self._tag_queue.get()
            if item is None:
                break
            path, fallback, row = item
            try:
                title, artist = self._display_in_worker(path, fallback)
            except Exception:
                title, artist = fallback, ""
            Clock.schedule_once(
                lambda dt, r=row, t=title, a=artist, p=path: r.apply_meta(t, a, p), 0
            )
            self._tag_queue.task_done()

    def _cover_worker(self):
        while True:
            item = self._cover_queue.get()
            if item is None:
                break
            kind, container, path, note_size = item
            try:
                cover = self._cover_path(path)
            except Exception:
                cover = None
            Clock.schedule_once(
                lambda dt, k=kind, c=container, cv=cover, p=path, ns=note_size:
                    self._apply_cover(k, c, cv, p, ns),
                0,
            )
            self._cover_queue.task_done()

    def _load_cover_async(self, container, path, note_size="20sp"):
        """Wyciaga okładke w watku tla i aktualizuje widget na glownym watku."""
        self._cover_queue.put(("box", container, path, note_size))

    def _apply_cover(self, kind, container, cover, path, note_size):
        try:
            if kind == "row":
                container.apply_cover(cover, path)
                return
            container.clear_widgets()
            if cover:
                container.add_widget(
                    AsyncImage(source=cover, allow_stretch=True, keep_ratio=True)
                )
            else:
                container.add_widget(
                    MDLabel(
                        text="♪",
                        font_size=note_size,
                        halign="center",
                        valign="middle",
                        theme_text_color="Custom",
                        text_color=(0.35, 0.55, 0.9, 1),
                    )
                )
        except Exception:
            pass

    def _playlist_tile(self, index, playlist):
        card = MDCard(
            orientation="vertical",
            size_hint_y=None,
            height=dp(124),
            radius=[dp(10)],
            elevation=1,
            md_bg_color=(0.07, 0.1, 0.22, 1),
            padding=dp(8),
            spacing=dp(4),
        )
        card._tile_index = index
        card._down_pos = None
        card._down_touch = None
        card._long_timer = None
        card._long_fired = False
        card.bind(
            on_touch_down=self._tile_touch_down,
            on_touch_up=self._tile_touch_up,
            on_touch_move=self._tile_touch_move,
        )
        thumb = MDBoxLayout(
            size_hint_y=None,
            height=dp(76),
            md_bg_color=(0.05, 0.07, 0.16, 1),
            padding=dp(2),
        )
        thumb.add_widget(
            MDLabel(
                text="♪",
                font_size="28sp",
                halign="center",
                valign="middle",
                theme_text_color="Custom",
                text_color=(0.35, 0.55, 0.9, 1),
            )
        )
        card.add_widget(thumb)
        if playlist.tracks:
            self._load_cover_async(thumb, playlist.tracks[0].path, "28sp")
        card.add_widget(
            MDLabel(
                text=playlist.name,
                bold=True,
                size_hint_y=None,
                height=dp(22),
                theme_text_color="Custom",
                text_color=(1, 1, 1, 1),
                shorten=True,
                shorten_from="right",
            )
        )
        card.add_widget(
            MDLabel(
                text=f"{len(playlist.tracks)} utworów",
                font_size="12sp",
                size_hint_y=None,
                height=dp(18),
                theme_text_color="Custom",
                text_color=(0.6, 0.68, 0.83, 1),
            )
        )
        return card

    def _tile_touch_down(self, tile, touch):
        if tile.collide_point(*touch.pos):
            tile._down_pos = (touch.x, touch.y)
            tile._down_touch = touch
            tile._long_fired = False
            tile._long_timer = Clock.schedule_once(
                lambda dt: self._tile_long_fired(tile), 0.5
            )
            self._debug_log("tile: down idx=%s pos=%s" % (tile._tile_index, touch.pos))
        return False

    def _tile_touch_up(self, tile, touch):
        self._tile_cancel(tile)
        if tile._long_fired:
            tile._long_fired = False
            tile._down_pos = None
            tile._down_touch = None
            return True
        if tile.collide_point(*touch.pos) and tile._down_pos is not None:
            dx = abs(touch.x - tile._down_pos[0])
            dy = abs(touch.y - tile._down_pos[1])
            if dx < dp(10) and dy < dp(10):
                self.open_playlist(tile._tile_index)
        tile._down_pos = None
        tile._down_touch = None
        return False

    def _tile_touch_move(self, tile, touch):
        if tile._down_pos is not None:
            dx = abs(touch.x - tile._down_pos[0])
            dy = abs(touch.y - tile._down_pos[1])
            if dx >= dp(30) or dy >= dp(30):
                self._tile_cancel(tile)
                tile._down_pos = None
        return False

    def _tile_cancel(self, tile):
        if tile._long_timer is not None:
            tile._long_timer.cancel()
            tile._long_timer = None

    def _tile_long_fired(self, tile):
        tile._long_timer = None
        if tile._down_touch is None:
            self._debug_log("tile: long BAIL (down_touch None)")
            tile._down_pos = None
            return
        if tile.parent is None:
            self._debug_log("tile: long BAIL (parent None)")
            tile._down_pos = None
            return
        if not tile.collide_point(*tile._down_touch.pos):
            self._debug_log(
                "tile: long BAIL (poza kafelkiem) pos=%s" % (tile._down_touch.pos,)
            )
            tile._down_pos = None
            return
        tile._long_fired = True
        self._debug_log("tile: LONG fired idx=%s" % tile._tile_index)
        self._show_playlist_menu(tile._tile_index)

    def _show_playlist_menu(self, index):
        if not (0 <= index < len(self.library.playlists)):
            self._debug_log("menu: BAIL index=%s poza zakresem" % index)
            return
        pl = self.library.playlists[index]
        try:
            from kivymd.uix.dialog import MDDialog

            dialog = MDDialog(
                title=pl.name,
                type="simple",
                items=[
                    OneLineListItem(
                        text="Usuń",
                        theme_text_color="Custom",
                        text_color=(1, 0.3, 0.3, 1),
                        on_release=lambda *a: self._ask_delete_playlist(pl.name, dialog),
                    ),
                    OneLineListItem(text="Anuluj", on_release=lambda *a: dialog.dismiss()),
                ],
            )
            dialog.open()
            self._debug_log("menu: MDDialog otwarty idx=%s" % index)
        except Exception as e:
            self._debug_log("menu: MDDialog FAILED: %r" % (e,))
            self._flash_delete_fallback(pl.name)

    def _flash_delete_fallback(self, name):
        """Fallback gdy MDDialog nie działa — Snackbar z przyciskiem Usuń."""
        try:
            from kivymd.uix.snackbar import Snackbar

            Snackbar(
                text="Usunąć playlistę „%s”?" % name,
                snackbar_x="12dp",
                snackbar_y="150dp",
                size_hint_x=0.9,
                duration=4,
                buttons=[
                    MDRectangleFlatButton(
                        text="Usuń",
                        text_color=(1, 0.3, 0.3, 1),
                        on_release=lambda *a: self._delete_playlist(name),
                    )
                ],
            ).open()
        except Exception as e:
            self._debug_log("menu: Snackbar fallback FAILED: %r" % (e,))
            self._delete_playlist(name)

    def _ask_delete_playlist(self, name, parent):
        try:
            parent.dismiss()
        except Exception:
            pass
        try:
            from kivymd.uix.dialog import MDDialog
        except Exception:
            self._remove_playlist_by_name(name)
            self._refresh_home()
            return
        confirm = MDDialog(
            title="Usunąć playlistę?",
            text="„%s” i jej plik .m3u z folderu MusicBox/" % name,
            buttons=[
                MDRectangleFlatButton(text="Anuluj", on_release=lambda *a: confirm.dismiss()),
                MDRectangleFlatButton(
                    text="Usuń",
                    on_release=lambda *a: (confirm.dismiss(), self._delete_playlist(name)),
                ),
            ],
        )
        confirm.open()

    def _delete_playlist(self, name):
        self._remove_playlist_by_name(name)
        if self.root.ids.manager.current == "playlist":
            self.show_home()
        else:
            self._refresh_home()

    def open_playlist(self, index):
        pl = self.library.switch_to(index)
        if pl is None:
            return
        self.controller.set_playlist(pl)
        self._set_track_data(self._screen_ids("playlist").playlist_rv, pl)
        self._screen_ids("playlist").playlist_header.text = pl.name
        self.root.ids.manager.current = "playlist"

    def _set_track_data(self, rv, playlist):
        t0 = time.time()
        rv.data = [
            {"path": t.path, "title": t.title, "index": i}
            for i, t in enumerate(playlist.tracks)
        ]
        self._debug_log(
            "perf: rv_data=%d utw %dms" % (len(rv.data), (time.time() - t0) * 1000)
        )

    def _on_track_clicked(self, index):
        track = self.controller.play_at(index)
        if track:
            self._play_track(track)

    # ---------- import .m3u ----------
    def on_import_playlist(self):
        if android_io.is_android():
            try:
                self._debug_log(
                    "import: klik Importuj, all_files=%s" % android_io.all_files_access()
                )
                android_io.musicbox_dir()
                self._debug_log("import: otwieram picker")
                if not android_io.pick_m3u(self._on_import_selected):
                    self._flash_status("Nie udało się otworzyć wyboru pliku")
            except Exception as e:
                self._debug_log("import: wyjatek " + repr(e))
                self._flash_status("Błąd przy wyborze pliku")
            return
        try:
            from plyer import filechooser
        except Exception:
            self._flash_status("Brak plyer — nie można wybrać pliku")
            return
        try:
            filechooser.open_file(
                filters=[("Playlisty", "*.m3u", "*.m3u8")],
                on_selection=lambda sel: Clock.schedule_once(
                    lambda dt, s=sel: self._on_import_selected(s)
                ),
            )
        except Exception:
            self._flash_status("Błąd przy wyborze pliku")

    def _on_import_selected(self, selection, error=None):
        self._debug_log(
            "import: on_selected selection=%s error=%s" % (list(selection), error)
        )
        if error:
            self._flash_status(error)
            return
        if not selection:
            self._debug_log("import: pusta selekcja (anulowano lub blad)")
            self._flash_status("Nie wybrano pliku (anulowano lub błąd wyboru)")
            return
        uri = selection[0]
        self._debug_log("import: uri=" + str(uri))
        threading.Thread(target=self._import_worker, args=(uri,), daemon=True).start()

    def _import_worker(self, uri):
        pl = None
        try:
            path = android_io.resolve_playlist_path(uri)
            if not path:
                self._debug_log("import: resolve_playlist_path zwrocilo None")
                Clock.schedule_once(
                    lambda dt: self._flash_status("Nie udało się odczytać pliku"), 0
                )
                return
            self._debug_log("import: path=" + str(path))
            pl = Playlist()
            loaded = 0
            try:
                loaded = pl.load_m3u(path)
            except OSError:
                loaded = 0
            if loaded == 0:
                self._debug_log("import: load_m3u=0, proba materializacji")
                self._try_materialized_m3u(pl, path)
        except Exception as e:
            self._debug_log("import: blad " + repr(e))
            pl = None
        finally:
            android_io.cleanup_import_files()
        Clock.schedule_once(lambda dt, p=pl: self._import_applied(p), 0)

    def _import_applied(self, pl):
        if pl is None:
            self._flash_status("Nie udało się odczytać pliku")
            return
        if not pl.tracks:
            self._debug_log("import: 0 utworow")
            self._flash_status(
                "Brak utworów. Sprawdź, czy aplikacja ma zgodę na multimedia i czy .m3u wskazuje istniejące pliki."
            )
            return
        self._debug_log("import: %d utworow, nazwa=%s" % (len(pl.tracks), pl.name))
        self.library.add_playlist(pl)
        storage.save_playlist(pl)
        self.root.ids.manager.current = "home"
        self._scan_playlists_async()
        self._refresh_home()
        self._flash_status(f"Dodano playlistę: {pl.name}")

    def _try_materialized_m3u(self, pl, path):
        """Gdy .m3u nie rozwiazal sciezek wzglednych, probuje znalezc
        pliki po nazwie w MediaStore."""
        try:
            with open(path, "rb") as f:
                raw = f.read()
        except OSError as e:
            self._debug_log("m3u: NIE MOGĘ ODCZYTAĆ " + str(path) + " " + repr(e))
            return
        names = android_io.m3u_basenames(raw)
        self._debug_log("m3u: odczytano, nazwy=%s" % names)
        if not names:
            return
        found = android_io.find_media_paths(names)
        self._debug_log("m3u: media_paths=%s" % found)
        for name, p in zip(names, found):
            if p:
                title = os.path.splitext(name)[0]
                pl.tracks.append(Track(path=p, title=title))
        if pl.tracks:
            pl.name = os.path.splitext(os.path.basename(path))[0] or "Playlista"
            pl.current_index = 0

    def _flash_status(self, text):
        try:
            from kivymd.uix.snackbar import Snackbar

            Snackbar(
                text=str(text),
                snackbar_x="12dp",
                snackbar_y="150dp",
                size_hint_x=0.9,
                duration=2.5,
            ).open()
        except Exception:
            Clock.schedule_once(lambda dt: self._set_status(text), 0)

    def _set_status(self, text):
        self._screen_ids("home").empty_label.text = text

    # ---------- odtwarzanie ----------
    def _wire_player_bar(self):
        pb = self.root.ids.player_bar
        pb.ids.play_btn.on_release = self.toggle_play
        pb.ids.next_btn.on_release = self.play_next
        pb.ids.prev_btn.on_release = self.play_prev
        pb.ids.shuffle_btn.on_release = self.toggle_shuffle
        pb.ids.repeat_btn.on_release = self.cycle_repeat
        slider = pb.ids.progress_slider
        slider.bind(value=self._on_seek_slider)
        slider.bind(on_touch_down=self._on_slider_touch_down)
        slider.bind(on_touch_up=self._on_slider_touch_up)

    def _setup_media_receiver(self):
        """Odbiera broadcasty stanu/pozycji od KeepAliveService (app-context)."""
        if not android_io.is_android():
            return
        try:

            def _on_bcast(context, intent):
                action = intent.getAction()
                if action == STATE_CHANGED:
                    state = {
                        "path": intent.getStringExtra("path"),
                        "index": intent.getIntExtra("index", -1),
                        "playing": intent.getBooleanExtra("playing", False),
                        "ended": intent.getBooleanExtra("ended", False),
                        "title": intent.getStringExtra("title"),
                        "cover": intent.getStringExtra("cover"),
                    }
                    Clock.schedule_once(lambda dt: self._on_media_state(state), 0)
                elif action == STATE_POSITION:
                    pos = intent.getIntExtra("position_ms", 0)
                    dur = intent.getIntExtra("duration_ms", 0)
                    Clock.schedule_once(
                        lambda dt, p=pos, d=dur: self._on_media_position(p, d), 0
                    )

            ok = android_io.register_media_receiver(
                _on_bcast,
                [STATE_CHANGED, STATE_POSITION],
            )
            self._debug_log("media_receiver: %s" % ("ok" if ok else "brak"))
        except Exception as e:
            self._debug_log("media_receiver: blad " + repr(e))

    def _on_media_action(self, action):
        self._debug_log("media_action: " + str(action))
        try:
            if action == "org.musicbox.musicbox.action.PLAY_PAUSE":
                self.toggle_play()
            elif action == "org.musicbox.musicbox.action.NEXT":
                self.play_next()
            elif action == "org.musicbox.musicbox.action.PREV":
                self.play_prev()
            elif action == "org.musicbox.musicbox.action.STOP":
                self.audio.stop()
                android_io.stop_playback_service()
                self._set_play_icon()
                self._clear_resume()
        except Exception:
            pass

    def _on_media_state(self, state):
        path = state.get("path") or ""
        index = int(state.get("index", -1))
        playing = bool(state.get("playing", False))
        ended = bool(state.get("ended", False))
        self.audio.apply_state(path, index, playing, ended, "", "")
        if ended:
            self._set_play_icon()
            self._clear_resume()
            self._last_state_path = ""
            return
        pl = self.controller.playlist
        matched = -1
        if pl is not None and path:
            for i, t in enumerate(pl.tracks):
                if t.path == path:
                    matched = i
                    break
            if matched >= 0:
                pl.current_index = matched
        if playing and path and matched >= 0 and path != self._last_state_path:
            self._last_state_path = path
            if pl is not None and pl.current() is not None:
                self._update_now_label(pl.current())
                if self.stats.has_profile:
                    self.stats.increment_play(pl.current().path)
                    self.stats.save()
                    self._sync_profile_out()
                self._persist_settings()
        self._set_play_icon()

    def _on_media_position(self, position_ms, duration_ms):
        self.audio.apply_position(position_ms, duration_ms)

    def _repeat_int(self):
        return {"all": 1, "one": 2, "off": 0}.get(self.controller.repeat_mode, 1)

    def _rebuild_play_order(self, keep_current=True):
        """Kolejnosc odtwarzania dla serwisu (naturalna albo potasowana)."""
        pl = self.controller.playlist
        if pl is None or not pl.tracks:
            self._play_order = []
            return
        paths = [t.path for t in pl.tracks]
        if not self.controller.shuffle_on:
            self._play_order = paths
            return
        order = paths[:]
        random.shuffle(order)
        current = self.controller.current()
        if keep_current and current is not None and current.path in order:
            order.remove(current.path)
            order = [current.path] + order
        self._play_order = order

    def _play_order_index(self, path):
        if path in self._play_order:
            return self._play_order.index(path)
        return 0

    def _send_playlist_meta(self, pl):
        """Wysyla do serwisu tytuly (szybko) i okładki (rownolegle) w kolejnosc odtwarzania."""

        def work():
            try:
                if pl is None or not pl.tracks:
                    return
                order = self._play_order or [t.path for t in pl.tracks]
                by_path = {t.path: t for t in pl.tracks}
                self._debug_log("meta: start %d" % len(order))
                names = []
                for p in order:
                    t = by_path.get(p)
                    names.append(self._display(p, t.title) if t else "")
                self._debug_log("meta: tytuly gotowe")
                self.audio.send_meta(names, [], has_covers=False)
                covers = [""] * len(order)
                lock = threading.Lock()
                q = queue.Queue()

                def compute():
                    while True:
                        i = q.get()
                        if i is None:
                            break
                        c = None
                        try:
                            c = self._cover_path(order[i])
                        except Exception:
                            c = None
                        with lock:
                            covers[i] = c or ""
                        q.task_done()

                for _ in range(4):
                    threading.Thread(target=compute, daemon=True).start()
                for i in range(len(order)):
                    q.put(i)
                q.join()
                for _ in range(4):
                    q.put(None)
                self._debug_log("meta: okładki gotowe")
                self.audio.send_meta(names, covers, has_covers=True)
                self._debug_log("meta: wyslano %d utworow" % len(order))
            except Exception as e:
                self._debug_log("meta: blad " + repr(e))

        threading.Thread(target=work, daemon=True).start()

    def _play_track(self, track):
        if track is None:
            return
        if android_io.is_android():
            pl = self.controller.playlist
            if not self._play_order or track.path not in self._play_order:
                self._rebuild_play_order(keep_current=False)
            paths = self._play_order or ([t.path for t in pl.tracks] if pl else [])
            index = self._play_order_index(track.path)
            name = self._display(track.path, track.title) or track.title or "MusicBox"
            cover = None
            try:
                cover = self._cover_path(track.path)
            except Exception:
                cover = None
            self.audio.play(track.path, index, paths, self._repeat_int(), name, cover)
            self._send_playlist_meta(pl)
            self._debug_log("audio: play %s" % track.path)
            self._update_now_label(track)
            self._set_play_icon()
            return
        t0 = time.time()
        ok = self.audio.play_file(track.path)
        if not ok:
            self._flash_status("Nie udało się odtworzyć utworu")
            self._set_play_icon()
            return
        if not self._provider_logged:
            self._provider_logged = True
            self._debug_log("audio: provider=%s" % self.audio.provider_name())
        self._debug_log(
            "audio: play %.0fms %s" % ((time.time() - t0) * 1000, track.path)
        )
        name = self._display(track.path, track.title) or track.title or "MusicBox"
        cover = None
        try:
            cover = self._cover_path(track.path)
        except Exception:
            cover = None
        android_io.start_playback_service(name, cover)
        self._set_play_icon()
        self._update_now_label(track)
        if self.stats.has_profile:
            self.stats.increment_play(track.path)
            self.stats.save()
            self._sync_profile_out()
        self._persist_settings()

    def _update_now_label(self, track):
        if track is None:
            return
        title = display_title(track.path, track.title) or track.title or "Brak utworu"
        artist = display_artist(track.path, "")
        pb = self.root.ids.player_bar.ids
        pb.track_label.text = title
        if "artist_label" in pb:
            pb.artist_label.text = artist or ""

    def _set_play_icon(self):
        self.root.ids.player_bar.ids.play_btn.icon = "pause" if self.audio.is_playing else "play-circle"

    def toggle_play(self):
        pl = self.controller.playlist
        if pl is None:
            return
        if android_io.is_android():
            if pl.current() is None and pl.tracks:
                self._play_track(pl.tracks[0])
                return
            if self.audio.is_playing:
                self.audio.pause()
            else:
                if self.audio.current_source:
                    self.audio.resume()
                else:
                    index = pl.current_index if pl.current_index >= 0 else 0
                    if 0 <= index < len(pl.tracks):
                        self._play_track(pl.tracks[index])
            self._set_play_icon()
            return
        if pl.current() is None and pl.tracks:
            self._play_track(self.controller.play_at(0))
            return
        if self.audio.is_playing:
            self.audio.pause()
            android_io.set_playback_paused(True)
            self._set_play_icon()
        else:
            restarted = self.controller.resume_after_round()
            if restarted is not None:
                self._play_track(restarted)
                return
            if self.audio.current_source:
                self.audio.resume()
                android_io.set_playback_paused(False)
            else:
                index = pl.current_index if pl.current_index >= 0 else 0
                self._play_track(self.controller.play_at(index))
            self._set_play_icon()

    def play_next(self):
        if android_io.is_android():
            self.audio.next_track()
            return
        track = self.controller.play_next()
        if track:
            self._play_track(track)

    def play_prev(self):
        if android_io.is_android():
            self.audio.prev_track()
            return
        track = self.controller.play_prev()
        if track:
            self._play_track(track)

    def toggle_shuffle(self):
        self.controller.set_shuffle(not self.controller.shuffle_on)
        self._refresh_shuffle_repeat_icons()
        if android_io.is_android():
            self._rebuild_play_order(keep_current=True)
            self._send_play_order()
            pl = self.controller.playlist
            if pl is not None:
                self._send_playlist_meta(pl)
        self._persist_settings()

    def _send_play_order(self):
        pl = self.controller.playlist
        if not self._play_order:
            return
        by_path = {t.path: t for t in pl.tracks} if pl else {}
        titles = [by_path[p].title if p in by_path else "" for p in self._play_order]
        self.audio.send_order(self._play_order, titles, [], has_covers=False)

    def cycle_repeat(self):
        modes = [REPEAT_ALL, REPEAT_ONE, REPEAT_OFF]
        current = self.controller.repeat_mode
        if current not in modes:
            current = REPEAT_ALL
        self.controller.set_repeat(modes[(modes.index(current) + 1) % 3])
        self._refresh_shuffle_repeat_icons()
        if android_io.is_android():
            self.audio.set_repeat(self._repeat_int())
        self._persist_settings()

    def _refresh_shuffle_repeat_icons(self):
        pb = self.root.ids.player_bar
        pb.ids.shuffle_btn.icon_color = (
            (0.35, 0.75, 1, 1) if self.controller.shuffle_on else (0.6, 0.68, 0.83, 1)
        )
        icons = {REPEAT_ALL: "repeat", REPEAT_ONE: "repeat-once", REPEAT_OFF: "repeat"}
        pb.ids.repeat_btn.icon = icons.get(self.controller.repeat_mode, "repeat")
        pb.ids.repeat_btn.icon_color = (
            (0.35, 0.75, 1, 1) if self.controller.repeat_mode != REPEAT_OFF else (0.6, 0.68, 0.83, 1)
        )

    def _on_ended(self):
        if android_io.is_android():
            return
        action, track = self.controller.on_playback_ended()
        if action == "replay":
            self.audio.replay()
        elif action == "next":
            self._play_track(track)
        else:
            self.audio.stop()
            android_io.stop_playback_service()
            self._set_play_icon()
            self._clear_resume()

    # ---------- audio: suwaki i tick ----------
    def _on_slider_touch_down(self, slider, touch):
        if slider.collide_point(*touch.pos):
            self._scrubbing = True

    def _on_slider_touch_up(self, slider, touch):
        was = self._scrubbing
        self._scrubbing = False
        if was:
            self.audio.seek(slider.value)

    def _on_audio_tick(self, pos, length):
        slider = self.root.ids.player_bar.ids.progress_slider
        self._tick_debug += 1
        if self._tick_debug % 8 == 0:
            self._debug_log("tick: pos=%.1f len=%s scrubbing=%s" % (pos, length, self._scrubbing))
        self._updating_slider = True
        try:
            slider.max = length or 1
            if not self._scrubbing:
                slider.value = pos
        finally:
            self._updating_slider = False
        pb = self.root.ids.player_bar.ids
        pb.time_pos.text = _fmt_time(pos)
        pb.time_total.text = _fmt_time(length)

    def _on_seek_slider(self, slider, value):
        if self._updating_slider or self._scrubbing:
            return
        self.audio.seek(value)

    def _on_tick(self, dt):
        if self.audio.is_playing:
            self._tick_count += 1
            if self._tick_count >= 10:
                self._tick_count = 0
                self._persist_settings()
        if self.stats.has_profile and self.audio.is_playing:
            self.stats.add_listening(1)
            self._stats_tick += 1
            if self._stats_tick >= 10:
                self._stats_tick = 0
                self.stats.save()
                self._sync_profile_out()

    # ---------- statystyki ----------
    @staticmethod
    def _month_label(key):
        _PL = ["Styczeń", "Luty", "Marzec", "Kwiecień", "Maj", "Czerwiec",
               "Lipiec", "Sierpień", "Wrzesień", "Październik", "Listopad", "Grudzień"]
        try:
            year, month = str(key).split("-")
            return f"{_PL[int(month) - 1]} {year}"
        except Exception:
            return str(key)

    def _stats_text(self, text, bold=False, muted=False):
        color = (0.6, 0.68, 0.83, 1) if muted else (0.9, 0.93, 1, 1)
        return MDLabel(
            text=text,
            bold=bold,
            theme_text_color="Custom",
            text_color=color,
            halign="left",
            valign="top",
            size_hint_y=None,
            height=dp(26),
            font_size="15sp" if not muted else "13sp",
        )

    def _period_summary_text(self, summary):
        lines = ["Czas słuchania: " + format_listening(summary.get("listening_seconds", 0))]
        pc = summary.get("play_counts") or {}
        ac = summary.get("artist_counts") or {}
        lines.append("Liczba odsłuchań: " + str(sum(pc.values())))
        top = sorted(pc.items(), key=lambda kv: (-kv[1], kv[0].lower()))[:3]
        if top:
            lines.append("Najczęściej słuchane utwory:")
            for i, (p, c) in enumerate(top, 1):
                lines.append(f"{i}. {self._display(p, os.path.basename(p))} — {c}")
        else:
            lines.append("Najczęściej słuchane utwory: brak")
        ta = sorted(ac.items(), key=lambda kv: (-kv[1], kv[0].lower()))[:3]
        if ta:
            lines.append("Najczęściej słuchani wykonawcy:")
            for i, (a, c) in enumerate(ta, 1):
                lines.append(f"{i}. {a} — {c}")
        else:
            lines.append("Najczęściej słuchani wykonawcy: brak")
        return "\n".join(lines)

    def create_profile(self):
        inp = getattr(self, "_profile_input", None)
        if inp is None:
            return
        text = inp.text.strip()
        if text and self.stats.create_profile(text):
            self._sync_profile_out()
            self._refresh_stats()
            self._flash_status("Utworzono profil")

    def _toggle_rename(self):
        self._renaming = not self._renaming
        box = getattr(self, "_rename_box", None)
        if box is not None:
            box.height = dp(120) if self._renaming else 0
            box.opacity = 1 if self._renaming else 0
            box.disabled = not self._renaming
            if self._renaming:
                self._rename_input.text = self.stats.profile_name

    def _save_rename(self):
        name = getattr(self, "_rename_input", None)
        if name is None:
            return
        text = name.text.strip()
        if text and self.stats.rename_profile(text):
            self._renaming = False
            self._sync_profile_out()
            self._refresh_stats()
            self._flash_status("Zmieniono nazwę profilu")

    def _reset_profile(self):
        if self.stats.reset():
            self._sync_profile_out()
            self._refresh_stats()
            self._flash_status("Zresetowano statystyki")

    def _profile_export_path(self):
        mdir = android_io.musicbox_dir() if android_io.is_android() else None
        if not mdir:
            mdir = storage.get_data_dir()
        return os.path.join(mdir, "profil.json")

    def _export_profile(self):
        path = self._profile_export_path()
        if self.stats.export(path):
            self._sync_profile_out()
            self._flash_status("Zapisano profil: " + os.path.basename(path))
        else:
            self._flash_status("Nie udało się zapisać profilu")

    def _import_profile(self):
        if android_io.is_android():
            if not android_io.pick_m3u(self._on_profile_selected):
                self._flash_status("Nie udało się otworzyć wyboru pliku")
            return
        try:
            from plyer import filechooser
            filechooser.open_file(
                filters=[("Profil", "*.json")],
                on_selection=lambda sel: Clock.schedule_once(
                    lambda dt, s=sel: self._on_profile_selected(s)
                ),
            )
        except Exception:
            self._flash_status("Brak plyer — nie można wybrać pliku")

    def _on_profile_selected(self, selection, error=None):
        if error:
            self._flash_status(error)
            return
        if not selection:
            return
        if self.stats.import_(selection[0]):
            android_io.cleanup_import_files()
            self._sync_profile_out()
            self._refresh_stats()
            self._flash_status("Zaimportowano profil")
        else:
            android_io.cleanup_import_files()
            self._flash_status("Nie udało się wczytać profilu")

    def _sync_profile_out(self):
        try:
            if not self.stats.has_profile:
                return
            path = self._profile_export_path()
            if path:
                self.stats.export(path)
        except Exception:
            pass

    def _sync_profile_in(self):
        try:
            if not android_io.is_android():
                return
            mdir = android_io.musicbox_dir()
            if not mdir:
                return
            src = os.path.join(mdir, "profil.json")
            if not os.path.isfile(src):
                return
            local = self.stats.path
            if os.path.isfile(local) and os.path.getmtime(src) <= os.path.getmtime(local):
                return
            if self.stats.import_(src):
                self._debug_log("profil: zaimportowano z MusicBox")
        except Exception:
            pass

    def _render_active_summary(self):
        text = ""
        if self._stats_period_kind == "month" and self._stats_period_key:
            s = self.stats.month_summary(self._stats_period_key)
            if s:
                text = (
                    f"Podsumowanie miesiąca: {self._month_label(self._stats_period_key)}\n\n"
                    + self._period_summary_text(s)
                )
        elif self._stats_period_kind == "year" and self._stats_period_key:
            for s in self.stats.year_summaries():
                if int(s.get("year", 0)) == self._stats_period_key:
                    text = (
                        f"Podsumowanie roku {self._stats_period_key}\n\n"
                        + self._period_summary_text(s)
                    )
                    break
        label = getattr(self, "_summary_label", None)
        if label is not None:
            label.text = text

    def _current_summary(self):
        """(etykieta, summary) dla aktualnie wybranego okresu albo None."""
        if self._stats_period_kind == "month" and self._stats_period_key:
            s = self.stats.month_summary(self._stats_period_key)
            if s:
                return (self._month_label(self._stats_period_key), s)
        elif self._stats_period_kind == "year" and self._stats_period_key:
            for s in self.stats.year_summaries():
                if int(s.get("year", 0)) == self._stats_period_key:
                    return ("Rok {}".format(self._stats_period_key), s)
        return None

    def _update_summary_button(self):
        btn = getattr(self, "_summary_card_btn", None)
        if btn is None:
            return
        has = self._current_summary() is not None and not self._summary_generating
        btn.disabled = not has
        btn.md_bg_color = (0.24, 0.48, 1, 1) if has else (0.16, 0.18, 0.28, 1)

    def _on_summary_card(self):
        current = self._current_summary()
        if current is None:
            self._flash_status("Najpierw wybierz miesiąc lub rok")
            return
        if self._summary_generating:
            return
        label, summary = current
        self._summary_generating = True
        btn = getattr(self, "_summary_card_btn", None)
        if btn is not None:
            btn.disabled = True
            btn.text = "Generowanie…"
        profile = self.stats.profile_name or "MusicBox"
        cover_dir = self._cover_cache_dir()
        threading.Thread(
            target=self._summary_card_worker,
            args=(profile, label, summary, cover_dir),
            daemon=True,
        ).start()

    def _summary_card_worker(self, profile, label, summary, cover_dir):
        from io import BytesIO

        from core.summary_pillow import render_summary_card

        try:
            image = render_summary_card(profile, label, summary, cover_dir=cover_dir)
            buf = BytesIO()
            image.save(buf, "PNG")
            data = buf.getvalue()
            slug = label.lower().replace(" ", "_")
            name = "podsumowanie_{}.png".format(
                "".join(c if c.isalnum() else "_" for c in slug)
            )
            saved = android_io.save_summary_png(data, name)
        except Exception as e:
            self._debug_log("summary_card: blad " + repr(e))
            saved, error = None, "Nie udało się wygenerować karty"
        else:
            error = None
        Clock.schedule_once(
            lambda dt: self._summary_card_done(saved, (saved or {}).get("uri"), error), 0
        )

    def _summary_card_done(self, saved, uri, error):
        self._summary_generating = False
        btn = getattr(self, "_summary_card_btn", None)
        if btn is not None:
            btn.text = "Karta + udostępnij"
        self._update_summary_button()
        if error:
            self._flash_status(error)
            return
        path = (saved or {}).get("path")
        if uri:
            self._debug_log("summary_card: zapisano path=%s uri=%s" % (path, uri))
            if android_io.share_file(uri):
                self._flash_status("Karta zapisana i udostępniona")
                return
            self._flash_status("Karta zapisana (udostępnianie niedostępne)")
            return
        if path:
            self._flash_status("Karta zapisana: " + os.path.basename(path))
            return
        self._flash_status("Nie udało się zapisać karty")

    def _on_month_spinner(self, text):
        for key in self.stats.months():
            if self._month_label(key) == text:
                self._stats_period_kind = "month"
                self._stats_period_key = key
                self._month_selection = text
                self._render_active_summary()
                self._update_summary_button()
                return

    def _on_year_spinner(self, text):
        try:
            year = int(str(text).replace("Rok", "").strip())
        except ValueError:
            return
        self._stats_period_kind = "year"
        self._stats_period_key = year
        self._year_selection = text
        self._render_active_summary()
        self._update_summary_button()

    def _refresh_stats(self):
        self.stats.maybe_create_year_summary(date.today())
        content = self._screen_ids("stats").stats_content
        content.clear_widgets()
        has = self.stats.has_profile
        if not has:
            content.add_widget(
                self._stats_text(
                    "Załóż profil, aby śledzić czas słuchania i najczęściej odtwarzane utwory.",
                    muted=True,
                )
            )
            inp = MDTextField(
                hint_text="Nazwa profilu…",
                size_hint_y=None,
                height=dp(48),
                multiline=False,
            )
            self._profile_input = inp
            content.add_widget(inp)
            content.add_widget(
                MDRectangleFlatButton(
                    text="Załóż profil",
                    size_hint_y=None,
                    height=dp(44),
                    on_release=lambda *a: self.create_profile(),
                )
            )
            return

        content.add_widget(self._stats_text(f"Profil: {self.stats.profile_name}", bold=True))
        content.add_widget(
            self._stats_text(
                "Czas słuchania: " + format_listening(self.stats.total_listening_seconds()),
                muted=True,
            )
        )
        top = self.stats.top_tracks(3)
        if top:
            content.add_widget(self._stats_text("Top 3 najczęściej słuchane utwory", bold=True))
            for i, (p, c) in enumerate(top, 1):
                content.add_widget(
                    self._stats_text(f"{i}. {self._display(p, os.path.basename(p))} — {c} odsłuchań", muted=True)
                )
        ta = self.stats.top_artists(3)
        if ta:
            content.add_widget(self._stats_text("Top 3 najczęściej słuchani wykonawcy", bold=True))
            for i, (a, c) in enumerate(ta, 1):
                content.add_widget(self._stats_text(f"{i}. {a} — {c} odsłuchań", muted=True))

        row1 = MDBoxLayout(orientation="horizontal", size_hint_y=None, height=dp(44), spacing=dp(6))
        row1.add_widget(MDRectangleFlatButton(text="Zmień profil", size_hint_x=1, on_release=lambda *a: self._toggle_rename()))
        row1.add_widget(MDRectangleFlatButton(text="Reset", size_hint_x=1, on_release=lambda *a: self._reset_profile()))
        content.add_widget(row1)
        row2 = MDBoxLayout(orientation="horizontal", size_hint_y=None, height=dp(44), spacing=dp(6))
        row2.add_widget(MDRectangleFlatButton(text="Eksport", size_hint_x=1, on_release=lambda *a: self._export_profile()))
        row2.add_widget(MDRectangleFlatButton(text="Import", size_hint_x=1, on_release=lambda *a: self._import_profile()))
        content.add_widget(row2)

        rename_box = MDBoxLayout(orientation="vertical", size_hint_y=None, spacing=dp(6))
        rename_input = MDTextField(
            hint_text="Nowa nazwa profilu…",
            size_hint_y=None,
            height=dp(44),
            multiline=False,
        )
        rename_box.add_widget(rename_input)
        rb = MDBoxLayout(orientation="horizontal", size_hint_y=None, height=dp(44), spacing=dp(6))
        rb.add_widget(MDRectangleFlatButton(text="Zapisz", size_hint_x=1, on_release=lambda *a: self._save_rename()))
        rb.add_widget(MDRectangleFlatButton(text="Anuluj", size_hint_x=1, on_release=lambda *a: self._toggle_rename()))
        rename_box.add_widget(rb)
        self._rename_box = rename_box
        self._rename_input = rename_input
        rename_box.height = dp(120) if self._renaming else 0
        rename_box.opacity = 1 if self._renaming else 0
        rename_box.disabled = not self._renaming
        if self._renaming:
            rename_input.text = self.stats.profile_name
        content.add_widget(rename_box)

        content.add_widget(self._stats_text("Podsumowania", bold=True))
        months = self.stats.months()
        years = self.stats.year_summaries()
        if months:
            mspin = Spinner(
                text=self._month_selection or "— wybierz miesiąc —",
                values=[self._month_label(k) for k in reversed(months)],
                size_hint_y=None,
                height=dp(44),
                background_color=(0.1, 0.14, 0.28, 1),
                on_text=self._on_month_spinner,
            )
            self._month_spinner = mspin
            content.add_widget(mspin)
        if years:
            yspin = Spinner(
                text=self._year_selection or "— wybierz rok —",
                values=["Rok " + str(s.get("year")) for s in years],
                size_hint_y=None,
                height=dp(44),
                background_color=(0.1, 0.14, 0.28, 1),
                on_text=self._on_year_spinner,
            )
            self._year_spinner = yspin
            content.add_widget(yspin)
        summary = MDLabel(
            text="",
            theme_text_color="Custom",
            text_color=(0.85, 0.9, 1, 1),
            halign="left",
            valign="top",
            size_hint_y=None,
            text_size=(dp(330), None),
            font_size="13sp",
        )
        summary.bind(texture_size=lambda *a: setattr(summary, "height", summary.texture_size[1]))
        self._summary_label = summary
        content.add_widget(summary)
        card_btn = MDRectangleFlatButton(
            text="Karta + udostępnij",
            size_hint_y=None,
            height=dp(44),
            on_release=lambda *a: self._on_summary_card(),
        )
        self._summary_card_btn = card_btn
        content.add_widget(card_btn)
        self._render_active_summary()
        self._update_summary_button()

    # ---------- zapamiętywanie sesji ----------
    def _find_playlist_by_path(self, path):
        target = os.path.normcase(os.path.abspath(path))
        for p in self.library.playlists:
            for t in p.tracks:
                if os.path.normcase(os.path.abspath(t.path)) == target:
                    return p
        return None

    def _index_of_path(self, playlist, path):
        target = os.path.normcase(os.path.abspath(path))
        for i, t in enumerate(playlist.tracks):
            if os.path.normcase(os.path.abspath(t.path)) == target:
                return i
        return -1

    def _persist_settings(self):
        if self._suppress:
            return
        resume = None
        src = self.controller.current()
        if src is not None and os.path.isfile(src.path):
            resume = {
                "path": src.path,
                "position_ms": max(0, int(self.audio.position() * 1000)),
                "playlist": self.controller.playlist.name if self.controller.playlist else None,
            }
        storage.save_settings(
            {
                "shuffle": self.controller.shuffle_on,
                "repeat": self.controller.repeat_mode,
                "resume": resume,
            }
        )

    def _clear_resume(self):
        if self._suppress:
            return
        storage.save_settings(
            {
                "shuffle": self.controller.shuffle_on,
                "repeat": self.controller.repeat_mode,
                "resume": None,
            }
        )

    def _restore_prefs(self):
        settings = storage.load_settings()
        self._resume_settings = settings.get("resume")
        self.controller.set_shuffle(settings.get("shuffle", False) is True)
        self.controller.set_repeat(settings.get("repeat", REPEAT_ALL))
        self._refresh_shuffle_repeat_icons()

    def _restore_resume(self):
        resume = self._resume_settings
        if not (isinstance(resume, dict) and isinstance(resume.get("path"), str)):
            return
        path = resume["path"]
        if os.path.isfile(path):
            playlist = self._find_playlist_by_path(path)
            if playlist is not None:
                index = self._index_of_path(playlist, path)
                if index >= 0:
                    playlist.current_index = index
                    self.controller.set_playlist(playlist)
                    if android_io.is_android():
                        pos_ms = max(0, int(resume.get("position_ms", 0)))
                        paths = [t.path for t in playlist.tracks]
                        current = playlist.current()
                        name = self._display(path, current.title) if current else "MusicBox"
                        cover = None
                        try:
                            cover = self._cover_path(path)
                        except Exception:
                            cover = None
                        self.audio.play(path, index, paths, self._repeat_int(), name, cover, resume_ms=pos_ms)
                        self._update_now_label(current)
                        self._set_play_icon()
                    else:
                        self._suppress = True
                        try:
                            self.audio.play_file(path)
                            self.audio.pause()
                            pos_sec = max(0, int(resume.get("position_ms", 0))) / 1000.0
                            self.audio.set_resume_position(pos_sec)
                            Clock.schedule_once(lambda dt: self.audio.seek(pos_sec), 0.3)
                            self._update_now_label(playlist.current())
                        finally:
                            self._suppress = False
        self._suppress = False
