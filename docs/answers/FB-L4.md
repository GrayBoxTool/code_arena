# FB-L4 · 모범 풀이

```python
def solve_case():
    import heapq
    n, m = map(int, input().split())
    g = [[] for _ in range(n + 1)]
    for _ in range(m):
        u, v, w = map(int, input().split())
        g[u].append((v, w))
        g[v].append((u, w))
    d = [10 ** 9] * (n + 1)
    d[1] = 0
    q = [(0, 1)]
    while q:
        cost, u = heapq.heappop(q)
        if cost != d[u]:
            continue
        for v, w in g[u]:
            candidate = max(cost, w)
            if candidate < d[v]:
                d[v] = candidate
                heapq.heappush(q, (candidate, v))
    print(*d[2:])
T = int(input())
for tc in range(1, T + 1):
    print(f'#{tc} ', end='')
    solve_case()
```
