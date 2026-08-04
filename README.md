# MusicBox

Odtwarzacz muzyki z playlistami **.m3u** w dwóch wersjach: na **telefon (Android)** i na **komputer (Windows/Linux/macOS)**.

- **Mobile:** Kivy 2.3 + KivyMD 1.2 (`mobile/`) — APK z buildozerem (WSL)
- **Desktop:** PySide6 / Qt (`ui/`) — uruchamiany ze źródła lub jako `dist/MusicBox.exe` (PyInstaller)
- **Wspólna logika:** `core/` (playlisty, biblioteka, statystyki, tagi, okładki)

---

## Funkcje

### Wspólne
- Odtwarzanie lokalnych plików audio (mp3/ogg/m4a/wav)
- Playlisty `.m3u` — import, zapis, edycja, auto-skan
- Losowanie (shuffle) i powtarzanie (repeat)
- Statystyki słuchania (profil, top 3 utwory, top 3 wykonawcy, czas słuchania, podsumowania miesięczne/roczne)
- Profil przenośny między urządzeniami (plik `profil.json` — ręczny import/eksport)
- Zapamiętywanie sesji (pozycja odtwarzania po restarcie)
- Okładki albumów (cache w kwadracie 512×512)

### Mobile (Android)
- **Odtwarzanie w tle:** dedykowany `KeepAliveService` (Java) trzyma `MediaPlayer` — muzyka gra po zminimalizowaniu aplikacji i po zablokowaniu ekranu, nawet gdy pętla UI jest uśpiona
- **Sterowanie z powiadomienia:** poprzedni / pauza / następny / stop + tytuł i okładka aktualnego utworu (działa w tle, niezależnie od interfejsu)
- **Shuffle działa też w tle** (serwis odtwarza w kolejności przekazanej przez aplikację)
- Folder **`MusicBox/`** na pamięci telefonu — wrzucasz tam `.m3u` i muzykę; pliki są przenośne na inne urządzenia
- Import przez systemowy wybór plików (Storage Access Framework)
- Działa z samym `READ_MEDIA_AUDIO`; opcjonalnie „Wszystkie pliki", jeśli chcesz widoczny folder `MusicBox/`
- Log debugowy: zawsze aktywny (`Android/data/org.musicbox.musicbox/files/MusicBox/musicbox_debug.log`)

### Desktop
- Zaawansowana biblioteka z wyszukiwaniem (tytuł, wykonawca)
- Okładki albumów
- Eksport statystyk do grafiki (PNG)
- Pobieranie muzyki z YouTube Music (CSV → ytmusicapi → yt-dlp)

---

## Uruchomienie — desktop

```bash
pip install -r requirements.txt
python main.py
```

Zależności: `PySide6`, `mutagen`, `ytmusicapi`.

**Build exe (PyInstaller):** po zmianach w źródle należy przebudować:

```bash
python -m PyInstaller MusicBox.spec --noconfirm
# wyniki: dist/MusicBox.exe
```

Exe musi być zamknięty podczas budowy (inaczej `PermissionError`).

## Budowa APK (Android)

Wymaga WSL (Ubuntu) z buildozerem. Pełna procedura i historia w `RESUME_BUILD.md`.

Skrót (po zsynchronizowaniu źródeł do WSL i przygotowaniu serwisu):

```bash
# na Windows: sync + prep serwisu
wsl -d Ubuntu -u root -- bash /mnt/c/Users/ThinkPad/AppData/Local/Temp/opencode/sync_to_wsl.sh
wsl -d Ubuntu -u root -- bash /mnt/c/Users/ThinkPad/AppData/Local/Temp/opencode/prep_service.sh

# build (WSL)
wsl -d Ubuntu -u root -- bash /mnt/c/Users/ThinkPad/AppData/Local/Temp/opencode/build_fg.sh

# APK: mobile/bin/musicbox-<wersja>-arm64-v8a_armeabi-v7a-debug.apk
```

Ważne w `mobile/buildozer.spec`:
- `android.add_src = java` — wstrzykuje klasę serwisu do builda (odporne na regenerację dista)
- wersję podbijaj przy każdej przebudowie (unikatowa nazwa APK)

## Testy

```bash
python -m pytest tests/ -q
```

Testy wymagające Qt (`test_main_window.py`, `test_summary_image.py`) uruchamiają się tylko, gdy PySide6 jest zainstalowane.

---

## Struktura

```
core/          wspólna logika (playlisty, statystyki, tagi, okładki, silnik media)
ui/            desktop (PySide6)
mobile/        aplikacja Android (Kivy/KivyMD) + buildozer.spec + java/ (serwis)
tests/         testy pytest
assets/        grafiki/ikony
main.py        wejście desktopa
MusicBox.spec  spec PyInstaller dla desktopa
```

## Diagnostyka (mobile)

Log debugowy zapisywany jest **zawsze** (rotacja 1 MB) w
`Android/data/org.musicbox.musicbox/files/MusicBox/musicbox_debug.log`.
Przydatne wpisy: `audio: provider=android`, `meta: wyslano N`, `tick: pos=… len=…`,
`media_receiver: ok`, `perms: …`.
