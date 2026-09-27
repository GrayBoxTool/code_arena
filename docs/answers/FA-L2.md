# FA-L2 · 모범 풀이

```python
def solve_case():
    n = int(input())
    g = [input().strip() for _ in range(n)]
    q = [(0, 0, 0)]
    seen = {(0, 0)}
    head = 0
    answer = -1
    while head < len(q):
        r, c, d = q[head]
        head += 1
        if (r, c) == (n - 1, n - 1):
            answer = d
            break
        for dr, dc in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nr, nc = (r + dr, c + dc)
            if 0 <= nr < n and 0 <= nc < n and (g[nr][nc] == '0') and ((nr, nc) not in seen):
                seen.add((nr, nc))
                q.append((nr, nc, d + 1))
    print(answer)
T = int(input())
for tc in range(1, T + 1):
    print(f'#{tc} ', end='')
    solve_case()
```
