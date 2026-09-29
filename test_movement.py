"""Tests for movement handling in gameinteraction.py."""

import copy
import io
import os
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch

os.chdir(os.path.dirname(os.path.abspath(__file__)))

import gameinteraction
from gameinteraction import myPlayer

PLAYER_FIELDS = ('name', 'job', 'hp', 'mp', 'status_effects', 'location', 'game_over')

LEGAL_MOVES = [
    ('b2', 'n', 'a2'), ('b2', 'e', 'b3'), ('b2', 's', 'c2'), ('b2', 'w', 'b1'),
    ('a1', 'e', 'a2'), ('a1', 's', 'b1'), ('a4', 's', 'b4'), ('a4', 'w', 'a3'),
    ('d1', 'n', 'c1'), ('d1', 'e', 'd2'), ('d4', 'n', 'c4'), ('d4', 'w', 'd3'),
    ('c1', 's', 'c2'), ('b3', 'e', 'b4'),
]

EDGE_MOVES = (
    [(zone, 'n') for zone in ('a1', 'a2', 'a3', 'a4')] +
    [(zone, 's') for zone in ('d1', 'd2', 'd3', 'd4')] +
    [(zone, 'w') for zone in ('a1', 'b1', 'c1', 'd1')] +
    [(zone, 'e') for zone in ('a4', 'b4', 'c4', 'd4')]
)

INVALID_DIRECTIONS = ['x', 'up', 'north', '', 'nn', '1', 'move', '??']


def snapshot(player):
    return copy.deepcopy({field: getattr(player, field) for field in PLAYER_FIELDS})


def run_move(inputs):
    buffer = io.StringIO()
    with patch('builtins.input', side_effect=inputs), redirect_stdout(buffer):
        gameinteraction.player_move()
    return buffer.getvalue()


def run_prompt(inputs):
    buffer = io.StringIO()
    with patch('builtins.input', side_effect=inputs), redirect_stdout(buffer):
        gameinteraction.prompt()
    return buffer.getvalue()


class MovementTestCase(unittest.TestCase):
    def setUp(self):
        myPlayer.name = ''
        myPlayer.job = ''
        myPlayer.hp = 0
        myPlayer.mp = 0
        myPlayer.status_effects = []
        myPlayer.location = 'b2'
        myPlayer.game_over = False


class TestLegalMoves(MovementTestCase):
    def test_legal_moves_table(self):
        for start, direction, expected in LEGAL_MOVES:
            with self.subTest(start=start, direction=direction):
                myPlayer.location = start
                output = run_move([direction])
                self.assertEqual(myPlayer.location, expected)
                self.assertIn('You have moved to ' + expected, output)

    def test_movement_handler_success(self):
        output_buffer = io.StringIO()
        with redirect_stdout(output_buffer):
            gameinteraction.movement_handler('a1')
        self.assertEqual(myPlayer.location, 'a1')
        self.assertIn('You have moved to a1.', output_buffer.getvalue())

    def test_movement_handler_repeated_calls(self):
        for destination in ('a1', 'a2', 'a3', 'a4'):
            with redirect_stdout(io.StringIO()):
                gameinteraction.movement_handler(destination)
            self.assertEqual(myPlayer.location, destination)

    def test_case_and_whitespace_directions(self):
        for raw_input in (' N ', 'N', 'n  ', ' n'):
            with self.subTest(raw_input=raw_input):
                myPlayer.location = 'b2'
                run_move([raw_input])
                self.assertEqual(myPlayer.location, 'a2')


class TestEdgeMoves(MovementTestCase):
    def test_edge_moves_table(self):
        for start, direction in EDGE_MOVES:
            with self.subTest(start=start, direction=direction):
                myPlayer.location = start
                before = snapshot(myPlayer)
                output = run_move([direction])
                self.assertEqual(myPlayer.location, start)
                self.assertEqual(snapshot(myPlayer), before)
                self.assertIn('no zone', output.lower())

    def test_repeated_edge_moves_no_drift(self):
        myPlayer.location = 'b1'
        before = snapshot(myPlayer)
        for _ in range(50):
            output = run_move(['w'])
            self.assertIn('no zone', output.lower())
        self.assertEqual(snapshot(myPlayer), before)

    def test_failure_then_success(self):
        myPlayer.location = 'b1'
        run_move(['w'])
        self.assertEqual(myPlayer.location, 'b1')
        run_move(['n'])
        self.assertEqual(myPlayer.location, 'a1')

    def test_deep_snapshot_after_rejected_call(self):
        myPlayer.name = 'Tester'
        myPlayer.job = 'mage'
        myPlayer.hp = 40
        myPlayer.mp = 120
        myPlayer.status_effects = ['poison']
        myPlayer.location = 'a1'
        before = snapshot(myPlayer)
        run_move(['n', 'w', 'n'])
        self.assertEqual(snapshot(myPlayer), before)

    def test_interrupted_move_leaves_state_untouched(self):
        before = snapshot(myPlayer)
        with patch('builtins.input', side_effect=EOFError):
            with self.assertRaises(EOFError), redirect_stdout(io.StringIO()):
                gameinteraction.player_move()
        self.assertEqual(snapshot(myPlayer), before)


class TestInvalidInput(MovementTestCase):
    def test_invalid_directions_table(self):
        for invalid in INVALID_DIRECTIONS:
            with self.subTest(invalid=invalid):
                myPlayer.location = 'b2'
                before = snapshot(myPlayer)
                output = run_move([invalid, 'n'])
                self.assertEqual(myPlayer.location, 'a2')
                self.assertIn('Not a valid location to move.', output)
                self.assertNotEqual(before['location'], myPlayer.location)

    def test_only_invalid_inputs_no_state_change(self):
        before = snapshot(myPlayer)
        with patch('builtins.input', side_effect=INVALID_DIRECTIONS + [EOFError]):
            with self.assertRaises(EOFError), redirect_stdout(io.StringIO()):
                gameinteraction.player_move()
        self.assertEqual(snapshot(myPlayer), before)

    def test_prompt_unknown_action_then_move(self):
        run_prompt(['bogus', ''])
        self.assertEqual(myPlayer.location, 'b2')
        run_prompt(['move', 'n'])
        self.assertEqual(myPlayer.location, 'a2')

    def test_prompt_quit_raises_system_exit(self):
        with self.assertRaises(SystemExit):
            run_prompt(['quit'])
        self.assertEqual(myPlayer.location, 'b2')


class TestSequences(MovementTestCase):
    SCRIPT = ['e', 'e', 'e', 's', 's', 'w', 'w', 'w', 'w', 'n']

    def walk(self, script):
        for direction in script:
            run_move([direction])

    def test_multi_turn_mixed_sequence(self):
        self.walk(self.SCRIPT)
        self.assertEqual(myPlayer.location, 'c1')

    def test_partial_completion_only_counts_successes(self):
        myPlayer.location = 'a1'
        self.walk(['e', 'n', 'e', 'w', 's'])
        self.assertEqual(myPlayer.location, 'b2')

    def test_replay_same_inputs_same_result(self):
        results = []
        for _ in range(2):
            myPlayer.location = 'b2'
            self.walk(self.SCRIPT)
            results.append(myPlayer.location)
        self.assertEqual(results[0], results[1])
        self.assertEqual(results[0], 'c1')

    def test_many_turns_no_recursion_error(self):
        script = ['e', 'w'] * 300
        self.walk(script)
        self.assertEqual(myPlayer.location, 'b2')


if __name__ == '__main__':
    unittest.main()
