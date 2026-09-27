# FB-L2 · 모범 풀이

```python
def solve_case():
    s, e = map(int, input().split())
    d = [-1] * 101
    d[s] = 0
    q = [s]
    head = 0
    while head < len(q):
        x = q[head]
        head += 1
        if x == e:
            break
        for y in (x - 1, x + 1, x * 2):
            if 0 <= y <= 100 and d[y] == -1:
                d[y] = d[x] + 1
                q.append(y)
    print(d[e])
T = int(input())
for tc in range(1, T + 1):
    print(f'#{tc} ', end='')
    solve_case()
```
