from __future__ import unicode_literals

import unittest

from autostart_service import ensure_session_connected


class ConnectedSession(object):
    def __init__(self):
        self.connected = True
        self.urls = []

    def isConnected(self):
        return self.connected

    def connect(self, url):
        self.urls.append(url)
        self.connected = True


class LegacySession(object):
    """NAOqi 2.1 Session: no isConnected, and connect() is not idempotent."""

    def __init__(self):
        self.urls = []

    def connect(self, url):
        self.urls.append(url)


class TestEnsureSessionConnected(unittest.TestCase):
    def test_naoqi_2_8_skips_connect_when_the_session_is_open(self):
        session = ConnectedSession()

        ensure_session_connected(session, "tcp://127.0.0.1:9559")

        self.assertEqual(session.urls, [])

    def test_naoqi_2_8_connects_when_the_session_is_down(self):
        session = ConnectedSession()
        session.connected = False

        ensure_session_connected(session, "tcp://127.0.0.1:9559")

        self.assertEqual(session.urls, ["tcp://127.0.0.1:9559"])
        self.assertTrue(session.isConnected())

    def test_naoqi_2_8_connects_when_is_connected_raises(self):
        class Broken(ConnectedSession):
            def isConnected(self):
                raise RuntimeError("socket closed")

        session = Broken()

        ensure_session_connected(session, "tcp://127.0.0.1:9559")

        self.assertEqual(session.urls, ["tcp://127.0.0.1:9559"])

    def test_naoqi_2_1_does_not_connect_again(self):
        session = LegacySession()

        ensure_session_connected(session, "tcp://127.0.0.1:9559")

        self.assertEqual(session.urls, [])


if __name__ == "__main__":
    unittest.main()
