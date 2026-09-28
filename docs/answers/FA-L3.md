# FA-L3 · 모범 풀이

```python
def solve_case():
    n,m=map(int,input().split())
    f={}
    for _ in range(n):
        s=input().strip()
        for i in range(1,len(s)+1):
            p=s[:i]; f[p]=f.get(p,0)+1
    print(*(f.get(input().strip(),0) for _ in range(m)))
T = int(input())
for tc in range(1, T + 1):
    print(f'#{tc} ', end='')
    solve_case()
```
