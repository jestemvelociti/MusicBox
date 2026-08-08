#!/bin/bash
# Build wersji macOS (universal2 .app) — uruchamiane na Macu.
#   chmod +x build_macos.sh && ./build_macos.sh
# Wynik: dist/MusicBox.app
set -e

cd "$(dirname "$0")"
echo "=== MusicBox macOS build ==="
echo "host arch: $(uname -m)"

mkdir -p bin/macos/arm64 bin/macos/x86_64

# ---------- narzędzia ----------
fetch_zip() { # $1=url $2=dest_dir $3=binary_name
    local url="$1" dest="$2" name="$3"
    local tmp="$(mktemp -d)"
    echo "[tools] pobieram $name <- $url"
    if curl -fL --retry 3 -o "$tmp/out.zip" "$url"; then
        (cd "$tmp" && unzip -o -q out.zip)
        if [ -f "$tmp/$name" ]; then
            cp -f "$tmp/$name" "$dest/$name"
            chmod +x "$dest/$name"
            echo "[tools] OK: $dest/$name"
        else
            echo "[tools] UWAGA: brak '$name' w archiwum — szukaj na PATH"
        fi
    else
        echo "[tools] UWAGA: pobieranie $name nieudane — szukaj na PATH (Homebrew)"
    fi
    rm -rf "$tmp"
}

fetch_raw() { # $1=url $2=dest_file
    echo "[tools] pobieram $2 <- $1"
    if curl -fL --retry 3 -o "$2" "$1"; then
        chmod +x "$2"
        echo "[tools] OK: $2"
    else
        echo "[tools] UWAGA: pobieranie $(basename "$2") nieudane — szukaj na PATH"
    fi
}

# yt-dlp (binary universal — to samo dla obu arch)
YTDLP_URL="https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp_macos"
fetch_raw "$YTDLP_URL" "bin/macos/arm64/yt-dlp"
fetch_raw "$YTDLP_URL" "bin/macos/x86_64/yt-dlp"

# deno (osobne binarki per arch)
fetch_zip "https://github.com/denoland/deno/releases/latest/download/deno-aarch64-apple-darwin.zip" "bin/macos/arm64" "deno"
fetch_zip "https://github.com/denoland/deno/releases/latest/download/deno-x86_64-apple-darwin.zip" "bin/macos/x86_64" "deno"

# ffmpeg (static, evermeet x86_64) — na arm64 używamy x86_64 (na M1 działa przez Rosetta 2)
fetch_zip "https://evermeet.cx/ffmpeg/getrelease/zip" "bin/macos/x86_64" "ffmpeg"
if [ -f bin/macos/x86_64/ffmpeg ] && [ ! -f bin/macos/arm64/ffmpeg ]; then
    cp -f bin/macos/x86_64/ffmpeg bin/macos/arm64/ffmpeg
    echo "[tools] ffmpeg arm64 = x86_64 (M1: przez Rosetta 2)"
fi

# CI: wszystkie narzędzia obowiazkowe (apka bez ffmpeg/yt-dlp/deno jest bezuzyteczna)
if [ "${MUSICBOX_TOOLS_REQUIRED:-0}" = "1" ]; then
    echo "[tools] tryb wymagany (CI) — sprawdzam kompletność"
    for tool in yt-dlp ffmpeg deno; do
        for arch in arm64 x86_64; do
            if [ ! -f "bin/macos/$arch/$tool" ]; then
                echo "[tools] BŁĄD: brak bin/macos/$arch/$tool (wymagany w trybie CI)"
                exit 1
            fi
        done
    done
fi

# ---------- ikona .icns ----------
if [ ! -f assets/icon.icns ] && command -v iconutil >/dev/null 2>&1; then
    echo "[icon] generuję assets/icon.icns z assets/icon.png"
    ICON_SET="$(mktemp -d)/icon.iconset"
    mkdir -p "$ICON_SET"
    for s in 16 32 64 128 256 512 1024; do
        sips -z "$s" "$s" assets/icon.png --out "$ICON_SET/icon_${s}x${s}.png" >/dev/null 2>&1 || true
    done
    iconutil -c icns "$ICON_SET" -o assets/icon.icns
    rm -rf "$(dirname "$ICON_SET")"
    echo "[icon] OK: assets/icon.icns"
fi

# ---------- Python + deps ----------
PY="$(command -v python3 || command -v python)"
echo "[py] $($PY --version) arch=$(uname -m)"
$PY -m pip install --upgrade pip >/dev/null
$PY -m pip install -r requirements.txt -r requirements-dev.txt

# ---------- build ----------
$PY -m PyInstaller MusicBox_macos.spec --noconfirm

echo ""
echo "=== GOTOWE: dist/MusicBox.app ==="
echo "Gatekeeper (niesygnowana apka): prawy klik -> Otwórz albo:"
echo "  xattr -dr com.apple.quarantine dist/MusicBox.app"
