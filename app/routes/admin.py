"""Admin routes for user management"""

import logging
import json
import requests
from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify, current_app
from flask_login import login_required, current_user
from functools import wraps
from db import get_db_connection

logger = logging.getLogger(__name__)

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')


def admin_required(f):
    """Decorator to require admin access"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            flash('Please log in to access this page.', 'error')
            return redirect(url_for('auth.login'))
        if not current_user.is_admin:
            flash('Access denied. Admin privileges required.', 'error')
            return redirect(url_for('dashboard.index'))
        return f(*args, **kwargs)
    return decorated_function


@admin_bp.route('/users')
@login_required
@admin_required
def users_list():
    """Display all users with their statistics"""
    conn = get_db_connection()
    
    # Get all users with their document counts and network data counts
    users = conn.execute('''
        SELECT 
            u.id,
            u.username,
            u.is_premium,
            u.is_admin,
            u.api_calls_today,
            u.api_calls_reset_date,
            COUNT(DISTINCT d.id) as total_books,
            COUNT(DISTINCT CASE WHEN ke.id IS NOT NULL THEN d.id END) as books_with_data
        FROM User u
        LEFT JOIN Document d ON u.id = d.user_id
        LEFT JOIN KnowledgeEntry ke ON d.id = ke.document_id
        GROUP BY u.id
        ORDER BY u.id
    ''').fetchall()
    
    conn.close()
    
    # Format users data
    users_data = []
    for user in users:
        users_data.append({
            'id': user['id'],
            'username': user['username'],
            'is_premium': bool(user['is_premium']),
            'is_admin': bool(user['is_admin']),
            'api_calls_today': user['api_calls_today'],
            'api_calls_reset_date': user['api_calls_reset_date'],
            'total_books': user['total_books'],
            'books_with_data': user['books_with_data']
        })
    
    return render_template('admin_dashboard.html', users=users_data)


@admin_bp.route('/users/<int:user_id>')
@login_required
@admin_required
def user_details(user_id):
    """Display detailed information about a specific user"""
    conn = get_db_connection()
    
    # Get user basic info
    user = conn.execute('SELECT * FROM User WHERE id = ?', (user_id,)).fetchone()
    
    if not user:
        conn.close()
        flash('User not found.', 'error')
        return redirect(url_for('admin.users_list'))
    
    # Get user's documents with processing status
    documents = conn.execute('''
        SELECT 
            d.id,
            d.filename,
            d.category,
            d.is_private,
            d.upload_timestamp,
            COUNT(ke.id) as entry_count
        FROM Document d
        LEFT JOIN KnowledgeEntry ke ON d.id = ke.document_id
        WHERE d.user_id = ?
        GROUP BY d.id
        ORDER BY d.upload_timestamp DESC
    ''', (user_id,)).fetchall()
    
    conn.close()
    
    # Format user data
    user_data = {
        'id': user['id'],
        'username': user['username'],
        'is_premium': bool(user['is_premium']),
        'is_admin': bool(user['is_admin']),
        'api_calls_today': user['api_calls_today'],
        'api_calls_reset_date': user['api_calls_reset_date']
    }
    
    # Format documents data
    documents_data = []
    for doc in documents:
        documents_data.append({
            'id': doc['id'],
            'filename': doc['filename'],
            'category': doc['category'],
            'is_private': bool(doc['is_private']),
            'created_at': doc['upload_timestamp'],
            'entry_count': doc['entry_count'],
            'has_network_data': doc['entry_count'] > 0
        })
    
    return render_template('admin_user_details.html', user=user_data, documents=documents_data)


@admin_bp.route('/api/admin/change-account-status', methods=['POST'])
@login_required
@admin_required
def api_change_account_status():
    """Change account status: admin, premium, free"""
    data = request.get_json() or {}
    user_id = data.get('user_id')
    new_status = data.get('status')  # expected: 'admin', 'premium', 'free'

    if not user_id or not new_status:
        return jsonify({'error': 'user_id and status are required'}), 400

    try:
        conn = get_db_connection()
        cur = conn.cursor()

        # Fetch target user
        target = cur.execute('SELECT * FROM User WHERE id = ?', (user_id,)).fetchone()
        if not target:
            conn.close()
            return jsonify({'error': 'User not found'}), 404

        # Prepare updates
        is_admin = 1 if new_status == 'admin' else 0
        is_premium = 1 if new_status == 'premium' else 0

        # If setting to admin, also set premium to 0 unless explicitly premium
        if new_status == 'admin':
            is_premium = 0

        cur.execute('UPDATE User SET is_admin = ?, is_premium = ? WHERE id = ?', (is_admin, is_premium, user_id))
        conn.commit()
        conn.close()

        logger.info(f"Admin {current_user.id} changed account status of user {user_id} to {new_status}")
        return jsonify({'success': True, 'message': f'User status changed to {new_status}'} )

    except Exception as e:
        logger.error(f'Error changing account status: {e}', exc_info=True)
        return jsonify({'error': 'Internal server error'}), 500


@admin_bp.route('/api/admin/delete-user-books', methods=['POST'])
@login_required
@admin_required
def api_delete_user_books():
    """Delete all documents and knowledge entries for a user"""
    data = request.get_json() or {}
    user_id = data.get('user_id')
    confirm = data.get('confirm', False)

    if not user_id:
        return jsonify({'error': 'user_id is required'}), 400
    if not confirm:
        return jsonify({'error': 'Confirmation required to delete books'}), 400

    try:
        conn = get_db_connection()
        cur = conn.cursor()

        # Find documents belonging to user
        docs = cur.execute('SELECT id, filename FROM Document WHERE user_id = ?', (user_id,)).fetchall()
        doc_ids = [d['id'] for d in docs]

        # Delete KnowledgeEntry rows
        if doc_ids:
            cur.execute(f"DELETE FROM KnowledgeEntry WHERE document_id IN ({','.join(['?']*len(doc_ids))})", tuple(doc_ids))
            # Delete Document rows
            cur.execute(f"DELETE FROM Document WHERE id IN ({','.join(['?']*len(doc_ids))})", tuple(doc_ids))

        conn.commit()
        conn.close()

        logger.info(f"Admin {current_user.id} deleted {len(doc_ids)} books for user {user_id}")
        return jsonify({'success': True, 'deleted_count': len(doc_ids)})

    except Exception as e:
        logger.error(f'Error deleting user books: {e}', exc_info=True)
        return jsonify({'error': 'Internal server error'}), 500


@admin_bp.route('/api/admin/delete-document', methods=['POST'])
@login_required
@admin_required
def api_delete_document():
    """Delete a single document and its knowledge entries"""
    data = request.get_json() or {}
    document_id = data.get('document_id')
    confirm = data.get('confirm', False)

    if not document_id:
        return jsonify({'error': 'document_id is required'}), 400
    if not confirm:
        return jsonify({'error': 'Confirmation required to delete document'}), 400

    try:
        conn = get_db_connection()
        cur = conn.cursor()

        # Get document info before deletion
        doc = cur.execute('SELECT id, filename, user_id FROM Document WHERE id = ?', (document_id,)).fetchone()
        if not doc:
            conn.close()
            return jsonify({'error': 'Document not found'}), 404

        # Delete KnowledgeEntry rows
        cur.execute('DELETE FROM KnowledgeEntry WHERE document_id = ?', (document_id,))
        
        # Delete Document row
        cur.execute('DELETE FROM Document WHERE id = ?', (document_id,))

        conn.commit()
        conn.close()

        logger.info(f"Admin {current_user.id} deleted document {document_id} ({doc['filename']}) for user {doc['user_id']}")
        return jsonify({'success': True, 'message': 'Document deleted successfully'})

    except Exception as e:
        logger.error(f'Error deleting document: {e}', exc_info=True)
        return jsonify({'error': 'Internal server error'}), 500


@admin_bp.route('/api/admin/edit-document', methods=['POST'])
@login_required
@admin_required
def api_edit_document():
    """Edit document metadata for a user's document"""
    data = request.get_json() or {}
    doc_id = data.get('document_id')
    updates = data.get('updates', {})

    if not doc_id or not updates:
        return jsonify({'error': 'document_id and updates are required'}), 400

    allowed = {'title', 'category', 'filename', 'is_private', 'author', 'year', 'publisher'}
    set_clauses = []
    params = []
    for k, v in updates.items():
        if k in allowed:
            set_clauses.append(f"{k} = ?")
            params.append(v)

    if not set_clauses:
        return jsonify({'error': 'No valid fields to update'}), 400

    params.append(doc_id)

    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(f"UPDATE Document SET {', '.join(set_clauses)} WHERE id = ?", tuple(params))
        conn.commit()
        conn.close()

        logger.info(f"Admin {current_user.id} updated document {doc_id} with {updates}")
        return jsonify({'success': True})

    except Exception as e:
        logger.error(f'Error editing document: {e}', exc_info=True)
        return jsonify({'error': 'Internal server error'}), 500


@admin_bp.route('/api/document-info')
@login_required
@admin_required
def api_document_info():
    """Return document metadata for editing"""
    doc_id = request.args.get('document_id')
    if not doc_id:
        return jsonify({'error': 'document_id is required'}), 400
    try:
        conn = get_db_connection()
        doc = conn.execute('SELECT * FROM Document WHERE id = ?', (doc_id,)).fetchone()
        conn.close()
        if not doc:
            return jsonify({'error': 'Document not found'}), 404
        return jsonify({
            'id': doc['id'],
            'title': doc['title'],
            'category': doc['category'],
            'filename': doc['filename'],
            'is_private': doc['is_private']
        })
    except Exception as e:
        logger.error(f'Error fetching document info: {e}', exc_info=True)
        return jsonify({'error': 'Internal server error'}), 500


@admin_bp.route('/api/admin/update-api-usage', methods=['POST'])
@login_required
@admin_required
def api_update_api_usage():
    """Update daily API usage for a user"""
    data = request.get_json() or {}
    user_id = data.get('user_id')
    api_calls_today = data.get('api_calls_today')

    if user_id is None or api_calls_today is None:
        return jsonify({'error': 'user_id and api_calls_today are required'}), 400

    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute('UPDATE User SET api_calls_today = ? WHERE id = ?', (int(api_calls_today), user_id))
        conn.commit()
        conn.close()

        logger.info(f"Admin {current_user.id} set api_calls_today={api_calls_today} for user {user_id}")
        return jsonify({'success': True})

    except Exception as e:
        logger.error(f'Error updating API usage: {e}', exc_info=True)
        return jsonify({'error': 'Internal server error'}), 500


@admin_bp.route('/similarity-check')
@login_required
@admin_required
def similarity_check():
    """Display keyword similarity detection page"""
    conn = get_db_connection()
    
    # Get all unique keywords from the global network
    keywords = conn.execute('''
        SELECT DISTINCT keyword
        FROM KnowledgeEntry
        WHERE keyword IS NOT NULL AND keyword != ''
        ORDER BY keyword
    ''').fetchall()
    
    conn.close()
    
    keywords_list = [kw['keyword'] for kw in keywords]
    
    return render_template('admin_similarity.html', keywords=keywords_list)


@admin_bp.route('/api/check-keyword-similarity', methods=['POST'])
@login_required
@admin_required
def check_keyword_similarity():
    """Check for similar questions within a keyword"""
    data = request.get_json()
    keyword = data.get('keyword')
    
    if not keyword:
        return jsonify({'error': 'Keyword is required'}), 400
    
    conn = get_db_connection()
    
    # Get all questions for this keyword
    questions = conn.execute('''
        SELECT DISTINCT question
        FROM KnowledgeEntry
        WHERE keyword = ?
        ORDER BY question
    ''', (keyword,)).fetchall()
    
    conn.close()
    
    questions_list = [q['question'] for q in questions]
    
    if len(questions_list) < 2:
        return jsonify({'similarities': {}, 'message': 'Not enough questions to compare'})
    
    # Check API call limits for admin (should be unlimited, but check anyway)
    from app.utils.api_limits import check_api_limit, increment_api_calls
    can_proceed, error_msg = check_api_limit(current_user, 1)
    if not can_proceed:
        return jsonify({'error': error_msg}), 429
    
    # Prepare prompt for Gemini
    prompt = f"""You are analyzing a list of questions for similarity. 
Here are the questions:
{json.dumps(questions_list, indent=2)}

If there are any similar sentences, match them and return them in this exact JSON format:
{{"sentence1": {{"sentence2": similarity_percentage_integer}}}}

Only include pairs with similarity over 90 percent.
If there are no similar sentences over 90 percent similarity, return an empty JSON object: {{}}

Return ONLY the JSON object, no additional text or explanation."""
    
    # Call Gemini API
    try:
        api_key = current_app.config['GEMINI_API_KEY']
        api_url = current_app.config['GEMINI_API_URL']
        
        headers = {'Content-Type': 'application/json'}
        payload = {
            'contents': [{
                'parts': [{'text': prompt}]
            }]
        }
        
        # Log full request
        logger.info('=== GEMINI API REQUEST (SIMILARITY CHECK) ===')
        logger.info(f'Keyword: {keyword}')
        logger.info(f'Number of questions: {len(questions_list)}')
        logger.info(f'URL: {api_url}')
        logger.info(f'Prompt sent:\n{prompt}')
        logger.info(f'Full payload: {json.dumps(payload, indent=2)}')
        
        response = requests.post(
            f"{api_url}?key={api_key}",
            headers=headers,
            json=payload,
            timeout=30
        )
        
        # Log full response
        logger.info('=== GEMINI API RESPONSE (SIMILARITY CHECK) ===')
        logger.info(f'Status Code: {response.status_code}')
        logger.info(f'Full response text: {response.text}')
        
        if response.status_code != 200:
            logger.error(f"Gemini API error: {response.status_code} - {response.text}")
            # Increment API call counter even on failure to track usage
            increment_api_calls(current_user.id)
            return jsonify({'error': f'API request failed with status {response.status_code}. Please try again later.'}), 500
        
        # Increment API call counter after successful request
        increment_api_calls(current_user.id)
        
        result = response.json()
        
        # Extract the response text
        if 'candidates' in result and len(result['candidates']) > 0:
            text_response = result['candidates'][0]['content']['parts'][0]['text']
            
            logger.info('=== EXTRACTED TEXT FROM RESPONSE ===')
            logger.info(f'Raw text response:\n{text_response}')
            
            # Clean up the response to extract JSON
            text_response = text_response.strip()
            if text_response.startswith('```json'):
                text_response = text_response[7:]
            if text_response.startswith('```'):
                text_response = text_response[3:]
            if text_response.endswith('```'):
                text_response = text_response[:-3]
            text_response = text_response.strip()
            
            logger.info('=== CLEANED TEXT FOR JSON PARSING ===')
            logger.info(f'Cleaned text:\n{text_response}')
            
            # Parse JSON
            similarities = json.loads(text_response)
            
            logger.info('=== SUCCESSFULLY PARSED SIMILARITIES ===')
            logger.info(f'Parsed similarities: {json.dumps(similarities, indent=2)}')
            
            return jsonify({
                'keyword': keyword,
                'similarities': similarities,
                'total_questions': len(questions_list)
            })
        else:
            logger.error(f"Unexpected API response: {result}")
            logger.error('=== MISSING CANDIDATES IN RESPONSE ===')
            logger.error(f'Full result structure: {json.dumps(result, indent=2)}')
            return jsonify({'error': 'Unexpected API response format. The analysis could not be completed.'}), 500
            
    except requests.exceptions.Timeout:
        logger.error(f"Gemini API timeout for keyword: {keyword}")
        logger.error('=== API REQUEST TIMEOUT ===')
        return jsonify({'error': 'API request timed out. Please try again with a smaller keyword or later.'}), 504
    except requests.exceptions.RequestException as e:
        logger.error(f"Gemini API request error: {e}")
        logger.error('=== NETWORK REQUEST EXCEPTION ===', exc_info=True)
        return jsonify({'error': f'Network error: {str(e)}. Please check your connection and try again.'}), 500
    except json.JSONDecodeError as e:
        logger.error(f"JSON parse error: {e} - Response: {text_response if 'text_response' in locals() else 'N/A'}")
        logger.error('=== JSON PARSING FAILED ===')
        logger.error(f'Error at position: {e.pos}')
        logger.error(f'Error line: {e.lineno}, column: {e.colno}')
        if 'text_response' in locals():
            logger.error(f'Problematic content:\n{text_response}')
        return jsonify({'error': 'Failed to parse API response. The AI response was malformed.'}), 500
    except Exception as e:
        logger.error(f"Error checking similarity: {e}", exc_info=True)
        logger.error('=== UNEXPECTED EXCEPTION ===')
        return jsonify({'error': f'An unexpected error occurred: {str(e)}'}), 500


@admin_bp.route('/api/approve-similarity', methods=['POST'])
@login_required
@admin_required
def approve_similarity():
    """Approve similarity and merge questions"""
    data = request.get_json()
    keyword = data.get('keyword')
    selected_question = data.get('selected_question')
    similar_question = data.get('similar_question')
    
    if not all([keyword, selected_question, similar_question]):
        return jsonify({'error': 'Missing required fields'}), 400
    
    try:
        conn = get_db_connection()
        
        # Update all entries with similar_question to use selected_question instead
        cursor = conn.execute('''
            UPDATE KnowledgeEntry
            SET question = ?
            WHERE keyword = ? AND question = ?
        ''', (selected_question, keyword, similar_question))
        
        rows_affected = cursor.rowcount
        conn.commit()
        conn.close()
        
        logger.info(f"Merged questions in keyword '{keyword}': '{similar_question}' -> '{selected_question}' ({rows_affected} rows)")
        
        return jsonify({
            'success': True,
            'message': f'Successfully merged {rows_affected} entries',
            'rows_affected': rows_affected
        })
        
    except Exception as e:
        logger.error(f"Error approving similarity: {e}")
        return jsonify({'error': str(e)}), 500


@admin_bp.route('/merge-keywords')
@login_required
@admin_required
def merge_keywords():
    """Display keyword merge page"""
    conn = get_db_connection()
    
    # Get all unique keywords from the global network
    keywords = conn.execute('''
        SELECT DISTINCT keyword
        FROM KnowledgeEntry
        WHERE keyword IS NOT NULL AND keyword != ''
        ORDER BY keyword
    ''').fetchall()
    
    conn.close()
    
    keywords_list = [kw['keyword'] for kw in keywords]
    
    return render_template('admin_merge_keywords.html', keywords=keywords_list)


@admin_bp.route('/api/merge-keywords', methods=['POST'])
@login_required
@admin_required
def merge_keywords_api():
    """Merge two keywords - change all instances of source to target"""
    data = request.get_json()
    source_keyword = data.get('source_keyword')
    target_keyword = data.get('target_keyword')
    
    if not all([source_keyword, target_keyword]):
        return jsonify({'error': 'Both source and target keywords are required'}), 400
    
    if source_keyword == target_keyword:
        return jsonify({'error': 'Source and target keywords cannot be the same'}), 400
    
    try:
        conn = get_db_connection()
        
        # Count entries that will be affected
        count = conn.execute('''
            SELECT COUNT(*) as cnt
            FROM KnowledgeEntry
            WHERE keyword = ?
        ''', (source_keyword,)).fetchone()
        
        entries_count = count['cnt']
        
        if entries_count == 0:
            conn.close()
            return jsonify({'error': f'No entries found with keyword "{source_keyword}"'}), 404
        
        # Update all entries with source_keyword to use target_keyword instead
        cursor = conn.execute('''
            UPDATE KnowledgeEntry
            SET keyword = ?
            WHERE keyword = ?
        ''', (target_keyword, source_keyword))
        
        rows_affected = cursor.rowcount
        conn.commit()
        conn.close()
        
        logger.info(f"Merged keywords: '{source_keyword}' -> '{target_keyword}' ({rows_affected} entries updated)")
        
        return jsonify({
            'success': True,
            'message': f'Successfully merged "{source_keyword}" into "{target_keyword}"',
            'rows_affected': rows_affected,
            'source_keyword': source_keyword,
            'target_keyword': target_keyword
        })
        
    except Exception as e:
        logger.error(f"Error merging keywords: {e}", exc_info=True)
        return jsonify({'error': f'An unexpected error occurred: {str(e)}'}), 500
