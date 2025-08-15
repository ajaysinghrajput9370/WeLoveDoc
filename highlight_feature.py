import os
from fpdf import FPDF
import pandas as pd

def process_files(pdf_path, excel_path, output_folder, highlight_type="uan"):
    os.makedirs(output_folder, exist_ok=True)
    out_pdf = os.path.join(output_folder, "highlighted.pdf")
    out_xlsx = os.path.join(output_folder, "Data_Not_Found.xlsx")

    # Create placeholder PDF
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=12)
    pdf.cell(0, 10, txt="Placeholder Highlighted PDF", ln=True)
    pdf.cell(0, 10, txt=f"Highlight type: {highlight_type}", ln=True)
    pdf.output(out_pdf)

    # Create placeholder Excel
    try:
        df = pd.read_excel(excel_path, engine="openpyxl")
        if not df.empty:
            first_col = df.columns[0]
            df_nf = pd.DataFrame({first_col: df[first_col], "Found": False})
        else:
            df_nf = pd.DataFrame({"ID": [], "Found": []})
    except Exception:
        df_nf = pd.DataFrame({"ID": [], "Found": []})

    df_nf.to_excel(out_xlsx, index=False)

    return out_pdf, out_xlsx
