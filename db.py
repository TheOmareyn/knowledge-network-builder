"""
Database helper functions for Knowledge Network Builder
Handles SQLite connection and initialization.
"""

import sqlite3
import logging

logger = logging.getLogger(__name__)

DATABASE = 'knowledge_network.db'

def get_db_connection():
    """Create and return a database connection with row factory."""
    logger.debug(f'Opening database connection to {DATABASE}')
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Initialize the database using schema.sql."""
    logger.info('Entering init_db')
    
    try:
        conn = get_db_connection()
        
        with open('schema.sql', 'r') as f:
            schema = f.read()
            logger.debug('Loaded schema.sql')
            conn.executescript(schema)

        # Ensure new columns are present on older databases: add page_number if missing
        try:
            cur = conn.execute("PRAGMA table_info('KnowledgeEntry')")
            cols = [row[1] for row in cur.fetchall()]
            if 'page_number' not in cols:
                logger.info('Adding missing column page_number to KnowledgeEntry')
                conn.execute('ALTER TABLE KnowledgeEntry ADD COLUMN page_number INTEGER')
        except Exception as e:
            logger.warning(f'Could not ensure page_number column exists: {e}')

        conn.commit()
        conn.close()
        logger.info('Database initialized successfully')
    
    except FileNotFoundError:
        logger.error('schema.sql file not found')
        raise
    
    except Exception as e:
        logger.error(f'Error initializing database: {str(e)}', exc_info=True)
        raise
    
    finally:
        logger.debug('Exiting init_db')