# Groupdoo - Flask Group Management & Authentication System

A Flask web application with user authentication and group management using SQLAlchemy and MariaDB.

## Features

### User Authentication
- User registration with email validation
- Secure password hashing with Werkzeug
- User login/logout functionality
- Session management with Flask-Login
- Protected routes requiring authentication

### Group Management
- **Create Groups**: Users can create groups with name, description, and type
- **Group Types**: Meetup, Online, or Playdate
- **Public/Private Groups**: Control group visibility
- **Invite System**: Owners can invite other users to their groups
- **On-Site Notifications**: Real-time invitation badges in navigation
- **Accept/Reject Invitations**: Users can manage their invitations
- **Member Management**: View members, leave groups
- **Browse Groups**: Explore public groups

### UI Features
- Bootstrap 5 responsive design
- Bootstrap Icons integration
- Real-time notification badges
- Intuitive dashboard with group sections
- Flash messages for user feedback
- MariaDB database backend
- **Internationalization**: Support for 6 languages (English, French, Spanish, German, Dutch, Italian)

## Prerequisites

- Python 3.8 or higher
- MariaDB or MySQL server running
- pip (Python package manager)

## Installation

1. **Clone or navigate to the project directory:**
   ```bash
   cd C:\groupdoo
   ```

2. **Create a virtual environment:**
   ```bash
   python -m venv .venv
   ```

3. **Activate the virtual environment:**
   ```bash
   .venv\Scripts\activate
   ```

4. **Install required packages:**
   ```bash
   pip install -r requirements.txt
   ```

5. **Set up MariaDB:**
   - Make sure MariaDB is running
   - Create a database named `groupdoo_db`:
   ```sql
   CREATE DATABASE groupdoo_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
   ```

6. **Configure database connection:**
   - Edit `config.py` and update the database URI with your credentials:
   ```python
   SQLALCHEMY_DATABASE_URI = 'mysql+pymysql://username:password@localhost:3306/groupdoo_db'
   ```
   - Or set the `DATABASE_URL` environment variable:
   ```bash
   $env:DATABASE_URL = "mysql+pymysql://username:password@localhost:3306/groupdoo_db"
   ```

7. **Initialize the database:**
   ```bash
   flask init-db
   ```

## Running the Application

1. **Start the Flask development server:**
   ```bash
   python app.py
   ```

2. **Access the application:**
   - Open your browser and navigate to: `http://127.0.0.1:5000`

## Usage

### Register a New User
1. Click "Register" in the navigation bar
2. Fill in username, email, and password
3. Submit the form
4. You'll be redirected to login

### Login
1. Click "Login" in the navigation bar
2. Enter your username and password
3. Optionally check "Remember Me" to stay logged in
4. Submit the form
5. You'll be redirected to the dashboard

### Access Protected Routes
- The dashboard route (`/dashboard`) is protected
- Users must be logged in to access it
- Unauthenticated users will be redirected to login

## Project Structure

```
groupdoo/
├── app.py              # Main Flask application
├── config.py           # Configuration settings
├── models.py           # Database models (User)
├── forms.py            # WTForms for login/registration
├── requirements.txt    # Python dependencies
├── templates/          # HTML templates
│   ├── base.html       # Base template
│   ├── index.html      # Home page
│   ├── login.html      # Login page
│   ├── register.html   # Registration page
│   └── dashboard.html  # Protected dashboard
└── static/             # Static files (CSS, JS, images)
```

## User Model

The User model includes:
- `id`: Primary key
- `username`: Unique username (3-80 characters)
- `email`: Unique email address
- `password_hash`: Hashed password (never stored in plain text)
- `created_at`: Account creation timestamp
- `updated_at`: Last update timestamp

## Security Features

- Passwords are hashed using Werkzeug's security utilities
- CSRF protection enabled via Flask-WTF
- Session-based authentication with Flask-Login
- Protected routes using `@login_required` decorator
- Input validation on all forms

## Security Configuration

The app supports additional security settings via environment variables:

- `SECRET_KEY`: Set a strong, random value in production.
- `SESSION_COOKIE_SECURE`: Set to `true` when running over HTTPS.
- `SESSION_COOKIE_SAMESITE`: Default `Lax`.
- `REMEMBER_COOKIE_SECURE`: Set to `true` when running over HTTPS.
- `PERMANENT_SESSION_LIFETIME`: Session lifetime in seconds (default `3600`).
- `SECURITY_HEADERS_ENABLE`: Enable/disable basic security headers (default `true`).
- `SECURITY_HEADERS_HSTS`: Set to `true` when running over HTTPS.
- `LOCKOUT_MAX_ATTEMPTS`: Number of failed attempts before lockout (default `5`).
- `LOCKOUT_MINUTES`: Lockout duration in minutes (default `15`).

Rate limiting is enabled using `Flask-Limiter` with default limits and tighter limits on login/registration/account deletion.

## Environment Variables

### Flask Server Configuration
- `FLASK_HOST`: Host address to bind to (default: `127.0.0.1`)
- `FLASK_PORT`: Port to listen on (default: `5000`)
- `FLASK_DEBUG`: Enable debug mode (default: `true`)

### Internationalization
- `BABEL_DEFAULT_LOCALE`: Default language (default: `en`)
  - Available: `en` (English), `fr` (French), `es` (Spanish), `de` (German), `nl` (Dutch), `it` (Italian)

### Email
- `EMAIL_BACKEND`: `console` or `smtp` (default: `console`)
- `EMAIL_FROM`: Sender address (default: `noreply@groupdoo.local`)
- `EMAIL_SUBJECT_PREFIX`: Subject prefix (default: `[Groupdoo] `)
- `EMAIL_DEBUG_TO`: Default recipient for testing
- `EMAIL_FAIL_SILENTLY`: `true` to suppress send errors (default: `false`)
- `EMAIL_VERIFY_TOKEN_HOURS`: Verification link lifetime in hours (default: `24`)
- `EMAIL_PASSWORD_RESET_HOURS`: Password reset link lifetime in hours (default: `2`)
- `EMAIL_SMTP_HOST`: SMTP host (default: `localhost`)
- `EMAIL_SMTP_PORT`: SMTP port (default: `587`)
- `EMAIL_SMTP_USERNAME`: SMTP username
- `EMAIL_SMTP_PASSWORD`: SMTP password
- `EMAIL_SMTP_USE_TLS`: `true` to use STARTTLS (default: `true`)
- `EMAIL_SMTP_USE_SSL`: `true` to use SSL (default: `false`)
- `EMAIL_SMTP_TIMEOUT`: SMTP timeout in seconds (default: `10`)

### Security and Database
- `SECRET_KEY`: Flask secret key for sessions (set in production!)
- `DATABASE_URL`: Database connection string

## Email System

Groupdoo includes a configurable email system ready to plug into registration/login flows later. The default backend is `console` (prints emails to stdout). Switch to `smtp` when you have credentials.

New auth flows:
- Email verification is required before login.
- Password reset is available at `/password-reset`.

Test the configuration using the provided harness:

```powershell
$env:EMAIL_BACKEND = "console"
$env:EMAIL_DEBUG_TO = "you@example.com"
python email_test.py
```

SMTP example:

```powershell
$env:EMAIL_BACKEND = "smtp"
$env:EMAIL_SMTP_HOST = "smtp.example.com"
$env:EMAIL_SMTP_PORT = "587"
$env:EMAIL_SMTP_USERNAME = "user"
$env:EMAIL_SMTP_PASSWORD = "pass"
$env:EMAIL_FROM = "noreply@example.com"
$env:EMAIL_DEBUG_TO = "you@example.com"
python email_test.py
```

## Internationalization (i18n)

Groupdoo supports **6 languages**:
- 🇬🇧 English (en) - Default
- 🇫🇷 French (fr)
- 🇪🇸 Spanish (es)
- 🇩🇪 German (de)
- 🇳🇱 Dutch (nl)
- 🇮🇹 Italian (it)

Users can switch languages using the globe icon (🌐) in the navigation bar. The language preference is stored in their session.

For developers working with translations, see the detailed [I18N_README.md](I18N_README.md) guide.

## Development

To make changes:
1. Modify the code as needed
2. If you change models, you may need to recreate the database:
   ```bash
   flask init-db
   ```
3. Restart the Flask server to see changes

## Troubleshooting

**Database connection errors:**
- Verify MariaDB is running
- Check credentials in `config.py`
- Ensure the database exists

**Import errors:**
- Make sure virtual environment is activated
- Reinstall requirements: `pip install -r requirements.txt`

**Template not found errors:**
- Ensure templates are in the `templates/` folder
- Check file names match the routes

## Database Backups

Use the built-in backup tool to regularly snapshot the database and restore it if needed.

Backup to JSON:
```powershell
python backup_db.py backup --output backups\groupdoo_backup.json
```

Backup to compressed JSON:
```powershell
python backup_db.py backup --output backups\groupdoo_backup.json.gz --compress
```

Restore from backup:
```powershell
python backup_db.py restore --input backups\groupdoo_backup.json
```

Dry run (safe test):
```powershell
python backup_db.py backup --output backup.json --dry-run
python backup_db.py restore --input backup.json --dry-run
```

## License

This project is provided as-is for educational purposes.
