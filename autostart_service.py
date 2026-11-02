#!/usr/bin/env python
"""Run the NAO Fair autostart process against the local NAOqi broker."""

from __future__ import print_function

import argparse
import logging
import os
import sys
import time

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("nao_fair_autostart")


def ensure_session_connected(session, url):
    """Connect when this qi build can report that the session is down.

    NAOqi 2.8 Session has isConnected(). NAOqi 2.1.4 does not. On 2.1,
    Application.start() has already connected, and a second connect() raises.
    """
    is_connected = getattr(session, "isConnected", None)
    if is_connected is None:
        return
    try:
        connected = bool(is_connected())
    except Exception:
        connected = False
    if not connected:
        session.connect(url)


def main(argv):
    parser = argparse.ArgumentParser(description="NAO Fair autostart on the robot")
    parser.add_argument("--qi-url", default=os.environ.get("QI_URL", "tcp://127.0.0.1:9559"))
    parser.add_argument(
        "--home",
        default=os.environ.get("NAO_FAIR_AUTOSTART_HOME", "/home/nao/nao-fair-autostart"),
    )
    args = parser.parse_args(argv[1:])
    import qi

    url = args.qi_url
    application = qi.Application(["nao-fair-autostart", "--qi-url=" + url])
    deadline = time.time() + 120
    while True:
        try:
            application.start()
            session = application.session
            ensure_session_connected(session, url)
            break
        except Exception:
            if time.time() > deadline:
                logger.exception("NAOqi did not accept a connection")
                return 1
            logger.exception("Waiting for NAOqi")
            time.sleep(2)
    from nao_fair_autostart.service import Service

    Service(session, os.path.join(args.home, "assignment.json")).start()
    logger.info("NAO Fair autostart is running")
    application.run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
