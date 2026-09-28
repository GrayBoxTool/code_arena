"""Original ten-minute final tasks, calibrated from the uploaded rumble workbook."""
import random

def build_final():
    rng=random.Random(202609282)
    bank=[]
    def nums(a):return ' '.join(map(str,a))+'\n'
    def add(side,l,title,statement,layout,inp,constraints,out,kind,hint,solution,samples,cases,explain):
        bank.append(dict(id=f'F{side}-L{l}',set=6 if side=='A' else 7,level=l,title=title,
                         statement=statement,input_format=layout,input=inp,constraints=constraints,output=out,
                         tag=kind,hint1=kind,hint2=hint,solution=solution,cases=samples+cases,sample_explanation=explain))
    add('A',1,'변경할 수 없는 수도 계약',
        '앞으로 N개월 동안 사용할 수도 회사를 하나 선택합니다. 계약 기간에는 회사를 바꿀 수 없습니다.\n\nA사는 매달 사용량 1리터당 P원을 받습니다. B사는 매달 기본요금 Q원으로 R리터까지 사용할 수 있고, 초과 사용량에는 1리터당 S원을 추가합니다. 기본요금과 무료 사용량은 매달 새로 적용됩니다.\n\n월별 사용량이 주어질 때, 한 회사만 계속 이용하는 총요금의 최솟값을 구하세요. 매달 더 싼 회사를 골라 합치면 안 됩니다.',
        'N P Q R S\nW1 W2 ... WN','첫 줄에 개월 수와 요금 정보, 다음 줄에 월별 사용량이 주어집니다.',
        '1 ≤ N ≤ 100\n1 ≤ P, Q, R, S ≤ 10000\n0 ≤ Wi ≤ 10000', '계약 기간의 최소 총요금을 출력합니다.',
        '조건문 / 누적 합','A와 B의 N개월 총요금을 따로 계산한 뒤 비교합니다. B의 기본요금은 사용량이 0인 달에도 발생합니다.',
        'n,p,q,r,s=map(int,input().split())\na=list(map(int,input().split()))\nprint(min(sum(a)*p,sum(q+max(0,w-r)*s for w in a)))',
        ['2 10 50 5 20\n1 10\n','2 9 10 100 1\n20 20\n'],
        ['1 1 1 1 1\n0\n','2 10 50 5 20\n5 6\n']+[f'{n} {rng.randint(1,100)} {rng.randint(1,100)} {rng.randint(1,100)} {rng.randint(1,100)}\n'+nums(rng.randint(0,1000) for _ in range(n)) for n in [1,2,5,20,100]*4],
        '첫 번째는 A사가 110원, B사가 200원이므로 110입니다.\n두 번째는 B사의 기본요금 10원을 두 달 내는 20원이 정답입니다.')
    add('B',1,'기한 없는 할인권 배분',
        'N장의 청구서와 K장의 할인권이 있습니다. 청구서 한 장에 할인권을 사용하면 그 청구서 금액의 절반을 할인받습니다. 할인액의 소수 부분은 버립니다.\n\n청구서 한 장에는 할인권을 최대 한 장만 쓸 수 있습니다. 할인권을 남겨도 되지만, 가능한 한 총 납부액이 작아지도록 사용하려고 합니다.\n\n모든 청구서의 금액이 주어질 때 최소 총 납부액을 구하세요.',
        'N K\na1 a2 ... aN','첫 줄에 청구서 수 N과 할인권 수 K, 다음 줄에 청구 금액 N개가 주어집니다.',
        '1 ≤ N ≤ 100\n0 ≤ K ≤ N\n0 ≤ ai ≤ 10000','할인 후 총 납부액의 최솟값을 출력합니다.',
        '정렬 / 그리디','각 청구서의 할인액은 금액 // 2입니다. 할인액이 큰 K개를 골라 원래 총액에서 빼세요.',
        'n,k=map(int,input().split())\na=list(map(int,input().split()))\nprint(sum(a)-sum(sorted((v//2 for v in a),reverse=True)[:k]))',
        ['4 2\n9 8 3 0\n','3 0\n1 2 3\n'],
        ['1 1\n1\n','3 3\n0 0 0\n']+[f'{n} {rng.randint(0,n)}\n'+nums(rng.randrange(10001) for _ in range(n)) for n in [1,2,5,30,100]*4],
        '첫 번째는 9원과 8원 청구서에서 각각 4원씩 할인받아 20 - 8 = 12원입니다.\n두 번째는 할인권이 없어 6원입니다.')
    add('A',2,'K개씩 사라지는 신호',
        '문자열을 왼쪽부터 한 글자씩 읽어 신호를 쌓습니다. 같은 문자가 연속하여 정확히 K개가 쌓이는 순간 그 K개를 모두 없앱니다.\n\n제거 후 이어진 부분에도 같은 규칙이 적용됩니다. 새 글자를 읽을 때마다 제거를 처리합니다. 모든 문자를 처리한 뒤 남은 문자열의 길이를 구하세요.\n\n원래 문제의 두 글자 제거를 일반화한 것으로, K보다 적게 남은 같은 문자는 제거하지 않습니다.',
        'K\nS','첫 줄에 제거 기준 K, 다음 줄에 공백 없는 대문자 문자열 S가 주어집니다.',
        '2 ≤ K ≤ 10\n1 ≤ 문자열 길이 ≤ 3000', '남은 문자열의 길이를 출력합니다.',
        '스택 / 연속 개수','스택에 문자와 현재 연속 개수를 함께 저장하세요. 맨 위 문자가 같으면 개수를 늘리고, K가 되면 해당 묶음을 제거합니다.',
        'k=int(input())\ns=input().strip()\nst=[]\nfor c in s:\n    if st and st[-1][0]==c: st[-1][1]+=1\n    else: st.append([c,1])\n    if st[-1][1]==k: st.pop()\nprint(sum(v for c,v in st))',
        ['3\nABBBAA\n','2\nABBA\n'],['10\n'+'A'*3000+'\n','3\nAAAA\n']+[f'{k}\n'+''.join(rng.choice('ABCD') for _ in range(n))+'\n' for k,n in [(2,10),(3,100),(5,1000),(10,3000)]*5],
        '첫 번째는 BBB가 지워진 뒤 AAA도 지워져 0입니다.\n두 번째는 BB와 AA가 지워져 0입니다.')
    add('B',2,'압축 문서의 구간 조회',
        '문자와 반복 횟수의 쌍 N개를 이어 붙이면 긴 문서가 됩니다. 문서의 위치는 1부터 시작합니다.\n\n문서를 전부 출력하는 대신, L번부터 R번까지 양 끝을 포함한 구간에서 문자 C가 몇 번 등장하는지 구하세요. 같은 문자가 이웃한 여러 압축 쌍으로 나뉘어 있을 수도 있습니다.\n\n압축을 풀면 문서가 매우 길어질 수 있습니다. 주어진 구간 밖의 문자는 답에 포함하지 않습니다.',
        'N L R C\n문자 반복횟수 (N줄)','첫 줄에 N, L, R, 찾을 문자 C가 주어집니다. 다음 N줄에 압축 쌍이 주어집니다.',
        '1 ≤ N ≤ 100\n문자는 A~Z입니다.\n1 ≤ 각 반복 횟수 ≤ 1000000\n1 ≤ L ≤ R ≤ 전체 문서 길이','구간 안에 있는 C의 개수를 출력합니다.',
        '구간 겹침 / 누적 길이','각 압축 쌍이 차지하는 시작·끝 위치를 계산하세요. 문자가 C이면 [L,R]과 겹치는 길이를 더합니다.',
        'n,l,r,target=input().split()\nn,l,r=int(n),int(l),int(r)\nstart=1\nans=0\nfor _ in range(n):\n    c,k=input().split(); k=int(k)\n    end=start+k-1\n    if c==target: ans+=max(0,min(r,end)-max(l,start)+1)\n    start=end+1\nprint(ans)',
        ['3 3 9 A\nA 5\nB 2\nA 4\n','1 1 5 B\nA 5\n'],
        ['1 1 1000000 Z\nZ 1000000\n']+[f'{n} {l} {r} {rng.choice("ABC")}\n'+''.join(f'{c} {k}\n' for c,k in blocks) for n,blocks in [(n,[(rng.choice('ABC'),rng.randint(1,1000000)) for _ in range(n)]) for n in [1,2,5,20,100]*4] for l,r in [sorted([rng.randint(1,sum(k for c,k in blocks)),rng.randint(1,sum(k for c,k in blocks))])]],
        '첫 번째는 위치 3~5의 A 세 개와 위치 8~9의 A 두 개로 총 5개입니다.\n두 번째 구간에는 B가 없으므로 0입니다.')
    add('A',3,'접두어별 검색 건수',
        '검색 대상 단어 N개와 검색어 M개가 있습니다. 각 검색어에 대해 그 검색어로 시작하는 대상 단어가 몇 개인지 구하세요.\n\n대상 단어 전체와 검색어가 같아도 포함됩니다. 동일한 대상 단어가 여러 줄에 있으면 각각 하나의 검색 결과로 셉니다. 각 검색어의 답을 입력된 순서대로 모두 출력하세요.',
        'N M\n대상 단어 N줄\n검색어 M줄','첫 줄에 N과 M, 다음 N줄에 대상 단어, 이후 M줄에 검색어가 주어집니다.',
        '1 ≤ N ≤ 3000\n1 ≤ M ≤ 300\n모든 단어와 검색어는 길이 1~20의 소문자 문자열입니다.', '검색어 M개의 결과 건수를 공백으로 구분해 출력합니다.',
        '문자열 / 접두어 빈도','대상 단어의 모든 접두어를 만들고 각각의 등장 횟수를 저장하세요. 존재 여부뿐 아니라 중복 단어 수까지 누적합니다.',
        'n,m=map(int,input().split())\nf={}\nfor _ in range(n):\n    s=input().strip()\n    for i in range(1,len(s)+1):\n        p=s[:i]; f[p]=f.get(p,0)+1\nprint(*(f.get(input().strip(),0) for _ in range(m)))',
        ['3 2\ncat\ncar\ncat\nca\ncat\n','1 1\ndog\nx\n'],
        ['3000 300\n'+'a'*20+'\n'+('abc\n'*2999)+('a\n'*300)]+[f'{n} {m}\n'+'\n'.join(''.join(rng.choice('abc') for _ in range(rng.randint(1,20))) for _ in range(n+m))+'\n' for n,m in [(1,1),(5,3),(30,10),(100,40)]*5],
        '첫 번째에서 ca로 시작하는 단어는 세 줄 모두이며 cat은 두 줄입니다. 따라서 3 2입니다.\n두 번째는 해당하는 단어가 없어 0입니다.')
    add('B',3,'누적되는 구역 경보',
        '일렬로 놓인 N개 구역의 경보 점수는 처음에 모두 0입니다. Q개의 사건이 차례로 기록됩니다.\n\n각 사건은 L번부터 R번까지의 모든 구역에 점수 V를 더합니다. 이전 점수를 덮어쓰지 않습니다.\n\n모든 사건을 반영한 뒤 가장 높은 경보 점수와, 그 점수를 가진 구역 수를 구하세요. 한 번도 영향을 받지 않은 구역의 점수는 0입니다.',
        'N Q\nL R V (Q줄)','첫 줄에 구역 수 N과 사건 수 Q, 다음 Q줄에 L, R, V가 주어집니다.',
        '1 ≤ N ≤ 10000\n0 ≤ Q ≤ 10000\n1 ≤ L ≤ R ≤ N\n1 ≤ V ≤ 1000','최고 점수와 해당 구역 수를 순서대로 출력합니다.',
        '차분 배열 / 누적합','L에서 V를 더하고 R+1에서 V를 빼는 기록만 남기세요. 마지막에 누적합을 구하면 각 구역의 점수가 됩니다.',
        'n,q=map(int,input().split())\nd=[0]*(n+2)\nfor _ in range(q):\n    l,r,v=map(int,input().split()); d[l]+=v; d[r+1]-=v\na=[]; score=0\nfor i in range(1,n+1):\n    score+=d[i]; a.append(score)\nbest=max(a)\nprint(best,a.count(best))',
        ['5 2\n1 3 2\n3 5 4\n','3 0\n'],
        ['10000 10000\n'+'1 10000 1000\n'*10000]+[f'{n} {q}\n'+''.join(nums([l,r,rng.randint(1,1000)]) for l,r in [sorted([rng.randint(1,n),rng.randint(1,n)]) for _ in range(q)]) for n,q in [(1,1),(5,10),(50,100),(1000,300)]*4],
        '첫 번째의 점수는 2, 2, 6, 4, 4입니다. 최고 점수 6인 구역은 한 개이므로 6 1입니다.\n두 번째는 모든 구역이 0이어서 0 3입니다.')
    add('A',4,'정확히 K개의 해피박스',
        '용량 C인 상자에 N개 물건 중 정확히 K개를 넣으려고 합니다. 각 물건에는 크기와 가격이 있으며, 같은 물건을 두 번 선택할 수 없습니다.\n\n크기 합은 C 이하여야 합니다. 조건을 만족하는 선택 중 가격 합의 최댓값을 구하세요. 개수가 K보다 적거나 많으면 인정하지 않습니다.\n\n어떤 방법으로도 정확히 K개를 담을 수 없다면 -1을 출력합니다. K가 0이면 빈 선택이 가능하고 가격 합은 0입니다.',
        'N C K\n크기 가격 (N줄)','첫 줄에 N, C, K, 다음 N줄에 각 물건의 크기와 가격이 주어집니다.',
        '1 ≤ N ≤ 30\n1 ≤ C ≤ 100\n0 ≤ K ≤ min(N,10)\n1 ≤ 크기, 가격 ≤ 50', '최대 가격 합을 출력합니다. 불가능하면 -1입니다.',
        '0/1 배낭 / 개수 상태','고른 개수와 사용 가능한 용량을 함께 상태로 저장하세요. 불가능한 상태는 -1로 구분하고, 개수와 용량을 큰 쪽부터 갱신합니다.',
        'n,c,k=map(int,input().split())\nd=[[-1]*(c+1) for _ in range(k+1)]\nd[0]=[0]*(c+1)\nfor _ in range(n):\n    w,v=map(int,input().split())\n    for count in range(k,0,-1):\n        for cap in range(c,w-1,-1):\n            if d[count-1][cap-w]>=0: d[count][cap]=max(d[count][cap],d[count-1][cap-w]+v)\nprint(d[k][c])',
        ['3 10 2\n6 10\n4 12\n5 13\n','2 5 2\n3 8\n4 9\n'],
        ['1 1 0\n50 50\n','30 100 10\n'+'10 50\n'*30]+[f'{n} {rng.randint(1,100)} {rng.randint(0,min(n,10))}\n'+''.join(nums([rng.randint(1,50),rng.randint(1,50)]) for _ in range(n)) for n in [1,3,8,15,30]*4],
        '첫 번째는 2번과 3번 물건을 담아 크기 9, 가격 25입니다.\n두 번째는 두 물건의 크기 합이 7이므로 -1입니다.')
    add('B',4,'정확한 인원의 구조대',
        'N명의 후보에게 각각 구조 능력치가 있습니다. 정확히 K명을 골라 능력치 합이 목표 B 이상인 구조대를 구성하려고 합니다.\n\n후보 한 명을 여러 번 고를 수 없고, 능력치가 같아도 후보 번호가 다르면 다른 사람입니다.\n\n조건을 만족하는 합 중 가장 작은 합을 골라 B와의 차이를 출력하세요. 정확히 K명을 골라서는 목표에 도달할 수 없다면 -1을 출력합니다.',
        'N K B\na1 a2 ... aN','첫 줄에 N, K, B, 다음 줄에 후보 능력치 N개가 주어집니다.',
        '1 ≤ N ≤ 30\n1 ≤ K ≤ min(N,10)\n1 ≤ ai ≤ 50\n1 ≤ B ≤ 1500', '목표를 넘는 양의 최솟값을 출력합니다. 정확히 목표면 0, 불가능하면 -1입니다.',
        '부분집합 / 개수별 도달 합','선택한 인원수별로 만들 수 있는 합을 저장하세요. 후보를 처리할 때 인원수를 큰 쪽부터 갱신해야 한 후보가 중복 사용되지 않습니다.',
        'n,k,b=map(int,input().split())\na=list(map(int,input().split()))\nd=[set() for _ in range(k+1)]\nd[0].add(0)\nfor x in a:\n    for count in range(k,0,-1): d[count].update(s+x for s in d[count-1])\npossible=[s-b for s in d[k] if s>=b]\nprint(min(possible) if possible else -1)',
        ['4 2 10\n3 5 6 8\n','3 1 20\n5 6 7\n'],
        ['30 10 500\n'+nums([50]*30),'2 2 100\n1 1\n']+[f'{n} {rng.randint(1,min(n,10))} {rng.randint(1,1500)}\n'+nums(rng.randint(1,50) for _ in range(n)) for n in [1,3,8,15,30]*4],
        '첫 번째는 3+8 또는 5+6으로 합 11을 만들어 차이 1입니다.\n두 번째는 한 명만 골라야 하므로 20에 도달할 수 없습니다.')
    add('A',5,'비용이 다른 네 색 깃발',
        'N행 M열의 깃발을 위에서부터 W, B, R, G 순서의 네 가로 구역으로 나눕니다. 각 구역은 적어도 한 행이어야 하며, 구역 안의 모든 칸은 해당 색이어야 합니다.\n\n각 칸에는 별도의 재도색 비용이 있습니다. 목표 색과 현재 색이 같으면 비용 0, 다르면 그 칸의 재도색 비용을 냅니다. 어느 새 색으로 바꾸든 같은 칸의 비용은 같습니다.\n\n세 경계의 위치를 정해 전체 재도색 비용을 최소화하세요. 단순히 바꾸는 칸 수가 적은 배치가 최소 비용이라는 보장은 없습니다.',
        'N M\n현재 색 문자열 N줄\n재도색 비용 M개씩 N줄','첫 줄에 N과 M이 주어집니다.\n다음 N줄에 공백 없는 색 문자열, 이후 N줄에 각 칸의 비용이 주어집니다.',
        '4 ≤ N ≤ 50\n1 ≤ M ≤ 50\n색은 W, B, R, G 중 하나입니다.\n1 ≤ 각 재도색 비용 ≤ 9','조건을 만족하는 최소 재도색 비용을 출력합니다.',
        '동적 계획법 / 구간 분할','행을 각 색으로 바꾸는 비용을 구하세요. 앞에서부터 몇 행을 몇 개의 색 구역으로 완성했는지 저장하고, 마지막 구역의 시작 행을 모두 비교합니다.',
        'n,m=map(int,input().split())\ng=[input().strip() for _ in range(n)]\nc=[list(map(int,input().split())) for _ in range(n)]\np=[[0]*(n+1) for _ in range(4)]\nfor color,ch in enumerate("WBRG"):\n    for r in range(n): p[color][r+1]=p[color][r]+sum(c[r][j] for j in range(m) if g[r][j]!=ch)\nd=[[10**9]*(n+1) for _ in range(5)]\nd[0][0]=0\nfor count in range(1,5):\n    for end in range(count,n+1):\n        d[count][end]=min(d[count-1][start]+p[count-1][end]-p[count-1][start] for start in range(count-1,end))\nprint(d[4][n])',
        ['4 1\nW\nB\nR\nG\n9\n8\n7\n6\n','4 1\nG\nR\nB\nW\n1\n2\n3\n4\n'],
        [f'{n} {m}\n'+''.join(''.join(rng.choice('WBRG') for _ in range(m))+'\n' for _ in range(n))+''.join(nums(rng.randint(1,9) for _ in range(m)) for _ in range(n)) for n,m in [(4,1),(5,3),(8,8),(20,20),(50,50)]*5],
        '첫 번째는 이미 네 구역의 색 순서가 맞아 0입니다.\n두 번째는 네 칸을 모두 칠해야 하므로 1+2+3+4=10입니다.')
    add('B',5,'원형 선반의 안전 장치',
        'N개의 안전 장치가 원형으로 배치되어 있고, 각 장치를 켰을 때의 출력이 주어집니다. 서로 이웃한 두 장치를 동시에 켤 수 없습니다. 1번과 N번도 이웃입니다.\n\n한 개 이상의 장치를 선택해 출력 합을 B 이상으로 만들려고 합니다. 가능한 합 중 가장 작은 값을 골라 목표 B를 초과하는 양을 구하세요.\n\n출력은 모두 양수이며 장치를 중복으로 선택할 수 없습니다. 조건을 만족하는 선택이 없으면 -1을 출력합니다.',
        'N B\na1 a2 ... aN','첫 줄에 장치 수 N과 목표 B, 다음 줄에 원을 따라 순서대로 출력 N개가 주어집니다.',
        '3 ≤ N ≤ 36\n1 ≤ ai ≤ 1000\n1 ≤ B ≤ 36000','B 이상인 최소 출력 합에서 B를 뺀 값을 출력합니다. 불가능하면 -1입니다.',
        '동적 계획법 / 원형 인접 제약','첫 장치를 선택하지 않는 경우와 선택하는 경우를 나누세요. 선택하면 두 번째와 마지막 장치는 제외합니다. 선형 구간에서는 직전 장치의 선택 여부별로 가능한 합을 저장할 수 있습니다.',
        'n,b=map(int,input().split())\na=list(map(int,input().split()))\ndef reachable(values):\n    skip,take=1,0\n    for x in values: skip,take=skip|take,skip<<x\n    return skip|take\nbits=reachable(a[1:]) | (reachable(a[2:-1])<<a[0])\nv=bits>>b\nprint((v&-v).bit_length()-1 if v else -1)',
        ['4 7\n4 2 5 3\n','3 6\n5 5 5\n'],
        ['4 12\n6 1 1 6\n','36 36000\n'+nums([1000]*36),'36 18000\n'+nums([1000]*36)]+[f'{n} {rng.randint(1,n*1000)}\n'+nums(rng.randint(1,1000) for _ in range(n)) for n in [3,4,8,16,24,36]*4],
        '첫 번째는 1번과 3번을 선택한 합 9가 최소이므로 차이 2입니다.\n두 번째는 원의 세 장치가 서로 이웃하므로 하나만 선택할 수 있어 -1입니다.')
    return sorted(bank,key=lambda p:(p['set'],p['level']))
