"""Global network visualization routes - showing all books in the database"""

import logging
import traceback
import json
import requests
from flask import Blueprint, render_template, jsonify, request, current_app
from flask_login import login_required, current_user

from db import get_db_connection
from app.utils.api_limits import check_api_limit, increment_api_calls
from app.utils.path_finder import QuestionPathFinder

logger = logging.getLogger(__name__)

bp = Blueprint('global_network', __name__)


@bp.route('/global-network')
@login_required
def global_network():
    """View global knowledge network visualization page showing all books"""
    logger.debug(f'Entering global_network route for user_id={current_user.id}')
    logger.info(f'User {current_user.id} viewing global network')
    return render_template('global_network.html')


@bp.route('/api/global_network_data')
@login_required
def global_network_data():
    """
    API endpoint returning global network graph data for Sigma.js
    Hierarchy: Category > Keywords > Questions > Books
    Books are connected to questions they answer
    """
    logger.debug(f'Entering global_network_data route for user_id={current_user.id}')
    
    conn = get_db_connection()
    
    # Get all knowledge entries for current user's documents
    entries_raw = conn.execute(
        '''SELECT ke.*, d.id as doc_id, d.title, d.filename, d.category, d.doctrine 
           FROM KnowledgeEntry ke
           JOIN Document d ON ke.document_id = d.id
           WHERE d.user_id = ?''',
        (current_user.id,)
    ).fetchall()
    entries = [dict(e) for e in entries_raw]
    conn.close()
    
    logger.debug(f'Found {len(entries)} knowledge entries for user {current_user.id}')
    
    # Build nodes and edges for Sigma.js
    # Hierarchy: Category (level 1) > Keywords (level 2) > Questions (level 3) > Books (level 4)
    nodes = []
    edges = []
    node_ids = set()
    
    # Track categories, keywords, and questions to avoid duplicates
    categories = {}
    keywords = {}
    questions = {}
    books = {}
    
    # Track which documents have entries (only show books with network data)
    docs_with_entries = set()

    try:
        # Process all knowledge entries
        for entry in entries:
            doc_id = entry['doc_id']
            docs_with_entries.add(doc_id)
            
            # Create book node only if not already created
            if doc_id not in books:
                book_id = f"book_{doc_id}"
                book_label = entry['title'] or entry['filename']
                book_category = entry.get('category') or 'Uncategorized'
                book_doctrine = entry.get('doctrine') or 'Uncategorized'
                books[doc_id] = book_id
                nodes.append({
                    'id': book_id,
                    'label': book_label[:50] + '...' if len(book_label) > 50 else book_label,
                    'size': 12,
                    'color': '#9C27B0',  # Purple for books
                    'type': 'book',
                    'document_id': doc_id,
                    'full_title': book_label,
                    'category': book_category,
                    'doctrine': book_doctrine
                })
                node_ids.add(book_id)
            
            category = entry.get('category') or 'Uncategorized'
            keyword = entry['keyword']
            question = entry['question']
            doc_id = entry['doc_id']
            
            # Create category node (level 1)
            category_id = f"cat_{category.replace(' ', '_')}"
            if category_id not in node_ids:
                categories[category] = category_id
                nodes.append({
                    'id': category_id,
                    'label': category,
                    'size': 20,
                    'color': '#FF5722',  # Deep Orange for categories
                    'type': 'category',
                    'category': category
                })
                node_ids.add(category_id)
            
            # Create keyword node (level 2)
            keyword_id = f"kw_{keyword.replace(' ', '_')}_{category_id}"
            if keyword_id not in node_ids:
                keywords[f"{category}_{keyword}"] = keyword_id
                nodes.append({
                    'id': keyword_id,
                    'label': keyword,
                    'size': 16,
                    'color': '#4CAF50',  # Green for keywords
                    'type': 'keyword',
                    'category': category
                })
                node_ids.add(keyword_id)
                
                # Create edge from category to keyword
                edges.append({
                    'id': f"e_{category_id}_{keyword_id}",
                    'source': category_id,
                    'target': keyword_id,
                    'size': 2.5,
                    'color': '#FF8A65'
                })
            
            # Create question node (level 3)
            # Use question text as unique identifier (questions can appear in multiple books)
            question_id = f"q_{abs(hash(question)) % 1000000}"
            if question_id not in node_ids:
                questions[question] = question_id
                nodes.append({
                    'id': question_id,
                    'label': question[:60] + '...' if len(question) > 60 else question,
                    'size': 13,
                    'color': '#2196F3',  # Blue for questions
                    'type': 'question',
                    'full_question': question,
                    'category': category
                })
                node_ids.add(question_id)
                
                # Create edge from keyword to question
                edges.append({
                    'id': f"e_{keyword_id}_{question_id}",
                    'source': keyword_id,
                    'target': question_id,
                    'size': 2,
                    'color': '#81C784'
                })
            
            # Create edge from question to book (showing which books answer this question)
            book_id = books.get(doc_id)
            if book_id:
                edge_id = f"e_{question_id}_{book_id}"
                # Avoid duplicate edges
                if not any(e['id'] == edge_id for e in edges):
                    edges.append({
                        'id': edge_id,
                        'source': question_id,
                        'target': book_id,
                        'size': 1.5,
                        'color': '#64B5F6'
                    })
    
    except Exception as e:
        tb = traceback.format_exc()
        logger.error(f'Error while building global network data: {e}\n{tb}')
        return jsonify({'error': 'internal', 'message': str(e), 'trace': tb}), 500
    
    result = {
        'nodes': nodes,
        'edges': edges
    }
    
    logger.info(f'Generated global network data: {len(nodes)} nodes, {len(edges)} edges')
    logger.debug('Exiting global_network_data route')
    
    return jsonify(result)


@bp.route('/api/find-question-path', methods=['POST'])
@login_required
def find_question_path():
    """
    Find a path between two questions through books that share questions.
    Uses breadth-first search where:
    - Each book is a node
    - Books are connected if they share exact same questions
    - Path shows the chain of books and shared questions connecting the two target questions
    - Respects category and doctrine filters
    """
    try:
        data = request.get_json()
        start_question = data.get('start_question')
        end_question = data.get('end_question')
        category_filter = data.get('category_filter', '')
        doctrine_filter = data.get('doctrine_filter', '')
        
        if not start_question or not end_question:
            return jsonify({'error': 'Both start and end questions are required'}), 400
        
        if start_question == end_question:
            return jsonify({'error': 'Start and end questions cannot be the same'}), 400
        
        logger.info(f'Question path search with filters - Category: {category_filter or "None"}, Doctrine: {doctrine_filter or "None"}')
        
        # Use the path finder module with filters
        with QuestionPathFinder(current_user.id, category_filter=category_filter, doctrine_filter=doctrine_filter) as finder:
            result = finder.find_paths(start_question, end_question)
        
        # Check if there was an error
        if 'error' in result:
            return jsonify(result), 400
        
        # Return the result
        if result['found']:
            return jsonify(result)
        else:
            return jsonify(result)
        
    except Exception as e:
        logger.error(f"Error finding question path: {e}", exc_info=True)
        return jsonify({'error': f'An unexpected error occurred: {str(e)}'}), 500


@bp.route('/api/check-consistency', methods=['POST'])
@login_required
def check_consistency():
    """
    Check answer consistency across books in a path using Gemini AI
    Analyzes ALL intersection questions between books in the path
    Caches results in database to avoid redundant API calls
    """
    try:
        data = request.get_json()
        detailed_paths = data.get('detailed_paths', [])
        path_index = data.get('path_index', 0)
        start_question = data.get('start_question', '')
        end_question = data.get('end_question', '')
        
        logger.info('=== CONSISTENCY CHECK REQUEST ===')
        logger.info(f'Path index: {path_index}')
        logger.info(f'Start question: {start_question[:100]}...')
        logger.info(f'End question: {end_question[:100]}...')
        
        if not detailed_paths or path_index >= len(detailed_paths):
            logger.error('Invalid path data or path index')
            return jsonify({'error': 'Invalid path data.'}), 400
        
        selected_path = detailed_paths[path_index]
        books = selected_path.get('books', [])
        
        if len(books) < 2:
            logger.error(f'Path has only {len(books)} books, need at least 2')
            return jsonify({'error': 'Path must contain at least 2 books.'}), 400
        
        logger.info(f'Analyzing path with {len(books)} books')
        
        conn = get_db_connection()
        
        # Collect all intersection questions between consecutive books
        intersection_questions = []
        
        for i in range(len(books) - 1):
            book1 = books[i]
            book2 = books[i + 1]
            book1_id = book1['book_id']
            book2_id = book2['book_id']
            book1_title = book1['book_title']
            book2_title = book2['book_title']
            
            logger.info(f'--- Analyzing intersection {i+1}: "{book1_title}" <-> "{book2_title}" ---')
            
            # Get all questions from both books
            book1_questions = set(conn.execute('''
                SELECT DISTINCT question FROM KnowledgeEntry WHERE document_id = ?
            ''', (book1_id,)).fetchall())
            book1_questions = {q['question'] for q in book1_questions}
            
            book2_questions = set(conn.execute('''
                SELECT DISTINCT question FROM KnowledgeEntry WHERE document_id = ?
            ''', (book2_id,)).fetchall())
            book2_questions = {q['question'] for q in book2_questions}
            
            # Find shared questions
            shared = book1_questions & book2_questions
            logger.info(f'Found {len(shared)} shared questions between books {book1_id} and {book2_id}')
            
            for question in shared:
                logger.debug(f'Shared question: {question[:80]}...')
                
                # Get answers from both books
                answer1 = conn.execute('''
                    SELECT answer FROM KnowledgeEntry 
                    WHERE document_id = ? AND question = ?
                ''', (book1_id, question)).fetchone()
                
                answer2 = conn.execute('''
                    SELECT answer FROM KnowledgeEntry 
                    WHERE document_id = ? AND question = ?
                ''', (book2_id, question)).fetchone()
                
                if answer1 and answer2:
                    intersection_questions.append({
                        'question': question,
                        'book1_id': book1_id,
                        'book2_id': book2_id,
                        'book1_title': book1_title,
                        'book2_title': book2_title,
                        'book1_answer': answer1['answer'],
                        'book2_answer': answer2['answer']
                    })
        
        logger.info(f'Total intersection questions to check: {len(intersection_questions)}')
        
        if not intersection_questions:
            conn.close()
            logger.warning('No intersection questions found')
            return jsonify({
                'error': 'No shared questions found between consecutive books in the path.'
            }), 400
        
        # Check cache and prepare questions that need API calls
        questions_needing_check = []
        cached_results = []
        
        for item in intersection_questions:
            question = item['question']
            book1_id = item['book1_id']
            book2_id = item['book2_id']
            
            # Normalize book IDs (smaller ID first for consistent cache lookup)
            min_book_id = min(book1_id, book2_id)
            max_book_id = max(book1_id, book2_id)
            
            # Check if we have this in cache
            cached = conn.execute('''
                SELECT * FROM ConsistencyCheck 
                WHERE question = ? AND book1_id = ? AND book2_id = ?
            ''', (question, min_book_id, max_book_id)).fetchone()
            
            if cached:
                logger.info(f'CACHE HIT: Question "{question[:60]}..." between books {min_book_id} and {max_book_id}')
                cached_results.append({
                    'question': question,
                    'book1_id': book1_id,
                    'book2_id': book2_id,
                    'book1_title': item['book1_title'],
                    'book2_title': item['book2_title'],
                    'book1_answer': item['book1_answer'],
                    'book2_answer': item['book2_answer'],
                    'contradiction_percentage': cached['contradiction_percentage'],
                    'from_cache': True
                })
            else:
                logger.info(f'CACHE MISS: Question "{question[:60]}..." between books {min_book_id} and {max_book_id}')
                questions_needing_check.append(item)
        
        logger.info(f'Cached results: {len(cached_results)}, Need API check: {len(questions_needing_check)}')
        
        # Analyze new questions with Gemini if needed
        new_results = []
        if questions_needing_check:
            # Check API limit
            can_call, error_msg = check_api_limit(current_user, 1)
            if not can_call:
                conn.close()
                logger.error(f'API limit exceeded: {error_msg}')
                return jsonify({'error': error_msg}), 429
            
            # Prepare data for Gemini
            questions_for_gemini = {}
            for item in questions_needing_check:
                question = item['question']
                if question not in questions_for_gemini:
                    questions_for_gemini[question] = []
                questions_for_gemini[question].append(item['book1_answer'])
                questions_for_gemini[question].append(item['book2_answer'])
            
            # Call Gemini API
            api_key = current_app.config['GEMINI_API_KEY']
            url = f'https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash-lite:generateContent?key={api_key}'
            
            prompt = f"""Analyze the consistency of answers to questions from different books.
For each question, determine the contradiction percentage (0-100):
- 0% = answers are completely consistent/parallel
- 100% = answers are completely contradictory
- Intermediate values = partial contradictions

Questions and their answers from different books:
{json.dumps(questions_for_gemini, indent=2)}

Return ONLY a JSON object in this exact format (no markdown, no explanation):
{{"Question 1 text": contradiction_percentage_integer, "Question 2 text": contradiction_percentage_integer}}"""
            
            payload = {
                'contents': [{
                    'parts': [{'text': prompt}]
                }],
                'generationConfig': {
                    'temperature': 0.1,
                    'maxOutputTokens': 4096
                }
            }
            
            logger.info('=== GEMINI API REQUEST (CONSISTENCY CHECK) ===')
            logger.info(f'URL: {url}')
            logger.info(f'Checking {len(questions_for_gemini)} questions')
            logger.debug(f'Prompt: {prompt}')
            
            response = requests.post(url, json=payload, timeout=60)
            
            logger.info('=== GEMINI API RESPONSE ===')
            logger.info(f'Status Code: {response.status_code}')
            logger.debug(f'Full response: {response.text}')
            
            if response.status_code != 200:
                conn.close()
                logger.error(f'Gemini API error: {response.text}')
                return jsonify({
                    'error': f'Gemini API error: {response.status_code}. Please try again.'
                }), 500
            
            response_data = response.json()
            
            # Parse response
            try:
                text = response_data['candidates'][0]['content']['parts'][0]['text']
                logger.info(f'Extracted text from Gemini response')
                logger.debug(f'Raw text: {text}')
                
                # Clean up markdown
                text = text.strip()
                if text.startswith('```json'):
                    text = text[7:]
                if text.startswith('```'):
                    text = text[3:]
                if text.endswith('```'):
                    text = text[:-3]
                text = text.strip()
                
                contradictions = json.loads(text)
                logger.info(f'Successfully parsed {len(contradictions)} contradiction results')
                logger.debug(f'Contradictions: {json.dumps(contradictions, indent=2)}')
                
                # Map results back to intersection questions and cache them
                for item in questions_needing_check:
                    question = item['question']
                    percentage = contradictions.get(question, 50)  # Default to 50 if not found
                    
                    # Normalize book IDs for storage
                    min_book_id = min(item['book1_id'], item['book2_id'])
                    max_book_id = max(item['book1_id'], item['book2_id'])
                    
                    # Store in database (use INSERT OR REPLACE to handle duplicates)
                    conn.execute('''
                        INSERT OR REPLACE INTO ConsistencyCheck 
                        (question, book1_id, book2_id, book1_answer, book2_answer, contradiction_percentage, checked_timestamp)
                        VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                    ''', (question, min_book_id, max_book_id, item['book1_answer'], item['book2_answer'], percentage))
                    
                    logger.info(f'Cached result: Question "{question[:60]}..." = {percentage}% contradiction')
                    
                    new_results.append({
                        'question': question,
                        'book1_id': item['book1_id'],
                        'book2_id': item['book2_id'],
                        'book1_title': item['book1_title'],
                        'book2_title': item['book2_title'],
                        'book1_answer': item['book1_answer'],
                        'book2_answer': item['book2_answer'],
                        'contradiction_percentage': percentage,
                        'from_cache': False
                    })
                
                conn.commit()
                logger.info(f'Committed {len(new_results)} new results to database')
                
                # Increment API call counter
                increment_api_calls(current_user.id)
                
            except (KeyError, IndexError, json.JSONDecodeError) as e:
                conn.close()
                logger.error(f'Error parsing Gemini response: {e}', exc_info=True)
                return jsonify({
                    'error': f'Error parsing AI response. Please try again.'
                }), 500
        
        conn.close()
        
        # Combine cached and new results
        all_results = cached_results + new_results
        logger.info(f'=== CONSISTENCY CHECK COMPLETE ===')
        logger.info(f'Total results: {len(all_results)} ({len(cached_results)} from cache, {len(new_results)} new)')
        
        # Calculate average contradiction
        avg_contradiction = sum(r['contradiction_percentage'] for r in all_results) / len(all_results) if all_results else 0
        logger.info(f'Average contradiction: {avg_contradiction:.1f}%')
        
        return jsonify({
            'intersection_question_results': all_results,
            'total_questions': len(all_results),
            'cached_count': len(cached_results),
            'new_count': len(new_results),
            'average_contradiction': round(avg_contradiction, 1)
        })
        
    except requests.exceptions.Timeout:
        logger.error('Gemini API request timed out')
        return jsonify({'error': 'Request timed out. Please try again.'}), 504
        
    except requests.exceptions.RequestException as e:
        logger.error(f'Network error calling Gemini API: {e}', exc_info=True)
        return jsonify({'error': 'Network error. Please check your connection and try again.'}), 503
        
    except Exception as e:
        logger.error(f"Error checking consistency: {e}", exc_info=True)
        return jsonify({'error': f'An unexpected error occurred: {str(e)}'}), 500


@bp.route('/api/narrative-analysis', methods=['POST'])
@login_required
def narrative_analysis():
    """Generate narrative analysis of the question path using Gemini API"""
    logger.debug(f'Entering narrative_analysis route for user_id={current_user.id}')
    
    try:
        # Check API limits (narrative analysis typically needs 1 API call)
        can_proceed, error_msg = check_api_limit(current_user, 1)
        if not can_proceed:
            logger.warning(f'API limit check failed for user {current_user.id}: {error_msg}')
            return jsonify({'error': error_msg}), 429
        
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        detailed_paths = data.get('detailed_paths', [])
        path_index = data.get('path_index', 0)
        start_question = data.get('start_question', '')
        end_question = data.get('end_question', '')
        
        if not detailed_paths or path_index >= len(detailed_paths):
            return jsonify({'error': 'Invalid path data provided'}), 400
        
        # Get the selected path
        selected_path = detailed_paths[path_index]
        
        logger.info(f'=== NARRATIVE ANALYSIS START ===')
        logger.info(f'User {current_user.id} - Path with {len(selected_path["books"])} books')
        logger.info(f'Start: {start_question[:50]}...')
        logger.info(f'End: {end_question[:50]}...')
        
        # Build detailed prompt for Gemini
        prompt = f"""You are a scholar analyzing a discourse path through Islamic jurisprudence (fiqh) texts. 

Please create a narrative analysis of how different authors build upon, contradict, or complement each other's views as they discuss related questions. Focus on the scholarly conversation and intellectual development of ideas.

**Starting Question:** {start_question}

**Ending Question:** {end_question}

**Path Through Books:**
"""
        
        # Add detailed information about each book and its questions
        for i, book_info in enumerate(selected_path['books']):
            prompt += f"\n**Book {i+1}: {book_info['book_title']}**\n"
            
            # Add questions from this book
            for j, question in enumerate(book_info['questions']):
                prompt += f"  Question {j+1}: {question}\n"
        
        prompt += f"""

Please analyze this scholarly path and create a flowing narrative that:

1. Starts with how the first author approaches the starting question
2. Shows how subsequent authors build upon, challenge, or refine the discourse
3. Identifies key points of agreement and disagreement between authors
4. Traces the intellectual development from the start question to the end question
5. Concludes with how the final author addresses the ending question

Write in an academic but accessible style, using phrases like:
- "Author X claims that..."
- "While they disagree on..., they agree on..."
- "Building on this foundation, Author Y argues..."
- "This creates a tension that Author Z attempts to resolve by..."
- "Finally, Author W concludes that..."

Focus on the scholarly conversation and how ideas evolve through the path. Make it read like a literature review that traces intellectual development.

**Length:** Aim for 300-500 words. Be comprehensive but concise.
"""

        logger.debug(f'Sending prompt to Gemini API (length: {len(prompt)} chars)')
        
        # Call Gemini API
        gemini_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-lite:generateContent?key={current_app.config['GEMINI_API_KEY']}"
        
        gemini_payload = {
            "contents": [{
                "parts": [{"text": prompt}]
            }],
            "generationConfig": {
                "temperature": 0.7,
                "maxOutputTokens": 8192,
                "topP": 0.8,
                "topK": 40
            }
        }
        
        logger.debug('Calling Gemini API for narrative analysis')
        response = requests.post(
            gemini_url,
            json=gemini_payload,
            headers={'Content-Type': 'application/json'},
            timeout=60
        )
        
        # Increment API counter
        increment_api_calls(current_user.id)
        
        if response.status_code != 200:
            logger.error(f'Gemini API error: {response.status_code} - {response.text}')
            return jsonify({'error': f'API error: {response.status_code}'}), 500
        
        response_data = response.json()
        logger.debug(f'Received response from Gemini API: {len(str(response_data))} chars')
        
        # Extract narrative from response
        if 'candidates' in response_data and len(response_data['candidates']) > 0:
            content = response_data['candidates'][0].get('content', {})
            if 'parts' in content and len(content['parts']) > 0:
                narrative = content['parts'][0].get('text', '')
                
                if narrative:
                    logger.info(f'=== NARRATIVE ANALYSIS COMPLETE ===')
                    logger.info(f'Generated narrative length: {len(narrative)} characters')
                    
                    return jsonify({
                        'narrative': narrative,
                        'path_summary': {
                            'books_count': len(selected_path['books']),
                            'start_question': start_question,
                            'end_question': end_question,
                            'path_index': path_index
                        }
                    })
        
        logger.error('No valid narrative generated by Gemini API')
        return jsonify({'error': 'Failed to generate narrative analysis'}), 500
        
    except requests.exceptions.Timeout:
        logger.error('Gemini API request timed out')
        return jsonify({'error': 'Request timed out. Please try again.'}), 504
        
    except requests.exceptions.RequestException as e:
        logger.error(f'Network error calling Gemini API: {e}', exc_info=True)
        return jsonify({'error': 'Network error. Please check your connection and try again.'}), 503
        
    except Exception as e:
        logger.error(f"Error in narrative analysis: {e}", exc_info=True)
        return jsonify({'error': f'An unexpected error occurred: {str(e)}'}), 500
