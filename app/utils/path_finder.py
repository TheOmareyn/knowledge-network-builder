"""
Question path finding module
Finds paths between questions through books that share common questions
Uses breadth-first search to find all shortest paths
"""

import logging
from collections import deque
from db import get_db_connection

logger = logging.getLogger(__name__)


class QuestionPathFinder:
    """Finds paths between questions in the knowledge network"""
    
    def __init__(self, user_id, category_filter='', doctrine_filter=''):
        self.user_id = user_id
        self.category_filter = category_filter
        self.doctrine_filter = doctrine_filter
        self.conn = None
    
    def __enter__(self):
        self.conn = get_db_connection()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.conn:
            self.conn.close()
    
    def find_paths(self, start_question, end_question):
        """
        Find all shortest paths between two questions
        
        Args:
            start_question (str): The starting question text
            end_question (str): The ending question text
        
        Returns:
            dict: Result containing:
                - found (bool): Whether any path was found
                - paths (list): List of paths (original format)
                - detailed_paths (list): List of paths with question details
                - path_count (int): Number of paths found
                - path_length (int): Length of paths in books
                - message (str): Descriptive message
                - start_question (str): Echo of start question
                - end_question (str): Echo of end question
        """
        logger.info('=== QUESTION PATH FINDING REQUEST ===')
        logger.info(f'Start Question: {start_question}')
        logger.info(f'End Question: {end_question}')
        
        # Log filter information
        if self.category_filter:
            logger.info(f'Category Filter: {self.category_filter}')
        if self.doctrine_filter:
            logger.info(f'Doctrine Filter: {self.doctrine_filter}')
        
        # Validate inputs
        if not start_question or not end_question:
            return {'error': 'Both start and end questions are required'}
        
        if start_question == end_question:
            return {'error': 'Start and end questions cannot be the same'}
        
        # Find books containing the questions
        start_books = self._get_books_with_question(start_question)
        end_books = self._get_books_with_question(end_question)
        
        logger.info(f'Found {len(start_books)} books containing start question:')
        for book in start_books:
            logger.info(f'  - Book {book["id"]}: {book["title"] or book["filename"]}')
        
        logger.info(f'Found {len(end_books)} books containing end question:')
        for book in end_books:
            logger.info(f'  - Book {book["id"]}: {book["title"] or book["filename"]}')
        
        # Build filter message for user feedback
        filter_msg = ""
        if self.category_filter or self.doctrine_filter:
            filters = []
            if self.category_filter:
                filters.append(f"Category: {self.category_filter}")
            if self.doctrine_filter:
                filters.append(f"Doctrine: {self.doctrine_filter}")
            filter_msg = f" (with filters: {', '.join(filters)})"
        
        if not start_books:
            return {
                'found': False,
                'message': f'No books found containing the start question{filter_msg}.'
            }
        
        if not end_books:
            return {
                'found': False,
                'message': f'No books found containing the end question{filter_msg}.'
            }
        
        # Check for direct connection
        start_book_ids = {b['id'] for b in start_books}
        end_book_ids = {b['id'] for b in end_books}
        direct_connection = start_book_ids & end_book_ids
        
        if direct_connection:
            return self._handle_direct_connection(direct_connection, start_question, end_question)
        
        # Build graph and find paths
        graph = self._build_book_graph()
        paths = self._find_all_shortest_paths(start_book_ids, end_book_ids, graph)
        
        if not paths:
            logger.warning('NO PATH FOUND between start and end questions')
            logger.info('=== PATH FINDING COMPLETE (NO PATH) ===')
            return {
                'found': False,
                'message': f'No path found between the two questions{filter_msg}. The questions are in disconnected parts of the knowledge network.'
            }
        
        # Build detailed path structure
        detailed_paths = self._build_detailed_paths(paths, start_question, end_question)
        
        logger.info('=== PATH FINDING COMPLETE ===')
        logger.info(f'Total shortest paths found: {len(paths)}')
        logger.info(f'Path length: {len(paths[0])} book(s)')
        
        # Log path summaries
        for idx, path in enumerate(paths):
            path_books = ' -> '.join([step['book_title'] for step in path])
            logger.info(f'Path {idx+1}: {path_books}')
        
        return {
            'found': True,
            'path_count': len(paths),
            'path_length': len(paths[0]),
            'message': f'Found {len(paths)} path{"s" if len(paths) > 1 else ""} of length {len(paths[0])} book(s).',
            'start_question': start_question,
            'end_question': end_question,
            'paths': paths,
            'detailed_paths': detailed_paths
        }
    
    def _get_books_with_question(self, question):
        """Get all books containing the specified question, respecting filters"""
        query = '''
            SELECT DISTINCT d.id, d.title, d.filename, d.category, d.doctrine
            FROM Document d
            JOIN KnowledgeEntry ke ON d.id = ke.document_id
            WHERE ke.question = ? AND d.user_id = ?
        '''
        params = [question, self.user_id]
        
        # Apply category filter
        if self.category_filter:
            query += ' AND d.category = ?'
            params.append(self.category_filter)
        
        # Apply doctrine filter
        if self.doctrine_filter:
            query += ' AND d.doctrine = ?'
            params.append(self.doctrine_filter)
        
        return self.conn.execute(query, params).fetchall()
    
    def _handle_direct_connection(self, book_ids, start_question, end_question):
        """Handle case where both questions are in the same book"""
        book_id = list(book_ids)[0]
        book = self.conn.execute('SELECT * FROM Document WHERE id = ?', (book_id,)).fetchone()
        
        logger.info(f'DIRECT CONNECTION FOUND in book {book_id}: {book["title"] or book["filename"]}')
        logger.info('=== PATH FINDING COMPLETE ===')
        
        path = [{
            'book_id': book['id'],
            'book_title': book['title'] or book['filename'],
            'connection_type': 'contains_both'
        }]
        
        # Build detailed path for direct connection
        detailed_path = {
            'path_id': 0,
            'books': [{
                'book_id': book['id'],
                'book_title': book['title'] or book['filename'],
                'questions': [start_question, end_question]
            }]
        }
        
        return {
            'found': True,
            'path_count': 1,
            'path_length': 1,
            'message': 'Direct connection found! Both questions exist in the same book.',
            'start_question': start_question,
            'end_question': end_question,
            'paths': [path],
            'detailed_paths': [detailed_path]
        }
    
    def _build_book_graph(self):
        """
        Build a graph of books connected by shared questions
        Respects category and doctrine filters
        
        Returns:
            dict: Adjacency list {book_id: [(connected_book, shared_question), ...]}
        """
        logger.info('Building book connectivity graph...')
        
        # Get all books with filters applied
        query = '''
            SELECT DISTINCT d.id, d.title, d.filename, d.category, d.doctrine
            FROM Document d
            JOIN KnowledgeEntry ke ON d.id = ke.document_id
            WHERE d.user_id = ?
        '''
        params = [self.user_id]
        
        # Apply category filter
        if self.category_filter:
            query += ' AND d.category = ?'
            params.append(self.category_filter)
        
        # Apply doctrine filter
        if self.doctrine_filter:
            query += ' AND d.doctrine = ?'
            params.append(self.doctrine_filter)
        
        all_books = self.conn.execute(query, params).fetchall()
        
        filter_msg = []
        if self.category_filter:
            filter_msg.append(f'Category: {self.category_filter}')
        if self.doctrine_filter:
            filter_msg.append(f'Doctrine: {self.doctrine_filter}')
        
        if filter_msg:
            logger.info(f'Applied filters: {", ".join(filter_msg)}')
        logger.info(f'Total books in filtered library: {len(all_books)}')
        
        # Build question sets for each book
        book_questions = {}
        for book in all_books:
            book_id = book['id']
            questions = self.conn.execute('''
                SELECT DISTINCT question
                FROM KnowledgeEntry
                WHERE document_id = ?
            ''', (book_id,)).fetchall()
            book_questions[book_id] = {q['question'] for q in questions}
            logger.debug(f'Book {book_id} ({book["title"] or book["filename"]}): {len(questions)} questions')
        
        # Build adjacency list
        adjacency = {book_id: [] for book_id in book_questions.keys()}
        total_connections = 0
        
        logger.info('Building adjacency list (book connections)...')
        
        for book1_id in book_questions:
            for book2_id in book_questions:
                if book1_id >= book2_id:  # Avoid duplicates and self-loops
                    continue
                
                # Find shared questions
                shared = book_questions[book1_id] & book_questions[book2_id]
                
                if shared:
                    shared_question = list(shared)[0]
                    adjacency[book1_id].append((book2_id, shared_question))
                    adjacency[book2_id].append((book1_id, shared_question))
                    total_connections += 1
                    logger.debug(f'Connection: Book {book1_id} <-> Book {book2_id} via "{shared_question[:50]}..."')
        
        logger.info(f'Graph built: {total_connections} book-to-book connections found')
        
        return adjacency
    
    def _find_all_shortest_paths(self, start_book_ids, end_book_ids, adjacency):
        """
        Use BFS to find all shortest paths from start books to end books
        
        Args:
            start_book_ids (set): Set of book IDs containing start question
            end_book_ids (set): Set of book IDs containing end question
            adjacency (dict): Graph adjacency list
        
        Returns:
            list: List of paths, where each path is a list of step dicts
        """
        logger.info('Starting BFS to find all shortest paths...')
        
        queue = deque()
        visited = {}  # book_id -> distance from start
        parents = {}  # book_id -> [(prev_book_id, shared_question), ...]
        
        # Initialize with all start books
        for book_id in start_book_ids:
            queue.append((book_id, 0))
            visited[book_id] = 0
            parents[book_id] = []
            logger.info(f'BFS initialized with start book {book_id} at distance 0')
        
        found_end_books = []
        shortest_distance = None
        bfs_iterations = 0
        
        # BFS loop
        while queue:
            current_book, current_distance = queue.popleft()
            bfs_iterations += 1
            
            logger.debug(f'BFS iteration {bfs_iterations}: Visiting book {current_book} at distance {current_distance}')
            
            # Stop if we've gone beyond the shortest distance
            if shortest_distance is not None and current_distance > shortest_distance:
                logger.debug(f'Skipping - distance {current_distance} > shortest {shortest_distance}')
                continue
            
            # Check if we reached an end book
            if current_book in end_book_ids:
                if shortest_distance is None:
                    shortest_distance = current_distance
                    logger.info(f'FOUND first end book {current_book} at distance {current_distance}!')
                if current_distance == shortest_distance:
                    found_end_books.append(current_book)
                    logger.info(f'Added end book {current_book} to found list (total: {len(found_end_books)})')
                continue
            
            # Explore neighbors
            neighbors = adjacency.get(current_book, [])
            logger.debug(f'Book {current_book} has {len(neighbors)} neighbors')
            
            for neighbor_book, shared_question in neighbors:
                neighbor_distance = current_distance + 1
                
                if neighbor_book not in visited:
                    visited[neighbor_book] = neighbor_distance
                    parents[neighbor_book] = [(current_book, shared_question)]
                    queue.append((neighbor_book, neighbor_distance))
                    logger.debug(f'  New neighbor {neighbor_book} at distance {neighbor_distance} via "{shared_question[:30]}..."')
                elif visited[neighbor_book] == neighbor_distance:
                    # Same distance - alternative path
                    parents[neighbor_book].append((current_book, shared_question))
                    logger.debug(f'  Alternative path to {neighbor_book} via "{shared_question[:30]}..."')
        
        logger.info(f'BFS complete after {bfs_iterations} iterations')
        logger.info(f'Visited {len(visited)} books total')
        
        if not found_end_books:
            return []
        
        # Reconstruct all paths
        logger.info(f'Reconstructing all paths from {len(found_end_books)} end books...')
        
        all_paths = []
        for end_book_idx, end_book in enumerate(found_end_books):
            logger.info(f'Reconstructing paths for end book {end_book_idx+1}/{len(found_end_books)}: book {end_book}')
            paths = self._reconstruct_paths(end_book, parents)
            logger.info(f'  Found {len(paths)} path(s) through this end book')
            all_paths.extend(paths)
        
        return all_paths
    
    def _reconstruct_paths(self, end_book, parents, depth=0):
        """
        Recursively reconstruct all paths from start to end_book
        
        Args:
            end_book (int): Book ID to reconstruct paths to
            parents (dict): Parent mapping from BFS
            depth (int): Recursion depth for logging
        
        Returns:
            list: List of paths to this book
        """
        indent = "  " * depth
        logger.debug(f'{indent}Reconstructing paths to book {end_book}')
        
        if not parents[end_book]:  # This is a start book
            book_info = self.conn.execute('SELECT * FROM Document WHERE id = ?', (end_book,)).fetchone()
            logger.debug(f'{indent}Reached start book {end_book}: {book_info["title"] or book_info["filename"]}')
            return [[{
                'book_id': end_book,
                'book_title': book_info['title'] or book_info['filename'],
                'shared_question': None
            }]]
        
        all_paths = []
        num_parents = len(parents[end_book])
        logger.debug(f'{indent}Book {end_book} has {num_parents} parent(s)')
        
        for idx, (prev_book, shared_q) in enumerate(parents[end_book]):
            logger.debug(f'{indent}Processing parent {idx+1}/{num_parents}: book {prev_book} via "{shared_q[:30]}..."')
            
            # Get all paths to the previous book
            prev_paths = self._reconstruct_paths(prev_book, parents, depth + 1)
            
            # Extend each path with current book
            book_info = self.conn.execute('SELECT * FROM Document WHERE id = ?', (end_book,)).fetchone()
            for path_idx, path in enumerate(prev_paths):
                new_path = path + [{
                    'book_id': end_book,
                    'book_title': book_info['title'] or book_info['filename'],
                    'shared_question': shared_q
                }]
                all_paths.append(new_path)
                logger.debug(f'{indent}  Created path variant {path_idx+1}')
        
        logger.debug(f'{indent}Total paths through book {end_book}: {len(all_paths)}')
        return all_paths
    
    def _build_detailed_paths(self, paths, start_question, end_question):
        """
        Build detailed path structure with all questions for each book
        
        Args:
            paths (list): List of basic paths
            start_question (str): Starting question
            end_question (str): Ending question
        
        Returns:
            list: List of detailed path structures with question information
        """
        logger.info('Building detailed path structure with all questions...')
        detailed_paths = []
        
        for path_idx, path in enumerate(paths):
            detailed_path = {
                'path_id': path_idx,
                'books': []
            }
            
            for step_idx, step in enumerate(path):
                book_id = step['book_id']
                book_title = step['book_title']
                
                # Get all questions for this book
                all_questions = self.conn.execute('''
                    SELECT DISTINCT question
                    FROM KnowledgeEntry
                    WHERE document_id = ?
                ''', (book_id,)).fetchall()
                
                all_question_texts = [q['question'] for q in all_questions]
                
                # Determine which questions to highlight
                questions_to_highlight = []
                
                # First book: include start question
                if step_idx == 0:
                    if start_question in all_question_texts:
                        questions_to_highlight.append(start_question)
                
                # Last book: include end question
                if step_idx == len(path) - 1:
                    if end_question in all_question_texts:
                        questions_to_highlight.append(end_question)
                
                # Find shared questions with neighbors
                if step_idx > 0:
                    # Shared with previous book
                    prev_book_id = path[step_idx - 1]['book_id']
                    prev_questions = self.conn.execute('''
                        SELECT DISTINCT question
                        FROM KnowledgeEntry
                        WHERE document_id = ?
                    ''', (prev_book_id,)).fetchall()
                    prev_question_texts = set(q['question'] for q in prev_questions)
                    
                    for q in all_question_texts:
                        if q in prev_question_texts and q not in questions_to_highlight:
                            questions_to_highlight.append(q)
                
                if step_idx < len(path) - 1:
                    # Shared with next book
                    next_book_id = path[step_idx + 1]['book_id']
                    next_questions = self.conn.execute('''
                        SELECT DISTINCT question
                        FROM KnowledgeEntry
                        WHERE document_id = ?
                    ''', (next_book_id,)).fetchall()
                    next_question_texts = set(q['question'] for q in next_questions)
                    
                    for q in all_question_texts:
                        if q in next_question_texts and q not in questions_to_highlight:
                            questions_to_highlight.append(q)
                
                detailed_path['books'].append({
                    'book_id': book_id,
                    'book_title': book_title,
                    'questions': questions_to_highlight
                })
                
                logger.debug(f'Path {path_idx}, Book {step_idx} ({book_title}): {len(questions_to_highlight)} questions to highlight')
                for q_idx, q_text in enumerate(questions_to_highlight):
                    logger.debug(f'  Question {q_idx+1}: {q_text[:100]}...')
            
            detailed_paths.append(detailed_path)
        
        return detailed_paths
