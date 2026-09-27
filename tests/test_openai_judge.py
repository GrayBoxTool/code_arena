"""Exercise the real harness with trusted fixture programs, mocked paid transport."""
import copy,email,json,os,subprocess,sys,tempfile,threading,time,unittest,urllib.request,urllib.error
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import openai_judge as remote
from openai_client import APIError
from problems import PROBLEMS,reference_code

class FakeAPI:
    def __init__(self):self.calls=[];self.script='';self.command='';self.tamper=None
    def __call__(self,path,payload=None,**kw):
        self.calls.append((path,payload,kw))
        if kw.get('method')=='DELETE':return {}
        if path=='containers':
            assert payload['network_policy']=={'type':'disabled'}
            return {'id':'cntr_test'}
        if path.endswith('/files'):
            msg=email.message_from_bytes(('Content-Type: '+kw['content_type']+'\r\nMIME-Version: 1.0\r\n\r\n').encode()+kw['raw'])
            self.script=msg.get_payload(0).get_payload(decode=True).decode()
            return {'path':'/mnt/data/test-runner.py'}
        if path=='responses':
            self.command=payload['input'][0]['content']
            result=subprocess.run([sys.executable,'-c',self.script],capture_output=True,text=True,timeout=20)
            assert result.returncode==0,result.stderr
            response={'status':'completed','output':[{'type':'code_interpreter_call','status':'completed','container_id':'cntr_test','code':self.command,'outputs':[{'type':'logs','logs':result.stdout}]}]}
            if self.tamper:self.tamper(response)
            return response
        raise AssertionError(path)

class RemoteJudgeTest(unittest.TestCase):
    def setUp(self):
        self.env=patch.dict(os.environ,{'JUDGE_PROVIDER':'openai','OPENAI_API_KEY':'fake-only','HOST':'0.0.0.0'});self.env.start()
        self.fake=FakeAPI();self.transport=patch.object(remote,'request',self.fake);self.transport.start()
    def tearDown(self):self.transport.stop();self.env.stop()
    def test_correct_wrong_error_and_timeout(self):
        p=PROBLEMS[0]
        for code,wanted in [(reference_code(p),'정답'),('print("wrong")','오답'),('1/0','실행 오류'),('while True: pass','시간 초과')]:
            with self.subTest(wanted=wanted):
                result=remote.judge_remote(code,p)
                # CPU hard-limit can surface as a signal exit rather than wall-clock timeout.
                if wanted=='시간 초과':self.assertIn(result[0].split(' (')[0],['시간 초과','실행 오류'])
                else:self.assertTrue(result[0].startswith(wanted),result)
        self.assertEqual(sum(x[2].get('method')=='DELETE' for x in self.fake.calls),4)
        self.assertNotIn('solution',self.fake.script.split('execute(json.loads(')[-1])
    def test_ignore_narrative_and_reject_modified_execution(self):
        for mutation in [lambda r:r['output'].clear(),lambda r:r['output'][0].update(code='print("정답")'),
                         lambda r:r['output'].append(copy.deepcopy(r['output'][0])),
                         lambda r:r['output'][0].update(container_id='cntr_other'),
                         lambda r:r['output'][0]['outputs'].clear()]:
            self.fake.tamper=mutation
            with self.assertRaises(remote.JudgeUnavailable):remote.judge_remote(reference_code(PROBLEMS[0]),PROBLEMS[0])
            self.assertEqual(self.fake.calls[-1][2]['method'],'DELETE')
    def test_network_failure_never_falls_back_to_local(self):
        with patch.object(remote,'request',side_effect=APIError('offline')),patch('services.judge') as local:
            with self.assertRaises(remote.JudgeUnavailable):remote.judge_submission('print(1)',PROBLEMS[0])
            local.assert_not_called()
    def test_public_local_mode_disabled(self):
        with patch.dict(os.environ,{'JUDGE_PROVIDER':'local'}):
            self.assertFalse(remote.enabled())
            with self.assertRaises(remote.JudgeUnavailable):remote.judge_submission('print(1)',PROBLEMS[0])

class ServerFailureTest(unittest.TestCase):
    def test_api_error_has_no_score_or_cooldown(self):
        import server
        with tempfile.TemporaryDirectory() as tmp,patch.object(server,'DATA',Path(tmp)),patch.object(server,'DB',Path(tmp)/'test.db'),patch.dict(os.environ,{'HOST':'0.0.0.0','JUDGE_PROVIDER':'openai','OPENAI_API_KEY':'fake-only','ACCESS_SEED':'test-failure-seed-at-least-32-characters'}),patch.object(server,'judge_submission',side_effect=remote.JudgeUnavailable('test outage')):
            server.setup()
            with server.db() as c:
                u=c.execute("SELECT * FROM users WHERE role='player' AND team_id=1 LIMIT 1").fetchone();uid=u['id'];token=u['token']
                m=c.execute('SELECT * FROM matches WHERE round=1 AND team_a=1').fetchone();mid=m['id']
                c.execute("UPDATE matches SET status='open',start_at=?,end_at=? WHERE id=?",(time.time(),time.time()+300,mid))
                c.execute('INSERT INTO round_assignments VALUES (1,1,?,1)',(uid,));server.setval(c,'round',1);server.setval(c,'phase','live')
                d=server.draft(c,mid,uid);body={'epoch':server.epoch(c),'match_id':mid,'rev':d['rev'],'code':'print(1)'}
            http=server.ThreadingHTTPServer(('127.0.0.1',0),server.Handler)
            thread=threading.Thread(target=http.serve_forever,daemon=True);thread.start()
            try:
                req=urllib.request.Request(f'http://127.0.0.1:{http.server_port}/api/submit',data=json.dumps(body).encode(),headers={'Authorization':'Bearer '+token,'Content-Type':'application/json'})
                with self.assertRaises(urllib.error.HTTPError) as err:urllib.request.urlopen(req,timeout=10)
                self.assertEqual(err.exception.code,503)
                with server.db() as c:
                    self.assertEqual(c.execute('SELECT COUNT(*) FROM submissions').fetchone()[0],0)
                    self.assertEqual(c.execute('SELECT COUNT(*) FROM solves').fetchone()[0],0)
                    self.assertEqual(server.draft(c,mid,uid)['cooldown_until'],0)
                self.assertFalse(server.SUBMITTING)
            finally:http.shutdown();http.server_close();thread.join()
if __name__=='__main__':unittest.main()
