"""Password hashing, account validation, and expiring bearer sessions."""
import hashlib
import hmac
import re
import secrets
import time

PASSWORD_MIN = 8
PASSWORD_MAX = 20
SESSION_SECONDS = 60 * 60 * 24 * 30


def validate_username(value):
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9_.-]{3,20}", value):
        raise ValueError("아이디는 영문, 숫자, 밑줄, 점, 하이픈으로 3~20자 입력하세요.")
    return value


def validate_nickname(value):
    if not isinstance(value, str):
        raise ValueError("닉네임을 입력하세요.")
    value = " ".join(value.split())
    hangul = sum("\uac00" <= ch <= "\ud7a3" for ch in value)
    if not value or len(value) > 20 or hangul > 10 or not all(ch.isalnum() or ch in " _-" for ch in value):
        raise ValueError("닉네임은 한글 최대 10자, 전체 최대 20자까지 입력할 수 있습니다.")
    return value


def validate_full_name(value):
    if not isinstance(value, str):
        raise ValueError("이름을 입력하세요.")
    value = " ".join(value.split())
    if not 2 <= len(value) <= 50 or not all(ch.isalnum() or ch in " _-·." for ch in value):
        raise ValueError("이름은 2~50자로 입력하세요.")
    return value


def validate_email(value):
    if not isinstance(value, str):
        raise ValueError("이메일 주소를 입력하세요.")
    value = value.strip().lower()
    if len(value) > 254 or not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", value):
        raise ValueError("올바른 이메일 주소를 입력하세요.")
    return value


def validate_password(value):
    if not isinstance(value, str) or not PASSWORD_MIN <= len(value) <= PASSWORD_MAX:
        raise ValueError("비밀번호는 8~20자로 설정하세요.")
    return value


def hash_password(password, salt=None):
    validate_password(password)
    salt = salt or secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, n=2**14, r=8, p=1, dklen=32)
    return "scrypt$" + salt.hex() + "$" + digest.hex()


def verify_password(password, stored):
    try:
        algorithm, salt_hex, digest_hex = stored.split("$")
        if algorithm != "scrypt":
            return False
        candidate = hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt_hex), n=2**14, r=8, p=1, dklen=32)
        return hmac.compare_digest(candidate, bytes.fromhex(digest_hex))
    except (ValueError, TypeError, MemoryError):
        return False


def opaque_hash(value):
    return hashlib.sha256(value.encode()).hexdigest()


def create_session(c, account_id):
    raw = secrets.token_urlsafe(36)
    c.execute("INSERT INTO account_sessions(token_hash,account_id,expires_at,created_at) VALUES (?,?,?,?)",
              (opaque_hash(raw), account_id, time.time() + SESSION_SECONDS, time.time()))
    return raw


def account_for_token(c, raw):
    if not raw:
        return None
    row = c.execute("SELECT a.* FROM account_sessions s JOIN accounts a ON a.id=s.account_id WHERE s.token_hash=? AND s.expires_at>?",
                    (opaque_hash(raw), time.time())).fetchone()
    return row


def create_schema(c):
    c.executescript("""
    CREATE TABLE IF NOT EXISTS accounts(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      username TEXT NOT NULL COLLATE NOCASE UNIQUE,
      nickname TEXT NOT NULL COLLATE NOCASE UNIQUE,
      full_name TEXT NOT NULL,
      email TEXT NOT NULL COLLATE NOCASE UNIQUE,
      password_hash TEXT NOT NULL,
      email_verified INTEGER NOT NULL DEFAULT 0,
      avatar_id INTEGER NOT NULL DEFAULT 1,
      rating INTEGER NOT NULL DEFAULT 1000,
      is_operator INTEGER NOT NULL DEFAULT 0,
      games INTEGER NOT NULL DEFAULT 0,
      wins INTEGER NOT NULL DEFAULT 0,
      consent_version TEXT NOT NULL,
      consent_at REAL NOT NULL,
      created_at REAL NOT NULL,
      last_seen REAL NOT NULL DEFAULT 0
    );
    CREATE TABLE IF NOT EXISTS account_sessions(
      token_hash TEXT PRIMARY KEY, account_id INTEGER NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
      expires_at REAL NOT NULL, created_at REAL NOT NULL
    );
    CREATE INDEX IF NOT EXISTS account_sessions_expiry ON account_sessions(expires_at);
    CREATE TABLE IF NOT EXISTS email_challenges(
      email TEXT NOT NULL COLLATE NOCASE, purpose TEXT NOT NULL, code_hash TEXT NOT NULL,
      payload TEXT NOT NULL DEFAULT '{}', expires_at REAL NOT NULL, attempts INTEGER NOT NULL DEFAULT 0,
      PRIMARY KEY(email,purpose)
    );
    CREATE TABLE IF NOT EXISTS account_stats(
      account_id INTEGER NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
      axis TEXT NOT NULL, value INTEGER NOT NULL DEFAULT 0, PRIMARY KEY(account_id,axis)
    );
    CREATE TABLE IF NOT EXISTS friendships(
      requester_id INTEGER NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
      target_id INTEGER NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
      status TEXT NOT NULL DEFAULT 'pending', created_at REAL NOT NULL,
      PRIMARY KEY(requester_id,target_id), CHECK(requester_id != target_id)
    );
    """)
    c.execute("DELETE FROM account_sessions WHERE expires_at<=?", (time.time(),))

import json


def _code_hash(code, salt=None):
    salt = salt or secrets.token_bytes(16)
    digest = hashlib.scrypt(code.encode(), salt=salt, n=2**12, r=8, p=1, dklen=32)
    return salt.hex() + "$" + digest.hex()


def _verify_code(code, stored):
    try:
        salt_hex, digest_hex = stored.split("$")
        candidate = hashlib.scrypt(code.encode(), salt=bytes.fromhex(salt_hex), n=2**12, r=8, p=1, dklen=32)
        return hmac.compare_digest(candidate, bytes.fromhex(digest_hex))
    except (ValueError, TypeError, MemoryError):
        return False


def begin_registration(c, data, consent_version):
    nickname = validate_nickname(data.get("nickname"))
    full_name = validate_full_name(data.get("full_name"))
    username = validate_username(data.get("username"))
    email = validate_email(data.get("email"))
    password = validate_password(data.get("password"))
    if data.get("consent") is not True or data.get("consent_version") != consent_version:
        raise ValueError("개인정보 수집·이용 동의가 필요합니다.")
    if c.execute("SELECT 1 FROM accounts WHERE username=? OR nickname=? OR email=?", (username, nickname, email)).fetchone():
        raise ValueError("아이디, 닉네임 또는 이메일이 이미 등록되어 있습니다.")
    code = f"{secrets.randbelow(1_000_000):06d}"
    payload = {"nickname": nickname, "full_name": full_name, "username": username,
               "password_hash": hash_password(password), "email": email}
    c.execute("INSERT OR REPLACE INTO email_challenges(email,purpose,code_hash,payload,expires_at,attempts) VALUES (?,?,?,?,?,0)",
              (email, "register", _code_hash(code), json.dumps(payload, ensure_ascii=False), time.time() + 600))
    return email, code


def verify_registration(c, email, code, consent_version):
    email = validate_email(email)
    row = c.execute("SELECT * FROM email_challenges WHERE email=? AND purpose='register'", (email,)).fetchone()
    _check_challenge(c, row, code)
    payload = json.loads(row["payload"])
    if c.execute("SELECT 1 FROM accounts WHERE username=? OR nickname=? OR email=?",
                 (payload["username"], payload["nickname"], email)).fetchone():
        c.execute("DELETE FROM email_challenges WHERE email=? AND purpose='register'", (email,))
        raise ValueError("아이디, 닉네임 또는 이메일이 이미 등록되어 있습니다.")
    now = time.time()
    cur = c.execute("INSERT INTO accounts(username,nickname,full_name,email,password_hash,email_verified,consent_version,consent_at,created_at) VALUES (?,?,?,?,?,1,?,?,?)",
                    (payload["username"], payload["nickname"], payload["full_name"], email,
                     payload["password_hash"], consent_version, now, now))
    account_id = cur.lastrowid
    for axis in ("implementation", "strings", "simulation", "data_structures", "search", "optimization"):
        c.execute("INSERT INTO account_stats(account_id,axis,value) VALUES (?,?,0)", (account_id, axis))
    c.execute("DELETE FROM email_challenges WHERE email=? AND purpose='register'", (email,))
    return account_id


def _check_challenge(c, row, code):
    if not row or row["expires_at"] <= time.time():
        raise ValueError("인증 코드가 만료되었거나 존재하지 않습니다. 새 코드를 요청하세요.")
    if row["attempts"] >= 5:
        c.execute("DELETE FROM email_challenges WHERE email=? AND purpose=?", (row["email"], row["purpose"]))
        raise ValueError("인증 시도 횟수를 초과했습니다. 새 코드를 요청하세요.")
    if not isinstance(code, str) or not _verify_code(code.strip(), row["code_hash"]):
        c.execute("UPDATE email_challenges SET attempts=attempts+1 WHERE email=? AND purpose=?", (row["email"], row["purpose"]))
        raise ValueError("인증 코드가 올바르지 않습니다.")


def begin_recovery(c, email, kind):
    email = validate_email(email)
    if kind not in ("username", "password"):
        raise ValueError("계정 찾기 유형을 확인하세요.")
    account = c.execute("SELECT id,username FROM accounts WHERE email=? AND email_verified=1", (email,)).fetchone()
    purpose = "recover-" + kind
    if account:
        code = f"{secrets.randbelow(1_000_000):06d}"
        payload = {"account_id": account["id"], "username": account["username"]}
        c.execute("INSERT OR REPLACE INTO email_challenges(email,purpose,code_hash,payload,expires_at,attempts) VALUES (?,?,?,?,?,0)",
                  (email, purpose, _code_hash(code), json.dumps(payload), time.time() + 600))
        return email, code, True
    return email, None, False


def finish_recovery(c, email, kind, code, new_password=None):
    email = validate_email(email)
    purpose = "recover-" + kind
    row = c.execute("SELECT * FROM email_challenges WHERE email=? AND purpose=?", (email, purpose)).fetchone()
    _check_challenge(c, row, code)
    payload = json.loads(row["payload"])
    if kind == "username":
        result = {"username": payload["username"]}
    elif kind == "password":
        password = validate_password(new_password)
        c.execute("UPDATE accounts SET password_hash=? WHERE id=?", (hash_password(password), payload["account_id"]))
        c.execute("DELETE FROM account_sessions WHERE account_id=?", (payload["account_id"],))
        result = {"reset": True}
    else:
        raise ValueError("계정 찾기 유형을 확인하세요.")
    c.execute("DELETE FROM email_challenges WHERE email=? AND purpose=?", (email, purpose))
    return result


def login(c, username, password):
    if not isinstance(username, str) or not isinstance(password, str):
        raise ValueError("아이디와 비밀번호를 입력하세요.")
    row = c.execute("SELECT * FROM accounts WHERE username=? COLLATE NOCASE", (username.strip(),)).fetchone()
    if not row or not verify_password(password, row["password_hash"]):
        raise PermissionError("아이디 또는 비밀번호를 확인하세요.")
    if not row["email_verified"]:
        raise PermissionError("이메일 인증을 완료한 뒤 로그인하세요.")
    c.execute("UPDATE accounts SET last_seen=? WHERE id=?", (time.time(), row["id"]))
    token = create_session(c, row["id"])
    return token, row
