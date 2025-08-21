import fitz  # PyMuPDF
import pandas as pd
import os

def highlight_pdf(pdf_path, excel_path, highlight_type="pf", output_folder="results"):
    """
    PDF highlighter with Excel + fixed phrases.
    highlight_type: "pf" or "esic"
    """
    # Fixed phrases to always highlight
    FIXED_PHRASES = [
        "Employees' State Insurance Corporation",
        "EMPLOYEE'S PROVIDENT FUND ORGANISATION"
    ]

    # Load Excel values
    df = pd.read_excel(excel_path, header=None)
    excel_values = df[0].astype(str).tolist()

    # Prepare output folder
    if os.path.exists(output_folder):
        for f in os.listdir(output_folder):
            os.remove(os.path.join(output_folder, f))
    else:
        os.makedirs(output_folder)

    pdf_doc = fitz.open(pdf_path)
    matched_pages = []

    # Keep track of values that are matched somewhere
    matched_values = set()

    for page_num in range(len(pdf_doc)):
        page = pdf_doc[page_num]
        page_matched = False

        # Get words on page
        words = page.get_text("words")  # x0,y0,x1,y1,text,block,line,word

        # --- Highlight Excel values ---
        for val in excel_values:
            val_lower = val.lower()
            matched_words = [w for w in words if val_lower in w[4].lower()]

            if matched_words:
                page_matched = True
                matched_values.add(val)  # mark as found
                for w in matched_words:
                    x0, y0, x1, y1, text, _, _, _ = w
                    if highlight_type.lower() == "pf":
                        rect = fitz.Rect(x0, y0, x1, y1)
                        page.add_highlight_annot(rect)
                    elif highlight_type.lower() == "esic":
                        # Full row highlight
                        row_words = [rw for rw in words if abs(rw[1]-y0) < 2 or abs(rw[3]-y1) < 2]
                        rect = fitz.Rect(min(rw[0] for rw in row_words),
                                         min(rw[1] for rw in row_words),
                                         max(rw[2] for rw in row_words),
                                         max(rw[3] for rw in row_words))
                        page.add_highlight_annot(rect)

        # --- Highlight fixed phrases ---
        for phrase in FIXED_PHRASES:
            for rect in page.search_for(phrase):
                page.add_highlight_annot(rect)
                page_matched = True

        if page_matched:
            matched_pages.append(page_num)

    # Save new PDF with only matched pages
    if matched_pages:
        new_pdf = fitz.open()
        for num in matched_pages:
            new_pdf.insert_pdf(pdf_doc, from_page=num, to_page=num)
        output_pdf_path = os.path.join(output_folder, "highlighted_output.pdf")
        new_pdf.save(output_pdf_path)
    else:
        output_pdf_path = None

    # Save Not Found Excel (only those never matched in any page)
    not_found = [val for val in excel_values if val not in matched_values]
    if not_found:
        not_found_df = pd.DataFrame(not_found)
        not_found_path = os.path.join(output_folder, "Data_Not_Found.xlsx")
        not_found_df.to_excel(not_found_path, index=False, header=False)
    else:
        not_found_path = None

    return output_pdf_path, not_found_path
