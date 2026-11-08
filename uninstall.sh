#!/usr/bin/env bash
# Remove Kirei for the current user.
#
#   ./uninstall.sh          remove the app, its icon and menu entry
#   ./uninstall.sh --purge  also remove Real-ESRGAN and Kirei's saved settings
#
# Uses the same PREFIX / ESRGAN_DIR overrides as install.sh.
set -euo pipefail

PREFIX="${PREFIX:-$HOME/.local}"
ESRGAN_DIR="${ESRGAN_DIR:-$HOME/.local/opt/realesrgan-ncnn-vulkan}"
CONFIG_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/kirei"

PURGE=0
for arg in "$@"; do
    case "$arg" in
        --purge) PURGE=1 ;;
        -h|--help) sed -n '2,7p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
        *) echo "Unknown option: $arg" >&2; exit 2 ;;
    esac
done

say() { printf '\033[1;33m==>\033[0m %s\n' "$*"; }

say "Removing Kirei from $PREFIX"
rm -f "$PREFIX/bin/kirei" \
      "$PREFIX/share/applications/kirei.desktop" \
      "$PREFIX/share/icons/hicolor/256x256/apps/kirei.png"

command -v update-desktop-database >/dev/null && update-desktop-database -q "$PREFIX/share/applications" || true
command -v gtk-update-icon-cache  >/dev/null && gtk-update-icon-cache -q -f -t "$PREFIX/share/icons/hicolor" 2>/dev/null || true

if [[ $PURGE == 1 ]]; then
    if [[ -d $ESRGAN_DIR && -x $ESRGAN_DIR/realesrgan-ncnn-vulkan ]]; then
        say "Removing Real-ESRGAN at $ESRGAN_DIR"
        rm -rf "$ESRGAN_DIR"
    fi
    if [[ -d $CONFIG_DIR ]]; then
        say "Removing settings at $CONFIG_DIR"
        rm -rf "$CONFIG_DIR"
    fi
fi

say "Done."
