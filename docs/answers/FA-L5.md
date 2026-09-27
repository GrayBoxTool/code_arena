# FA-L5 · 모범 풀이

```python
def solve_case():
    n, k = map(int, input().split())
    a = list(map(int, input().split()))
    answers = []

    def dfs(i, count, total):
        if count == k:
            answers.append(total)
            return
        if i >= n:
            return
        dfs(i + 1, count, total)
        dfs(i + 2, count + 1, total + a[i])
    dfs(0, 0, 0)
    print(min(answers))
T = int(input())
for tc in range(1, T + 1):
    print(f'#{tc} ', end='')
    solve_case()
```
