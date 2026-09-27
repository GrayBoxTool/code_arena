"""Run with `python -m unittest discover -s tests -v`."""
import json
import os
import shutil
import socket
import sqlite3
import subprocess
import sys
import tempfile
import time
import unittest
import urllib.error
import urllib.request
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE))
from problems import PROBLEMS, REWARD, judge_inputs, reference_code  # noqa: E402
from server import judge  # noqa: E402


class TournamentTest(unittest.TestCase):
    def test_all_reference_solutions(self):
        self.assertEqual(REWARD, {1: 100, 2: 150, 3: 200, 4: 250, 5: 300})
        self.assertEqual({level: points // 2 for level, points in REWARD.items()},
                         {1: 50, 2: 75, 3: 100, 4: 125, 5: 150})
        for p in PROBLEMS:
            with self.subTest(problem=p['id']):
                self.assertGreaterEqual(len(p['cases']), 11)
                self.assertGreaterEqual(len(judge_inputs(p)), 4)
                verdict, passed, total = judge(reference_code(p), p)
                self.assertEqual((verdict, passed), ('정답', total))
                self.assertNotEqual(judge(p['solution'], p)[0], '정답')

    def test_stable_free_service_codes(self):
        seed = 'test-only-access-seed-that-is-over-32-characters'
        env = os.environ | {'ACCESS_SEED': seed}
        output = subprocess.check_output([sys.executable, str(BASE / 'access_codes.py')], env=env)
        codes = json.loads(output)
        self.assertEqual(len(codes['teams']), 5)
        self.assertEqual(len({row['code'] for team in codes['teams'].values() for row in team}), 25)
        same = subprocess.check_output([sys.executable, str(BASE / 'access_codes.py')], env=env)
        self.assertEqual(output, same)
        other = subprocess.check_output([sys.executable, str(BASE / 'access_codes.py')],
                                        env=env | {'ACCESS_SEED': seed + '-other'})
        self.assertNotEqual(output, other)

    def test_round_to_final(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            shutil.copy(BASE / 'server.py', root)
            shutil.copy(BASE / 'problems.py', root)
            shutil.copy(BASE / 'access_codes.py', root)
            shutil.copytree(BASE / 'static', root / 'static')
            with socket.socket() as s:
                s.bind(('127.0.0.1', 0)); port = s.getsockname()[1]
            env = os.environ | {'PORT': str(port), 'ACCESS_SEED': 'integration-test-seed-with-at-least-32-characters'}
            env.pop('OPENAI_API_KEY', None)
            proc = subprocess.Popen([sys.executable, str(root / 'server.py')], stdout=subprocess.DEVNULL,
                                    stderr=subprocess.PIPE, env=env)
            try:
                path = root / 'data' / 'access.json'
                for _ in range(100):
                    if path.exists(): break
                    time.sleep(.05)
                access = json.loads(path.read_text(encoding='utf-8'))
                computed = json.loads(subprocess.check_output([sys.executable, str(root / 'access_codes.py')], env=env))
                self.assertEqual(access, computed)
                admin = access['admin']
                a = access['teams']['블루'][0]['code']
                a2 = access['teams']['블루'][1]['code']
                b = access['teams']['레드'][0]['code']
                with urllib.request.urlopen(f'http://127.0.0.1:{port}/', timeout=10) as page:
                    self.assertIn(b'CODE RUMBLE', page.read())

                def request(route, token, body=None):
                    data = None if body is None else json.dumps(body).encode()
                    req = urllib.request.Request(f'http://127.0.0.1:{port}/api/{route}', data=data,
                                                 headers={'Authorization': 'Bearer ' + token,
                                                          'Content-Type': 'application/json'})
                    try:
                        with urllib.request.urlopen(req, timeout=10) as r:
                            return json.load(r)
                    except urllib.error.HTTPError as e:
                        return json.load(e)

                self.assertFalse(request('state', a)['me']['profile_complete'])
                self.assertEqual(request('selection', a, {'level': 3})['error'], '먼저 선수 이름을 설정하세요.')
                initial = request('profile', a, {'name': '민수', 'captain': True})
                self.assertTrue(initial['me']['profile_complete'])
                self.assertTrue(initial['me']['is_captain'])
                self.assertEqual(initial['rewards'], {'1': 100, '2': 150, '3': 200, '4': 250, '5': 300})
                self.assertIn('이미 팀장이', request('profile', a2, {'name': '지우', 'captain': True})['error'])
                self.assertEqual(request('profile', a2, {'name': '민수'})['error'], '팀 안에 같은 이름을 사용하는 선수가 있습니다.')
                request('profile', a2, {'name': '지우'})
                self.assertEqual(request('team/name', a2, {'name': '번개팀'})['error'], '팀명은 대기실에 들어가기 전 팀장만 정할 수 있습니다.')
                named = request('team/name', a, {'name': '번개팀'})
                self.assertEqual(named['team_setup']['name'], '번개팀')
                self.assertEqual(named['next_match']['team_a_name'], '번개팀')
                logos = request('team/logos', a, {})['team_setup']['candidates']
                self.assertEqual(len(logos), 3)
                self.assertTrue(all(x['source'] == '임시 로고' for x in logos))
                self.assertTrue(request('team/choose-logo', a, {'slot': 2})['team_setup']['complete'])
                self.assertEqual(request('state', a2)['lobby_teams'][0]['name'], '번개팀')
                # If no one volunteers, the last member becomes captain automatically.
                gold = [x['code'] for x in access['teams']['골드']]
                for i, token in enumerate(gold[:4]):
                    self.assertFalse(request('profile', token, {'name': f'선수{i+1}'})['me']['is_captain'])
                self.assertTrue(request('state', gold[4])['me']['force_captain'])
                self.assertTrue(request('profile', gold[4], {'name': '마지막선수'})['me']['is_captain'])
                request('profile', b, {'name': '지훈'})
                self.assertEqual(request('state', a)['round'], 0)
                self.assertEqual(request('selection', a, {'level': 3})['next_selection']['members'][0]['level'], 3)
                self.assertIn('이미 선택한', request('selection', a2, {'level': 3})['error'])
                self.assertIsNone(request('state', a2)['next_selection']['members'][1]['level'])
                request('selection', a2, {'level': 1})
                request('selection', b, {'level': 1})
                round_state = request('admin/advance', admin, {})
                self.assertEqual(round_state['duration'], 300)
                self.assertAlmostEqual(round_state['matches'][0]['end_at'] - round_state['matches'][0]['start_at'], 300)
                self.assertTrue(round_state['matches'][0]['status'] == 'open')
                self.assertEqual(request('state', a)['me']['level'], 3)
                self.assertEqual(request('state', a2)['me']['level'], 1)
                with sqlite3.connect(root / 'data' / 'rumble.sqlite3') as conn:
                    for team in (1, 2):
                        levels = [row[0] for row in conn.execute(
                            "SELECT level FROM round_assignments WHERE round=1 AND team_id=?", (team,))]
                        self.assertEqual(sorted(levels), [1, 2, 3, 4, 5])
                # Simulate a 20-minute deadline left by an earlier prototype.
                with sqlite3.connect(root / 'data' / 'rumble.sqlite3') as conn:
                    conn.execute("UPDATE matches SET end_at=start_at+1200 WHERE round=1 AND status='open'")
                proc.terminate(); proc.communicate(timeout=3)
                proc = subprocess.Popen([sys.executable, str(root / 'server.py')], stdout=subprocess.DEVNULL,
                                        stderr=subprocess.PIPE, env=env)
                for _ in range(100):
                    try:
                        migrated = request('state', a)
                        break
                    except urllib.error.URLError:
                        time.sleep(.05)
                self.assertAlmostEqual(migrated['match']['end_at'] - migrated['match']['start_at'], 300)
                sample = request('state', a2)['problems'][0]
                self.assertTrue(sample['sample_input'].startswith('2\n'))
                self.assertTrue(sample['sample_output'].startswith('#1 '))
                error = request('submit', a2, {'code': 'T=int(input())\nprint(1/0)'})
                self.assertIn('ZeroDivisionError', error['verdict'])
                self.assertIn('ZeroDivisionError', request('state', a2)['last_submission']['verdict'])
                self.assertTrue(request('hint', a, {'kind': 'type'})['error'].startswith('사용 가능한'))
                code = reference_code(PROBLEMS[0])
                first = request('submit', a2, {'code': code})
                self.assertEqual((first['verdict'], first['win_points']), ('정답', 100))
                self.assertEqual(first['state']['standings'][0]['credit'], 100)
                hint_now = request('hint', a, {'kind': 'type'})
                self.assertEqual(hint_now['detail'], PROBLEMS[2]['hint1'])
                self.assertEqual(request('state', a)['standings'][0]['credit'], 50)
                second = request('submit', b, {'code': code})
                self.assertEqual((second['verdict'], second['win_points']), ('정답', 50))
                repeat = request('submit', a2, {'code': code})
                self.assertEqual(repeat['win_points'], 0)
                request('selection', a, {'level': 5})
                request('admin/advance', admin, {})
                self.assertEqual(request('state', a)['me']['level'], 5)
                self.assertEqual(request('state', a)['standings'][0]['credit'], 50)
                for _ in range(3): request('admin/advance', admin, {})
                self.assertIsNone(request('state', a)['next_selection'])
                request('admin/close', admin, {})
                self.assertEqual(request('selection', a, {'level': 4})['next_selection']['round'], 6)
                request('selection', b, {'level': 4})
                final = request('admin/advance', admin, {})
                self.assertEqual(final['round'], 6)
                self.assertEqual(len(final['matches']), 1)
                self.assertEqual(request('state', a)['me']['level'], 4)
                self.assertEqual(request('state', b)['me']['level'], 4)
            finally:
                proc.terminate()
                try: proc.communicate(timeout=3)
                except subprocess.TimeoutExpired: proc.kill()


if __name__ == '__main__':
    unittest.main()
