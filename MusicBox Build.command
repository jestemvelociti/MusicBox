#!/bin/bash
# MusicBox — build na macOS (M1). Kliknij 2x, Terminal zrobi resztę.
cd "$(dirname "$0")"
chmod +x build_macos.sh 2>/dev/null || true
echo "=== MusicBox — build na macOS ==="
echo "To potrwa ~10-15 minut. Nic nie wpisuj, tylko czekaj."
exec bash build_macos.sh
