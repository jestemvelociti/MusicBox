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
- **Wersja APK: 0.2.4** — zainstalowany przez adb na Xiaomi 15T Pro. APK: `mobile/bin/musicbox-0.2.4-arm64-v8a_armeabi-v7a-debug.apk` + Pulpit.
- **UX 0.2.4:** (1) brak auto-grania po otwarciu playlisty — utwór gra tylko po tapnięciu (`_on_track_clicked`); (2) auto-odświeżanie po imporcie .m3u — `_on_import_selected` przechodzi na home, robi `_scan_playlist_folders()` + `_refresh_home()` + komunikat.
- **Root cause importu naprawiony (0.2.3):** `str(jnius.Uri)` zwraca repr → `uri.toString()`. Import przez picker NIGDY nie działał (0.1.3+) — teraz powinien.
- **Działający stan (potwierdzony przez adb):** android=True (API 36), READ_MEDIA_AUDIO granted, skan MusicBox dodaje playlistę, ścieżki względne działają względem folderu .m3u.
- **adb:** `C:\Users\ThinkPad\AppData\Local\Temp\opencode\platform-tools\adb.exe`. MIUI blokuje `adb shell input`.
- **Widoczny log:** `/storage/emulated/0/Android/data/org.musicbox.musicbox/files/MusicBox/musicbox_debug.log`.
- Weryfikacja: py_compile OK, pytest **75 passed**.
- **NASTĘPNY KROK:** user testuje import (wybór .m3u → playlista od razu w menu, bez grania przy wejściu). Gdy działa → 0.3.x.
- Zmienione pliki zsynchronizowane do kopii w WSL: `/root/musicbox-build/mobile/` (app.py, android_io.py, audio.py, buildozer.spec wersja 0.1.4).
- Weryfikacja: `py_compile` OK, `pytest` — **75 passed** (bez kivy; testy kivyowe pomijane).
- Build: incremental (reużyto dist musicbox), `dists/musicbox` + `other_builds` + SDK/NDK cache zachowane w WSL; CFLAGS patch w `.buildozer/android/platform/python-for-android/pythonforandroid/archs.py:126` obecny.

## Następne kroki / TODO
- [ ] **Przetestować na telefonie** (adb install 0.1.6): przy imporcie ZEZWOLIĆ na „Wszystkie pliki" (osobny ekran) + multimedia; sprawdzić że powstaje `/storage/emulated/0/MusicBox/` i .m3u się kopiuje; potem zaimportować i odtworzyć.
- [ ] Obsługa `media.documents` działa pewnie na API <29; na API 29+ `_data` dla plików innych aplikacji może być puste (scoped storage) → zostaje materializacja do temp + ostrzeżenie. Ewentualnie dopracować.
- [ ] `_play_track` — komunikat „Nie udało się odtworzyć" pokazuje się w `empty_label` na ekranie home (może być nieczytelne jeśli użytkownik jest na innym ekranie) — do rozważenia.

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
