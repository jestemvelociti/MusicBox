# WZNOWIENIE BUDOWY APK

Ten plik jest dla mnie (asystenta). Po wpisaniu przez użytkownika „kontynuuj"
CZYTAJ TEN PLIK i kontynuuj od „AKTUALNY KROK". Nie zaczynaj od nowa.

## AKTUALNY KROK
[ 20 ] UX: brak auto-grania po otwarciu playlisty + auto-odświeżanie po imporcie + BUILD 0.2.4 (02:43). APK: musicbox-0.2.4-arm64-v8a_armeabi-v7a-debug.apk
      - mobile/bin/  i  Pulpit, zainstalowany PRZEZ ADB na Xiaomi 15T Pro
      - Co zmieniono:
        1. WYŁĄCZONE AUTO-GRANIE po wejściu w playlistę — usunięto `_play_track(pl.current())` z open_playlist. Odtwarzanie tylko po tapnięciu utworu.
        2. AUTO-ODŚWIEŻANIE po imporcie .m3u — w _on_import_selected: przejście na ekran główny + _scan_playlist_folders() (podłapuje też .m3u z MusicBox/) + _refresh_home() + komunikat "Dodano playlistę".
      - Weryfikacja: py_compile OK, pytest 75 passed, wersja 0.2.4, instalacja przez adb OK.
      - Następny krok: user testuje import (wybór .m3u) i sprawdza, że playlista od razu się pojawia oraz że wejście w playlistę nie gra.

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

