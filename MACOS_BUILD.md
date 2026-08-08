# Wersja macOS — build i uruchamianie

Aplikacja MusicBox dla macOS (Apple Silicon + Intel, jeden uniwersalny `MusicBox.app`).
Plik `.app` MUSI powstać na macOS (PyInstaller nie cross-kompiluje z Windows) —
budujemy go automatycznie w GitHub Actions (chmura macOS).

## Opcja A (zalecana): build przez GitHub Actions

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

## Opcja B: build lokalnie na Macu

```bash
chmod +x build_macos.sh
./build_macos.sh
# wynik: dist/MusicBox.app
```

Wymagania na Macu:
- Python **universal2** (np. z https://www.python.org/downloads/macos/).
- `iconutil` (wbudowany w macOS).
- Sieć (pobieranie narzędzi yt-dlp/ffmpeg/deno do `bin/macos/arm64` + `x86_64`).

Jeśli pobranie narzędzi się nie powiedzie, skrypt ostrzega i apka użyje narzędzi
z PATH (np. `brew install ffmpeg deno yt-dlp`).

## Co robi `MusicBox_macos.spec`
- `Analysis(target_arch='universal2')` → jeden plik binarny z obiema architekturami.
- `BUNDLE` → `MusicBox.app` (windowed, ikona `assets/icon.icns`, bundle id `org.musicbox.musicbox`).
- `bin/` (z narzędziami per arch) bundlowane do apki; aplikacja wybiera narzędzia
  wg `platform.machine()` (`bin/macos/arm64` vs `bin/macos/x86_64`).
