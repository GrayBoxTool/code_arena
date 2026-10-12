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
from problems import public_samples, PROBLEMS, REWARD, HINT_COST, public_problem, judge_inputs, expected_outputs
from services import judge, assist
import account_security as accounts
import lobby_service as lobbies
from mail_service import send_code
from privacy_notice import CONSENT_VERSION, PRIVACY_NOTICE

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
        accounts.create_schema(c)
        lobbies.create_schema(c)
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
        op_id=os.environ.get('BOOTSTRAP_OPERATOR_ID','').strip()
        op_password=os.environ.get('BOOTSTRAP_OPERATOR_PASSWORD','')
        op_email=os.environ.get('BOOTSTRAP_OPERATOR_EMAIL','').strip().lower()
        if op_id and op_password and op_email and not c.execute('SELECT 1 FROM accounts WHERE username=?',(op_id,)).fetchone():
            op_id=accounts.validate_username(op_id); op_email=accounts.validate_email(op_email)
            op_name=accounts.validate_nickname(os.environ.get('BOOTSTRAP_OPERATOR_NAME','운영자'))
            c.execute('INSERT INTO accounts(username,nickname,full_name,email,password_hash,email_verified,is_operator,consent_version,consent_at,created_at) VALUES (?,?,?,?,?,1,1,?,?,?)',
                      (op_id,op_name,op_name,op_email,accounts.hash_password(op_password),CONSENT_VERSION,time.time(),time.time()))
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
    a,b=points(c,m['id'],m['team_a']),points(c,m['id'],m['team_b'])
    winner=m['team_a'] if a>b else m['team_b'] if b>a else None
    if m['round']==6 and winner is None:
        ca,cb=balance(c,m['team_a']),balance(c,m['team_b'])
        winner=m['team_a'] if ca>cb else m['team_b'] if cb>ca else None
        if winner: reason='solve_tiebreak'
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

def award_points(c,m,level):
    if m["round"]==6: return REWARD[level]
    # Final teams have distinct question IDs; first/second is compared by level.
    prior=c.execute('SELECT 1 FROM solves WHERE match_id=? AND problem_id LIKE ?',
                    (m['id'],f'%-L{level}')).fetchone()
    return REWARD[level]//2 if prior else REWARD[level]

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
        score=award_points(c,m,level)
        c.execute('INSERT INTO submissions(match_id,user_id,problem_id,at,verdict,passed,total,code) VALUES (?,?,?,?,?,?,?,?)',
                  (m['id'],uid,p['id'],now,'정답',len(judge_inputs(p)),len(judge_inputs(p)),'# 운영자 리허설 정답 · 실제 제출 코드 아님'))
        c.execute('INSERT INTO solves(match_id,team_id,user_id,problem_id,at,win_points,solve_points) VALUES (?,?,?,?,?,?,?)',
                  (m['id'],team_id,uid,p['id'],now,score,REWARD[level]))
        c.execute('INSERT INTO credits(team_id,amount,available_round,reason,at) VALUES (?,?,?,?,?)',
                  (team_id,REWARD[level],m['round'],'리허설 '+p['id'],now))
        event(c,m['id'],team_id,uid,'solve',f'리허설 Lv{level} 정답 · +{score} 승점')

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
    return public_problem(p)|{'reward':REWARD[p['level']], **public_samples(p)}


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
            'last_submission':dict(last) if last else None,'hints':hints,'relay':None,'events':list(reversed(ev)),
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

def erase_last_lines(code,count=2):
    lines=code.splitlines(keepends=True)
    for i in range(len(lines)-1,-1,-1):
        if lines[i].strip():
            del lines[i]
            count-=1
            if count==0: break
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

TIER_TABLE=[(800,"브론즈","🪨"),(1000,"실버","🥈"),(1200,"골드","🥇"),(1400,"플래티넘","💠"),(1600,"다이아몬드","💎"),(1800,"챌린저","👑")]
SKILL_AXES=["implementation","strings","simulation","data_structures","search","optimization"]

def tier_for(rating):
    chosen=TIER_TABLE[0]
    for row in TIER_TABLE:
        if rating>=row[0]: chosen=row
    return {"name":chosen[1],"icon":chosen[2],"min_rating":chosen[0]}

def account_summary(c,row):
    if not row:return None
    stats={x:0 for x in SKILL_AXES}
    if c:
        stats.update({x["axis"]:x["value"] for x in c.execute('SELECT axis,value FROM account_stats WHERE account_id=?',(row['id'],))})
    rating=row['rating']
    return {"id":row['id'],"username":row['username'],"nickname":row['nickname'],"full_name":row['full_name'],
            "email":row['email'],"avatar_id":row['avatar_id'],"rating":rating,"tier":tier_for(rating),
            "games":row['games'],"wins":row['wins'],"is_operator":bool(row['is_operator']),"skills":stats}

def account_home(c,me):
    active=c.execute("SELECT l.id FROM lobbies l JOIN lobby_members m ON m.lobby_id=l.id WHERE m.account_id=? AND l.status NOT IN ('closed','cancelled') LIMIT 1",(me['id'],)).fetchone()
    queue=c.execute('SELECT q.joined_at,q.batch_lobby_id,(SELECT COUNT(*) FROM matchmaking_queue WHERE batch_lobby_id IS NULL) AS waiting,(SELECT phase_ends_at FROM lobbies WHERE id=q.batch_lobby_id) AS phase_ends_at FROM matchmaking_queue q WHERE q.account_id=?',(me['id'],)).fetchone()
    friends=[dict(x) for x in c.execute("SELECT a.id,a.nickname,a.rating,a.avatar_id FROM friendships f JOIN accounts a ON a.id=CASE WHEN f.requester_id=? THEN f.target_id ELSE f.requester_id END WHERE (f.requester_id=? OR f.target_id=?) AND f.status='accepted'",(me['id'],me['id'],me['id']))]
    incoming=[dict(x) for x in c.execute("SELECT a.id AS requester_id,a.nickname,a.rating FROM friendships f JOIN accounts a ON a.id=f.requester_id WHERE f.target_id=? AND f.status='pending'",(me['id'],))]
    return {"me":account_summary(c,me),"lobbies":lobbies.public_lobbies(c),"friends":friends,"friend_requests":incoming,
            "active_lobby":active[0] if active else None,
            "queue":{"joined":bool(queue),"joined_at":queue['joined_at'] if queue else None,"batch_lobby_id":queue['batch_lobby_id'] if queue else None,"phase_ends_at":queue['phase_ends_at'] if queue else None,"waiting":queue['waiting'] if queue else 0}}

def friend_request(c,account_id,nickname):
    if not isinstance(nickname,str):raise ValueError('친구 닉네임을 입력하세요.')
    target=c.execute('SELECT id FROM accounts WHERE nickname=? COLLATE NOCASE',(nickname.strip(),)).fetchone()
    if not target:raise ValueError('해당 닉네임의 계정을 찾을 수 없습니다.')
    if target['id']==account_id:raise ValueError('자기 자신에게 친구 요청을 보낼 수 없습니다.')
    x,y=sorted((account_id,target['id']))
    if c.execute('SELECT 1 FROM friendships WHERE (requester_id=? AND target_id=?) OR (requester_id=? AND target_id=?)',(x,y,y,x)).fetchone():raise ValueError('이미 친구 요청이 있거나 친구입니다.')
    c.execute('INSERT INTO friendships(requester_id,target_id,status,created_at) VALUES (?,?,"pending",?)',(account_id,target['id'],time.time()))

def friend_respond(c,account_id,requester_id,accept):
    row=c.execute("SELECT status FROM friendships WHERE requester_id=? AND target_id=? AND status='pending'",(requester_id,account_id)).fetchone()
    if not row:raise ValueError('친구 요청을 찾을 수 없습니다.')
    if accept:c.execute("UPDATE friendships SET status='accepted' WHERE requester_id=? AND target_id=?",(requester_id,account_id))
    else:c.execute('DELETE FROM friendships WHERE requester_id=? AND target_id=?',(requester_id,account_id))

def queue_join(c,account_id):
    active=c.execute("SELECT 1 FROM lobby_members m JOIN lobbies l ON l.id=m.lobby_id WHERE m.account_id=? AND l.status NOT IN ('closed','cancelled')",(account_id,)).fetchone()
    if active:raise ValueError('진행 중이거나 대기 중인 로비를 먼저 나가세요.')
    c.execute('INSERT OR IGNORE INTO matchmaking_queue(account_id,joined_at) VALUES (?,?)',(account_id,time.time()))
    waiting=list(c.execute('SELECT q.account_id,a.rating FROM matchmaking_queue q JOIN accounts a ON a.id=q.account_id WHERE q.batch_lobby_id IS NULL ORDER BY q.joined_at LIMIT 10'))
    if len(waiting)==10:
        a,b=lobbies.balanced_split(waiting)
        lobby_id=c.execute("INSERT INTO lobbies(name,mode,owner_id,visibility,status,phase,phase_ends_at,created_at) VALUES ('랭크 매칭','normal',?,'private','running','countdown',?,?)",(waiting[0]['account_id'],time.time()+10,time.time())).lastrowid
        for team,players in ((1,a),(2,b)):
            for player in players:c.execute('INSERT INTO lobby_members(lobby_id,account_id,team_no,joined_at) VALUES (?,?,?,?)',(lobby_id,player['account_id'],team,time.time()))
        ids=[x['account_id'] for x in waiting]
        c.executemany('UPDATE matchmaking_queue SET batch_lobby_id=? WHERE account_id=?',[(lobby_id,x) for x in ids])

def progress_lobby(c,lobby_id):
    before=c.execute('SELECT * FROM lobbies WHERE id=?',(lobby_id,)).fetchone()
    if before and before['phase']=='live' and before['phase_ends_at'] and before['phase_ends_at']<=time.time():
        settle_account_game(c,lobby_id)
    if before and before['phase']=='team_setup' and before['phase_ends_at'] and before['phase_ends_at']<=time.time():
        for identity in c.execute('SELECT * FROM lobby_team_identity WHERE lobby_id=?',(lobby_id,)).fetchall():
            name=identity['name'] or f"팀 {identity['team_no']}"
            candidates=identity['candidates_json'] or json.dumps(placeholders(name))
            c.execute('UPDATE lobby_team_identity SET name=?,candidates_json=?,selected_logo=COALESCE(selected_logo,1) WHERE lobby_id=? AND team_no=?',(name,candidates,lobby_id,identity['team_no']))
    lobbies.progress(c,lobby_id)
    after=c.execute('SELECT * FROM lobbies WHERE id=?',(lobby_id,)).fetchone()
    if after and after['phase']=='live': start_account_game(c,lobby_id)

ACCOUNT_ROUNDS=[[(1,2),(3,4)],[(1,3),(2,5)],[(1,4),(3,5)],[(1,5),(2,4)],[(2,3),(4,5)]]

def start_account_game(c,lobby_id):
    lobby=c.execute("SELECT * FROM lobbies WHERE id=? AND phase='live'",(lobby_id,)).fetchone()
    if not lobby:return
    existing=c.execute("SELECT id FROM lobby_game_rounds WHERE lobby_id=? AND round_no=? AND phase='live'",(lobby_id,lobby['stage_no'] or 1)).fetchone()
    if existing:
        c.execute('UPDATE lobbies SET active_game_id=? WHERE id=?',(existing['id'],lobby_id));return
    stage=lobby['stage_no'] or 1
    used=set()
    if lobby['mode']=='challenge':
        for row in c.execute('SELECT problem_map_json FROM lobby_game_rounds WHERE lobby_id=?',(lobby_id,)):
            used.update(json.loads(row['problem_map_json']).values())
    problem_map={}
    for level in range(1,6):
        candidates=[p for p in PROBLEMS if p['level']==level and (lobby['mode']!='challenge' or (p['id'] not in used and (p.get('set') in (6,7) if stage==6 else p.get('set') in (1,2,3,4,5))))]
        if not candidates: candidates=[p for p in PROBLEMS if p['level']==level]
        chosen=random.choice(candidates)
        problem_map[str(level)]=chosen['id']
    if lobby['mode']=='challenge' and stage==6:
        totals=list(c.execute('SELECT team_no,win_points,solve_points FROM lobby_team_totals WHERE lobby_id=? ORDER BY win_points DESC,solve_points DESC,team_no',(lobby_id,)))
        finalists=json.loads(lobby['finalists_json']) if lobby['finalists_json'] else [x['team_no'] for x in totals[:2]]
        if len(finalists)<2: finalists=[1,2]
        pairs=[tuple(finalists)]
        # The two finalist teams receive distinct but equal-level problems.
        for level in range(1,6):
            options=[p for p in PROBLEMS if p['level']==level and p.get('set') in (6,7) and p['id'] not in used]
            for team,problem in zip(finalists,options): problem_map[f'{team}:{level}']=problem['id']
    elif lobby['mode']=='challenge': pairs=ACCOUNT_ROUNDS[min(stage-1,4)]
    else: pairs=[(1,2)]
    round_id=c.execute('INSERT INTO lobby_game_rounds(lobby_id,round_no,phase,started_at,ends_at,scores_json,problem_map_json) VALUES (?,?,\'live\',?,?,?,?)',
        (lobby_id,stage,time.time(),lobby['phase_ends_at'],json.dumps({'pairs':pairs},separators=(',',':')),json.dumps(problem_map))).lastrowid
    if lobby['mode']=='challenge' and stage==6:
        active=set(pairs[0])
    elif lobby['mode']=='challenge':active={team for pair in pairs for team in pair}
    else:active={1,2}
    for team in active:
        players=list(c.execute('SELECT account_id,level FROM lobby_members WHERE lobby_id=? AND team_no=? AND is_operator=0 ORDER BY account_id',(lobby_id,team)))
        if lobby['mode']=='challenge':
            for index,member in enumerate(players):
                level=index+1
                problem_id=problem_map.get(f'{team}:{level}',problem_map[str(level)])
                c.execute('INSERT INTO lobby_game_members(game_round_id,account_id,team_no,level,problem_id) VALUES (?,?,?,?,?)',(round_id,member['account_id'],team,level,problem_id))
                c.execute('INSERT INTO lobby_game_drafts(game_round_id,account_id,code,updated_at) VALUES (?,?,\'\',?)',(round_id,member['account_id'],time.time()))
        else:
            for member in players:
                level=member['level'] or random.randint(1,5);problem_id=problem_map[str(level)]
                c.execute('UPDATE lobby_members SET level=? WHERE lobby_id=? AND account_id=?',(level,lobby_id,member['account_id']))
                c.execute('INSERT INTO lobby_game_members(game_round_id,account_id,team_no,level,problem_id) VALUES (?,?,?,?,?)',(round_id,member['account_id'],team,level,problem_id))
                c.execute('INSERT INTO lobby_game_drafts(game_round_id,account_id,code,updated_at) VALUES (?,?,\'\',?)',(round_id,member['account_id'],time.time()))
        c.execute('INSERT OR IGNORE INTO lobby_team_totals(lobby_id,team_no) VALUES (?,?)',(lobby_id,team))
    c.execute('UPDATE lobbies SET active_game_id=? WHERE id=?',(round_id,lobby_id))

def settle_account_game(c,lobby_id):
    game=c.execute("SELECT * FROM lobby_game_rounds WHERE lobby_id=? AND phase='live' ORDER BY round_no DESC LIMIT 1",(lobby_id,)).fetchone()
    if not game:return
    rows=list(c.execute('SELECT team_no,COALESCE(SUM(solve_earned),0) AS earned,COALESCE(SUM(solve_spent),0) AS spent FROM lobby_game_members WHERE game_round_id=? GROUP BY team_no',(game['id'],)))
    score_data=json.loads(game['scores_json']);pairs=score_data.get('pairs',[]); winners=[];winners_by_team={}
    for pair in pairs:
        a,b=pair
        points={x['team_no']:x['win_points'] for x in c.execute('SELECT team_no,win_points FROM lobby_team_totals WHERE lobby_id=?',(lobby_id,))}
        # Scores in totals are lobby-wide; use this round's awarded points for the winner.
        round_scores={team:c.execute('SELECT COALESCE(SUM(gm.solve_earned),0) FROM lobby_game_members gm WHERE gm.game_round_id=? AND gm.team_no=? AND gm.solved=1',(game['id'],team)).fetchone()[0] for team in (a,b)}
        # win_points are stored in submissions' award detail by adding to the round score below.
        award_scores={team:c.execute('SELECT COALESCE(SUM(CASE WHEN solved=1 THEN solve_earned ELSE 0 END),0) FROM lobby_game_members WHERE game_round_id=? AND team_no=?',(game['id'],team)).fetchone()[0] for team in (a,b)}
        # Each solve's solve_earned is also its solve-point reward; score rows use an explicit per-round cache.
        score_data=json.loads(game['scores_json']); round_scores=score_data.get('round_points',{})
        pa=int(round_scores.get(str(a),award_scores[a]));pb=int(round_scores.get(str(b),award_scores[b]))
        winner=a if pa>pb else b if pb>pa else None
        if winner is None and game['round_no']==6:
            solve={team:c.execute('SELECT solve_points FROM lobby_team_totals WHERE lobby_id=? AND team_no=?',(lobby_id,team)).fetchone()[0] for team in (a,b)}
            winner=a if solve[a]>solve[b] else b if solve[b]>solve[a] else None
        if winner:
            winners.append(winner); c.execute('UPDATE lobby_team_totals SET wins=wins+1,win_points=win_points+100 WHERE lobby_id=? AND team_no=?',(lobby_id,winner))
            loser=b if winner==a else a;c.execute('UPDATE lobby_team_totals SET losses=losses+1 WHERE lobby_id=? AND team_no=?',(lobby_id,loser))
        winners_by_team[str(a)]=winner;winners_by_team[str(b)]=winner
        averages={team:(c.execute('SELECT COALESCE(AVG(a.rating),1000) FROM lobby_members m JOIN accounts a ON a.id=m.account_id WHERE m.lobby_id=? AND m.team_no=? AND m.is_operator=0',(lobby_id,team)).fetchone()[0]) for team in (a,b)}
        for team,opp in ((a,b),(b,a)):
            members=list(c.execute('SELECT gm.account_id,gm.level,gm.solved,gm.solve_earned,gm.solve_spent,a.rating FROM lobby_game_members gm JOIN accounts a ON a.id=gm.account_id WHERE gm.game_round_id=? AND gm.team_no=?',(game['id'],team)))
            for person in members:
                delta=lobbies.rating_change(averages[team],averages[opp],winner==team,person['level'],bool(person['solved']),person['solve_earned']-person['solve_spent']) if winner else 0
                c.execute('UPDATE accounts SET rating=MAX(100, rating+?),games=games+1,wins=wins+? WHERE id=?',(delta,int(winner==team),person['account_id']))
                c.execute('UPDATE lobby_game_members SET rating_delta=? WHERE game_round_id=? AND account_id=?',(delta,game['id'],person['account_id']))
    score_data['winners_by_team']=winners_by_team
    c.execute("UPDATE lobby_game_rounds SET phase='results',winner_team=?,scores_json=? WHERE id=?",(winners[0] if len(pairs)==1 else None,json.dumps(score_data),game['id']))

def account_lobby_view(c,lobby_id,viewer_id):
    value=lobbies.lobby_view(c,lobby_id,viewer_id)
    lobby=c.execute('SELECT * FROM lobbies WHERE id=?',(lobby_id,)).fetchone()
    if lobby['phase']=='finalist_choice':
        totals=list(c.execute('SELECT team_no,win_points,solve_points,wins,losses FROM lobby_team_totals WHERE lobby_id=? ORDER BY win_points DESC,team_no',(lobby_id,)))
        if len(totals)>=2:
            cutoff=totals[1]['win_points']; eligible=[dict(x) for x in totals if x['win_points']>=cutoff]
            locked=totals[0]['team_no'] if totals[0]['win_points']>cutoff else None
            value['finalist_choices']={'candidates':eligible,'locked_first':locked}
    game_id=c.execute('SELECT active_game_id FROM lobbies WHERE id=?',(lobby_id,)).fetchone()[0]
    if not game_id:return value
    game=c.execute('SELECT * FROM lobby_game_rounds WHERE id=?',(game_id,)).fetchone()
    member=c.execute('SELECT gm.*,d.code,d.updated_at FROM lobby_game_members gm LEFT JOIN lobby_game_drafts d ON d.game_round_id=gm.game_round_id AND d.account_id=gm.account_id WHERE gm.game_round_id=? AND gm.account_id=?',(game_id,viewer_id)).fetchone()
    totals=[dict(x) for x in c.execute('SELECT * FROM lobby_team_totals WHERE lobby_id=? ORDER BY team_no',(lobby_id,))]
    score_data=json.loads(game['scores_json'])
    info={'round_no':game['round_no'],'phase':game['phase'],'started_at':game['started_at'],'ends_at':game['ends_at'],'totals':totals,'pairs':score_data.get('pairs',[]),'winners_by_team':score_data.get('winners_by_team',{})}
    if member:
        p=LOOKUP[member['problem_id']]
        info['player']={'level':member['level'],'solved':bool(member['solved']),'solve_earned':member['solve_earned'],'solve_spent':member['solve_spent'],'rating_delta':member['rating_delta'],'cooldown_until':member['cooldown_until'],'code':member['code'] or ''}
        info['problem']={**public_problem(p),**public_samples(p)}
        info['solve_balance']=c.execute('SELECT solve_points FROM lobby_team_totals WHERE lobby_id=? AND team_no=?',(lobby_id,member['team_no'])).fetchone()[0]
        info['hints']=[dict(x) for x in c.execute('SELECT kind,detail,cost,at FROM lobby_game_items WHERE game_round_id=? AND team_no=? ORDER BY id',(game_id,member['team_no']))]
    info['winner_team']=game['winner_team']
    if value.get('is_operator'):
        players=[]
        for x in c.execute('SELECT gm.account_id,gm.team_no,gm.level,gm.problem_id,gm.solved,gm.solve_earned,gm.solve_spent,a.nickname,d.code,d.updated_at FROM lobby_game_members gm JOIN accounts a ON a.id=gm.account_id LEFT JOIN lobby_game_drafts d ON d.game_round_id=gm.game_round_id AND d.account_id=gm.account_id WHERE gm.game_round_id=? ORDER BY gm.team_no,gm.level',(game_id,)):
            players.append({**dict(x),'problem_title':LOOKUP[x['problem_id']]['title']})
        info['players']=players
    value['game']=info
    return value

def choose_account_finalists(c,lobby_id,account_id,team_a,team_b):
    lobby=c.execute("SELECT * FROM lobbies WHERE id=? AND mode='challenge' AND phase='finalist_choice'",(lobby_id,)).fetchone()
    member=c.execute('SELECT is_operator FROM lobby_members WHERE lobby_id=? AND account_id=?',(lobby_id,account_id)).fetchone()
    if not lobby or not member or (lobby['owner_id']!=account_id and not member['is_operator']):raise PermissionError('로비 생성자 또는 운영자만 결승 진출팀을 확정할 수 있습니다.')
    totals=list(c.execute('SELECT team_no,win_points FROM lobby_team_totals WHERE lobby_id=? ORDER BY win_points DESC,team_no',(lobby_id,)))
    if len(totals)<2:raise ValueError('결승 진출팀을 정할 점수 기록이 없습니다.')
    cutoff=totals[1]['win_points'];eligible={x['team_no'] for x in totals if x['win_points']>=cutoff}
    locked=totals[0]['team_no'] if totals[0]['win_points']>cutoff else None
    if type(team_a) is not int or type(team_b) is not int or team_a==team_b or team_a not in eligible or team_b not in eligible or (locked and locked not in (team_a,team_b)):
        raise ValueError('점수 동점 후보 안에서 두 팀을 선택하세요. 단독 1위 팀이 있으면 반드시 포함해야 합니다.')
    has_operator=c.execute('SELECT 1 FROM lobby_members WHERE lobby_id=? AND is_operator=1',(lobby_id,)).fetchone()
    c.execute("UPDATE lobbies SET finalists_json=?,phase=?,status='running',phase_ends_at=? WHERE id=?",(json.dumps([team_a,team_b]),'operator_results' if has_operator else 'break',None if has_operator else time.time()+20,lobby_id))
    return {'finalists':[team_a,team_b]}

def skill_axis_for_problem(problem):
    tag=problem.get('tag','')
    if any(k in tag for k in ('문자열','접두','문자')):return 'strings'
    if any(k in tag for k in ('탐색','검색','완전 탐색')):return 'search'
    if any(k in tag for k in ('자료구조','스택','큐','빈도')):return 'data_structures'
    if any(k in tag for k in ('최적화','그리디','누적합')):return 'optimization'
    if any(k in tag for k in ('시뮬레이션','날짜','구현')):return 'simulation'
    return 'implementation'

def save_account_draft(lobby_id,account_id,code):
    code=valid_code(code,allow_empty=True)
    with LOCK,db() as c:
        row=c.execute('SELECT l.phase,gm.game_round_id FROM lobbies l JOIN lobby_game_members gm ON gm.game_round_id=l.active_game_id WHERE l.id=? AND gm.account_id=?',(lobby_id,account_id)).fetchone()
        if not row or row['phase']!='live':raise ValueError('진행 중인 경기의 코드만 저장할 수 있습니다.')
        c.execute('UPDATE lobby_game_drafts SET code=?,updated_at=? WHERE game_round_id=? AND account_id=?',(code,time.time(),row['game_round_id'],account_id))
        return {'saved':True}

def purchase_account_hint(lobby_id,account_id,kind,code):
    costs={'type':50,'structure':150,'assist':300}
    if kind not in costs:raise ValueError('AI 힌트 종류를 확인하세요.')
    code=valid_code(code,allow_empty=True)
    with LOCK,db() as c:
        row=c.execute("SELECT l.phase,gm.*,gr.id AS round_id,gr.phase AS game_phase FROM lobbies l JOIN lobby_game_rounds gr ON gr.id=l.active_game_id JOIN lobby_game_members gm ON gm.game_round_id=gr.id WHERE l.id=? AND gm.account_id=?",(lobby_id,account_id)).fetchone()
        if not row or row['phase']!='live' or row['game_phase']!='live':raise ValueError('진행 중인 문제에서만 힌트를 사용할 수 있습니다.')
        if row['solved']:raise ValueError('문제를 해결한 뒤에는 힌트를 사용할 수 없습니다.')
        balance=c.execute('SELECT solve_points FROM lobby_team_totals WHERE lobby_id=? AND team_no=?',(lobby_id,row['team_no'])).fetchone()[0]
        if balance<costs[kind]:raise ValueError(f"팀 solve 포인트가 부족합니다. 현재 {balance}점입니다.")
        problem=LOOKUP[row['problem_id']]
    if kind=='type':detail=problem['hint1']
    elif kind=='structure':detail=problem['hint2']
    else:detail=assist(problem,code)
    with LOCK,db() as c:
        current=c.execute('SELECT phase FROM lobbies WHERE id=?',(lobby_id,)).fetchone()
        balance=c.execute('SELECT solve_points FROM lobby_team_totals WHERE lobby_id=? AND team_no=?',(lobby_id,row['team_no'])).fetchone()[0]
        if not current or current['phase']!='live':raise ValueError('경기가 끝나 힌트를 반영하지 않았습니다.')
        if balance<costs[kind]:raise ValueError('팀 solve 포인트가 다른 아이템 사용으로 부족해졌습니다. 비용은 차감하지 않았습니다.')
        c.execute('UPDATE lobby_team_totals SET solve_points=solve_points-? WHERE lobby_id=? AND team_no=?',(costs[kind],lobby_id,row['team_no']))
        c.execute('UPDATE lobby_game_members SET solve_spent=solve_spent+? WHERE game_round_id=? AND account_id=?',(costs[kind],row['round_id'],account_id))
        c.execute('INSERT INTO lobby_game_items(game_round_id,account_id,team_no,kind,detail,cost,at) VALUES (?,?,?,?,?,?,?)',(row['round_id'],account_id,row['team_no'],kind,detail,costs[kind],time.time()))
        return {'kind':kind,'detail':detail,'cost':costs[kind]}

def submit_account_game(lobby_id,account_id,code):
    code=valid_code(code)
    with LOCK,db() as c:
        row=c.execute('SELECT l.*,gm.*,gr.phase AS game_phase,gr.ends_at,gr.id AS round_id FROM lobbies l JOIN lobby_game_rounds gr ON gr.id=l.active_game_id JOIN lobby_game_members gm ON gm.game_round_id=gr.id WHERE l.id=? AND gm.account_id=?',(lobby_id,account_id)).fetchone()
        if not row or row['phase']!='live' or row['game_phase']!='live' or row['ends_at']<=time.time():raise ValueError('현재 제출할 수 있는 진행 중인 매치가 없습니다.')
        if row['solved']:raise ValueError('이미 정답을 제출한 문제입니다.')
        if row['cooldown_until']>time.time():raise ValueError(f"오답 재제출까지 {max(1,round(row['cooldown_until']-time.time()))}초 남았습니다.")
        p=LOOKUP[row['problem_id']]; key=('lobby',row['round_id'],account_id)
        if key in SUBMITTING:raise ValueError('이미 채점 중입니다.')
        SUBMITTING.add(key)
        c.execute('UPDATE lobby_game_drafts SET code=?,updated_at=? WHERE game_round_id=? AND account_id=?',(code,time.time(),row['round_id'],account_id))
    try:
        verdict,passed,total=judge_submission(code,p)
        with LOCK,db() as c:
            row=c.execute('SELECT * FROM lobby_game_members WHERE game_round_id=? AND account_id=?',(row['round_id'],account_id)).fetchone()
            current=c.execute('SELECT phase FROM lobby_game_rounds WHERE id=?',(row['game_round_id'],)).fetchone()
            if not current or current['phase']!='live':raise ValueError('경기가 끝나 채점 결과를 반영하지 않았습니다.')
            c.execute('INSERT INTO lobby_game_submissions(game_round_id,account_id,problem_id,code,verdict,at) VALUES (?,?,?,?,?,?)',(row['game_round_id'],account_id,row['problem_id'],code,verdict,time.time()))
            if verdict=='정답':
                first=c.execute('SELECT 1 FROM lobby_game_members WHERE game_round_id=? AND team_no=? AND level=? AND solved=1',(row['game_round_id'],row['team_no'],row['level'])).fetchone()
                if not first:
                    game=c.execute('SELECT scores_json FROM lobby_game_rounds WHERE id=?',(row['game_round_id'],)).fetchone();meta=json.loads(game['scores_json']);pairs=meta.get('pairs',[])
                    opp=next((b if a==row['team_no'] else a for a,b in pairs if row['team_no'] in (a,b)),None)
                    rival=c.execute('SELECT 1 FROM lobby_game_members WHERE game_round_id=? AND team_no=? AND level=? AND solved=1',(row['game_round_id'],opp,row['level'])).fetchone() if opp else None
                    final_round=c.execute('SELECT round_no FROM lobby_game_rounds WHERE id=?',(row['game_round_id'],)).fetchone()[0]==6
                    win_points=REWARD[row['level']] if final_round or not rival else REWARD[row['level']]//2
                    meta.setdefault('round_points',{})[str(row['team_no'])]=meta.setdefault('round_points',{}).get(str(row['team_no']),0)+win_points
                    c.execute('UPDATE lobby_game_rounds SET scores_json=? WHERE id=?',(json.dumps(meta),row['game_round_id']))
                    c.execute('UPDATE lobby_team_totals SET win_points=win_points+? WHERE lobby_id=? AND team_no=?',(win_points,lobby_id,row['team_no']))
                c.execute('UPDATE lobby_game_members SET solved=1,solve_earned=? WHERE game_round_id=? AND account_id=?',(REWARD[row['level']],row['game_round_id'],account_id))
                c.execute('UPDATE lobby_team_totals SET solve_points=solve_points+? WHERE lobby_id=? AND team_no=?',(REWARD[row['level']],lobby_id,row['team_no']))
                axis=skill_axis_for_problem(p)
                c.execute('UPDATE account_stats SET value=MIN(100,value+?) WHERE account_id=? AND axis=?',(max(1,passed*5),account_id,axis))
            else:
                c.execute('UPDATE lobby_game_members SET cooldown_until=? WHERE game_round_id=? AND account_id=?',(time.time()+10,row['game_round_id'],account_id))
            return {'verdict':verdict,'passed':passed,'total':total,'lobby':account_lobby_view(c,lobby_id,account_id)}
    finally:
        SUBMITTING.discard(key)

def lobby_logo_worker(lobby_id,team_no,name,captain_id):
    try:
        images=create_logos(name)
    except Exception:
        images=placeholders(name)
    with LOCK,db() as c:
        identity=c.execute('SELECT * FROM lobby_team_identity WHERE lobby_id=? AND team_no=? AND captain_id=?',(lobby_id,team_no,captain_id)).fetchone()
        if not identity or identity['name']!=name:return
        c.execute('UPDATE lobby_team_identity SET candidates_json=? WHERE lobby_id=? AND team_no=?',(json.dumps(images),lobby_id,team_no))

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
    def account(self,c):
        token=self.headers.get('Authorization','').removeprefix('Bearer ')
        row=accounts.account_for_token(c,token)
        if not row: raise PermissionError('로그인이 만료되었습니다. 다시 로그인하세요.')
        return row
    def auth_post(self,path,b):
        if path=='/api/auth/register/start':
            with LOCK,db() as c: email,code=accounts.begin_registration(c,b,CONSENT_VERSION)
            send_code(email,code,'register')
            return self.send({'ok':True,'message':'인증 코드를 이메일로 보냈습니다. 10분 안에 입력하세요.'})
        if path=='/api/auth/register/verify':
            with LOCK,db() as c:
                account_id=accounts.verify_registration(c,b.get('email'),b.get('code'),CONSENT_VERSION)
                row=c.execute('SELECT * FROM accounts WHERE id=?',(account_id,)).fetchone()
                token=accounts.create_session(c,account_id)
            return self.send({'token':token,'me':account_summary(None,row)})
        if path=='/api/auth/login':
            with LOCK,db() as c: token,row=accounts.login(c,b.get('username'),b.get('password'))
            with db() as c: row=c.execute('SELECT * FROM accounts WHERE id=?',(row['id'],)).fetchone(); me=account_summary(c,row)
            return self.send({'token':token,'me':me})
        if path=='/api/auth/logout':
            raw=self.headers.get('Authorization','').removeprefix('Bearer ')
            with LOCK,db() as c: c.execute('DELETE FROM account_sessions WHERE token_hash=?',(accounts.opaque_hash(raw),))
            return self.send({'ok':True})
        if path=='/api/auth/recovery/start':
            kind=b.get('kind');email=b.get('email')
            with LOCK,db() as c: email,code,found=accounts.begin_recovery(c,email,kind)
            if found: send_code(email,code,'recovery')
            return self.send({'ok':True,'message':'등록된 이메일이면 인증 코드를 보냈습니다.'})
        if path=='/api/auth/recovery/finish':
            with LOCK,db() as c: result=accounts.finish_recovery(c,b.get('email'),b.get('kind'),b.get('code'),b.get('new_password'))
            return self.send(result)
        raise ValueError('지원하지 않는 인증 요청입니다.')

    def account_post(self,path,b):
        with LOCK,db() as c:
            me=self.account(c)
            if path=='/api/account/nickname':
                nick=accounts.validate_nickname(b.get('nickname'))
                if c.execute('SELECT 1 FROM accounts WHERE nickname=? COLLATE NOCASE AND id!=?',(nick,me['id'])).fetchone(): raise ValueError('이미 사용 중인 닉네임입니다.')
                c.execute('UPDATE accounts SET nickname=? WHERE id=?',(nick,me['id']))
            elif path=='/api/account/avatar':
                avatar=b.get('avatar_id')
                if type(avatar) is not int or avatar not in range(1,6): raise ValueError('기본 아이콘 5개 중에서 선택하세요.')
                c.execute('UPDATE accounts SET avatar_id=? WHERE id=?',(avatar,me['id']))
            elif path=='/api/lobby/create':
                lid=lobbies.create_lobby(c,me['id'],b.get('name',''),b.get('mode'))
                return self.send(lobbies.lobby_view(c,lid,me['id']))
            elif path=='/api/lobby/join':
                lobbies.join_lobby(c,int(b.get('lobby_id',0)),me['id'],b.get('team_no'))
            elif path=='/api/lobby/leave':
                lid=int(b.get('lobby_id',0)); target=c.execute('SELECT visibility,phase FROM lobbies WHERE id=?',(lid,)).fetchone()
                if target and target['visibility']=='private' and target['phase'] in ('countdown','level_select','start_countdown'):
                    raise ValueError('자동 매칭이 시작되는 동안에는 로비를 나갈 수 없습니다.')
                c.execute('DELETE FROM lobby_members WHERE lobby_id=? AND account_id=?',(lid,me['id']))
                if target and target['visibility']=='private':c.execute('DELETE FROM matchmaking_queue WHERE account_id=? AND batch_lobby_id=?',(me['id'],lid))
                c.execute("UPDATE lobbies SET status='cancelled' WHERE id=? AND owner_id=? AND NOT EXISTS(SELECT 1 FROM lobby_members WHERE lobby_id=? AND account_id=owner_id)",(lid,me['id'],lid))
            elif path=='/api/lobby/draft': return self.send(save_account_draft(int(b.get('lobby_id',0)),me['id'],b.get('code','')))
            elif path=='/api/lobby/move': lobbies.move_team(c,int(b.get('lobby_id',0)),me['id'],int(b.get('team_no',0)))
            elif path=='/api/lobby/ready': lobbies.set_ready(c,int(b.get('lobby_id',0)),me['id'],b.get('ready') is True)
            elif path=='/api/lobby/swap-request': lobbies.request_swap(c,int(b.get('lobby_id',0)),me['id'],int(b.get('target_id',0)))
            elif path=='/api/lobby/swap-response': lobbies.respond_swap(c,int(b.get('request_id',0)),me['id'],b.get('accept') is True)
            elif path=='/api/lobby/start': lobbies.start_lobby(c,int(b.get('lobby_id',0)),me['id'])
            elif path=='/api/lobby/level': lobbies.choose_level(c,int(b.get('lobby_id',0)),me['id'],b.get('level'))
            elif path=='/api/lobby/operator-seat':
                if not me['is_operator']: raise PermissionError('운영자 계정만 운영자 자리에 참여할 수 있습니다.')
                lobbies.join_operator(c,int(b.get('lobby_id',0)),me['id'])
            elif path=='/api/lobby/captain-vote': lobbies.cast_captain_vote(c,int(b.get('lobby_id',0)),me['id'],int(b.get('candidate_id',0)))
            elif path=='/api/lobby/team-name':
                lid=int(b.get('lobby_id',0)); team=int(b.get('team_no',0)); name=valid_name(b.get('name'),24)
                phase=c.execute('SELECT phase FROM lobbies WHERE id=?',(lid,)).fetchone()
                identity=c.execute('SELECT * FROM lobby_team_identity WHERE lobby_id=? AND team_no=? AND captain_id=?',(lid,team,me['id'])).fetchone()
                if not identity or not phase or phase['phase']!='team_setup': raise PermissionError('팀 설정 시간에 해당 팀의 팀장만 팀명을 정할 수 있습니다.')
                c.execute('UPDATE lobby_team_identity SET name=?,candidates_json=?,selected_logo=NULL WHERE lobby_id=? AND team_no=?',(name,json.dumps(placeholders(name)),lid,team))
                if os.environ.get('OPENAI_API_KEY'):
                    threading.Thread(target=lobby_logo_worker,args=(lid,team,name,me['id']),daemon=True).start()
            elif path=='/api/lobby/choose-logo':
                lid=int(b.get('lobby_id',0)); team=int(b.get('team_no',0)); slot=b.get('slot')
                phase=c.execute('SELECT phase FROM lobbies WHERE id=?',(lid,)).fetchone()
                identity=c.execute('SELECT * FROM lobby_team_identity WHERE lobby_id=? AND team_no=? AND captain_id=?',(lid,team,me['id'])).fetchone()
                if not identity or not phase or phase['phase']!='team_setup' or not identity['name'] or type(slot) is not int or slot not in (1,2,3): raise ValueError('팀 설정 시간에 팀 이름과 로고 후보를 확인하세요.')
                c.execute('UPDATE lobby_team_identity SET selected_logo=? WHERE lobby_id=? AND team_no=?',(slot,lid,team))
            elif path=='/api/lobby/operator-start': lobbies.operator_start(c,int(b.get('lobby_id',0)),me['id'])
            elif path=='/api/lobby/operator-close':
                lid=int(b.get('lobby_id',0));settle_account_game(c,lid);lobbies.operator_close(c,lid,me['id'])
            elif path=='/api/lobby/operator-next': lobbies.operator_next(c,int(b.get('lobby_id',0)),me['id'])
            elif path=='/api/lobby/finalists':
                return self.send(choose_account_finalists(c,int(b.get('lobby_id',0)),me['id'],b.get('team_a'),b.get('team_b')))
            elif path=='/api/friends/request': friend_request(c,me['id'],b.get('nickname'))
            elif path=='/api/friends/respond': friend_respond(c,me['id'],int(b.get('requester_id',0)),b.get('accept') is True)
            elif path=='/api/matchmaking/join': queue_join(c,me['id'])
            elif path=='/api/matchmaking/cancel': c.execute('DELETE FROM matchmaking_queue WHERE account_id=?',(me['id'],))
            else: raise ValueError('지원하지 않는 요청입니다.')
            return self.send(account_home(c,me))

    def do_OPTIONS(self):
        if not FRONTEND_ORIGIN or self.headers.get('Origin')!=FRONTEND_ORIGIN: return self.send({'error':'허용되지 않은 출처'},403)
        self.send_response(204); self.cors(); self.end_headers()
    def do_GET(self):
        parsed=urlparse(self.path); path=parsed.path
        try:
            if path=='/api/privacy': return self.send({'version':CONSENT_VERSION,'notice':PRIVACY_NOTICE})
            if path in ('/api/account/me','/api/home','/api/lobbies') or path.startswith('/api/lobby/'):
                with LOCK,db() as c:
                    me=self.account(c)
                    c.execute("UPDATE team_swap_requests SET status='expired' WHERE status='pending' AND expires_at<=?",(time.time(),))
                    for active in c.execute("SELECT id FROM lobbies WHERE status IN ('running','results')").fetchall(): progress_lobby(c,active['id'])
                    if path=='/api/account/me': result=account_summary(c,me)
                    elif path in ('/api/home','/api/lobbies'): result=account_home(c,me)
                    else:
                        parts=path.strip('/').split('/')
                        if len(parts)!=3: raise ValueError('로비 주소를 확인하세요.')
                        lid=int(parts[2]); progress_lobby(c,lid); result=account_lobby_view(c,lid,me['id'])
                return self.send(result)
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
            if not (target.resolve().is_relative_to((ROOT/'static').resolve()) and (target.parent==ROOT/'static' or target.parent==ROOT/'static'/'problem-images')) or target.suffix not in ('.html','.css','.js','.svg','.png') or not target.is_file(): return self.send({'error':'찾을 수 없습니다.'},404)
            data=target.read_bytes(); self.send_response(200); self.send_header('Content-Type',{'.html':'text/html','.js':'text/javascript','.css':'text/css','.svg':'image/svg+xml','.png':'image/png'}[target.suffix]+'; charset=utf-8'); self.send_header('Content-Length',str(len(data))); self.send_header('Cache-Control','no-store'); self.end_headers(); self.wfile.write(data)
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
            if path.startswith('/api/auth/'):
                return self.auth_post(path,b)
            if path=='/api/lobby/submit':
                with LOCK,db() as c: me=self.account(c)
                return self.send(submit_account_game(int(b.get('lobby_id',0)),me['id'],b.get('code','')))
            if path=='/api/lobby/hint':
                with LOCK,db() as c: me=self.account(c)
                return self.send(purchase_account_hint(int(b.get('lobby_id',0)),me['id'],b.get('kind'),b.get('code','')))
            if path.startswith('/api/lobby/') or path.startswith('/api/matchmaking/') or path.startswith('/api/friends/') or path.startswith('/api/account/'):
                return self.account_post(path,b)
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
                            detail='마지막 내용 있는 코드 두 줄 삭제'
                            if l==2: code,detail=rename_variable(code)
                            else: code=erase_last_lines(code)
                            c.execute('UPDATE drafts SET code=?,rev=rev+1,updated_at=? WHERE match_id=? AND user_id=?',(code,time.time(),m['id'],target['user_id']))
                    c.execute('INSERT INTO used_items VALUES (?,?,?,?)',(m['id'],u['id'],kind,time.time()))
                    event(c,m['id'],opponent,u['id'],kind,{1:'상대 팀 20초 빙결',2:'상대 Lv4·5 변수 교란',3:'상대 Lv4·5 마지막 내용 있는 두 줄 삭제'}[l])
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
            p=problem_for(m,u['team_id'],l)
        try:
            verdict,passed,total=judge_submission(code,p)
            with LOCK,db() as c:
                tick(c)
                now_m=c.execute('SELECT * FROM matches WHERE id=?',(m['id'],)).fetchone()
                if epoch(c)!=ep or not now_m or now_m['status']!='open': raise ValueError('채점 도중 경기가 종료되어 점수에 반영되지 않았습니다.')
                now=time.time()
                c.execute('INSERT INTO submissions(match_id,user_id,problem_id,at,verdict,passed,total,code) VALUES (?,?,?,?,?,?,?,?)',(m['id'],u['id'],p['id'],now,verdict,passed,total,code))
                if verdict=='정답':
                    score=award_points(c,m,l)
                    c.execute('INSERT INTO solves(match_id,team_id,user_id,problem_id,at,win_points,solve_points) VALUES (?,?,?,?,?,?,?)',(m['id'],u['team_id'],u['id'],p['id'],now,score,REWARD[l]))
                    c.execute('INSERT INTO credits(team_id,amount,available_round,reason,at) VALUES (?,?,?,?,?)',(u['team_id'],REWARD[l],m['round'],p['id'],now))
                    event(c,m['id'],u['team_id'],u['id'],'solve',f'Lv{l} 정답 · +{score} 승점')
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
