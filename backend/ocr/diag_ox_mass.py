import sys, os
sys.path.insert(0, os.path.dirname(__file__))
import extract_books as E
import booklib as B
import pypdfium2
BOOK_ID='PH-OX-2023'
book=next(b for b in E.BOOKS if b['id']==BOOK_ID)
pdf=pypdfium2.PdfDocument(book['path'])
for i in [706,707,708]:  # pdf 707,708,709
    page=pdf[i]
    H=float(page.get_height()); W=float(page.get_width())
    # replicate find_gutter internals for the candidate
    tp=page.get_textpage(); n=tp.count_chars()
    bin_w=3.0; nbins=int(W/bin_w)+1
    xs=[]; ys=[]
    for k in range(n):
        try:
            b=tp.get_charbox(k); x0,y0,x1,y1=float(b[0]),float(b[1]),float(b[2]),float(b[3])
        except Exception:
            continue
        cx=(x0+x1)/2.0; cy=(y0+y1)/2.0
        xs.append(cx); ys.append(cy)
    tp.close()
    # find widest empty run in central zone
    hist=[0]*nbins
    for cx in xs:
        bi=int(cx/bin_w)
        if 0<=bi<nbins: hist[bi]+=1
    smooth=[0.0]*nbins
    for k in range(nbins):
        a=max(0,k-1); b=min(nbins,k+2); smooth[k]=sum(hist[a:b])/(b-a)
    lo=int(0.40*W/bin_w); hi=int(0.60*W/bin_w)
    FLANK=16
    best=None; cur=0; cs=lo
    for x in range(lo,hi+1):
        if smooth[x]<3.0:
            if cur==0: cs=x
            cur+=1
        else:
            if cur>=5:
                mid=cs+cur/2.0
                if best is None or cur>best[1]: best=(mid,cur)
            cur=0
    if cur>=5 and (best is None or cur>best[1]): best=(cs+cur/2.0,cur)
    if best is None:
        print(f"pdf {i+1}: no central empty run"); continue
    mid,ln=best; gx=mid*bin_w
    ls_x=max(0.0,gx-FLANK*bin_w); rs_x=min(W,gx+FLANK*bin_w)
    ly=[y for (x,y) in zip(xs,ys) if ls_x<=x<=gx]
    ry=[y for (x,y) in zip(xs,ys) if gx<=x<=rs_x]
    nb=int(H/(0.10*H))
    lset=set(int(y/(H/nb)) for y in ly); rset=set(int(y/(H/nb)) for y in ry)
    print(f"pdf {i+1}: gutter_x={gx:.1f} left_chars={len(ly)} right_chars={len(ry)} "
          f"left_occ={len(lset)/nb:.2f} right_occ={len(rset)/nb:.2f}")
