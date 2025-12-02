"""Dashboard route"""

import logging
from flask import Blueprint, render_template
from flask_login import login_required, current_user

from db import get_db_connection

logger = logging.getLogger(__name__)

bp = Blueprint('dashboard', __name__)


@bp.route('/dashboard')
@login_required
def dashboard():
    """User dashboard showing statistics and quick actions"""
    logger.debug(f'Entering dashboard route for user_id={current_user.id}')
    
    conn = get_db_connection()
    
    # Get total books count (only books with knowledge entries)
    total_books = conn.execute(
        '''SELECT COUNT(DISTINCT d.id) as count 
           FROM Document d
           JOIN KnowledgeEntry ke ON ke.document_id = d.id
           WHERE d.user_id = ?''',
        (current_user.id,)
    ).fetchone()['count']
    
    # Get total questions count
    total_questions = conn.execute(
        '''SELECT COUNT(DISTINCT ke.question) as count 
           FROM KnowledgeEntry ke
           JOIN Document d ON ke.document_id = d.id
           WHERE d.user_id = ?''',
        (current_user.id,)
    ).fetchone()['count']
    
    # Get total answers count
    total_answers = conn.execute(
        '''SELECT COUNT(*) as count 
           FROM KnowledgeEntry ke
           JOIN Document d ON ke.document_id = d.id
           WHERE d.user_id = ?''',
        (current_user.id,)
    ).fetchone()['count']
    
    # Get categories count (unique categories from documents with network data)
    categories_query = conn.execute(
        '''SELECT COUNT(DISTINCT d.category) as count 
           FROM Document d
           JOIN KnowledgeEntry ke ON ke.document_id = d.id
           WHERE d.user_id = ? AND d.category IS NOT NULL AND d.category != ""''',
        (current_user.id,)
    ).fetchone()
    categories_count = categories_query['count'] if categories_query else 0
    
    # Get top categories (only from documents with network data)
    top_categories = conn.execute(
        '''SELECT d.category as name, COUNT(DISTINCT d.id) as count 
           FROM Document d
           JOIN KnowledgeEntry ke ON ke.document_id = d.id
           WHERE d.user_id = ? AND d.category IS NOT NULL AND d.category != ""
           GROUP BY d.category
           ORDER BY count DESC
           LIMIT 5''',
        (current_user.id,)
    ).fetchall()
    
    conn.close()

    stats = {
        'total_books': total_books,
        'total_questions': total_questions,
        'total_answers': total_answers,
        'categories_count': categories_count,
        'top_categories': [dict(cat) for cat in top_categories]
    }
    
    logger.debug(f'User {current_user.id} stats: {stats}')
    logger.debug('Exiting dashboard route')
    return render_template('dashboard.html', stats=stats)
