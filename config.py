import os


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

    # Database configuration for MariaDB
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or \
        'mysql+pymysql://root:password@localhost:3306/groupdoo_db'

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

