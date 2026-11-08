#!/usr/bin/env bash
# Install Kirei for the current user (no root needed).
#
# Works from a release tarball (prebuilt ./kirei) or from a source checkout
# (builds dist/kirei first if it's missing).
#
#   ./install.sh                  install Kirei, and Real-ESRGAN if it's not there yet
#   ./install.sh --no-realesrgan  skip the Real-ESRGAN download
#
# Environment overrides:
#   PREFIX       where to install (default: ~/.local)
#   ESRGAN_DIR   where Real-ESRGAN lives (default: ~/.local/opt/realesrgan-ncnn-vulkan)
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
PREFIX="${PREFIX:-$HOME/.local}"
BIN_DIR="$PREFIX/bin"
APP_DIR="$PREFIX/share/applications"
ICON_DIR="$PREFIX/share/icons/hicolor/256x256/apps"
ESRGAN_DIR="${ESRGAN_DIR:-$HOME/.local/opt/realesrgan-ncnn-vulkan}"
ESRGAN_URL="https://github.com/xinntao/Real-ESRGAN/releases/download/v0.2.5.0/realesrgan-ncnn-vulkan-20220424-ubuntu.zip"
ESRGAN_SHA256="e5aa6eb131234b87c0c51f82b89390f5e3e642b7b70f2b9bbe95b6a285a40c96"

WITH_ESRGAN=1
for arg in "$@"; do
    case "$arg" in
        --no-realesrgan) WITH_ESRGAN=0 ;;
        -h|--help) sed -n '2,12p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
        *) echo "Unknown option: $arg" >&2; exit 2 ;;
    esac
done

say()  { printf '\033[1;33m==>\033[0m %s\n' "$*"; }
fail() { printf '\033[1;31merror:\033[0m %s\n' "$*" >&2; exit 1; }

first_existing() { for f in "$@"; do [[ -e $f ]] && { echo "$f"; return; }; done; }

# ── locate (or build) the pieces ─────────────────────────────
BINARY=$(first_existing "$HERE/kirei" "$HERE/dist/kirei")
if [[ -z $BINARY ]]; then
    [[ -f $HERE/build.sh ]] || fail "No kirei binary found next to this script."
    say "No binary yet, building it first"
    "$HERE/build.sh"
    BINARY="$HERE/dist/kirei"
fi
ICON=$(first_existing "$HERE/kirei.png" "$HERE/assets/kirei.png")
DESKTOP="$HERE/kirei.desktop"
[[ -n $ICON ]] || fail "Icon kirei.png not found."
[[ -f $DESKTOP ]] || fail "kirei.desktop not found."

# ── install Kirei ────────────────────────────────────────────
say "Installing Kirei to $PREFIX"
install -Dm755 "$BINARY" "$BIN_DIR/kirei"
install -Dm644 "$ICON" "$ICON_DIR/kirei.png"
mkdir -p "$APP_DIR"
sed "s|@EXEC@|$BIN_DIR/kirei|" "$DESKTOP" > "$APP_DIR/kirei.desktop"
chmod 644 "$APP_DIR/kirei.desktop"

command -v update-desktop-database >/dev/null && update-desktop-database -q "$APP_DIR" || true
command -v gtk-update-icon-cache  >/dev/null && gtk-update-icon-cache -q -f -t "$PREFIX/share/icons/hicolor" 2>/dev/null || true

# ── Real-ESRGAN ──────────────────────────────────────────────
if [[ -x $ESRGAN_DIR/realesrgan-ncnn-vulkan ]]; then
    say "Real-ESRGAN already installed at $ESRGAN_DIR"
elif [[ $WITH_ESRGAN == 1 ]]; then
    command -v unzip >/dev/null || fail "unzip is needed to install Real-ESRGAN (sudo apt install unzip), or rerun with --no-realesrgan."
    say "Downloading Real-ESRGAN (~45 MB)"
    TMP=$(mktemp -d)
    trap 'rm -rf "$TMP"' EXIT
    if command -v curl >/dev/null; then
        curl -fL --progress-bar -o "$TMP/esrgan.zip" "$ESRGAN_URL"
    elif command -v wget >/dev/null; then
        wget -q --show-progress -O "$TMP/esrgan.zip" "$ESRGAN_URL"
    else
        fail "curl or wget is needed to download Real-ESRGAN."
    fi
    if command -v sha256sum >/dev/null; then
        echo "$ESRGAN_SHA256  $TMP/esrgan.zip" | sha256sum -c --quiet - \
            || fail "The download isn't the expected file, so it wasn't installed."
    fi
    mkdir -p "$ESRGAN_DIR"
    unzip -q -o "$TMP/esrgan.zip" -d "$ESRGAN_DIR"
    rm -f "$ESRGAN_DIR"/input*.jpg "$ESRGAN_DIR"/*.mp4   # demo files from the release
    chmod +x "$ESRGAN_DIR/realesrgan-ncnn-vulkan"
    say "Real-ESRGAN installed at $ESRGAN_DIR"
else
    say "Skipped Real-ESRGAN. Point Kirei at your copy under Advanced."
fi

# ── done ─────────────────────────────────────────────────────
echo
say "Done. Launch Kirei from your app menu, or run: kirei"
case ":$PATH:" in
    *":$BIN_DIR:"*) ;;
    *) echo "    Note: $BIN_DIR is not in your PATH, so 'kirei' won't work in a terminal until you add it." ;;
esac
