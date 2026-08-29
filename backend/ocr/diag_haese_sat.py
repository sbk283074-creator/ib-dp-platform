import sys, os
sys.path.insert(0, os.path.dirname(__file__))
import extract_books as E
import booklib as B
import pypdfium2
book=next(b for b in E.BOOKS if b['id']=='MA-HAESE-CORE1')
pdf=pypdfium2.PdfDocument(book['path'])
i=482  # printed 482
page=pdf[i]
H=float(page.get_height()); W=float(page.get_width())
scale=200/72.0
bmp=page.render(scale=scale); img=bmp.to_pil().convert('RGB')
Wp,Hp=img.width,img.height
px=img.load()
x0=0; x1=int(0.14*Wp)
# For each connected component in left strip, report its colour stats
def comps_in():
    ink=set()
    for py in range(Hp):
        for pxc in range(x0,x1):
            r,g,b=px[pxc,py]
            lum=0.299*r+0.587*g+0.114*b
            mx=max(r,g,b); mn=min(r,g,b); sat=mx-mn
            if lum<150 or sat>70: ink.add((py,pxc))
    from collections import deque
    seen=set(); out=[]
    for seed in ink:
        if seed in seen: continue
        st=deque([seed]); seen.add(seed); ys=[]; xs=[]
        while st:
            y,x=st.popleft(); ys.append(y); xs.append(x)
            for dy,dx in((-1,0),(1,0),(0,-1),(0,1)):
                nb=(y+dy,x+dx)
                if nb in ink and nb not in seen: seen.add(nb); st.append(nb)
        h=max(ys)-min(ys)+1; w=max(xs)-min(xs)+1
        if 6<=h<=60 and 4<=w<=60:
            # sample colour
            rs=gs=bs=0; n=0
            for y in range(min(ys),max(ys)+1):
                for x in range(min(xs),max(xs)+1):
                    if (y,x) in ink:
                        r,g,b=px[x,y]; rs+=r; gs+=g; bs+=b; n+=1
            if n:
                r,g,b=rs/n,gs/n,bs/n
                mx=max(r,g,b); mn=min(r,g,b); sat=mx-mn
                out.append((round((min(ys)+max(ys))/2/scale,0), round(sat,0), (int(r),int(g),int(b))))
    return out
out=comps_in()
for c in sorted(out):
    print(f"  y={c[0]} sat={c[1]} rgb={c[2]}")
