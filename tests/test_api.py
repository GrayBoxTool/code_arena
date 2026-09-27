"""Mock network contracts; no paid API calls or real credentials."""
import io,json,os,sys,tempfile,unittest,urllib.error
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import server,services
from problems import PROBLEMS
class APITest(unittest.TestCase):
    def test_advice_contract_and_failure(self):
        payload={'output':[{'content':[{'type':'output_text','text':'반복문의 범위를 확인하세요.'}]}]}
        with patch.dict(os.environ,{'OPENAI_API_KEY':'fake-test-only'}):
            with patch('urllib.request.urlopen',return_value=io.BytesIO(json.dumps(payload).encode())) as call:
                self.assertEqual(services.assist(PROBLEMS[0],'print(1)'),'반복문의 범위를 확인하세요.')
                body=json.loads(call.call_args.args[0].data)
                self.assertFalse(body['store']);self.assertEqual(call.call_args.kwargs['timeout'],18)
            for response in ({}, {'output':[]}):
                with patch('urllib.request.urlopen',return_value=io.BytesIO(json.dumps(response).encode())):
                    with self.assertRaisesRegex(ValueError,'차감되지'): services.assist(PROBLEMS[0],'print(1)')
            with patch('urllib.request.urlopen',side_effect=urllib.error.URLError('offline')):
                with self.assertRaisesRegex(ValueError,'차감되지'): services.assist(PROBLEMS[0],'print(1)')
    def test_logo_contract_and_stale_response(self):
        with tempfile.TemporaryDirectory() as temp, patch.object(server,'DATA',Path(temp)),patch.object(server,'DB',Path(temp)/'rumble.sqlite3'),patch.dict(os.environ,{'ACCESS_SEED':'test-api-seed-with-at-least-32-characters','OPENAI_API_KEY':'fake-test-only'}):
            server.setup()
            with server.db() as c:
                ep=server.epoch(c);team=c.execute('SELECT name FROM teams WHERE id=1').fetchone()[0]
            payload={'data':[{'b64_json':'dGVzdA=='} for _ in range(3)]}
            server.LOGO_JOBS[1]={'id':'job','started':0,'status':'running'}
            with patch('urllib.request.urlopen',return_value=io.BytesIO(json.dumps(payload).encode())) as call:
                server.logo_worker(1,team,'job',ep)
                req=call.call_args.args[0];body=req.data
                self.assertTrue(req.full_url.endswith('/images/edits'))
                self.assertEqual(body.count(b'name="image[]"'),2)
                self.assertIn(b'name="n"\r\n\r\n3',body)
                self.assertIn('젠지'.encode(),body)
                self.assertIn(b'name="quality"\r\n\r\nlow',body)
            self.assertEqual(server.LOGO_JOBS[1]['status'],'done')
            with server.db() as c:
                self.assertEqual(c.execute('SELECT COUNT(*) FROM logo_candidates').fetchone()[0],3)
                c.execute('DELETE FROM logo_candidates');c.execute('UPDATE teams SET configured=1 WHERE id=1')
            with patch('urllib.request.urlopen',return_value=io.BytesIO(json.dumps(payload).encode())):server.logo_worker(1,team,'job',ep)
            with server.db() as c:self.assertEqual(c.execute('SELECT COUNT(*) FROM logo_candidates').fetchone()[0],0)
            with patch('urllib.request.urlopen',side_effect=urllib.error.URLError('offline')):server.logo_worker(1,team,'job',ep)
            self.assertEqual(server.LOGO_JOBS[1]['status'],'failed')
            server.LOGO_JOBS.clear()
if __name__=='__main__': unittest.main()
