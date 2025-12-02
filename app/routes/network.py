"""Network visualization routes"""

import logging
import traceback
from flask import Blueprint, render_template, jsonify, flash, redirect, url_for
from flask_login import login_required, current_user

from db import get_db_connection

logger = logging.getLogger(__name__)

bp = Blueprint('network', __name__)


@bp.route('/view/<int:document_id>')
@login_required
def view_network(document_id):
    """View knowledge network visualization page"""
    logger.debug(f'Entering view_network route for document_id={document_id}, user_id={current_user.id}')
    
    conn = get_db_connection()
    document = conn.execute(
        'SELECT * FROM Document WHERE id = ? AND user_id = ?',
        (document_id, current_user.id)
    ).fetchone()
    conn.close()
    
    if not document:
        logger.warning(f'User {current_user.id} attempted to view unauthorized document {document_id}')
        flash('Document not found or access denied.', 'error')
        return redirect(url_for('dashboard.dashboard'))
    
    logger.info(f'User {current_user.id} viewing network for document {document_id}')
    logger.debug('Exiting view_network route')
    return render_template('view_network.html', document=document)


@bp.route('/api/network_data/<int:document_id>')
@login_required
def network_data(document_id):
    """API endpoint returning network graph data for Sigma.js"""
    logger.debug(f'Entering network_data route for document_id={document_id}, user_id={current_user.id}')
    
    conn = get_db_connection()
    
    # Verify document belongs to current user
    document = conn.execute(
        'SELECT * FROM Document WHERE id = ? AND user_id = ?',
        (document_id, current_user.id)
    ).fetchone()
    
    if not document:
        logger.warning(f'User {current_user.id} attempted to access unauthorized document {document_id}')
        conn.close()
        return jsonify({'error': 'Document not found or access denied'}), 404
    
    # Get all knowledge entries for this document
    entries_raw = conn.execute(
        'SELECT * FROM KnowledgeEntry WHERE document_id = ?',
        (document_id,)
    ).fetchall()
    entries = [dict(e) for e in entries_raw]
    conn.close()
    
    logger.debug(f'Found {len(entries)} knowledge entries for document {document_id}')
    
    # Build nodes and edges for Sigma.js
    nodes = []
    edges = []
    node_ids = set()

    try:
        for entry in entries:
            keyword = entry['keyword']
            question = entry['question']

            # Create keyword node
            keyword_id = f"k_{keyword.replace(' ', '_')}"
            if keyword_id not in node_ids:
                nodes.append({
                    'id': keyword_id,
                    'label': keyword,
                    'size': 15,
                    'color': '#4CAF50',
                    'type': 'keyword'
                })
                node_ids.add(keyword_id)

            # Create question node
            question_id = f"q_{entry['id']}"
            nodes.append({
                'id': question_id,
                'label': question[:50] + '...' if len(question) > 50 else question,
                'size': 10,
                'color': '#2196F3',
                'type': 'question',
                'full_question': question,
                'answer': entry['answer'],
                'proof': entry['proof']
            })

            # Create edge from keyword to question
            edges.append({
                'id': f"e_{keyword_id}_{question_id}",
                'source': keyword_id,
                'target': question_id,
                'size': 2,
                'color': '#999'
            })

            # Create answer node (level 3) if present
            if entry.get('answer') and entry.get('answer').strip():
                answer_id = f"a_{entry['id']}"
                nodes.append({
                    'id': answer_id,
                    'label': entry['answer'][:80] + ('...' if len(entry['answer']) > 80 else ''),
                    'size': 8,
                    'color': '#FF9800',
                    'type': 'answer',
                    'answer_text': entry['answer']
                })
                edges.append({
                    'id': f"e_{question_id}_{answer_id}",
                    'source': question_id,
                    'target': answer_id,
                    'size': 1.5,
                    'color': '#EF9A9A'
                })

                # Create proof node (level 4) if present
                if entry.get('proof') and entry.get('proof').strip():
                    proof_id = f"p_{entry['id']}"
                    nodes.append({
                        'id': proof_id,
                        'label': entry['proof'][:80] + ('...' if len(entry['proof']) > 80 else ''),
                        'size': 6,
                        'color': '#F44336',
                        'type': 'proof',
                        'proof_text': entry['proof']
                    })
                    edges.append({
                        'id': f"e_{answer_id}_{proof_id}",
                        'source': answer_id,
                        'target': proof_id,
                        'size': 1,
                        'color': '#EF5350'
                    })
    except Exception as e:
        tb = traceback.format_exc()
        logger.error(f'Error while building network data for document {document_id}: {e}\n{tb}')
        return jsonify({'error': 'internal', 'message': str(e), 'trace': tb}), 500
    
    result = {
        'nodes': nodes,
        'edges': edges
    }
    
    logger.info(f'Generated network data for document {document_id}: {len(nodes)} nodes, {len(edges)} edges')
    logger.debug('Exiting network_data route')
    
    return jsonify(result)
