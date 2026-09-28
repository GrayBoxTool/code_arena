import threading
import unittest
import urllib.request
import urllib.error
from pathlib import Path
from http.server import ThreadingHTTPServer
from problems import PROBLEMS,public_problem
from server import Handler
from export_problem_files import question

ROOT=Path(__file__).resolve().parents[1]
class FigureTest(unittest.TestCase):
    def test_figures_documents_and_static_routes(self):
        server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        try:
            count=0
            for p in PROBLEMS:
                pub=public_problem(p)
                self.assertNotIn('input_format',pub)
                self.assertNotIn('sample_explanation',pub)
                doc=question(p)
                self.assertNotIn('테스트케이스 하나의 입력 형식',doc)
                self.assertNotIn('예제 해설',doc)
                for f in pub['figures']:
                    count+=1
                    path=ROOT/'static'/f['src'].lstrip('/')
                    with urllib.request.urlopen(f'http://127.0.0.1:{server.server_port}'+f['src']) as response:
                        self.assertEqual(response.read(),path.read_bytes())
                        self.assertTrue(response.headers['Content-Type'].startswith('image/'))
                    self.assertIn('../../static'+f['src'],doc)
            self.assertEqual(count,15)
            with self.assertRaises(urllib.error.HTTPError) as failure:
                urllib.request.urlopen(f'http://127.0.0.1:{server.server_port}/../server.py')
            self.assertEqual(failure.exception.code,404)
        finally:
            server.shutdown();server.server_close();thread.join()
