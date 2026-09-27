"""Fifteen original, self-contained programming problems.

The `cases` and `solution` fields never leave the server. All input/output
is UTF-8 plain text; submissions are ordinary Python stdin/stdout programs.
"""

PROBLEMS = [
    dict(id="S1-L1", set=1, level=1, title="충전 기록", tag="반복문·조건문",
         statement="배터리 잔량의 하루별 변화량이 주어진다. 양수인 변화량만 더해 총 충전량을 출력하라.",
         input="첫 줄 N(1≤N≤100), 다음 줄에 변화량 N개(-100~100).", output="양수 변화량의 합.",
         cases=["5\n3 -2 0 7 -4\n", "1\n-8\n", "1\n100\n", "4\n0 0 0 0\n", "6\n-1 1 -2 2 -3 3\n", "3\n99 99 -100\n"],
         hint1="구현 / 순회", hint2="각 값을 순서대로 읽고 0보다 큰 값만 누적하세요.",
         solution="n=int(input()); a=list(map(int,input().split())); print(sum(x for x in a if x>0))"),
    dict(id="S1-L2", set=1, level=2, title="보관함 잠금 로그", tag="스택",
         statement="잠금 기호 ( ) [ ]가 기록된 문자열이 있다. 모든 닫는 기호가 가장 최근의 같은 종류 여는 기호와 짝을 이루면 YES, 아니면 NO를 출력하라.",
         input="괄호만으로 된 문자열 한 줄(1≤길이≤30).", output="YES 또는 NO.",
         cases=["([])\n", "([)]\n", "(([]))\n", "]\n", "(()\n", "[][]()\n", "([[]])()\n"],
         hint1="스택", hint2="여는 기호를 쌓고 닫는 기호에서는 맨 위를 비교하세요. 마지막에 스택이 비어야 합니다.",
         solution="s=input().strip(); st=[]; pair={')':'(',']':'['}; ok=True\nfor c in s:\n if c in '([': st.append(c)\n elif not st or st.pop()!=pair[c]: ok=False; break\nprint('YES' if ok and not st else 'NO')"),
    dict(id="S1-L3", set=1, level=3, title="폐쇄된 통로", tag="BFS",
         statement="지도에서 S에서 E까지 상하좌우로 이동한다. #은 벽이고 .은 빈 칸이다. 최단 이동 횟수를 출력하라. 도달할 수 없으면 -1이다.",
         input="첫 줄 R C(1≤R,C≤6), 다음 R줄에 길이 C의 지도. S와 E는 각각 한 개.", output="최단 이동 횟수 또는 -1.",
         cases=["3 4\nS...\n##.#\n...E\n", "1 2\nSE\n", "3 3\nS##\n###\n##E\n", "4 4\nS#..\n.#.#\n.#..\n...E\n", "2 5\nS...E\n.....\n", "3 3\nS..\n.#.\n..E\n"],
         hint1="그래프 탐색 / BFS", hint2="S에서 시작해 큐로 거리 순서대로 탐색하고, 방문한 칸은 다시 넣지 마세요.",
         solution="from collections import deque\nr,c=map(int,input().split()); g=[input().strip() for _ in range(r)]; sr,sc=next((i,j) for i in range(r) for j in range(c) if g[i][j]=='S'); q=deque([(sr,sc,0)]); seen={(sr,sc)}; ans=-1\nwhile q:\n i,j,d=q.popleft()\n if g[i][j]=='E': ans=d; break\n for di,dj in ((1,0),(-1,0),(0,1),(0,-1)):\n  ni,nj=i+di,j+dj\n  if 0<=ni<r and 0<=nj<c and g[ni][nj]!='#' and (ni,nj) not in seen: seen.add((ni,nj)); q.append((ni,nj,d+1))\nprint(ans)"),
    dict(id="S1-L4", set=1, level=4, title="작업 시간표", tag="정렬·그리디",
         statement="작업마다 시작 시각과 종료 시각이 있다. 서로 겹치지 않게 수행할 수 있는 작업 수의 최댓값을 구하라. 한 작업의 종료 시각에 다음 작업을 바로 시작할 수 있다.",
         input="첫 줄 N(1≤N≤12), 다음 N줄에 시작 종료(0≤시작<종료≤30).", output="최대 작업 수.",
         cases=["4\n1 3\n2 5\n3 6\n6 7\n", "1\n0 10\n", "3\n0 2\n2 4\n4 6\n", "3\n0 10\n1 2\n2 3\n", "5\n1 3\n1 2\n2 4\n3 5\n5 6\n", "3\n5 6\n0 1\n2 3\n"],
         hint1="정렬 / 그리디", hint2="종료 시각이 빠른 작업부터 고르고, 직전에 선택한 종료 시각 이후 시작하는 작업만 세세요.",
         solution="n=int(input()); jobs=sorted((tuple(map(int,input().split())) for _ in range(n)),key=lambda x:x[1]); end=-1; count=0\nfor s,e in jobs:\n if s>=end: end=e; count+=1\nprint(count)"),
    dict(id="S1-L5", set=1, level=5, title="가장 싼 도로", tag="다익스트라",
         statement="1번 도시에서 N번 도시까지 방향 있는 도로로 이동한다. 도로의 통행료 합이 가장 적은 경로의 비용을 구하라. 갈 수 없다면 -1을 출력하라.",
         input="첫 줄 N M(2≤N≤10, 0≤M≤25), 다음 M줄 u v w(1≤w≤30).", output="최소 통행료 또는 -1.",
         cases=["4 4\n1 2 5\n2 4 5\n1 3 2\n3 4 20\n", "2 1\n1 2 9\n", "3 1\n1 2 2\n", "3 3\n1 2 8\n2 3 9\n1 3 20\n", "4 5\n1 2 1\n2 3 10\n3 4 1\n1 3 5\n2 4 20\n", "3 2\n1 2 1\n2 3 1\n"],
         hint1="최단 경로 / 다익스트라", hint2="도시까지의 최솟값을 저장하고, 현재 비용이 가장 낮은 도시의 다음 도로를 갱신하세요.",
         solution="import heapq\nn,m=map(int,input().split()); g=[[] for _ in range(n+1)]\nfor _ in range(m):\n u,v,w=map(int,input().split()); g[u].append((v,w))\nINF=10**9; dist=[INF]*(n+1); dist[1]=0; q=[(0,1)]\nwhile q:\n d,u=heapq.heappop(q)\n if d!=dist[u]: continue\n for v,w in g[u]:\n  if d+w<dist[v]: dist[v]=d+w; heapq.heappush(q,(d+w,v))\nprint(dist[n] if dist[n]<INF else -1)"),
    dict(id="S2-L1", set=2, level=1, title="첫 중복 신호", tag="집합",
         statement="왼쪽부터 들어오는 정수 신호에서 처음으로 이전에 등장한 신호를 출력하라. 끝까지 중복이 없으면 -1.",
         input="첫 줄 N(1≤N≤100), 다음 줄 정수 N개(0~1000).", output="처음 재등장한 값 또는 -1.",
         cases=["6\n7 3 9 3 7 9\n", "3\n1 2 3\n", "1\n8\n", "4\n0 0 1 1\n", "5\n5 4 3 2 5\n", "5\n8 7 8 7 8\n"],
         hint1="집합 / 순회", hint2="이미 본 값을 집합에 넣고, 매 값마다 집합에 존재하는지 먼저 확인하세요.",
         solution="n=int(input()); a=list(map(int,input().split())); seen=set(); ans=-1\nfor x in a:\n if x in seen: ans=x; break\n seen.add(x)\nprint(ans)"),
    dict(id="S2-L2", set=2, level=2, title="연속 보급 구간", tag="슬라이딩 윈도우",
         statement="연속한 K일의 보급량 합 중 최솟값을 구하라.",
         input="첫 줄 N K(1≤K≤N≤1000), 다음 줄 N개의 보급량(0~1000).", output="K일 연속 합의 최솟값.",
         cases=["5 3\n6 2 5 1 4\n", "1 1\n7\n", "4 4\n1 2 3 4\n", "5 1\n9 4 8 0 2\n", "6 2\n1 9 2 8 3 7\n", "5 3\n4 4 4 4 4\n"],
         hint1="누적합 / 슬라이딩 윈도우", hint2="첫 K개를 합한 다음 한 칸 이동할 때 빠지는 값은 빼고 들어오는 값은 더하세요.",
         solution="n,k=map(int,input().split()); a=list(map(int,input().split())); now=sum(a[:k]); ans=now\nfor i in range(k,n): now+=a[i]-a[i-k]; ans=min(ans,now)\nprint(ans)"),
    dict(id="S2-L3", set=2, level=3, title="분리된 기지", tag="DFS·BFS",
         statement="N개의 기지가 M개의 양방향 통로로 연결되어 있다. 서로 오갈 수 있는 기지 묶음의 개수를 구하라.",
         input="첫 줄 N M(1≤N≤15, 0≤M≤25), 다음 M줄 u v(1≤u,v≤N).", output="연결 요소 개수.",
         cases=["5 2\n1 2\n4 5\n", "1 0\n", "4 3\n1 2\n2 3\n3 4\n", "5 0\n", "6 4\n1 2\n2 3\n4 5\n5 6\n", "3 3\n1 2\n2 3\n1 3\n"],
         hint1="그래프 탐색", hint2="아직 방문하지 않은 기지에서 탐색을 시작할 때마다 묶음 수를 하나 올리세요.",
         solution="n,m=map(int,input().split()); g=[[] for _ in range(n+1)]\nfor _ in range(m):\n u,v=map(int,input().split()); g[u].append(v); g[v].append(u)\nseen=set(); ans=0\nfor i in range(1,n+1):\n if i in seen: continue\n ans+=1; seen.add(i); stack=[i]\n while stack:\n  for v in g[stack.pop()]:\n   if v not in seen: seen.add(v); stack.append(v)\nprint(ans)"),
    dict(id="S2-L4", set=2, level=4, title="교환권 최소 사용", tag="동적 계획법",
         statement="가치가 서로 다른 교환권을 무제한 쓸 수 있다. 정확히 V를 만들 때 필요한 최소 장수를 출력하라. 불가능하면 -1.",
         input="첫 줄 N V(1≤N≤6, 0≤V≤50), 다음 줄 N개 교환권 가치(1~50).", output="최소 장수 또는 -1.",
         cases=["3 11\n1 5 7\n", "2 3\n2 4\n", "1 0\n9\n", "3 6\n1 3 4\n", "2 12\n5 7\n", "3 14\n4 6 9\n"],
         hint1="동적 계획법", hint2="dp[x]를 x를 만드는 최소 장수로 정의하고, 작은 금액부터 각 교환권을 시험하세요.",
         solution="n,v=map(int,input().split()); coins=list(map(int,input().split())); dp=[10**9]*(v+1); dp[0]=0\nfor x in range(1,v+1):\n for c in coins:\n  if c<=x: dp[x]=min(dp[x],dp[x-c]+1)\nprint(dp[v] if dp[v]<10**9 else -1)"),
    dict(id="S2-L5", set=2, level=5, title="작업 순서 결정", tag="위상 정렬·힙",
         statement="작업 u가 v보다 먼저 끝나야 한다. 가능한 순서 중 매 단계에서 수행 가능한 작업 번호가 가장 작은 것을 선택해 모든 번호를 출력하라. 순환이 있으면 -1.",
         input="첫 줄 N M(1≤N≤12, 0≤M≤20), 다음 M줄 u v(1≤u,v≤N).", output="공백으로 구분한 작업 순서 또는 -1.",
         cases=["4 3\n1 3\n2 3\n3 4\n", "3 0\n", "3 3\n1 2\n2 3\n3 1\n", "5 3\n2 4\n1 4\n4 5\n", "4 2\n3 1\n2 1\n", "2 1\n2 1\n"],
         hint1="위상 정렬 / 우선순위 큐", hint2="진입 차수가 0인 번호들을 최소 힙에 넣고, 꺼낸 작업의 다음 작업 진입 차수를 낮추세요.",
         solution="import heapq\nn,m=map(int,input().split()); g=[[] for _ in range(n+1)]; deg=[0]*(n+1)\nfor _ in range(m):\n u,v=map(int,input().split()); g[u].append(v); deg[v]+=1\nq=[i for i in range(1,n+1) if deg[i]==0]; heapq.heapify(q); ans=[]\nwhile q:\n u=heapq.heappop(q); ans.append(u)\n for v in g[u]:\n  deg[v]-=1\n  if deg[v]==0: heapq.heappush(q,v)\nprint(' '.join(map(str,ans)) if len(ans)==n else -1)"),
    dict(id="S3-L1", set=3, level=1, title="연결하지 않은 전구", tag="순회",
         statement="전구 N개의 상태가 0(꺼짐), 1(켜짐)으로 주어진다. 켜진 전구 바로 오른쪽에 꺼진 전구가 있는 횟수를 세라. 마지막 전구의 오른쪽은 세지 않는다.",
         input="첫 줄 N(1≤N≤100), 다음 줄에 0 또는 1 N개.", output="해당하는 인접 쌍 개수.",
         cases=["6\n1 0 1 1 0 0\n", "1\n1\n", "3\n0 0 0\n", "5\n1 0 1 0 1\n", "4\n1 1 1 0\n", "4\n0 1 0 0\n"],
         hint1="순회 / 인접 비교", hint2="인덱스 0부터 N-2까지 현재가 1이고 다음이 0인 경우를 세세요.",
         solution="n=int(input()); a=list(map(int,input().split())); print(sum(a[i]==1 and a[i+1]==0 for i in range(n-1)))"),
    dict(id="S3-L2", set=3, level=2, title="돌아가는 인쇄 대기열", tag="큐",
         statement="중요도가 가장 높은 문서부터 인쇄한다. 맨 앞 문서보다 중요도가 높은 문서가 하나라도 남아 있으면 맨 앞 문서를 맨 뒤로 보낸다. 처음 위치 K인 문서는 몇 번째로 인쇄되는가? 중요도가 같은 문서는 현재 큐 순서를 따른다.",
         input="첫 줄 N K(1≤N≤10, 0≤K<N), 다음 줄 중요도 N개(1~9).", output="1부터 시작하는 인쇄 순서.",
         cases=["4 2\n1 3 2 3\n", "1 0\n9\n", "3 0\n1 2 3\n", "5 4\n2 2 2 2 2\n", "6 1\n1 1 9 1 1 1\n", "4 3\n9 1 1 8\n"],
         hint1="큐 / 시뮬레이션", hint2="(원래 인덱스, 중요도)를 큐에 넣고 맨 앞이 현재 최대 중요도보다 작으면 뒤로 이동시키세요.",
         solution="from collections import deque\nn,k=map(int,input().split()); a=list(map(int,input().split())); q=deque(enumerate(a)); cnt=0\nwhile q:\n i,p=q.popleft()\n if any(other>p for _,other in q): q.append((i,p))\n else:\n  cnt+=1\n  if i==k: print(cnt); break"),
    dict(id="S3-L3", set=3, level=3, title="목표 합 짝", tag="투 포인터",
         statement="서로 다른 N개의 정수에서 두 수를 골라 합이 T가 되는 서로 다른 쌍의 개수를 구하라. 순서는 고려하지 않는다.",
         input="첫 줄 N T(2≤N≤30, -100≤T≤100), 다음 줄 서로 다른 정수 N개(-50~50).", output="쌍의 개수.",
         cases=["5 7\n1 6 2 5 3\n", "2 0\n-1 1\n", "3 100\n1 2 3\n", "6 0\n-3 -2 -1 1 2 3\n", "4 4\n1 3 5 7\n", "5 2\n0 1 2 3 4\n"],
         hint1="정렬 / 투 포인터", hint2="정렬 후 양 끝에서 시작해 합이 목표보다 작으면 왼쪽, 크면 오른쪽 포인터를 움직이세요.",
         solution="n,t=map(int,input().split()); a=sorted(map(int,input().split())); l=0; r=n-1; ans=0\nwhile l<r:\n s=a[l]+a[r]\n if s==t: ans+=1; l+=1; r-=1\n elif s<t: l+=1\n else: r-=1\nprint(ans)"),
    dict(id="S3-L4", set=3, level=4, title="병력 합치기", tag="힙·그리디",
         statement="병력 묶음이 N개 있다. 한 번에 가장 작은 묶음 두 개를 합쳐 하나로 만들고, 새 묶음의 크기만큼 비용을 낸다. 이를 K번 반복할 때 총비용을 구하라.",
         input="첫 줄 N K(2≤N≤12, 0≤K<N), 다음 줄 양의 정수 N개(1~30).", output="총비용.",
         cases=["4 2\n1 2 3 4\n", "2 0\n3 5\n", "2 1\n3 5\n", "5 3\n1 1 1 1 1\n", "4 3\n2 2 2 2\n", "5 4\n7 1 3 2 9\n"],
         hint1="힙 / 그리디", hint2="최소 힙에서 두 개를 꺼내 더한 비용을 누적하고 새 묶음을 다시 힙에 넣으세요.",
         solution="import heapq\nn,k=map(int,input().split()); a=list(map(int,input().split())); heapq.heapify(a); total=0\nfor _ in range(k):\n x=heapq.heappop(a)+heapq.heappop(a); total+=x; heapq.heappush(a,x)\nprint(total)"),
    dict(id="S3-L5", set=3, level=5, title="기지 연결 비용", tag="최소 신장 트리",
         statement="N개 기지를 양방향 후보 케이블 M개로 모두 연결하려 한다. 필요한 케이블의 총 비용 최솟값을 구하라. 모두 연결할 수 없으면 -1.",
         input="첫 줄 N M(2≤N≤8, 0≤M≤20), 다음 M줄 u v 비용(1≤비용≤100).", output="최소 연결 비용 또는 -1.",
         cases=["4 5\n1 2 2\n1 3 6\n2 3 3\n2 4 8\n3 4 1\n", "2 0\n", "2 1\n1 2 9\n", "4 2\n1 2 1\n3 4 1\n", "3 3\n1 2 5\n2 3 6\n1 3 2\n", "5 6\n1 2 1\n2 3 2\n3 4 3\n4 5 4\n1 5 100\n2 4 1\n"],
         hint1="그래프 / 최소 신장 트리", hint2="비용 순으로 간선을 보면서 서로 다른 연결 집합을 잇는 간선만 채택하세요.",
         solution="n,m=map(int,input().split()); edges=[]\nfor _ in range(m):\n u,v,w=map(int,input().split()); edges.append((w,u,v))\np=list(range(n+1))\ndef find(x):\n while p[x]!=x: p[x]=p[p[x]]; x=p[x]\n return x\nans=0; cnt=0\nfor w,u,v in sorted(edges):\n a,b=find(u),find(v)\n if a!=b: p[a]=b; ans+=w; cnt+=1\nprint(ans if cnt==n-1 else -1)"),
]

# Short, explicit contest copy. Each case follows the same input format; the
# shared T / #tc wrapper is added by public_problem below.
EDITORIAL = {
    "S1-L1": ("하루별 배터리 잔량의 변화량 N개가 입력 순서대로 주어진다. 양수는 충전, 음수는 소모, 0은 변화가 없음을 뜻한다. 양수 값만 모두 더하라. 양수가 없다면 0을 출력한다.",
              "첫 줄 N(1≤N≤100), 다음 줄 정수 N개(-100≤값≤100).", "양수 변화량의 합."),
    "S1-L2": ("문자열은 (, ), [, ] 네 기호만으로 이루어진다. 각 닫는 괄호가 가장 최근의 같은 종류 여는 괄호와 짝을 이루고, 모든 괄호가 짝지어지면 YES를 출력한다. 그 외에는 NO를 출력한다.",
              "괄호로만 이루어진 문자열 한 줄(1≤길이≤30). 공백은 없다.", "YES 또는 NO."),
    "S1-L3": ("S에서 E까지 상하좌우로 한 칸씩 이동한다. .은 이동할 수 있는 칸이고 #은 들어갈 수 없는 벽이다. S와 E도 지나갈 수 있다. 최소 이동 횟수를 구하고, 도착할 수 없다면 -1을 출력한다.",
              "첫 줄 R C(1≤R,C≤6, R×C≥2). 이어서 길이가 C인 지도 R줄. S와 E는 서로 다른 칸에 하나씩 있다.", "S에서 E까지의 최소 이동 횟수 또는 -1."),
    "S1-L4": ("작업 N개의 시작 시각과 종료 시각이 주어진다. 한 번에 하나만 수행하며, 앞 작업의 종료 시각과 다음 작업의 시작 시각이 같아도 두 작업을 모두 수행할 수 있다. 수행 가능한 작업 수의 최댓값을 구하라.",
              "첫 줄 N(1≤N≤12). 다음 N줄에 시작 시각 s와 종료 시각 e(0≤s<e≤30).", "수행할 수 있는 최대 작업 수."),
    "S1-L5": ("1번 도시에서 N번 도시까지 방향이 있는 도로를 따라 이동한다. 도로 비용의 합이 최소인 경로의 비용을 구하라. 같은 도시 사이에 도로가 여러 개 있을 수 있으며, N번 도시에 도착할 수 없으면 -1을 출력한다.",
              "첫 줄 N M(2≤N≤10, 0≤M≤25). 다음 M줄에 출발 도시 u, 도착 도시 v, 비용 w(1≤u,v≤N, 1≤w≤30).", "최소 비용 또는 -1."),
    "S2-L1": ("정수 신호를 왼쪽부터 하나씩 확인한다. 이미 앞에서 등장한 값이 처음 다시 등장하는 순간, 그 값을 출력한다. 끝까지 재등장한 값이 없다면 -1을 출력한다. 가장 작은 값이 아니라 먼저 반복된 값이다.",
              "첫 줄 N(1≤N≤100), 다음 줄 정수 N개(0≤값≤1000).", "처음 재등장한 신호 값 또는 -1."),
    "S2-L2": ("날짜별 보급량 N개가 입력 순서대로 주어진다. 연속한 정확히 K일의 보급량 합 중 가장 작은 값을 구하라.",
              "첫 줄 N K(1≤K≤N≤1000). 다음 줄 보급량 N개(0≤값≤1000).", "연속 K일 보급량의 최소 합."),
    "S2-L3": ("번호가 1부터 N까지인 기지를 양방향 통로가 연결한다. 서로 통로를 따라 오갈 수 있는 기지들을 한 묶음으로 볼 때, 전체 묶음 수를 구하라. 통로가 없는 기지는 각각 하나의 묶음이다.",
              "첫 줄 N M(1≤N≤15, 0≤M≤25). 다음 M줄에 서로 다른 기지 u v(1≤u,v≤N). 같은 통로가 중복으로 주어질 수 있다.", "연결된 기지 묶음의 수."),
    "S2-L4": ("서로 다른 가치의 교환권 N종류가 있고, 각 종류를 원하는 만큼 사용할 수 있다. 가치의 합을 정확히 V로 만드는 데 필요한 최소 장수를 구하라. 만들 수 없다면 -1, V가 0이라면 0을 출력한다.",
              "첫 줄 N V(1≤N≤6, 0≤V≤50). 다음 줄 서로 다른 교환권 가치 N개(1≤가치≤50).", "필요한 최소 장수 또는 -1."),
    "S2-L5": ("선행 관계 u v는 작업 u를 끝낸 후 작업 v를 할 수 있다는 뜻이다. 아직 수행하지 않은 작업 중 선행 작업이 모두 끝난 번호가 가장 작은 작업부터 수행한다. 가능한 순서를 출력하고, 순환 때문에 모든 작업을 수행할 수 없다면 -1을 출력한다.",
              "첫 줄 N M(1≤N≤12, 0≤M≤20). 다음 M줄에 u v(1≤u,v≤N). 같은 선행 관계가 여러 번 나올 수 있다.", "작업 번호를 수행 순서대로 공백으로 구분해 출력한다. 불가능하면 -1."),
    "S3-L1": ("전구 N개의 상태가 왼쪽부터 0(꺼짐) 또는 1(켜짐)으로 주어진다. 왼쪽 전구가 1이고 바로 오른쪽 전구가 0인 인접한 쌍의 수를 구하라. 마지막 전구의 오른쪽에는 전구가 없다.",
              "첫 줄 N(1≤N≤100). 다음 줄에 0 또는 1인 상태 N개.", "(1, 0)인 인접한 쌍의 수."),
    "S3-L2": ("0부터 N-1까지 순서대로 놓인 문서에 중요도가 있다. 맨 앞 문서보다 중요도가 높은 문서가 큐에 하나라도 남아 있으면 그 문서를 맨 뒤로 보낸다. 그렇지 않으면 인쇄한다. 중요도가 같은 문서는 현재 순서를 따른다. 처음 위치 K인 문서가 몇 번째로 인쇄되는지 구하라.",
              "첫 줄 N K(1≤N≤10, 0≤K<N). 다음 줄 중요도 N개(1≤중요도≤9).", "K번 문서의 인쇄 순서(첫 번째는 1)."),
    "S3-L3": ("서로 다른 정수 N개 중 서로 다른 위치의 두 수를 골라 합이 T가 되는 쌍의 수를 구하라. 두 수의 순서만 바뀐 경우는 같은 쌍으로 센다.",
              "첫 줄 N T(2≤N≤30, -100≤T≤100). 다음 줄 서로 다른 정수 N개(-50≤값≤50).", "합이 T인 쌍의 수."),
    "S3-L4": ("크기가 양수인 병력 묶음 N개가 있다. 한 번의 작업에서 현재 가장 작은 묶음 두 개를 꺼내 합치고, 새 묶음의 크기만큼 비용을 낸다. 새 묶음은 다시 후보에 들어간다. 이를 정확히 K번 반복할 때 비용의 합을 구하라. 같은 크기의 묶음은 어느 것을 골라도 된다.",
              "첫 줄 N K(2≤N≤12, 0≤K<N). 다음 줄 묶음 크기 N개(1≤크기≤30).", "K번 합치는 데 드는 총비용."),
    "S3-L5": ("N개 기지를 양방향 후보 케이블로 모두 연결하려 한다. 필요한 케이블만 골라 비용 합을 최소화하라. 같은 두 기지 사이에 후보 케이블이 여러 개 있을 수 있다. 모든 기지를 연결할 수 없다면 -1을 출력한다.",
              "첫 줄 N M(2≤N≤8, 0≤M≤20). 다음 M줄에 서로 다른 기지 u v와 비용 w(1≤u,v≤N, 1≤w≤100).", "모든 기지를 연결하는 최소 비용 또는 -1."),
}

EXTRA_CASES = {
    "S1-L1": ["4\n-5 -4 -3 -2\n", "5\n2 2 2 2 2\n", "6\n100 0 -100 1 -1 99\n", "2\n0 0\n", "7\n-1 0 1 0 -2 3 4\n"],
    "S1-L2": ["()[]\n", "[(])\n", "((((()))))\n", "([][])[()]\n", "(((()\n"],
    "S1-L3": ["2 2\nS#\n#E\n", "2 3\nS..\n..E\n", "1 6\nS...#E\n", "3 4\nS.#.\n..#.\n...E\n", "4 4\nS...\n.##.\n...#\n...E\n"],
    "S1-L4": ["4\n0 1\n0 2\n1 3\n3 4\n", "3\n1 4\n1 4\n1 4\n", "4\n0 2\n2 4\n4 6\n6 8\n", "5\n2 3\n0 1\n1 2\n3 4\n0 4\n", "2\n0 30\n1 2\n"],
    "S1-L5": ["3 0\n", "3 3\n1 2 20\n1 2 2\n2 3 3\n", "4 4\n1 2 1\n2 3 1\n3 2 1\n3 4 1\n", "3 2\n2 1 1\n2 3 1\n", "5 6\n1 2 2\n2 5 20\n1 3 7\n3 4 1\n4 5 1\n1 5 15\n"],
    "S2-L1": ["5\n9 8 7 8 9\n", "4\n1 2 3 4\n", "6\n5 4 5 4 5 4\n", "3\n0 1000 0\n", "7\n1 2 3 4 5 6 1\n"],
    "S2-L2": ["5 2\n5 0 0 9 3\n", "4 1\n7 8 1 2\n", "5 5\n1 1 1 1 1\n", "7 3\n5 4 3 2 1 2 3\n", "6 4\n0 0 0 0 9 9\n"],
    "S2-L3": ["4 0\n", "4 4\n1 2\n2 3\n3 4\n1 4\n", "5 3\n1 2\n1 2\n4 5\n", "6 3\n1 2\n2 3\n4 5\n", "2 1\n2 1\n"],
    "S2-L4": ["2 0\n2 3\n", "2 9\n4 5\n", "3 12\n2 5 7\n", "2 7\n4 6\n", "4 17\n1 4 6 9\n"],
    "S2-L5": ["3 2\n1 3\n2 3\n", "3 3\n1 2\n1 2\n2 3\n", "4 4\n1 2\n2 3\n3 2\n3 4\n", "5 3\n5 2\n5 1\n2 4\n", "1 0\n"],
    "S3-L1": ["2\n1 0\n", "2\n0 1\n", "7\n1 1 0 1 0 0 1\n", "5\n0 0 0 0 0\n", "6\n1 0 1 0 1 0\n"],
    "S3-L2": ["4 0\n1 1 1 1\n", "4 2\n1 2 3 4\n", "5 3\n9 8 7 6 5\n", "3 2\n2 2 2\n", "6 5\n1 9 1 9 1 9\n"],
    "S3-L3": ["4 0\n-2 -1 1 2\n", "5 2\n-1 0 1 2 3\n", "3 100\n-50 0 50\n", "6 -1\n-5 -4 -3 2 3 4\n", "2 0\n-50 50\n"],
    "S3-L4": ["3 0\n1 2 3\n", "3 1\n1 2 10\n", "4 3\n1 1 1 1\n", "5 2\n1 3 5 7 9\n", "2 1\n30 30\n"],
    "S3-L5": ["3 3\n1 2 10\n1 2 1\n2 3 2\n", "4 0\n", "4 4\n1 2 1\n2 3 1\n3 4 1\n1 4 10\n", "5 3\n1 2 1\n2 3 1\n4 5 1\n", "3 3\n1 2 10\n2 3 10\n1 3 1\n"],
}

for problem in PROBLEMS:
    problem["statement"], problem["input"], problem["output"] = EDITORIAL[problem["id"]]
    problem["cases"].extend(EXTRA_CASES[problem["id"]])

REWARD = {1: 100, 2: 150, 3: 200, 4: 250, 5: 300}
HINT_COST = {"type": 50, "structure": 120, "assist": 250}


def reference_code(problem):
    """Make the case-level editorial solution use SWEA's T/#tc convention."""
    import textwrap
    return ("def solve_case():\n" + textwrap.indent(problem["solution"], "    ") +
            "\nT = int(input())\nfor tc in range(1, T + 1):\n"
            "    print(f'#{tc} ', end='')\n    solve_case()\n")


def judge_inputs(problem):
    """Several independent multi-case files; the first is public."""
    cases = problem["cases"]
    groups = [cases[:2]] + [cases[i:i+3] for i in range(2,len(cases),3)]
    return [str(len(group)) + "\n" + "".join(group) for group in groups]


def expected_outputs(problem):
    """Run only developer-authored reference code with controlled in-memory IO."""
    import contextlib
    import io
    result = []
    code = compile(reference_code(problem), f'<reference:{problem["id"]}>', "exec")
    for case in judge_inputs(problem):
        stdin, stdout = io.StringIO(case), io.StringIO()
        with contextlib.redirect_stdout(stdout):
            import sys
            prior = sys.stdin
            try:
                sys.stdin = stdin
                exec(code, {"__name__": "__main__"})
            finally:
                sys.stdin = prior
        result.append(stdout.getvalue())
    return result


def public_problem(problem):
    result = {k: problem[k] for k in ("id", "set", "level", "title", "statement", "input", "output")}
    result["input"] = "첫 줄에 테스트케이스 수 T(1≤T≤3)가 주어진다. 각 테스트케이스마다 " + result["input"]
    result["output"] = "각 테스트케이스의 정답을 '#tc 정답' 형식으로 한 줄씩 출력한다. " + result["output"]
    return result
