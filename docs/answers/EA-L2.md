# EA-L2 · 모범 풀이

```python
def solve_case():
    s=input().strip()
    best=run=1
    for i in range(1,len(s)):
     run=run+1 if s[i]==s[i-1] else 1
     best=max(best,run)
    print(best)
T = int(input())
for tc in range(1, T + 1):
    print(f'#{tc} ', end='')
    solve_case()
```
