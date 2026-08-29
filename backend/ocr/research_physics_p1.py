#!/usr/bin/env python3
"""Session research only: Physics HL Paper 1 (no extraction, no DB writes)."""
import os, re, json
import pypdfium2 as pdfium

BASE = "/Users/lucas.ma/Downloads/dp learning/Physics-HL-Past Papers&Mark Schemes(1999.05~2025.11)"
# Scope follows FINAL_PLAN: May 2016 through November 2025. English only;
# translation duplicates excluded. 2020 May was cancelled / absent from source.
YEAR_RE = re.compile(r'^(20(?:1[6-9]|2[0-5]))')

def is_english(f):
    x=f.lower()
    return not any(k in x for k in ('french','spanish','german'))

def load(path):
    d=pdfium.PdfDocument(path)
    pages=[d[i].get_textpage().get_text_range() for i in range(len(d))]
    full='\n'.join(pages)
    # Image objects are used only as a research signal; no images are rendered.
    image_objs=[]
    for i in range(len(d)):
        for o in d[i].get_objects():
            try:
                if o.type == 3:
                    image_objs.append((i+1, o.get_px_size(), o.get_bounds()))
            except Exception:
                pass
    d.close()
    return pages,full,image_objs

def qp_header_lines(full):
    out=[]
    for ln in full.splitlines():
        s=ln.strip()
        if re.search(r'(?:Maximum mark|Maximum marks)',s,re.I) or re.match(r'^\s*Question\s+\d+',s,re.I):
            out.append(s)
    return out

def number_lines(full):
    out=[]
    for ln in full.splitlines():
        s=ln.strip()
        if re.match(r'^\s*\d+\s*[.)]',s): out.append(s)
    return out

def qnums(full):
    # Most old QPs expose one number per question at line start; 2025 may use
    # new labels, so retain both count and visible-number diagnostics.
    vals=[]
    for ln in full.splitlines():
        m=re.match(r'^\s*(\d+)\s*[.)]\s',ln)
        if m: vals.append(int(m.group(1)))
    return vals

def ascii_sample(full, n=900):
    return full[:n].replace('\r','')

def main():
    inventory=[]
    for d in sorted(os.listdir(BASE)):
        dp=os.path.join(BASE,d)
        if not os.path.isdir(dp) or not YEAR_RE.match(d): continue
        year=int(YEAR_RE.match(d).group(1))
        # All English QP files that are paper 1 (including 2025 1A/1B).
        qps=sorted(f for f in os.listdir(dp) if 'paper_1' in f.lower() and 'markscheme' not in f.lower() and is_english(f))
        for f in qps:
            ms=f[:-4]+'_markscheme.pdf'
            # Some sources may use a slight filename mismatch; this reports it.
            inventory.append({'dir':d,'year':year,'qp':f,'ms':ms,'qp_exists':os.path.exists(os.path.join(dp,f)),'ms_exists':os.path.exists(os.path.join(dp,ms))})
    print('INVENTORY_COUNT',len(inventory))
    for r in inventory: print(json.dumps(r,ensure_ascii=False))
    print('\nPROBES')
    # Representative old/pre-new, transition, modern old-guide, and new 2025.
    probes=[]
    for r in inventory:
        if r['year'] in (2016,2021,2024,2025):
            probes.append(r)
    # one per year/session/format, not every TZ in the probe table
    seen=set(); chosen=[]
    for r in probes:
        key=(r['year'], '1A' if '1A' in r['qp'] else '1B' if '1B' in r['qp'] else 'old')
        if key not in seen and r['ms_exists']:
            seen.add(key); chosen.append(r)
    for r in chosen:
        qp=os.path.join(BASE,r['dir'],r['qp']); ms=os.path.join(BASE,r['dir'],r['ms'])
        qp_pages,qp_full,qp_imgs=load(qp); ms_pages,ms_full,ms_imgs=load(ms)
        print(f"\n--- {r['dir']} / {r['qp']} ---")
        print('QP pages',len(qp_pages),'chars',len(qp_full),'PUA',len(re.findall(r'[\ue000-\uf8ff]',qp_full)),'image_objs',len(qp_imgs),'visible_qnums_sample',qnums(qp_full)[:60])
        print('MS pages',len(ms_pages),'chars',len(ms_full),'PUA',len(re.findall(r'[\ue000-\uf8ff]',ms_full)),'image_objs',len(ms_imgs),'visible_qnums_sample',qnums(ms_full)[:60])
        print('QP headers',qp_header_lines(qp_full)[:10])
        print('QP number lines',number_lines(qp_full)[:15])
        print('MS number lines',number_lines(ms_full)[:15])
        print('QP_SAMPLE',ascii_sample(qp_full))
        print('MS_SAMPLE',ascii_sample(ms_full))

if __name__=='__main__': main()
