import fitz  # PyMuPDF
import pytesseract
from PIL import Image
import io
import os
import logging

logger = logging.getLogger(__name__)

def extract_text_pymupdf(path: str) -> str:
    """Extract text from a PDF with an embedded text layer using PyMuPDF."""
    text_content = []
    try:
        doc = fitz.open(path)
        for page_num in range(len(doc)):
            page = doc.load_page(page_num)
            text = page.get_text()
            text_content.append(f"--- [PAGE {page_num + 1}] ---\n{text}")
        return "\n".join(text_content)
    except Exception as e:
        logger.error(f"Error in extract_text_pymupdf: {e}")
        return ""

def extract_text_tesseract(path: str) -> str:
    """Extract text from a scanned PDF using Tesseract OCR."""
    text_content = []
    try:
        doc = fitz.open(path)
        for page_num in range(len(doc)):
            page = doc.load_page(page_num)
            # Render page to an image
            pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))  # 2x zoom for better OCR
            img_data = pix.tobytes("png")
            img = Image.open(io.BytesIO(img_data))
            
            # Use Tesseract to do OCR on the image
            text = pytesseract.image_to_string(img)
            text_content.append(f"--- [PAGE {page_num + 1}] ---\n{text}")
        return "\n".join(text_content)
    except Exception as e:
        logger.error(f"Error in extract_text_tesseract: {e}")
        return ""

def needs_ocr(path: str) -> bool:
    """Determine if a PDF needs OCR by checking if the first few pages contain text."""
    try:
        doc = fitz.open(path)
        # Check first 3 pages or all if less than 3
        pages_to_check = min(3, len(doc))
        for page_num in range(pages_to_check):
            page = doc.load_page(page_num)
            text = page.get_text().strip()
            if len(text) > 50:
                # Found reasonable amount of text, probably doesn't need OCR
                return False
        return True
    except Exception as e:
        logger.error(f"Error in needs_ocr: {e}")
        return True
