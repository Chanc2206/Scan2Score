"""
Scan2Score Configuration Settings
Environment variables and application settings
"""

import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    """Base configuration class"""
    
    # Flask Settings
    SECRET_KEY = os.getenv('SECRET_KEY', 'scan2score-secret-key-2024')
    FLASK_ENV = os.getenv('FLASK_ENV', 'development')
    DEBUG = os.getenv('DEBUG', 'True').lower() == 'true'
    
    # Database Settings
    MONGODB_URI = os.getenv('MONGODB_URI', 'mongodb://localhost:27017/scan2score')
    DB_NAME = os.getenv('DB_NAME', 'scan2score')
    
    # AI API Keys
    ANTHROPIC_API_KEY = os.getenv('ANTHROPIC_API_KEY')
    OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
    
    # Plagiarism Detection APIs
    GPTZERO_API_KEY = os.getenv('GPTZERO_API_KEY')
    COPYLEAKS_EMAIL = os.getenv('COPYLEAKS_EMAIL')
    COPYLEAKS_API_KEY = os.getenv('COPYLEAKS_API_KEY')
    
    # File Upload Settings
    UPLOAD_FOLDER = os.getenv('UPLOAD_FOLDER', 'uploads')
    MAX_CONTENT_LENGTH = int(os.getenv('MAX_CONTENT_LENGTH', 16 * 1024 * 1024))  # 16MB
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'pdf', 'docx', 'doc'}
    
    # OCR Settings
    OCR_LANGUAGES = ['en', 'ch']  # English and Chinese
    OCR_CONFIDENCE_THRESHOLD = float(os.getenv('OCR_CONFIDENCE_THRESHOLD', 0.6))
    
    # AI Evaluation Settings
    CLAUDE_MODEL = os.getenv('CLAUDE_MODEL', 'claude-3-sonnet-20240229')
    GPT_MODEL = os.getenv('GPT_MODEL', 'gpt-4-turbo-preview')
    MAX_TOKENS = int(os.getenv('MAX_TOKENS', 4000))
    TEMPERATURE = float(os.getenv('TEMPERATURE', 0.3))
    
    # Grading Settings
    DEFAULT_SCORING_SCALE = 100
    MIN_SCORE = 0
    MAX_SCORE = 100
    
    # Security Settings
    JWT_EXPIRATION_HOURS = int(os.getenv('JWT_EXPIRATION_HOURS', 24))
    BCRYPT_ROUNDS = int(os.getenv('BCRYPT_ROUNDS', 12))
    
    # Logging
    LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
    LOG_FILE = os.getenv('LOG_FILE', 'scan2score.log')

class DevelopmentConfig(Config):
    """Development configuration"""
    DEBUG = True
    MONGODB_URI = os.getenv('DEV_MONGODB_URI', 'mongodb://localhost:27017/scan2score_dev')

class ProductionConfig(Config):
    """Production configuration"""
    DEBUG = False
    MONGODB_URI = os.getenv('PROD_MONGODB_URI')

class TestingConfig(Config):
    """Testing configuration"""
    TESTING = True
    MONGODB_URI = 'mongodb://localhost:27017/scan2score_test'

# Configuration mapping
config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    'default': DevelopmentConfig
}