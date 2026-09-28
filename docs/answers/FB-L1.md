# FB-L1 · 모범 풀이

```python
def solve_case():
    n,k=map(int,input().split())
    a=list(map(int,input().split()))
    print(sum(a)-sum(sorted((v//2 for v in a),reverse=True)[:k]))
T = int(input())
for tc in range(1, T + 1):
    print(f'#{tc} ', end='')
    solve_case()
```
