# EA-L5 · 모범 풀이

```python
def solve_case():
    n=int(input());a=[list(map(int,input().split())) for _ in range(n)];d=[[10**12]*n for _ in range(n)]
    for r in range(n):
     for c in range(n):
      if r==c==0:d[r][c]=a[r][c]
      else:d[r][c]=min(d[r-1][c] if r else 10**12,d[r][c-1] if c else 10**12)+a[r][c]
    print(d[-1][-1])
T = int(input())
for tc in range(1, T + 1):
    print(f'#{tc} ', end='')
    solve_case()
```
