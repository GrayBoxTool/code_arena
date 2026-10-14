# EA-L4 · 모범 풀이

```python
def solve_case():
    n,m,s=map(int,input().split());g=[[] for _ in range(n+1)]
    for _ in range(m):
     u,v=map(int,input().split());g[u].append(v);g[v].append(u)
    seen={s};q=[s]
    for u in q:
     for v in g[u]:
      if v not in seen:seen.add(v);q.append(v)
    print(len(seen))
T = int(input())
for tc in range(1, T + 1):
    print(f'#{tc} ', end='')
    solve_case()
```
