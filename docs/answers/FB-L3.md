# FB-L3 · 모범 풀이

```python
def solve_case():
    n, k = map(int, input().split())
    a = [0] + list(map(int, input().split()))
    for i in range(n, 1, -1):
        a[i // 2] += a[i]
    print(a[1], a[k])
T = int(input())
for tc in range(1, T + 1):
    print(f'#{tc} ', end='')
    solve_case()
```
