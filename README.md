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

- `SECRET_KEY`: Flask secret key for sessions (set in production!)
- `DATABASE_URL`: Database connection string

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
