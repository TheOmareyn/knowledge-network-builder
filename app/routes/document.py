"""Document routes - Upload and Processing"""

import logging
import os
import json
from datetime import datetime
from flask import Blueprint, request, redirect, url_for, flash, session, current_app, render_template
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename

from db import get_db_connection
from app.utils import allowed_file, get_pdf_page_count, check_api_limit, increment_api_calls
from app.services import extract_text_from_pdf, get_knowledge_from_text, decompose_json_to_db

logger = logging.getLogger(__name__)

bp = Blueprint('document', __name__)


@bp.route('/upload')
@login_required
def upload_page():
    """Display the upload form page"""
    logger.debug(f'Entering upload page for user_id={current_user.id}')
    
    conn = get_db_connection()
    
    # Get all distinct doctrines for the dropdown
    doctrines = conn.execute('''
        SELECT DISTINCT doctrine 
        FROM Document 
        WHERE doctrine IS NOT NULL AND doctrine != ''
        ORDER BY doctrine
    ''').fetchall()
    doctrine_list = [d['doctrine'] for d in doctrines]
    
    # Get last uploaded document from session
    # Don't pop it if it's being processed - keep it for refreshes
    last_uploaded_id = session.get('last_uploaded_doc_id', None)
    last_uploaded_doc = None
    
    # If we have a session document, use it
    if last_uploaded_id:
        doc = conn.execute(
            'SELECT * FROM Document WHERE id = ? AND user_id = ?',
            (last_uploaded_id, current_user.id)
        ).fetchone()
        
        if doc:
            last_uploaded_doc = dict(doc)
            progress_path = os.path.join(current_app.config['UPLOAD_FOLDER'], f"{doc['id']}.progress.json")
            progress = None
            if os.path.exists(progress_path):
                try:
                    with open(progress_path, 'r', encoding='utf-8') as pf:
                        progress = json.load(pf)
                except Exception:
                    progress = None
            last_uploaded_doc['progress'] = progress
            
            # Only remove from session if processing is complete or errored
            if progress:
                status = progress.get('status', '')
                if status == 'done' or 'error' in status.lower():
                    session.pop('last_uploaded_doc_id', None)
                    last_uploaded_doc = None  # Clear it so we fall through to most recent
    
    # If no session document (or it was just cleared), get the most recently uploaded
    if not last_uploaded_doc:
        recent_doc = conn.execute(
            'SELECT * FROM Document WHERE user_id = ? ORDER BY upload_timestamp DESC LIMIT 1',
            (current_user.id,)
        ).fetchone()
        
        if recent_doc:
            last_uploaded_doc = dict(recent_doc)
            progress_path = os.path.join(current_app.config['UPLOAD_FOLDER'], f"{recent_doc['id']}.progress.json")
            progress = None
            if os.path.exists(progress_path):
                try:
                    with open(progress_path, 'r', encoding='utf-8') as pf:
                        progress = json.load(pf)
                except Exception:
                    progress = None
            last_uploaded_doc['progress'] = progress
    
    conn.close()
    logger.debug('Exiting upload page route')
    return render_template('upload.html', last_uploaded_doc=last_uploaded_doc, doctrines=doctrine_list)


@bp.route('/networks')
@login_required
def networks_page():
    """Display all user's knowledge networks (only documents with network data)"""
    logger.debug(f'Entering networks page for user_id={current_user.id}')
    
    conn = get_db_connection()
    
    # Only get documents that have knowledge entries
    documents = conn.execute(
        '''SELECT DISTINCT d.* 
           FROM Document d
           JOIN KnowledgeEntry ke ON ke.document_id = d.id
           WHERE d.user_id = ? 
           ORDER BY d.upload_timestamp DESC''',
        (current_user.id,)
    ).fetchall()
    
    # Convert to dict and add network status (always True since we filtered)
    docs_with_status = []
    for d in documents:
        doc = dict(d)
        doc['has_network'] = True
        docs_with_status.append(doc)
    
    conn.close()

    logger.debug(f'User {current_user.id} has {len(docs_with_status)} documents')
    logger.debug('Exiting networks page route')
    return render_template('networks.html', documents=docs_with_status)


@bp.route('/upload', methods=['POST'])
@login_required
def upload():
    """Handle PDF file upload"""
    logger.debug(f'Entering upload route for user_id={current_user.id}')
    
    if 'file' not in request.files:
        logger.warning(f'User {current_user.id} upload failed: no file part')
        flash('No file part in the request.', 'error')
        return redirect(url_for('document.upload_page'))
    
    file = request.files['file']
    
    if file.filename == '':
        logger.warning(f'User {current_user.id} upload failed: no selected file')
        flash('No file selected.', 'error')
        return redirect(url_for('document.upload_page'))
    
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        unique_filename = f"{current_user.id}_{timestamp}_{filename}"
        filepath = os.path.join(current_app.config['UPLOAD_FOLDER'], unique_filename)
        
        logger.info(f'User {current_user.id} uploading file: {filename} as {unique_filename}')
        file.save(filepath)
        
        # Get page count from PDF
        page_count = get_pdf_page_count(filepath)
        logger.info(f'PDF has {page_count} pages')
        
        # Get metadata from form
        title = request.form.get('title', '').strip()
        author = request.form.get('author', '').strip()
        year = request.form.get('year', '').strip()
        publisher = request.form.get('publisher', '').strip()
        journal = request.form.get('journal', '').strip()
        volume = request.form.get('volume', '').strip()
        number = request.form.get('number', '').strip()
        pages = request.form.get('pages', '').strip()
        publication_type = request.form.get('publication_type', '').strip()
        category = request.form.get('category', '').strip()
        doctrine = request.form.get('doctrine', '').strip()
        
        # Get privacy setting (only for premium users)
        is_private = 0
        if current_user.is_premium:
            is_private = 1 if request.form.get('is_private') == 'on' else 0
        
        # Add document to database
        conn = get_db_connection()
        cursor = conn.execute(
            'INSERT INTO Document (user_id, filename, title, author, year, publisher, journal, volume, number, pages, publication_type, category, doctrine, page_count, is_private) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
            (current_user.id, unique_filename, title, author, year, publisher, journal, volume, number, pages, publication_type, category, doctrine, page_count, is_private)
        )
        document_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        logger.info(f'Document {filename} saved with id={document_id}')
        
        # Create progress file
        progress = {
            'next_paragraph': 0,
            'status': 'pending',
            'error': None
        }
        progress_path = os.path.join(current_app.config['UPLOAD_FOLDER'], f"{document_id}.progress.json")
        try:
            with open(progress_path, 'w', encoding='utf-8') as pf:
                json.dump(progress, pf)
        except Exception:
            logger.warning(f'Could not write progress file for document {document_id}')

        flash(f'File uploaded successfully! Document ID: {document_id}', 'success')
        session['last_uploaded_doc_id'] = document_id
        return redirect(url_for('document.upload_page'))
    
    logger.warning(f'User {current_user.id} upload failed: invalid file type')
    flash('Invalid file type. Only PDF files are allowed.', 'error')
    return redirect(url_for('document.upload_page'))


@bp.route('/process_document/<int:document_id>', methods=['POST'])
@login_required
def process_document(document_id):
    """Process a document by extracting knowledge with Gemini API"""
    logger.debug(f'Entering process_document for document_id={document_id}, user_id={current_user.id}')

    # Get batch size from form (default 10, min 5, max 20)
    batch_size = request.form.get('batch_size', '10')
    try:
        batch_size = int(batch_size)
        batch_size = max(5, min(20, batch_size))
    except ValueError:
        batch_size = 10
    logger.debug(f'Batch size set to {batch_size}')
    
    # Get padding parameters
    skip_start = max(0, int(request.form.get('skip_start', '0') or 0))
    skip_end = max(0, int(request.form.get('skip_end', '0') or 0))
    logger.debug(f'Padding: skip_start={skip_start}, skip_end={skip_end}')

    # Verify document ownership
    conn = get_db_connection()
    document = conn.execute(
        'SELECT * FROM Document WHERE id = ? AND user_id = ?',
        (document_id, current_user.id)
    ).fetchone()
    conn.close()

    if not document:
        logger.warning(f'User {current_user.id} attempted to process unauthorized document {document_id}')
        flash('Document not found or access denied.', 'error')
        return redirect(url_for('dashboard.dashboard'))

    filepath = os.path.join(current_app.config['UPLOAD_FOLDER'], document['filename'])
    if not os.path.exists(filepath):
        logger.error(f'File for document {document_id} not found at {filepath}')
        flash('Uploaded file not found on server.', 'error')
        return redirect(url_for('dashboard.dashboard'))

    # Load and paginate pages
    all_pages = extract_text_from_pdf(filepath)
    total_pages_in_pdf = len(all_pages)
    
    # Apply padding
    end_index = total_pages_in_pdf - skip_end
    if skip_start >= end_index or end_index <= 0:
        logger.error(f'Invalid padding: skip_start={skip_start}, skip_end={skip_end}, total={total_pages_in_pdf}')
        flash('Invalid page range: Start and end padding exceed total pages.', 'error')
        return redirect(url_for('dashboard.dashboard'))
    
    pages = all_pages[skip_start:end_index]
    total_pages = len(pages)
    logger.info(f'Processing document {document_id}: {total_pages} pages after padding (batch size: {batch_size})')

    # Check API call limits
    total_batches = (total_pages + batch_size - 1) // batch_size
    api_calls_needed = total_batches
    
    can_proceed, error_msg = check_api_limit(current_user, api_calls_needed)
    if not can_proceed:
        flash(error_msg, 'error')
        return redirect(url_for('dashboard.dashboard'))
    
    # Progress tracking file
    progress_path = os.path.join(current_app.config['UPLOAD_FOLDER'], f"{document_id}.progress.json")
    progress = {'next_paragraph': 0, 'status': 'pending', 'error': None}
    try:
        if os.path.exists(progress_path):
            with open(progress_path, 'r', encoding='utf-8') as pf:
                progress = json.load(pf)
    except Exception as e:
        logger.warning(f'Unable to read progress file for document {document_id}: {e}')

    start_index = int(progress.get('next_paragraph', 0))
    entries_added_total = 0
    i = start_index
    batch_number = 0
    
    while i < total_pages:
        # Collect batch
        batch_pages = []
        batch_start = i
        for j in range(batch_size):
            if i < total_pages:
                batch_pages.append(pages[i])
                i += 1
        
        if not batch_pages:
            break
        
        batch_number += 1
        batch_end = i
        page_range = f"{batch_start + 1}-{batch_end}" if batch_start + 1 != batch_end else str(batch_start + 1)
        logger.debug(f'Processing page batch {page_range}/{total_pages} for document {document_id}')

        # Update progress
        progress['status'] = f'Processing Batch {batch_number}/{total_batches}'
        progress['current_batch'] = batch_number
        progress['total_batches'] = total_batches
        try:
            with open(progress_path, 'w', encoding='utf-8') as pf:
                json.dump(progress, pf)
        except Exception:
            logger.warning(f'Could not update progress file for document {document_id}')

        # Skip empty batches
        combined_text = ' '.join(batch_pages)
        if len(combined_text.strip()) < 50:
            logger.debug(f'Skipping empty batch {page_range}')
            progress['next_paragraph'] = batch_end
            try:
                with open(progress_path, 'w', encoding='utf-8') as pf:
                    json.dump(progress, pf)
            except Exception:
                logger.warning(f'Could not update progress file for document {document_id}')
            continue

        # Call Gemini API
        knowledge_json = get_knowledge_from_text(combined_text)
        
        # Increment API counter
        increment_api_calls(current_user.id)

        if not knowledge_json:
            msg = f'API error while processing batch {batch_number}/{total_batches} (pages {page_range}). Processing stopped.'
            logger.error(msg)
            progress['status'] = 'error'
            progress['error'] = msg
            progress['next_paragraph'] = batch_start
            try:
                with open(progress_path, 'w', encoding='utf-8') as pf:
                    json.dump(progress, pf)
            except Exception:
                logger.warning(f'Could not write progress file for document {document_id}')
            flash(msg + ' You can retry processing this document from the dashboard.', 'error')
            return redirect(url_for('dashboard.dashboard'))

        # Insert results into DB
        try:
            entries = decompose_json_to_db(knowledge_json, document_id, page_number=page_range)
            entries_added_total += entries
        except Exception as e:
            logger.error(f'Error inserting knowledge entries for document {document_id}: {e}', exc_info=True)
            progress['status'] = 'error'
            progress['error'] = str(e)
            progress['next_paragraph'] = batch_start
            try:
                with open(progress_path, 'w', encoding='utf-8') as pf:
                    json.dump(progress, pf)
            except Exception:
                logger.warning(f'Could not write progress file for document {document_id}')
            flash('Database error while processing document. Processing stopped.', 'error')
            return redirect(url_for('dashboard.dashboard'))

        # Successfully processed batch
        progress['next_paragraph'] = batch_end
        progress['status'] = f'Completed Batch {batch_number}/{total_batches}'
        try:
            with open(progress_path, 'w', encoding='utf-8') as pf:
                json.dump(progress, pf)
        except Exception:
            logger.warning(f'Could not update progress file for document {document_id}')

    # All pages processed
    try:
        progress['status'] = 'done'
        progress['next_paragraph'] = total_pages
        with open(progress_path, 'w', encoding='utf-8') as pf:
            json.dump(progress, pf)
    except Exception:
        logger.warning(f'Could not finalize progress file for document {document_id}')

    logger.info(f'Document {document_id} processing complete: {entries_added_total} entries added')
    flash(f'Processing complete: {entries_added_total} knowledge entries added.', 'success')
    return redirect(url_for('dashboard.dashboard'))
