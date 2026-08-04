# MusicBox

Odtwarzacz muzyki z playlistami **.m3u** w dwóch wersjach: na **telefon (Android)** i na **komputer (Windows/Linux/macOS)**.

- **Mobile:** Kivy + KivyMD (`mobile/`)
- **Desktop:** PySide6 / Qt (`ui/`)
- **Wspólna logika:** `core/` (playlisty, biblioteka, statystyki, tagi, pobieranie, okładki)

---

## Funkcje

### Wspólne
- Odtwarzanie lokalnych plików audio (mp3/ogg/m4a/wav)
- Playlisty `.m3u` — import, zapis, edycja
- Losowanie (shuffle) i powtarzanie (repeat)
- Statystyki słuchania (profil, top utwory, top wykonawcy, czas słuchania)
- Zapamiętywanie sesji (pozycja odtwarzania po restarcie)

### Mobile (Android)
- Folder **`MusicBox/`** na pamięci telefonu — wrzucasz tam `.m3u` i muzykę; pliki są przenośne na inne urządzenia
- Auto-skan folderu `MusicBox/` przy starcie
- Import przez systemowy wybór plików (Storage Access Framework)
- Wymaga zgody na multimedia (`READ_MEDIA_AUDIO`) i najlepiej „Wszystkie pliki", jeśli chcesz, aby aplikacja tworzyła swój folder

### Desktop
- Zaawansowana biblioteka z wyszukiwaniem (tytuł, wykonawca)
- Pobieranie muzyki z YouTube Music (CSV → ytmusicapi → yt-dlp)
- Okładki albumów
- Eksport statystyk do grafiki (PNG)

---

## Uruchomienie — desktop

```bash
pip install -r requirements.txt
python main.py
```

Zależności: `PySide6`, `mutagen`, `ytmusicapi`.

## Budowa APK (Android)

Wymaga WSL (Ubuntu) z buildozerem — pełna procedura w `RESUME_BUILD.md`.

Skrót:

```bash
cd mobile
buildozer -v android debug
# APK: mobile/bin/musicbox-*.apk
```

## Testy

```bash
python -m pytest tests/ -q
```

Testy wymagające Qt (`test_main_window.py`, `test_summary_image.py`) uruchamiają się tylko, gdy PySide6 jest zainstalowane.

---

## Struktura

```
core/          wspólna logika (playlisty, statystyki, tagi, downloader, okładki)
ui/            desktop (PySide6)
mobile/        aplikacja Android (Kivy/KivyMD) + buildozer.spec
tests/         testy pytest
assets/        grafiki/ikony
main.py        wejście desktopa
```

## Diagnostyka (mobile)

Log debugowy zapisywany jest tylko przy ustawionej zmiennej środowiskowej `MUSICBOX_DEBUG`
(plik `Android/data/org.musicbox.musicbox/files/MusicBox/musicbox_debug.log`).
