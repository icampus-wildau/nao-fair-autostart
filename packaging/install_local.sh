#!/bin/sh
# Install NAO Fair autostart on this machine. Run it on the NAO, as the nao user.
# No robot IP or SSH password: the files are written into this home directory.
#
# Already logged in on the robot, with nothing cloned:
#
#   curl -LsSf https://raw.githubusercontent.com/icampus-wildau/nao-fair-autostart/main/packaging/install_local.sh | sh
#
# Or, from a checkout of this repo on the robot:
#
#   sh packaging/install_local.sh
#
# A checkout is used as-is. Otherwise the script downloads the main branch.
# wget is used when curl is not installed. python is the NAO's Python 2.7.

set -eu

if [ "$(id -un 2>/dev/null || true)" != "nao" ]; then
  echo "Run this on the NAO as the nao user. Current user is $(id -un 2>/dev/null || echo unknown)." >&2
  exit 1
fi

REPO=https://github.com/icampus-wildau/nao-fair-autostart
BRANCH=main

DEST=${NAO_FAIR_AUTOSTART_HOME:-$HOME/nao-fair-autostart}
AUTOLOAD=$HOME/naoqi/preferences/autoload.ini

fetch() {
  url=$1
  dest=$2
  if command -v curl >/dev/null 2>&1; then
    curl -fsSL "$url" -o "$dest"
  elif command -v wget >/dev/null 2>&1; then
    wget -O "$dest" "$url"
  else
    echo "curl or wget is required to download autostart." >&2
    return 1
  fi
}

download_main() {
  work=$1
  echo "Downloading $REPO ($BRANCH)"
  fetch "$REPO/archive/refs/heads/$BRANCH.tar.gz" "$work/autostart.tar.gz"
  mkdir -p "$work/src"
  gzip -dc "$work/autostart.tar.gz" | tar -xf - -C "$work/src"
  ROOT=$work/src/nao-fair-autostart-$BRANCH
}

if [ -f "$0" ]; then
  SCRIPT_DIR=$(CDPATH= cd -- "$(dirname "$0")" && pwd)
  MAYBE_ROOT=$(CDPATH= cd -- "$SCRIPT_DIR/.." && pwd)
  if [ -f "$MAYBE_ROOT/autostart_service.py" ]; then
    ROOT=$MAYBE_ROOT
  fi
fi

WORKDIR=
if [ -z "${ROOT:-}" ]; then
  if command -v mktemp >/dev/null 2>&1; then
    WORKDIR=$(mktemp -d)
  else
    WORKDIR=/tmp/nao-fair-autostart-install.$$
    mkdir -p "$WORKDIR"
  fi
  trap 'rm -rf "$WORKDIR"' EXIT
  trap 'rm -rf "$WORKDIR"; exit 130' INT
  trap 'rm -rf "$WORKDIR"; exit 143' TERM
  download_main "$WORKDIR"
fi

if [ ! -f "$ROOT/autostart_service.py" ]; then
  echo "No autostart_service.py under $ROOT" >&2
  exit 1
fi

if ! command -v python >/dev/null 2>&1; then
  echo "python is required to register the autoload entry." >&2
  exit 1
fi

echo "Installing NAO Fair autostart into $DEST"
mkdir -p "$DEST/nao_fair_autostart" "$HOME/naoqi/preferences"
cp "$ROOT/autostart_service.py" "$DEST/autostart_service.py"
cp "$ROOT/nao_fair_autostart/"*.py "$DEST/nao_fair_autostart/"
cp "$ROOT/packaging/run_forever.sh" "$DEST/run_forever.sh"
cp "$ROOT/packaging/register_autoload.py" "$DEST/register_autoload.py"
chmod 755 "$DEST/run_forever.sh" "$DEST/autostart_service.py"

python "$DEST/register_autoload.py" "$AUTOLOAD" "$DEST/run_forever.sh"
"$DEST/run_forever.sh" stop || true
NAO_FAIR_AUTOSTART_HOME=$DEST "$DEST/run_forever.sh"

cat <<EOF
Installed into $DEST.

NAOqi will start autostart from [program] in
$AUTOLOAD the next time it boots.
The process was also started now.

Log:
  tail -f $DEST/run_forever.log

Stop:
  $DEST/run_forever.sh stop
EOF
