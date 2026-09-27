"""Paid connectivity check, invoked explicitly by the administrator."""
import time
from openai_judge import judge_remote
from services import assist

CHECK_PROBLEM={'cases':['2 3\n','-2 7\n','0 0\n'],'solution':'a,b=map(int,input().split())\nprint(a+b)',
    'statement':'두 정수의 합을 출력하세요.','input':'첫 줄 T, 이후 각 줄 두 정수.'}

def run_checks(report):
    from problems import reference_code
    tests=[('정답 채점',reference_code(CHECK_PROBLEM),'정답'),('오답 채점','print("wrong")','오답'),
           ('실행 오류 채점','raise ValueError("API 연결 시험")','실행 오류')]
    for label,code,expected in tests:
        start=time.monotonic()
        try:
            verdict=judge_remote(code,CHECK_PROBLEM)[0];ok=verdict.startswith(expected)
            report({'name':label,'ok':ok,'seconds':round(time.monotonic()-start,1),'detail':verdict.splitlines()[0]})
        except Exception as e:
            report({'name':label,'ok':False,'seconds':round(time.monotonic()-start,1),'detail':str(e)[:400]})
            return # Stop costly repeats when the first connection is broken.
    start=time.monotonic()
    try:
        result=assist(CHECK_PROBLEM,'a,b=map(int,input().split())\nprint(a-b)')
        report({'name':'AI 조언','ok':True,'seconds':round(time.monotonic()-start,1),'detail':result})
    except Exception as e:report({'name':'AI 조언','ok':False,'seconds':round(time.monotonic()-start,1),'detail':str(e)[:400]})
