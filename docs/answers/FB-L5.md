# FB-L5 · 모범 풀이

```python
def solve_case():
    n, k = map(int, input().split())
    a = list(map(int, input().split()))
    total = sum(a)
    answers = []

    def dfs(i, count, load):
        if count == k:
            answers.append(abs(total - 2 * load))
            return
        if i >= n or count + n - i < k:
            return
        dfs(i + 1, count, load)
        dfs(i + 1, count + 1, load + a[i])
    dfs(0, 0, 0)
    print(min(answers))
T = int(input())
for tc in range(1, T + 1):
    print(f'#{tc} ', end='')
    solve_case()
```
