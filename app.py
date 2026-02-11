import os
import secrets
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_sqlalchemy import SQLAlchemy
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import smtplib

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///minilms.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Email configuration (optional - can be set via environment variables)
app.config['MAIL_SERVER'] = os.environ.get('MAIL_SERVER', 'smtp.gmail.com')
app.config['MAIL_PORT'] = int(os.environ.get('MAIL_PORT', 587))
app.config['MAIL_USE_TLS'] = os.environ.get('MAIL_USE_TLS', 'True') == 'True'
app.config['MAIL_USERNAME'] = os.environ.get('MAIL_USERNAME', '')
app.config['MAIL_PASSWORD'] = os.environ.get('MAIL_PASSWORD', '')

db = SQLAlchemy(app)

# Database Models
class Course(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=False)
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    access_codes = db.relationship('AccessCode', backref='course', lazy=True, cascade='all, delete-orphan')

    def __repr__(self):
        return f'<Course {self.title}>'

class AccessCode(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(20), unique=True, nullable=False)
    course_id = db.Column(db.Integer, db.ForeignKey('course.id'), nullable=False)
    email = db.Column(db.String(120), nullable=False)
    is_used = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    used_at = db.Column(db.DateTime, nullable=True)

    def __repr__(self):
        return f'<AccessCode {self.code}>'

# Helper functions
def generate_access_code():
    """Generate a random 12-character access code"""
    return secrets.token_urlsafe(9)[:12].upper()

def send_access_code_email(email, code, course_title):
    """Send access code via email"""
    if not app.config['MAIL_USERNAME'] or not app.config['MAIL_PASSWORD']:
        print(f"Email not configured. Access code for {email}: {code}")
        return False
    
    try:
        msg = MIMEMultipart()
        msg['From'] = app.config['MAIL_USERNAME']
        msg['To'] = email
        msg['Subject'] = f'Your Access Code for {course_title}'
        
        body = f"""
Hello,

Your access code for the course "{course_title}" is: {code}

Please use this code to access the course at: {request.url_root}

Best regards,
MiniLMS Team
"""
        msg.attach(MIMEText(body, 'plain'))
        
        server = smtplib.SMTP(app.config['MAIL_SERVER'], app.config['MAIL_PORT'])
        server.starttls()
        server.login(app.config['MAIL_USERNAME'], app.config['MAIL_PASSWORD'])
        server.send_message(msg)
        server.quit()
        return True
    except Exception as e:
        print(f"Failed to send email: {e}")
        return False

# Routes
@app.route('/')
def index():
    """Homepage showing all available courses"""
    courses = Course.query.all()
    return render_template('index.html', courses=courses)

@app.route('/course/<int:course_id>')
def course_detail(course_id):
    """Show course details if user has valid access code"""
    course = Course.query.get_or_404(course_id)
    
    # Check if user has access via session
    accessed_courses = session.get('accessed_courses', [])
    if course_id in accessed_courses:
        return render_template('course_detail.html', course=course)
    
    # User needs to enter access code
    return redirect(url_for('enter_code', course_id=course_id))

@app.route('/course/<int:course_id>/enter-code', methods=['GET', 'POST'])
def enter_code(course_id):
    """Page for entering access code"""
    course = Course.query.get_or_404(course_id)
    
    if request.method == 'POST':
        code = request.form.get('code', '').strip().upper()
        
        # Validate access code
        access_code = AccessCode.query.filter_by(
            code=code,
            course_id=course_id,
            is_used=False
        ).first()
        
        if access_code:
            # Mark code as used
            access_code.is_used = True
            access_code.used_at = datetime.utcnow()
            db.session.commit()
            
            # Grant access via session
            accessed_courses = session.get('accessed_courses', [])
            if course_id not in accessed_courses:
                accessed_courses.append(course_id)
                session['accessed_courses'] = accessed_courses
            
            flash('Access granted! Welcome to the course.', 'success')
            return redirect(url_for('course_detail', course_id=course_id))
        else:
            flash('Invalid or already used access code.', 'error')
    
    return render_template('enter_code.html', course=course)

@app.route('/request-access/<int:course_id>', methods=['GET', 'POST'])
def request_access(course_id):
    """Request access code for a course"""
    course = Course.query.get_or_404(course_id)
    
    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        
        if not email:
            flash('Please provide your email address.', 'error')
        else:
            # Generate and save access code
            code = generate_access_code()
            access_code = AccessCode(
                code=code,
                course_id=course_id,
                email=email
            )
            db.session.add(access_code)
            db.session.commit()
            
            # Send email (or print if email not configured)
            if send_access_code_email(email, code, course.title):
                flash('Access code has been sent to your email!', 'success')
            else:
                flash(f'Email not configured. Your access code is: {code}', 'info')
            
            return redirect(url_for('enter_code', course_id=course_id))
    
    return render_template('request_access.html', course=course)

# Admin routes (simplified - no authentication for minimal LMS)
@app.route('/admin')
def admin():
    """Simple admin panel to manage courses"""
    courses = Course.query.all()
    return render_template('admin.html', courses=courses)

@app.route('/admin/course/new', methods=['GET', 'POST'])
def new_course():
    """Create a new course"""
    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        description = request.form.get('description', '').strip()
        content = request.form.get('content', '').strip()
        
        if title and description and content:
            course = Course(title=title, description=description, content=content)
            db.session.add(course)
            db.session.commit()
            flash('Course created successfully!', 'success')
            return redirect(url_for('admin'))
        else:
            flash('All fields are required.', 'error')
    
    return render_template('new_course.html')

@app.route('/admin/course/<int:course_id>/edit', methods=['GET', 'POST'])
def edit_course(course_id):
    """Edit an existing course"""
    course = Course.query.get_or_404(course_id)
    
    if request.method == 'POST':
        course.title = request.form.get('title', '').strip()
        course.description = request.form.get('description', '').strip()
        course.content = request.form.get('content', '').strip()
        
        if course.title and course.description and course.content:
            db.session.commit()
            flash('Course updated successfully!', 'success')
            return redirect(url_for('admin'))
        else:
            flash('All fields are required.', 'error')
    
    return render_template('edit_course.html', course=course)

@app.route('/admin/course/<int:course_id>/delete', methods=['POST'])
def delete_course(course_id):
    """Delete a course"""
    course = Course.query.get_or_404(course_id)
    db.session.delete(course)
    db.session.commit()
    flash('Course deleted successfully!', 'success')
    return redirect(url_for('admin'))

@app.route('/admin/course/<int:course_id>/codes')
def view_access_codes(course_id):
    """View access codes for a course"""
    course = Course.query.get_or_404(course_id)
    access_codes = AccessCode.query.filter_by(course_id=course_id).order_by(AccessCode.created_at.desc()).all()
    return render_template('access_codes.html', course=course, access_codes=access_codes)

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)
