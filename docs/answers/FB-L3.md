# FB-L3 · 모범 풀이

```python
def solve_case():
    n,q=map(int,input().split())
    d=[0]*(n+2)
    for _ in range(q):
        l,r,v=map(int,input().split()); d[l]+=v; d[r+1]-=v
    a=[]; score=0
    for i in range(1,n+1):
        score+=d[i]; a.append(score)
    best=max(a)
    print(best,a.count(best))
T = int(input())
for tc in range(1, T + 1):
    print(f'#{tc} ', end='')
    solve_case()
```
