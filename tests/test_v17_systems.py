"""Contract tests for account recovery, 3-8 teams, social ACLs and adaptive profiles."""
import json
import sqlite3
import time
import unittest
from unittest.mock import patch
import account_security as accounts
import game_systems as systems
import lobby_service as lobbies
import social_service as social
import server
from problems import PROBLEMS,reference_code,expected_outputs,public_samples

class SystemsTest(unittest.TestCase):
    def setUp(self):
        self.c=sqlite3.connect(':memory:');self.c.row_factory=sqlite3.Row
        accounts.create_schema(self.c);lobbies.create_schema(self.c)
    def tearDown(self):self.c.close()
    def account(self,n):
        return self.c.execute('INSERT INTO accounts(username,nickname,full_name,email,password_hash,email_verified,consent_version,consent_at,created_at,last_seen) VALUES (?,?,?,?,?,1,?,?,?,?)',(f'u{n}',f'선수{n}',f'이름{n}',f'u{n}@example.com','test-hash','test',time.time(),time.time(),time.time())).lastrowid
    def test_signup_confirmation_and_recovery_pair(self):
        d={'username':'test01','nickname':'홍길동','full_name':'홍길동','email':'Hong@Example.com','password':'secret123','password_confirm':'different','consent':True,'consent_version':'v1'}
        with self.assertRaisesRegex(ValueError,'확인'):accounts.begin_registration(self.c,d,'v1')
        d['password_confirm']=d['password'];email,code=accounts.begin_registration(self.c,d,'v1');uid=accounts.verify_registration(self.c,email,code,'v1')
        token=accounts.create_session(self.c,uid)
        with self.assertRaisesRegex(ValueError,'일치'):accounts.begin_recovery(self.c,email,'password','someoneelse')
        with self.assertRaisesRegex(ValueError,'일치'):accounts.begin_recovery(self.c,'other@example.com','password','test01')
        address,code,found=accounts.begin_recovery(self.c,'HONG@EXAMPLE.COM','password','TEST01')
        self.assertTrue(found);self.assertEqual(address,'hong@example.com')
        accounts.finish_recovery(self.c,address,'password',code,'newsecret123')
        self.assertIsNone(accounts.account_for_token(self.c,token))
        self.assertTrue(accounts.verify_password('newsecret123',self.c.execute('SELECT password_hash FROM accounts WHERE id=?',(uid,)).fetchone()[0]))
        with self.assertRaises(ValueError):accounts.finish_recovery(self.c,address,'password',code,'secret123')
    def test_round_robin_every_pair_once(self):
        for n in range(3,9):
            rounds=systems.round_robin(range(1,n+1));pairs=[tuple(sorted(p)) for r in rounds for p in r]
            self.assertEqual(len(pairs),n*(n-1)//2);self.assertEqual(len(pairs),len(set(pairs)))
            self.assertEqual(len(rounds),n if n%2 else n-1)
            for r in rounds:self.assertEqual(len({t for p in r for t in p}),len(r)*2)
    def test_three_to_eight_teams_through_final_without_reuse(self):
        serial=0
        for n in range(3,9):
            with self.subTest(teams=n):
                owner=self.account(serial);serial+=1;lid=lobbies.create_lobby(self.c,owner,f'대회 {n}','challenge')
                for team in range(1,n+1):
                    for j in range(4 if team==1 else 5):
                        uid=self.account(serial);serial+=1;lobbies.join_lobby(self.c,lid,uid,team);lobbies.set_ready(self.c,lid,uid,True)
                lobbies.start_lobby(self.c,lid,owner)
                for phase in ('captain_vote','team_setup'):
                    self.c.execute('UPDATE lobbies SET phase_ends_at=0 WHERE id=?',(lid,));server.progress_lobby(self.c,lid)
                self.assertEqual(self.c.execute('SELECT phase FROM lobbies WHERE id=?',(lid,)).fetchone()[0],'countdown')
                used=set();rounds=systems.rumble_rounds(self.c,lid)
                for stage in range(1,rounds+2):
                    self.c.execute('UPDATE lobbies SET phase_ends_at=0 WHERE id=?',(lid,));server.progress_lobby(self.c,lid)
                    game=self.c.execute('SELECT * FROM lobby_game_rounds WHERE id=(SELECT active_game_id FROM lobbies WHERE id=?)',(lid,)).fetchone()
                    self.assertEqual(game['round_no'],stage)
                    mapping=json.loads(game['problem_map_json']);ids=set(mapping.values())
                    self.assertTrue(used.isdisjoint(ids));used.update(ids)
                    if stage==rounds+1:
                        self.assertEqual(len(ids),10);self.assertAlmostEqual(game['ends_at']-time.time(),600,delta=2)
                        nonfinalist=self.c.execute('SELECT account_id FROM lobby_members WHERE lobby_id=? AND team_no=1',(lid,)).fetchone()[0]
                        view=server.account_lobby_view(self.c,lid,nonfinalist)
                        self.assertTrue(view['spectator']);self.assertEqual(len(view['game']['players']),10)
                        with self.assertRaises(ValueError):lobbies.operator_close(self.c,lid,nonfinalist)
                        self.assertEqual(self.c.execute('SELECT phase FROM lobbies WHERE id=?',(lid,)).fetchone()[0],'live')
                        self.assertEqual(self.c.execute('SELECT SUM(win_points) FROM lobby_team_totals WHERE lobby_id=? AND team_no IN (?,?)',(lid,n,n-1)).fetchone()[0],0)
                        break
                    self.assertAlmostEqual(game['ends_at']-time.time(),300,delta=2)
                    self.c.execute('UPDATE lobbies SET phase_ends_at=0 WHERE id=?',(lid,));server.progress_lobby(self.c,lid)
                    if stage==rounds:self.c.execute('UPDATE lobby_team_totals SET win_points=team_no*100 WHERE lobby_id=?',(lid,))
                    for _ in range(2):
                        self.c.execute('UPDATE lobbies SET phase_ends_at=0 WHERE id=?',(lid,));server.progress_lobby(self.c,lid)
    def test_chat_and_invites_acl_retention_and_game_block(self):
        a,b,x=[self.account(i) for i in range(3)]
        self.c.execute("INSERT INTO friendships VALUES (?,?,'accepted',?)",(a,b,time.time()))
        mid=social.send_message(self.c,a,b,'hello')
        self.assertEqual(social.inbox(self.c,b)['unread_chat'],1)
        self.assertEqual(social.conversation(self.c,b,a)['messages'][0]['text'],'hello')
        self.assertEqual(social.inbox(self.c,b)['unread_chat'],0)
        with self.assertRaises(PermissionError):social.send_message(self.c,a,x,'private')
        lid=lobbies.create_lobby(self.c,a,'친구 초대','normal');social.invite(self.c,lid,a,b)
        self.assertEqual(len(social.inbox(self.c,b)['invites']),1)
        with self.assertRaises(PermissionError):social.invite(self.c,lid,a,x)
        self.c.execute("UPDATE lobbies SET phase='live',status='running' WHERE id=?",(lid,))
        with self.assertRaises(ValueError):social.send_message(self.c,b,a,'blocked')
        with self.assertRaises(ValueError):social.conversation(self.c,b,a)
        self.c.execute('UPDATE friend_messages SET created_at=? WHERE id=?',(time.time()-social.RETENTION-1,mid));social.prune(self.c)
        self.assertEqual(self.c.execute('SELECT COUNT(*) FROM friend_messages').fetchone()[0],0)
    def test_skill_cap_and_evidence_updates(self):
        uid=self.account(0);p={'account_id':uid,'solved':1,'level':4,'solve_earned':250}
        self.c.execute("INSERT INTO lobby_game_submissions(game_round_id,account_id,problem_id,code,verdict,at) VALUES (1,?,'p','','정답',?)",(uid,time.time()-150))
        g={'id':1,'started_at':time.time()-200,'ends_at':time.time()+100}
        systems.update_skills(self.c,p,g,True)
        low=systems.profile(self.c,uid,800);high=systems.profile(self.c,uid,1800)
        self.assertEqual(low['skill_max'],20);self.assertEqual(high['skill_max'],120)
        self.assertGreater(high['skills']['completion'],low['skills']['completion'])
        before=high['skills']['completion'];p['solved']=0;systems.update_skills(self.c,p,g,False)
        self.assertLess(systems.profile(self.c,uid,1800)['skills']['completion'],before)
    def test_difficulty_moves_with_match_rating_and_outcomes(self):
        low,_=systems.allocate(self.c,PROBLEMS,800,set(),rng=__import__('random').Random(1))
        high,_=systems.allocate(self.c,PROBLEMS,1800,set(),rng=__import__('random').Random(1))
        lookup={p['id']:p for p in PROBLEMS}
        self.assertGreaterEqual(sum(systems.difficulty(self.c,lookup[k])['difficulty_rating'] for k in high.values()),sum(systems.difficulty(self.c,lookup[k])['difficulty_rating'] for k in low.values()))
        p=PROBLEMS[0];initial=systems.difficulty(self.c,p)['difficulty_rating']
        for _ in range(30):systems.record_difficulty(self.c,p,1000,True)
        self.assertLess(systems.difficulty(self.c,p)['difficulty_rating'],initial)
    def test_queue_hides_size_and_balances_ten(self):
        ids=[self.account(i) for i in range(10)]
        for uid in ids:server.queue_join(self.c,uid)
        homes=[server.account_home(self.c,self.c.execute('SELECT * FROM accounts WHERE id=?',(uid,)).fetchone()) for uid in ids]
        self.assertNotIn('waiting',homes[0]['queue']);self.assertIn('estimated_seconds',homes[0]['queue'])
        self.assertEqual(len({h['queue']['batch_lobby_id'] for h in homes}),1)
        self.assertIsNotNone(homes[0]['queue']['batch_lobby_id'])

if __name__=='__main__':unittest.main()
