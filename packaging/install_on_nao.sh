#!/bin/sh
# Copy this checkout onto a NAO and register autostart.
# Usage: sh packaging/install_on_nao.sh nao@ROBOT_IP
#
# packaging/install.sh downloads the latest release and calls this script. Use this file
# directly to copy a checkout that is not in a release yet.

set -eu

if [ "$#" -ne 1 ]; then
  echo "Usage: sh packaging/install_on_nao.sh nao@ROBOT_IP" >&2
  exit 1
fi

trim_field() {
  field=$(printf '%s' "$1" | tr -d '\r')
  field=${field#"${field%%[![:space:]]*}"}
  field=${field%"${field##*[![:space:]]}"}
  printf '%s' "$field"
}

ssh_name_ok() {
  case "$1" in
    ""|-*)
      return 1
      ;;
    *[!A-Za-z0-9._-]*)
      return 1
      ;;
  esac
}

raw=$(trim_field "$1")
case "$raw" in
  *@*)
    login=$(trim_field "${raw%@*}")
    host=$(trim_field "${raw##*@}")
    ;;
  *)
    login=nao
    host=$raw
    ;;
esac
case "$host" in
  *" ("*")")
    host=$(trim_field "${host%% (*}")
    ;;
esac
if ! ssh_name_ok "$login" || ! ssh_name_ok "$host"; then
  echo "Cannot connect to '$raw'." >&2
  echo "ssh rejects that address (hostname contains invalid characters)." >&2
  echo "Enter the robot IP on its own, for example 192.168.2.57." >&2
  exit 1
fi
ROBOT=$login@$host
ROOT=$(CDPATH= cd -- "$(dirname "$0")/.." && pwd)
REMOTE_DIR=/home/nao/nao-fair-autostart
CONTROL_DIR=$(mktemp -d)
CONTROL_PATH=$CONTROL_DIR/ssh.sock

ssh_base() {
  if [ -n "${NAO_KNOWN_HOSTS:-}" ]; then
    printf '%s\n' -o "UserKnownHostsFile=$NAO_KNOWN_HOSTS" -o StrictHostKeyChecking=yes
  fi
  printf '%s\n' -o ControlMaster=auto -o "ControlPath=$CONTROL_PATH" -o ControlPersist=120
}

ssh_nao() {
  # shellcheck disable=SC2046
  ssh $(ssh_base) "$@"
}

scp_nao() {
  # shellcheck disable=SC2046
  scp -O $(ssh_base) "$@"
}

cleanup() {
  ssh -o ControlPath="$CONTROL_PATH" -O exit "$ROBOT" >/dev/null 2>&1 || true
  rm -rf "$CONTROL_DIR"
}
trap cleanup EXIT
trap 'cleanup; exit 130' INT
trap 'cleanup; exit 143' TERM

STAGE=$REMOTE_DIR.stage
echo "Installing NAO Fair autostart on $ROBOT"
if [ -z "${SSH_ASKPASS:-}" ]; then
  echo "Enter the SSH password once. The rest of the install reuses that login."
fi
ssh_nao "$ROBOT" "rm -rf '$STAGE' && mkdir -p '$STAGE/nao_fair_autostart' /home/nao/naoqi/preferences"
scp_nao "$ROOT/autostart_service.py" "$ROBOT:$STAGE/autostart_service.py"
scp_nao "$ROOT/nao_fair_autostart/"*.py "$ROBOT:$STAGE/nao_fair_autostart/"
scp_nao "$ROOT/packaging/run_forever.sh" "$ROBOT:$STAGE/run_forever.sh"
scp_nao "$ROOT/packaging/register_autoload.py" "$ROBOT:$STAGE/register_autoload.py"
scp_nao "$ROOT/packaging/replace_tree.sh" "$ROBOT:$STAGE/replace_tree.sh"
if [ -n "${NAO_PROGRAM_VERSION:-}" ]; then
  printf '%s\n' "$NAO_PROGRAM_VERSION" > "$CONTROL_DIR/VERSION"
  scp_nao "$CONTROL_DIR/VERSION" "$ROBOT:$STAGE/VERSION"
fi
ssh_nao "$ROBOT" "chmod 755 '$STAGE/run_forever.sh' '$STAGE/autostart_service.py' '$STAGE/replace_tree.sh'"
ssh_nao "$ROBOT" "NAO_CANON='$REMOTE_DIR' NAO_STAGE='$STAGE' NAO_MARKER='autostart_service.py' NAO_HOME_TOKEN='nao-fair-autostart' NAO_KEEP='assignment.json' NAO_REGISTER=1 '$STAGE/replace_tree.sh'"

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
