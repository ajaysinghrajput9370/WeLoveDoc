import fitz
import pandas as pd
import os

def process_files(pdf_path, excel_path, result_folder):
    df = pd.read_excel(excel_path)
    pdf_doc = fitz.open(pdf_path)
    not_found_data = []

    for index, row in df.iterrows():
        found = False
        for page in pdf_doc:
            instances = page.search_for(str(row[0]))  # UAN/ESIC in first column
            if instances:
                found = True
                for inst in instances:
                    page.add_highlight_annot(inst)
        if not found:
            not_found_data.append(row)

    output_pdf = os.path.join(result_folder, f"highlighted_{os.path.basename(pdf_path)}")
    pdf_doc.save(output_pdf, garbage=4, deflate=True)
    pdf_doc.close()

    if not_found_data:
        not_found_df = pd.DataFrame(not_found_data)
        not_found_excel = os.path.join(result_folder, "Data_Not_Found.xlsx")
        not_found_df.to_excel(not_found_excel, index=False)
    else:
        not_found_excel = None

    return os.path.basename(output_pdf), os.path.basename(not_found_excel) if not_found_excel else None
