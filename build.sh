#!/usr/bin/env bash
# Build Kirei into a single self-contained binary at dist/kirei.
#   ./build.sh            build the binary
#   ./build.sh --package  also make dist/kirei-<version>-linux-x86_64.tar.gz for a GitHub release
set -euo pipefail
cd "$(dirname "$0")"

VERSION=$(sed -n 's/^__version__ = "\(.*\)"/\1/p' main.py)
PY=.venv/bin/python

if [[ ! -x $PY ]]; then
    echo "==> Creating virtual environment"
    python3 -m venv .venv
fi

echo "==> Installing build dependencies"
$PY -m pip install --quiet --upgrade pip
$PY -m pip install --quiet -r requirements.txt -r requirements-dev.txt

echo "==> Rendering icon"
$PY tools/export_icon.py assets/kirei.png 256

echo "==> Building binary (this takes a minute)"
$PY -m PyInstaller --noconfirm --clean --log-level WARN \
    --onefile --windowed --name kirei \
    --exclude-module tkinter \
    main.py

echo "==> Built dist/kirei ($(du -h dist/kirei | cut -f1))"

if [[ ${1:-} == "--package" ]]; then
    NAME="kirei-${VERSION}-linux-x86_64"
    STAGE="dist/$NAME"
    rm -rf "$STAGE"
    mkdir -p "$STAGE"
    cp dist/kirei install.sh uninstall.sh kirei.desktop README.md "$STAGE/"
    cp assets/kirei.png "$STAGE/"
    [[ -f LICENSE ]] && cp LICENSE "$STAGE/"
    tar -C dist -czf "dist/$NAME.tar.gz" "$NAME"
    rm -rf "$STAGE"
    echo "==> Packaged dist/$NAME.tar.gz ($(du -h "dist/$NAME.tar.gz" | cut -f1))"
fi
