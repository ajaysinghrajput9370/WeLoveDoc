import fitz  # PyMuPDF
import pandas as pd
import os

def process_files(pdf_path, excel_path, highlight_type="uan"):
    # Excel load
    df = pd.read_excel(excel_path)
    values = df.iloc[:, 0].astype(str).str.strip().tolist()  # first column ke values

    doc = fitz.open(pdf_path)

    # Output files
    highlighted_pdf = pdf_path.replace(".pdf", "_highlighted.pdf")
    not_found_excel = excel_path.replace(".xlsx", "_not_found.xlsx")

    not_found = []

    # Always highlight these keywords
    always_highlight = ["Employees' State Insurance Corporation", "Employee's State Insurance Corporation",
                        "Employees' Provident Fund", "Employee's Provident Fund"]

    for page in doc:
        # Always highlight ESIC & EPF mentions
        for keyword in always_highlight:
            text_instances = page.search_for(keyword)
            for inst in text_instances:
                page.add_highlight_annot(inst)

        # Search excel values
        for value in values:
            text_instances = page.search_for(value)
            if text_instances:
                if highlight_type == "uan":
                    # 🔹 UAN → sirf number ko highlight karo
                    for inst in text_instances:
                        page.add_highlight_annot(inst)

                elif highlight_type == "esic":
                    # 🔹 ESIC → puri row highlight karo
                    for inst in text_instances:
                        y0, y1 = inst.y0, inst.y1
                        rect = fitz.Rect(0, y0, page.rect.width, y1)  # full row
                        page.add_highlight_annot(rect)

            else:
                not_found.append(value)

    # Save highlighted PDF
    doc.save(highlighted_pdf)
    doc.close()

    # Save not found excel
    if not_found:
        pd.DataFrame(not_found, columns=["Not Found"]).to_excel(not_found_excel, index=False)
    else:
        not_found_excel = None  # agar sab match ho gya

    return highlighted_pdf, not_found_excel
