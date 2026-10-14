# EB-L2 · 모범 풀이

```python
def solve_case():
    n=int(input())
    print(len(set(map(int,input().split()))))
T = int(input())
for tc in range(1, T + 1):
    print(f'#{tc} ', end='')
    solve_case()
```
