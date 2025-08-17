import os
import pandas as pd
from PyPDF2 import PdfReader, PdfWriter


def process_files(pdf_path, excel_path, highlight_type="uan", results_folder="results"):
    """
    pdf_path: Uploaded PDF file path
    excel_path: Uploaded Excel file path
    highlight_type: "uan" or "esic"
    results_folder: Folder to save results
    """

    # Output file names
    highlighted_pdf = os.path.join(results_folder, "highlighted_output.pdf")
    not_found_excel = os.path.join(results_folder, "not_found.xlsx")

    # Excel values
    df = pd.read_excel(excel_path)
    search_values = df.iloc[:, 0].astype(str).tolist()

    reader = PdfReader(pdf_path)
    writer = PdfWriter()

    found_values = []
    not_found_values = []

    for page in reader.pages:
        text = page.extract_text()
        if not text:
            writer.add_page(page)
            continue

        for val in search_values:
            if val in text:
                found_values.append(val)
                # NOTE: Actual highlight add karne ke liye pdfplumber + fpdf2 ki zaroorat hogi
            else:
                not_found_values.append(val)

        writer.add_page(page)

    # Save highlighted PDF
    with open(highlighted_pdf, "wb") as f:
        writer.write(f)

    # Save Not Found Excel
    if not_found_values:
        pd.DataFrame(not_found_values, columns=["Not Found"]).to_excel(not_found_excel, index=False)
        return [highlighted_pdf, not_found_excel]
    else:
        return highlighted_pdf
