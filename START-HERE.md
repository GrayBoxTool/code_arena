# OpenAI 연결과 배포 — 순서대로 따라 하기

이 압축본은 채점·AI 조언·팀 로고 후보 생성에 OpenAI 키 하나를 사용하도록 수정한 버전입니다. 아래 작업은 새 대회를 시작하기 전에 진행하세요. 이미 배포된 서비스에는 파일 업로드와 재배포가 필요합니다.

## 1. 기존 설정 보관

기존 `static/config.js`의 Render 주소와 Render Environment의 `ACCESS_SEED`, `FRONTEND_ORIGIN`을 보관하세요. ACCESS_SEED는 접속 코드를 만드는 값이므로 바꾸지 마세요. 이 파일의 안내를 따라 API 키를 ChatGPT 채팅이나 GitHub에 붙여 넣을 필요는 없습니다.

## 2. OpenAI 결제 설정과 키 발급

- https://platform.openai.com 에 로그인합니다.
- Settings의 Billing에서 결제 수단과 API 크레딧을 설정합니다. ChatGPT 구독과는 별도의 API 결제입니다. 충전 금액은 화면에 표시된 기준을 따르세요.
- https://platform.openai.com/api-keys 에서 서비스용 Secret Key를 생성하고 안전하게 보관합니다.
- 이 키에 Responses, Containers 및 컨테이너 파일, Images 사용 권한이 필요합니다. 제한된 권한으로 발급했다면 해당 API 권한을 확인하세요.
- 이미지 기능에서 조직 인증을 요구하면 OpenAI 화면의 인증 절차를 완료합니다.
- Usage/Billing의 사용량·지출 한도·자동 충전 설정을 확인합니다. 채점 컨테이너와 모델 토큰, 조언, 이미지 모두 API 사용료가 발생합니다.

## 3. GitHub의 프로젝트 파일 교체

압축을 풀면 `code-rumble` 폴더가 있습니다. 그 안의 파일들을 기존 저장소의 프로젝트 루트에 덮어씁니다. `code-rumble/code-rumble`처럼 이중 폴더로 올리지 마세요.

이번에는 다음 파일·폴더가 반드시 포함되어야 합니다.

- 모든 `.py` 파일. 특히 `openai_client.py`, `openai_judge.py`, `judge_runner.py`, `logo_service.py`, `api_check.py`가 새로 필요합니다.
- `assets/` 폴더 전체: 로고 원본 30개, 참고 시트 두 장, 이름 대응표.
- `logo_prompt.txt`, `static/` 폴더 전체, `render.yaml`, `netlify.toml`.

`docs/`와 `tests/`도 보관하면 운영·문제 확인에 도움이 됩니다. `data/`, 실제 API 키, 개인 접속 코드 파일은 GitHub에 올리지 마세요. 정답과 숨은 테스트가 포함되므로 저장소는 비공개로 관리하세요.

기존 Render가 GitHub 변경을 자동 배포한다면 파일 커밋 후 배포가 시작될 수 있습니다. 대회 도중에는 바꾸지 마세요.

## 4. Render 환경변수 입력

Render Dashboard → 기존 백엔드 Web Service → Environment에서 다음 값을 저장합니다. 따옴표 없이 입력하세요. 새로운 Blueprint를 만들 필요는 없습니다.

| Key | Value |
|---|---|
| OPENAI_API_KEY | 방금 발급받은 비밀 키 |
| JUDGE_PROVIDER | openai |
| OPENAI_JUDGE_MODEL | gpt-4.1-mini |
| OPENAI_MODEL | gpt-4.1-mini |
| OPENAI_IMAGE_MODEL | gpt-image-2.5-flare |
| HOST | 0.0.0.0 |
| ACCESS_SEED | 기존 값 그대로 |
| FRONTEND_ORIGIN | 실제 Netlify 주소, 예: https://my-game.netlify.app |

`FRONTEND_ORIGIN`에는 `/api` 같은 경로를 붙이지 않습니다. 모델 접근 권한이 없다면 먼저 해당 프로젝트의 모델 권한과 결제 상태를 확인하세요.

Settings의 Build Command는 `python -m compileall -q .`, Start Command는 `python server.py`입니다. 저장 후 배포하거나 Manual Deploy → 최신 커밋 배포를 실행합니다. 기존 서비스를 쓰는 경우 render.yaml만 바꿔도 환경변수가 자동 추가된다고 가정하지 마세요. Environment에서 직접 확인하세요.

## 5. Netlify 주소 연결과 재배포

`static/config.js`에 실제 Render 주소를 다시 입력합니다.

```javascript
window.RUMBLE_API_BASE_URL = 'https://실제서비스.onrender.com';
```

주소 뒤에 `/api`를 붙이지 마세요. API 키는 여기에 넣지 않습니다.

Git 연동이면 이 변경을 커밋하고 Netlify의 Publish directory가 `static`인지 확인합니다. 수동 업로드 방식이면 `static` 폴더를 배포합니다. 프로젝트 전체를 정적 사이트로 공개하지 마세요. 브라우저에서 Ctrl+Shift+R로 새로고침합니다.

## 6. 운영자로 실제 연결 시험

운영자 코드로 입장하면 `OpenAI 연결 상태`가 보입니다. 경기 시작 전에 `채점·AI 조언 연결 시험 (유료 호출)`을 누릅니다.

정답 채점, 오답 채점, 실행 오류 채점, AI 조언의 성공 표시와 소요 시간을 확인합니다. 시험은 대회 점수를 바꾸지 않습니다. 기본적으로 채점 컨테이너 3개와 조언 요청 1건을 사용하며 요금이 발생합니다. 연결 오류가 나면 반복해서 누르기 전에 메시지를 확인하세요.

| 표시되는 오류 | 확인할 것 |
|---|---|
| HTTP 401 | 키의 오타·만료·폐기 여부 |
| HTTP 403 | 모델/도구 권한, 조직 인증 |
| HTTP 429 | API 잔액, 요청 한도, 동시 요청 수 |
| HTTP 400 | 설정한 모델의 Code Interpreter 지원, API 권한과 요청 설정 |
| 지정한 실행 명령을 그대로 수행하지 않음 | 채점 도구 검증 실패. 실제 오류 내용을 기록하고 대회 시작 전 수정 필요 |
| 연결 실패·응답 지연 | 잠시 후 재시험, Render 로그와 OpenAI 상태 확인 |

연결 시험이 성공해야 해당 계정·모델에서 실제 실행이 된다는 것을 확인할 수 있습니다. 현재 제공자는 사용자 API 키를 받지 않았으므로 실제 유료 호출을 대신 수행하지 않았습니다.

## 7. 팀 로고 시험

아직 팀 설정을 완료하지 않은 팀장으로 로그인합니다. 팀명 저장 → 로고 후보 3개 만들기를 누릅니다. 참고 이미지와 한국어 별칭은 자동으로 API에 전달됩니다.

예를 들어 `T1 = 티원`, `Gen.G = 젠지`, `KWANGDONG FREECS = 광동 프릭스`를 같은 참고 팀으로 인식하도록 자료가 포함되어 있습니다. 30개 전체 대응표는 `docs/logo-reference-guide.md`에서 확인할 수 있습니다. 모델을 재학습하는 것이 아니라 실제 이미지 두 장과 프롬프트를 매번 전송합니다.

AI 생성이 30초를 넘으면 임시 후보를 먼저 선택할 수 있습니다. AI 후보 3개의 30초 완료를 보장하지 않습니다. 이미 임시 후보를 확정했다면 뒤늦은 AI 결과로 선택을 바꾸지 않습니다. 기존 팀 설정이 완료된 상태에서 시험하려고 전체 초기화를 누르면 모든 진행 기록도 삭제되므로 새 대회를 준비할 때만 사용하세요.

## 8. 실제 경기 리허설

선수 이름·팀명·로고를 설정하고 각 선수의 레벨 선택·준비를 완료한 뒤 운영자가 라운드를 시작합니다. 정답/오답/실행 오류를 제출해 점수, 10초 제한, 오류 표시를 확인합니다. 팀 solve 300점 이상이 생기면 AI 조언을 사용합니다.

25명 동시 제출에서 소요 시간과 API 한도를 반드시 확인하세요. 기본 동시 채점 제한은 25건입니다. 정답 비교는 Render 서버가 수행하며 AI가 말한 ‘정답’은 판정에 사용하지 않습니다. 장애 때는 오답·감점·10초 제한을 적용하지 않습니다.

현재 규칙은 **채점 완료가 서버에서 승인된 시각**이 선착 기준입니다. 경기 종료 후 도착한 결과는 점수에 반영되지 않습니다. OpenAI 처리 지연도 경기 시간에 포함됩니다. 이는 전용 채점 서비스와 동등한 지연 시간 보장이 아니므로, 리허설에서 대회 진행에 적합한지 판단해야 합니다.

## 9. 기록 보존 확인

OpenAI 채점 연결과 경기 기록 저장은 별개입니다. 무료 Render의 임시 SQLite는 휴면·재시작·재배포 때 사라질 수 있습니다. 이 버전은 DB를 외부 저장소로 자동 이전하지 않습니다. 일회성 테스트에는 사용할 수 있지만 지속적인 정식 운영에는 영속 저장 구성이 필요합니다. 선택용 `render-paid.yaml`은 유료이므로 추가 비용을 원하지 않으면 적용하지 마세요.

## 비용과 검증 범위

키 자체를 구매하는 것이 아니라 API 사용량을 결제합니다. 매 제출마다 새 실행 컨테이너를 사용하므로 제출 횟수가 늘면 비용이 늘어납니다. 정확한 비용은 https://developers.openai.com/api/docs/pricing 의 컨테이너·모델·이미지 요금과 실제 Usage에서 확인하세요. 실패한 요청도 서비스 측에서 실행됐다면 사용료가 발생할 수 있습니다.

자동 검증: 35개 문제의 정답 코드, 대회 진행, 원격 실행 프로그램의 정상/오답/오류/시간초과 처리, 명령 변조/실행 로그 누락 거부, API 장애 시 점수·대기시간 미반영을 확인했습니다. 유료 API 실연결, 이미지 실생성, 25명 동시 API 부하, 실제 브라우저 클릭 검증은 아직 수행하지 않았습니다.

공식 문서: [Code Interpreter](https://developers.openai.com/api/docs/guides/tools-code-interpreter), [이미지 생성](https://developers.openai.com/api/docs/guides/image-generation), [Render 무료 서비스](https://render.com/docs/free).
