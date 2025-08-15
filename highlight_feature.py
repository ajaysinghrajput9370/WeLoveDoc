import fitz  # PyMuPDF
import pandas as pd
from typing import List, Tuple

def load_ids_from_excel(excel_path: str) -> List[str]:
    # Read first column (no header assumed)
    df = pd.read_excel(excel_path, header=None)
    ids = df.iloc[:, 0].astype(str).str.strip().tolist()
    ids = [x for x in ids if x and x.lower() != 'nan']
    return ids

def find_line_bbox(page, inst):
    # inst is a rect-like (x0,y0,x1,y1)
    x0, y0, x1, y1 = inst
    blocks = page.get_text("blocks")
    line_candidates = []
    for b in blocks:
        bx0, by0, bx1, by1 = b[0], b[1], b[2], b[3]
        # if vertical overlap then consider it part of the same line
        if by0 <= y0 <= by1 or by0 <= y1 <= by1 or (y0 <= by0 and y1 >= by1):
            line_candidates.append((bx0, by0, bx1, by1))
    if line_candidates:
        by0 = min(b[1] for b in line_candidates)
        by1 = max(b[3] for b in line_candidates)
        # extend across page width with small padding
        return (10, by0 - 1, page.rect.width - 10, by1 + 1)
    # fallback
    return (10, y0 - 1, page.rect.width - 10, y1 + 1)

def highlight_pdf_by_ids(pdf_path: str, ids: List[str], out_path: str) -> Tuple[int, int]:
    doc = fitz.open(pdf_path)
    matched_pages = set()
    total_marks = 0
    # Normalize keys to strings
    keys = [str(k).strip() for k in ids if k]
    for pno in range(len(doc)):
        page = doc[pno]
        for key in keys:
            try:
                areas = page.search_for(key, quads=False)
            except Exception:
                areas = []
            for rect in areas:
                full_row = find_line_bbox(page, rect)
                # page.add_highlight_annot expects a rect object; convert
                r = fitz.Rect(full_row)
                page.add_highlight_annot(r)
                matched_pages.add(pno)
                total_marks += 1
    # Save only matched pages into new document
    if matched_pages:
        new_doc = fitz.open()
        for pno in sorted(matched_pages):
            new_doc.insert_pdf(doc, from_page=pno, to_page=pno)
        new_doc.save(out_path)
        new_doc.close()
    else:
        # no matches: save original (or save empty) — here we save original copy
        doc.save(out_path)
    doc.close()
    return len(matched_pages), total_marks

def save_unmatched_to_excel(ids: List[str], matched_pdf_pages_count: int, excel_path: str, out_excel: str):
    import pandas as pd
    if matched_pdf_pages_count == 0:
        df = pd.DataFrame({"Unmatched_IDs": ids})
    else:
        df = pd.DataFrame({"Unmatched_IDs": []})
    df.to_excel(out_excel, index=False)
