"""Gemini API service for knowledge extraction"""

import logging
import json
import requests
from flask import current_app

logger = logging.getLogger(__name__)


def get_knowledge_from_text(text):
    """
    Send text to Gemini API and extract knowledge structure.
    Returns structured JSON with keywords, questions, answers, and proofs.
    """
    logger.debug('Entering get_knowledge_from_text')
    logger.debug(f'Text length: {len(text)} characters')
    
    prompt = """Analyze the given paragraphes of text and perform the following steps:

1. **Keyword (Type 1):** Identify the primary keyword or topic.
2. **Question (Type 2):** Formulate a question the paragraph answers.
3. **Answer (Type 3):** Extract the answer given by author. If longer than one sentence summarize the answer to one sentence.
4. **Reasoning/Proof/Citing (Type 4):** Extract evidence/reasoning/citing. If longer than one sentence summarize the proof to one sentence.

Respond as a single JSON object in the given structure:
{
  "keyword1": {
    "question1": {
      "answer1": "proof1"
    },
    "question2": {
      "answer2": "proof2"
    }
  },
  "keyword3": {
    "question3": {
      "answer3": "proof3"
    }
  }
}
**Important:**
Each paragraph should be analayzed separately. And try to catch the main question the author is trying to answer in the paragraph. Each paragraph should have only 1 main question recorded.
If the text is about the contents of the book, the publisher of the book, the author of the book, the rights of the book, the abstract of the book, and the literature review, or bibliography/references section ignore these text.
Not all statements have a reasoning or proof. If there is no reasoning or proof given to an answer do not give a proof. If the reasoning is a citation from another author, only mention the citation.
Even some questions may not have answers in the text. In that case, do not include them in the JSON.
The answer should end in one output by gemini. Do not respond with incomplete json answers.
Keywords should be more general and shouldn't be longer than 2 words.
If there is nothing to analyze, respond with an empty JSON object: {}.
Text to analyze:
""" + text

    payload = {
        "contents": [{
            "parts": [{
                "text": prompt
            }]
        }],
        "generationConfig": {
            "temperature": 0.7,
            "maxOutputTokens": 4096
        }
    }
    
    # Log full request
    logger.info('=== GEMINI API REQUEST ===')
    logger.info(f'URL: {current_app.config["GEMINI_API_URL"]}')
    logger.info(f'Prompt: {prompt}')
    logger.info(f'Full payload: {json.dumps(payload, indent=2)}')
    
    try:
        response = requests.post(
            f'{current_app.config["GEMINI_API_URL"]}?key={current_app.config["GEMINI_API_KEY"]}',
            headers={'Content-Type': 'application/json'},
            json=payload,
            timeout=45
        )
        
        # Log full response
        logger.info('=== GEMINI API RESPONSE ===')
        logger.info(f'Status Code: {response.status_code}')
        logger.info(f'Full response: {response.text}')
        
        if response.status_code == 200:
            response_data = response.json()
            
            # Extract text from Gemini response
            if 'candidates' in response_data and len(response_data['candidates']) > 0:
                content = response_data['candidates'][0]['content']['parts'][0]['text']
                logger.debug(f'Extracted content: {content}')
                
                # Parse JSON from response
                content = content.strip()
                if content.startswith('```json'):
                    content = content[7:]
                if content.startswith('```'):
                    content = content[3:]
                if content.endswith('```'):
                    content = content[:-3]
                content = content.strip()
                
                try:
                    knowledge_json = json.loads(content)
                    
                    if not knowledge_json or knowledge_json == {}:
                        logger.info('=== EMPTY JSON RESPONSE ===')
                        logger.info('API returned empty JSON - no extractable content from these pages. Passing.')
                        return {}
                    
                    logger.info('=== SUCCESSFULLY PARSED JSON ===')
                    logger.info(f'Parsed knowledge JSON: {json.dumps(knowledge_json, indent=2)}')
                    return knowledge_json
                    
                except json.JSONDecodeError as json_error:
                    logger.error('=== JSON PARSING FAILED ===')
                    logger.error(f'JSON Error: {str(json_error)}')
                    logger.error(f'Error at position: {json_error.pos}')
                    logger.error(f'Error line: {json_error.lineno}, column: {json_error.colno}')
                    logger.error(f'Problematic content:\n{content}')
                    logger.error('Returning empty dict due to JSON parsing error.')
                    return {}
            else:
                logger.error('No candidates in Gemini response')
                return {}
        else:
            logger.error(f'Gemini API request failed with status {response.status_code}')
            return {}
    
    except Exception as e:
        logger.error(f'Error calling Gemini API: {str(e)}', exc_info=True)
        logger.debug('Exiting get_knowledge_from_text with error')
        return {}
