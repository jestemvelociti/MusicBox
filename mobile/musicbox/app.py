"""Aplikacja mobilna MusicBox (Kivy + KivyMD).

Zakres v1: odtwarzanie lokalnych utworow, playlisty (import .m3u),
biblioteka i podstawowe statystyki. Pobieranie z YouTube jest swiadomie
pominiete (wymaga yt-dlp/ffmpeg — niedostepne na Androidzie).
"""
import os
from datetime import date

from kivy.clock import Clock
from kivy.lang import Builder
from kivy.metrics import dp
from kivy.uix.screenmanager import ScreenManager
from kivymd.app import MDApp
from kivymd.uix.list import OneLineListItem

from core import storage
from core.library import Library
from core.playlist import Playlist, Track
from core.stats import Stats, format_listening
from core.tags import display_name

from musicbox import android_io
from musicbox.audio import AudioPlayer
from musicbox.controller import PlaybackController, REPEAT_ALL, REPEAT_OFF, REPEAT_ONE

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

<PlayerBar@BoxLayout>:
    orientation: "vertical"
    size_hint_y: None
    height: dp(120)
    padding: dp(12), dp(4)
    spacing: dp(2)
    canvas.before:
        Color:
            rgba: C("#101827")
        Rectangle:
            pos: self.pos
            size: self.size
    MDLabel:
        id: track_label
        text: "Brak utworu"
        theme_text_color: "Custom"
        text_color: 1, 1, 1, 1
        bold: True
        halign: "center"
        valign: "middle"
        shorten: True
        shorten_from: "center"
        text_size: self.width, None
        size_hint_y: None
        height: dp(26)
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
        MDLabel:
            text: "MusicBox"
            font_style: "H5"
            bold: True
            theme_text_color: "Custom"
            text_color: 1, 1, 1, 1
            size_hint_y: None
            height: dp(48)
            valign: "middle"
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
        ScrollView:
            MDList:
                id: playlist_list

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
        ScrollView:
            MDList:
                id: playlist_tracks

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
        ScrollView:
            MDList:
                id: library_tracks

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
        MDTextField:
            id: profile_input
            hint_text: "Nazwa profilu…"
            size_hint_y: None
            height: dp(48)
            pos_hint: {"center_x": 0.5}
            size_hint_x: 0.9
        MDRectangleFlatButton:
            id: create_profile_btn
            text: "Załóż profil"
            size_hint_y: None
            height: dp(44)
            pos_hint: {"center_x": 0.5}
            size_hint_x: 0.6
            on_release: app.create_profile()
        ScrollView:
            MDLabel:
                id: stats_body
                text: ""
                theme_text_color: "Custom"
                text_color: 1, 1, 1, 1
                padding: dp(16), dp(8)
                size_hint_y: None
                text_size: self.width, None
                height: self.texture_size[1]

BoxLayout:
    orientation: "vertical"
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

    def build(self):
        root = Builder.load_string(KV)
        self.root = root
        if android_io.is_android():
            root.padding = (0, dp(android_io.status_bar_height()), 0, 0)
        android_io.set_debug_logger(self._debug_log)
        self._wire_player_bar()
        self.library.playlists = storage.load_saved_playlists()
        self._restore_session()
        self._log_env()
        if android_io.is_android():
            android_io.request_storage_permissions()
            if android_io.all_files_access():
                android_io.musicbox_dir()
            self._scan_playlist_folders()
        Clock.schedule_interval(self._on_tick, 1.0)
        self._refresh_home()
        return root

    def _debug_log(self, msg):
        """Zapisuje zdarzenie do logu tylko gdy MUSICBOX_DEBUG jest ustawione."""
        if not os.environ.get("MUSICBOX_DEBUG"):
            return
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
            with open(target, "a", encoding="utf-8") as f:
                f.write(msg + "\n")
        except Exception:
            pass

    def _log_env(self):
        self._debug_log("=== MusicBox start (0.3.0) ===")
        self._debug_log("api_level=%s android=%s" % (android_io.android_api_level(), android_io.is_android()))
        if android_io.is_android():
            self._debug_log("all_files_access=%s" % android_io.all_files_access())
            self._debug_log("musicbox_dir=%s" % android_io.musicbox_dir())
            self._debug_log("external_log_dir=%s" % android_io.external_log_dir())
        self._debug_log("playlists_loaded=%d" % len(self.library.playlists))

    def _scan_playlist_folders(self):
        """Skanuje foldery z .m3u i dodaje nieznane playlisty do biblioteki."""
        try:
            self._scan_playlist_folder(storage.playlists_dir())
        except Exception:
            pass
        if android_io.is_android():
            folder = android_io.musicbox_dir()
            if folder:
                try:
                    self._scan_playlist_folder(folder)
                except Exception:
                    pass

    def _scan_playlist_folder(self, folder):
        if not folder or not os.path.isdir(folder):
            self._debug_log("skan: brak folderu " + str(folder))
            return
        m3u = [n for n in sorted(os.listdir(folder)) if n.lower().endswith(".m3u")]
        self._debug_log("skan: folder=%s, pliki_m3u=%d" % (folder, len(m3u)))
        known = {p.name for p in self.library.playlists}
        added = 0
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
                self.library.add_playlist(pl)
                storage.save_playlist(pl)
                known.add(pl.name)
                added += 1
                self._debug_log("skan: dodano " + pl.name)
        if added:
            self._debug_log("skan: %d nowych playlist z %s" % (added, folder))

    # ---------- UI: nawigacja ----------
    def _screen_ids(self, name):
        return self.root.ids.manager.get_screen(name).ids

    def show_home(self):
        self.root.ids.manager.current = "home"
        if android_io.is_android():
            self._scan_playlist_folders()
        self._refresh_home()

    def show_library(self):
        pl = build_library_playlist(self.library.playlists)
        self.controller.set_playlist(pl)
        self._populate_list(self._screen_ids("library").library_tracks, pl)
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
            item = OneLineListItem(
                text=f"{p.name} · {len(p.tracks)} utworów",
                on_release=lambda x, idx=i: self.open_playlist(idx),
            )
            lst.add_widget(item)
        ids.empty_label.opacity = 0 if self.library.playlists else 1
        if android_io.is_android():
            mdir = android_io.musicbox_dir()
            if mdir:
                ids.folder_label.text = f"Folder: {mdir}"
            else:
                ids.folder_label.text = "Brak dostępu do pamięci — włącz 'Wszystkie pliki'"
        else:
            ids.folder_label.text = ""

    def open_playlist(self, index):
        pl = self.library.switch_to(index)
        if pl is None:
            return
        self.controller.set_playlist(pl)
        self._populate_list(self._screen_ids("playlist").playlist_tracks, pl)
        self._screen_ids("playlist").playlist_header.text = pl.name
        self.root.ids.manager.current = "playlist"

    def _populate_list(self, list_widget, playlist):
        list_widget.clear_widgets()
        for i, t in enumerate(playlist.tracks):
            name = display_name(t.path, t.title)
            item = OneLineListItem(
                text=name,
                on_release=lambda x, idx=i: self._on_track_clicked(idx),
            )
            list_widget.add_widget(item)

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
                on_selection=self._on_import_selected,
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
        path = android_io.resolve_playlist_path(uri)
        if not path:
            self._debug_log("import: resolve_playlist_path zwrocilo None")
            self._flash_status("Nie udało się odczytać pliku")
            return
        self._debug_log("import: path=" + str(path))
        pl = Playlist()
        loaded = 0
        try:
            loaded = pl.load_m3u(path)
        except OSError:
            loaded = 0
        if loaded == 0:
            self._try_materialized_m3u(pl, path)
        android_io.cleanup_import_files()
        if not pl.tracks:
            self._debug_log("import: 0 utworow z " + str(path))
            self._flash_status(
                "Brak utworów. Sprawdź, czy aplikacja ma zgodę na multimedia i czy .m3u wskazuje istniejące pliki."
            )
            return
        self._debug_log("import: %d utworow, nazwa=%s" % (len(pl.tracks), pl.name))
        self.library.add_playlist(pl)
        storage.save_playlist(pl)
        self.root.ids.manager.current = "home"
        self._scan_playlist_folders()
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
        pb.ids.progress_slider.bind(value=self._on_seek_slider)

    def _play_track(self, track):
        if track is None:
            return
        if not self.audio.play_file(track.path):
            self._flash_status("Nie udało się odtworzyć utworu")
            self._set_play_icon()
            return
        self._set_play_icon()
        self._update_now_label(track)
        if self.stats.has_profile:
            self.stats.increment_play(track.path)
            self.stats.save()
        self._persist_settings()

    def _update_now_label(self, track):
        self.root.ids.player_bar.ids.track_label.text = (
            display_name(track.path, track.title) or track.title or "Brak utworu"
        )

    def _set_play_icon(self):
        self.root.ids.player_bar.ids.play_btn.icon = "pause" if self.audio.is_playing else "play-circle"

    def toggle_play(self):
        pl = self.controller.playlist
        if pl is None:
            return
        if pl.current() is None and pl.tracks:
            self._play_track(self.controller.play_at(0))
            return
        if self.audio.is_playing:
            self.audio.pause()
            self._set_play_icon()
        else:
            restarted = self.controller.resume_after_round()
            if restarted is not None:
                self._play_track(restarted)
                return
            if self.audio.current_source:
                self.audio.resume()
            else:
                index = pl.current_index if pl.current_index >= 0 else 0
                self._play_track(self.controller.play_at(index))
            self._set_play_icon()

    def play_next(self):
        track = self.controller.play_next()
        if track:
            self._play_track(track)

    def play_prev(self):
        track = self.controller.play_prev()
        if track:
            self._play_track(track)

    def toggle_shuffle(self):
        self.controller.set_shuffle(not self.controller.shuffle_on)
        self._refresh_shuffle_repeat_icons()
        self._persist_settings()

    def cycle_repeat(self):
        modes = [REPEAT_ALL, REPEAT_ONE, REPEAT_OFF]
        current = self.controller.repeat_mode
        if current not in modes:
            current = REPEAT_ALL
        self.controller.set_repeat(modes[(modes.index(current) + 1) % 3])
        self._refresh_shuffle_repeat_icons()
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
        action, track = self.controller.on_playback_ended()
        if action == "replay":
            self.audio.replay()
        elif action == "next":
            self._play_track(track)
        else:
            self.audio.stop()
            self._set_play_icon()
            self._clear_resume()

    # ---------- audio: suwaki i tick ----------
    def _on_audio_tick(self, pos, length):
        slider = self.root.ids.player_bar.ids.progress_slider
        self._updating_slider = True
        try:
            slider.max = length or 1
            slider.value = pos
        finally:
            self._updating_slider = False
        pb = self.root.ids.player_bar.ids
        pb.time_pos.text = _fmt_time(pos)
        pb.time_total.text = _fmt_time(length)

    def _on_seek_slider(self, slider, value):
        if self._updating_slider:
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

    # ---------- statystyki ----------
    def create_profile(self):
        name = self._screen_ids("stats").profile_input.text.strip()
        if name and self.stats.create_profile(name):
            self._refresh_stats()

    def _refresh_stats(self):
        ids = self._screen_ids("stats")
        has = self.stats.has_profile
        ids.profile_input.disabled = has
        ids.create_profile_btn.disabled = has
        if not has:
            ids.stats_body.text = (
                "Załóż profil, aby śledzić czas słuchania i najczęściej odtwarzane utwory."
            )
            return
        lines = [
            f"Profil: {self.stats.profile_name}",
            "Czas słuchania: " + format_listening(self.stats.total_listening_seconds()),
            "",
            "Top utwory:",
        ]
        top = self.stats.top_tracks(3)
        if top:
            for i, (p, count) in enumerate(top, 1):
                lines.append(f"{i}. {display_name(p, os.path.basename(p))} — {count}")
        else:
            lines.append("  brak")
        lines.append("")
        lines.append("Top wykonawcy:")
        top_artists = self.stats.top_artists(3)
        if top_artists:
            for i, (a, count) in enumerate(top_artists, 1):
                lines.append(f"{i}. {a} — {count}")
        else:
            lines.append("  brak")
        ids.stats_body.text = "\n".join(lines)

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

    def _restore_session(self):
        settings = storage.load_settings()
        self.controller.set_shuffle(settings.get("shuffle", False) is True)
        self.controller.set_repeat(settings.get("repeat", REPEAT_ALL))
        self._refresh_shuffle_repeat_icons()

        resume = settings.get("resume")
        if isinstance(resume, dict) and isinstance(resume.get("path"), str):
            path = resume["path"]
            if os.path.isfile(path):
                playlist = self._find_playlist_by_path(path)
                if playlist is not None:
                    index = self._index_of_path(playlist, path)
                    if index >= 0:
                        playlist.current_index = index
                        self.controller.set_playlist(playlist)
                        self._suppress = True
                        try:
                            self.audio.play_file(path)
                            self.audio.pause()
                            pos_ms = max(0, int(resume.get("position_ms", 0)))
                            pos_sec = pos_ms / 1000.0
                            self.audio.set_resume_position(pos_sec)
                            Clock.schedule_once(lambda dt: self.audio.seek(pos_sec), 0.3)
                            self._update_now_label(playlist.current())
                        finally:
                            self._suppress = False
        self._suppress = False
