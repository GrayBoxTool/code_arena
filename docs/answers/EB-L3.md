# EB-L3 · 모범 풀이

```python
def solve_case():
    n,k=map(int,input().split())
    a=list(map(int,input().split()));s=sum(a[:k]);best=s
    for i in range(k,n):
     s+=a[i]-a[i-k];best=max(best,s)
    print(best)
T = int(input())
for tc in range(1, T + 1):
    print(f'#{tc} ', end='')
    solve_case()
```
