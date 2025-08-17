import os
import pandas as pd
import fitz  # PyMuPDF
import time

def process_files(pdf_path, excel_path, highlight_type="uan", results_folder="results"):
    """
    pdf_path: Uploaded PDF file path
    excel_path: Uploaded Excel file path
    highlight_type: "uan" or "esic"
    results_folder: Folder to save results

    Returns:
        list -> [highlighted_pdf, not_found_excel] if some values are missing
        list -> [highlighted_pdf] if all values are found
    """

    # Ensure results folder exists
    os.makedirs(results_folder, exist_ok=True)

    # Timestamp to avoid overwriting files
    ts = int(time.time())
    highlighted_pdf = os.path.join(results_folder, f"highlighted_{ts}.pdf")
    not_found_excel = os.path.join(results_folder, f"not_found_{ts}.xlsx")

    # Read Excel values (first column)
    df = pd.read_excel(excel_path)
    search_values = df.iloc[:, 0].astype(str).tolist()

    # Open PDF
    doc = fitz.open(pdf_path)

    found_values = set()
    not_found_values = set(search_values)

    for page in doc:
        text = page.get_text("text")
        for val in search_values:
            val = str(val)
            if val in text:
                found_values.add(val)
                if val in not_found_values:
                    not_found_values.remove(val)

                # Highlight occurrences
                areas = page.search_for(val)
                for area in areas:
                    highlight = page.add_highlight_annot(area)
                    highlight.update()

    # Save highlighted PDF
    doc.save(highlighted_pdf, garbage=4, deflate=True)
    doc.close()

    # Save Not Found Excel if any
    if not_found_values:
        pd.DataFrame(list(not_found_values), columns=["Not Found"]).to_excel(not_found_excel, index=False)
        return [highlighted_pdf, not_found_excel]
    else:
        return [highlighted_pdf]
