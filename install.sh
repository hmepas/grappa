#!/usr/bin/env bash
# grappa installer for systems without Homebrew.
#
#   curl -fsSL https://raw.githubusercontent.com/hmepas/grappa/main/install.sh | bash
#
# Installs grappa into an isolated virtualenv under ~/.local/share/grappa
# and symlinks the `grappa` command into ~/.local/bin.
#
# Overridable via environment variables:
#   GRAPPA_INSTALL_DIR  install location (default: ~/.local/share/grappa)
#   GRAPPA_BIN_DIR      symlink location (default: ~/.local/bin)
#   GRAPPA_REF          git branch or tag to install (default: main)
set -euo pipefail

REPO="https://github.com/hmepas/grappa"
INSTALL_DIR="${GRAPPA_INSTALL_DIR:-$HOME/.local/share/grappa}"
BIN_DIR="${GRAPPA_BIN_DIR:-$HOME/.local/bin}"
REF="${GRAPPA_REF:-main}"

info() { printf '\033[1;34m==>\033[0m %s\n' "$*"; }
error() { printf '\033[1;31merror:\033[0m %s\n' "$*" >&2; exit 1; }

# Find a Python >= 3.10 and < 3.14
PYTHON=""
for candidate in python3.13 python3.12 python3.11 python3.10 python3; do
    if command -v "$candidate" >/dev/null 2>&1 &&
        "$candidate" -c 'import sys; sys.exit(0 if (3, 10) <= sys.version_info < (3, 14) else 1)' 2>/dev/null; then
        PYTHON="$(command -v "$candidate")"
        break
    fi
done
[ -n "$PYTHON" ] || error "Python >= 3.10 and < 3.14 is required but was not found."

info "Using $PYTHON ($("$PYTHON" --version 2>&1))"

info "Creating virtualenv in $INSTALL_DIR/venv"
mkdir -p "$INSTALL_DIR"
"$PYTHON" -m venv --clear "$INSTALL_DIR/venv"

info "Installing grappa ($REF) from $REPO"
"$INSTALL_DIR/venv/bin/pip" install --quiet --upgrade pip
"$INSTALL_DIR/venv/bin/pip" install --quiet "git+${REPO}.git@${REF}"

mkdir -p "$BIN_DIR"
ln -sf "$INSTALL_DIR/venv/bin/grappa" "$BIN_DIR/grappa"
info "Installed: $BIN_DIR/grappa"

case ":$PATH:" in
    *":$BIN_DIR:"*) ;;
    *)
        printf '\n%s is not in your PATH. Add this to your shell profile:\n' "$BIN_DIR"
        printf '  export PATH="%s:$PATH"\n' "$BIN_DIR"
        ;;
esac

cat <<EOF

grappa installed. Next steps:
  1. Get Telegram API credentials at https://my.telegram.org/apps
  2. Run: grappa test-connection
     (on first run grappa asks for the credentials and saves them
      to ~/.config/grappa/config.env)

To uninstall: rm -rf "$INSTALL_DIR" "$BIN_DIR/grappa"
EOF
