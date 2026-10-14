# EA-L3 · 모범 풀이

```python
def solve_case():
    n,q=map(int,input().split())
    a=list(map(int,input().split()));p=[0]
    for v in a:p.append(p[-1]+v)
    ans=[]
    for _ in range(q):
     l,r=map(int,input().split());ans.append(p[r]-p[l-1])
    print(*ans)
T = int(input())
for tc in range(1, T + 1):
    print(f'#{tc} ', end='')
    solve_case()
```
