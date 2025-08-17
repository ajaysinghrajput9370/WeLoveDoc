import os
import pandas as pd
from PyPDF2 import PdfReader, PdfWriter


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

    # Output file names
    highlighted_pdf = os.path.join(results_folder, "highlighted_output.pdf")
    not_found_excel = os.path.join(results_folder, "not_found.xlsx")

    # Read Excel values
    df = pd.read_excel(excel_path)
    search_values = df.iloc[:, 0].astype(str).tolist()

    reader = PdfReader(pdf_path)
    writer = PdfWriter()

    found_values = set()
    not_found_values = set(search_values)  # Start with all as not found

    for page in reader.pages:
        text = page.extract_text()
        if not text:
            writer.add_page(page)
            continue

        for val in search_values:
            if val in text:
                found_values.add(val)
                if val in not_found_values:
                    not_found_values.remove(val)

        writer.add_page(page)

    # Save highlighted PDF (actually just a copy, no highlights yet)
    with open(highlighted_pdf, "wb") as f:
        writer.write(f)

    # Save Not Found Excel if needed
    if not_found_values:
        pd.DataFrame(list(not_found_values), columns=["Not Found"]).to_excel(not_found_excel, index=False)
        return [highlighted_pdf, not_found_excel]
    else:
        return [highlighted_pdf]
