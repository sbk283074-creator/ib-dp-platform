import sys, os
import pypdfium2 as pdfium

def render(pdf, pages, outdir='/tmp/render', scale=1.4):
    os.makedirs(outdir, exist_ok=True)
    doc = pdfium.PdfDocument(pdf)
    n = len(doc)
    for p in pages:
        idx = p - 1
        if idx < 0 or idx >= n:
            print('skip (out of range) p=%d n=%d' % (p, n)); continue
        page = doc[idx]
        bmp = page.render(scale=scale)
        img = bmp.to_pil()
        out = os.path.join(outdir, 'p%d.png' % p)
        img.save(out)
        print('wrote', out, img.size)

if __name__ == '__main__':
    pdf = sys.argv[1]
    pages = [int(x) for x in sys.argv[2:]]
    render(pdf, pages)
