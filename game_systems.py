"""Tournament schedules, outcome-based profiles, and adaptive problem allocation."""
import json
import random
import time
from functools import lru_cache
from pathlib import Path
SKILL_LABELS={'completion':'문제 완수','speed':'풀이 속도','accuracy':'제출 정확도','independence':'자립 풀이','contribution':'팀 기여','challenge':'도전 수준'}
TIER_TABLE=[(800,'브론즈','bronze','#bd8654'),(1000,'실버','silver','#b9cbdf'),(1200,'골드','gold','#f6c955'),(1400,'플래티넘','platinum','#68e2bf'),(1600,'다이아몬드','diamond','#79b9ff'),(1800,'챌린저','challenger','#e5a3ff')]
CATALOG_PATH=Path(__file__).with_name('problem_catalog.json')
LEVEL_OFFSETS={1:-500,2:-250,3:0,4:250,5:500}

def round_robin(teams):
    ring=list(teams)
    if len(ring)%2:ring.append(None)
    rounds=[]
    for _ in range(len(ring)-1):
        rounds.append([(ring[i],ring[-1-i]) for i in range(len(ring)//2) if ring[i] is not None and ring[-1-i] is not None])
        ring=[ring[0],ring[-1],*ring[1:-1]]
    return rounds

def schedule(c,lid):
    row=c.execute('SELECT schedule_json FROM lobbies WHERE id=?',(lid,)).fetchone()
    return json.loads(row[0] or '[]') if row else []

def rumble_rounds(c,lid):return len(schedule(c,lid)) or 5

def is_final(c,lid,stage):
    row=c.execute('SELECT mode FROM lobbies WHERE id=?',(lid,)).fetchone()
    return bool(row and row[0]=='challenge' and stage==rumble_rounds(c,lid)+1)

def estimated_seconds(n):
    rounds=n if n%2 else n-1
    return 70+(rounds+1)*10+rounds*300+600+rounds*40+30

def tier_for(rating):
    index=0
    for i,row in enumerate(TIER_TABLE):
        if rating>=row[0]:index=i
    low,name,key,color=TIER_TABLE[index]
    return {'name':name,'key':key,'color':color,'index':index,'min_rating':low,'icon':['🛡','✦','★','❖','◆','♛'][index]}

def skill_cap(rating):return round(20+100*max(0,min(1,(rating-800)/1000)))

def create_schema(c):
    c.executescript('''CREATE TABLE IF NOT EXISTS measured_skills(account_id INTEGER NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,axis TEXT NOT NULL,value REAL NOT NULL DEFAULT 0,samples INTEGER NOT NULL DEFAULT 0,PRIMARY KEY(account_id,axis));
    CREATE TABLE IF NOT EXISTS problem_difficulty_stats(problem_id TEXT PRIMARY KEY,rating REAL NOT NULL,samples INTEGER NOT NULL DEFAULT 0,successes INTEGER NOT NULL DEFAULT 0,last_updated REAL NOT NULL DEFAULT 0);
    CREATE TABLE IF NOT EXISTS matchmaking_history(id INTEGER PRIMARY KEY,wait_seconds REAL NOT NULL,average_rating REAL NOT NULL,at REAL NOT NULL);''')

def profile(c,uid,rating):
    cap=skill_cap(rating)
    rows={r['axis']:r['value'] for r in c.execute('SELECT axis,value FROM measured_skills WHERE account_id=?',(uid,))} if c else {}
    return {'skills':{k:round(rows.get(k,0)*cap/100,1) for k in SKILL_LABELS},'skill_labels':SKILL_LABELS,'skill_max':cap,'skill_total_max':6*cap}

def update_skills(c,person,game,won):
    submissions=list(c.execute('SELECT verdict,at FROM lobby_game_submissions WHERE game_round_id=? AND account_id=? ORDER BY id',(game['id'],person['account_id'])))
    spent=c.execute('SELECT COALESCE(SUM(cost),0) FROM lobby_game_items WHERE game_round_id=? AND account_id=?',(game['id'],person['account_id'])).fetchone()[0]
    solved=bool(person['solved']);accepted=next((x['at'] for x in submissions if x['verdict']=='정답'),game['ends_at'])
    elapsed=max(0,accepted-game['started_at']);duration=max(1,game['ends_at']-game['started_at'])
    measures={'completion':100 if solved else 0,'speed':100*max(0,1-elapsed/duration) if solved else 0,'accuracy':100/max(1,len(submissions)) if solved else 0,'independence':100*max(0,1-spent/500) if solved else 0,'contribution':max(0,min(100,(person['solve_earned']-spent)/3+(15 if won else 0))),'challenge':20*person['level'] if solved else 0}
    for key,value in measures.items():
        old=c.execute('SELECT value FROM measured_skills WHERE account_id=? AND axis=?',(person['account_id'],key)).fetchone()
        score=value if not old else old[0]*.8+value*.2
        c.execute('INSERT INTO measured_skills(account_id,axis,value,samples) VALUES (?,?,?,1) ON CONFLICT(account_id,axis) DO UPDATE SET value=excluded.value,samples=samples+1',(person['account_id'],key,score))

@lru_cache(maxsize=1)
def catalog():return json.loads(CATALOG_PATH.read_text(encoding='utf-8'))['problems']

def difficulty(c,p):
    meta=catalog().get(p['id'])
    if not meta:raise ValueError('문제 난이도 메타데이터가 없습니다: '+p['id'])
    observed=c.execute('SELECT rating,samples FROM problem_difficulty_stats WHERE problem_id=?',(p['id'],)).fetchone()
    rating=meta['difficulty_rating'] if not observed or observed['samples']<30 else observed['rating']
    return {**meta,'difficulty_rating':round(rating),'observed_samples':observed['samples'] if observed else 0}

def record_difficulty(c,p,player_rating,solved):
    initial=catalog()[p['id']]['difficulty_rating'];row=c.execute('SELECT rating FROM problem_difficulty_stats WHERE problem_id=?',(p['id'],)).fetchone();old=row[0] if row else initial
    expected=1/(1+10**((old-player_rating)/400));updated=max(initial-250,min(initial+250,old+12*(expected-int(solved))))
    c.execute('INSERT INTO problem_difficulty_stats(problem_id,rating,samples,successes,last_updated) VALUES (?,?,1,?,?) ON CONFLICT(problem_id) DO UPDATE SET rating=excluded.rating,samples=samples+1,successes=successes+excluded.successes,last_updated=excluded.last_updated',(p['id'],updated,int(solved),time.time()))

def match_targets(avg,final=False):return {level:max(100,round(avg+offset+(150 if final else 0))) for level,offset in LEVEL_OFFSETS.items()}

def allocate(c,problems,avg,used,final=False,teams=None,rng=None):
    rng=rng or random.SystemRandom();meta=catalog();selected={};targets=match_targets(avg,final);forbidden=set(used)
    previous_rating=0
    for level in range(1,6):
        amount=2 if final else 1;options=[]
        for p in problems:
            m=meta.get(p['id'])
            if not m or p['id'] in forbidden or level not in m['eligible_levels'] or final!=(m['stage']=='final'):continue
            value=difficulty(c,p)['difficulty_rating']
            if value<previous_rating+25:continue
            options.append((abs(value-targets[level]),value,p))
        if len(options)<amount:raise ValueError(f'중복 없이 배정할 레벨 {level} 문제가 부족합니다. 문제 카탈로그를 추가하세요.')
        closest=sorted(options,key=lambda x:(x[0],x[2]['id']));band=[x for x in closest if x[0]<=closest[0][0]+40]
        chosen=rng.sample(band,amount) if len(band)>=amount else closest[:amount]
        previous_rating=max(item[1] for item in chosen)
        for i,item in enumerate(chosen):
            selected[f'{teams[i]}:{level}' if final else str(level)]=item[2]['id'];forbidden.add(item[2]['id'])
    return selected,targets
