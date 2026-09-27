"""Trusted execution harness uploaded to an OpenAI container, never run by the web server.
Payload is appended by openai_judge. Expected answers and credentials are NOT uploaded.
"""
import base64,json,subprocess,sys,tempfile,os,signal,resource
from pathlib import Path

def execute(payload):
    results=[]
    for index,test in enumerate(payload['inputs']):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'solution.py'
            path.write_bytes(base64.b64decode(payload['code']))
            def limits():
                resource.setrlimit(resource.RLIMIT_CPU,(2,3))
                resource.setrlimit(resource.RLIMIT_AS,(256*1024**2,256*1024**2))
                resource.setrlimit(resource.RLIMIT_FSIZE,(65536,65536))
                resource.setrlimit(resource.RLIMIT_NOFILE,(32,32))
            with tempfile.TemporaryFile() as stdout,tempfile.TemporaryFile() as stderr:
                proc=subprocess.Popen([sys.executable,'-I','-S','-B',str(path)],stdin=subprocess.PIPE,
                    stdout=stdout,stderr=stderr,cwd=directory,env={'PYTHONIOENCODING':'utf-8'},
                    start_new_session=True,preexec_fn=limits)
                timed_out=False
                try:proc.communicate(base64.b64decode(test),timeout=2.5)
                except subprocess.TimeoutExpired:timed_out=True
                finally:
                    try:os.killpg(proc.pid,signal.SIGKILL)
                    except ProcessLookupError:pass
                    proc.wait()
                if proc.returncode == -signal.SIGXCPU:timed_out=True
                stdout.seek(0);out=stdout.read(20001);stderr.seek(0);err=stderr.read(4000)
                results.append({'index':index,'stdout':out.decode('utf-8','replace'),
                    'stderr':err.decode('utf-8','replace'),'exit_code':proc.returncode,
                    'timed_out':timed_out,'output_limit':len(out)>20000})
                if timed_out or proc.returncode!=0 or len(out)>20000:break
    print(payload['marker']+json.dumps({'nonce':payload['nonce'],'results':results},ensure_ascii=True))
