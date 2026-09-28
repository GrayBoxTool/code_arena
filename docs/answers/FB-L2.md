# FB-L2 · 모범 풀이

```python
def solve_case():
    n,l,r,target=input().split()
    n,l,r=int(n),int(l),int(r)
    start=1
    ans=0
    for _ in range(n):
        c,k=input().split(); k=int(k)
        end=start+k-1
        if c==target: ans+=max(0,min(r,end)-max(l,start)+1)
        start=end+1
    print(ans)
T = int(input())
for tc in range(1, T + 1):
    print(f'#{tc} ', end='')
    solve_case()
```
