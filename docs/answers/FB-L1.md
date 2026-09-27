# FB-L1 · 모범 풀이

```python
def solve_case():
    n = int(input())
    a = list(map(int, input().split()))
    run = best = 1
    for i in range(1, n):
        run = run + 1 if a[i] == a[i - 1] else 1
        best = max(best, run)
    print(best)
T = int(input())
for tc in range(1, T + 1):
    print(f'#{tc} ', end='')
    solve_case()
```
