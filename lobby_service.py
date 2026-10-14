"""Public lobby and ranked queue persistence helpers for the account-based game flow."""
import itertools
import time
import game_systems as systems
import social_service as social

MAX_TEAM = 5
CHALLENGE_TEAMS = 8


def create_schema(c):
    c.executescript("""
    CREATE TABLE IF NOT EXISTS lobbies(
      id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, mode TEXT NOT NULL,
      owner_id INTEGER NOT NULL REFERENCES accounts(id), visibility TEXT NOT NULL DEFAULT 'public',
      status TEXT NOT NULL DEFAULT 'waiting', phase TEXT NOT NULL DEFAULT 'waiting',
      phase_ends_at REAL, created_at REAL NOT NULL, active_game_id INTEGER
    );
    CREATE TABLE IF NOT EXISTS lobby_members(
      lobby_id INTEGER NOT NULL REFERENCES lobbies(id) ON DELETE CASCADE,
      account_id INTEGER NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
      team_no INTEGER NOT NULL, is_operator INTEGER NOT NULL DEFAULT 0,
      ready INTEGER NOT NULL DEFAULT 0, level INTEGER, joined_at REAL NOT NULL,
      PRIMARY KEY(lobby_id,account_id)
    );
    CREATE INDEX IF NOT EXISTS lobby_members_team ON lobby_members(lobby_id,team_no);
    CREATE TABLE IF NOT EXISTS captain_votes(
      lobby_id INTEGER NOT NULL, team_no INTEGER NOT NULL, voter_id INTEGER NOT NULL, candidate_id INTEGER NOT NULL,
      PRIMARY KEY(lobby_id,voter_id)
    );
    CREATE TABLE IF NOT EXISTS lobby_team_identity(
      lobby_id INTEGER NOT NULL, team_no INTEGER NOT NULL, captain_id INTEGER NOT NULL,
      name TEXT, candidates_json TEXT, selected_logo INTEGER, PRIMARY KEY(lobby_id,team_no)
    );
    CREATE TABLE IF NOT EXISTS team_swap_requests(
      id INTEGER PRIMARY KEY AUTOINCREMENT, lobby_id INTEGER NOT NULL,
      requester_id INTEGER NOT NULL, target_id INTEGER NOT NULL,
      expires_at REAL NOT NULL, status TEXT NOT NULL DEFAULT 'pending'
    );
    CREATE TABLE IF NOT EXISTS matchmaking_queue(
      account_id INTEGER PRIMARY KEY REFERENCES accounts(id) ON DELETE CASCADE,
      joined_at REAL NOT NULL, batch_lobby_id INTEGER
    );
    CREATE TABLE IF NOT EXISTS lobby_game_rounds(
      id INTEGER PRIMARY KEY AUTOINCREMENT, lobby_id INTEGER NOT NULL, round_no INTEGER NOT NULL,
      phase TEXT NOT NULL, started_at REAL, ends_at REAL, winner_team INTEGER,
      scores_json TEXT NOT NULL DEFAULT '{}', problem_map_json TEXT NOT NULL DEFAULT '{}'
    );
    CREATE TABLE IF NOT EXISTS lobby_game_members(
      game_round_id INTEGER NOT NULL, account_id INTEGER NOT NULL, team_no INTEGER NOT NULL,
      level INTEGER NOT NULL, problem_id TEXT NOT NULL, solved INTEGER NOT NULL DEFAULT 0,
      solve_earned INTEGER NOT NULL DEFAULT 0, solve_spent INTEGER NOT NULL DEFAULT 0,
      rating_delta INTEGER NOT NULL DEFAULT 0, cooldown_until REAL NOT NULL DEFAULT 0,
      PRIMARY KEY(game_round_id,account_id)
    );
    CREATE TABLE IF NOT EXISTS lobby_game_drafts(
      game_round_id INTEGER NOT NULL, account_id INTEGER NOT NULL, code TEXT NOT NULL DEFAULT '',
      updated_at REAL NOT NULL DEFAULT 0, PRIMARY KEY(game_round_id,account_id)
    );
    CREATE TABLE IF NOT EXISTS lobby_game_submissions(
      id INTEGER PRIMARY KEY AUTOINCREMENT, game_round_id INTEGER NOT NULL,
      account_id INTEGER NOT NULL, problem_id TEXT NOT NULL, code TEXT NOT NULL,
      verdict TEXT NOT NULL, at REAL NOT NULL
    );
    CREATE TABLE IF NOT EXISTS lobby_game_items(
      id INTEGER PRIMARY KEY AUTOINCREMENT, game_round_id INTEGER NOT NULL,
      account_id INTEGER NOT NULL, team_no INTEGER NOT NULL, kind TEXT NOT NULL,
      detail TEXT NOT NULL, cost INTEGER NOT NULL, at REAL NOT NULL
    );
    CREATE TABLE IF NOT EXISTS lobby_team_totals(
      lobby_id INTEGER NOT NULL, team_no INTEGER NOT NULL, win_points INTEGER NOT NULL DEFAULT 0,
      solve_points INTEGER NOT NULL DEFAULT 0, wins INTEGER NOT NULL DEFAULT 0, losses INTEGER NOT NULL DEFAULT 0,
      PRIMARY KEY(lobby_id,team_no)
    );
    """)
    columns={x[1] for x in c.execute("PRAGMA table_info(lobbies)")}
    if "stage_no" not in columns:
        c.execute("ALTER TABLE lobbies ADD COLUMN stage_no INTEGER NOT NULL DEFAULT 0")
    if "finalists_json" not in columns:
        c.execute("ALTER TABLE lobbies ADD COLUMN finalists_json TEXT")
    if "schedule_json" not in columns:
        c.execute("ALTER TABLE lobbies ADD COLUMN schedule_json TEXT")
    systems.create_schema(c)
    social.create_schema(c)
    member_columns={x[1] for x in c.execute("PRAGMA table_info(lobby_game_members)")}
    if "cooldown_until" not in member_columns:
        c.execute("ALTER TABLE lobby_game_members ADD COLUMN cooldown_until REAL NOT NULL DEFAULT 0")


def team_capacity(mode):
    return CHALLENGE_TEAMS if mode == "challenge" else 2


def lobby_team_slots(c,lobby_id,mode):
    if mode!='challenge':return 2
    row=c.execute('SELECT COUNT(*),COALESCE(MAX(team_no),0) FROM lobby_members WHERE lobby_id=? AND is_operator=0',(lobby_id,)).fetchone()
    return min(8,max(3,(row[0]+4)//5,row[1]))


def team_count(c, lobby_id, team_no):
    return c.execute("SELECT COUNT(*) FROM lobby_members WHERE lobby_id=? AND team_no=? AND is_operator=0",
                     (lobby_id, team_no)).fetchone()[0]


def balanced_split(players):
    """Find the 5v5 split with the closest total rating; deterministic ties by ID."""
    players = sorted(players, key=lambda p: p["id"])
    target = len(players) // 2
    total = sum(p["rating"] for p in players)
    candidates = []
    first = players[0]
    for chosen in itertools.combinations(players[1:], target - 1):
        team_a = [first, *chosen]
        ids = {p["id"] for p in team_a}
        team_b = [p for p in players if p["id"] not in ids]
        candidates.append((abs(sum(p["rating"] for p in team_a) * 2 - total), tuple(p["id"] for p in team_a), team_a, team_b))
    _, _, a, b = min(candidates, key=lambda row: (row[0], row[1]))
    return a, b


def rating_change(rating_a, rating_b, won, level, solved, solve_net):
    """Elo team result plus bounded personal difficulty/solve contribution."""
    expected = 1 / (1 + 10 ** ((rating_b - rating_a) / 400))
    result = 1.0 if won else 0.0
    base = round(24 * (result - expected))
    performance = min(8, max(0, level - 1) * 2 + (6 if solved else 0) + max(-2, min(2, solve_net // 100)))
    delta = base + (performance if won else -performance)
    return max(-32, min(32, delta))

import json
import secrets


def public_lobbies(c):
    rows = c.execute("""SELECT l.*,a.nickname AS owner_nickname,
      COUNT(CASE WHEN m.is_operator=0 THEN 1 END) AS players,
      SUM(CASE WHEN m.ready=1 AND m.is_operator=0 THEN 1 ELSE 0 END) AS ready_count
      FROM lobbies l JOIN accounts a ON a.id=l.owner_id
      LEFT JOIN lobby_members m ON m.lobby_id=l.id
      WHERE l.visibility='public' AND l.status='waiting'
      GROUP BY l.id ORDER BY l.created_at DESC LIMIT 50""").fetchall()
    result=[]
    for x in rows:
        result.append({"id":x["id"],"name":x["name"],"owner":x["owner_nickname"],
          "players":x["players"],"capacity":team_capacity(x["mode"])*MAX_TEAM,
          "mode":x["mode"],"status":x["status"],"ready":x["ready_count"] or 0,"full":x["players"]>=team_capacity(x["mode"])*MAX_TEAM})
    return result


def lobby_view(c, lobby_id, viewer_id):
    lobby=c.execute("SELECT * FROM lobbies WHERE id=?",(lobby_id,)).fetchone()
    if not lobby: raise ValueError("로비를 찾을 수 없습니다.")
    if lobby["visibility"]=="private" and not c.execute("SELECT 1 FROM lobby_members WHERE lobby_id=? AND account_id=?",(lobby_id,viewer_id)).fetchone():
        raise PermissionError("비공개 매치 로비에 참가한 계정만 볼 수 있습니다.")
    members=[]
    for x in c.execute("SELECT m.*,a.nickname,a.rating,a.avatar_id FROM lobby_members m JOIN accounts a ON a.id=m.account_id WHERE m.lobby_id=? ORDER BY m.team_no,m.joined_at",(lobby_id,)):
        members.append({"id":x["account_id"],"nickname":x["nickname"],"rating":x["rating"],"avatar_id":x["avatar_id"],"tier":systems.tier_for(x["rating"]),"team_no":x["team_no"],"operator":bool(x["is_operator"]),"ready":bool(x["ready"]),"level":x["level"]})
    now=time.time()
    swaps=[dict(x) for x in c.execute("SELECT id,requester_id,target_id,expires_at,status FROM team_swap_requests WHERE lobby_id=? AND status='pending' AND expires_at>? AND target_id=?",(lobby_id,now,viewer_id))]
    identities=[dict(x) for x in c.execute("SELECT team_no,captain_id,name,candidates_json,selected_logo FROM lobby_team_identity WHERE lobby_id=? ORDER BY team_no",(lobby_id,))]
    for item in identities:
        item["candidates"]=json.loads(item.pop("candidates_json") or "[]")
    all_ready=c.execute("SELECT COUNT(*) FROM lobby_members WHERE lobby_id=? AND is_operator=0 AND ready=0",(lobby_id,)).fetchone()[0]==0
    outgoing=[dict(x) for x in c.execute("SELECT id,requester_id,target_id,expires_at,status FROM team_swap_requests WHERE lobby_id=? AND status='pending' AND expires_at>? AND requester_id=?",(lobby_id,now,viewer_id))]
    votes={str(x["team_no"]):x["votes"] for x in c.execute("SELECT team_no,COUNT(*) AS votes FROM captain_votes WHERE lobby_id=? GROUP BY team_no",(lobby_id,))}
    my_vote=c.execute("SELECT candidate_id FROM captain_votes WHERE lobby_id=? AND voter_id=?",(lobby_id,viewer_id)).fetchone()
    operator=next((x["id"] for x in members if x["operator"]),None)
    return {"id":lobby["id"],"name":lobby["name"],"mode":lobby["mode"],"owner_id":lobby["owner_id"],"status":lobby["status"],"phase":lobby["phase"],"phase_ends_at":lobby["phase_ends_at"],"stage_no":lobby["stage_no"],"capacity":team_capacity(lobby["mode"])*MAX_TEAM,"team_slots":lobby_team_slots(c,lobby_id,lobby["mode"]),"rumble_rounds":systems.rumble_rounds(c,lobby_id),"final_stage":systems.rumble_rounds(c,lobby_id)+1,"estimated_team_count":max(3,len({x["team_no"] for x in members if not x["operator"]})) if lobby["mode"]=="challenge" else 2,"estimated_seconds":systems.estimated_seconds(max(3,len({x["team_no"] for x in members if not x["operator"]}))) if lobby["mode"]=="challenge" else 370,"visibility":lobby["visibility"],"members":members,"swaps":swaps,"outgoing_swaps":outgoing,"is_owner":lobby["owner_id"]==viewer_id,"identities":identities,"votes":votes,"my_vote":my_vote[0] if my_vote else None,"operator_id":operator,"is_operator":any(x["id"]==viewer_id and x["operator"] for x in members),"all_ready":all_ready}


def create_lobby(c, account_id, name, mode):
    name=" ".join(name.split()) if isinstance(name,str) else ""
    if not 2<=len(name)<=40: raise ValueError("로비 이름은 2~40자로 입력하세요.")
    if mode not in ("normal","challenge"): raise ValueError("게임 모드를 선택하세요.")
    if c.execute("SELECT 1 FROM lobby_members m JOIN lobbies l ON l.id=m.lobby_id WHERE m.account_id=? AND l.status NOT IN ('closed','cancelled')",(account_id,)).fetchone():
        raise ValueError("이미 참가 중인 게임이 있습니다.")
    cap=MAX_TEAM*team_capacity(mode)
    lobby_id=c.execute("INSERT INTO lobbies(name,mode,owner_id,created_at) VALUES (?,?,?,?)",(name,mode,account_id,time.time())).lastrowid
    c.execute("INSERT INTO lobby_members(lobby_id,account_id,team_no,joined_at) VALUES (?,?,1,?)",(lobby_id,account_id,time.time()))
    return lobby_id


def join_lobby(c, lobby_id, account_id, team_no=None):
    lobby=c.execute("SELECT * FROM lobbies WHERE id=? AND status='waiting' AND visibility='public'",(lobby_id,)).fetchone()
    if not lobby: raise ValueError("참가할 수 있는 공개 로비가 아닙니다.")
    if c.execute("SELECT 1 FROM lobby_members m JOIN lobbies l ON l.id=m.lobby_id WHERE m.account_id=? AND l.status NOT IN ('closed','cancelled')",(account_id,)).fetchone(): raise ValueError("이미 참가 중인 게임이 있습니다.")
    teams=min(8,max(3,(sum(team_count(c,lobby_id,i) for i in range(1,9))+5)//5)) if lobby["mode"]=="challenge" else 2
    available=[i for i in range(1,teams+1) if team_count(c,lobby_id,i)<MAX_TEAM]
    if not available: raise ValueError("로비 인원이 가득 찼습니다.")
    if team_no not in available: team_no=min(available,key=lambda i:(team_count(c,lobby_id,i),i))
    c.execute("INSERT INTO lobby_members(lobby_id,account_id,team_no,joined_at) VALUES (?,?,?,?)",(lobby_id,account_id,team_no,time.time()))


def move_team(c, lobby_id, account_id, team_no):
    lobby=c.execute("SELECT * FROM lobbies WHERE id=? AND status='waiting'",(lobby_id,)).fetchone()
    member=c.execute("SELECT * FROM lobby_members WHERE lobby_id=? AND account_id=?",(lobby_id,account_id)).fetchone()
    if not lobby or lobby["visibility"]=="private" or not member or member["is_operator"] or member["ready"]: raise ValueError("준비 전인 참가자만 팀을 옮길 수 있습니다.")
    if not 1<=team_no<=team_capacity(lobby["mode"]) or team_count(c,lobby_id,team_no)>=MAX_TEAM: raise ValueError("선택한 팀에 자리가 없습니다.")
    c.execute("UPDATE lobby_members SET team_no=? WHERE lobby_id=? AND account_id=?",(team_no,lobby_id,account_id))


def set_ready(c,lobby_id,account_id,ready):
    lobby=c.execute("SELECT * FROM lobbies WHERE id=? AND status='waiting'",(lobby_id,)).fetchone()
    member=c.execute("SELECT * FROM lobby_members WHERE lobby_id=? AND account_id=?",(lobby_id,account_id)).fetchone()
    if not lobby or not member or member["is_operator"]: raise ValueError("대기 중인 로비 참가자가 아닙니다.")
    c.execute("UPDATE lobby_members SET ready=? WHERE lobby_id=? AND account_id=?",(int(bool(ready)),lobby_id,account_id))


def request_swap(c,lobby_id,requester_id,target_id):
    lobby=c.execute("SELECT * FROM lobbies WHERE id=? AND status='waiting'",(lobby_id,)).fetchone()
    a=c.execute("SELECT * FROM lobby_members WHERE lobby_id=? AND account_id=?",(lobby_id,requester_id)).fetchone()
    b=c.execute("SELECT * FROM lobby_members WHERE lobby_id=? AND account_id=?",(lobby_id,target_id)).fetchone()
    if not lobby or lobby["visibility"]=="private" or not a or not b or a["is_operator"] or b["is_operator"] or a["team_no"]==b["team_no"] or a["ready"] or b["ready"]: raise ValueError("서로 다른 팀의 준비 전 참가자끼리만 교체를 요청할 수 있습니다.")
    if team_count(c,lobby_id,a["team_no"])!=MAX_TEAM or team_count(c,lobby_id,b["team_no"])!=MAX_TEAM: raise ValueError("양 팀이 모두 다 찬 뒤에 교체를 요청할 수 있습니다.")
    c.execute("UPDATE team_swap_requests SET status='expired' WHERE lobby_id=? AND status='pending' AND expires_at<=?",(lobby_id,time.time()))
    expiry=time.time()+10
    return c.execute("INSERT INTO team_swap_requests(lobby_id,requester_id,target_id,expires_at) VALUES (?,?,?,?)",(lobby_id,requester_id,target_id,expiry)).lastrowid


def respond_swap(c, request_id, target_id, accept):
    row=c.execute("SELECT * FROM team_swap_requests WHERE id=? AND target_id=? AND status='pending'",(request_id,target_id)).fetchone()
    if not row or row["expires_at"]<time.time(): raise ValueError("팀 교체 요청 시간이 만료되었습니다.")
    if accept:
        a=c.execute("SELECT team_no,ready FROM lobby_members WHERE lobby_id=? AND account_id=?",(row["lobby_id"],row["requester_id"])).fetchone()
        b=c.execute("SELECT team_no,ready FROM lobby_members WHERE lobby_id=? AND account_id=?",(row["lobby_id"],target_id)).fetchone()
        if not a or not b or a["ready"] or b["ready"]: raise ValueError("이미 준비한 참가자는 팀을 바꿀 수 없습니다.")
        if a["team_no"]==b["team_no"]: raise ValueError("두 참가자는 이미 같은 팀입니다.")
        c.execute("UPDATE lobby_members SET team_no=? WHERE lobby_id=? AND account_id=?",(b["team_no"],row["lobby_id"],row["requester_id"]))
        c.execute("UPDATE lobby_members SET team_no=? WHERE lobby_id=? AND account_id=?",(a["team_no"],row["lobby_id"],target_id))
    c.execute("UPDATE team_swap_requests SET status=? WHERE id=?",("accepted" if accept else "declined",request_id))


def start_lobby(c,lobby_id,account_id):
    lobby=c.execute("SELECT * FROM lobbies WHERE id=? AND status='waiting'",(lobby_id,)).fetchone()
    if not lobby or lobby["owner_id"]!=account_id: raise ValueError("로비 생성자만 게임을 시작할 수 있습니다.")
    members=list(c.execute("SELECT * FROM lobby_members WHERE lobby_id=? AND is_operator=0",(lobby_id,)))
    team_ids=sorted({m['team_no'] for m in members})
    if lobby['mode']=='challenge':
        if not 3<=len(team_ids)<=8 or any(team_count(c,lobby_id,t)!=MAX_TEAM for t in team_ids):
            raise ValueError('챌린지는 3~8팀, 각 팀 5명이 필요합니다. 빈 팀은 참가 팀에 포함되지 않습니다.')
        rounds=systems.round_robin(team_ids)
        from problems import PROBLEMS
        metadata=systems.catalog()
        for level in range(1,6):
            if sum(p['id'] in metadata and metadata[p['id']]['stage']=='rumble' and level in metadata[p['id']]['eligible_levels'] for p in PROBLEMS)<len(rounds) or sum(p['id'] in metadata and metadata[p['id']]['stage']=='final' and level in metadata[p['id']]['eligible_levels'] for p in PROBLEMS)<2:
                raise ValueError(f'레벨 {level}에 필요한 중복 없는 문제 풀이 부족합니다. 카탈로그를 추가하세요.')
        c.execute('UPDATE lobbies SET schedule_json=? WHERE id=?',(json.dumps(rounds),lobby_id))
    elif len(members)!=10 or any(team_count(c,lobby_id,t)!=MAX_TEAM for t in (1,2)):
        raise ValueError('일반 모드는 양 팀이 각각 5명이어야 시작할 수 있습니다.')
    if any(not m["ready"] for m in members if m["account_id"]!=account_id): raise ValueError("로비 생성자를 제외한 모든 참가자가 준비해야 합니다.")
    phase="captain_vote" if lobby["mode"]=="challenge" else "level_select"
    duration=10 if phase=="captain_vote" else 30
    lobby=c.execute("UPDATE lobbies SET status='running',phase=?,phase_ends_at=? WHERE id=? RETURNING *",(phase,time.time()+duration,lobby_id)).fetchone()
    return lobby


def choose_level(c,lobby_id,account_id,level):
    if type(level) is not int or level not in range(1,6):raise ValueError('레벨은 1~5 중에서 선택하세요.')
    lobby=c.execute('SELECT phase FROM lobbies WHERE id=?',(lobby_id,)).fetchone()
    member=c.execute('SELECT team_no,is_operator FROM lobby_members WHERE lobby_id=? AND account_id=?',(lobby_id,account_id)).fetchone()
    if not lobby or lobby['phase'] not in ('waiting','level_select','operator_start','break','operator_results') or not member or member['is_operator']:raise ValueError('현재 레벨을 선택할 수 없습니다.')
    if c.execute('SELECT 1 FROM lobby_members WHERE lobby_id=? AND team_no=? AND account_id!=? AND level=? AND is_operator=0',(lobby_id,member['team_no'],account_id,level)).fetchone():raise ValueError('같은 팀원이 이미 선택한 레벨입니다.')
    c.execute('UPDATE lobby_members SET level=? WHERE lobby_id=? AND account_id=?',(level,lobby_id,account_id))


def assign_levels(c,lobby_id):
    import random
    teams=[r[0] for r in c.execute('SELECT DISTINCT team_no FROM lobby_members WHERE lobby_id=? AND is_operator=0',(lobby_id,))]
    for team in teams:
        used=set();pending=[]
        for member in c.execute('SELECT account_id,level FROM lobby_members WHERE lobby_id=? AND team_no=? AND is_operator=0 ORDER BY joined_at',(lobby_id,team)).fetchall():
            if member['level'] in range(1,6) and member['level'] not in used:used.add(member['level'])
            else:pending.append(member['account_id'])
        remaining=list(set(range(1,6))-used);random.shuffle(remaining)
        for uid,level in zip(pending,remaining):c.execute('UPDATE lobby_members SET level=? WHERE lobby_id=? AND account_id=?',(level,lobby_id,uid))


def join_operator(c,lobby_id,account_id):
    lobby=c.execute("SELECT * FROM lobbies WHERE id=? AND status='waiting' AND mode='challenge'",(lobby_id,)).fetchone()
    if not lobby:raise ValueError("운영자가 참가할 수 있는 챌린지 로비가 아닙니다.")
    if c.execute("SELECT 1 FROM lobby_members WHERE lobby_id=? AND is_operator=1",(lobby_id,)).fetchone():raise ValueError("운영자 자리가 이미 찼습니다.")
    if c.execute("SELECT 1 FROM lobby_members m JOIN lobbies l ON l.id=m.lobby_id WHERE m.account_id=? AND l.status NOT IN ('closed','cancelled')",(account_id,)).fetchone():raise ValueError("다른 로비나 경기에 이미 참가 중입니다.")
    c.execute("INSERT INTO lobby_members(lobby_id,account_id,team_no,is_operator,joined_at) VALUES (?,?,0,1,?)",(lobby_id,account_id,time.time()))


def cast_captain_vote(c,lobby_id,voter_id,candidate_id):
    lobby=c.execute("SELECT * FROM lobbies WHERE id=? AND phase='captain_vote'",(lobby_id,)).fetchone()
    voter=c.execute("SELECT team_no,is_operator FROM lobby_members WHERE lobby_id=? AND account_id=?",(lobby_id,voter_id)).fetchone()
    candidate=c.execute("SELECT team_no,is_operator FROM lobby_members WHERE lobby_id=? AND account_id=?",(lobby_id,candidate_id)).fetchone()
    if not lobby or not voter or not candidate or voter["is_operator"] or candidate["is_operator"] or voter["team_no"]!=candidate["team_no"]:raise ValueError("같은 팀 참가자 중에서 팀장을 투표하세요.")
    c.execute("INSERT OR REPLACE INTO captain_votes(lobby_id,team_no,voter_id,candidate_id) VALUES (?,?,?,?)",(lobby_id,voter["team_no"],voter_id,candidate_id))


def resolve_captains(c,lobby_id):
    import random
    c.execute("DELETE FROM lobby_team_identity WHERE lobby_id=?",(lobby_id,))
    for team in [r[0] for r in c.execute("SELECT DISTINCT team_no FROM lobby_members WHERE lobby_id=? AND is_operator=0 ORDER BY team_no",(lobby_id,))]:
        members=[x[0] for x in c.execute("SELECT account_id FROM lobby_members WHERE lobby_id=? AND team_no=? AND is_operator=0",(lobby_id,team))]
        votes=list(c.execute("SELECT candidate_id,COUNT(*) AS n FROM captain_votes WHERE lobby_id=? AND team_no=? GROUP BY candidate_id",(lobby_id,team)))
        highest=max((x["n"] for x in votes),default=0)
        winners=[x["candidate_id"] for x in votes if x["n"]==highest] if highest else members
        captain=random.choice(winners)
        c.execute("INSERT INTO lobby_team_identity(lobby_id,team_no,captain_id) VALUES (?,?,?)",(lobby_id,team,captain))
    c.execute("UPDATE lobbies SET phase='team_setup',phase_ends_at=? WHERE id=?",(time.time()+60,lobby_id))


def progress(c,lobby_id):
    """Advance timed lobby phases. Returns the updated lobby row."""
    import random
    lobby=c.execute("SELECT * FROM lobbies WHERE id=?",(lobby_id,)).fetchone()
    if not lobby or lobby["phase_ends_at"] is None or time.time()<lobby["phase_ends_at"]:
        return lobby
    phase=lobby["phase"]
    if phase=="captain_vote":
        resolve_captains(c,lobby_id)
    elif phase=="team_setup":
        operator=c.execute("SELECT 1 FROM lobby_members WHERE lobby_id=? AND is_operator=1",(lobby_id,)).fetchone()
        if operator:
            c.execute("UPDATE lobbies SET phase='operator_start',phase_ends_at=NULL WHERE id=?",(lobby_id,))
        else:
            c.execute("UPDATE lobbies SET phase='countdown',phase_ends_at=? WHERE id=?",(time.time()+10,lobby_id))
    elif phase=="countdown":
        if lobby["mode"]=="normal":
            c.execute("UPDATE lobbies SET phase='level_select',phase_ends_at=? WHERE id=?",(time.time()+30,lobby_id))
        else:
            stage=lobby["stage_no"]+1
            duration=600 if lobby["mode"]=="challenge" and systems.is_final(c,lobby_id,stage) else 300
            c.execute("UPDATE lobbies SET stage_no=?,phase='live',phase_ends_at=? WHERE id=?",(stage,time.time()+duration,lobby_id))
    elif phase=="level_select":
        assign_levels(c,lobby_id)
        c.execute("UPDATE lobbies SET phase='start_countdown',phase_ends_at=? WHERE id=?",(time.time()+10,lobby_id))
    elif phase=="start_countdown":
        c.execute("UPDATE lobbies SET phase='live',phase_ends_at=? WHERE id=?",(time.time()+300,lobby_id))
    elif phase=="live":
        duration=30 if lobby["mode"]=="normal" or systems.is_final(c,lobby_id,lobby["stage_no"]) else 20
        c.execute("UPDATE lobbies SET phase='results',status='results',phase_ends_at=? WHERE id=?",(time.time()+duration,lobby_id))
    elif phase=="results":
        if lobby["mode"]=="challenge" and lobby["stage_no"]==systems.rumble_rounds(c,lobby_id) and not lobby["finalists_json"]:
            totals=list(c.execute('SELECT team_no,win_points FROM lobby_team_totals WHERE lobby_id=? ORDER BY win_points DESC,team_no',(lobby_id,)))
            if len(totals)>=3 and totals[1]['win_points']==totals[2]['win_points']:
                c.execute("UPDATE lobbies SET phase='finalist_choice',status='running',phase_ends_at=NULL WHERE id=?",(lobby_id,))
            elif c.execute("SELECT 1 FROM lobby_members WHERE lobby_id=? AND is_operator=1",(lobby_id,)).fetchone():
                c.execute("UPDATE lobbies SET phase='operator_results',phase_ends_at=NULL WHERE id=?",(lobby_id,))
            else:
                c.execute("UPDATE lobbies SET status='running',phase='break',phase_ends_at=? WHERE id=?",(time.time()+20,lobby_id))
        elif lobby["mode"]=="challenge" and lobby["stage_no"]<systems.rumble_rounds(c,lobby_id)+1:
            if c.execute("SELECT 1 FROM lobby_members WHERE lobby_id=? AND is_operator=1",(lobby_id,)).fetchone():
                c.execute("UPDATE lobbies SET phase='operator_results',phase_ends_at=NULL WHERE id=?",(lobby_id,))
            else:c.execute("UPDATE lobbies SET status='running',phase='break',phase_ends_at=? WHERE id=?",(time.time()+20,lobby_id))
        else:
            if lobby["mode"]=="challenge" and c.execute("SELECT 1 FROM lobby_members WHERE lobby_id=? AND is_operator=1",(lobby_id,)).fetchone():
                c.execute("UPDATE lobbies SET phase='operator_results',phase_ends_at=NULL WHERE id=?",(lobby_id,))
            else:
                c.execute("UPDATE lobbies SET status='closed',phase='closed',phase_ends_at=NULL WHERE id=?",(lobby_id,))
                c.execute("DELETE FROM matchmaking_queue WHERE batch_lobby_id=?",(lobby_id,))
    elif phase=="break":
        c.execute("UPDATE lobbies SET phase='countdown',phase_ends_at=? WHERE id=?",(time.time()+10,lobby_id))
    return c.execute("SELECT * FROM lobbies WHERE id=?",(lobby_id,)).fetchone()


def operator_start(c,lobby_id,account_id):
    lobby=c.execute("SELECT * FROM lobbies WHERE id=? AND mode='challenge' AND phase='operator_start'",(lobby_id,)).fetchone()
    member=c.execute("SELECT is_operator FROM lobby_members WHERE lobby_id=? AND account_id=?",(lobby_id,account_id)).fetchone()
    if not lobby or not member or not member["is_operator"]:
        raise ValueError("챌린지 운영자 자리에서만 시작할 수 있습니다.")
    c.execute("UPDATE lobbies SET phase='countdown',phase_ends_at=? WHERE id=?",(time.time()+10,lobby_id))


def operator_close(c,lobby_id,account_id):
    lobby=c.execute("SELECT phase FROM lobbies WHERE id=?",(lobby_id,)).fetchone()
    member=c.execute("SELECT is_operator FROM lobby_members WHERE lobby_id=? AND account_id=?",(lobby_id,account_id)).fetchone()
    if not lobby or not member or not member["is_operator"] or lobby["phase"]!="live":
        raise ValueError("진행 중인 챌린지 경기를 운영자만 종료할 수 있습니다.")
    c.execute("UPDATE lobbies SET phase='results',status='results',phase_ends_at=? WHERE id=?",(time.time()+20,lobby_id))


def operator_next(c,lobby_id,account_id):
    lobby=c.execute("SELECT * FROM lobbies WHERE id=? AND mode='challenge' AND phase='operator_results'",(lobby_id,)).fetchone()
    member=c.execute("SELECT is_operator FROM lobby_members WHERE lobby_id=? AND account_id=?",(lobby_id,account_id)).fetchone()
    if not lobby or not member or not member["is_operator"]:raise ValueError("매치 결과 화면에서 운영자만 다음 단계로 진행할 수 있습니다.")
    if lobby["stage_no"]>=systems.rumble_rounds(c,lobby_id)+1:
        c.execute("UPDATE lobbies SET status='closed',phase='closed',phase_ends_at=NULL WHERE id=?",(lobby_id,))
        return
    c.execute("UPDATE lobbies SET status='running',phase='break',phase_ends_at=? WHERE id=?",(time.time()+20,lobby_id))
