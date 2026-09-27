"""Reference-conditioned logo generation using the user's 30 uploaded team logos."""
import json,os
from pathlib import Path
from openai_client import request,multipart
ROOT=Path(__file__).resolve().parent

def logo_prompt(name):
    aliases=json.loads((ROOT/'assets/logo-references/teams.json').read_text())
    prompt=(ROOT/'logo_prompt.txt').read_text()
    return prompt.replace('{team_name}',name)+'\nREFERENCE LABELS (English = Korean pronunciation):\n'+'\n'.join(x['english']+' = '+x['korean'] for x in aliases)

def create_logos(name):
    files=[]
    for i in (1,2):
        p=ROOT/f'assets/logo-references/reference-sheet-{i}.jpg'
        files.append(('image[]',p.name,'image/jpeg',p.read_bytes()))
    data,content_type=multipart({'model':os.environ.get('OPENAI_IMAGE_MODEL','gpt-image-2.5-flare'),
        'prompt':logo_prompt(name),'n':3,'size':'1024x1024','quality':'low','output_format':'jpeg','output_compression':65},files)
    result=request('images/edits',raw=data,content_type=content_type,timeout=120)
    images=result.get('data',[])
    if len(images)!=3 or any(not x.get('b64_json') for x in images):raise ValueError('로고 후보 3개의 이미지 응답을 받지 못했습니다.')
    return ['data:image/jpeg;base64,'+x['b64_json'] for x in images]
