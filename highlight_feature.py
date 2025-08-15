import os
import io
import uuid
import pandas as pd
import pdfplumber
from PyPDF2 import PdfReader, PdfWriter
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

# Register a font for drawing text if needed (optional)
try:
    pdfmetrics.registerFont(TTFont('SegoeUI', 'seguiemj.ttf'))
except Exception:
    pass

HIGHLIGHT_COLOR = (1, 1, 0)  # Yellow (R,G,B) in 0..1


def _read_ids_from_excel(excel_path: str) -> set[str]:
    df = pd.read_excel(excel_path, header=None)
    col0 = df.iloc[:, 0].astype(str).str.strip()
    ids = set(x for x in col0 if x and x.lower() != 'nan')
    return ids


def _make_overlay(page_width, page_height, rects):
    """rects = list of (x0, y0, x1, y1) in PDF points"""
    packet = io.BytesIO()
    c = canvas.Canvas(packet, pagesize=(page_width, page_height))
    c.setFillColorRGB(*HIGHLIGHT_COLOR, alpha=0.35)
    for (x0, y0, x1, y1) in rects:
        c.rect(x0, y0, x1 - x0, y1 - y0, stroke=0, fill=1)
    c.save()
    packet.seek(0)
    return packet


def process_files(pdf_path: str, excel_path: str, highlight_type: str, result_dir: str) -> tuple[str, str|None]:
    """
    Returns: (output_pdf_path, unmatched_excel_path or None)
    Keeps only pages with at least one highlight.
    """
    ids = _read_ids_from_excel(excel_path)
    found_ids = set()

    reader = PdfReader(open(pdf_path, 'rb'))
    writer = PdfWriter()

    with pdfplumber.open(pdf_path) as pdf:
        for p_idx, page in enumerate(pdf.pages):
            words = page.extract_words(use_text_flow=True, keep_blank_chars=False)
            page_width = float(page.width)
            page_height = float(page.height)

            rects = []
            page_matched = False

            # Build quick lookup of words to their bboxes
            for w in words:
                text = (w.get('text') or '').strip()
                if not text:
            
