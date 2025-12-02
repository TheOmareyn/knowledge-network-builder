"""PDF text extraction service"""

import logging
from PyPDF2 import PdfReader

logger = logging.getLogger(__name__)


def extract_text_from_pdf(pdf_path):
    """
    Extract text from PDF file page by page using PyPDF2.
    Returns a list of page texts (index 0 == page 1).
    """
    logger.debug(f'Entering extract_text_from_pdf with path: {pdf_path}')

    try:
        pages = []
        reader = PdfReader(pdf_path)
        num_pages = len(reader.pages)

        for page_num, page in enumerate(reader.pages):
            logger.debug(f'Extracting text from page {page_num + 1}/{num_pages}')
            try:
                text = page.extract_text() or ""
            except Exception as e:
                logger.warning(f'Failed to extract text from page {page_num + 1}: {e}')
                text = ""

            # Normalize whitespace
            text = '\n'.join([ln.rstrip() for ln in text.splitlines()])
            pages.append(text)

        logger.info(f'Successfully extracted {len(pages)} pages from {pdf_path}')
        logger.debug('Exiting extract_text_from_pdf')
        return pages

    except Exception as e:
        logger.error(f'Error extracting text from PDF {pdf_path}: {str(e)}', exc_info=True)
        return []
