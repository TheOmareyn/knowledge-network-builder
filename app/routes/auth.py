"""Authentication routes - Login, Register, Logout"""

import logging
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_user, logout_user, current_user, login_required
from werkzeug.security import generate_password_hash, check_password_hash

from db import get_db_connection
from app.models.user import User

logger = logging.getLogger(__name__)

bp = Blueprint('auth', __name__)


@bp.route('/')
def index():
    """Root route - redirect to dashboard or login"""
    logger.debug('Entering index route')
    if current_user.is_authenticated:
        logger.debug(f'User {current_user.id} is authenticated, redirecting to dashboard')
        return redirect(url_for('dashboard.dashboard'))
    logger.debug('User not authenticated, redirecting to login')
    return redirect(url_for('auth.login'))


@bp.route('/register', methods=['GET', 'POST'])
def register():
    """User registration"""
    logger.debug('Entering register route')
    
    if current_user.is_authenticated:
        logger.debug(f'User {current_user.id} already authenticated, redirecting to dashboard')
        return redirect(url_for('dashboard.dashboard'))
    
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        logger.info(f'Registration attempt for username: {username}')
        
        if not username or not password:
            logger.warning('Registration failed: missing username or password')
            flash('Username and password are required.', 'error')
            return render_template('register.html')
        
        conn = get_db_connection()
        
        # Check if user already exists
        existing_user = conn.execute('SELECT * FROM User WHERE username = ?', (username,)).fetchone()
        
        if existing_user:
            logger.warning(f'Registration failed: username {username} already exists')
            flash('Username already exists.', 'error')
            conn.close()
            return render_template('register.html')
        
        # Create new user
        password_hash = generate_password_hash(password, method='pbkdf2:sha256')
        conn.execute('INSERT INTO User (username, password_hash) VALUES (?, ?)', (username, password_hash))
        conn.commit()
        
        user_id = conn.execute('SELECT id FROM User WHERE username = ?', (username,)).fetchone()['id']
        conn.close()
        
        logger.info(f'User {username} (id={user_id}) registered successfully')
        flash('Registration successful! Please log in.', 'success')
        return redirect(url_for('auth.login'))
    
    logger.debug('Exiting register route - showing form')
    return render_template('register.html')


@bp.route('/login', methods=['GET', 'POST'])
def login():
    """User login"""
    logger.debug('Entering login route')
    
    if current_user.is_authenticated:
        logger.debug(f'User {current_user.id} already authenticated, redirecting to dashboard')
        return redirect(url_for('dashboard.dashboard'))
    
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        logger.info(f'Login attempt for username: {username}')
        
        conn = get_db_connection()
        user_data = conn.execute('SELECT * FROM User WHERE username = ?', (username,)).fetchone()
        conn.close()
        
        if user_data and check_password_hash(user_data['password_hash'], password):
            user = User(user_data['id'], user_data['username'], user_data['password_hash'])
            login_user(user)
            logger.info(f'User {username} (id={user.id}) logged in successfully')
            flash('Logged in successfully!', 'success')
            return redirect(url_for('dashboard.dashboard'))
        else:
            logger.warning(f'Login failed for username: {username}')
            flash('Invalid username or password.', 'error')
    
    logger.debug('Exiting login route - showing form')
    return render_template('login.html')


@bp.route('/logout')
@login_required
def logout():
    """User logout"""
    logger.debug('Entering logout route')
    logger.info(f'User {current_user.id} logging out')
    logout_user()
    flash('Logged out successfully.', 'success')
    logger.debug('Exiting logout route')
    return redirect(url_for('auth.login'))
