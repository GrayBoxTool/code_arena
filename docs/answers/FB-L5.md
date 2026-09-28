# FB-L5 · 모범 풀이

```python
def solve_case():
    n,b=map(int,input().split())
    a=list(map(int,input().split()))
    def reachable(values):
        skip,take=1,0
        for x in values: skip,take=skip|take,skip<<x
        return skip|take
    bits=reachable(a[1:]) | (reachable(a[2:-1])<<a[0])
    v=bits>>b
    print((v&-v).bit_length()-1 if v else -1)
T = int(input())
for tc in range(1, T + 1):
    print(f'#{tc} ', end='')
    solve_case()
```
