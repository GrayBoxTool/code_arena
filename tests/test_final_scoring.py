import sqlite3
import unittest
from unittest.mock import patch
from server import award_points, close_match

class FinalScoring(unittest.TestCase):
    def test_equal_rewards_and_tiebreak(self):
        c=sqlite3.connect(':memory:');c.row_factory=sqlite3.Row
        c.executescript('''CREATE TABLE matches(id INTEGER PRIMARY KEY, round INTEGER, team_a INTEGER, team_b INTEGER, settled INTEGER, status TEXT,end_at REAL,winner INTEGER,bonus INTEGER,reason TEXT);
        CREATE TABLE solves(match_id INTEGER,team_id INTEGER,problem_id TEXT,win_points INTEGER);
        CREATE TABLE credits(team_id INTEGER,amount INTEGER);
        INSERT INTO matches VALUES(1,6,1,2,0,'open',9999999999,NULL,0,NULL);
        INSERT INTO solves VALUES(1,1,'FA-L5',300);
        INSERT INTO solves VALUES(1,2,'FB-L5',300);
        INSERT INTO credits VALUES(1,500),(1,-150),(2,400);''')
        m=c.execute('SELECT * FROM matches').fetchone()
        self.assertEqual(award_points(c,m,5),300)
        self.assertEqual(award_points(c,dict(m)|{'round':1},5),150)
        with patch('server.event'):
            close_match(c,m)
            result=c.execute('SELECT * FROM matches').fetchone()
            self.assertEqual(result['winner'],2)
            self.assertEqual(result['reason'],'solve_tiebreak')
            self.assertEqual(result['bonus'],0)
            c.execute('UPDATE matches SET settled=0')
            c.execute('INSERT INTO credits VALUES(1,50)')
            close_match(c,c.execute('SELECT * FROM matches').fetchone())
            self.assertIsNone(c.execute('SELECT winner FROM matches').fetchone()[0])
            c.execute('UPDATE matches SET settled=0')
            c.execute("INSERT INTO solves VALUES(1,1,'FA-L1',100)")
            c.execute('INSERT INTO credits VALUES(2,10000)')
            close_match(c,c.execute('SELECT * FROM matches').fetchone())
            self.assertEqual(c.execute('SELECT winner FROM matches').fetchone()[0],1)
        c.close()
