# NAO Fair autostart

Process that runs on a NAO v6 and performs the trigger assignment stored by the NAO Fair app. It starts at boot, in the robot's Python 2.7, the same way as the microphone bridge. The app is not required to be running.

While the NAO Fair app is connected it renews a lease through NAOqi about once a second, and this process ignores triggers. An explicit release, or 20 seconds without a renewal, hands the triggers back. The assignment itself is a JSON file under `/home/nao/nao-fair-autostart/assignment.json`, so it survives a reboot. ALMemory is only the live channel.

The process speaks with the robot's own TTS, stops speech, waves, nods, shakes, sits, stands, and stops a gesture. Gespräch beenden stops speech. Gespräch starten, Gespräch umschalten, and Gespräch beenden und Kontext löschen do nothing here.

Installing it from the NAO Fair app, and detecting that it is already present, comes later.

This is a separate process. Do not add it under `[python]` in `autoload.ini`. That section runs inside NAOqi. The install registers `/home/nao/nao-fair-autostart/run_forever.sh` under `[program]` instead.

## Install from a laptop

On Linux use a terminal with `curl` (or download the script with `wget`), OpenSSH (`ssh` and `scp`), `gzip`, and `tar`. On Windows, run the same command in a WSL Linux terminal with those tools installed; the command is not a PowerShell command.

```bash
curl -LsSf https://raw.githubusercontent.com/icampus-wildau/nao-fair-autostart/main/packaging/install.sh | sh
```

The script downloads the `main` branch, asks for the NAO IP and the `nao` password, copies the files, registers autoload, and starts the process. The first connection prints the robot's SSH host key and waits for `yes`. The address is the IP on its own, for example `192.168.2.57`.

## Install while logged in on the robot

```bash
curl -LsSf https://raw.githubusercontent.com/icampus-wildau/nao-fair-autostart/main/packaging/install_local.sh | sh
```

The script writes into the current home directory and uses `python` and whichever of `wget` or `curl` is installed.

From a checkout already on the robot, `sh packaging/install_local.sh` installs those files instead of downloading `main`.

## Install a local checkout

Use this to copy files that are not on `main` yet:

```bash
sh packaging/install_on_nao.sh nao@ROBOT_IP
```

The script asks for the `nao` SSH password, copies the files to `/home/nao/nao-fair-autostart/`, registers autoload, and starts the process.

A robot without this process still accepts a NAO Fair app connection. The app reports that the autostart assignment was not stored.

## On the robot

Every method copies these into `/home/nao/nao-fair-autostart/`:

- `autostart_service.py`
- `nao_fair_autostart/`
- `run_forever.sh` and `register_autoload.py`

Autoload is `/home/nao/naoqi/preferences/autoload.ini`, under `[program]`. NAOqi merges that file with `/etc/naoqi/autoload.ini`. Leave the system file alone. The install starts the process immediately. The autoload entry starts it again on the next boot.

Stop it:

```bash
ssh nao@ROBOT_IP /home/nao/nao-fair-autostart/run_forever.sh stop
```

Follow the log:

```bash
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

There is no extra secret. Anyone who can already reach NAOqi can already make the robot speak.
