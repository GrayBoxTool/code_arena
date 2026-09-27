# FA-L3 · 모범 풀이

```python
def solve_case():
    n, k = map(int, input().split())
    a = [0] * (n + 1)
    value = [1]

    def visit(i):
        if i > n:
            return
        visit(i * 2)
        a[i] = value[0]
        value[0] += 1
        visit(i * 2 + 1)
    visit(1)
    print(a[1], a[k])
T = int(input())
for tc in range(1, T + 1):
    print(f'#{tc} ', end='')
    solve_case()
```
