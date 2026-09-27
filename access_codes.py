"""Print the same codes as a free Render service configured with ACCESS_SEED."""
import json
import os

from server import TEAM_NAMES, access_token

if not os.environ.get("qOaVlYO_QqB1HnOhxu-XDblvAxfFE5jvYL9YIXPOq8o"):
    raise SystemExit("먼저 Render에 입력한 것과 같은 ACCESS_SEED 환경 변수를 설정하세요.")

codes = {"admin": access_token("admin"), "teams": {}}
for team_id, name in enumerate(TEAM_NAMES, 1):
    codes["teams"][name] = [
        {"name": f"{name} {level}번", "level": level,
         "code": access_token("player", team_id, level)}
        for level in range(1, 6)
    ]
print(json.dumps(codes, ensure_ascii=False, indent=2))
