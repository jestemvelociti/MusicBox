# PAMIĘĆ — MusicBox (notatki asystenta)

> Komenda przywracania: `/przywróć pamięć`
> Po ponownym uruchomieniu PC wpisz tę komendę, a wczytam ten plik i kontynuuję pracę.

## Projekt
- Aplikacja odtwarzacz muzyki **MusicBox** (tytuł APK: MusicBox, package: org.musicbox.musicbox).
- Lokalizacja: `C:\Users\ThinkPad\Desktop\Music player`
- Moduły:
  - `core/` — czysta logika (playlist, storage, stats, library, tags, downloader, cover, summary_image) — testowalna bez Kivy.
  - `mobile/musicbox/` — aplikacja Android (Kivy 2.3.0 + KivyMD 1.2.0): `app.py`, `audio.py`, `android_io.py`, `controller.py`.
  - `mobile/buildozer.spec` — konfiguracja buildu APK (WSL + buildozer).
  - `ui/` + reszta na Pulpicie — wersja desktopowa.
- Zakres v1 (mobile): odtwarzanie lokalnych utworów, playlisty (import .m3u), biblioteka, statystyki. YouTube pominięty (yt-dlp/ffmpeg niedostępne na Androidzie).

## Aktualny stan (2026-08-04)
- **Wersja APK: 0.3.7** — powiadomienie pokazuje TYTUŁ UTWORU (contentTitle, duży) + OKŁADKĘ (setLargeIcon) i NIE ZNIKA po pauzie (stan playing, ikona play/pauza). APK: `mobile/bin/musicbox-0.3.7-arm64-v8a_armeabi-v7a-debug.apk` + Pulpit. **Zainstalowany przez adb na Moto g54 5G (ZY22HXF268); Xiaomi (6e7781db) ODŁĄCZONE — ma 0.3.6, czeka na aktualizację. CZEKA NA TEST UŻYTKOWNIKA.**
- **0.3.7:**
  1. `KeepAliveService.java`: stan `playing`/`currentTitle`/`currentCover`; `onStartCommand` czyta extras TYLKO gdy `hasExtra`; contentTitle=tytuł, contentText="Odtwarzanie"/"Wstrzymano"; dynamiczna ikona play/pauza (ic_media_play/ic_media_pause, label "Odtwarzaj"/"Pauza"); `setLargeIcon` z BitmapFactory.decodeFile(cover); **wake lock TYLKO podczas grania** (release przy pauzie, acquire przy graniu — bateria).
  2. `android_io`: `start_playback_service(title, cover, playing=True)`; `set_playback_paused(paused)` → wysyła playing bez zmiany title/cover.
  3. `app.py`: `_play_track` przekazuje tytuł+okładkę (`_cover_path`); `toggle_play` przy pauzie → `set_playback_paused(True)` (BEZ stop serwisu), przy wznowieniu → `set_playback_paused(False)`. Serwis (powiadomienie) znika tylko przy STOP / naturalnym końcu playlisty / onTaskRemoved.
- **Weryfikacja:** py_compile OK, pytest **75 passed**; APK classes4.dex ma setLargeIcon+ic_media_play+EXTRA_PLAYING; na Moto `media_receiver: ok`, build=0.42s, bez crasha.
- **UWAGI:** Moto g54 5G nie ma plików muzycznych (load_m3u=0, media_paths=[]) — to nie bug 0.3.7. Xiaomi (główny, 6e7781db) odłączone — zaktualizować APK z Pulpitu lub podpiąć do adb.
- **adb:** `C:\Users\ThinkPad\AppData\Local\Temp\opencode\platform-tools\adb.exe`. Urządzenia: Xiaomi 6e7781db (główny, 0.3.6), Moto g54 5G ZY22HXF268 (0.3.7).
- Build: incremental ~2 min. Sync: `sync_to_wsl.sh`; prep: `prep_service.sh`; APK z WSL → **Copy-Item \\wsl.localhost\Ubuntu\root\...**.

## Następne kroki / TODO
- [ ] **Zaktualizować Xiaomi (6e7781db) do 0.3.7** (APK na Pulpicie / podpiąć do adb) — odłączone.
- [ ] **Test 0.3.7:** powiadomienie pokazuje tytuł utworu + okładkę; PAUZA → powiadomienie ZOSTAJE (ikona ▶ Odtwarzaj); wznowienie → ⏸ Pauza; poprzedni/następny/stop działają; usunięcie z pamięci zamyka.
- [ ] **Test 0.3.5 (do potwierdzenia):** szybka lista (RecycleView), suwak się przesuwa i przewija, Home → gra dalej.
- [ ] Przetestować na **głównym telefonie z dużą biblioteką** — `perf: stat_latency` pokaże realny koszt statu FUSE.
- [ ] Jeżeli nadal crash w tle (mimo MediaPlayera) → osobny proces serwisu (`android:process=":media"`).
- [ ] `_flash_status` w `empty_label` na home (nieczytelne na innych ekranach) — do rozważenia.

## Ważne decyzje i pułapki (nauki z RESUME_BUILD.md)
1. Kopia źródeł w WSL `/root/musicbox-build/mobile/` jest NIEZALEŻNA od Windowsa — po edycjach trzeba ją zsynchronizować (komenda sync_to_wsl.sh).
2. Wersja w `buildozer.spec` musi być podbijana przy każdej przebudowie (unikatowa nazwa APK).
3. WSL Ubuntu 26.04 (user: root). Buildozer 1.6.0, p4a.branch=develop, p4a.update=False.
4. PEP 668 → `PIP_BREAK_SYSTEM_PACKAGES=1` wymagane w WSL.
5. `nohup ... &` przez `wsl ... bash -c` → proces zabijany gdy wsl wraca. Trwały build: Start-Process wsl.exe na przedzie (build_fg.sh).
6. Kivy 2.3.0 NIE wspiera Pythona 3.14 → requirements `hostpython3==3.11.9,python3==3.11.9`.
7. NDK r28c (clang 18) traktuje `-Wincompatible-function-pointer-types` jako ERROR przy Kivy 2.3.0 → patch CFLAGS w `pythonforandroid/archs.py` (w .buildozer — znika przy p4a.update=True/clean).
8. WSL RAM zwiększony do 6GB; vmIdleTimeout=-1 w `.wslconfig` (VM nie gaśnie).
9. Desktop: plyer filechooser nie działał na Androidzie → natywny `pick_m3u()` przez jnius (ACTION_GET_CONTENT + on_activity_result).
10. `Playlist.load_m3u` rozwiązuje ścieżki względne względem folderu pliku .m3u — dlatego przy materializacji do temp względne ścieżki zawodzą.
11. **KV NIE jest walidowane przez py_compile** — błędy OptionProperty wykrywane dopiero przy Builder.load_string (crash przy starcie). Opcje: `shorten_from`: left/center/right; `valign`: top/middle/bottom; `halign`: left/center/right/justify. Przed buildem sprawdzać nowe wartości KV pod kątem OptionProperty (Kivy label.py ~linia 962).
12. **jnius InputStream:** Java InputStream ma `read()`, `read(byte[])`, `read(byte[],int,int)` — NIE ma `read(int)`. Czytanie strumienia: bajt-po-bajcie `stream.read()` (int, -1=EOF) — 100% pewne; `stream.read(bytearray)` bywa zawodne; `bytes(stream.read())` złe (read() = 1 bajt int → bytes(int) = NUL).
13. **Detekcja Androida:** NIE polegać na `import android` na górze modułu (może cicho paść → appka w trybie desktop!). Używać env: `ANDROID_ARGUMENT`/`ANDROID_APP_PATH`/`P4A_BOOTSTRAP` (p4a ustawia je w PythonActivity.java:135,157).
14. **Logi dla usera:** `getFilesDir()` = /data/user/0/... (prywatny, niewidoczny); do logów widocznych dla usera używać `getExternalFilesDir(None)` = /storage/emulated/0/Android/data/<pkg>/files.
15. **jnius Java obiekty:** NIE używać `str(obiekt_jnius)` do pobrania stringa — zwraca Python repr (`<android.net.Uri at 0x...>`)! Używać metody Java `.toString()`. To był ROOT CAUSE importu .m3u (0.1.3 → 0.2.2).

## Komendy
- Testy (Windows, bez kivy): `python -m pytest tests/ -q --ignore=tests/test_main_window.py --ignore=tests/test_summary_image.py` (75 passed)
- Testy kontrolera: `python -m pytest tests/test_mobile_controller.py tests/test_playlist.py -q`
- Sprawdzenie składni: `python -m py_compile mobile/musicbox/app.py mobile/musicbox/android_io.py mobile/musicbox/audio.py`
- Sync do WSL: skrypt `C:\Users\ThinkPad\AppData\Local\Temp\opencode\sync_to_wsl.sh` (wzór), uruchamiany: `wsl -d Ubuntu -u root -- bash /mnt/c/Users/ThinkPad/AppData/Local/Temp/opencode/sync_to_wsl.sh`
- Build APK: pełna procedura w `RESUME_BUILD.md` (AKTUALNY KROK: 9 — test importu .m3u na telefonie).
- Przywrócenie pamięci: wpisz `/przywróć pamięć`.

## Log zmian
- 2026-08-04: Utworzono ten plik. Poprawki z review (6 punktów, patrz „Aktualny stan"), wersja 0.1.4, sync do WSL, 75 testów OK.
- 2026-08-04: BUILD 0.1.4 SUKCES (przyrostowy, ~2 min). APK w mobile/bin/ i na Pulpicie. Poprawki zweryfikowane w spakowanym kodzie.
- 2026-08-04: NAPRAWA IMPORTU .M3U v2 (root cause: read_bytes 1 bajt + /tmp niezapisywalne + brak uprawnień runtime). BUILD 0.1.5 SUKCES, APK w mobile/bin/ i na Pulpicie, READ_MEDIA_AUDIO dodane.
- 2026-08-04: DOSTĘP DO PAMIĘCI („Wszystkie pliki") + widoczny folder MusicBox/ + kopiowanie .m3u tam. MANAGE_EXTERNAL_STORAGE, settings intent na imporcie. BUILD 0.1.6 SUKCES, APK w mobile/bin/ i na Pulpicie.
- 2026-08-04: FOLDER MusicBox v2 — folder tworzony zawsze (start/import/refresh home), kopia archiwalna .m3u także dla realnych ścieżek, label ze ścieżką na home. BUILD 0.1.7 SUKCES, APK w mobile/bin/ i na Pulpicie.
- 2026-08-04: NAPRAWA CRASHA — `shorten_from: "middle"` (niedozwolone w Kivy) → "center". BUILD 0.1.8 SUKCES, APK w mobile/bin/ i na Pulpicie. Nauka o OptionProperty w KV dodana do pułapek.
- 2026-08-04: AUTO-SKAN playlist (build + show_home) + NAPRAWA IMPORTU (root cause: `stream.read(8192)` — InputStream nie ma read(int) → read_bytes()=b"" → materializacja cicho zawodziła od 0.1.5) + komunikaty + musicbox_debug.log. BUILD 0.1.9 SUKCES, APK w mobile/bin/ i na Pulpicie. NAUKA: Java InputStream ma read(), read(byte[]), read(byte[],int,int) — NIE read(int); jnius: bytearray→byte[] działa, int nie jest konwertowany na byte[].
- 2026-08-04: WERSJA DIAGNOSTYCZNA 0.2.0 — log do storage.get_data_dir() (zawsze zapisywalny), banner startowy, log on_activity_result/picker/resolve/scan, status na ekranie. CZEKA na log od usera (Moto g54 5G: zgoda TAK, picker się otwiera, ale import nic). BUILD 0.2.0 SUKCES, APK w mobile/bin/ i na Pulpicie. NAUKA: app_storage_path() = getFilesDir() = /data/user/0/<pkg>/files — PRYWATNY, user nie zobaczy logu; log musi iść do getExternalFilesDir(None) = /storage/emulated/0/Android/data/<pkg>/files (widoczny).
- 2026-08-04: NAPRAWA DETEKCJI ANDROIDA 0.2.1 — _ANDROID po env (ANDROID_ARGUMENT/ANDROID_APP_PATH/P4A_BOOTSTRAP), nie po import android; _read_stream_all bajt-po-bajcie; widoczny log (getExternalFilesDir/MusicBox); komunikat przy pustej selekcji; status android=True/False na ekranie. BUILD 0.2.1 SUKCES, APK w mobile/bin/ i na Pulpicie.
- 2026-08-04: 0.2.2 + TEST ADB NA XIAOMI 15T PRO — usunięto bramkę „Wszystkie pliki" z importu; logi czytania w skanie; ZWERYFIKOWANO na urządzeniu (logcat): android=True, READ_MEDIA_AUDIO granted, skan MusicBox → "dodano test2" → playlista zapisana. Mechanizm działa. adb w C:\Users\ThinkPad\AppData\Local\Temp\opencode\platform-tools\.
- 2026-08-04: 0.2.3 — ROOT CAUSE IMPORTU: `str(jnius.Uri)` zwraca repr, nie URI → `uri.toString()`. Import przez picker NIGDY nie działał (0.1.3+), skan tak. NAUKA: jnius Java obiekty — do stringa używać .toString(), NIE str(obj).
- 2026-08-04: 0.2.4 — UX: brak auto-grania po otwarciu playlisty; auto-odświeżanie po imporcie (home+skan+refresh). Zainstalowane przez adb.
- 2026-08-04: FINALIZACJA 0.3.0 — czysty folder_label, log pod MUSICBOX_DEBUG, usunięta obietnica profil.json; README.md + .gitignore + git init (commit c27ae16); sprzątanie (do_analizy 2,4GB, build/, __pycache__, .pytest_cache, 15 starych APK). PROJEKT FINALNY.
- 2026-08-04: WYGLĄD 0.3.1 — pełny ekran (Window.clearcolor), okładki MDCard (playlista/biblioteka/home kafelki), statystyki 1:1 (rename/reset/eksport/import + podsumowania miesiąc/rok), auto-sync profilu (profil.json w MusicBox/, import przy starcie). UWAGA: MIUI blokuje adb install → instalacja ręczna lub "Install via USB" w opcjach deweloperskich.
- 2026-08-04: WYMUSZENIE+CACHE 0.3.2 — pełne wymuszenie „Wszystkich plików" (brama Importuj + auto-prompt start + komunikat); przycisk refresh na home + auto-check co 10s; cache: okładki cache-first (nie czyta mp3 gdy okładka w cache), async okładki (wątek+Clock), cache tytułów JSON (path+mtime). NAUKA: przy cache okładek sprawdzać plik cache PRZED extract_cover (inaczej każdy build czyta mp3).
- 2026-08-04: SUWAK+W TLE 0.3.3 — suwak: _scrubbing (seek po puszczeniu); odtwarzanie w tle: KeepAliveService (Java, ten sam proces), onTaskRemoved stopSelf. NAUKA: manifest p4a z AKTYWNYCH szablonów dists/musicbox/templates + bootstrap_builds/sdl2/templates, NIE z _sdl_common; prep_service.sh przed buildem.
- 2026-08-04: NAPRAWA 0.3.4 (3 zgłoszenia usera). ROOT CAUSE tła: SIGABRT w wątku AudioTrack przy zamrożeniu przez MIUI (logcat 11:31:23) — mimo FGS proces pada natywnie. Fix: foregroundServiceType=mediaPlayback + startForeground 3-arg + MediaStyle/MediaSession + wake lock; WAKE_LOCK w spec. WOLNE ŁADOWANIE: tagi w tle (4 workery), okładki przez wspólną kolejkę (2 workery) — koniec blokady UI mutagen.File. SUWAK: defensywnie _updating_slider wokół slider.max (brak seek przy clamp). LOGI: _debug_log zawsze-on (bez MUSICBOX_DEBUG), rotacja 1MB, log providera. NAUKA: MIUI blokuje adb input tap (INJECT_EVENTS denied) — test UI tylko ręcznie. BUILD 0.3.4 SUKCES (~2 min, incremental), APK w mobile/bin/ i na Pulpicie, zainstalowany przez adb.
- 2026-08-04: PRAWDZIWY ROOT CAUSE 0.3.5 — **Kivy używa SDL2 zamiast MediaPlayera**: `kivy/core/audio/audio_android.py` robi `from android import api_version` (na import), a p4a's `android/__init__.pyc` ma TYLKO `co_names=['android._android']` → **HAS api_version: False** → ImportError → provider android pomijany → SDL2. Skutki SDL2: pos=0 (martwy suwak), brak seeka, SIGABRT przy onPause (tło). FIX: własny backend `android.media.MediaPlayer` przez jnius w audio.py (setDataSource/prepare/pause/start/seekTo/getCurrentPosition/getDuration/OnCompletionListener). WOLNOŚĆ: FUSE `stat` ~22ms/op (52 pliki=1.15s w shellu) — usunięto per-utworowe getmtime/isfile z main-threadu (tylko workery), **RecycleView+TrackRow** (lazy) dla playlisty/biblioteki, skan+load playlist w wątku tła (`_startup_async`/`_scan_playlists_async`+lock), cache dirty+flush co 5s, instrumentacja perf (build=0.32s). NAUKA: kopiowanie APK z WSL na Windows — `cp` przez bash bywa cicho zawodne; pewne: **Copy-Item z \\wsl.localhost\Ubuntu\root\...**. BUILD 0.3.5 SUKCES, APK w mobile/bin/ i na Pulpicie, zainstalowany przez adb.
- 2026-08-04: PRZYCISKI W POWIADOMIENIU 0.3.6 — KeepAliveService: 4 akcje MediaStyle (PLAY_PAUSE/NEXT/PREV/STOP, ikony systemowe ic_media_*, PendingIntent.getBroadcast IMMUTABLE+setPackage, setShowActionsInCompactView(0,1,2), setActive(true)), tytuł utworu z Intent extra; android_io.start_playback_service(title); app._setup_media_receiver przez **android.broadcast.BroadcastReceiver** (p4a, callback na wątku handlera → Clock.schedule_once), _on_media_action→toggle_play/play_next/play_prev/stop. NAUKA: sterowanie musi wrócić do Pythona (właściciela MediaPlayera) przez broadcast, bo proces trzyma FGS. Weryfikacja: GenericBroadcastReceiver w classes5.dex, action string w classes4.dex, `media_receiver: ok` w logu. BUILD 0.3.6 SUKCES, APK w mobile/bin/ i na Pulpicie, zainstalowany przez adb.
- 2026-08-04: TYTUŁ+OKŁADKA+PAUZA 0.3.7 — powiadomienie: contentTitle=tytuł (duży), contentText=Odtwarzanie/Wstrzymano, setLargeIcon(okładka z cache), dynamiczna ikona play/pauza (ic_media_play/pause), wake lock TYLKO podczas grania (bateria). app._play_track przekazuje title+cover; toggle_play: pauza→set_playback_paused(True) BEZ stop serwisu (powiadomienie zostaje), wznowienie→set_playback_paused(False). NAUKA: `set_playback_paused` wysyła Intent z samym playing (serwis trzyma title/cover); serwis czyta extras tylko gdy hasExtra. Weryfikacja: setLargeIcon/ic_media_play/EXTRA_PLAYING w classes4.dex. UWAGA: Xiaomi odłączone (ma 0.3.6), Moto g54 5G ZY22HXF268 dostaje 0.3.7. BUILD 0.3.7 SUKCES.
