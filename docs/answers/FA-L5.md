# FA-L5 · 모범 풀이

```python
def solve_case():
    n,m=map(int,input().split())
    g=[input().strip() for _ in range(n)]
    c=[list(map(int,input().split())) for _ in range(n)]
    p=[[0]*(n+1) for _ in range(4)]
    for color,ch in enumerate("WBRG"):
        for r in range(n): p[color][r+1]=p[color][r]+sum(c[r][j] for j in range(m) if g[r][j]!=ch)
    d=[[10**9]*(n+1) for _ in range(5)]
    d[0][0]=0
    for count in range(1,5):
        for end in range(count,n+1):
            d[count][end]=min(d[count-1][start]+p[count-1][end]-p[count-1][start] for start in range(count-1,end))
    print(d[4][n])
T = int(input())
for tc in range(1, T + 1):
    print(f'#{tc} ', end='')
    solve_case()
```
