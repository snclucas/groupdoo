import os

from dotenv import load_dotenv

load_dotenv()

class Config:
    """Application configuration"""
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-key-change-in-production'

    # Flask server configuration
    HOST = os.environ.get('FLASK_HOST', '127.0.0.1')
    PORT = int(os.environ.get('FLASK_PORT', '5000'))
    DEBUG = os.environ.get('FLASK_DEBUG', 'true').lower() == 'true'

    # Internationalization configuration
    BABEL_DEFAULT_LOCALE = os.environ.get('BABEL_DEFAULT_LOCALE', 'en')
    BABEL_TRANSLATION_DIRECTORIES = 'translations'
    LANGUAGES = {
        'en': 'English',
        'fr': 'Français',
        'es': 'Español',
        'de': 'Deutsch',
        'nl': 'Nederlands',
        'it': 'Italiano'
    }

    # Email configuration
    EMAIL_BACKEND = os.environ.get('EMAIL_BACKEND', 'console')  # console | smtp
    EMAIL_FROM = os.environ.get('EMAIL_FROM', 'noreply@groupdoo.local')
    EMAIL_SUBJECT_PREFIX = os.environ.get('EMAIL_SUBJECT_PREFIX', '[Groupdoo] ')
    EMAIL_DEBUG_TO = os.environ.get('EMAIL_DEBUG_TO', '')
    EMAIL_FAIL_SILENTLY = os.environ.get('EMAIL_FAIL_SILENTLY', 'false').lower() == 'true'
    EMAIL_VERIFY_TOKEN_HOURS = int(os.environ.get('EMAIL_VERIFY_TOKEN_HOURS', '24'))
    EMAIL_PASSWORD_RESET_HOURS = int(os.environ.get('EMAIL_PASSWORD_RESET_HOURS', '2'))

    EMAIL_SMTP_HOST = os.environ.get('EMAIL_SMTP_HOST', 'smtp-relay.brevo.com')
    EMAIL_SMTP_PORT = int(os.environ.get('EMAIL_SMTP_PORT', '587'))
    EMAIL_SMTP_USERNAME = os.environ.get('EMAIL_SMTP_USERNAME')
    EMAIL_SMTP_PASSWORD = os.environ.get('EMAIL_SMTP_PASSWORD')
    EMAIL_SMTP_USE_TLS = os.environ.get('EMAIL_SMTP_USE_TLS', 'true').lower() == 'true'
    EMAIL_SMTP_USE_SSL = os.environ.get('EMAIL_SMTP_USE_SSL', 'false').lower() == 'true'
    EMAIL_SMTP_TIMEOUT = int(os.environ.get('EMAIL_SMTP_TIMEOUT', '10'))

    # Database configuration for MariaDB
    # Build from individual components if provided, otherwise use direct URL
    _db_driver = os.environ.get('DB_DRIVER', 'mysql+pymysql')
    _db_user = os.environ.get('DB_USER', 'root')
    _db_password = os.environ.get('DB_PASSWORD', 'password')
    _db_host = os.environ.get('DB_HOST', 'localhost')
    _db_port = os.environ.get('DB_PORT', '3306')
    _db_name = os.environ.get('DB_NAME', 'groupdoo_db')

    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or \
        f'{_db_driver}://{_db_user}:{_db_password}@{_db_host}:{_db_port}/{_db_name}'

    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ECHO = False

    # Currency configuration (configurable via environment variable)
    CURRENCY_SYMBOL = os.environ.get('CURRENCY_SYMBOL', '$')  # e.g., '$', '€', '£', '¥'
    CURRENCY_CODE = os.environ.get('CURRENCY_CODE', 'USD')    # e.g., 'USD', 'EUR', 'GBP'

    # Event category configuration
    EVENT_CATEGORIES = [
        'Playdate',
        'Meal',
        'Museum visit',
        'Other'
    ]
    EVENT_CATEGORY_DEFAULT = 'Uncategorised'  # Default category when not specified

    # Event space configuration
    EVENT_SPACES = [
        'Indoor',
        'Outdoor',
        'Both'
    ]
    EVENT_SPACE_DEFAULT = 'Not specified'  # Default space when not specified

    # Group invite method configuration
    GROUP_INVITE_METHODS = [
        'website',
        'token'
    ]
    GROUP_INVITE_METHOD_LABELS = {
        'website': 'Invite via Groupdoo website',
        'token': 'External invite via one-time token'
    }
    GROUP_INVITE_METHOD_DEFAULT = 'website'

    # Session and cookie security
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = os.environ.get('SESSION_COOKIE_SAMESITE', 'Lax')
    SESSION_COOKIE_SECURE = os.environ.get('SESSION_COOKIE_SECURE', 'false').lower() == 'true'
    REMEMBER_COOKIE_HTTPONLY = True
    REMEMBER_COOKIE_SAMESITE = os.environ.get('REMEMBER_COOKIE_SAMESITE', 'Lax')
    REMEMBER_COOKIE_SECURE = os.environ.get('REMEMBER_COOKIE_SECURE', 'false').lower() == 'true'
    PERMANENT_SESSION_LIFETIME = int(os.environ.get('PERMANENT_SESSION_LIFETIME', '3600'))

    # Basic security headers
    SECURITY_HEADERS_ENABLE = os.environ.get('SECURITY_HEADERS_ENABLE', 'true').lower() == 'true'
    SECURITY_HEADERS_HSTS = os.environ.get('SECURITY_HEADERS_HSTS', 'false').lower() == 'true'

    # Account lockout
    LOCKOUT_MAX_ATTEMPTS = int(os.environ.get('LOCKOUT_MAX_ATTEMPTS', '5'))
    LOCKOUT_MINUTES = int(os.environ.get('LOCKOUT_MINUTES', '15'))

    # Audit log retention (days)
    AUDIT_LOG_RETENTION_DAYS = int(os.environ.get('AUDIT_LOG_RETENTION_DAYS', '90'))

    # GDPR Configuration
    GDPR_DATA_EXPORT_EXPIRY_DAYS = int(os.environ.get('GDPR_DATA_EXPORT_EXPIRY_DAYS', '30'))  # How long to keep exported data available
    GDPR_DOWNLOAD_TOKEN_EXPIRY_HOURS = int(os.environ.get('GDPR_DOWNLOAD_TOKEN_EXPIRY_HOURS', '24'))  # How long download token is valid
    GDPR_DELETION_CONFIRMATION_HOURS = int(os.environ.get('GDPR_DELETION_CONFIRMATION_HOURS', '24'))  # Time to confirm deletion before it happens
    GDPR_MAX_DATA_EXPORT_REQUESTS_PER_DAY = int(os.environ.get('GDPR_MAX_DATA_EXPORT_REQUESTS_PER_DAY', '3'))  # Rate limit
    GDPR_CONSENT_TYPES = [
        'marketing_emails',
        'analytics',
        'third_party_sharing'
    ]
