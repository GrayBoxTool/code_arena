REWARD = {1: 100, 2: 150, 3: 200, 4: 250, 5: 300}
HINT_COST = {"type": 50, "structure": 150, "assist": 300}


def reference_code(problem):
    """Make the case-level editorial solution use SWEA's T/#tc convention."""
    import textwrap
    return ("def solve_case():\n" + textwrap.indent(problem["solution"], "    ") +
            "\nT = int(input())\nfor tc in range(1, T + 1):\n" +
            ("    print(f'#{tc}')\n" if problem.get("output_mode")=="block" else "    print(f'#{tc} ', end='')\n") + "    solve_case()\n")


def judge_inputs(problem):
    """Several independent multi-case files; the first is public."""
    cases = problem["cases"]
    groups = [cases[:2]] + [cases[i:i+3] for i in range(2,len(cases),3)]
    if problem.get('case_label'):
        groups=[[str(i)+'\n'+case.split('\n',1)[1] for i,case in enumerate(group,1)] for group in groups]
    return [str(len(group)) + "\n" + "".join(group) for group in groups]


from functools import lru_cache
import builtins as _builtins
import io as _io

@lru_cache(maxsize=256)
def _reference_outputs(solution, inputs):
    result=[]
    for text in inputs:
        stdin, stdout = _io.StringIO(text), _io.StringIO()
        functions = vars(_builtins).copy()
        def read(prompt=''):
            line=stdin.readline()
            if line=='': raise EOFError('reference input exhausted')
            return line.rstrip('\n')
        def write(*args, **kwargs):
            kwargs['file']=stdout
            _builtins.print(*args, **kwargs)
        functions.update(input=read, print=write)
        exec(solution, {'__name__':'__main__','__builtins__':functions})
        result.append(stdout.getvalue())
    return tuple(result)

def expected_outputs(problem):
    return list(_reference_outputs(reference_code(problem), tuple(judge_inputs(problem))))


def public_problem(problem):
    fields=("id", "set", "level", "title", "statement", "input", "output",
            "constraints", "output_format")
    result={k:problem[k] for k in fields}
    result["figures"]=problem.get("figures",[])
    result["input"]=("전체 입력의 첫 줄에는 테스트케이스 수 T가 주어집니다. (1 ≤ T ≤ 3)\n"
                     "이후 아래 설명에 따라 테스트케이스가 T개 이어집니다. 테스트케이스 사이에 빈 줄은 없습니다.\n\n"
                     +result["input"]+"\n\n한 줄의 여러 값은 공백으로 구분됩니다. 문자열·지도 행의 공백 여부는 위 설명을 따르세요.")
    result["output"]=("각 테스트케이스마다 한 줄에 #과 테스트케이스 번호 tc를 붙여 출력하고, 공백 한 칸 뒤에 정답을 출력합니다.\n"
                      "tc는 1부터 시작합니다. 예: #1 10\n\n"+result["output"])
    if problem.get('output_mode')=='block':
        result['output']='각 테스트케이스의 첫 줄에 #과 번호를 붙여 출력합니다. 예: #1\n다음 줄부터 복원한 문자열을 10글자씩 줄을 바꾸어 출력합니다. 마지막 줄은 10글자보다 짧을 수 있습니다.\n\n'+problem['output']
    return result

from rumble_bank import build_rumble
from final_bank import build_final
PROBLEMS = build_rumble() + build_final()
import json
from pathlib import Path
_FIGURES=json.loads(Path(__file__).with_name("problem_figures.json").read_text(encoding="utf-8"))
for p in PROBLEMS:
    p["figures"]=_FIGURES.get(p["id"],[])
    p['output_format'] = '#tc\n결과 문자열을 10글자씩 출력' if p.get('output_mode')=='block' else '#tc answer'

def public_samples(p):
    """Only two abbreviated examples leave the server; never expose a full expansion."""
    def shorten(lines, limit):
        lines=[line if len(line)<=160 else line[:100]+' … (줄 일부 생략) … '+line[-30:] for line in lines]
        if len(lines)>limit:
            return lines[:limit-2]+['… (중간 줄 생략) …',lines[-1]]
        return lines
    cases=p['cases'][:2]
    if p.get('case_label'):
        cases=[str(i)+'\n'+case.split('\n',1)[1] for i,case in enumerate(cases,1)]
    inp=['2']
    out=[]
    limits=[len(case.rstrip('\n').splitlines()) for case in cases]
    while sum(limits)>9:
        idx=0 if limits[0]>=limits[1] else 1
        limits[idx]-=1
    for i,case in enumerate(cases,1):
        inp+=shorten(case.rstrip('\n').splitlines(),limits[i-1])
        value=_reference_outputs(reference_code(p),('1\n'+case,))[0].rstrip('\n')
        value=value.replace('#1',f'#{i}',1)
        out+=shorten(value.splitlines(),5)
    return {'sample_input':'\n'.join(inp),'sample_output':'\n'.join(out)}
