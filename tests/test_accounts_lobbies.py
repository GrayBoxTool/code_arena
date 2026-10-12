"""Account security and lobby lifecycle tests; no network or credentials required."""
import json
import sqlite3
import sys
import time
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import account_security as accounts
import lobby_service as lobbies
import server


class AccountLobbyTests(unittest.TestCase):
    def setUp(self):
        self.c = sqlite3.connect(":memory:")
        self.c.row_factory = sqlite3.Row
        self.c.execute("PRAGMA foreign_keys=ON")
        accounts.create_schema(self.c)
        lobbies.create_schema(self.c)
        self.ids=[]

    def tearDown(self):
        self.c.close()

    def account(self, number, operator=False):
        now=time.time()
        cur=self.c.execute("INSERT INTO accounts(username,nickname,full_name,email,password_hash,email_verified,is_operator,consent_version,consent_at,created_at) VALUES (?,?,?,?,?,1,1,?,?,?)" if operator else "INSERT INTO accounts(username,nickname,full_name,email,password_hash,email_verified,consent_version,consent_at,created_at) VALUES (?,?,?,?,?,1,?,?,?)",
            (f"player{number}",f"선수{number}",f"이름{number}",f"p{number}@example.com",accounts.hash_password("secretpass"),"test-v1",now,now))
        self.ids.append(cur.lastrowid)
        return cur.lastrowid

    def test_registration_requires_consent_and_password_is_hashed(self):
        data={"nickname":"홍길동","full_name":"홍길동","username":"hong01","email":"hong@example.com","password":"secret123","consent":False,"consent_version":"test-v1"}
        with self.assertRaisesRegex(ValueError,"동의"):
            accounts.begin_registration(self.c,data,"test-v1")
        data["consent"]=True
        email,code=accounts.begin_registration(self.c,data,"test-v1")
        account_id=accounts.verify_registration(self.c,email,code,"test-v1")
        row=self.c.execute("SELECT * FROM accounts WHERE id=?",(account_id,)).fetchone()
        self.assertTrue(row["password_hash"].startswith("scrypt$"))
        self.assertNotEqual(row["password_hash"],data["password"])
        self.assertTrue(accounts.verify_password("secret123",row["password_hash"]))

    def test_name_and_id_limits(self):
        self.assertEqual(accounts.validate_nickname("홍길동"),"홍길동")
        with self.assertRaises(ValueError): accounts.validate_nickname("가나다라마바사아자차카")
        with self.assertRaises(ValueError): accounts.validate_username("x"*21)
        with self.assertRaises(ValueError): accounts.validate_password("x"*21)

    def test_public_lobby_ready_and_challenge_timed_phases(self):
        owner=self.account(0); lid=lobbies.create_lobby(self.c,owner,"연습 대회","challenge")
        for team in range(1,6):
            for _ in range(4 if team==1 else 5):
                user=self.account(len(self.ids))
                lobbies.join_lobby(self.c,lid,user,team)
                lobbies.set_ready(self.c,lid,user,True)
        lobbies.start_lobby(self.c,lid,owner)
        self.assertEqual(self.c.execute("SELECT phase FROM lobbies WHERE id=?",(lid,)).fetchone()[0],"captain_vote")
        self.c.execute("UPDATE lobbies SET phase_ends_at=0 WHERE id=?",(lid,))
        lobbies.progress(self.c,lid)
        self.assertEqual(self.c.execute("SELECT phase FROM lobbies WHERE id=?",(lid,)).fetchone()[0],"team_setup")
        self.c.execute("UPDATE lobbies SET phase_ends_at=0 WHERE id=?",(lid,))
        lobbies.progress(self.c,lid)
        row=self.c.execute("SELECT phase,phase_ends_at FROM lobbies WHERE id=?",(lid,)).fetchone()
        self.assertEqual(row["phase"],"countdown")
        self.assertGreater(row["phase_ends_at"],time.time())

    def test_ranked_match_balances_ten_players_by_rating(self):
        players=[]
        for n,rating in enumerate([800,900,950,1000,1100,1200,1250,1300,1400,1500]):
            uid=self.account(n)
            self.c.execute("UPDATE accounts SET rating=? WHERE id=?",(rating,uid))
            players.append({"id":uid,"rating":rating})
        a,b=lobbies.balanced_split(players)
        self.assertEqual(len(a),5);self.assertEqual(len(b),5)
        self.assertLessEqual(abs(sum(x["rating"] for x in a)-sum(x["rating"] for x in b)),100)

    def test_challenge_problem_pairs_match_and_do_not_repeat_between_stages(self):
        owner=self.account(0);lid=lobbies.create_lobby(self.c,owner,"문제 재사용 검사","challenge")
        for team in range(1,6):
            users=[owner] if team==1 else []
            while len(users)<5:
                uid=self.account(len(self.ids));lobbies.join_lobby(self.c,lid,uid,team);users.append(uid)
        for stage in (1,2):
            self.c.execute("UPDATE lobbies SET phase='live',status='running',stage_no=?,phase_ends_at=? WHERE id=?",(stage,time.time()+300,lid))
            server.start_account_game(self.c,lid)
            game_id=self.c.execute("SELECT active_game_id FROM lobbies WHERE id=?",(lid,)).fetchone()[0]
            group=list(self.c.execute("SELECT team_no,level,problem_id FROM lobby_game_members WHERE game_round_id=?",(game_id,)))
            by={(x['team_no'],x['level']):x['problem_id'] for x in group}
            for a,b in server.ACCOUNT_ROUNDS[stage-1]:
                for level in range(1,6):self.assertEqual(by[(a,level)],by[(b,level)])
            if stage==1: first=set(by.values())
            else:self.assertTrue(first.isdisjoint(set(by.values())))
        self.c.execute("UPDATE lobbies SET phase='live',status='running',stage_no=6,active_game_id=NULL,phase_ends_at=? WHERE id=?",(time.time()+600,lid))
        server.start_account_game(self.c,lid)
        gid=self.c.execute("SELECT active_game_id FROM lobbies WHERE id=?",(lid,)).fetchone()[0]
        finalists=list(self.c.execute("SELECT team_no,level,problem_id FROM lobby_game_members WHERE game_round_id=? ORDER BY team_no,level",(gid,)))
        self.assertEqual(len(finalists),10)
        for level in range(1,6):self.assertNotEqual(finalists[level-1]['problem_id'],finalists[level+4]['problem_id'])

    def test_first_solver_gets_full_points_and_later_opponent_half(self):
        owner=self.account(0);lid=lobbies.create_lobby(self.c,owner,"일반 매치","normal")
        users={1:[owner],2:[]}
        for team in (1,2):
            while len(users[team])<5:
                uid=self.account(len(self.ids));lobbies.join_lobby(self.c,lid,uid,team);users[team].append(uid)
        self.c.execute("UPDATE lobby_members SET level=1 WHERE lobby_id=?",(lid,))
        self.c.execute("UPDATE lobbies SET phase='live',status='running',phase_ends_at=? WHERE id=?",(time.time()+300,lid))
        server.start_account_game(self.c,lid)
        first,second=users[1][0],users[2][0]
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/"game.sqlite3"
            self.c.commit()
            disk=sqlite3.connect(path);self.c.backup(disk);disk.close()
            with patch.object(server,"DB",path),patch.object(server,"judge_submission",return_value=("정답",3,3)):
                one=server.submit_account_game(lid,first,"print(1)")
                two=server.submit_account_game(lid,second,"print(1)")
            self.assertEqual(one['verdict'],"정답");self.assertEqual(two['verdict'],"정답")
            c=sqlite3.connect(path)
            scores=dict(c.execute("SELECT team_no,win_points FROM lobby_team_totals WHERE lobby_id=?",(lid,)))
            level=c.execute("SELECT level FROM lobby_game_members WHERE account_id=?",(first,)).fetchone()[0]
            reward={1:100,2:150,3:200,4:250,5:300}[level]
            self.assertEqual(sorted(scores.values()),[reward//2,reward]);c.close()

    def test_challenge_boundary_tie_waits_for_manual_finalist_choice(self):
        owner=self.account(0);lid=lobbies.create_lobby(self.c,owner,"동점 결승","challenge")
        for team,points in enumerate((1200,900,900,500,300),1):
            self.c.execute('INSERT INTO lobby_team_totals(lobby_id,team_no,win_points) VALUES (?,?,?)',(lid,team,points))
        self.c.execute("UPDATE lobbies SET status='results',phase='results',stage_no=5,phase_ends_at=0 WHERE id=?",(lid,))
        lobbies.progress(self.c,lid)
        self.assertEqual(self.c.execute('SELECT phase FROM lobbies WHERE id=?',(lid,)).fetchone()[0],'finalist_choice')
        result=server.choose_account_finalists(self.c,lid,owner,1,3)
        self.assertEqual(result['finalists'],[1,3])
        row=self.c.execute('SELECT phase,finalists_json FROM lobbies WHERE id=?',(lid,)).fetchone()
        self.assertEqual(row['phase'],'break');self.assertEqual(json.loads(row['finalists_json']),[1,3])


if __name__=="__main__": unittest.main()
