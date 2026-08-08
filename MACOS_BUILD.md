# Wersja macOS — build i uruchamianie

Aplikacja MusicBox dla macOS. Plik `.app` MUSI powstać na macOS (PyInstaller
nie cross-kompiluje z Windows). Build buduje **natywną architekturę**:
na Macu Apple Silicon (M1/M2/M3…) → `arm64`.

## Opcja A (najprostsza): build lokalnie na Macu — podwójne kliknięcie

1. Skopiuj projekt na Maca (zip przez chmurę albo z GitHuba: Code → Download ZIP).
2. Rozpakuj.
3. **2x klik na `MusicBox Build.command`** (otworzy się Terminal).
4. Czekaj ~10–15 min — skrypt sam: pobiera narzędzia (yt-dlp/ffmpeg/deno),
   generuje `assets/icon.icns`, instaluje zależności (PySide6, Pillow…),
   buduje **`dist/MusicBox.app`** i otwiera folder.
5. Przeciągnij `MusicBox.app` do **Aplikacje**.
6. Pierwsze uruchomienie (Gatekeeper): **prawy klik → Otwórz**.
   Jak nie pomoże, w Terminalu: `xattr -dr com.apple.quarantine /ścieżka/do/MusicBox.app`.

Jeśli podwójne kliknięcie nie działa (brak uprawnień wykonywania), uruchom ręcznie:
```bash
chmod +x "MusicBox Build.command"
bash "MusicBox Build.command"
```
albo wprost:
```bash
bash build_macos.sh
```

Uwaga: build jest **arm64** (Apple Silicon). Na Macu Intel trzeba zbudować na Macu Intel.

## Opcja B: build przez GitHub Actions (chmura macOS)

Pobierasz gotowy `MusicBox.app` z Actions — przydatne, gdy nie masz Maka pod ręką.

### Krok 1 — wypchnij projekt na GitHub
Jeśli repo nie ma zdalnego:
```bash
git remote add origin https://github.com/TWOJ_LOGIN/MusicBox.git
git push -u origin main
```

### Krok 2 — odpal build
1. GitHub → repo → zakładka **Actions**.
2. Po lewej: **Build macOS App**.
3. Przycisk **Run workflow** → gałąź `main` → **Run workflow**.
4. Poczekaj ~10–15 min (runner pobiera Pythona, narzędzia i buduje).

Workflow odpala się też automatycznie przy `push` zmieniającym `core/`, `ui/`, `main.py`,
`MusicBox_macos.spec`, `build_macos.sh` albo sam workflow.

### Krok 3 — pobierz apkę
1. W przebiegu (run) na dole sekcja **Artifacts**.
2. Kliknij **`MusicBox-macOS`** → pobiera zip.
3. Rozpakuj → **`MusicBox.app`**.

### Krok 4 — uruchom
1. (opcjonalnie) Przeciągnij `MusicBox.app` do folderu **Aplikacje**.
2. Pierwsze uruchomienie (Gatekeeper, apka niesygnowana): **prawy klik → Otwórz**,
   albo w Terminalu:
   ```bash
   xattr -dr com.apple.quarantine "/ścieżka/do/MusicBox.app"
   ```
3. Kliknij 2x — działa. Funkcje identyczne jak wersja exe:
   pobieranie z CSV / linku Spotify, tryb album, tagi (TALB/TRCK 1/12/TCON),
   ustawienia, pasek z autorem i przewijaniem.

## Co robi `MusicBox_macos.spec`
- Buduje `.app` **natywnie** (na M1 = arm64) — bez universal2, dzięki czemu
  nie ma problemów z architekturą zależności (np. Pillow).
- `BUNDLE` → `MusicBox.app` (windowed, ikona `assets/icon.icns`, bundle id `org.musicbox.musicbox`).
- `bin/` (narzędzia yt-dlp/ffmpeg/deno) bundlowane do apki; aplikacja wybiera
  narzędzia wg `platform.machine()` (`bin/macos/arm64` vs `bin/macos/x86_64`).

