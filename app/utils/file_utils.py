"""File handling utilities"""

import logging
from flask import current_app
from PyPDF2 import PdfReader

logger = logging.getLogger(__name__)


def allowed_file(filename):
    """Check if the uploaded file has an allowed extension."""
    logger.debug(f'Checking if filename is allowed: {filename}')
    result = '.' in filename and filename.rsplit('.', 1)[1].lower() in current_app.config['ALLOWED_EXTENSIONS']
    logger.debug(f'File {filename} allowed: {result}')
    return result


def get_pdf_page_count(pdf_path):
    """Get the number of pages in a PDF file."""
    try:
        reader = PdfReader(pdf_path)
        return len(reader.pages)
    except Exception as e:
        logger.error(f'Error getting page count from {pdf_path}: {str(e)}')
        return None
