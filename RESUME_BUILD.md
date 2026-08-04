# WZNOWIENIE BUDOWY APK

Ten plik jest dla mnie (asystenta). Po wpisaniu przez użytkownika „kontynuuj"
CZYTAJ TEN PLIK i kontynuuj od „AKTUALNY KROK". Nie zaczynaj od nowa.

## AKTUALNY KROK
[ 28 ] TYTUŁ+OKŁADKA W POWIADOMIENIU + PAUZA BEZ ZNIKANIA + BUILD 0.3.7 (14:16). APK: musicbox-0.3.7-arm64-v8a_armeabi-v7a-debug.apk
      - mobile/bin/ i Pulpit. Zainstalowany przez adb na Moto g54 5G (ZY22HXF268). Xiaomi (6e7781db) ODŁĄCZONE — ma 0.3.6, czeka na aktualizację. CZEKA NA TEST USERa.
      - Co zmieniono:
        1. KeepAliveService.java: stan playing/currentTitle/currentCover; onStartCommand czyta extras tylko gdy hasExtra; contentTitle=tytuł, contentText="Odtwarzanie"/"Wstrzymano"; dynamiczna ikona play/pauza (ic_media_play/ic_media_pause); setLargeIcon(BitmapFactory.decodeFile(cover)); wake lock TYLKO podczas grania.
        2. android_io: start_playback_service(title, cover, playing=True); set_playback_paused(paused) → Intent z samym playing.
        3. app.py: _play_track przekazuje title+cover (_cover_path); toggle_play: pauza→set_playback_paused(True) BEZ stop serwisu; wznowienie→set_playback_paused(False). Serwis znika tylko przy STOP/koniec playlisty/onTaskRemoved.
      - Weryfikacja: py_compile OK, pytest 75 passed; classes4.dex ma setLargeIcon+ic_media_play+EXTRA_PLAYING; na Moto media_receiver: ok, build=0.42s, bez crasha.
      - UWAGA: Moto nie ma plików muzycznych (load_m3u=0, media_paths=[]) — nie bug. Xiaomi zaktualizować APK z Pulpitu.
      - Następny krok: test — tytuł+okładka w powiadomieniu, pauza zostawia powiadomienie (▶), wznowienie (⏸), poprzedni/następny/stop, usunięcie z pamięci zamyka.

## WAŻNE NAUKI (nie powtarzaj błędów)
1. `nohup ... &` przez `wsl ... bash -c` → proces ZABIJANY gdy komenda wsl wraca (~20-30s później).
2. Usługa systemd też dostaje SIGTERM przy zamykaniu sesji wsl.
3. ROZWIĄZANIE: uruchom buildozera na PRZODZIE wsl.exe przez PowerShell Start-Process (detached),
   wsl.exe żyje cały czas → sesja otwarta → build nie ginie.
4. WSL miał 3.8GB RAM (za mało, peak 2.8GB) → zwiększono do 6GB w .wslconfig.
5. PEP 668 → PIP_BREAK_SYSTEM_PACKAGES=1 wymagane.
6. p4a.branch=develop, p4a.update=False.
7. VM nie wyłącza się (vmIdleTimeout=172800000) — to działa.

## SPRAWDZONE FAKTY O ŚRODOWISKU
- Windows 11 (10.0.22621), PowerShell 5.1
- WSL 2.7.11.0 JUŻ zainstalowany (Store), domyślna wersja 2
- Brak dystrybucji Linuxa (`wsl -l -v` = brak)
- Powłoka NIE jest adminem
- Projekt: C:\Users\ThinkPad\Desktop\Music player
- W WSL projekty dostępne pod /mnt/c/Users/ThinkPad/Desktop/Music\ player

## PLAN OGÓLNY
1. Zainstaluj dystrybucję Ubuntu w WSL (najpewniej BEZ restartu, bo WSL jest już gotowy)
2. W Ubuntu jako root: apt update, zainstaluj pakiety buildu (patrz niżej)
3. pip3 install buildozer
4. Przygotuj źródła w Linuxie (~/musicbox-build):
   cp -r mobile ~/musicbox-build/mobile
   cp -r core ~/musicbox-build/mobile/core
   mkdir -p ~/musicbox-build/mobile/assets && cp assets/icon.png ~/musicbox-build/mobile/assets/
5. cd ~/musicbox-build/mobile && buildozer -v android debug  (1-szy raz pobiera SDK/NDK ~15GB)
6. APK trafia do ~/musicbox-build/mobile/bin/*.apk
7. Skopiuj APK do /mnt/c/Users/ThinkPad/Desktop/Music\ player/mobile/bin/ oraz na Pulpit

## KOMENDY KLUCZOWE
- wsl --install -d Ubuntu --no-launch
- wsl -d Ubuntu -u root -- sh -c "apt update -y && apt install -y python3 python3-pip git zip unzip openjdk-17-jdk build-essential libffi-dev libssl-dev autoconf automake libtool pkg-config zlib1g-dev libncurses-dev cmake"
- pip3 install buildozer
- buildozer -v android debug

## UWAGA DOT. RESTARTU
- Jeśli Windows wymaga restartu podczas instalacji WSL: zrób restart NA POCZĄTKU,
  zanim cokolwiek innego się stanie. Po restarcie użytkownik wpisze „kontynuuj",
  wtedy SPRAWDŹ czy wsl działa (wsl --status) i wznowij od AKTUALNY KROK.

## LOG POSTĘPU
- 2026-08-03: sprawdzono środowisko (WSL gotowy, brak dystrybucji). Utworzono ten plik.
- 2026-08-03: ZAINSTALOWANO Ubuntu 26.04 LTS (wsl --install -d Ubuntu --no-launch). BEZ RESTARTU.
- 2026-08-03: WSL działa jako root (wsl -d Ubuntu -u root).
- 2026-08-03: Zainstalowano pakiety buildu (python3, pip, git, java-17, build-essential, libffi, libssl, cmake itd.).
- 2026-08-03: Zainstalowano buildozer 1.6.0 (pip3 install buildozer cython).
- 2026-08-03: Przygotowano źródła w ~/musicbox-build/mobile (mobile+core+assets). Spec: dodano android.accept_sdk_license.
- 2026-08-03: Problem: `git clone` p4a padal na sieci (invalid index-pack). Naprawa: git config http.version=HTTP/1.1 + postBuffer; pre-klon python-for-android (p4a.update=False w spec).
- 2026-08-03: Problem: WSL gasl maszynę po ~60s (vmIdleTimeout) i ubijał build. Naprawa: C:\Users\ThinkPad\.wslconfig z [wsl2] vmIdleTimeout=-1, potem wsl --shutdown.
- 2026-08-03: Build wznawiany przez skrypty w /mnt/c/Users/ThinkPad/AppData/Local/Temp/opencode/ (launch_build.sh, monitor.sh).
- 2026-08-03: Problem PEP 668 (pip blokowany przez Ubuntu 26.04). Naprawa: `Environment=PIP_BREAK_SYSTEM_PACKAGES=1` w usłudze + ręczna instalacja deps z --break-system-packages.
- 2026-08-03: p4a.branch = develop (gałąź istniejąca na GitHubie). Skrypt start_service.sh, diag_service.sh, monitor2.sh.
- 2026-08-03: 17:50 — BUILD TRWA: pobrane ANT+SDK+NDK r28c, API 33, ściąga zależności kivy (sdl2_ttf). Usługa systemd przeżywa wyjście z komendy wsl.
- IMPORTANT: procesy `nohup`/`&` startowane przez `wsl ... bash -c` SĄ ZABIJANE gdy komenda wsl wraca. Tylko usługa systemd działa stabilnie.
- 2026-08-03: systemd też zabijane przy zamykaniu sesji. Nowe podejście: Start-Process wsl.exe na przedzie (build_fg.sh). WSL pamięć zwiększona do 6GB.
- 2026-08-03: 18:0x — BUILD DZIAŁA stabilnie (Start-Process). Kompilacja hostpython3 (CPython 3.14.2). SDK/NDK pobrane. PIP_BREAK_SYSTEM_PACKAGES=1 w build_fg.sh.
- 2026-08-03: BŁĄD: Kivy 2.3.0 NIE wspiera Pythona 3.14 (błędy kompilacji C). NAPRAWA: requirements = python3==3.11.9. Usunięto artefakty 3.14, SDK/NDK zostają w cache.
- 2026-08-03: BŁĄD: clang 18 (NDK r28c) traktuje `-Wincompatible-function-pointer-types` jako ERROR (Kivy 2.3.0 cgl_gl.c, glShaderSource). NAPRAWA: dodano `-Wno-incompatible-function-pointer-types` do CFLAGS w pythonforandroid/archs.py (p4a develop w .buildozer/android/platform/python-for-android/). Uwaga na przyszłość: ten patch jest w katalogu .buildozer i zniknie przy p4a.update=True/clean.
- 2026-08-03: 19:53 — BUILD SUKCES. APK: musicbox-0.1.0-arm64-v8a_armeabi-v7a-debug.apk (50MB), skopiowany do mobile/bin/ i na Pulpit.
- 2026-08-03: 20:44 — Poprawki GUI (mobile/musicbox/app.py): usunięto suwak głośności (zbędny na telefonie; audio na pełnej głośności = przyciski telefonu), naprawiono przepełnienia poziome (size_hint_x:1 na przyciskach playerbar i home, shorten playlist_header, ScrollView+size_hint_x na statystykach), safe-area (status_bar_height() w android_io.py + padding roota). Weryfikacja KV przez hostpython3 (kivy 2.3.0 + kivymd 1.2.0 + mutagen doinstalowane do hostpython3). pytest mobile: 12 passed.
- 2026-08-03: BŁĄD: pierwszy build z poprawkami (20:44) NIE zawierał zmian — buildozer kompilował ze STAREJ kopii /root/musicbox-build/mobile (kopia źródeł w WSL jest niezależna od Windowsa; edycje robiono tylko w C:\...\Music player\mobile). NAPRAWA: skopiowano app.py/audio.py/android_io.py z Windows do WSL, podbito wersję do 0.1.1 (unikatowa nazwa APK), przebudowano.
- 2026-08-03: 21:17 — PRZEBUDOWA z poprawnymi zmianami. APK musicbox-0.1.1-arm64-v8a_armeabi-v7a-debug.apk (50MB), zweryfikowano w .buildozer/android/app/musicbox/app.py: volume_slider=0, size_hint_x/ScrollView/status_bar_height obecne. Skopiowany do mobile/bin/ i na Pulpit.
- 2026-08-03: 21:33 — Tytuł "MusicBox" rozciągał się na cały ekran (brak size_hint_y: None) → logo i przyciski były na środku wysokości. NAPRAWA: size_hint_y: None + height dp(48) + valign middle w HomeScreen. Wersja 0.1.2. Zweryfikowano w spakowanym kodzie. APK skopiowany do mobile/bin/ i na Pulpit.
- 2026-08-03: 22:16 — IMPORT .M3U NIE DZIAŁAŁ na Androidzie (okno wyboru pliku się nie otwierało). Przyczyna: plyer filechooser na p4a develop niestabilny (wyjątek cicho ginął w except ImportError). NAPRAWA: natywny pick_m3u() przez jnius (ACTION_GET_CONTENT + activity.bind(on_activity_result)), uri_to_path obsługuje com.android.externalstorage.documents i downloads.documents, resolve_playlist_path materializuje content:// do temp gdy brak realnej ścieżki. try/except + komunikaty błędów. UWAGA: .m3u musi być w tym samym folderze co mp3 (ścieżki względne). Wersja 0.1.3. Weryfikacja: ast OK, test hostpython3 OK (load_m3u, pick_m3u desktop=False, resolve_playlist_path), spakowany kod zawiera pick_m3u. APK skopiowany do mobile/bin/ i na Pulpit.
- 2026-08-03: Poprawki z review kodu (Wersja 0.1.4):
  - android_io.py: obsługa autorytetu com.android.providers.media.documents (doc id `audio:<id>` → MediaStore _data), co pokrywa DocumentsUI na API 29+; pliki materializowane do temp są śledzone i usuwane (cleanup_import_files); pick_m3u odbindowuje on_activity_result.
  - app.py: pozycja wznowienia sesji nie jest już gubiona (set_resume_position w audio.py po pause() zamiast samego opóźnionego seeka); _play_track wraca wcześnie z komunikatem gdy play_file zawiedzie (bez zawyżania statystyk); status_bar_height() jest konwertowane przez kivy.metrics.dp (wcześniej dp traktowane jak px → za mały padding na gęstościach >1); _on_import_selected sprząta pliki temp i pokazuje czytelniejszy komunikat dla materializowanych importów.
  - Weryfikacja: py_compile OK, pytest 75 passed (bez kivy). Buildozer wersja 0.1.4.
- 2026-08-04: 00:10 — BUILD 0.1.4 SUKCES (przyrostowy, reużyto dist; ~2 min). APK musicbox-0.1.4-arm64-v8a_armeabi-v7a-debug.apk (50 604 397 B), zweryfikowano w .buildozer/android/app (media.documents, cleanup_import_files, set_resume_position, kivy.metrics dp, komunikat błędu odtwarzania). Skopiowany do mobile/bin/ i na Pulpit.
- 2026-08-04: 00:33 — NAPRAWA IMPORTU .M3U v2 (root cause). Diagnoza: `bytes(stream.read())` w read_bytes czytało 1 bajt (int) → `bytes(int)` = bajty NUL → .m3u zapisywany jako śmieci; do tego materializacja do `tempfile` (/tmp niezapisywalne na Androidzie) cicho połykana → "nic się nie dzieje"; brak uprawnień w runtime (READ_EXTERNAL_STORAGE nieaktywne na API 33+). NAPRAWA: pełny odczyt InputStream, cache aplikacji (getCacheDir), komunikaty zamiast ciszy, request_permissions (READ_MEDIA_AUDIO API 33+ / READ_EXTERNAL_STORAGE niżej), fallback MediaStore DISPLAY_NAME. BUILD 0.1.5 SUKCES (~2 min). APK 50 607 313 B, READ_MEDIA_AUDIO w manifestcie, wersja 0.1.5. Skopiowany do mobile/bin/ i na Pulpit.
- 2026-08-04: 00:46 — DOSTĘP DO PAMIĘCI + FOLDER MusicBox. Powód: user chce żeby appka prosiła o „Wszystkie pliki" i tworzyła widoczny folder MusicBox/ (przenośny między urządzeniami). NAPRAWA: MANAGE_EXTERNAL_STORAGE, on_import_playlist otwiera settings (ACTION_MANAGE_APP_ALL_FILES_ACCESS_PERMISSION) gdy brak zgody, musicbox_dir() tworzy /storage/emulated/0/MusicBox, persist_to_musicbox() kopiuje .m3u tam z oryginalną nazwą, fallback MediaStore szerszy. BUILD 0.1.6 SUKCES (~2 min). APK 50 609 517 B, MANAGE_EXTERNAL_STORAGE w manifestcie, wersja 0.1.6. Skopiowany do mobile/bin/ i na Pulpit.
- 2026-08-04: 00:58 — FOLDER MusicBox v2. User zgłosił że folder nadal nie powstaje. Przyczyna: z pełnym dostępem uri_to_path zwraca realne ścieżki → gałąź materializacji (persist_to_musicbox) nie była wykonywana; folder tworzony tylko przy starcie (gdy zgoda już była). NAPRAWA: musicbox_dir() wołany też na klik Importuj i w _refresh_home; persist_to_musicbox robi kopię archiwalną także dla realnych ścieżek (ładuje z realnej); label na home pokazuje ścieżkę folderu. BUILD 0.1.7 SUKCES. APK 50 609 837 B, wersja 0.1.7. Skopiowany do mobile/bin/ i na Pulpit.
- 2026-08-04: 01:05 — NAPRAWA CRASHA PO INSTALACJI. User: appka wywala się po zainstalowaniu 0.1.7. Przyczyna: `shorten_from: "middle"` w KV (folder_label) — Kivy label.py: `shorten_from = OptionProperty('center', options=['left','center','right'])`, "middle" → ValueError przy Builder.load_string → crash na starcie. NAPRAWA: "middle" → "center". NAUKA: py_compile NIE łapie błędów KV; OptionProperty waliduje wartości (shorten_from: left/center/right, valign: top/middle/bottom, halign: left/center/right/justify). BUILD 0.1.8 SUKCES. APK 50 609 829 B, wersja 0.1.8. Skopiowany do mobile/bin/ i na Pulpit.
- 2026-08-04: 01:22 — AUTO-SKAN + NAPRAWA IMPORTU. User: ręcznie wrzucony .m3u do MusicBox/ nie pojawia się; import przez Importuj nie działa. (1) Root cause importu: `_read_stream_all` wołało `stream.read(8192)` — InputStream nie ma read(int) → wyjątek → read_bytes() = b"" → materializacja zawodziła (cicho) OD 0.1.5. NAPRAWA: read(bytearray) + fallback bajt-po-bajcie. (2) Auto-skan playlist: _scan_playlist_folder() w build() + show_home, dedup po nazwie, fallback MediaStore. (3) Komunikaty zamiast ciszy + musicbox_debug.log. BUILD 0.1.9 SUKCES. APK 50 611 597 B, wersja 0.1.9. Skopiowany do mobile/bin/ i na Pulpit.
- 2026-08-04: 01:39 — DIAGNOSTYKA 0.2.0. User (Moto g54 5G): "Wszystkie pliki" WŁĄCZONE, picker SIĘ OTWIERA, ale import nic, manualny .m3u nic, zero logów; tylko profil działa (pamięć aplikacji). Podejrzenia: on_activity_result nie odpala się PO powrocie z pickera LUB musicbox_dir() zawodzi. NAPRAWA (diagnostyka): log do storage.get_data_dir()/musicbox_debug.log (zawsze zapisywalny) + banner startowy + log każdego kroku + status na ekranie. BUILD 0.2.0 SUKCES. APK 50 613 845 B, wersja 0.2.0. Skopiowany do mobile/bin/ i na Pulpit.
- 2026-08-04: 01:54 — NAPRAWA DETEKCJI ANDROIDA 0.2.1. Ustalenie: log 0.2.0 szedł do /data/user/0/.../MusicBox/ (PRYWATNA pamięć, niewidoczna dla usera) — dlatego user nie znajdował logu. GŁÓWNA POPRAWKA: _ANDROID po zmiennych env (ANDROID_ARGUMENT/ANDROID_APP_PATH/P4A_BOOTSTRAP) zamiast import android na górze modułu (import mógł padać cicho → cała appka w trybie desktop: plyer zamiast pick_m3u, brak MusicBox, brak skanu). _read_stream_all bajt-po-bajcie. Log przeniesiony do getExternalFilesDir(None)/MusicBox (WIDOCZNY: /storage/emulated/0/Android/data/org.musicbox.musicbox/files/MusicBox/). Komunikat przy pustej selekcji. Status na ekranie z android=True/False. BUILD 0.2.1 SUKCES. APK 50 614 153 B, wersja 0.2.1. Skopiowany do mobile/bin/ i na Pulpit.
- 2026-08-04: 02:20 — BUILD 0.2.2 + TEST NA URZĄDZENIU PRZEZ ADB. Połączono Xiaomi 15T Pro (Android 16). Usunięto bramkę „Wszystkie pliki" z importu (picker zawsze się otwiera). Logi czytania w skanie. WERYFIKACJA logcat: android=True, READ_MEDIA_AUDIO granted, skan MusicBox → "skan: dodano test2" → playlista zapisana. MECHANIZM DZIAŁA. Wcześniejsze „nic" wynikało z: (1) bramki All-files blokującej import, (2) uszkodzonego testowego .m3u (song.mp3 sklejone z #EXTINF). APK 50 614 085 B, wersja 0.2.2. Zainstalowane przez adb + na Pulpicie.
- 2026-08-04: 02:29 — ROOT CAUSE IMPORTU (.toString) 0.2.3. Dowód z logu usera (0.2.2): "on_activity_result: uri=<android.net.Uri at 0x...>" — `str(jnius.Uri)` zwraca REPR, nie URI. Fix: `uri.toString()`. To wyjaśnia, czemu import przez picker NIGDY nie działał (od 0.1.3), choć skan działał. APK 50 614 121 B, wersja 0.2.3, zainstalowany przez adb. NAUKA: jnius Java obiekty — NIE używać str(obj) do stringa, używać .toString().
- 2026-08-04: 02:43 — UX 0.2.4: brak auto-grania po otwarciu playlisty (open_playlist bez _play_track); auto-odświeżanie po imporcie (home + skan + refresh). APK 50 614 089 B, wersja 0.2.4, zainstalowany przez adb.
- 2026-08-04: 02:58 — FINALIZACJA 0.3.0. Mobile: czysty folder_label, log tylko przy MUSICBOX_DEBUG, usunięta obietnica profil.json. README.md + .gitignore + git init + commit (c27ae16). Sprzątanie: do_analizy/ (2,4GB), build/, .pytest_cache, __pycache__, 15 starych APK (mobile/bin + Pulpit). APK 50 613 993 B, wersja 0.3.0, zainstalowany przez adb. PROJEKT FINALNY.
- 2026-08-04: 03:24 — WYGLĄD 0.3.1. Pełny ekran (Window.clearcolor), okładki MDCard (playlista/biblioteka/ekran główny), statystyki 1:1 (rename/reset/eksport/import + podsumowania miesięczne/roczne), auto-sync profilu (profil.json w MusicBox/, import przy starcie). APK 50 623 233 B, wersja 0.3.1. UWAGA: MIUI blokuje adb install (INSTALL_FAILED_USER_RESTRICTED) — APK pushnięty do Download/ do ręcznej instalacji; dla adb install trzeba włączyć "Install via USB" w opcjach deweloperskich.
- 2026-08-04: 03:47 — WYMUSZENIE+CACHE 0.3.2. Pełne wymuszenie „Wszystkich plików" (brama Importuj + auto-prompt start ~1,5s + komunikat); przycisk refresh na home + auto-check co 10s (po zmianie .m3u); cache: okładki cache-first (nie czyta mp3 gdy okładka w cache), ładowanie okładek asynchronicznie (wątek+Clock), cache tytułów/tagów JSON (path+mtime). APK 50 626 149 B, wersja 0.3.2.
- 2026-08-04: 04:26 — SUWAK+W TLE 0.3.3. Suwak: _scrubbing (seek po puszczeniu). Odtwarzanie w tle: KeepAliveService (Java, ten sam proces), start przy graniu/stop przy pauzie, onTaskRemoved stopSelf (usunięcie z pamięci zamyka). NAUKA: manifest p4a generuje się z AKTYWNYCH szablonów dists/musicbox/templates + build/bootstrap_builds/sdl2/templates (NIE z pythonforandroid/_sdl_common) — prep_service.sh przed każdym buildem. APK 50 628 465 B, wersja 0.3.3.
- 2026-08-04: 12:47 — NAPRAWA 0.3.4 (tło + wolne ładowanie + suwak). ROOT CAUSE TŁA: logcat 11:31:23 — "FORTIFY: pthread_mutex_lock called on a destroyed mutex" + "Fatal signal 6 (SIGABRT) in tid (AudioTrack)" 2s po wejściu w tło mimo FGS → MIUI/HyperOS zamraża proces, wątek audio MediaPlayera pada natywnie. Fix: foregroundServiceType="mediaPlayback" (prep_service.sh — teraz replace/inject z typem), KeepAliveService z startForeground 3-arg (API 29+) + Notification.MediaStyle + MediaSession + PARTIAL_WAKE_LOCK, WAKE_LOCK w spec, on_pause/on_resume. WOLNE ŁADOWANIE: mutagen.File zszedł z głównego wątku (4 workery _tag_worker, _display_cached, karta od razu z fallbackiem), okładki przez _cover_queue (2 workery) zamiast wątku na utwór, lock na _tags_cache. SUWAK: _updating_slider obejmuje slider.max (brak seek przy clamp max), log tick. LOGI: _debug_log zawsze-on + rotacja 1MB + log providera audio. UWAGA: MIUI blokuje adb input tap (INJECT_EVENTS denied). APK 50 631 249 B, wersja 0.3.4, zainstalowany przez adb.
- 2026-08-04: 13:38 — PRAWDZIWY ROOT CAUSE + PRZEBUDOWA 0.3.5. Dowód: log 0.3.4 "audio: provider=SoundSDL2" + "tick: pos=0.0 len=207.9" (SDL2 nie daje pozycji mp3) + SIGABRT 13:12:01. Zbadano bundle p4a: android/__init__.pyc co_names=['android._android'], HAS api_version=False → `from android import api_version` w kivy audio_android.py rzuca ImportError → ciche przejście na SDL2. FIX: własny MediaPlayer przez jnius w audio.py (start/prepare/pause/start/seekTo/getCurrentPosition/getDuration/OnCompletionListener), provider_name(). WYDANOŚĆ: FUSE stat ~22ms/op (52 pliki=1.15s w shellu) — ZERO getmtime/isfile na main-threadzie, RecycleView+TrackRow (lazy), skan/load w wątku tła, cache dirty+flush. NAUKA: kopiowanie APK z WSL → Copy-Item \\wsl.localhost\Ubuntu\root\... (cp przez bash cicho zawodzi). APK 50 638 581 B, wersja 0.3.5, zainstalowany przez adb.
- 2026-08-04: 14:00 — PRZYCISKI W POWIADOMIENIU 0.3.6. KeepAliveService: 4 akcje (PLAY_PAUSE/NEXT/PREV/STOP), Notification.Action (ikony systemowe), PendingIntent.getBroadcast IMMUTABLE+setPackage, MediaStyle.setShowActionsInCompactView(0,1,2), setActive(true), tytuł z Intent extra; android_io.start_playback_service(title); app._setup_media_receiver przez android.broadcast.BroadcastReceiver (p4a) → _on_media_action (toggle_play/play_next/play_prev/stop). NAUKA: sterowanie wraca do Pythona przez broadcast (proces trzyma FGS); GenericBroadcastReceiver jest w classes5.dex. APK 50 640 321 B, wersja 0.3.6, zainstalowany przez adb.
- 2026-08-04: 14:16 — TYTUŁ+OKŁADKA+PAUZA 0.3.7. Powiadomienie: contentTitle=tytuł (duży), contentText=Odtwarzanie/Wstrzymano, setLargeIcon(okładka), dynamiczna ikona play/pauza, wake lock tylko podczas grania. app._play_track przekazuje title+cover; toggle_play pauza→set_playback_paused(True) BEZ stop serwisu (powiadomienie zostaje), wznowienie→False. NAUKA: serwis czyta extras tylko gdy hasExtra; set_playback_paused wysyła sam playing. APK 50 640 877 B, wersja 0.3.7; zainstalowany na Moto g54 5G; Xiaomi odłączone.

