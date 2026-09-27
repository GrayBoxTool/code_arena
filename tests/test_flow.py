"""Integration coverage: readiness, scoring, cooldown, authoritative effects and reset."""
import itertools
import json
import os
from pathlib import Path
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

BASE=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(BASE))
from problems import PROBLEMS,REWARD,HINT_COST,reference_code,expected_outputs,judge_inputs
from services import judge
from server import rename_variable,erase_last_line

class ProblemsTest(unittest.TestCase):
    def test_all_reference_solutions(self):
        self.assertEqual(len(PROBLEMS),35)
        self.assertEqual(HINT_COST,{'type':50,'structure':150,'assist':300})
        for p in PROBLEMS:
            with self.subTest(id=p['id']):
                self.assertGreaterEqual(len(p['cases']),11)
                result=judge(reference_code(p),p)
                self.assertEqual(result[0],'정답')
                self.assertNotEqual(judge('T=int(input())\nfor tc in range(1,T+1): print(f"#{tc} -999999")',p)[0],'정답')

    def test_final_independent_oracles(self):
        for p in PROBLEMS:
            if p['set'] not in (6,7) or p['level'] not in (4,5): continue
            for case in p['cases']:
                lines=case.splitlines()
                if p['level']==4:
                    n,m=map(int,lines[0].split()); d=[[10**9]*n for _ in range(n)]
                    for i in range(n): d[i][i]=0
                    for line in lines[1:]:
                        a,b,w=map(int,line.split());d[a-1][b-1]=min(d[a-1][b-1],w)
                        if p['set']==7: d[b-1][a-1]=min(d[b-1][a-1],w)
                    for k in range(n):
                        for i in range(n):
                            for j in range(n):
                                candidate=d[i][k]+d[k][j] if p['set']==6 else max(d[i][k],d[k][j])
                                d[i][j]=min(d[i][j],candidate)
                    expected=d[0][1:]
                else:
                    n,k=map(int,lines[0].split()); a=list(map(int,lines[1].split()))
                    sums=[sum(a[i] for i in subset) for subset in itertools.combinations(range(n),k) if p['set']==7 or all(y-x>1 for x,y in zip(subset,subset[1:]))]
                    expected=[min(sums) if p['set']==6 else min(abs(sum(a)-2*s) for s in sums)]
                actual=expected_outputs(p|{'cases':[case]})[0].strip().split()[1:]
                self.assertEqual(list(map(int,actual)),expected)

    def test_effects_preserve_non_variables(self):
        code='count=1\ncount+=count\n# count comment\ntext="count"\nobj.count=5\n'
        new,detail=rename_variable(code)
        self.assertIn('"count"',new);self.assertIn('# count comment',new);self.assertIn('obj.count',new)
        replacement=detail.split(' → ')[1]
        self.assertEqual(len(replacement),10);self.assertTrue(replacement.isalpha())
        self.assertIn(replacement+'+=',new)
        formatted,_=rename_variable('count=2\nprint(f"한글 {count + count}")\n')
        namespace={}
        exec(compile(formatted,'<test>','exec'),namespace)
        self.assertNotIn('{count',formatted)
        self.assertEqual(erase_last_line('a=1\nprint(a)\n\n   \n'),'a=1\n\n   \n')

class FlowTest(unittest.TestCase):
    def test_complete_tournament(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            for p in BASE.glob('*.py'): shutil.copy(p,root)
            shutil.copytree(BASE/'static',root/'static')
            with socket.socket() as sock: sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
            env=os.environ|{'PORT':str(port),'HOST':'127.0.0.1','JUDGE_PROVIDER':'local','RUMBLE_DATA_DIR':str(root/'data'),'ACCESS_SEED':'integration-seed-with-more-than-32-characters'}
            env.pop('OPENAI_API_KEY',None)
            proc=subprocess.Popen([sys.executable,str(root/'server.py')],env=env,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)
            try:
                path=root/'data'/'access.json'
                for _ in range(100):
                    if path.exists(): break
                    time.sleep(.05)
                access=json.loads(path.read_text()); admin=access['admin']; teams=list(access['teams'].values())
                tokens=[[p['code'] for p in team] for team in teams]
                def req(route,token=admin,body=None):
                    data=json.dumps(body).encode() if body is not None else None
                    request=urllib.request.Request(f'http://127.0.0.1:{port}/api/{route}',data=data,headers={'Authorization':'Bearer '+token,'Content-Type':'application/json'})
                    try:
                        with urllib.request.urlopen(request,timeout=20) as r: return json.load(r)
                    except urllib.error.HTTPError as e: return json.load(e)
                def mutate(sql,args=()):
                    with sqlite3.connect(root/'data'/'rumble.sqlite3') as c: c.execute(sql,args)
                def action(route,token=admin,**kw): return req(route,token,{'epoch':req('state',token)['epoch'],**kw})
                def submit(token,code=None):
                    s=req('state',token);p=next(p for p in PROBLEMS if p['id']==s['problem']['id'])
                    return req('submit',token,{'epoch':s['epoch'],'match_id':s['match']['id'],'rev':s['draft']['rev'],'code':code or reference_code(p)})
                def write(token,code,rev=None):
                    s=req('state',token)
                    return req('draft',token,{'epoch':s['epoch'],'match_id':s['match']['id'],'rev':s['draft']['rev'] if rev is None else rev,'code':code})
                def prepare():
                    s=req('state')
                    ids={p['id']:(ti,pi) for ti in range(5) for pi in range(5) for p in [req('state',tokens[ti][pi])['me']]}
                    for match in s['matches']:
                        for team in match['teams']:
                            for i,p in enumerate(team['members']):
                                ti,pi=ids[p['id']];token=tokens[ti][pi]
                                self.assertNotIn('error',action('selection',token,level=i+1))
                                self.assertNotIn('error',action('ready',token,ready=True))
                    return action('admin/start')
                self.assertEqual(req('state')['phase'],'matching')
                self.assertIn('error',action('admin/start'))
                # Exercise the actual onboarding endpoints for all twenty-five users.
                for tid in range(5):
                    for i,token in enumerate(tokens[tid]):
                        s=req('profile',token,{'name':f'선수{tid+1}-{i+1}','captain':i==0})
                        self.assertNotIn('error',s)
                    req('team/name',tokens[tid][0],{'name':f'테스트팀{tid+1}'})
                    logos=req('team/logos',tokens[tid][0],{})
                    self.assertEqual(len(logos['team_setup']['candidates']),3)
                    req('team/choose-logo',tokens[tid][0],{'slot':1})
                s=prepare(); self.assertEqual(s['phase'],'live');self.assertEqual(s['duration'],300)
                wrong=submit(tokens[0][0],'print("wrong")')
                self.assertEqual(wrong['last_submission']['verdict'],'오답')
                self.assertGreater(wrong['draft']['cooldown_until'],wrong['server_time'])
                self.assertIn('대기시간',submit(tokens[0][0])['error'])
                self.assertNotIn('error',write(tokens[0][0],'answer=123'))
                mutate('UPDATE drafts SET cooldown_until=0')
                first=submit(tokens[0][0]);self.assertEqual(first['solved']['win_points'],100)
                second=submit(tokens[1][0]);self.assertEqual(second['solved']['win_points'],50)
                hint=action('hint',tokens[0][1],kind='type')
                self.assertEqual(hint['hints'][0]['cost'],50)
                self.assertEqual(next(t for t in hint['standings'] if t['id']==1)['credit'],50)
                details=req('inspect?user_id='+str(first['me']['id']))
                self.assertIsNotNone(details['accepted_code'])
                self.assertIn('error',req('inspect?user_id='+str(first['me']['id']),tokens[1][0]))
                self.assertNotIn('draft',first['match']['teams'][1]['members'][0])
                # The background timer ends the match without any state request.
                mutate("UPDATE matches SET end_at=? WHERE round=1",(time.time()-.1,));time.sleep(.7)
                with sqlite3.connect(root/'data'/'rumble.sqlite3') as c:
                    self.assertEqual(c.execute("SELECT COUNT(*) FROM matches WHERE round=1 AND status='closed'").fetchone()[0],2)
                s=req('state');self.assertEqual(s['phase'],'results');self.assertEqual(s['standings'][0]['points'],200)
                self.assertEqual(req('state')['standings'][0]['points'],200) # bonus once
                self.assertIn('error',action('admin/start'))
                for round_no in range(2,6):
                    self.assertEqual(action('admin/next')['phase'],'matching')
                    self.assertEqual(prepare()['round'],round_no)
                    action('admin/close')
                action('admin/next'); final=prepare()
                self.assertEqual(final['duration'],600)
                self.assertEqual(final['round'],6)
                self.assertEqual(len(final['matches']),1)
                a,b=tokens[0],tokens[1]
                self.assertNotEqual(req('state',a[0])['problem']['id'],req('state',b[0])['problem']['id'])
                early=submit(a[4],'print("wrong")')
                self.assertEqual(early['last_submission']['verdict'],'오답')
                self.assertIsNone(early['relay'])
                mutate('UPDATE drafts SET cooldown_until=0')
                submit(a[0]);freeze=action('item',a[0]);self.assertFalse(freeze['item_available'])
                self.assertIn('빙결',write(b[3],'x=1')['error'])
                self.assertTrue(all(x['freeze_until']>time.time() for x in req('state')['matches'][0]['teams'][1]['members']))
                self.assertIn('이미',action('item',a[0])['error'])
                mutate('UPDATE drafts SET freeze_until=0')
                for token in b[3:]: write(token,'count=1\ncount+=count\nprint(count)\n\n')
                stale=req('state',b[3])['draft']['rev']
                submit(a[1]);action('item',a[1])
                self.assertNotIn('count',req('state',b[3])['draft']['code'])
                self.assertTrue(write(b[3],'count=99',stale)['conflict'])
                before=req('state',b[3])['draft']['code']
                submit(a[2]);action('item',a[2])
                self.assertEqual(req('state',b[3])['draft']['code'],erase_last_line(before))
                relay=submit(a[3]);self.assertTrue(relay['relay']['output'])
                self.assertEqual(req('state',a[4])['relay'],relay['relay'])
                self.assertIsNone(req('state',b[4])['relay'])
                winner=submit(a[4]);self.assertEqual(winner['phase'],'finished');self.assertEqual(winner['match']['winner'],1)
                self.assertEqual(winner['match']['bonus'],0)
                self.assertIn('error',action('admin/next'))
                old_epoch=winner['epoch'];reset=action('admin/reset',confirmation='전체 초기화')
                self.assertNotEqual(reset['epoch'],old_epoch);self.assertEqual(reset['round'],0)
                self.assertTrue(all(t['points']==0 for t in reset['standings']))
                self.assertFalse(req('state',a[0])['me']['profile_complete'])
            finally:
                proc.terminate();out,err=proc.communicate(timeout=5)
                if err: print(err.decode(),file=sys.stderr)

if __name__=='__main__': unittest.main()
