# FA-L1 · 모범 풀이

```python
def solve_case():
    n, k = map(int, input().split())
    a = list(map(int, input().split()))
    s = sum(a[:k])
    ans = s
    for i in range(k, n):
        s += a[i] - a[i - k]
        ans = min(ans, s)
    print(ans)
T = int(input())
for tc in range(1, T + 1):
    print(f'#{tc} ', end='')
    solve_case()
```
