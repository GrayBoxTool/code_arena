"""Regenerate operator problem book and split question/answer/hint/test documents."""
from pathlib import Path
import json
from problems import PROBLEMS, public_problem, judge_inputs, expected_outputs, reference_code

ROOT=Path(__file__).resolve().parent/'docs'

def question(p):
    pub=public_problem(p)
    for field in ('statement','input','output','sample_explanation'):
        pub[field]=pub[field].replace('\n','  \n')
    sections=[f'# {p["id"]} · {p["title"]}',
              '## 문제 설명\n\n'+pub['statement'],
              '## 입력\n\n'+pub['input'],
              '### 테스트케이스 하나의 입력 형식\n\n```text\n'+pub['input_format']+'\n```\n\n위의 이름은 자리 표시자이며, `...`는 반복을 뜻합니다. 실제 입력에는 숫자·문자열만 들어 있습니다.',
              '## 제약조건\n\n'+'\n'.join('- '+line for line in pub['constraints'].splitlines()),
              '## 출력\n\n'+pub['output'],
              '```text\n'+pub['output_format']+'\n```',
              '## 예제 입력\n\n```text\n'+judge_inputs(p)[0].rstrip('\n')+'\n```',
              '## 예제 출력\n\n```text\n'+expected_outputs(p)[0].rstrip('\n')+'\n```',
              '## 예제 해설\n\n'+pub['sample_explanation'],
              '## 공백과 줄바꿈 안내\n\n코드 블록 안의 띄어쓰기는 실제 공백이며, 각 행은 실제 줄바꿈입니다. 게임 화면의 **공백·줄바꿈 표시 보기**에서는 공백을 `␠`, 줄바꿈을 `↵`로 확인할 수 있습니다. 이 표시 기호를 입력하거나 출력하지 마세요.']
    return '\n\n'.join(sections)+'\n'

def main():
    for name in ('questions','answers','hints','tests'):(ROOT/name).mkdir(parents=True,exist_ok=True)
    book=['# Code Rumble 문제집 · 운영자용\n\n럼블 25문제와 결승 A/B 각 5문제입니다. 정답 코드와 힌트가 포함되어 있으므로 참가자에게 공개하지 마세요.']
    all_cases=[]
    for p in PROBLEMS:
        q=question(p)
        answer=f'# {p["id"]} · 모범 풀이\n\n```python\n{reference_code(p).rstrip()}\n```\n'
        hints=f'# {p["id"]} · 힌트\n\n## 문제 유형 공개\n\n{p["hint1"]}\n\n## 핵심 구조 공개\n\n{p["hint2"]}\n'
        cases={'id':p['id'],'files':[{'public':i==0,'input':inp,'output':out} for i,(inp,out) in enumerate(zip(judge_inputs(p),expected_outputs(p)))]}
        for folder,text,suffix in (('questions',q,'.md'),('answers',answer,'.md'),('hints',hints,'.md'),('tests',json.dumps(cases,ensure_ascii=False,indent=2)+'\n','.json')):
            (ROOT/folder/(p['id']+suffix)).write_text(text,encoding='utf-8')
        book.extend([q,hints,answer]);all_cases.append(cases)
    (ROOT/'problem-book.md').write_text('\n\n---\n\n'.join(book),encoding='utf-8')
    (ROOT/'test-cases.json').write_text(json.dumps(all_cases,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(f'{len(PROBLEMS)} questions, answers, hint files and test bundles exported.')

if __name__=='__main__':main()
