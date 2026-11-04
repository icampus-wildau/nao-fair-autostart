# nao-fair-autostart

*Run the NAO Fair trigger assignment on the robot, including after a reboot.*

![Python](https://img.shields.io/badge/python-2.7-blue?style=flat-square)
![CI](https://img.shields.io/github/actions/workflow/status/icampus-wildau/nao-fair-autostart/ci.yml?style=flat-square&label=CI)
![License: Apache 2.0](https://img.shields.io/badge/license-Apache%20License%202.0-blue)

This is a service application for the [NAO Fair app](https://github.com/icampus-wildau/nao-fair), allowing assigned static interactions being auto-started on the robot independently of the app.

The process runs in the NAO's Python 2.7, the same way as the [websocket bridge service](https://github.com/icampus-wildau/nao-websocket-bridge). 

While the app is connected it renews a lease through NAOqi about once a second, and this process ignores triggers. An explicit release, or 20 seconds without a renewal, hands the triggers back. The assignment is `assignment.json` under `/home/nao/nao-fair-autostart/`, so it survives a reboot. ALMemory is only the live channel.

On its own it speaks with the robot's TTS, stops speech, steps through a stored dialog, waves, nods, shakes, sits, stands, and stops a gesture. `stop_conversation` (Gespräch beenden) only stops speech. `start_conversation`, `toggle_conversation`, and `stop_and_clear` do nothing here.

The NAO Fair app installs this process from its system tab. A robot without it still accepts a connection. The app then reports that the autostart assignment was not stored.

Do not add this program under `[python]` in `autoload.ini`. That section runs inside NAOqi. The install registers `/home/nao/nao-fair-autostart/run_forever.sh` under `[program]`.

## Install

### Via the NAO Fair app

Easiest way is to install via the NAO Fair app in the system tab.

### From a laptop

From a laptop, with `curl` or `wget`, OpenSSH, `gzip`, and `tar`. On Windows, run this in WSL.

```bash
curl -LsSf https://raw.githubusercontent.com/icampus-wildau/nao-fair-autostart/main/packaging/install.sh | sh
```

The script downloads the latest GitHub release, asks for the NAO IP and the `nao` password, copies the files, registers autoload, and starts the process. 
The address is the IP on its own, for example `192.168.2.57`.

```bash
# while logged in on the robot; writes into the current home directory
curl -LsSf https://raw.githubusercontent.com/icampus-wildau/nao-fair-autostart/main/packaging/install_local.sh | sh

# checkout already on the robot, using those files instead of main
sh packaging/install_local.sh

# copy a checkout that is not on main yet
sh packaging/install_on_nao.sh nao@ROBOT_IP
```

## On the robot

Files land in `/home/nao/nao-fair-autostart/`: `autostart_service.py`, `nao_fair_autostart/`, `run_forever.sh`, and `register_autoload.py`.

Autoload is `/home/nao/naoqi/preferences/autoload.ini`, under `[program]`. NAOqi merges that file with `/etc/naoqi/autoload.ini`. Leave the system file alone. The install starts the process immediately. The autoload entry starts it again on the next boot.

```bash
ssh nao@ROBOT_IP /home/nao/nao-fair-autostart/run_forever.sh stop
ssh nao@ROBOT_IP tail -f /home/nao/nao-fair-autostart/run_forever.log
```

## ALMemory keys

| Key | Writer | Meaning |
|---|---|---|
| `NAOFair/Autostart/Assignment` | App | JSON assignment |
| `NAOFair/Autostart/AssignmentSeq` | App | Integer bumped on each push |
| `NAOFair/Autostart/AckSeq` | Robot | Sequence persisted to disk |
| `NAOFair/Autostart/LeaseCommand` | App | `hold` or `release` |
| `NAOFair/Autostart/LeaseSeq` | App | Integer bumped about once a second while connected |
| `NAOFair/Autostart/LeaseAckSeq` | Robot | Last hold sequence after speech and the current gesture were stopped |
| `NAOFair/Dialog/Position` | Both | JSON dialog position |
| `NAOFair/Dialog/PositionSeq` | Both | Integer bumped when the position changes |
| `NAOFair/Autostart/Version` | Robot | Installed autostart version |

There is no extra secret. Anyone who can already reach NAOqi can already make the robot speak.
