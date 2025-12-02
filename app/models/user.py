"""User model and authentication"""

import logging
from datetime import date
from flask_login import UserMixin
from db import get_db_connection

logger = logging.getLogger(__name__)


class User(UserMixin):
    """User model for Flask-Login"""
    
    def __init__(self, id, username, password_hash, is_premium=0, is_admin=0, api_calls_today=0, api_calls_reset_date=None):
        logger.debug(f'Creating User object for user_id={id}, username={username}, is_premium={is_premium}, is_admin={is_admin}')
        self.id = id
        self.username = username
        self.password_hash = password_hash
        self.is_premium = bool(is_premium)
        self.is_admin = bool(is_admin)
        self.api_calls_today = api_calls_today
        self.api_calls_reset_date = api_calls_reset_date


def load_user(user_id):
    """Load user by ID for Flask-Login"""
    logger.debug(f'Loading user with id={user_id}')
    conn = get_db_connection()
    user_data = conn.execute('SELECT * FROM User WHERE id = ?', (user_id,)).fetchone()
    
    if user_data:
        logger.debug(f'User {user_id} loaded successfully')
        # sqlite3.Row uses indexing, not .get()
        try:
            is_premium = user_data['is_premium'] if 'is_premium' in user_data.keys() else 0
            is_admin = user_data['is_admin'] if 'is_admin' in user_data.keys() else 0
            api_calls_today = user_data['api_calls_today'] if 'api_calls_today' in user_data.keys() else 0
            api_calls_reset_date = user_data['api_calls_reset_date'] if 'api_calls_reset_date' in user_data.keys() else None
        except (KeyError, IndexError):
            is_premium = 0
            is_admin = 0
            api_calls_today = 0
            api_calls_reset_date = None
        
        # Reset daily counter if needed (new day)
        today = str(date.today())
        if api_calls_reset_date != today:
            logger.info(f'Resetting daily API counter for user {user_id} (last reset: {api_calls_reset_date}, today: {today})')
            conn.execute('UPDATE User SET api_calls_today = 0, api_calls_reset_date = ? WHERE id = ?', 
                        (today, user_id))
            conn.commit()
            api_calls_today = 0
            api_calls_reset_date = today
        
        conn.close()
        
        return User(
            user_data['id'], 
            user_data['username'], 
            user_data['password_hash'],
            is_premium,
            is_admin,
            api_calls_today,
            api_calls_reset_date
        )
    
    conn.close()
    logger.debug(f'User {user_id} not found')
    return None
