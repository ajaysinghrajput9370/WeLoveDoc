import os
import pandas as pd
import fitz  # PyMuPDF

HEADER_PHRASES = [
    "EMPLOYEE'S PROVIDENT FUND ORGANISATION",
    "Employees' State Insurance Corporation",
]

def _ensure_dir(path: str):
    os.makedirs(path, exist_ok=True)

def _unique_path(base_dir: str, base_name: str, ext: str) -> str:
    n = 1
    while True:
        p = os.path.join(base_dir, f"{base_name}{n}.{ext}")
        if not os.path.exists(p):
            return p
        n += 1

def process_files(pdf_path, excel_path, mode, output_dir=None):
    if output_dir is None:
        output_dir = os.path.dirname(pdf_path) or os.getcwd()
    _ensure_dir(output_dir)

    df = pd.read_excel(excel_path)
    if df.shape[1] == 0:
        return None, None
    ids_list = df.iloc[:, 0].dropna().astype(str).str.strip().tolist()
    ids_set = set(ids_list)

    doc = fitz.open(pdf_path)
    newdoc = fitz.open()
    found_ids = set()

    for pno, page in enumerate(doc):
        page_marked = False
        words = page.get_text("words")

        for phrase in HEADER_PHRASES:
            rects = page.search_for(phrase, quads=False)
            for rect in rects:
                page.add_highlight_annot(rect)
                page_marked = True

        if mode.lower() == "uan":
            for w in words:
                text = w[4].strip()
                if text in ids_set:
                    found_ids.add(text)
                    rect = fitz.Rect(w[:4])
                    page.add_highlight_annot(rect)
                    page_marked = True

        elif mode.lower() == "esic":
            for w in words:
                text = w[4].strip()
                if text in ids_set:
                    found_ids.add(text)
                    y0, y1 = w[1], w[3]
                    row_words = [rw for rw in words if abs(rw[1] - y0) < 1 and abs(rw[3] - y1) < 1]
                    if row_words:
                        min_x = min(rw[0] for rw in row_words)
                        max_x = max(rw[2] for rw in row_words)
                        rect = fitz.Rect(min_x, y0, max_x, y1)
                        page.add_highlight_annot(rect)
                    page_marked = True

        if page_marked:
            newdoc.insert_pdf(doc, from_page=pno, to_page=pno)

    base = "uan_highlight" if mode.lower() == "uan" else "esic_highlight"
    out_pdf = _unique_path(output_dir, base, "pdf")
    if newdoc.page_count == 0:
        newdoc.new_page().insert_text((72, 72), "No matches found.")
    newdoc.save(out_pdf)

    unmatched = [v for v in ids_list if v not in found_ids]
    not_found_path = os.path.join(output_dir, "Data_Not_Found.xlsx")
    if unmatched:
        pd.DataFrame(unmatched, columns=["Not Found"]).to_excel(not_found_path, index=False)
    elif os.path.exists(not_found_path):
        os.remove(not_found_path)

    doc.close()
    newdoc.close()

    return out_pdf, not_found_path
