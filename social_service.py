"""Friend-only chat, lobby invitations and durable notifications."""
import time
RETENTION=7*24*3600

def create_schema(c):
    c.executescript('''CREATE TABLE IF NOT EXISTS friend_messages(id INTEGER PRIMARY KEY AUTOINCREMENT,sender_id INTEGER NOT NULL,recipient_id INTEGER NOT NULL,text TEXT NOT NULL,created_at REAL NOT NULL,read_at REAL);
    CREATE INDEX IF NOT EXISTS messages_retention ON friend_messages(created_at);
    CREATE INDEX IF NOT EXISTS messages_recipient ON friend_messages(recipient_id,read_at);
    CREATE TABLE IF NOT EXISTS social_notifications(id INTEGER PRIMARY KEY AUTOINCREMENT,recipient_id INTEGER NOT NULL,kind TEXT NOT NULL,actor_id INTEGER NOT NULL,reference_id INTEGER,created_at REAL NOT NULL,read_at REAL);
    CREATE TABLE IF NOT EXISTS lobby_invites(id INTEGER PRIMARY KEY AUTOINCREMENT,lobby_id INTEGER NOT NULL,sender_id INTEGER NOT NULL,recipient_id INTEGER NOT NULL,expires_at REAL NOT NULL,status TEXT NOT NULL DEFAULT 'pending');''')

def prune(c):
    cutoff=time.time()-RETENTION
    c.execute('DELETE FROM friend_messages WHERE created_at<=?',(cutoff,))
    c.execute('DELETE FROM social_notifications WHERE created_at<=?',(cutoff,))
    c.execute("DELETE FROM lobby_invites WHERE expires_at<=? OR status!='pending'",(time.time(),))

def friends(c,a,b):
    return bool(c.execute("SELECT 1 FROM friendships WHERE status='accepted' AND ((requester_id=? AND target_id=?) OR (requester_id=? AND target_id=?))",(a,b,b,a)).fetchone())

def blocked(c,uid):
    return bool(c.execute("SELECT 1 FROM lobby_members m JOIN lobbies l ON l.id=m.lobby_id WHERE m.account_id=? AND l.status NOT IN ('closed','cancelled') AND l.phase!='waiting' LIMIT 1",(uid,)).fetchone())

def notify(c,recipient,kind,actor,reference=None):
    c.execute('INSERT INTO social_notifications(recipient_id,kind,actor_id,reference_id,created_at) VALUES (?,?,?,?,?)',(recipient,kind,actor,reference,time.time()))

def send_message(c,sender,recipient,text):
    if not friends(c,sender,recipient):raise PermissionError('친구에게만 채팅을 보낼 수 있습니다.')
    if blocked(c,sender) or blocked(c,recipient):raise ValueError('게임이 시작된 동안에는 양쪽 모두 채팅을 사용할 수 없습니다.')
    if not isinstance(text,str) or not 1<=len(text.strip())<=1000:raise ValueError('메시지는 1~1000자로 입력하세요.')
    prune(c)
    mid=c.execute('INSERT INTO friend_messages(sender_id,recipient_id,text,created_at) VALUES (?,?,?,?)',(sender,recipient,text.strip(),time.time())).lastrowid
    notify(c,recipient,'chat',sender,mid)
    return mid

def conversation(c,viewer,friend,before=None):
    if not friends(c,viewer,friend):raise PermissionError('친구와의 채팅만 확인할 수 있습니다.')
    if blocked(c,viewer) or blocked(c,friend):raise ValueError('게임이 진행 중이므로 채팅을 사용할 수 없습니다.')
    prune(c)
    rows=[dict(r) for r in c.execute('SELECT id,sender_id,recipient_id,text,created_at FROM friend_messages WHERE ((sender_id=? AND recipient_id=?) OR (sender_id=? AND recipient_id=?)) AND id<? ORDER BY id DESC LIMIT 100',(viewer,friend,friend,viewer,before or 2**63-1))]
    c.execute('UPDATE friend_messages SET read_at=? WHERE recipient_id=? AND sender_id=? AND read_at IS NULL',(time.time(),viewer,friend))
    c.execute("UPDATE social_notifications SET read_at=? WHERE recipient_id=? AND actor_id=? AND kind='chat' AND read_at IS NULL",(time.time(),viewer,friend))
    return {'messages':list(reversed(rows)),'has_older':len(rows)==100,'retention_days':7}

def invite(c,lid,sender,recipient):
    if not friends(c,sender,recipient):raise PermissionError('친구만 초대할 수 있습니다.')
    if not c.execute("SELECT 1 FROM lobby_members m JOIN lobbies l ON l.id=m.lobby_id WHERE l.id=? AND m.account_id=? AND l.phase='waiting' AND l.visibility='public'",(lid,sender)).fetchone():raise ValueError('대기 중인 공개 로비에서만 초대할 수 있습니다.')
    if c.execute("SELECT 1 FROM lobby_invites WHERE lobby_id=? AND recipient_id=? AND status='pending' AND expires_at>?",(lid,recipient,time.time())).fetchone():raise ValueError('이미 초대가 전달되었습니다.')
    iid=c.execute('INSERT INTO lobby_invites(lobby_id,sender_id,recipient_id,expires_at) VALUES (?,?,?,?)',(lid,sender,recipient,time.time()+120)).lastrowid
    notify(c,recipient,'invite',sender,iid)
    return iid

def inbox(c,uid):
    prune(c)
    notifications=[dict(r) for r in c.execute('SELECT n.id,n.kind,n.actor_id,n.reference_id,n.created_at,a.nickname FROM social_notifications n JOIN accounts a ON a.id=n.actor_id WHERE n.recipient_id=? AND n.read_at IS NULL ORDER BY n.id DESC LIMIT 100',(uid,))]
    invites=[dict(r) for r in c.execute("SELECT i.id,i.lobby_id,i.sender_id,i.expires_at,l.name,a.nickname FROM lobby_invites i JOIN lobbies l ON l.id=i.lobby_id JOIN accounts a ON a.id=i.sender_id WHERE i.recipient_id=? AND i.status='pending' AND i.expires_at>? AND l.phase='waiting' AND l.visibility='public'",(uid,time.time()))]
    return {'notifications':notifications,'invites':invites,'chat_blocked':blocked(c,uid),'unread_chat':c.execute('SELECT COUNT(*) FROM friend_messages WHERE recipient_id=? AND read_at IS NULL',(uid,)).fetchone()[0]}
