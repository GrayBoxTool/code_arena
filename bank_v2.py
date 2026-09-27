"""New rounds and paired finals. Deterministic server-only hidden cases."""
import random


def build_bank(old):
    bank = [dict(p) for p in old]
    rng = random.Random(9282026)

    def add(round_no, level, title, statement, inp, out, kind, hint, solution, cases, final=False):
        pid = f'F{"A" if round_no == 6 else "B"}-L{level}' if final else f'S{round_no}-L{level}'
        p = dict(id=pid, set=round_no, level=level, title=title, statement=statement,
                 input=inp, output=out, tag=kind, hint1=kind, hint2=hint,
                 solution=solution, cases=cases)
        bank[:] = [x for x in bank if x['id'] != pid]
        bank.append(p)

    def arrays(nlow, nhigh, low, high, count=14):
        result = []
        for _ in range(count):
            n = rng.randint(nlow, nhigh)
            a = [rng.randint(low, high) for _ in range(n)]
            result.append((n, a))
        return result

    subset = '''n,k,target=map(int,input().split())
a=list(map(int,input().split()))
answer=0
for mask in range(1<<n):
    count=0
    total=0
    for i in range(n):
        if mask & (1<<i):
            count+=1
            total+=a[i]
    if count==k and total==target:
        answer+=1
print(answer)'''
    cases=[]
    for n,a in arrays(1,12,0,9):
        k=rng.randint(0,n); target=sum(a[:k]) if len(cases)%2 else rng.randint(0,40)
        cases.append(f'{n} {k} {target}\n'+ ' '.join(map(str,a))+'\n')
    add(1,5,'정찰대 편성','서로 구별되는 대원 N명의 능력치가 주어진다. 정확히 K명을 골라 능력치 합이 V가 되는 선택의 수를 구하라.\n능력치가 같아도 대원 번호가 다르면 다른 선택이다. 선택 순서는 고려하지 않는다. K=0일 때 빈 선택 하나의 합은 0이다.',
        'N K V(1≤N≤12, 0≤K≤N, 0≤V≤108). 다음 줄 능력치 N개(0~9).','조건을 만족하는 선택 수.',
        '부분집합 / 비트마스크','비트마스크마다 선택한 원소 수와 합을 함께 세세요.',subset,cases)
    cases=[f'{n} {rng.randint(1,n)}\n' for n in range(1,16)]
    add(2,5,'완전 트리의 관측 구역','노드가 1부터 N까지 번호를 가진 완전 이진 트리다. 노드 i의 왼쪽 자식은 2i, 오른쪽 자식은 2i+1이며 N을 넘는 번호는 없다.\n노드 K 자신과 그 아래의 모든 자손을 합친 노드 수를 구하라.',
        'N K(1≤K≤N≤1000).','K를 루트로 하는 서브트리의 노드 수.','트리 / DFS',
        '노드 번호가 N 이하일 때만 자신을 세고 두 자식으로 내려가세요.',
        'n,k=map(int,input().split())\ndef count(x):\n    if x>n: return 0\n    return 1+count(x*2)+count(x*2+1)\nprint(count(k))',cases+['1000 1\n','1000 500\n'])
    cases=[]
    for n,a in arrays(1,12,1,15):
        cases.append(f'{n} {rng.randint(0,sum(a)+5)}\n'+ ' '.join(map(str,a))+'\n')
    add(3,5,'목표 이상 보급','보급 상자 N개 중 원하는 상자를 골라 합을 V 이상으로 만든다. 가능한 합 중 가장 작은 값을 구하라.\n상자는 각각 최대 한 번 사용하며, V=0이면 아무것도 고르지 않아도 된다. 불가능하면 -1이다.',
        'N V(1≤N≤12, 0≤V≤200). 다음 줄 크기 N개(1~15).','최소 합 또는 -1.','부분집합 / 완전 탐색',
        '각 상자를 선택하거나 건너뛰는 경우를 모두 확인하고 V 이상인 최소 합을 기록하세요.',
        'n,v=map(int,input().split())\na=list(map(int,input().split()))\nsums=[0]\nfor x in a:\n    sums += [s+x for s in sums]\npossible=[s for s in sums if s>=v]\nprint(min(possible) if possible else -1)',cases)
    add(4,1,'온도 상승량','시간순 온도에서 바로 이전 측정보다 상승한 양만 더하라. 첫 측정은 비교 대상이 없어 합에 넣지 않는다.',
        'N(1≤N≤100). 다음 줄 온도 N개(-50~50).','상승량 합.','순회 / 인접 비교','현재 온도와 바로 전 온도의 차이가 양수일 때만 더하세요.',
        'n=int(input())\na=list(map(int,input().split()))\nprint(sum(max(0,a[i]-a[i-1]) for i in range(1,n)))',
        [f'{n}\n'+ ' '.join(map(str,a))+'\n' for n,a in arrays(1,100,-50,50)])
    add(4,2,'사라지는 문자 쌍','문자열을 왼쪽부터 읽는다. 이미 남긴 문자열의 마지막 문자와 새 문자가 같으면 두 문자를 없앤다. 다르면 새 문자를 끝에 붙인다.\n모든 문자를 읽은 뒤 남은 문자열의 길이를 구하라.',
        'A, B, C로 된 문자열 한 줄(1≤길이≤100).','남은 길이.','스택','스택의 맨 위와 같으면 pop, 다르면 push하세요.',
        's=input().strip()\nst=[]\nfor ch in s:\n    if st and st[-1]==ch: st.pop()\n    else: st.append(ch)\nprint(len(st))',
        [s+'\n' for s in ['A','AA','ABBA','ABC','ABCCBA','AAAAA']]+[''.join(rng.choice('ABC') for _ in range(rng.randint(1,100)))+'\n' for _ in range(10)])
    grids=[]
    for _ in range(15):
        n=rng.randint(1,6); grids.append(f'{n}\n'+'\n'.join(''.join(rng.choice('01') for _ in range(n)) for _ in range(n))+'\n')
    add(4,3,'섬의 수','N×N 지도에서 1은 땅, 0은 물이다. 상하좌우로 맞닿은 땅은 같은 섬이다. 대각선 접촉은 연결이 아니다. 섬의 수를 구하라.',
        'N(1≤N≤6). 다음 N줄에 공백 없는 0과 1 N개.','섬의 수.','DFS / 연결 요소','새로운 땅을 만나면 섬 수를 늘리고 연결된 땅을 모두 방문 처리하세요.',
        '''n=int(input())
g=[list(input().strip()) for _ in range(n)]
answer=0
for r in range(n):
    for c in range(n):
        if g[r][c]!='1': continue
        answer+=1
        g[r][c]='0'
        st=[(r,c)]
        while st:
            x,y=st.pop()
            for dx,dy in ((1,0),(-1,0),(0,1),(0,-1)):
                nx,ny=x+dx,y+dy
                if 0<=nx<n and 0<=ny<n and g[nx][ny]=='1':
                    g[nx][ny]='0'
                    st.append((nx,ny))
print(answer)''',grids)
    add(4,4,'최소 힙의 조상','주어진 순서대로 값을 최소 힙에 삽입한다. 배열 인덱스는 1부터 시작한다. 삽입된 값은 부모보다 작을 때만 교환한다.\n모두 삽입한 뒤 마지막 노드 N의 조상에 저장된 값의 합을 구하라. N 자신은 제외한다.',
        'N(1≤N≤100). 다음 줄 정수 N개(1~1000). 중복이 가능하다.','조상 값의 합. N=1이면 0.','이진 최소 힙','삽입 시 부모와 비교해 올린 뒤 N//2부터 부모 번호를 따라가세요.',
        '''n=int(input())
a=list(map(int,input().split()))
h=[0]
for x in a:
    h.append(x)
    i=len(h)-1
    while i>1 and h[i]<h[i//2]:
        h[i],h[i//2]=h[i//2],h[i]
        i//=2
answer=0
i=n//2
while i:
    answer+=h[i]
    i//=2
print(answer)''',[f'{n}\n'+ ' '.join(map(str,a))+'\n' for n,a in arrays(1,100,1,1000)])
    add(4,5,'오른쪽 아래 보급로','N×N 격자의 왼쪽 위에서 오른쪽 아래로 이동한다. 오른쪽 또는 아래로만 한 칸 이동할 수 있다. 방문한 모든 칸의 비용을 더한 최솟값을 구하라. 시작 칸과 도착 칸도 포함한다.',
        'N(1≤N≤8). 다음 N줄에 비용 N개(0~9), 공백 구분.','최소 비용.','동적 계획법 / 격자','각 칸까지의 최소 비용은 위와 왼쪽 중 작은 비용에 현재 칸 비용을 더한 값입니다.',
        '''n=int(input())
g=[list(map(int,input().split())) for _ in range(n)]
for r in range(n):
    for c in range(n):
        if r==0 and c==0: continue
        best=10**9
        if r: best=min(best,g[r-1][c])
        if c: best=min(best,g[r][c-1])
        g[r][c]+=best
print(g[-1][-1])''',[f'{n}\n'+'\n'.join(' '.join(str(rng.randint(0,9)) for _ in range(n)) for _ in range(n))+'\n' for n in [1,2,3,4,5,6,7,8,2,4,6,8]])
    add(5,1,'신호 범위 검사','정수 신호 N개 중 L 이상 R 이하인 신호의 개수를 센다. 같은 값이 여러 번 등장하면 각각 센다.',
        'N L R(1≤N≤100, -50≤L≤R≤50). 다음 줄 신호 N개(-50~50).','범위 안 신호의 개수.','순회 / 조건문','양쪽 경계를 포함하는지 비교하세요.',
        'n,l,r=map(int,input().split())\na=list(map(int,input().split()))\nprint(sum(l<=x<=r for x in a))',
        [f'{n} -10 20\n'+ ' '.join(map(str,a))+'\n' for n,a in arrays(1,100,-50,50)])
    cases=[]
    for _ in range(15):
        a=''.join(rng.choice('AB') for _ in range(rng.randint(1,70)))
        b=''.join(rng.choice('AB') for _ in range(rng.randint(1,5)))
        cases.append(a+' '+b+'\n')
    add(5,2,'단축키 입력','문자열 A를 처음부터 입력한다. 키 한 번으로 문자 한 개 또는 문자열 B 전체를 입력할 수 있다. 지우기는 불가능하다. A를 완성하는 최소 키 입력 수를 구하라.',
        'A B가 공백으로 구분되어 한 줄에 주어진다. A와 B는 A, B 문자로 구성되며 1≤길이(A)≤100, 1≤길이(B)≤10이다.','최소 입력 횟수.','문자열 / 그리디','현재 위치부터 B와 일치하면 B 길이만큼, 아니면 한 칸 전진하세요.',
        'a,b=input().split()\ni=0\ncount=0\nwhile i<len(a):\n    i+=len(b) if a.startswith(b,i) else 1\n    count+=1\nprint(count)',cases)
    add(5,3,'네 자리 탐사 번호','3×3 격자에서 아무 칸이나 출발해 상하좌우로 세 번 이동한다. 출발 칸을 포함해 네 칸의 숫자를 이어 붙인 서로 다른 문자열 수를 구하라.\n방문한 칸에 다시 가도 되고, 앞자리 0도 문자열의 일부다.',
        '숫자 0~3이 공백으로 구분된 3줄. 각 줄은 숫자 3개다.','서로 다른 네 자리 문자열 수.','DFS / 집합','모든 시작 칸에서 길이가 4가 될 때까지 탐색하고 완성 문자열을 집합에 넣으세요.',
        '''g=[input().split() for _ in range(3)]
found=set()
def dfs(r,c,s):
    if len(s)==4:
        found.add(s)
        return
    for dr,dc in ((1,0),(-1,0),(0,1),(0,-1)):
        nr,nc=r+dr,c+dc
        if 0<=nr<3 and 0<=nc<3: dfs(nr,nc,s+g[nr][nc])
for r in range(3):
    for c in range(3): dfs(r,c,g[r][c])
print(len(found))''',['\n'.join(' '.join(str(rng.randint(0,3)) for _ in range(3)) for _ in range(3))+'\n' for _ in range(14)])
    add(5,4,'이진 탐색 횟수','페이지는 1부터 P까지다. left=1, right=P로 시작하고 center=(left+right)//2를 계산한다. 목표면 종료하고, 목표가 작으면 right=center-1, 크면 left=center+1로 바꾼다.\n목표 A와 B를 각각 찾을 때 계산한 center 횟수를 비교한다. A가 적으면 A, B가 적으면 B, 같으면 TIE를 출력한다.',
        'P A B(1≤A,B≤P≤1000000).','A, B 또는 TIE.','이진 탐색','두 목표에 같은 탐색 함수를 적용하고 center를 계산할 때마다 횟수를 늘리세요.',
        '''p,a,b=map(int,input().split())
def search(target):
    l,r=1,p
    count=0
    while l<=r:
        count+=1
        m=(l+r)//2
        if m==target: return count
        if target<m: r=m-1
        else: l=m+1
x,y=search(a),search(b)
print('A' if x<y else 'B' if y<x else 'TIE')''',[f'{p} {rng.randint(1,p)} {rng.randint(1,p)}\n' for p in [1,2,3,4,5,10,20,50,100,1000,9999,1000000,7,8]])
    # A small subset task fits the five-minute last level without a long graph implementation.
    add(5,5,'세 장의 암호 카드','서로 다른 위치의 카드 정확히 세 장을 골라 합이 V 이하이면서 가장 크게 만든다.\n카드에 같은 수가 있어도 다른 카드다. 세 장을 고를 수 없으면 -1이다.',
        'N V(3≤N≤40, 0≤V≤300). 다음 줄 카드 값 N개(1~100).','가장 큰 합 또는 -1.','완전 탐색 / 조합','i<j<k인 세 인덱스만 확인하면 중복 선택을 피할 수 있습니다.',
        'n,v=map(int,input().split())\na=list(map(int,input().split()))\nans=-1\nfor i in range(n):\n    for j in range(i+1,n):\n        for k in range(j+1,n):\n            s=a[i]+a[j]+a[k]\n            if s<=v: ans=max(ans,s)\nprint(ans)',
        [f'{n} {rng.randint(0,300)}\n'+ ' '.join(map(str,a))+'\n' for n,a in arrays(3,40,1,100)])
    for side in (6,7):
        suffix='청색' if side==6 else '적색'
        mode='min' if side==6 else 'max'
        add(side,1,suffix+' 보급 창',f'연속한 정확히 K개 보급량의 합 중 {"최솟값" if side==6 else "최댓값"}을 구하라. 보급량은 음수일 수도 있다.',
            'N K(1≤K≤N≤500). 다음 줄 보급량 N개(-100~100).','조건에 맞는 합.','슬라이딩 윈도우 / 누적합','처음 K개 합을 구하고 한 칸 이동할 때 빠진 값을 빼고 새 값을 더하세요.',
            f'n,k=map(int,input().split())\na=list(map(int,input().split()))\ns=sum(a[:k])\nans=s\nfor i in range(k,n):\n    s+=a[i]-a[i-k]\n    ans={mode}(ans,s)\nprint(ans)',
            [f'{n} {rng.randint(1,n)}\n'+ ' '.join(map(str,a))+'\n' for n,a in arrays(1,500,-100,100)],True)
        directions='((1,0),(-1,0),(0,1),(0,-1))' if side==6 else '((1,1),(1,-1),(-1,1),(-1,-1))'
        movement='상하좌우' if side==6 else '네 대각선 방향'
        sol=f'''n=int(input())
g=[input().strip() for _ in range(n)]
q=[(0,0,0)]
seen={{(0,0)}}
head=0
answer=-1
while head<len(q):
    r,c,d=q[head]
    head+=1
    if r==n-1 and c==n-1:
        answer=d
        break
    for dr,dc in {directions}:
        nr,nc=r+dr,c+dc
        if 0<=nr<n and 0<=nc<n and g[nr][nc]=='0' and (nr,nc) not in seen:
            seen.add((nr,nc))
            q.append((nr,nc,d+1))
print(answer)'''
        cases=[]
        for n in [2,3,4,5,6,7,8,9,10,3,6,10]:
            g=[[rng.choice('0001') for _ in range(n)] for _ in range(n)]; g[0][0]=g[-1][-1]='0'
            cases.append(str(n)+'\n'+'\n'.join(''.join(row) for row in g)+'\n')
        add(side,2,suffix+' 전송 미로',f'N×N 격자에서 왼쪽 위에서 오른쪽 아래로 이동한다. {movement}으로 한 칸씩 움직이며 1인 칸에는 들어갈 수 없다.\n한 번 이동할 때 1회로 센다. 도착할 수 없으면 -1을 출력한다.'+(' 대각선 사이의 가로·세로 칸은 검사하지 않는다.' if side==7 else ''),
            'N(2≤N≤10). 다음 N줄에 공백 없는 0,1 문자열. 시작과 도착 칸은 0이다.','최소 이동 횟수 또는 -1.','BFS / 최단 거리','방문 칸을 기록하며 큐에서 가까운 칸부터 꺼내세요.',sol,cases,True)
        init='1' if side==6 else 'n'; change='1' if side==6 else '-1'
        add(side,3,suffix+' 트리 암호',f'노드 번호 1~N의 완전 이진 트리에 중위 순회(왼쪽, 자신, 오른쪽) 순서로 {"1부터 N까지 증가하는" if side==6 else "N부터 1까지 감소하는"} 값을 저장한다.\n루트에 저장된 값과 노드 K에 저장된 값을 출력하라. 자식 번호가 N을 넘으면 그 자식은 없다.',
            'N K(1≤K≤N≤500).','루트 값과 K번 노드 값, 공백 구분.','이진 트리 / 중위 순회','노드 번호와 노드에 저장하는 값을 구분하고 순회 중 현재 값을 배정하세요.',
            f'n,k=map(int,input().split())\na=[0]*(n+1)\nvalue=[{init}]\ndef visit(i):\n    if i>n: return\n    visit(i*2)\n    a[i]=value[0]\n    value[0]+={change}\n    visit(i*2+1)\nvisit(1)\nprint(a[1],a[k])',
            [f'{n} {rng.randint(1,n)}\n' for n in [1,2,3,4,5,7,8,10,31,50,100,500,255,256]],True)
        direction_note='1번에서 2~N번 각각으로 가는' if side==6 else '1~N-1번 각각에서 N번으로 가는'
        sol='''import heapq
n,m=map(int,input().split())
g=[[] for _ in range(n+1)]
for _ in range(m):
    u,v,w=map(int,input().split())
    EDGE
start=START
dist=[10**9]*(n+1)
dist[start]=0
q=[(0,start)]
while q:
    cost,u=heapq.heappop(q)
    if cost!=dist[u]: continue
    for v,w in g[u]:
        if cost+w<dist[v]:
            dist[v]=cost+w
            heapq.heappush(q,(dist[v],v))
print(*VALUES)'''.replace('EDGE','g[u].append((v,w))' if side==6 else 'g[v].append((u,w))').replace('START','1' if side==6 else 'n').replace('VALUES','dist[2:]' if side==6 else 'dist[1:n]')
        cases=[relay_case(side,rng.randint(5,16),rng) for _ in range(14)]
        add(side,4,suffix+' 경로 해독',f'방향이 있는 도로의 통행료가 주어진다. {direction_note} 최소 통행료를 번호 순서대로 구하라. 모든 해당 경로는 존재한다.\n정답을 제출하면 서버가 별도로 검사한 팀 전용 경로 비용 목록을 레벨 5 담당자에게 전달한다. 직접 채팅으로 전달할 필요는 없다.',
            'N M(5≤N≤16, N-1≤M≤60). 다음 M줄 u v w(1≤u,v≤N, u≠v, 1≤w≤30). 중복 도로가 가능하다.','N-1개의 최소 비용을 공백으로 구분해 출력한다.','최단 경로 / 다익스트라',
            'A형은 출발점에서 탐색하세요. B형은 모든 도로를 뒤집고 도착점에서 탐색하면 각 출발점의 비용을 한 번에 구할 수 있습니다.',sol,cases,True)
        extremum='최소' if side==6 else '최대'
        sol=f'''n,k=map(int,input().split())
a=list(map(int,input().split()))
answers=[]
def dfs(i,count,total):
    if count==k:
        answers.append(total)
        return
    if i>=n: return
    dfs(i+1,count,total)
    dfs(i+2,count+1,total+a[i])
dfs(0,0,0)
print({mode}(answers))'''
        cases=[f'{n} {rng.randint(1,(n+1)//2)}\n'+ ' '.join(map(str,a))+'\n' for n,a in arrays(4,15,1,450)]
        add(side,5,suffix+' 최종 장치',f'일렬로 놓인 N개 장치에서 정확히 K개를 선택한다. 바로 이웃한 두 장치를 동시에 선택할 수 없다. 첫 장치와 마지막 장치는 이웃이 아니다.\n선택한 장치 비용 합의 {extremum}값을 구하라.\n일반 입력 형식과 예제로 코드를 미리 작성할 수 있다. 승리 판정에는 레벨 4 정답 후 공개되는 팀 전용 비용 목록을 사용하는 최종 검증이 추가된다. 그 전에는 레벨 5 제출이 잠겨 있다.',
            'N K(4≤N≤15, 1≤K≤(N+1)//2). 다음 줄 양의 비용 N개(1~450).','조건에 맞는 '+extremum+' 비용 합.','백트래킹 / 조합',
            '현재 장치를 고르면 다음 장치는 건너뛰세요. 고른 개수가 K일 때 비용 합을 후보에 넣으세요.',sol,cases,True)
    return sorted(bank,key=lambda p:(p['set'],p['level']))


def relay_case(side, n=12, rng=None):
    rng=rng or random.Random(2026+side)
    edges=[(i,i+1,rng.randint(1,30)) for i in range(1,n)]
    for _ in range(min(60-(n-1),n*2)):
        u,v=rng.sample(range(1,n+1),2)
        edges.append((u,v,rng.randint(1,30)))
    return f'{n} {len(edges)}\n'+'\n'.join(f'{u} {v} {w}' for u,v,w in edges)+'\n'
