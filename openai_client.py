"""Small standard-library OpenAI client. Never retries billable requests automatically."""
import json,os,secrets,urllib.request,urllib.error

class APIError(ValueError): pass

def multipart(fields,files):
    boundary='rumble'+secrets.token_hex(16); chunks=[]
    for key,value in fields.items():
        chunks.append(f'--{boundary}\r\nContent-Disposition: form-data; name="{key}"\r\n\r\n{value}\r\n'.encode())
    for field,name,mime,content in files:
        chunks.append(f'--{boundary}\r\nContent-Disposition: form-data; name="{field}"; filename="{name}"\r\nContent-Type: {mime}\r\n\r\n'.encode()+content+b'\r\n')
    chunks.append(f'--{boundary}--\r\n'.encode())
    return b''.join(chunks),'multipart/form-data; boundary='+boundary

def request(path,payload=None,*,method=None,raw=None,content_type=None,timeout=30):
    key=os.environ.get('OPENAI_API_KEY','').strip()
    if not key: raise APIError('Render Environment에 OPENAI_API_KEY를 설정하세요.')
    data=raw if raw is not None else json.dumps(payload).encode() if payload is not None else None
    req=urllib.request.Request('https://api.openai.com/v1/'+path,data=data,method=method,
        headers={'Authorization':'Bearer '+key,'Content-Type':content_type or 'application/json'})
    try:
        with urllib.request.urlopen(req,timeout=timeout) as r:
            body=r.read();return json.loads(body) if body else {}
    except urllib.error.HTTPError as e:
        reason={401:'API 키가 잘못되었거나 만료되었습니다.',403:'모델·도구 접근 권한 또는 조직 인증을 확인하세요.',429:'API 잔액 또는 요청 한도를 확인하세요.',400:'모델과 API 설정을 확인하세요.'}.get(e.code,'OpenAI 서비스 응답 오류입니다.')
        rid=e.headers.get('x-request-id','')
        raise APIError(f'OpenAI HTTP {e.code}: {reason}'+(f' 요청 ID: {rid}' if rid else '')) from None
    except (urllib.error.URLError,TimeoutError,OSError): raise APIError('OpenAI 응답 지연 또는 연결 실패입니다. 잠시 후 다시 시도하세요.') from None
    except (ValueError,TypeError): raise APIError('OpenAI 응답 형식이 잘못되었습니다.') from None
