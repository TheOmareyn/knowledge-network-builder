"""
Main entry point for the Knowledge Network Builder application
Run with: python run.py
"""

import logging
import sys
from app import create_app

# Configure logging with UTF-8 encoding to handle Turkish and other Unicode characters
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('app.log', encoding='utf-8'),
        logging.StreamHandler(stream=sys.stdout)
    ]
)

# Force UTF-8 encoding for stdout/stderr on Windows
if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except AttributeError:
        # Python < 3.7 fallback
        import codecs
        sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
        sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')

logger = logging.getLogger(__name__)

# Create the app
app = create_app()

if __name__ == '__main__':
    logger.info('=== Starting Knowledge Network Builder Application ===')
    app.run(debug=True)
