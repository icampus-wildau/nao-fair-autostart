#!/bin/sh
# Install from a checkout already on the NAO, as the nao user.
# sh packaging/install_local.sh

set -eu

if [ "$(id -un 2>/dev/null || true)" != "nao" ]; then
  echo "Run this on the NAO as the nao user." >&2
  exit 1
fi

ROOT=$(CDPATH= cd -- "$(dirname "$0")/.." && pwd)
DEST=${NAO_FAIR_AUTOSTART_HOME:-$HOME/nao-fair-autostart}
mkdir -p "$DEST/nao_fair_autostart" "$HOME/naoqi/preferences"
cp "$ROOT/autostart_service.py" "$DEST/autostart_service.py"
cp "$ROOT/nao_fair_autostart/"*.py "$DEST/nao_fair_autostart/"
cp "$ROOT/packaging/run_forever.sh" "$DEST/run_forever.sh"
cp "$ROOT/packaging/register_autoload.py" "$DEST/register_autoload.py"
chmod 755 "$DEST/run_forever.sh" "$DEST/autostart_service.py"
python "$DEST/register_autoload.py"
"$DEST/run_forever.sh" stop || true
"$DEST/run_forever.sh"
echo "Installed in $DEST"
