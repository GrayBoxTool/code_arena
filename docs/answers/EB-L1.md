# EB-L1 · 모범 풀이

```python
def solve_case():
    n,k=map(int,input().split())
    a=list(map(int,input().split()))
    print(sum(v>=k for v in a))
T = int(input())
for tc in range(1, T + 1):
    print(f'#{tc} ', end='')
    solve_case()
```
