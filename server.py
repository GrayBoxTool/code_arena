"""Code Rumble server. OpenAI-hosted execution for public deployments; trusted local judge for localhost."""
import ast
from openai_judge import judge_submission, enabled as judge_enabled, provider as judge_provider, JudgeUnavailable
from logo_service import create_logos
from api_check import run_checks
import base64
import builtins
import hashlib
import hmac
import html
import io
import json
import keyword
import os
import random
import secrets
import sqlite3
import string
import sys
import threading
import time
import tokenize
import urllib.request
import urllib.error
from collections import Counter
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse, parse_qs
from problems import PROBLEMS, REWARD, HINT_COST, public_problem, judge_inputs, expected_outputs
from bank_v2 import relay_case
from services import judge, assist

ROOT=Path(__file__).resolve().parent
DATA=Path(os.environ.get('RUMBLE_DATA_DIR',str(ROOT/'data')))
DB=DATA/'rumble.sqlite3'
LOCK=threading.RLock()
API_CHECK={}
ROUND_SECONDS=300
FINAL_SECONDS=600
TEAM_NAMES=['블루','레드','골드','바이올렛','민트']
ROUNDS=[[(1,2),(3,4)],[(1,3),(2,5)],[(1,4),(3,5)],[(1,5),(2,4)],[(2,3),(4,5)]]
LOOKUP={p['id']:p for p in PROBLEMS}
FRONTEND_ORIGIN=os.environ.get('FRONTEND_ORIGIN','').strip().rstrip('/')
LOGO_JOBS={}
SUBMITTING=set()

@contextmanager
def db():
    c=sqlite3.connect(DB,timeout=15)
    c.row_factory=sqlite3.Row
    c.execute('PRAGMA foreign_keys=ON')
    try:
        yield c
        c.commit()
    except Exception:
        c.rollback(); raise
    finally: c.close()

def access_token(role,team_id=0,level=0):
    seed=os.environ.get('ACCESS_SEED')
    if not seed: return secrets.token_urlsafe(24)
    if len(seed)<32: raise ValueError('ACCESS_SEED는 32자 이상으로 설정하세요.')
    raw=hmac.new(seed.encode(),f'code-rumble:v1:{role}:{team_id}:{level}'.encode(),hashlib.sha256).digest()[:24]
    return base64.urlsafe_b64encode(raw).decode().rstrip('=')

def setting(c,key,default=''):
    row=c.execute('SELECT value FROM settings WHERE key=?',(key,)).fetchone()
    return row[0] if row else default

def setval(c,key,value):
    c.execute('INSERT OR REPLACE INTO settings VALUES (?,?)',(key,str(value)))

def current_round(c): return int(setting(c,'round','0'))
def epoch(c): return setting(c,'epoch','1')

def create_schedule(c):
    for r,pairs in enumerate(ROUNDS,1):
        for a,b in pairs:
            c.execute('INSERT INTO matches(round,team_a,team_b,problem_set) VALUES (?,?,?,?)',(r,a,b,r))

def setup():
    DATA.mkdir(parents=True,exist_ok=True)
    with db() as c:
        c.executescript('''
        CREATE TABLE IF NOT EXISTS teams(id INTEGER PRIMARY KEY,name TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY,name TEXT NOT NULL,team_id INTEGER,level INTEGER,
          token TEXT UNIQUE NOT NULL,role TEXT NOT NULL,profile_complete INTEGER NOT NULL DEFAULT 0);
        CREATE TABLE IF NOT EXISTS matches(id INTEGER PRIMARY KEY,round INTEGER NOT NULL,team_a INTEGER NOT NULL,
          team_b INTEGER NOT NULL,problem_set INTEGER NOT NULL,start_at REAL,end_at REAL,status TEXT NOT NULL DEFAULT 'pending');
        CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY,value TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS solves(id INTEGER PRIMARY KEY,match_id INTEGER NOT NULL,team_id INTEGER NOT NULL,
          user_id INTEGER NOT NULL,problem_id TEXT NOT NULL,at REAL NOT NULL,win_points INTEGER NOT NULL,
          solve_points INTEGER NOT NULL,UNIQUE(match_id,team_id,problem_id));
        CREATE TABLE IF NOT EXISTS submissions(id INTEGER PRIMARY KEY,match_id INTEGER NOT NULL,user_id INTEGER NOT NULL,
          problem_id TEXT NOT NULL,at REAL NOT NULL,verdict TEXT NOT NULL,passed INTEGER NOT NULL,total INTEGER NOT NULL);
        CREATE TABLE IF NOT EXISTS purchases(id INTEGER PRIMARY KEY,match_id INTEGER NOT NULL,team_id INTEGER NOT NULL,
          user_id INTEGER NOT NULL,problem_id TEXT NOT NULL,kind TEXT NOT NULL,detail TEXT NOT NULL,cost INTEGER NOT NULL,
          at REAL NOT NULL,UNIQUE(match_id,team_id,problem_id,kind));
        CREATE TABLE IF NOT EXISTS credits(id INTEGER PRIMARY KEY,team_id INTEGER NOT NULL,amount INTEGER NOT NULL,
          available_round INTEGER NOT NULL,reason TEXT NOT NULL,at REAL NOT NULL);
        CREATE TABLE IF NOT EXISTS round_preferences(round INTEGER NOT NULL,team_id INTEGER NOT NULL,user_id INTEGER NOT NULL,
          level INTEGER NOT NULL,PRIMARY KEY(round,user_id),UNIQUE(round,team_id,level));
        CREATE TABLE IF NOT EXISTS round_assignments(round INTEGER NOT NULL,team_id INTEGER NOT NULL,user_id INTEGER NOT NULL,
          level INTEGER NOT NULL,PRIMARY KEY(round,user_id),UNIQUE(round,team_id,level));
        CREATE TABLE IF NOT EXISTS round_ready(round INTEGER NOT NULL,user_id INTEGER NOT NULL,ready INTEGER NOT NULL DEFAULT 0,
          PRIMARY KEY(round,user_id));
        CREATE TABLE IF NOT EXISTS drafts(match_id INTEGER NOT NULL,user_id INTEGER NOT NULL,code TEXT NOT NULL DEFAULT '',
          rev INTEGER NOT NULL DEFAULT 0,updated_at REAL NOT NULL DEFAULT 0,freeze_until REAL NOT NULL DEFAULT 0,
          cooldown_until REAL NOT NULL DEFAULT 0,PRIMARY KEY(match_id,user_id));
        CREATE TABLE IF NOT EXISTS events(id INTEGER PRIMARY KEY AUTOINCREMENT,match_id INTEGER,team_id INTEGER,user_id INTEGER,
          kind TEXT NOT NULL,detail TEXT NOT NULL,at REAL NOT NULL);
        CREATE TABLE IF NOT EXISTS used_items(match_id INTEGER,user_id INTEGER,kind TEXT,at REAL,
          PRIMARY KEY(match_id,user_id));
        CREATE TABLE IF NOT EXISTS relays(match_id INTEGER,team_id INTEGER,input TEXT,output TEXT,level5_input TEXT,
          PRIMARY KEY(match_id,team_id));
        CREATE TABLE IF NOT EXISTS logo_candidates(team_id INTEGER NOT NULL,slot INTEGER NOT NULL,source TEXT NOT NULL,
          data_uri TEXT NOT NULL,PRIMARY KEY(team_id,slot));
        ''')
        def columns(table,defs):
            present={x[1] for x in c.execute(f'PRAGMA table_info({table})')}
            for name,definition in defs.items():
                if name not in present: c.execute(f'ALTER TABLE {table} ADD COLUMN {name} {definition}')
        columns('teams',{'captain_user_id':'INTEGER','logo_data':'TEXT','configured':'INTEGER NOT NULL DEFAULT 0','named':'INTEGER NOT NULL DEFAULT 0'})
        columns('users',{'profile_complete':'INTEGER NOT NULL DEFAULT 0','last_seen':'REAL NOT NULL DEFAULT 0'})
        columns('matches',{'winner':'INTEGER','bonus':'INTEGER NOT NULL DEFAULT 0','settled':'INTEGER NOT NULL DEFAULT 0','reason':'TEXT'})
        columns('submissions',{'code':"TEXT NOT NULL DEFAULT ''"})
        if not c.execute('SELECT 1 FROM users').fetchone():
            c.execute("INSERT INTO users(name,token,role,profile_complete) VALUES (?,?,?,1)",('운영자',access_token('admin'),'admin'))
            for tid,name in enumerate(TEAM_NAMES,1):
                c.execute('INSERT INTO teams(id,name) VALUES (?,?)',(tid,name))
                for level in range(1,6):
                    c.execute('INSERT INTO users(name,team_id,level,token,role) VALUES (?,?,?,?,?)',
                              (f'{name} {level}번',tid,level,access_token('player',tid,level),'player'))
            create_schedule(c); setval(c,'round',0)
        if not setting(c,'phase'):
            r=current_round(c)
            opened=c.execute("SELECT 1 FROM matches WHERE round=? AND status='open'",(r,)).fetchone()
            setval(c,'phase','live' if opened else 'results' if r else 'matching')
        if not setting(c,'epoch'): setval(c,'epoch',secrets.token_hex(8))
        c.execute("UPDATE matches SET problem_set=round WHERE status='pending' AND round<=5")
        for t in c.execute('SELECT id FROM teams WHERE captain_user_id IS NULL'):
            enrolled=list(c.execute('SELECT id FROM users WHERE team_id=? AND profile_complete=1 ORDER BY id',(t[0],)))
            if len(enrolled)==5: c.execute('UPDATE teams SET captain_user_id=? WHERE id=?',(enrolled[-1][0],t[0]))
        codes={'admin':c.execute("SELECT token FROM users WHERE role='admin'").fetchone()[0],'teams':{}}
        for tid,name in enumerate(TEAM_NAMES,1):
            codes['teams'][name]=[{'name':f'{name} {x["level"]}번','level':x['level'],'code':x['token']} for x in c.execute('SELECT * FROM users WHERE team_id=? ORDER BY level',(tid,))]
        (DATA/'access.json').write_text(json.dumps(codes,ensure_ascii=False,indent=2),encoding='utf-8')
        os.chmod(DATA/'access.json',0o600)

def balance(c,team):
    return c.execute('SELECT COALESCE(SUM(amount),0) FROM credits WHERE team_id=?',(team,)).fetchone()[0]

def points(c,mid,team):
    return c.execute('SELECT COALESCE(SUM(win_points),0) FROM solves WHERE match_id=? AND team_id=?',(mid,team)).fetchone()[0]

def standings(c):
    result=[]
    for t in c.execute('SELECT * FROM teams'):
        solved=c.execute('SELECT COALESCE(SUM(win_points),0),COUNT(*) FROM solves WHERE team_id=? AND match_id IN (SELECT id FROM matches WHERE round<=5)',(t['id'],)).fetchone()
        bonus=c.execute('SELECT COALESCE(SUM(bonus),0),COUNT(*) FROM matches WHERE round<=5 AND settled=1 AND winner=?',(t['id'],)).fetchone()
        result.append({'id':t['id'],'name':t['name'],'logo':t['logo_data'],'points':solved[0]+bonus[0],
                       'solved':solved[1],'wins':bonus[1],'credit':balance(c,t['id'])})
    return sorted(result,key=lambda x:(-x['points'],-x['wins'],-x['solved'],x['id']))

def event(c,m,team,user,kind,detail):
    c.execute('INSERT INTO events(match_id,team_id,user_id,kind,detail,at) VALUES (?,?,?,?,?,?)',(m,team,user,kind,detail,time.time()))

def close_match(c,m,winner=None,reason='time'):
    if m['settled']: return
    if m['round']<=5:
        a,b=points(c,m['id'],m['team_a']),points(c,m['id'],m['team_b'])
        winner=m['team_a'] if a>b else m['team_b'] if b>a else None
    bonus=100 if m['round']<=5 and winner else 0
    c.execute("UPDATE matches SET status='closed',end_at=MIN(COALESCE(end_at,?),?),winner=?,bonus=?,settled=1,reason=? WHERE id=?",
              (time.time(),time.time(),winner,bonus,reason,m['id']))
    event(c,m['id'],winner,None,'result','승리 팀 확정' if winner else '무승부')

def tick(c):
    if setting(c,'phase')!='live': return
    r=current_round(c)
    for m in list(c.execute("SELECT * FROM matches WHERE round=? AND status='open' AND end_at<=?",(r,time.time()))):
        close_match(c,m)
    if not c.execute("SELECT 1 FROM matches WHERE round=? AND status='open'",(r,)).fetchone():
        setval(c,'phase','finished' if r==6 else 'results')

def match_for(c,team,r):
    return c.execute('SELECT * FROM matches WHERE round=? AND (team_a=? OR team_b=?)',(r,team,team)).fetchone()

def target_round(c): return current_round(c)+1 if setting(c,'phase')=='matching' else current_round(c)

def ranking_key(team):
    return team['points']

def final_tie(c):
    """A tied cumulative match score at the final cutoff needs an explicit decision."""
    ranked=standings(c)
    if len(ranked)<3: return {'required':False,'candidates':[],'chosen':None}
    cutoff=ranking_key(ranked[1])
    required=ranking_key(ranked[0])==cutoff or ranking_key(ranked[2])==cutoff
    candidates=[{'id':t['id'],'name':t['name'],'points':t['points'],'wins':t['wins'],'solved':t['solved']}
                for t in ranked if ranking_key(t)>=cutoff] if required else []
    a,b=setting(c,'final_a'),setting(c,'final_b')
    chosen=[int(a),int(b)] if a and b else None
    return {'required':required,'candidates':candidates,'chosen':chosen,
            'locked_first':ranked[0]['id'] if ranking_key(ranked[0])>cutoff else None}

def ensure_final(c):
    if current_round(c)==5 and not c.execute('SELECT 1 FROM matches WHERE round=6').fetchone():
        tie=final_tie(c)
        if tie['required'] and not tie['chosen']:
            raise ValueError('동점 팀이 있습니다. 운영자가 결승 진출 두 팀을 먼저 선택하세요.')
        top=tie['chosen'] if tie['required'] else [t['id'] for t in standings(c)[:2]]
        c.execute('INSERT INTO matches(round,team_a,team_b,problem_set) VALUES (6,?,?,6)',(*top,))

def rehearsal(c): return setting(c,'rehearsal','0')=='1'

def simulate_result(c,match_id,team_id,level,verdict):
    if not rehearsal(c) or setting(c,'phase')!='live': raise ValueError('진행 중인 리허설 경기에서만 사용할 수 있습니다.')
    m=c.execute("SELECT * FROM matches WHERE id=? AND round=? AND status='open'",(match_id,current_round(c))).fetchone()
    if not m or team_id not in (m['team_a'],m['team_b']) or type(level) is not int or level not in range(1,6):
        raise ValueError('경기·팀·레벨을 확인하세요.')
    if verdict not in ('correct','wrong'):raise ValueError('리허설 판정 종류를 확인하세요.')
    row=c.execute('SELECT u.* FROM users u JOIN round_assignments a ON a.user_id=u.id WHERE a.round=? AND a.team_id=? AND a.level=?',(m['round'],team_id,level)).fetchone()
    if not row:raise ValueError('담당 선수가 배정되지 않았습니다.')
    uid=row['id']; p=problem_for(m,team_id,level)
    if (epoch(c),m['id'],uid) in SUBMITTING:raise ValueError('해당 선수의 실제 채점이 진행 중입니다.')
    if c.execute('SELECT 1 FROM solves WHERE match_id=? AND user_id=?',(m['id'],uid)).fetchone():raise ValueError('이미 정답 처리한 선수입니다.')
    now=time.time()
    if verdict=='wrong':
        c.execute('INSERT INTO submissions(match_id,user_id,problem_id,at,verdict,passed,total,code) VALUES (?,?,?,?,?,?,?,?)',
                  (m['id'],uid,p['id'],now,'오답',0,len(judge_inputs(p)),'# 운영자 리허설 오답 · 실제 제출 코드 아님'))
        c.execute('UPDATE drafts SET cooldown_until=? WHERE match_id=? AND user_id=?',(now+10,m['id'],uid))
        event(c,m['id'],team_id,uid,'wrong',f'리허설 Lv{level} 오답')
    else:
        prior=c.execute('SELECT 1 FROM solves WHERE match_id=? AND problem_id=?',(m['id'],p['id'])).fetchone()
        score=REWARD[level]//2 if prior and m['round']<=5 else REWARD[level]
        c.execute('INSERT INTO submissions(match_id,user_id,problem_id,at,verdict,passed,total,code) VALUES (?,?,?,?,?,?,?,?)',
                  (m['id'],uid,p['id'],now,'정답',len(judge_inputs(p)),len(judge_inputs(p)),'# 운영자 리허설 정답 · 실제 제출 코드 아님'))
        c.execute('INSERT INTO solves(match_id,team_id,user_id,problem_id,at,win_points,solve_points) VALUES (?,?,?,?,?,?,?)',
                  (m['id'],team_id,uid,p['id'],now,score,REWARD[level]))
        c.execute('INSERT INTO credits(team_id,amount,available_round,reason,at) VALUES (?,?,?,?,?)',
                  (team_id,REWARD[level],m['round'],'리허설 '+p['id'],now))
        event(c,m['id'],team_id,uid,'solve',f'리허설 Lv{level} 정답 · +{score} 승점')
        if m['round']==6 and level==5:close_match(c,m,team_id,'level5');tick(c)

def problem_for(m,team,level):
    if m['round']==6: return LOOKUP[f'F{"A" if team==m["team_a"] else "B"}-L{level}']
    return LOOKUP[f'S{m["problem_set"]}-L{level}']

def assignment(c,m,user):
    row=c.execute('SELECT level FROM round_assignments WHERE round=? AND user_id=?',(m['round'],user)).fetchone()
    return row[0] if row else None

def draft(c,mid,uid):
    c.execute('INSERT OR IGNORE INTO drafts(match_id,user_id) VALUES (?,?)',(mid,uid))
    return c.execute('SELECT * FROM drafts WHERE match_id=? AND user_id=?',(mid,uid)).fetchone()

def public(p):
    return public_problem(p)|{'reward':REWARD[p['level']], 'sample_input':judge_inputs(p)[0], 'sample_output':expected_outputs(p)[0]}

def relay_problem(c,m,team,level):
    p=dict(problem_for(m,team,level))
    if m['round']==6 and level in (4,5):
        r=c.execute('SELECT * FROM relays WHERE match_id=? AND team_id=?',(m['id'],team)).fetchone()
        p['cases']=p['cases']+[r['input'] if level==4 else r['level5_input']]
    return p

def match_view(c,m,admin=False):
    teams=[]
    for tid in (m['team_a'],m['team_b']):
        t=c.execute('SELECT * FROM teams WHERE id=?',(tid,)).fetchone()
        members=[]
        for u in c.execute('SELECT * FROM users WHERE team_id=? ORDER BY id',(tid,)):
            row=c.execute('SELECT level FROM round_assignments WHERE round=? AND user_id=?',(m['round'],u['id'])).fetchone()
            if not row: row=c.execute('SELECT level FROM round_preferences WHERE round=? AND user_id=?',(m['round'],u['id'])).fetchone()
            ready=c.execute('SELECT ready FROM round_ready WHERE round=? AND user_id=?',(m['round'],u['id'])).fetchone()
            s=c.execute('SELECT * FROM solves WHERE match_id=? AND user_id=?',(m['id'],u['id'])).fetchone()
            last=c.execute('SELECT verdict,at FROM submissions WHERE match_id=? AND user_id=? ORDER BY id DESC LIMIT 1',(m['id'],u['id'])).fetchone()
            d=c.execute('SELECT * FROM drafts WHERE match_id=? AND user_id=?',(m['id'],u['id'])).fetchone()
            member={'id':u['id'],'name':u['name'] if u['profile_complete'] else f'{t["name"]} Lv{u["level"]} (리허설)' if rehearsal(c) else '참가 전','level':row[0] if row else None,
                    'ready':bool((ready and ready[0]) or rehearsal(c)),'enrolled':bool(u['profile_complete'] or rehearsal(c)),'online':time.time()-u['last_seen']<10,
                    'captain':u['id']==t['captain_user_id'],'win_points':s['win_points'] if s else 0,
                    'solved':bool(s),'verdict':last['verdict'].splitlines()[0] if last else '',
                    'purchases':[dict(h) for h in c.execute('SELECT kind,cost,at FROM purchases WHERE match_id=? AND user_id=?',(m['id'],u['id']))],
                    'item_used':bool(c.execute('SELECT 1 FROM used_items WHERE match_id=? AND user_id=?',(m['id'],u['id'])).fetchone()),
                    'freeze_until':d['freeze_until'] if d else 0,'cooldown_until':d['cooldown_until'] if d else 0}
            if admin: member['draft']=d['code'] if d else ''; member['updated_at']=d['updated_at'] if d else 0
            members.append(member)
        teams.append({'id':tid,'name':t['name'],'logo':f'/api/logo/{tid}' if t['logo_data'] else None,
                      'configured':bool(t['configured']),'members':members,'points':points(c,m['id'],tid),
                      'bonus':m['bonus'] if m['winner']==tid else 0,'credit':balance(c,tid)})
    return dict(m)|{'teams':teams,'scores':{str(t['id']):t['points'] for t in teams}}

def upcoming_pairs(c,phase,round_no):
    if phase not in ('live','results') or round_no>=6:return None
    nxt=round_no+1
    if nxt==6:
        tie=final_tie(c)
        if tie['required'] and not tie['chosen']:return {'round':6,'pairs':[],'pending_tie':True,'tentative':False}
        selected=tie['chosen'] if tie['required'] else [t['id'] for t in standings(c)[:2]]
        pairs=[selected];tentative=phase=='live'
    else:
        pairs=[(m['team_a'],m['team_b']) for m in c.execute('SELECT * FROM matches WHERE round=? ORDER BY id',(nxt,))]
        tentative=False
    return {'round':nxt,'pairs':[[{'id':tid,'name':t['name'],'logo':f'/api/logo/{tid}' if t['logo_data'] else None}
                   for tid in pair for t in [c.execute('SELECT * FROM teams WHERE id=?',(tid,)).fetchone()]] for pair in pairs],
            'pending_tie':False,'tentative':tentative}

def snapshot(c,user):
    tick(c); r=current_round(c); phase=setting(c,'phase'); target=target_round(c)
    if phase=='matching' and target==6: ensure_final(c)
    matches=[match_view(c,m,user['role']=='admin') for m in c.execute('SELECT * FROM matches WHERE round=? ORDER BY id',(target,))]
    t=c.execute('SELECT * FROM teams WHERE id=?',(user['team_id'],)).fetchone()
    completed=c.execute('SELECT COUNT(*) FROM users WHERE team_id=? AND profile_complete=1',(user['team_id'],)).fetchone()[0]
    m=match_for(c,user['team_id'],r) if user['role']=='player' and r else None
    level=assignment(c,m,user['id']) if m else None
    own_draft=dict(draft(c,m['id'],user['id'])) if m and level else None
    p=public(problem_for(m,user['team_id'],level)) if m and level else None
    hints=[dict(h) for h in c.execute('SELECT problem_id,kind,detail,cost FROM purchases WHERE match_id=? AND user_id=?',(m['id'],user['id']))] if m else []
    solved=c.execute('SELECT * FROM solves WHERE match_id=? AND user_id=?',(m['id'],user['id'])).fetchone() if m else None
    last=c.execute('SELECT verdict,passed,total,at FROM submissions WHERE match_id=? AND user_id=? ORDER BY id DESC LIMIT 1',(m['id'],user['id'])).fetchone() if m else None
    relay=None
    if m and m['round']==6 and c.execute("SELECT 1 FROM solves WHERE match_id=? AND team_id=? AND problem_id LIKE '%-L4'",(m['id'],user['team_id'])).fetchone():
        rr=c.execute('SELECT output,level5_input FROM relays WHERE match_id=? AND team_id=?',(m['id'],user['team_id'])).fetchone()
        relay=dict(rr) if rr else None
    ev=[dict(e) for e in c.execute('SELECT * FROM events ORDER BY id DESC LIMIT 40')]
    if user['role']!='admin':
        ev=[e for e in ev if m and e['match_id']==m['id']]
    return {'epoch':epoch(c),'server_time':time.time(),'phase':phase,'round':r,'target_round':target,
            'api_check':dict(API_CHECK) if user['role']=='admin' else None,
            'rehearsal':rehearsal(c),'tie':final_tie(c) if user['role']=='admin' and r==5 and phase=='results' else None,
            'upcoming':upcoming_pairs(c,phase,r) if user['role']=='admin' else None,
            'completed_matches':[match_view(c,x) for x in c.execute("SELECT * FROM matches WHERE status='closed' ORDER BY round DESC,id")] if user['role']=='admin' else None,
            'duration':600 if target==6 else 300,'matches':matches,'standings':standings(c),'costs':HINT_COST,'rewards':REWARD,
            'me':{'id':user['id'],'name':user['name'],'role':user['role'],'team_id':user['team_id'],'level':level,
                  'profile_complete':bool(user['profile_complete']),'is_captain':bool(t and t['captain_user_id']==user['id']),
                  'captain_available':bool(t and not t['captain_user_id']),'force_captain':bool(t and not t['captain_user_id'] and completed==4)},
            'team_setup':({'name':t['name'],'named':bool(t['named']),'complete':bool(t['configured']),
               'candidates':[dict(x) for x in c.execute('SELECT slot,source FROM logo_candidates WHERE team_id=? ORDER BY slot',(t['id'],))],
               'job':LOGO_JOBS.get(t['id'],{} )} if t else None),
            'match':match_view(c,m) if m else None,'problem':p,'draft':own_draft,'solved':dict(solved) if solved else None,
            'last_submission':dict(last) if last else None,'hints':hints,'relay':relay,'events':list(reversed(ev)),
            'assist_enabled':bool(os.environ.get('OPENAI_API_KEY')),
            'judge_enabled':judge_enabled(),'judge_provider':judge_provider(),
            'item_available':bool(m and m['round']==6 and level in (1,2,3) and solved and not c.execute('SELECT 1 FROM used_items WHERE match_id=? AND user_id=?',(m['id'],user['id'])).fetchone())}

def active_player(c,u):
    if u['role']!='player': raise PermissionError('선수 계정으로 접속하세요.')
    m=match_for(c,u['team_id'],current_round(c))
    if setting(c,'phase')!='live' or not m or m['status']!='open' or time.time()>=m['end_at']: raise ValueError('현재 진행 중인 내 경기가 없습니다.')
    level=assignment(c,m,u['id'])
    if not level: raise ValueError('담당 레벨이 없습니다.')
    return m,level,draft(c,m['id'],u['id'])

def check_epoch(c,b):
    if b.get('epoch')!=epoch(c): raise ValueError('대회가 초기화되었습니다. 화면을 새로고침하세요.')

def check_freeze(d):
    if d['freeze_until']>time.time(): raise ValueError('빙결 효과 중에는 코드 수정·제출을 할 수 없습니다.')

def rename_variable(code):
    tokens=[]
    try:
        for tok in tokenize.generate_tokens(io.StringIO(code).readline): tokens.append(tok)
    except (tokenize.TokenError,IndentationError,SyntaxError): pass
    assigned=set(); tree=None
    try:
        tree=ast.parse(code)
        assigned={n.id for n in ast.walk(tree) if isinstance(n,ast.Name) and isinstance(n.ctx,ast.Store)}
        assigned|={n.arg for n in ast.walk(tree) if isinstance(n,ast.arg)}
    except SyntaxError: pass
    lines=code.splitlines(keepends=True); offsets=[0]
    for line in lines: offsets.append(offsets[-1]+len(line))
    occurrences=[]
    if tree is not None:
        # AST positions include expressions inside f-strings; columns are UTF-8 byte offsets.
        for node in ast.walk(tree):
            name=node.id if isinstance(node,ast.Name) else node.arg if isinstance(node,ast.arg) else None
            if name not in assigned: continue
            col=len(lines[node.lineno-1].encode()[:node.col_offset].decode())
            start=offsets[node.lineno-1]+col
            occurrences.append((name,start,start+len(name)))
    else:
        filtered=[t for t in tokens if t.type not in (tokenize.ENCODING,tokenize.COMMENT,tokenize.NL,tokenize.NEWLINE,tokenize.INDENT,tokenize.DEDENT)]
        for i,t in enumerate(filtered):
            if t.type!=tokenize.NAME or keyword.iskeyword(t.string) or t.string in dir(builtins): continue
            if i and filtered[i-1].string=='.': continue
            if i+1<len(filtered) and filtered[i+1].string=='(': continue
            occurrences.append((t.string,offsets[t.start[0]-1]+t.start[1],offsets[t.end[0]-1]+t.end[1]))
    if not occurrences: return code,'변수 없음'
    counts=Counter(n for n,_,_ in occurrences); target=sorted(counts,key=lambda x:(-counts[x],x))[0]
    replacement=''.join(secrets.choice(string.ascii_letters) for _ in range(10))
    while replacement in code: replacement=''.join(secrets.choice(string.ascii_letters) for _ in range(10))
    for a,b in sorted({(a,b) for n,a,b in occurrences if n==target},reverse=True): code=code[:a]+replacement+code[b:]
    return code,f'{target} → {replacement}'

def erase_last_line(code):
    lines=code.splitlines(keepends=True)
    for i in range(len(lines)-1,-1,-1):
        if lines[i].strip(): del lines[i]; break
    return ''.join(lines)

def start_round(c):
    if setting(c,'phase')!='matching': raise ValueError('대진·준비 확인 단계에서 시작하세요.')
    target=target_round(c)
    matches=list(c.execute('SELECT * FROM matches WHERE round=?',(target,)))
    if not matches: raise ValueError('시작할 대진이 없습니다.')
    for m in matches:
        for tid in (m['team_a'],m['team_b']):
            t=c.execute('SELECT * FROM teams WHERE id=?',(tid,)).fetchone()
            if not rehearsal(c) and not t['configured']: raise ValueError(f'{t["name"]} 팀명·로고 설정을 완료하세요.')
            players=list(c.execute('SELECT * FROM users WHERE team_id=?',(tid,)))
            if len(players)!=5 or (not rehearsal(c) and any(not p['profile_complete'] or not c.execute('SELECT 1 FROM round_ready WHERE round=? AND user_id=? AND ready=1',(target,p['id'])).fetchone() for p in players)):
                raise ValueError(f'{t["name"]} 팀원 5명의 준비 완료가 필요합니다.')
            picked=[(x['user_id'],x['level']) for x in c.execute('SELECT * FROM round_preferences WHERE round=? AND team_id=?',(target,tid))]
            remain=[p['id'] for p in players if p['id'] not in {x[0] for x in picked}]; secrets.SystemRandom().shuffle(remain)
            levels=[l for l in range(1,6) if l not in {x[1] for x in picked}]
            for uid,l in picked+list(zip(remain,levels)):
                c.execute('INSERT INTO round_assignments VALUES (?,?,?,?)',(target,tid,uid,l)); draft(c,m['id'],uid)
            if target==6:
                side=6 if tid==m['team_a'] else 7
                case=relay_case(side,12,random.Random(secrets.randbits(64)))
                p=dict(problem_for(m,tid,4)); p['cases']=[case]
                out=expected_outputs(p)[0].strip().split(' ',1)[1]
                values=out.split(); relay_in=f'{len(values)} 4\n'+out+'\n'
                c.execute('INSERT INTO relays VALUES (?,?,?,?,?)',(m['id'],tid,case,out,relay_in))
    now=time.time()
    c.execute("UPDATE matches SET start_at=?,end_at=?,status='open' WHERE round=?",(now,now+(600 if target==6 else 300),target))
    setval(c,'round',target); setval(c,'phase','live')

def reset_all(c):
    for table in ('solves','submissions','purchases','credits','round_preferences','round_assignments','round_ready','drafts','events','used_items','relays','logo_candidates','matches'):
        c.execute(f'DELETE FROM {table}')
    c.execute("UPDATE users SET profile_complete=0,last_seen=0 WHERE role='player'")
    for tid,name in enumerate(TEAM_NAMES,1):
        c.execute('UPDATE teams SET name=?,captain_user_id=NULL,logo_data=NULL,configured=0,named=0 WHERE id=?',(name,tid))
        for u in list(c.execute('SELECT id,level FROM users WHERE team_id=?',(tid,))):
            c.execute('UPDATE users SET name=? WHERE id=?',(f'{name} {u["level"]}번',u['id']))
    create_schedule(c); setval(c,'rehearsal',0);setval(c,'final_a','');setval(c,'final_b',''); setval(c,'round',0); setval(c,'phase','matching'); setval(c,'epoch',secrets.token_hex(8)); LOGO_JOBS.clear()


def placeholders(name):
    result=[]
    for color in ('#58dfe0','#eebc63','#dd88fe'):
        svg=f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 128 128"><path d="M64 7 115 30 102 95 64 121 26 95 13 30Z" fill="#15213b" stroke="{color}" stroke-width="5"/><text x="64" y="78" text-anchor="middle" font-family="sans-serif" font-size="34" font-weight="bold" fill="{color}">{html.escape(name[:2])}</text></svg>'
        result.append('data:image/svg+xml;base64,'+base64.b64encode(svg.encode()).decode())
    return result

def logo_worker(tid,name,generation,ep):
    try:
        images=create_logos(name)
        with LOCK,db() as c:
            t=c.execute('SELECT * FROM teams WHERE id=?',(tid,)).fetchone()
            if epoch(c)!=ep or LOGO_JOBS.get(tid,{}).get('id')!=generation or not t or t['configured'] or t['name']!=name: return
            for slot,img in enumerate(images,1):
                c.execute('INSERT OR REPLACE INTO logo_candidates VALUES (?,?,?,?)',(tid,slot,'AI 생성',img))
            LOGO_JOBS[tid]={'id':generation,'status':'done','started':LOGO_JOBS[tid]['started']}
    except Exception as exc:
        with LOCK:
            if LOGO_JOBS.get(tid,{}).get('id')==generation:
                LOGO_JOBS[tid]['status']='failed'
                LOGO_JOBS[tid]['error']='API 생성 실패: '+str(exc)[:250]+' 임시 후보를 선택할 수 있습니다.'

class Handler(BaseHTTPRequestHandler):
    def log_message(self,*args): pass
    def cors(self):
        if FRONTEND_ORIGIN and self.headers.get('Origin')==FRONTEND_ORIGIN:
            self.send_header('Access-Control-Allow-Origin',FRONTEND_ORIGIN)
            self.send_header('Vary','Origin')
            self.send_header('Access-Control-Allow-Headers','Authorization,Content-Type')
            self.send_header('Access-Control-Allow-Methods','GET,POST,OPTIONS')
    def send(self,obj,status=200):
        data=json.dumps(obj,ensure_ascii=False).encode(); self.send_response(status)
        self.send_header('Content-Type','application/json; charset=utf-8'); self.send_header('Content-Length',str(len(data)))
        self.send_header('Cache-Control','no-store'); self.cors(); self.end_headers(); self.wfile.write(data)
    def user(self,c):
        token=self.headers.get('Authorization','').removeprefix('Bearer ')
        u=c.execute('SELECT * FROM users WHERE token=?',(token,)).fetchone()
        if not u: raise PermissionError('참가 코드를 확인하세요.')
        return u
    def do_OPTIONS(self):
        if not FRONTEND_ORIGIN or self.headers.get('Origin')!=FRONTEND_ORIGIN: return self.send({'error':'허용되지 않은 출처'},403)
        self.send_response(204); self.cors(); self.end_headers()
    def do_GET(self):
        parsed=urlparse(self.path); path=parsed.path
        try:
            if path.startswith('/api/logo/'):
                tid=int(path.rsplit('/',1)[1]); slot=parse_qs(parsed.query).get('slot',[None])[0]
                with db() as c:
                    row=c.execute('SELECT data_uri FROM logo_candidates WHERE team_id=? AND slot=?',(tid,int(slot))).fetchone() if slot else c.execute('SELECT logo_data FROM teams WHERE id=?',(tid,)).fetchone()
                    if not row or not row[0]: return self.send({'error':'로고 없음'},404)
                    header,data=row[0].split(',',1); binary=base64.b64decode(data)
                self.send_response(200); self.send_header('Content-Type',header[5:].split(';')[0]); self.send_header('Content-Length',str(len(binary))); self.send_header('Cache-Control','no-store'); self.cors(); self.end_headers(); self.wfile.write(binary); return
            if path in ('/api/state','/api/inspect'):
                with LOCK,db() as c:
                    u=self.user(c); tick(c); c.execute('UPDATE users SET last_seen=? WHERE id=?',(time.time(),u['id']))
                    if path=='/api/state': result=snapshot(c,u)
                    else:
                        if u['role']!='admin': raise PermissionError('운영자만 볼 수 있습니다.')
                        uid=int(parse_qs(parsed.query).get('user_id',['0'])[0]); player=c.execute("SELECT * FROM users WHERE id=? AND role='player'",(uid,)).fetchone()
                        m=match_for(c,player['team_id'],current_round(c)) if player else None
                        l=assignment(c,m,uid) if m else None
                        if not l: raise ValueError('진행한 경기의 담당 문제가 없습니다.')
                        accepted=c.execute("SELECT code FROM submissions WHERE match_id=? AND user_id=? AND verdict='정답' ORDER BY id LIMIT 1",(m['id'],uid)).fetchone()
                        last=c.execute('SELECT code,verdict FROM submissions WHERE match_id=? AND user_id=? ORDER BY id DESC LIMIT 1',(m['id'],uid)).fetchone()
                        result={'name':player['name'],'problem':public(problem_for(m,player['team_id'],l)),
                                'draft':dict(draft(c,m['id'],uid)),'accepted_code':accepted[0] if accepted else None,'last':dict(last) if last else None}
                return self.send(result)
            target=ROOT/'static'/('index.html' if path=='/' else path.lstrip('/'))
            if target.parent!=ROOT/'static' or target.suffix not in ('.html','.css','.js','.svg') or not target.exists(): return self.send({'error':'찾을 수 없습니다.'},404)
            data=target.read_bytes(); self.send_response(200); self.send_header('Content-Type',{'.html':'text/html','.js':'text/javascript','.css':'text/css','.svg':'image/svg+xml'}[target.suffix]+'; charset=utf-8'); self.send_header('Content-Length',str(len(data))); self.send_header('Cache-Control','no-store'); self.end_headers(); self.wfile.write(data)
        except PermissionError as e: self.send({'error':str(e)},401)
        except (ValueError,TypeError) as e: self.send({'error':str(e)},400)
        except Exception as e:
            print(repr(e),file=sys.stderr); self.send({'error':'서버 처리 중 오류'},500)
    def do_POST(self):
        try:
            n=int(self.headers.get('Content-Length',0))
            if not 0<n<100000: raise ValueError('요청 크기가 잘못되었습니다.')
            b=json.loads(self.rfile.read(n)); path=urlparse(self.path).path
            if not isinstance(b,dict): raise ValueError('JSON 객체가 필요합니다.')
            if path=='/api/submit': return self.submit_code(b)
            if path=='/api/hint' and b.get('kind')=='assist': return self.ai_hint(b)
            with LOCK,db() as c:
                u=self.user(c); tick(c)
                if path.startswith('/api/admin/'):
                    if u['role']!='admin': raise PermissionError('운영자만 사용할 수 있습니다.')
                    check_epoch(c,b)
                    if path=='/api/admin/api-check':
                        if setting(c,'phase')=='live': raise ValueError('연결 시험은 경기 시작 전에 실행하세요.')
                        if API_CHECK.get('status')=='running': raise ValueError('연결 시험이 이미 진행 중입니다.')
                        if judge_provider()!='openai' or not judge_enabled(): raise ValueError('JUDGE_PROVIDER=openai 및 OPENAI_API_KEY를 설정하세요.')
                        API_CHECK.clear(); API_CHECK.update(status='running',results=[],started=time.time())
                        threading.Thread(target=api_check_worker,daemon=True).start()
                    elif path=='/api/admin/rehearsal':
                        if current_round(c)!=0 or setting(c,'phase')!='matching':raise ValueError('리허설 모드는 첫 라운드 시작 전에만 설정할 수 있습니다. 진행 기록 초기화가 필요합니다.')
                        if type(b.get('enabled')) is not bool:raise ValueError('리허설 설정 오류')
                        setval(c,'rehearsal',int(b['enabled']))
                    elif path=='/api/admin/simulate':
                        simulate_result(c,b.get('match_id'),b.get('team_id'),b.get('level'),b.get('verdict'))
                    elif path=='/api/admin/finalists':
                        if current_round(c)!=5 or setting(c,'phase')!='results':raise ValueError('럼블 5라운드 결과 확인 단계에서만 지정할 수 있습니다.')
                        tie=final_tie(c)
                        if not tie['required']:raise ValueError('결승 진출 경계에 동점이 없습니다.')
                        a,other=b.get('team_a'),b.get('team_b')
                        if type(a) is not int or type(other) is not int or a==other:raise ValueError('서로 다른 두 팀을 선택하세요.')
                        eligible={x['id'] for x in tie['candidates']}
                        if a not in eligible or other not in eligible or (tie['locked_first'] and tie['locked_first'] not in (a,other)):
                            raise ValueError('상위 확정 팀과 동점 후보 안에서 두 팀을 선택하세요.')
                        setval(c,'final_a',a);setval(c,'final_b',other)
                    elif path=='/api/admin/start': start_round(c)
                    elif path=='/api/admin/close':
                        if setting(c,'phase')!='live': raise ValueError('진행 중인 라운드가 없습니다.')
                        for m in list(c.execute("SELECT * FROM matches WHERE round=? AND status='open'",(current_round(c),))): close_match(c,m,reason='admin')
                        tick(c)
                    elif path=='/api/admin/next':
                        if setting(c,'phase')!='results' or current_round(c)>=6: raise ValueError('결과 확인 단계에서 다음 대진을 열어주세요.')
                        if current_round(c)==5: ensure_final(c)
                        setval(c,'phase','matching')
                    elif path=='/api/admin/reset':
                        if b.get('confirmation')!='전체 초기화': raise ValueError('전체 초기화를 정확히 입력하세요.')
                        reset_all(c)
                    else: raise ValueError('지원하지 않는 운영 명령입니다.')
                elif path=='/api/profile':
                    if u['role']!='player' or u['profile_complete']: raise ValueError('이미 이름을 설정했습니다.')
                    name=valid_name(b.get('name'),20)
                    if c.execute('SELECT 1 FROM users WHERE team_id=? AND name=? AND id!=?',(u['team_id'],name,u['id'])).fetchone(): raise ValueError('팀 안에 같은 이름이 있습니다.')
                    t=c.execute('SELECT * FROM teams WHERE id=?',(u['team_id'],)).fetchone()
                    count=c.execute('SELECT COUNT(*) FROM users WHERE team_id=? AND profile_complete=1',(u['team_id'],)).fetchone()[0]
                    if b.get('captain') and t['captain_user_id']: raise ValueError('이미 팀장이 정해졌습니다.')
                    if not t['captain_user_id'] and (b.get('captain') or count==4): c.execute('UPDATE teams SET captain_user_id=? WHERE id=?',(u['id'],u['team_id']))
                    c.execute('UPDATE users SET name=?,profile_complete=1 WHERE id=?',(name,u['id']))
                elif path.startswith('/api/team/'):
                    t=c.execute('SELECT * FROM teams WHERE id=?',(u['team_id'],)).fetchone()
                    if not t or t['captain_user_id']!=u['id'] or t['configured']: raise PermissionError('팀 설정 중인 팀장만 사용할 수 있습니다.')
                    if path=='/api/team/name':
                        name=valid_name(b.get('name'),24)
                        if c.execute('SELECT 1 FROM teams WHERE id!=? AND name=?',(t['id'],name)).fetchone(): raise ValueError('다른 팀이 사용하는 팀명입니다.')
                        if t['name']!=name:
                            c.execute('DELETE FROM logo_candidates WHERE team_id=?',(t['id'],)); LOGO_JOBS.pop(t['id'],None)
                        c.execute('UPDATE teams SET name=?,named=1 WHERE id=?',(name,t['id']))
                    elif path=='/api/team/logos':
                        if not t['named']: raise ValueError('먼저 팀명을 저장하세요.')
                        if not c.execute('SELECT 1 FROM logo_candidates WHERE team_id=?',(t['id'],)).fetchone():
                            for slot,image in enumerate(placeholders(t['name']),1): c.execute('INSERT INTO logo_candidates VALUES (?,?,?,?)',(t['id'],slot,'임시 로고',image))
                        if os.environ.get('OPENAI_API_KEY') and t['id'] not in LOGO_JOBS:
                            gen=secrets.token_hex(8); ep=epoch(c)
                            LOGO_JOBS[t['id']]={'id':gen,'status':'running','started':time.time()}
                            threading.Thread(target=logo_worker,args=(t['id'],t['name'],gen,ep),daemon=True).start()
                    elif path=='/api/team/choose-logo':
                        row=c.execute('SELECT data_uri FROM logo_candidates WHERE team_id=? AND slot=?',(t['id'],b.get('slot'))).fetchone()
                        if not row: raise ValueError('로고 후보를 선택하세요.')
                        c.execute('UPDATE teams SET logo_data=?,configured=1 WHERE id=?',(row[0],t['id']))
                    else: raise ValueError('팀 설정 경로 오류')
                elif path in ('/api/selection','/api/ready'):
                    check_epoch(c,b)
                    if not u['profile_complete'] or setting(c,'phase')!='matching': raise ValueError('대진 확인 단계에서 이름을 설정한 후 준비하세요.')
                    target=target_round(c); m=match_for(c,u['team_id'],target)
                    if not m: raise ValueError('이번 라운드는 휴식입니다.')
                    if path=='/api/selection':
                        level=b.get('level')
                        if level is not None and (type(level)!=int or level not in REWARD): raise ValueError('레벨 1~5를 선택하세요.')
                        c.execute('DELETE FROM round_preferences WHERE round=? AND user_id=?',(target,u['id']))
                        if level:
                            if c.execute('SELECT 1 FROM round_preferences WHERE round=? AND team_id=? AND level=?',(target,u['team_id'],level)).fetchone(): raise ValueError('팀원이 이미 선택한 레벨입니다.')
                            c.execute('INSERT INTO round_preferences VALUES (?,?,?,?)',(target,u['team_id'],u['id'],level))
                        c.execute('INSERT OR REPLACE INTO round_ready VALUES (?,?,0)',(target,u['id']))
                    else: c.execute('INSERT OR REPLACE INTO round_ready VALUES (?,?,?)',(target,u['id'],int(bool(b.get('ready')))))
                elif path=='/api/draft':
                    check_epoch(c,b); m,l,d=active_player(c,u); check_freeze(d)
                    if b.get('match_id')!=m['id']: raise ValueError('경기가 변경되었습니다.')
                    if b.get('rev')!=d['rev']: return self.send({'conflict':True,'draft':dict(d)},409)
                    code=valid_code(b.get('code'),allow_empty=True)
                    c.execute('UPDATE drafts SET code=?,rev=rev+1,updated_at=? WHERE match_id=? AND user_id=?',(code,time.time(),m['id'],u['id']))
                    c.commit(); return self.send({'draft':dict(draft(c,m['id'],u['id']))})
                elif path=='/api/item':
                    check_epoch(c,b); m,l,d=active_player(c,u)
                    if m['round']!=6 or l not in (1,2,3): raise ValueError('결승 레벨 1~3만 아이템을 사용합니다.')
                    if not c.execute('SELECT 1 FROM solves WHERE match_id=? AND user_id=?',(m['id'],u['id'])).fetchone(): raise ValueError('문제 정답을 먼저 제출하세요.')
                    if c.execute('SELECT 1 FROM used_items WHERE match_id=? AND user_id=?',(m['id'],u['id'])).fetchone(): raise ValueError('이미 사용한 아이템입니다.')
                    opponent=m['team_b'] if m['team_a']==u['team_id'] else m['team_a']
                    kind={1:'freeze',2:'rename',3:'erase'}[l]
                    for target in c.execute('SELECT user_id,level FROM round_assignments WHERE round=6 AND team_id=?',(opponent,)):
                        if l!=1 and target['level'] not in (4,5): continue
                        td=draft(c,m['id'],target['user_id']); code=td['code']
                        if l==1: c.execute('UPDATE drafts SET freeze_until=MAX(freeze_until,?),rev=rev+1 WHERE match_id=? AND user_id=?',(time.time()+20,m['id'],target['user_id']))
                        else:
                            detail='마지막 코드 줄 삭제'
                            if l==2: code,detail=rename_variable(code)
                            else: code=erase_last_line(code)
                            c.execute('UPDATE drafts SET code=?,rev=rev+1,updated_at=? WHERE match_id=? AND user_id=?',(code,time.time(),m['id'],target['user_id']))
                    c.execute('INSERT INTO used_items VALUES (?,?,?,?)',(m['id'],u['id'],kind,time.time()))
                    event(c,m['id'],opponent,u['id'],kind,{1:'상대 팀 20초 빙결',2:'상대 Lv4·5 변수 교란',3:'상대 Lv4·5 마지막 줄 삭제'}[l])
                elif path=='/api/hint':
                    check_epoch(c,b); m,l,d=active_player(c,u); check_freeze(d)
                    kind=b.get('kind'); p=problem_for(m,u['team_id'],l)
                    if kind not in ('type','structure'): raise ValueError('힌트 종류 오류')
                    purchase(c,u,m,p,kind,p['hint1'] if kind=='type' else p['hint2'])
                else: raise ValueError('지원하지 않는 요청입니다.')
                c.commit(); result=snapshot(c,self.user(c))
            self.send(result)
        except PermissionError as e: self.send({'error':str(e)},403)
        except (ValueError,TypeError,sqlite3.IntegrityError) as e: self.send({'error':str(e)},400)
        except Exception as e:
            print(repr(e),file=sys.stderr); self.send({'error':'서버 처리 중 오류'},500)
    def submit_code(self,b):
        with LOCK,db() as c:
            u=self.user(c); tick(c); check_epoch(c,b); m,l,d=active_player(c,u); check_freeze(d)
            if d['cooldown_until']>time.time(): raise ValueError('재제출 대기시간이 남아 있습니다.')
            if c.execute('SELECT 1 FROM solves WHERE match_id=? AND user_id=?',(m['id'],u['id'])).fetchone(): raise ValueError('이미 해결한 문제입니다.')
            if not judge_enabled(): raise ValueError('OpenAI 채점 설정과 API 키를 확인하세요.')
            if b.get('match_id')!=m['id'] or b.get('rev')!=d['rev']: raise ValueError('코드가 변경되었습니다. 동기화 후 다시 제출하세요.')
            code=valid_code(b.get('code')); ep=epoch(c); key=(ep,m['id'],u['id'])
            if key in SUBMITTING: raise ValueError('이미 채점 중입니다.')
            SUBMITTING.add(key)
            c.execute('UPDATE drafts SET code=?,rev=rev+1,updated_at=? WHERE match_id=? AND user_id=?',(code,time.time(),m['id'],u['id']))
            p=relay_problem(c,m,u['team_id'],l)
        try:
            verdict,passed,total=judge_submission(code,p)
            with LOCK,db() as c:
                tick(c)
                now_m=c.execute('SELECT * FROM matches WHERE id=?',(m['id'],)).fetchone()
                if epoch(c)!=ep or not now_m or now_m['status']!='open': raise ValueError('채점 도중 경기가 종료되어 점수에 반영되지 않았습니다.')
                now=time.time()
                c.execute('INSERT INTO submissions(match_id,user_id,problem_id,at,verdict,passed,total,code) VALUES (?,?,?,?,?,?,?,?)',(m['id'],u['id'],p['id'],now,verdict,passed,total,code))
                if verdict=='정답':
                    prior=c.execute('SELECT 1 FROM solves WHERE match_id=? AND problem_id=?',(m['id'],p['id'])).fetchone()
                    score=REWARD[l]//2 if prior and m['round']<=5 else REWARD[l]
                    c.execute('INSERT INTO solves(match_id,team_id,user_id,problem_id,at,win_points,solve_points) VALUES (?,?,?,?,?,?,?)',(m['id'],u['team_id'],u['id'],p['id'],now,score,REWARD[l]))
                    c.execute('INSERT INTO credits(team_id,amount,available_round,reason,at) VALUES (?,?,?,?,?)',(u['team_id'],REWARD[l],m['round'],p['id'],now))
                    event(c,m['id'],u['team_id'],u['id'],'solve',f'Lv{l} 정답 · +{score} 승점')
                    if m['round']==6 and l==5: close_match(c,now_m,u['team_id'],'level5'); tick(c)
                else:
                    c.execute('UPDATE drafts SET cooldown_until=? WHERE match_id=? AND user_id=?',(now+10,m['id'],u['id']))
                    event(c,m['id'],u['team_id'],u['id'],'wrong',f'Lv{l} {verdict.splitlines()[0]}')
                c.commit(); result=snapshot(c,self.user(c))
            self.send(result)
        except JudgeUnavailable as exc:
            self.send({'error':'채점 서비스 오류: '+str(exc)+' 오답으로 처리하지 않았으며 재제출 대기시간도 적용하지 않았습니다.'},503)
        finally:
            with LOCK: SUBMITTING.discard(key)
    def ai_hint(self,b):
        with LOCK,db() as c:
            u=self.user(c); tick(c); check_epoch(c,b); m,l,d=active_player(c,u); check_freeze(d)
            p=problem_for(m,u['team_id'],l)
            old=c.execute('SELECT 1 FROM purchases WHERE match_id=? AND user_id=? AND kind=?',(m['id'],u['id'],'assist')).fetchone()
            if old: return self.send(snapshot(c,u))
            if balance(c,u['team_id'])<HINT_COST['assist']: raise ValueError('solve포인트가 부족합니다.')
            ep=epoch(c); code=valid_code(b.get('code'))
        detail=assist(p,code)
        with LOCK,db() as c:
            tick(c)
            if epoch(c)!=ep or current_round(c)!=m['round'] or setting(c,'phase')!='live': raise ValueError('경기가 종료되어 차감하지 않았습니다.')
            purchase(c,u,m,p,'assist',detail); c.commit(); result=snapshot(c,self.user(c))
        self.send(result)

def purchase(c,u,m,p,kind,detail):
    if c.execute('SELECT 1 FROM purchases WHERE match_id=? AND user_id=? AND kind=?',(m['id'],u['id'],kind)).fetchone(): return
    cost=HINT_COST[kind]
    if balance(c,u['team_id'])<cost: raise ValueError('팀 solve포인트가 부족합니다.')
    now=time.time()
    c.execute('INSERT INTO purchases(match_id,team_id,user_id,problem_id,kind,detail,cost,at) VALUES (?,?,?,?,?,?,?,?)',(m['id'],u['team_id'],u['id'],p['id'],kind,detail,cost,now))
    c.execute('INSERT INTO credits(team_id,amount,available_round,reason,at) VALUES (?,?,?,?,?)',(u['team_id'],-cost,m['round'],kind,now))
    event(c,m['id'],u['team_id'],u['id'],'hint',f'{u["name"]} · '+{'type':'문제 유형 공개','structure':'핵심 구조 공개','assist':'AI 조언'}[kind]+f' · -{cost} solve')

def valid_name(value,limit):
    if not isinstance(value,str): raise ValueError('이름을 입력하세요.')
    value=' '.join(value.split())
    if not 2<=len(value)<=limit or not all(ch.isalnum() or ch in ' _-' for ch in value): raise ValueError(f'이름은 2~{limit}자의 문자·숫자·공백·_·-로 입력하세요.')
    return value

def valid_code(code,allow_empty=False):
    if not isinstance(code,str) or len(code)>16000 or (not allow_empty and not code.strip()): raise ValueError('코드는 16,000자 이하로 입력하세요.')
    return code

def api_check_worker():
    def report(row):
        with LOCK: API_CHECK['results'].append(row)
    try: run_checks(report)
    except Exception as e: report({'name':'연결 시험','ok':False,'seconds':0,'detail':str(e)[:400]})
    with LOCK: API_CHECK['status']='done'; API_CHECK['ended']=time.time()

def ticker():
    while True:
        try:
            with LOCK,db() as c: tick(c)
        except Exception as e: print('timer:',repr(e),file=sys.stderr)
        time.sleep(.5)

if __name__=='__main__':
    setup(); threading.Thread(target=ticker,daemon=True).start()
    host=os.environ.get('HOST','127.0.0.1'); port=int(os.environ.get('PORT','8765'))
    print(f'Code Rumble: http://{host}:{port}',flush=True)
    ThreadingHTTPServer((host,port),Handler).serve_forever()
