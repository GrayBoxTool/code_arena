# EA-L1 · 모범 풀이

```python
def solve_case():
    n=int(input())
    s=0
    for _ in range(n):
     c,w=map(int,input().split());s+=c*w
    print(s)
T = int(input())
for tc in range(1, T + 1):
    print(f'#{tc} ', end='')
    solve_case()
```
