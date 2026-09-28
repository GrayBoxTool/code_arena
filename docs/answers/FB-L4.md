# FB-L4 · 모범 풀이

```python
def solve_case():
    n,k,b=map(int,input().split())
    a=list(map(int,input().split()))
    d=[set() for _ in range(k+1)]
    d[0].add(0)
    for x in a:
        for count in range(k,0,-1): d[count].update(s+x for s in d[count-1])
    possible=[s-b for s in d[k] if s>=b]
    print(min(possible) if possible else -1)
T = int(input())
for tc in range(1, T + 1):
    print(f'#{tc} ', end='')
    solve_case()
```
