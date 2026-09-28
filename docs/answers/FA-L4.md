# FA-L4 · 모범 풀이

```python
def solve_case():
    n,c,k=map(int,input().split())
    d=[[-1]*(c+1) for _ in range(k+1)]
    d[0]=[0]*(c+1)
    for _ in range(n):
        w,v=map(int,input().split())
        for count in range(k,0,-1):
            for cap in range(c,w-1,-1):
                if d[count-1][cap-w]>=0: d[count][cap]=max(d[count][cap],d[count-1][cap-w]+v)
    print(d[k][c])
T = int(input())
for tc in range(1, T + 1):
    print(f'#{tc} ', end='')
    solve_case()
```
