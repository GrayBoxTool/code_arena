# FA-L1 · 모범 풀이

```python
def solve_case():
    n,p,q,r,s=map(int,input().split())
    a=list(map(int,input().split()))
    print(min(sum(a)*p,sum(q+max(0,w-r)*s for w in a)))
T = int(input())
for tc in range(1, T + 1):
    print(f'#{tc} ', end='')
    solve_case()
```
