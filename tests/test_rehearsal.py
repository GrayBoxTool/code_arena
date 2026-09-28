"""An administrator alone can stage every round and resolve a finalist tie."""
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import unittest
import urllib.error
import urllib.request
from unittest.mock import patch

BASE=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(BASE))
import server


class RehearsalTest(unittest.TestCase):
    def test_score_tie_requires_choice_even_when_win_counts_differ(self):
        ranked=[{'id':1,'name':'A','points':400,'wins':3,'solved':1},
                {'id':2,'name':'B','points':300,'wins':2,'solved':3},
                {'id':3,'name':'C','points':300,'wins':1,'solved':5},
                {'id':4,'name':'D','points':100,'wins':1,'solved':0}]
        with patch.object(server,'standings',return_value=ranked),patch.object(server,'setting',return_value=''):
            tie=server.final_tie(None)
        self.assertTrue(tie['required'])
        self.assertEqual(tie['locked_first'],1)
        self.assertEqual([x['id'] for x in tie['candidates']],[1,2,3])

    def test_solo_rehearsal_and_finalist_tie(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            for source in BASE.glob('*.py'): shutil.copy(source,root)
            shutil.copytree(BASE/'static',root/'static')
            with socket.socket() as sock:
                sock.bind(('127.0.0.1',0))
                port=sock.getsockname()[1]
            env=os.environ|{'PORT':str(port),'HOST':'127.0.0.1','JUDGE_PROVIDER':'local',
                            'RUMBLE_DATA_DIR':str(root/'data'),
                            'ACCESS_SEED':'solo-rehearsal-integration-seed-123456789'}
            env.pop('OPENAI_API_KEY',None)
            proc=subprocess.Popen([sys.executable,str(root/'server.py')],env=env,
                                  stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)
            try:
                access=root/'data'/'access.json'
                for _ in range(100):
                    if access.exists(): break
                    time.sleep(.05)
                self.assertTrue(access.exists())
                codes=json.loads(access.read_text())
                admin=codes['admin']

                def req(route,payload=None,token=None):
                    data=json.dumps(payload).encode() if payload is not None else None
                    request=urllib.request.Request(f'http://127.0.0.1:{port}/api/{route}',data=data,
                        headers={'Authorization':'Bearer '+(token or admin),'Content-Type':'application/json'})
                    try:
                        with urllib.request.urlopen(request,timeout=20) as response:return json.load(response)
                    except urllib.error.HTTPError as error:return json.load(error)

                def action(route,**payload):
                    return req('admin/'+route,{'epoch':req('state')['epoch'],**payload})

                self.assertIn('error',action('start'))  # normal mode still enforces readiness
                self.assertTrue(action('rehearsal',enabled=True)['rehearsal'])
                self.assertEqual(action('start')['round'],1)
                match=req('state')['matches'][0]
                first,second=[team['id'] for team in match['teams']]
                verdict=action('simulate',match_id=match['id'],team_id=first,level=1,verdict='wrong')
                self.assertEqual(next(x for x in verdict['matches'][0]['teams'][0]['members'] if x['level']==1)['verdict'],'오답')
                self.assertIn('error',action('simulate',match_id=match['id'],team_id=999,level=1,verdict='correct'))
                correct=action('simulate',match_id=match['id'],team_id=first,level=1,verdict='correct')
                self.assertEqual(correct['matches'][0]['teams'][0]['points'],100)
                second_result=action('simulate',match_id=match['id'],team_id=second,level=1,verdict='correct')
                self.assertEqual(second_result['matches'][0]['teams'][1]['points'],50)
                self.assertEqual(next(t for t in second_result['standings'] if t['id']==first)['credit'],100)
                self.assertIn('error',action('simulate',match_id=match['id'],team_id=first,level=1,verdict='correct'))
                # Reset also clears rehearsal settings. A scoreless run leaves every team tied.
                reset=action('reset',confirmation='전체 초기화')
                self.assertFalse(reset['rehearsal'])
                self.assertEqual(reset['round'],0)
                action('rehearsal',enabled=True)
                for round_no in range(1,6):
                    if round_no>1:
                        preview=req('state')['upcoming']
                        self.assertEqual(preview['round'],round_no)
                        self.assertEqual(len(preview['pairs']),2)
                        self.assertEqual(action('next')['phase'],'matching')
                    live=action('start')
                    self.assertEqual(live['round'],round_no)
                    self.assertEqual(live['duration'],300)
                    self.assertTrue(all(all(member['ready'] and member['enrolled'] for member in team['members'])
                                        for match in live['matches'] for team in match['teams']))
                    result=action('close')
                    self.assertEqual(result['phase'],'results')
                tie=req('state')['tie']
                self.assertTrue(tie['required'])
                self.assertEqual(len(tie['candidates']),5)
                self.assertIsNone(tie['locked_first'])
                self.assertTrue(req('state')['upcoming']['pending_tie'])
                self.assertIn('error',action('next'))
                self.assertIn('error',action('finalists',team_a=1,team_b=1))
                chosen=action('finalists',team_a=2,team_b=4)
                self.assertEqual(chosen['tie']['chosen'],[2,4])
                preview=chosen['upcoming']['pairs'][0]
                self.assertEqual([x['id'] for x in preview],[2,4])
                self.assertEqual(action('next')['phase'],'matching')
                final=action('start')
                self.assertEqual(final['duration'],600)
                self.assertEqual(final['round'],6)
                mid=final['matches'][0]['id']
                # Final Lv5 is permitted even before the same team's Lv4 is solved.
                from problems import PROBLEMS,reference_code
                token=next(player['code'] for roster in codes['teams'].values() for player in roster
                           if (lambda s:s['me']['team_id']==2 and s['me']['level']==5)(req('state',token=player['code'])))
                player=req('state',token=token)
                self.assertIsNone(player['relay'])
                problem=next(p for p in PROBLEMS if p['id']==player['problem']['id'])
                accepted=req('submit',{'epoch':player['epoch'],'match_id':mid,'rev':player['draft']['rev'],
                                       'code':reference_code(problem)},token=token)
                self.assertEqual(accepted['last_submission']['verdict'],'정답')
                self.assertEqual(req('state')['phase'],'live')
                done=action('close')
                self.assertEqual(done['phase'],'finished')
                self.assertEqual(done['matches'][0]['winner'],2)
                self.assertEqual(len(done['completed_matches']),11)
                self.assertIn('error',action('rehearsal',enabled=False))
            finally:
                proc.terminate()
                _,errors=proc.communicate(timeout=5)
                if errors:print(errors.decode(),file=sys.stderr)


if __name__=='__main__':unittest.main()
