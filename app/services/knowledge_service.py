"""Knowledge entry database service"""

import logging
import json
from db import get_db_connection

logger = logging.getLogger(__name__)


def decompose_json_to_db(json_data, document_id, page_number=None):
    """
    Parse JSON structure and insert into KnowledgeEntry table.
    Supports two formats:
    1) Nested: {keyword: {question: {answer: proof}}}
    2) Flat: {keyword: {question: answer_text}}
    """
    logger.debug(f'Entering decompose_json_to_db for document_id={document_id}')
    logger.debug(f'JSON data: {json.dumps(json_data, indent=2)}')
    
    conn = get_db_connection()
    entries_added = 0
    
    try:
        for keyword, questions_dict in json_data.items():
            logger.debug(f'Processing keyword: {keyword}')
            
            if not isinstance(questions_dict, dict):
                logger.debug(f'Skipping non-dict value for keyword {keyword}')
                continue
            
            for question, answer_or_dict in questions_dict.items():
                logger.debug(f'Processing question: {question}')
                
                # Check if answer_or_dict is a nested dict (old format) or a string (new flat format)
                if isinstance(answer_or_dict, dict):
                    # Old nested format: {answer: proof}
                    for answer, proof in answer_or_dict.items():
                        # Handle None/null values from API - convert to empty string
                        proof = proof if proof is not None else ""
                        logger.debug(f'Inserting entry (nested): keyword={keyword}, question={question}, answer={answer}, proof={proof}')
                        if page_number is not None:
                            conn.execute(
                                'INSERT INTO KnowledgeEntry (document_id, keyword, question, answer, proof, page_number) VALUES (?, ?, ?, ?, ?, ?)',
                                (document_id, keyword, question, answer, proof, page_number)
                            )
                        else:
                            conn.execute(
                                'INSERT INTO KnowledgeEntry (document_id, keyword, question, answer, proof) VALUES (?, ?, ?, ?, ?)',
                                (document_id, keyword, question, answer, proof)
                            )
                        entries_added += 1
                else:
                    # New flat format: answer_text (string), no proof
                    answer = str(answer_or_dict) if answer_or_dict else ""
                    proof = ""  # no proof in flat format
                    logger.debug(f'Inserting entry (flat): keyword={keyword}, question={question}, answer={answer}')
                    if page_number is not None:
                        conn.execute(
                            'INSERT INTO KnowledgeEntry (document_id, keyword, question, answer, proof, page_number) VALUES (?, ?, ?, ?, ?, ?)',
                            (document_id, keyword, question, answer, proof, page_number)
                        )
                    else:
                        conn.execute(
                            'INSERT INTO KnowledgeEntry (document_id, keyword, question, answer, proof) VALUES (?, ?, ?, ?, ?)',
                            (document_id, keyword, question, answer, proof)
                        )
                    entries_added += 1
        
        conn.commit()
        logger.info(f'Successfully added {entries_added} knowledge entries for document_id={document_id}')
    
    except Exception as e:
        logger.error(f'Error decomposing JSON to database: {str(e)}', exc_info=True)
        conn.rollback()
        raise  # Re-raise to notify caller that processing failed
    
    finally:
        conn.close()
        logger.debug('Exiting decompose_json_to_db')
    
    return entries_added
