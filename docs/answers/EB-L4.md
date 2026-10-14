# EB-L4 · 모범 풀이

```python
def solve_case():
    n=int(input());a=[input().strip() for _ in range(n)];d=[[-1]*n for _ in range(n)];d[0][0]=0;q=[(0,0)]
    for r,c in q:
     for dr,dc in [(1,0),(-1,0),(0,1),(0,-1)]:
      nr,nc=r+dr,c+dc
      if 0<=nr<n and 0<=nc<n and a[nr][nc]=='0' and d[nr][nc]<0:
       d[nr][nc]=d[r][c]+1;q.append((nr,nc))
    print(d[-1][-1])
T = int(input())
for tc in range(1, T + 1):
    print(f'#{tc} ', end='')
    solve_case()
```
