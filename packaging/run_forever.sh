#!/bin/sh
# Keep NAO Fair autostart running across Python crashes.
# The first invocation returns immediately so NAOqi's [program] autoload
# does not wait on the restart loop.

AUTOSTART_HOME=${NAO_FAIR_AUTOSTART_HOME:-/home/nao/nao-fair-autostart}
cd "$AUTOSTART_HOME" || exit 1

PIDFILE=$AUTOSTART_HOME/run_forever.pid
LOGFILE=$AUTOSTART_HOME/run_forever.log

# `ps` on the NAO prints the short command name. Match /proc/PID/cmdline.
autostart_pids() {
  for dir in /proc/[0-9]*; do
    pid=${dir#/proc/}
    [ -r "$dir/cmdline" ] || continue
    cmd=$(tr '\0' ' ' < "$dir/cmdline" 2>/dev/null) || continue
    case "$cmd" in
      *autostart_service.py*)
        printf '%s\n' "$pid"
        ;;
      *run_forever.sh*)
        case "$cmd" in
          *" stop"*) ;;
          *) printf '%s\n' "$pid" ;;
        esac
        ;;
    esac
  done
}

signal_autostart() {
  sig=$1
  autostart_pids | while read -r pid; do
    [ -n "$pid" ] || continue
    kill "$sig" "$pid" 2>/dev/null || true
  done
}

autostart_is_running() {
  autostart_pids | grep -q .
}

if [ "${1:-}" = "stop" ]; then
  signal_autostart -TERM
  i=0
  while autostart_is_running; do
    if [ "$i" -ge 4 ]; then
      break
    fi
    sleep 1
    i=$((i + 1))
  done
  if autostart_is_running; then
    signal_autostart -KILL
    i=0
    while autostart_is_running; do
      if [ "$i" -ge 3 ]; then
        echo "NAO Fair autostart is still running" >&2
        exit 1
      fi
      sleep 1
      i=$((i + 1))
    done
  fi
  rm -f "$PIDFILE"
  exit 0
fi

if [ -z "${NAO_FAIR_AUTOSTART_CHILD:-}" ]; then
  if [ -f "$PIDFILE" ]; then
    old=$(cat "$PIDFILE")
    if kill -0 "$old" 2>/dev/null; then
      echo "NAO Fair autostart restart loop already running ($old)."
      exit 0
    fi
  fi
  NAO_FAIR_AUTOSTART_CHILD=1 nohup "$0" >>"$LOGFILE" 2>&1 &
  echo $! > "$PIDFILE"
  exit 0
fi

echo $$ > "$PIDFILE"

add_ld() {
  if [ -d "$1" ]; then
    case ":${LD_LIBRARY_PATH:-}:" in
      *":$1:"*) ;;
      *) LD_LIBRARY_PATH="$1${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}" ;;
    esac
  fi
}
add_py() {
  if [ -d "$1/qi" ] || [ -f "$1/qi.so" ]; then
    case ":${PYTHONPATH:-}:" in
      *":$1:"*) ;;
      *) PYTHONPATH="$1${PYTHONPATH:+:$PYTHONPATH}" ;;
    esac
  fi
}
add_ld /opt/aldebaran/lib
add_ld /usr/lib
export LD_LIBRARY_PATH
add_py /opt/aldebaran/lib/python2.7/site-packages
add_py /usr/lib/python2.7/site-packages
export PYTHONPATH

PYTHON_BIN=""
for candidate in /usr/bin/python2.7 /usr/bin/python2 python2 python; do
  if [ -x "$candidate" ] || command -v "$candidate" >/dev/null 2>&1; then
    if "$candidate" -c "import qi" >/dev/null 2>&1; then
      PYTHON_BIN=$candidate
      break
    fi
  fi
done
if [ -z "$PYTHON_BIN" ]; then
  echo "No interpreter could import qi." >&2
  if [ -x /usr/bin/python2.7 ]; then
    PYTHON_BIN=/usr/bin/python2.7
  else
    PYTHON_BIN=python
  fi
fi
echo "NAO Fair autostart Python: $PYTHON_BIN"

child=0
stop_child() {
  if [ "$child" -ne 0 ]; then
    kill -TERM "$child" 2>/dev/null || true
  fi
  child=0
  exit 0
}
trap stop_child TERM INT

while true; do
  "$PYTHON_BIN" autostart_service.py --home "$AUTOSTART_HOME" &
  child=$!
  wait "$child"
  status=$?
  child=0
  echo "autostart exited ($status), restarting in 2s"
  sleep 2
done
