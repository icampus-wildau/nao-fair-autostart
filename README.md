# NAO Fair autostart

Process that runs on a NAO v6 and performs the trigger assignment stored by the NAO Fair app. It starts at boot, in the robot's Python 2.7, the same way as the microphone bridge. The app is not required to be running.

While the NAO Fair app is connected it renews a lease through NAOqi about once a second, and this process ignores triggers. An explicit release, or 20 seconds without a renewal, hands the triggers back. The assignment itself is a JSON file under `/home/nao/nao-fair-autostart/assignment.json`, so it survives a reboot. ALMemory is only the live channel.

The process speaks with the robot's own TTS, stops speech, waves, nods, shakes, sits, stands, and stops a gesture. Gespräch beenden stops speech. Gespräch starten, Gespräch umschalten, and Gespräch beenden und Kontext löschen do nothing here.

Installing it from the NAO Fair app, and detecting that it is already present, comes later. Until then, copy a checkout by hand.

## Install a local checkout

On Linux, or in WSL, from this directory:

```bash
sh packaging/install_on_nao.sh nao@ROBOT_IP
```

The script asks for the `nao` SSH password, copies the files to `/home/nao/nao-fair-autostart/`, registers `/home/nao/nao-fair-autostart/run_forever.sh` under `[program]` in `/home/nao/naoqi/preferences/autoload.ini`, and starts the process. Do not add it under `[python]`. That section runs inside NAOqi.

From a checkout already on the robot, as the `nao` user:

```bash
sh packaging/install_local.sh
```

A robot without this process still accepts a NAO Fair app connection. The app reports that the autostart assignment was not stored.

## On the robot

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
