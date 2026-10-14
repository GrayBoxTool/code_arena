# EB-L5 · 모범 풀이

```python
def solve_case():
    n,k=map(int,input().split());d=[0]*(k+1)
    for _ in range(n):
     w,v=map(int,input().split())
     for j in range(k,w-1,-1):d[j]=max(d[j],d[j-w]+v)
    print(d[k])
T = int(input())
for tc in range(1, T + 1):
    print(f'#{tc} ', end='')
    solve_case()
```
