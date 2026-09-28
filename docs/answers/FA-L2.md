# FA-L2 · 모범 풀이

```python
def solve_case():
    k=int(input())
    s=input().strip()
    st=[]
    for c in s:
        if st and st[-1][0]==c: st[-1][1]+=1
        else: st.append([c,1])
        if st[-1][1]==k: st.pop()
    print(sum(v for c,v in st))
T = int(input())
for tc in range(1, T + 1):
    print(f'#{tc} ', end='')
    solve_case()
```
