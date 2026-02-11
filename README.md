# MiniLMS

A minimal Learning Management System (LMS) built with Flask that provides basic course presentation functionality with access control through custom codes sent via email.

## Features

- **Simple Course Management**: Create, edit, and delete courses through an admin panel
- **Access Code System**: Students request access codes via email to unlock courses
- **Email Integration**: Automatically send access codes to students (optional - codes can be displayed on screen if email is not configured)
- **Clean Interface**: Minimalist, responsive design for easy navigation
- **SQLite Database**: Lightweight database for storing courses and access codes

## Installation

1. Clone the repository:
```bash
git clone https://github.com/andrejli/MiniLMS.git
cd MiniLMS
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. (Optional) Configure email settings:
```bash
cp .env.example .env
# Edit .env with your email settings
```

4. Run the application:
```bash
python app.py
```

5. Open your browser and navigate to `http://localhost:5000`

## Usage

### For Administrators

1. Navigate to `/admin` to access the admin panel
2. Create new courses with title, description, and content
3. View generated access codes for each course
4. Edit or delete existing courses

### For Students

1. Browse available courses on the homepage
2. Click "Request Access" to request an access code
3. Enter your email address to receive the code
4. Use the access code to unlock and view the course content

## Configuration

The application can be configured using environment variables in a `.env` file:

- `SECRET_KEY`: Flask secret key for sessions (required for production)
- `ADMIN_PASSWORD`: Password for admin panel access (default: admin123)
- `MAIL_SERVER`: SMTP server address (default: smtp.gmail.com)
- `MAIL_PORT`: SMTP port (default: 587)
- `MAIL_USE_TLS`: Use TLS encryption (default: True)
- `MAIL_USERNAME`: Email address for sending codes
- `MAIL_PASSWORD`: Email password or app-specific password (for Gmail, use app-specific password)

**Note**: If email is not configured, access codes will be displayed on the screen instead of being sent via email.

## Security Features

- **Admin Authentication**: Password-based access to admin panel (configurable via ADMIN_PASSWORD)
- **XSS Protection**: HTML content sanitization to prevent cross-site scripting attacks
- **Session-based Access Control**: Course access managed through Flask sessions
- **Single-use Access Codes**: Each access code can only be used once

## Database

The application uses SQLite database (`minilms.db`) which is created automatically on first run. The database includes:

- **Course**: Stores course information (title, description, content)
- **AccessCode**: Stores generated access codes with email and usage status

## Technology Stack

- **Backend**: Flask (Python web framework)
- **Database**: SQLAlchemy with SQLite
- **Frontend**: HTML5, CSS3 (responsive design)
- **Email**: Python smtplib

## License

See LICENSE file for details.
