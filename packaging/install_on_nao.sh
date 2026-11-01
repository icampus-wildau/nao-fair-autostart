#!/bin/sh
# Copy this checkout onto a NAO and register autostart.
# Usage: sh packaging/install_on_nao.sh nao@ROBOT_IP
#
# Detecting whether the process is already installed, and installing it from
# the NAO Fair app, is a later step. This script is the manual copy.

set -eu

if [ "$#" -ne 1 ]; then
  echo "Usage: sh packaging/install_on_nao.sh nao@ROBOT_IP" >&2
  exit 1
fi

ROBOT=$1
ROOT=$(CDPATH= cd -- "$(dirname "$0")/.." && pwd)
REMOTE_DIR=/home/nao/nao-fair-autostart
CONTROL_DIR=$(mktemp -d)
CONTROL_PATH=$CONTROL_DIR/ssh.sock

ssh_nao() {
  ssh -o ControlMaster=auto -o ControlPath="$CONTROL_PATH" -o ControlPersist=120 "$@"
}

scp_nao() {
  scp -O -o ControlMaster=auto -o ControlPath="$CONTROL_PATH" -o ControlPersist=120 "$@"
}

cleanup() {
  ssh -o ControlPath="$CONTROL_PATH" -O exit "$ROBOT" >/dev/null 2>&1 || true
  rm -rf "$CONTROL_DIR"
}
trap cleanup EXIT
trap 'cleanup; exit 130' INT
trap 'cleanup; exit 143' TERM

echo "Installing NAO Fair autostart on $ROBOT"
if [ -z "${SSH_ASKPASS:-}" ]; then
  echo "Enter the SSH password once. The rest of the install reuses that login."
fi
ssh_nao "$ROBOT" "mkdir -p '$REMOTE_DIR/nao_fair_autostart' /home/nao/naoqi/preferences"
scp_nao "$ROOT/autostart_service.py" "$ROBOT:$REMOTE_DIR/autostart_service.py"
scp_nao "$ROOT/nao_fair_autostart/"*.py "$ROBOT:$REMOTE_DIR/nao_fair_autostart/"
scp_nao "$ROOT/packaging/run_forever.sh" "$ROBOT:$REMOTE_DIR/run_forever.sh"
scp_nao "$ROOT/packaging/register_autoload.py" "$ROBOT:$REMOTE_DIR/register_autoload.py"
ssh_nao "$ROBOT" "chmod 755 '$REMOTE_DIR/run_forever.sh' '$REMOTE_DIR/autostart_service.py'"
ssh_nao "$ROBOT" "python '$REMOTE_DIR/register_autoload.py'"
ssh_nao "$ROBOT" "'$REMOTE_DIR/run_forever.sh' stop" || true
ssh_nao "$ROBOT" "'$REMOTE_DIR/run_forever.sh'"

cat <<EOF
Installed on $ROBOT.

NAOqi will start autostart from [program] in
/home/nao/naoqi/preferences/autoload.ini the next time it boots.
The process was also started now.

Log:
  ssh $ROBOT tail -f $REMOTE_DIR/run_forever.log

Stop:
  ssh $ROBOT $REMOTE_DIR/run_forever.sh stop
EOF
