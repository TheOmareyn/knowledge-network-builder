"""API call limit management"""

import logging
from datetime import date
from db import get_db_connection

logger = logging.getLogger(__name__)


def check_api_limit(user, api_calls_needed):
    """
    Check if user has enough API calls remaining.
    Returns (bool, str) - (can_proceed, error_message)
    """
    # Admin users have unlimited API calls
    if user.is_admin:
        logger.debug(f'Admin user {user.id} bypassing API limit check')
        return True, None
    
    conn = get_db_connection()
    user_data = conn.execute('SELECT * FROM User WHERE id = ?', (user.id,)).fetchone()
    
    # Reset daily counter if needed
    today = str(date.today())
    if user_data['api_calls_reset_date'] != today:
        conn.execute('UPDATE User SET api_calls_today = 0, api_calls_reset_date = ? WHERE id = ?', 
                    (today, user.id))
        conn.commit()
        api_calls_today = 0
    else:
        api_calls_today = user_data['api_calls_today']
    
    conn.close()
    
    # Set limits based on premium status
    daily_limit = 100 if user.is_premium else 20
    
    if api_calls_today + api_calls_needed > daily_limit:
        logger.warning(f'User {user.id} exceeded API limit. Used: {api_calls_today}, Needed: {api_calls_needed}, Limit: {daily_limit}')
        error_msg = f'API call limit exceeded. You have used {api_calls_today}/{daily_limit} calls today. This document needs {api_calls_needed} calls.'
        if not user.is_premium:
            error_msg += ' Upgrade to premium for 100 calls/day!'
        return False, error_msg
    
    return True, None


def increment_api_calls(user_id):
    """Increment the API call counter for a user."""
    conn = get_db_connection()
    conn.execute('UPDATE User SET api_calls_today = api_calls_today + 1 WHERE id = ?', (user_id,))
    conn.commit()
    conn.close()
    logger.debug(f'Incremented API call counter for user {user_id}')
