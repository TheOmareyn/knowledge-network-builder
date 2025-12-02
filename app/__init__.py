"""
Knowledge Network Builder - Flask Application Factory
"""

import os
from flask import Flask
from flask_login import LoginManager
from dotenv import load_dotenv

from db import init_db

# Initialize Flask-Login
login_manager = LoginManager()

def create_app():
    """Application factory pattern"""
    
    # Load environment variables
    load_dotenv()
    
    # Create Flask app
    app = Flask(__name__, 
                template_folder='../templates',
                static_folder='../static')
    
    # App configuration
    app.secret_key = os.getenv('SECRET_KEY', 'your-secret-key-change-this')
    app.config['UPLOAD_FOLDER'] = 'uploads'
    app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size
    app.config['ALLOWED_EXTENSIONS'] = {'pdf'}
    
    # Gemini API configuration
    app.config['GEMINI_API_KEY'] = os.getenv('GEMINI_API_KEY')
    app.config['GEMINI_API_URL'] = 'https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-lite:generateContent'
    
    # Ensure upload directory exists
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    
    # Initialize Flask-Login
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'
    
    # Import and register user loader
    from app.models.user import load_user
    login_manager.user_loader(load_user)
    
    # Register blueprints
    from app.routes import auth, dashboard, document, network, global_network, admin
    app.register_blueprint(auth.bp)
    app.register_blueprint(dashboard.bp)
    app.register_blueprint(document.bp)
    app.register_blueprint(network.bp)
    app.register_blueprint(global_network.bp)
    app.register_blueprint(admin.admin_bp)
    
    # Initialize database
    with app.app_context():
        init_db()
    
    return app
