import json
import os
import tempfile
import threading
import unittest

from test_contract import document
from test_dialog_playback import Memory, Speech, session
from nao_fair_autostart.contract import ASSIGNMENT, LEASE_COMMAND, POSITION, parse_assignment, read_assignment
from nao_fair_autostart.service import Service
from nao_fair_autostart.touch import TouchClassifier


class ReliabilityTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.clock = 100.0
        self.memory = Memory()
        self.speech = Speech()
        self.speech.setParameter = lambda *args: None
        self.speech.setLanguage = lambda *args: None
        self.service = Service(session(self.speech, self.memory), os.path.join(self.tmp.name, 'assignment.json'), now=lambda: self.clock)
        self.doc = document(dialogs=[{'id': 'tour', 'idle_reset_secs': 5, 'lines': [
            {'id': 'a', 'text': 'A'}, {'id': 'b', 'text': 'B'}, {'id': 'c', 'text': 'C'}]}], active_dialog_id='tour')
        self.service.engine.load(parse_assignment(self.doc))

    def test_both_bumpers_toggle_once_and_persist(self):
        left = self.service._pressed('left_bumper')
        right = self.service._pressed('right_bumper')
        left(1)
        self.clock += 0.1
        right(1)
        self.service._check_bumpers(self.clock + 1.9)
        self.assertTrue(self.service.engine.assignment['armed'])
        self.service._check_bumpers(self.clock + 2.01)
        self.service._speech_worker.join(1)
        self.assertFalse(read_assignment(self.service.store_path)['armed'])
        self.assertIn('Autostart aus', self.speech.calls)
        self.service._check_bumpers(self.clock + 5)
        self.assertFalse(self.service.engine.assignment['armed'])
        left(0)
        right(0)
        left(1)
        right(1)
        self.service._check_bumpers(self.clock + 2.01)
        self.service._speech_worker.join(1)
        self.assertTrue(read_assignment(self.service.store_path)['armed'])
        self.assertIn('Autostart ein', self.speech.calls)

    def test_chord_during_app_lease_publishes_and_persists(self):
        from nao_fair_autostart.contract import ARMED_STATE
        self.memory.data[LEASE_COMMAND] = 'hold'
        self.service._on_lease(1)
        self.service._pressed('left_bumper')(1)
        self.clock += 0.1
        self.service._pressed('right_bumper')(1)
        with self.service._lock:
            self.service._check_bumpers(self.clock + 2.01)
        self.service._speech_worker.join(1)
        state = json.loads(self.memory.data[ARMED_STATE])
        self.assertFalse(state['armed'])
        self.assertFalse(read_assignment(self.service.store_path)['armed'])
        self.assertTrue(state['change'])
        self.assertFalse(self.service.engine.handling)
        self.assertIn('Autostart aus', self.speech.calls)

    def test_outdated_assignment_does_not_undo_chord(self):
        from nao_fair_autostart.contract import ACK_SEQ
        self.service._pressed('left_bumper')(1)
        self.service._pressed('right_bumper')(1)
        self.service._check_bumpers(self.clock + 2.1)
        self.service._speech_worker.join(1)
        self.doc['_expected_arm_change_id'] = 'stale'
        self.memory.data[ASSIGNMENT] = json.dumps(self.doc)
        self.service._on_assignment(44)
        self.assertFalse(self.service.engine.assignment['armed'])
        self.assertNotEqual(self.memory.data.get(ACK_SEQ), 44)

    def test_watchdog_restarts_stalled_service(self):
        class Stop:
            def wait(self, seconds):
                return False
        self.service._stop = Stop()
        self.service._heartbeat = 0
        exits = []
        self.service._watchdog(terminate=exits.append, now=lambda: 31)
        self.assertEqual(exits, [1])

    def test_speech_handoff_cannot_post_old_phrase_after_stop(self):
        entered = threading.Event()
        release = threading.Event()
        calls = []
        original_stop = self.speech.stopAll
        def say(text, _async=False):
            entered.set()
            release.wait(1)
            calls.append('say')
            return None
        def stop():
            calls.append('stop')
            original_stop()
        self.speech.say = say
        self.speech.stopAll = stop
        self.service._speak('old')
        self.assertTrue(entered.wait(1))
        self.memory.data[LEASE_COMMAND] = 'hold'
        lease = threading.Thread(target=self.service._on_lease, args=(1,))
        lease.start()
        release.set()
        lease.join(1)
        self.service._speech_worker.join(1)
        self.assertEqual(calls, ['say', 'stop'])

    def test_long_release_is_not_a_tap(self):
        touch = TouchClassifier()
        touch.down('head', 0)
        self.assertEqual(touch.up('head', 0.61, False), 'long_press')

    def test_reconciled_position_with_same_sequence_is_adopted(self):
        self.service._position = {'dialog_id': 'tour', 'line_id': 'b', 'seq': 2}
        self.memory.data[POSITION] = json.dumps({'dialog_id': 'tour', 'line_id': 'a', 'seq': 2})
        self.service._on_position(2)
        self.assertEqual(self.service._position['line_id'], 'a')

    def test_disabling_idle_timeout_clears_old_deadline(self):
        self.service._play_dialog('dialog_next', False)
        self.doc['dialogs'][0]['idle_reset_secs'] = None
        self.memory.data[ASSIGNMENT] = json.dumps(self.doc)
        self.service._on_assignment(1)
        self.service._idle_due(110)
        self.assertIsNotNone(self.service._position)

    def test_invalid_dialog_does_not_replace_assignment(self):
        self.memory.data[ASSIGNMENT] = json.dumps(dict(self.doc, dialogs=[None]))
        self.service._on_assignment(1)
        self.assertEqual(self.service.engine.assignment['dialogs'][0]['id'], 'tour')

    def test_press_during_lease_is_not_replayed(self):
        self.memory.data[LEASE_COMMAND] = 'hold'
        self.service._on_lease(1)
        pressed = self.service._pressed('front_head')
        pressed(1)
        pressed(0)
        self.memory.data[LEASE_COMMAND] = 'release'
        self.service._on_lease(2)
        self.assertEqual(self.service._touch.tick(self.clock + 1), [])

    def test_delayed_speech_error_restores_position(self):
        done = threading.Event()
        class FailedFuture:
            def isRunning(self):
                return not done.is_set()
            def wait(self):
                done.wait(1)
            def hasError(self):
                return True
        self.speech.say = lambda *args, **kwargs: FailedFuture()
        with self.service._lock:
            self.service._play_dialog('dialog_next', False)
        self.assertEqual(self.service._position['line_id'], 'a')
        done.set()
        for thread in threading.enumerate():
            if thread is not threading.current_thread() and thread.name.startswith('Thread-'):
                thread.join(0.2)
        self.assertIsNone(self.service._position)
