"""Tournament prototype. Public deployments require an isolated judge; see README."""
import base64
import hashlib
import html
import hmac
import json
import os
import secrets
import sqlite3
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import RLock
from urllib.parse import urlparse

from problems import HINT_COST, PROBLEMS, REWARD, expected_outputs, judge_inputs, public_problem

ROOT = Path(__file__).resolve().parent
DATA = Path(os.environ.get("RUMBLE_DATA_DIR", str(ROOT / "data")))
DB = DATA / "rumble.sqlite3"
LOCK = RLock()
LOOKUP = {p["id"]: p for p in PROBLEMS}
ANSWERS = {p["id"]: expected_outputs(p) for p in PROBLEMS}
ROUNDS = [[(1, 2), (3, 4)], [(1, 3), (2, 5)], [(1, 4), (3, 5)],
          [(1, 5), (2, 4)], [(2, 3), (4, 5)]]
TEAM_NAMES = ["블루", "레드", "골드", "바이올렛", "민트"]
ROUND_SECONDS = 300
FRONTEND_ORIGIN = os.environ.get("FRONTEND_ORIGIN", "").rstrip("/")
LOGO_PROMPT = ("Create an original esports tournament team emblem for the name '{name}'. "
               "Visual direction: bold symmetrical heraldic silhouette, sharp geometric animal or "
               "mythic motif, confident negative space, compact vector-like shapes, high contrast, "
               "premium competitive gaming identity, dark backdrop, clean edges, legible at 64px. "
               "Use only the supplied team name as text, if any. Make an independent design: "
               "do not reproduce or closely imitate any existing esports team logo, trademark, "
               "mascot, crest, lettermark or distinctive color arrangement. Square composition.")


def access_token(role, team_id=0, level=0):
    """Keep access codes stable across ephemeral free-service restarts."""
    seed = os.environ.get("ACCESS_SEED")
    if not seed:
        return secrets.token_urlsafe(24 if role == "admin" else 18)
    if len(seed) < 32:
        raise ValueError("ACCESS_SEED는 추측하기 어려운 32자 이상의 값으로 설정하세요.")
    label = f"code-rumble:v1:{role}:{team_id}:{level}".encode()
    digest = hmac.new(seed.encode(), label, hashlib.sha256).digest()[:24]
    return base64.urlsafe_b64encode(digest).decode().rstrip("=")


@contextmanager
def db():
    conn = sqlite3.connect(DB, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA busy_timeout=10000")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def setup():
    DATA.mkdir(parents=True, exist_ok=True)
    with db() as c:
        c.executescript("""
        CREATE TABLE IF NOT EXISTS teams(id INTEGER PRIMARY KEY, name TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY, name TEXT NOT NULL,
          team_id INTEGER, level INTEGER, token TEXT UNIQUE NOT NULL, role TEXT NOT NULL,
          profile_complete INTEGER NOT NULL DEFAULT 0);
        CREATE TABLE IF NOT EXISTS matches(id INTEGER PRIMARY KEY, round INTEGER NOT NULL,
          team_a INTEGER NOT NULL, team_b INTEGER NOT NULL, problem_set INTEGER NOT NULL,
          start_at REAL, end_at REAL, status TEXT NOT NULL DEFAULT 'pending');
        CREATE TABLE IF NOT EXISTS solves(id INTEGER PRIMARY KEY, match_id INTEGER NOT NULL,
          team_id INTEGER NOT NULL, user_id INTEGER NOT NULL, problem_id TEXT NOT NULL,
          at REAL NOT NULL, win_points INTEGER NOT NULL, solve_points INTEGER NOT NULL,
          UNIQUE(match_id, team_id, problem_id));
        CREATE TABLE IF NOT EXISTS submissions(id INTEGER PRIMARY KEY, match_id INTEGER NOT NULL,
          user_id INTEGER NOT NULL, problem_id TEXT NOT NULL, at REAL NOT NULL,
          verdict TEXT NOT NULL, passed INTEGER NOT NULL, total INTEGER NOT NULL);
        CREATE TABLE IF NOT EXISTS purchases(id INTEGER PRIMARY KEY, match_id INTEGER NOT NULL,
          team_id INTEGER NOT NULL, user_id INTEGER NOT NULL, problem_id TEXT NOT NULL,
          kind TEXT NOT NULL, detail TEXT NOT NULL, cost INTEGER NOT NULL, at REAL NOT NULL,
          UNIQUE(match_id, team_id, problem_id, kind));
        CREATE TABLE IF NOT EXISTS credits(id INTEGER PRIMARY KEY, team_id INTEGER NOT NULL,
          amount INTEGER NOT NULL, available_round INTEGER NOT NULL, reason TEXT NOT NULL,
          at REAL NOT NULL);
        CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY, value TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS round_preferences(round INTEGER NOT NULL, team_id INTEGER NOT NULL,
          user_id INTEGER NOT NULL, level INTEGER NOT NULL CHECK(level BETWEEN 1 AND 5),
          PRIMARY KEY(round,user_id), UNIQUE(round,team_id,level));
        CREATE TABLE IF NOT EXISTS round_assignments(round INTEGER NOT NULL, team_id INTEGER NOT NULL,
          user_id INTEGER NOT NULL, level INTEGER NOT NULL CHECK(level BETWEEN 1 AND 5),
          PRIMARY KEY(round,user_id), UNIQUE(round,team_id,level));
        CREATE TABLE IF NOT EXISTS logo_candidates(team_id INTEGER NOT NULL, slot INTEGER NOT NULL,
          source TEXT NOT NULL, data_uri TEXT NOT NULL, PRIMARY KEY(team_id,slot));
        CREATE INDEX IF NOT EXISTS idx_credits_team_round ON credits(team_id,available_round);
        CREATE INDEX IF NOT EXISTS idx_solves_match_problem ON solves(match_id,problem_id);
        """)
        if "profile_complete" not in {row[1] for row in c.execute("PRAGMA table_info(users)")}:
            c.execute("ALTER TABLE users ADD COLUMN profile_complete INTEGER NOT NULL DEFAULT 0")
            c.execute("UPDATE users SET profile_complete=1 WHERE role='admin'")
        team_columns = {row[1] for row in c.execute("PRAGMA table_info(teams)")}
        for column, definition in (("captain_user_id", "INTEGER"), ("logo_data", "TEXT"),
                                   ("configured", "INTEGER NOT NULL DEFAULT 0"),
                                   ("named", "INTEGER NOT NULL DEFAULT 0")):
            if column not in team_columns:
                c.execute(f"ALTER TABLE teams ADD COLUMN {column} {definition}")
        if c.execute("SELECT 1 FROM users LIMIT 1").fetchone():
            # Migrate fully enrolled teams from versions that did not have captains.
            for team in c.execute("SELECT id FROM teams WHERE captain_user_id IS NULL"):
                members = c.execute("SELECT id FROM users WHERE team_id=? AND profile_complete=1 ORDER BY id",
                                    (team["id"],)).fetchall()
                if len(members) == 5:
                    c.execute("UPDATE teams SET captain_user_id=? WHERE id=?", (members[-1]["id"], team["id"]))
            # Older prototypes stored 20-minute deadlines. Retain scores and
            # accounts while shortening any currently open match on restart.
            c.execute("""UPDATE matches SET end_at=start_at+?
                WHERE status='open' AND start_at IS NOT NULL
                  AND (end_at IS NULL OR ABS(end_at-start_at-?)>0.5)""",
                      (ROUND_SECONDS, ROUND_SECONDS))
            c.execute("""UPDATE matches SET end_at=MIN(start_at+?,?)
                WHERE status='closed' AND start_at IS NOT NULL
                  AND end_at>start_at+?+0.5""",
                      (ROUND_SECONDS, time.time(), ROUND_SECONDS))
            for m in c.execute("SELECT round,team_a,team_b FROM matches WHERE status!='pending'"):
                for team in (m["team_a"], m["team_b"]):
                    for player in c.execute("SELECT id,level FROM users WHERE team_id=?", (team,)):
                        c.execute("""INSERT OR IGNORE INTO round_assignments(round,team_id,user_id,level)
                            VALUES (?,?,?,?)""", (m["round"], team, player["id"], player["level"]))
            r = current_round(c)
            c.execute("UPDATE credits SET available_round=? WHERE amount>0 AND available_round=?",
                      (r, r+1))
            return
        access = {"admin": None, "teams": {}}
        token = access_token("admin")
        c.execute("INSERT INTO users(name,team_id,level,token,role,profile_complete) VALUES (?,?,?,?,?,1)",
                  ("운영자", None, None, token, "admin"))
        access["admin"] = token
        for team_id, name in enumerate(TEAM_NAMES, 1):
            c.execute("INSERT INTO teams(id,name) VALUES (?,?)", (team_id, name))
            access["teams"][name] = []
            for level in range(1, 6):
                t = access_token("player", team_id, level)
                player = f"{name} {level}번"
                c.execute("INSERT INTO users(name,team_id,level,token,role) VALUES (?,?,?,?,?)",
                          (player, team_id, level, t, "player"))
                access["teams"][name].append({"name": player, "level": level, "code": t})
        for r, pairs in enumerate(ROUNDS, 1):
            for a, b in pairs:
                c.execute("INSERT INTO matches(round,team_a,team_b,problem_set) VALUES (?,?,?,?)",
                          (r, a, b, (r - 1) % 3 + 1))
        c.execute("INSERT INTO settings VALUES ('round','0')")
        # Convenience credentials for the local organizer; never served by HTTP.
        (DATA / "access.json").write_text(json.dumps(access, ensure_ascii=False, indent=2), encoding="utf-8")
        try:
            os.chmod(DATA / "access.json", 0o600)
        except OSError:
            pass
        print("운영자 코드:", token, flush=True)


def current_round(c):
    return int(c.execute("SELECT value FROM settings WHERE key='round'").fetchone()[0])


def credit_balance(c, team, round_no):
    return c.execute("SELECT COALESCE(SUM(amount),0) FROM credits WHERE team_id=? AND available_round<=?",
                     (team, round_no)).fetchone()[0]


def standings(c):
    rows = c.execute("""SELECT t.id,t.name,
      COALESCE(SUM(s.win_points),0) AS points,
      COUNT(s.id) AS solved FROM teams t
      LEFT JOIN solves s ON t.id=s.team_id AND s.match_id IN
        (SELECT id FROM matches WHERE round<=5)
      GROUP BY t.id""").fetchall()
    wins = {i: 0 for i in range(1, 6)}
    for m in c.execute("SELECT * FROM matches WHERE round<=5 AND status='closed'"):
        totals = [c.execute("SELECT COALESCE(SUM(win_points),0) FROM solves WHERE match_id=? AND team_id=?",
                            (m["id"], team)).fetchone()[0] for team in (m["team_a"], m["team_b"])]
        if totals[0] != totals[1]:
            wins[(m["team_a"], m["team_b"])[totals[1] > totals[0]]] += 1
    result = [dict(r) | {"wins": wins[r["id"]], "credit": credit_balance(c, r["id"], current_round(c))}
              for r in rows]
    return sorted(result, key=lambda x: (-x["points"], -x["wins"], -x["solved"], x["id"]))


def match_for(c, team, round_no):
    return c.execute("SELECT * FROM matches WHERE round=? AND (team_a=? OR team_b=?)",
                     (round_no, team, team)).fetchone()


def eligible_teams(c, round_no):
    if 1 <= round_no <= 5:
        return {team for pair in ROUNDS[round_no-1] for team in pair}
    if round_no == 6 and current_round(c) == 5:
        rows = c.execute("SELECT status,end_at FROM matches WHERE round=5").fetchall()
        if len(rows) == 2 and all(row["status"] == "closed" or (row["end_at"] or 0) <= time.time() for row in rows):
            return {entry["id"] for entry in standings(c)[:2]}
    return set()


def assign_round(c, round_no):
    """Freeze preferences, then randomly distribute all unclaimed levels."""
    for match in c.execute("SELECT team_a,team_b FROM matches WHERE round=?", (round_no,)):
        for team in (match["team_a"], match["team_b"]):
            players = [row["id"] for row in c.execute("SELECT id FROM users WHERE team_id=? ORDER BY id", (team,))]
            if len(players) != 5:
                raise ValueError("팀당 선수가 정확히 5명이어야 합니다.")
            picked = [(row["user_id"], row["level"]) for row in c.execute(
                "SELECT user_id,level FROM round_preferences WHERE round=? AND team_id=?", (round_no, team))]
            remaining_players = [user_id for user_id in players if user_id not in {p[0] for p in picked}]
            remaining_levels = [level for level in range(1, 6) if level not in {p[1] for p in picked}]
            secrets.SystemRandom().shuffle(remaining_players)
            for user_id, level in picked + list(zip(remaining_players, remaining_levels)):
                c.execute("""INSERT INTO round_assignments(round,team_id,user_id,level)
                    VALUES (?,?,?,?)""", (round_no, team, user_id, level))


def logo_candidates(team_name):
    """Use the image API when configured; otherwise provide visibly provisional SVGs."""
    key = os.environ.get("OPENAI_API_KEY")
    if key:
        payload = json.dumps({"model": os.environ.get("OPENAI_IMAGE_MODEL", "gpt-image-1"),
                              "prompt": LOGO_PROMPT.format(name=team_name), "n": 3,
                              "size": "1024x1024"}).encode()
        request = urllib.request.Request("https://api.openai.com/v1/images/generations", data=payload,
                                         headers={"Authorization": "Bearer " + key,
                                                  "Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(request, timeout=120) as response:
                images = json.load(response).get("data", [])
            if len(images) != 3 or any(not x.get("b64_json") for x in images):
                raise ValueError("로고 이미지 세 개를 받지 못했습니다.")
            return [("AI 생성", "data:image/png;base64," + x["b64_json"]) for x in images]
        except (urllib.error.URLError, ValueError) as exc:
            raise ValueError("로고 생성에 실패했습니다. API 설정을 확인한 뒤 다시 시도하세요.") from exc
    palette = [("#61d6ee", "#101f3d"), ("#ecb960", "#34304d"), ("#dc8bff", "#27334e")]
    initial = html.escape(team_name[:2])
    result = []
    for index, (accent, shade) in enumerate(palette):
        shapes = [f'<path d="M64 10 110 31 105 92 64 119 23 92 18 31Z" fill="{shade}" stroke="{accent}" stroke-width="5"/>',
                  f'<path d="M64 13 111 45 94 110 34 110 17 45Z" fill="{shade}" stroke="{accent}" stroke-width="5"/>',
                  f'<path d="M64 8 114 35 105 97 64 120 23 97 14 35Z" fill="{shade}" stroke="{accent}" stroke-width="5"/>']
        svg = f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 128 128">{shapes[index]}<text x="64" y="78" text-anchor="middle" font-family="sans-serif" font-weight="900" font-size="38" fill="{accent}">{initial}</text></svg>'
        result.append(("임시 로고", "data:image/svg+xml;base64," + base64.b64encode(svg.encode()).decode()))
    return result


def snapshot(c, user):
    r = current_round(c)
    active = c.execute("SELECT * FROM matches WHERE round=? ORDER BY id", (r,)).fetchall()
    own = match_for(c, user["team_id"], r) if user["role"] == "player" else None
    m = own if own else None
    assigned = c.execute("SELECT level FROM round_assignments WHERE round=? AND user_id=?",
                         (r, user["id"])).fetchone() if m else None
    level = assigned["level"] if assigned else None
    picks = [public_problem(p) | {"reward": REWARD[p["level"]], "sample_input": judge_inputs(p)[0],
                                    "sample_output": ANSWERS[p["id"]][0]}
             for p in PROBLEMS if m and p["set"] == m["problem_set"] and
             p["level"] == level]
    teams = {row["id"]: dict(row) for row in c.execute("SELECT * FROM teams")}
    def to_match(row):
        return dict(row) | {"team_a_name": teams[row["team_a"]]["name"],
                            "team_b_name": teams[row["team_b"]]["name"],
                            "scores": {str(t): c.execute("SELECT COALESCE(SUM(win_points),0) FROM solves WHERE match_id=? AND team_id=?",
                                                      (row["id"], t)).fetchone()[0] for t in (row["team_a"], row["team_b"])}}
    solves = [dict(s) for s in c.execute("SELECT team_id,problem_id,win_points,at FROM solves WHERE match_id=? ORDER BY at", (m["id"],))] if m else []
    hints = [dict(h) for h in c.execute("SELECT problem_id,kind,detail FROM purchases WHERE match_id=? AND team_id=?",
                                        (m["id"], user["team_id"]))] if m else []
    last_submission = None
    if m and user["role"] == "player":
        last = c.execute("""SELECT verdict,passed,total,at FROM submissions
            WHERE match_id=? AND user_id=? AND problem_id=? ORDER BY id DESC LIMIT 1""",
                         (m["id"], user["id"], f"S{m['problem_set']}-L{level}")).fetchone()
        if last:
            last_submission = dict(last)
    next_round = r+1 if r < 6 else None
    choices = None
    if user["role"] == "player" and next_round and user["team_id"] in eligible_teams(c, next_round):
        choices = {"round": next_round, "members": [dict(row) for row in c.execute("""SELECT u.id,u.name,p.level
            FROM users u LEFT JOIN round_preferences p ON p.user_id=u.id AND p.round=?
            WHERE u.team_id=? ORDER BY u.id""", (next_round, user["team_id"]))]}
    team = teams.get(user["team_id"])
    completed = c.execute("SELECT COUNT(*) FROM users WHERE team_id=? AND profile_complete=1",
                          (user["team_id"],)).fetchone()[0] if team else 0
    upcoming = match_for(c, user["team_id"], next_round) if team and next_round else None
    if not upcoming and team and next_round == 6:
        # Before finalists are known, leave the opponent undecided.
        pass
    lobby_match = to_match(upcoming) if upcoming else None
    rosters = {}
    for tid in ((user["team_id"],
                 upcoming["team_b"] if upcoming["team_a"] == user["team_id"] else upcoming["team_a"])
                if upcoming else (user["team_id"],)) if team else ():
        rosters[str(tid)] = [{"id": x["id"], "name": x["name"] if x["profile_complete"] else "참가 전",
                              "level": x["level"], "captain": x["id"] == teams[tid]["captain_user_id"],
                              "selected_level": c.execute("SELECT level FROM round_preferences WHERE round=? AND user_id=?",
                                                          (next_round, x["id"])).fetchone()[0]
                              if next_round and c.execute("SELECT 1 FROM round_preferences WHERE round=? AND user_id=?",
                                                          (next_round, x["id"])).fetchone() else None}
                             for x in c.execute("SELECT * FROM users WHERE team_id=? ORDER BY id", (tid,))]
    return {"me": {"id": user["id"], "name": user["name"], "team_id": user["team_id"],
                   "level": level, "role": user["role"], "profile_complete": bool(user["profile_complete"]),
                   "is_captain": bool(team and team["captain_user_id"] == user["id"]),
                   "captain_available": bool(team and not team["captain_user_id"]),
                   "force_captain": bool(team and not team["captain_user_id"] and completed == 4)},
            "round": r, "match": to_match(m) if m else None, "matches": [to_match(x) for x in active],
            "problems": picks, "solves": solves, "hints": hints, "last_submission": last_submission,
            "standings": standings(c), "next_selection": choices,
            "costs": HINT_COST, "rewards": REWARD, "duration": ROUND_SECONDS,
            "team_setup": ({"name": team["name"], "named": bool(team["named"]),
                            "complete": bool(team["configured"]), "logo": team["logo_data"],
                            "candidates": [dict(row) for row in c.execute(
                                "SELECT slot,source,data_uri FROM logo_candidates WHERE team_id=? ORDER BY slot",
                                (user["team_id"],))] if team["captain_user_id"] == user["id"] else []}
                           if team else None),
            "next_match": lobby_match,
            "lobby_teams": [{"id": tid, "name": teams[tid]["name"], "logo": teams[tid]["logo_data"],
                             "roster": rosters[str(tid)]} for tid in map(int, rosters)],
            "assist_enabled": bool(os.environ.get("OPENAI_API_KEY"))}


def judge(code, problem):
    if not isinstance(code, str) or not code.strip() or len(code) > 16000:
        raise ValueError("코드를 입력하세요 (최대 16,000자).")
    # No security boundary: only use with trusted participants on a local machine.
    # subprocess timeout and resource limits prevent ordinary accidental hangs.
    tests = judge_inputs(problem)
    for i, (test, expected) in enumerate(zip(tests, ANSWERS[problem["id"]]), 1):
        def limits():
            try:
                import resource
                resource.setrlimit(resource.RLIMIT_CPU, (2, 2))
                resource.setrlimit(resource.RLIMIT_AS, (256 * 1024**2, 256 * 1024**2))
                resource.setrlimit(resource.RLIMIT_FSIZE, (0, 0))
                os.setsid()
            except (ImportError, OSError, ValueError):
                pass
        try:
            with tempfile.TemporaryDirectory() as temp:
                result = subprocess.run([sys.executable, "-I", "-S", "-B", "-c", code],
                                        input=test, text=True, capture_output=True, timeout=2.5,
                                        cwd=temp, env={"PYTHONIOENCODING": "utf-8", "PATH": os.environ.get("PATH", "")},
                                        preexec_fn=limits if os.name == "posix" else None)
        except subprocess.TimeoutExpired:
            return ("시간 초과", i - 1, len(tests))
        if result.returncode:
            return ("실행 오류 (종료 코드 " + str(result.returncode) + "):\n" +
                    result.stderr[-4000:], i - 1, len(tests))
        if len(result.stdout) > 20000:
            return ("출력이 너무 깁니다", i - 1, len(tests))
        actual_lines = [" ".join(line.split()) for line in result.stdout.strip().splitlines()]
        expected_lines = [" ".join(line.split()) for line in expected.strip().splitlines()]
        if actual_lines != expected_lines:
            return ("오답", i - 1, len(tests))
    return ("정답", len(tests), len(tests))


def assist(problem, code):
    key = os.environ.get("OPENAI_API_KEY")
    if not key:
        raise ValueError("AI 도움말을 사용하려면 서버에 OPENAI_API_KEY를 설정해야 합니다.")
    if not isinstance(code, str) or not code.strip() or len(code) > 12000:
        raise ValueError("현재 작성 중인 코드를 입력하세요 (최대 12,000자).")
    prompt = ("한국어 알고리즘 튜터입니다. 다음 문제와 사용자의 Python 코드에 대해"
              " 핵심 오류나 다음 단계만 3문장 이내로 조언하세요. 정답 코드, 전체 알고리즘 구현, 숨은 테스트 정답은 공개하지 마세요.\n"
              f"문제: {problem['statement']}\n입력: {problem['input']}\n사용자 코드:\n{code}")
    payload = json.dumps({"model": os.environ.get("OPENAI_MODEL", "gpt-4.1-mini"),
                          "input": prompt, "store": False, "max_output_tokens": 250}).encode()
    req = urllib.request.Request("https://api.openai.com/v1/responses", data=payload,
                                 headers={"Authorization": "Bearer " + key, "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=18) as response:
            data = json.load(response)
        return "\n".join(c.get("text", "") for item in data.get("output", [])
                         for c in item.get("content", []) if c.get("type") == "output_text").strip()[:1500] or "응답이 비어 있습니다."
    except (urllib.error.URLError, ValueError) as exc:
        raise ValueError("AI 응답을 받지 못했습니다. 포인트는 차감되지 않았습니다.") from exc


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass

    def send(self, obj, status=200):
        data = json.dumps(obj, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.cors()
        self.end_headers()
        self.wfile.write(data)

    def cors(self):
        if FRONTEND_ORIGIN and self.headers.get("Origin") == FRONTEND_ORIGIN:
            self.send_header("Access-Control-Allow-Origin", FRONTEND_ORIGIN)
            self.send_header("Vary", "Origin")
            self.send_header("Access-Control-Allow-Headers", "Authorization, Content-Type")
            self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")

    def do_OPTIONS(self):
        if self.headers.get("Origin") != FRONTEND_ORIGIN or not FRONTEND_ORIGIN:
            self.send({"error": "허용되지 않은 출처입니다."}, 403)
            return
        self.send_response(204)
        self.cors()
        self.end_headers()

    def user(self, c):
        token = self.headers.get("Authorization", "").removeprefix("Bearer ")
        user = c.execute("SELECT * FROM users WHERE token=?", (token,)).fetchone()
        if not user:
            raise PermissionError("참가 코드를 확인하세요.")
        return user

    def do_GET(self):
        path = urlparse(self.path).path
        if path == "/api/state":
            try:
                with db() as c:
                    self.send(snapshot(c, self.user(c)))
            except PermissionError as e:
                self.send({"error": str(e)}, 401)
            return
        target = ROOT / "static" / ("index.html" if path == "/" else path.lstrip("/"))
        if target.parent != ROOT / "static" or target.suffix not in (".html", ".css", ".js", ".svg") or not target.exists():
            self.send({"error": "찾을 수 없습니다."}, 404)
            return
        data = target.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", {".html": "text/html; charset=utf-8", ".css": "text/css; charset=utf-8",
                                          ".js": "text/javascript; charset=utf-8", ".svg": "image/svg+xml"}[target.suffix])
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def do_POST(self):
        received_at = time.time()
        try:
            size = int(self.headers.get("Content-Length", 0))
            if not 0 < size < 40000:
                raise ValueError("요청 크기가 잘못되었습니다.")
            body = json.loads(self.rfile.read(size))
            path = urlparse(self.path).path
            if path == "/api/team/logos":
                # Image requests can take a minute; do not hold the database lock during the API call.
                with LOCK, db() as c:
                    user = self.user(c)
                    team = c.execute("SELECT * FROM teams WHERE id=?", (user["team_id"],)).fetchone()
                    if not team or team["captain_user_id"] != user["id"] or not team["named"]:
                        raise PermissionError("팀명 설정을 마친 팀장만 로고를 만들 수 있습니다.")
                    existing = c.execute("SELECT 1 FROM logo_candidates WHERE team_id=?", (team["id"],)).fetchone()
                    name = team["name"]
                if not existing:
                    logos = logo_candidates(name)
                    with LOCK, db() as c:
                        team = c.execute("SELECT name FROM teams WHERE id=?", (user["team_id"],)).fetchone()
                        if team and team["name"] == name:
                            for slot, (source, image) in enumerate(logos, 1):
                                c.execute("INSERT OR IGNORE INTO logo_candidates VALUES (?,?,?,?)",
                                          (user["team_id"], slot, source, image))
                with db() as c:
                    self.send(snapshot(c, self.user(c)))
                return
            with LOCK, db() as c:
                user = self.user(c)
                if path == "/api/admin/advance":
                    if user["role"] != "admin":
                        raise PermissionError("운영자만 진행할 수 있습니다.")
                    r = current_round(c)
                    if r >= 6:
                        raise ValueError("결승이 이미 종료되었습니다.")
                    c.execute("""UPDATE matches SET status='closed',end_at=MIN(end_at,?)
                        WHERE round=? AND status='open'""", (time.time(), r))
                    if r == 5:
                        top = standings(c)[:2]
                        c.execute("INSERT INTO matches(round,team_a,team_b,problem_set) VALUES (6,?,?,3)",
                                  (top[0]["id"], top[1]["id"]))
                    r += 1
                    assign_round(c, r)
                    now = time.time()
                    c.execute("UPDATE matches SET start_at=?,end_at=?,status='open' WHERE round=?",
                              (now, now + ROUND_SECONDS, r))
                    c.execute("UPDATE settings SET value=? WHERE key='round'", (str(r),))
                    c.commit()
                    self.send(snapshot(c, user))
                    return
                if path == "/api/admin/close":
                    if user["role"] != "admin":
                        raise PermissionError("운영자만 진행할 수 있습니다.")
                    r = current_round(c)
                    c.execute("""UPDATE matches SET status='closed',end_at=MIN(end_at,?)
                        WHERE round=? AND status='open'""", (time.time(), r))
                    c.commit()
                    self.send(snapshot(c, user))
                    return
                if user["role"] != "player":
                    raise PermissionError("선수 계정으로 접속하세요.")
                if path == "/api/profile":
                    if user["profile_complete"]:
                        raise ValueError("이미 이름을 설정했습니다.")
                    name = body.get("name")
                    if not isinstance(name, str):
                        raise ValueError("이름을 입력하세요.")
                    name = " ".join(name.split())
                    if not 2 <= len(name) <= 20 or not all(ch.isalnum() or ch in " _-" for ch in name):
                        raise ValueError("이름은 2~20자의 문자, 숫자, 공백, _ 또는 -만 사용할 수 있습니다.")
                    if c.execute("SELECT 1 FROM users WHERE team_id=? AND name=? AND id!=?",
                                 (user["team_id"], name, user["id"])).fetchone():
                        raise ValueError("팀 안에 같은 이름을 사용하는 선수가 있습니다.")
                    team = c.execute("SELECT captain_user_id FROM teams WHERE id=?", (user["team_id"],)).fetchone()
                    count = c.execute("SELECT COUNT(*) FROM users WHERE team_id=? AND profile_complete=1",
                                      (user["team_id"],)).fetchone()[0]
                    wants_captain = body.get("captain", False)
                    if type(wants_captain) is not bool:
                        raise ValueError("팀장 선택 값이 잘못되었습니다.")
                    if wants_captain and team["captain_user_id"]:
                        raise ValueError("이미 팀장이 정해졌습니다. 화면을 새로고침하세요.")
                    if not team["captain_user_id"] and (wants_captain or count == 4):
                        c.execute("UPDATE teams SET captain_user_id=? WHERE id=?", (user["id"], user["team_id"]))
                    c.execute("UPDATE users SET name=?,profile_complete=1 WHERE id=?", (name, user["id"]))
                    c.commit()
                    self.send(snapshot(c, self.user(c)))
                    return
                if not user["profile_complete"]:
                    raise ValueError("먼저 선수 이름을 설정하세요.")
                if path == "/api/team/name":
                    team = c.execute("SELECT * FROM teams WHERE id=?", (user["team_id"],)).fetchone()
                    if team["captain_user_id"] != user["id"] or team["configured"]:
                        raise PermissionError("팀명은 대기실에 들어가기 전 팀장만 정할 수 있습니다.")
                    name = body.get("name")
                    if not isinstance(name, str):
                        raise ValueError("팀명을 입력하세요.")
                    name = " ".join(name.split())
                    if not 2 <= len(name) <= 24 or not all(ch.isalnum() or ch in " _-" for ch in name):
                        raise ValueError("팀명은 2~24자의 문자, 숫자, 공백, _ 또는 -만 사용할 수 있습니다.")
                    if c.execute("SELECT 1 FROM teams WHERE name=? AND id!=?", (name, user["team_id"])).fetchone():
                        raise ValueError("다른 팀에서 이미 사용하는 이름입니다.")
                    if name != team["name"]:
                        c.execute("DELETE FROM logo_candidates WHERE team_id=?", (user["team_id"],))
                    c.execute("UPDATE teams SET name=?,named=1 WHERE id=?", (name, user["team_id"]))
                    c.commit()
                    self.send(snapshot(c, user))
                    return
                if path == "/api/team/choose-logo":
                    team = c.execute("SELECT * FROM teams WHERE id=?", (user["team_id"],)).fetchone()
                    if team["captain_user_id"] != user["id"] or not team["named"] or team["configured"]:
                        raise PermissionError("팀장만 준비된 로고를 선택할 수 있습니다.")
                    slot = body.get("slot")
                    if type(slot) is not int or slot not in (1, 2, 3):
                        raise ValueError("로고 후보 세 개 중 하나를 선택하세요.")
                    chosen = c.execute("SELECT data_uri FROM logo_candidates WHERE team_id=? AND slot=?",
                                       (user["team_id"], slot)).fetchone()
                    if not chosen:
                        raise ValueError("먼저 로고 후보를 생성하세요.")
                    c.execute("UPDATE teams SET logo_data=?,configured=1 WHERE id=?",
                              (chosen[0], user["team_id"]))
                    c.execute("DELETE FROM logo_candidates WHERE team_id=?", (user["team_id"],))
                    c.commit()
                    self.send(snapshot(c, user))
                    return
                if path == "/api/selection":
                    next_round = current_round(c) + 1
                    if user["team_id"] not in eligible_teams(c, next_round):
                        raise ValueError("현재는 다음 라운드 레벨을 선택할 수 없습니다.")
                    level = body.get("level")
                    if level is not None and (type(level) is not int or level not in REWARD):
                        raise ValueError("레벨 1~5 중에서 선택하세요.")
                    c.execute("DELETE FROM round_preferences WHERE round=? AND user_id=?",
                              (next_round, user["id"]))
                    if level is not None:
                        if c.execute("SELECT 1 FROM round_preferences WHERE round=? AND team_id=? AND level=?",
                                     (next_round, user["team_id"], level)).fetchone():
                            raise ValueError("팀원이 이미 선택한 레벨입니다. 다른 레벨을 선택하세요.")
                        c.execute("INSERT INTO round_preferences(round,team_id,user_id,level) VALUES (?,?,?,?)",
                                  (next_round, user["team_id"], user["id"], level))
                    c.commit()
                    self.send(snapshot(c, user))
                    return
                r = current_round(c)
                match = match_for(c, user["team_id"], r)
                if not match or match["status"] != "open" or not match["start_at"] <= time.time() < match["end_at"]:
                    raise ValueError("현재 진행 중인 내 경기가 없습니다.")
                assignment = c.execute("SELECT level FROM round_assignments WHERE round=? AND user_id=?",
                                       (r, user["id"])).fetchone()
                if not assignment:
                    raise ValueError("이번 라운드에 문제 레벨이 배정되지 않았습니다.")
                level = assignment["level"]
                pid = f"S{match['problem_set']}-L{level}"
                problem = LOOKUP[pid]
                if path == "/api/submit":
                    if os.environ.get("HOST", "127.0.0.1") not in ("127.0.0.1", "localhost"):
                        raise ValueError("공개 서버의 코드 실행은 격리 채점기 연결 전까지 비활성화됩니다. README를 확인하세요.")
                    verdict, passed, total = judge(body.get("code"), problem)
                    now = received_at
                    if now >= match["end_at"]:
                        raise ValueError("경기 종료 후 제출은 점수에 반영되지 않습니다.")
                    c.execute("INSERT INTO submissions(match_id,user_id,problem_id,at,verdict,passed,total) VALUES (?,?,?,?,?,?,?)",
                              (match["id"], user["id"], pid, now, verdict[:5000], passed, total))
                    points = 0
                    if verdict == "정답":
                        previous = c.execute("SELECT 1 FROM solves WHERE match_id=? AND problem_id=?",
                                             (match["id"], pid)).fetchone()
                        points = REWARD[level] // 2 if previous else REWARD[level]
                        c.execute("INSERT OR IGNORE INTO solves(match_id,team_id,user_id,problem_id,at,win_points,solve_points) VALUES (?,?,?,?,?,?,?)",
                                  (match["id"], user["team_id"], user["id"], pid, now, points, REWARD[level]))
                        if c.execute("SELECT changes()").fetchone()[0]:
                            c.execute("INSERT INTO credits(team_id,amount,available_round,reason,at) VALUES (?,?,?,?,?)",
                                      (user["team_id"], REWARD[level], r, f"{pid} 정답", now))
                        else:
                            points = 0
                    c.commit()
                    self.send({"verdict": verdict, "passed": passed, "total": total, "win_points": points,
                               "state": snapshot(c, user)})
                    return
                if path == "/api/hint":
                    kind = body.get("kind")
                    if kind not in HINT_COST:
                        raise ValueError("힌트 종류가 잘못되었습니다.")
                    existing = c.execute("SELECT detail FROM purchases WHERE match_id=? AND team_id=? AND problem_id=? AND kind=?",
                                         (match["id"], user["team_id"], pid, kind)).fetchone()
                    if existing:
                        self.send({"detail": existing[0], "state": snapshot(c, user)})
                        return
                    cost = HINT_COST[kind]
                    if credit_balance(c, user["team_id"], r) < cost:
                        raise ValueError("사용 가능한 solve포인트가 부족합니다. 팀원이 정답을 맞히면 즉시 사용할 수 있습니다.")
                    if kind == "assist":
                        detail = assist(problem, body.get("code"))
                    else:
                        detail = problem["hint1"] if kind == "type" else problem["hint2"]
                    now = time.time()
                    c.execute("INSERT INTO purchases(match_id,team_id,user_id,problem_id,kind,detail,cost,at) VALUES (?,?,?,?,?,?,?,?)",
                              (match["id"], user["team_id"], user["id"], pid, kind, detail, cost, now))
                    c.execute("INSERT INTO credits(team_id,amount,available_round,reason,at) VALUES (?,?,?,?,?)",
                              (user["team_id"], -cost, r, f"{pid} {kind} 힌트", now))
                    c.commit()
                    self.send({"detail": detail, "state": snapshot(c, user)})
                    return
                self.send({"error": "찾을 수 없습니다."}, 404)
        except PermissionError as exc:
            self.send({"error": str(exc)}, 403)
        except (ValueError, TypeError, json.JSONDecodeError) as exc:
            self.send({"error": str(exc)}, 400)
        except Exception as exc:
            print("서버 오류:", repr(exc), file=sys.stderr)
            self.send({"error": "서버 처리 중 오류가 발생했습니다."}, 500)


if __name__ == "__main__":
    setup()
    port = int(os.environ.get("PORT", "8765"))
    host = os.environ.get("HOST", "127.0.0.1")
    print(f"Code Rumble: http://{host}:{port}", flush=True)
    ThreadingHTTPServer((host, port), Handler).serve_forever()
