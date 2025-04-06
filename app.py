from flask import Flask, render_template, request, jsonify, redirect, url_for, flash
import google.generativeai as genai
import re
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from models import db, User, Update, Email, EmailCategory, Meeting
from email_utils import EmailProcessor, EmailPrioritizer, process_email
from email_reply_suggester import EmailReplySuggester
from meeting_utils import MeetingScheduler, create_calendar_event
from dotenv import load_dotenv
import os
import dateparser
import datetime

# Load environment variables
load_dotenv()

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///employee_reports.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Initialize extensions
db.init_app(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

# Initialize Gemini
api_key = os.environ.get('GEMINI_API_KEY', "AIzaSyAzD34ljTgzWdZUpbCl3iynxAqh8uy6irc")
genai.configure(api_key=api_key)
model = genai.GenerativeModel("gemini-2.0-flash")

# Initialize email utilities
email_processor = EmailProcessor(api_key)
email_prioritizer = EmailPrioritizer(api_key)
email_reply_suggester = EmailReplySuggester(api_key)

# Initialize meeting scheduler
meeting_scheduler = MeetingScheduler(api_key)

# Add context processor for template variables
@app.context_processor
def inject_now():
    return {'now': datetime.datetime.now()}

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

@app.route('/')
def home():
    if current_user.is_authenticated:
        if current_user.role == 'manager':
            return redirect(url_for('manager_dashboard'))
        else:
            return redirect(url_for('employee_dashboard'))
    return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('home'))
    
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        user = User.query.filter_by(username=username).first()
        if user and user.check_password(password):
            login_user(user)
            next_page = request.args.get('next')
            flash('Login successful', 'success')
            return redirect(next_page or url_for('home'))
        flash('Invalid username or password', 'error')
    
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('home'))
    
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        role = request.form.get('role')
        
        if User.query.filter_by(username=username).first():
            flash('Username already exists')
            return redirect(url_for('register'))
        
        if User.query.filter_by(email=email).first():
            flash('Email already exists')
            return redirect(url_for('register'))
        
        user = User(username=username, email=email, role=role)
        user.set_password(password)
        
        db.session.add(user)
        db.session.commit()
        
        flash('Registration successful')
        return redirect(url_for('login'))
    
    return render_template('register.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('home'))

@app.route('/employee/dashboard')
@login_required
def employee_dashboard():
    if current_user.role != 'employee':
        flash('Access denied')
        return redirect(url_for('home'))
    
    updates = Update.query.filter_by(user_id=current_user.id).order_by(Update.date_posted.desc()).all()
    unread_emails = Email.query.filter_by(user_id=current_user.id, is_read=False).count()
    urgent_emails = Email.query.filter_by(user_id=current_user.id, is_urgent=True).count()
    
    return render_template('employee_dashboard.html', updates=updates, 
                          unread_emails=unread_emails, urgent_emails=urgent_emails)

@app.route('/employee/submit_update', methods=['GET', 'POST'])
@login_required
def submit_update():
    if current_user.role != 'employee':
        flash('Access denied')
        return redirect(url_for('home'))
    
    if request.method == 'POST':
        content = request.form.get('content')
        if content:
            update = Update(content=content, user_id=current_user.id)
            db.session.add(update)
            db.session.commit()
            flash('Update submitted successfully')
            return redirect(url_for('employee_dashboard'))
    
    return render_template('submit_update.html')

@app.route('/manager/dashboard')
@login_required
def manager_dashboard():
    if current_user.role != 'manager':
        flash('Access denied')
        return redirect(url_for('home'))
    
    employees = User.query.filter_by(role='employee').all()
    unread_emails = Email.query.filter_by(user_id=current_user.id, is_read=False).count()
    urgent_emails = Email.query.filter_by(user_id=current_user.id, is_urgent=True).count()
    
    return render_template('manager_dashboard.html', employees=employees,
                          unread_emails=unread_emails, urgent_emails=urgent_emails)

@app.route('/manager/employee/<int:employee_id>')
@login_required
def employee_updates(employee_id):
    if current_user.role != 'manager':
        flash('Access denied')
        return redirect(url_for('home'))
    
    employee = User.query.get_or_404(employee_id)
    updates = Update.query.filter_by(user_id=employee_id).order_by(Update.date_posted.desc()).all()
    return render_template('employee_updates.html', employee=employee, updates=updates)

@app.route('/generate_report', methods=['POST'])
@login_required
def generate_report():
    if request.is_json:
        updates = request.json.get('updates', [])
    else:
        employee_id = request.form.get('employee_id')
        employee = User.query.get_or_404(employee_id)
        updates = [update.content for update in Update.query.filter_by(user_id=employee_id).all()]
    
    if not updates:
        return jsonify({'error': 'No updates provided'}), 400

    raw_text = "\n".join(updates)

    prompt = (
        "Analyze the following employee work updates:\n"
        f"{raw_text}\n\n"
        "1. Provide a brief summary.\n"
        "2. Identify all possible visualizations (bar, pie, line, etc.) based on numerical and temporal data.\n"
        "3. Create as many graphs as you can.\n"
        "4. Every graph must have more than one component; if there are graphs with only one component, merge them.\n"
        "5. You should always include a pie chart which shows the total distribution of effort into various fields.\n"
        "6. Output a JSON in this format ONLY (using double quotes):\n\n"
        '{\n'
        '  "summary": "...",\n'
        '  "charts": [\n'
        '    {\n'
        '      "title": "...",\n'
        '      "type": "bar" | "pie" | "line",\n'
        '      "labels": [...],\n'
        '      "data": [...]\n'
        '    }\n'
        '  ]\n'
        '}\n\n'
        "Only return the JSON object. Do not add explanations or markdown. Use 'line' chart if updates span over dates, days, or show a trend."
    )

    while True:
        try:
            response_text = model.generate_content(prompt).text.strip()

            import re, json

            match = re.search(r'\{[\s\S]+\}', response_text)
            if not match:
                return jsonify({'error': 'Failed to parse Gemini response', 'raw': response_text}), 500

            json_str = match.group()
            json_str = json_str.replace("'", '"')

            parsed = json.loads(json_str)
            return jsonify(parsed)

        except Exception as e:
            pass

@app.route('/manager/generate_report/<int:employee_id>')
@login_required
def show_report_page(employee_id):
    if current_user.role != 'manager':
        flash('Access denied')
        return redirect(url_for('home'))
    
    employee = User.query.get_or_404(employee_id)
    updates = [update.content for update in Update.query.filter_by(user_id=employee_id).all()]
    return render_template('report.html', employee=employee, updates=updates)

# Email functionality routes
@app.route('/mailbox')
@login_required
def mailbox():
    """View all emails in the mailbox."""
    emails = Email.query.filter_by(user_id=current_user.id).order_by(Email.date_received.desc()).all()
    return render_template('mailbox.html', emails=emails)

@app.route('/email/<int:email_id>')
@login_required
def view_email_detail(email_id):
    """View a specific email."""
    email = Email.query.get_or_404(email_id)
    
    # Check if the email belongs to the current user
    if email.user_id != current_user.id:
        flash('Access denied')
        return redirect(url_for('mailbox'))
    
    # Get all emails for prev/next navigation
    all_emails = Email.query.filter_by(user_id=current_user.id).order_by(Email.date_received.desc()).all()
    
    # Find current email's position
    email_ids = [e.id for e in all_emails]
    current_index = email_ids.index(email_id) if email_id in email_ids else -1
    
    prev_email_id = email_ids[current_index - 1] if current_index > 0 else None
    next_email_id = email_ids[current_index + 1] if current_index < len(email_ids) - 1 else None
    
    # Mark email as read
    if not email.is_read:
        email.is_read = True
        db.session.commit()
    
    return render_template('email_detail.html', email=email, 
                          prev_email_id=prev_email_id, next_email_id=next_email_id)

@app.route('/email/toggle_read/<int:email_id>', methods=['POST'])
@login_required
def toggle_read_status(email_id):
    """Toggle the read status of an email."""
    email = Email.query.get_or_404(email_id)
    
    # Check if the email belongs to the current user
    if email.user_id != current_user.id:
        return jsonify({'success': False, 'error': 'Access denied'}), 403
    
    email.is_read = not email.is_read
    db.session.commit()
    
    return jsonify({'success': True, 'is_read': email.is_read})

@app.route('/email/toggle_urgent/<int:email_id>', methods=['POST'])
@login_required
def toggle_urgent_status(email_id):
    """Toggle the urgent status of an email."""
    email = Email.query.get_or_404(email_id)
    
    # Check if the email belongs to the current user
    if email.user_id != current_user.id:
        return jsonify({'success': False, 'error': 'Access denied'}), 403
    
    email.is_urgent = not email.is_urgent
    db.session.commit()
    
    return jsonify({'success': True, 'is_urgent': email.is_urgent})

@app.route('/high_priority_emails')
@login_required
def high_priority_emails():
    """View all high priority emails."""
    emails = Email.query.filter_by(user_id=current_user.id, is_urgent=True).order_by(Email.date_received.desc()).all()
    return render_template('high_priority_emails.html', emails=emails)

@app.route('/email_categories')
@login_required
def email_categories():
    """View all email categories."""
    # Get all categories with emails for this user
    categories = EmailCategory.query.all()
    
    # For each category, count the number of emails and urgent emails
    for category in categories:
        # Filter emails for current user
        category.emails = [e for e in category.emails if e.user_id == current_user.id]
        category.urgent_count = sum(1 for e in category.emails if e.is_urgent)
    
    # Filter out categories with no emails for this user
    categories = [c for c in categories if c.emails]
    
    return render_template('email_categories.html', categories=categories)

@app.route('/category/<int:category_id>')
@login_required
def view_category(category_id):
    """View all emails in a specific category."""
    category = EmailCategory.query.get_or_404(category_id)
    emails = Email.query.filter_by(user_id=current_user.id, category_id=category_id).order_by(Email.date_received.desc()).all()
    return render_template('mailbox.html', emails=emails, category=category)

@app.route('/compose_email', methods=['GET', 'POST'])
@login_required
def compose_email():
    """Compose a new email."""
    if request.method == 'POST':
        recipient_id = request.form.get('recipient')
        subject = request.form.get('subject')
        content = request.form.get('content')
        is_urgent = 'is_urgent' in request.form
        category_id = request.form.get('category_id') or None
        use_ai = 'use_ai' in request.form
        
        recipient = User.query.get_or_404(recipient_id)
        
        if use_ai:
            # Process with AI
            email = process_email(
                subject=subject,
                content=content,
                sender=current_user.username,
                user_id=recipient.id
            )
            flash('Email sent and processed with AI')
        else:
            # Create without AI processing
            email = Email(
                subject=subject,
                content=content,
                sender=current_user.username,
                is_urgent=is_urgent,
                category_id=category_id,
                user_id=recipient.id
            )
            db.session.add(email)
            db.session.commit()
            flash('Email sent')
        
        return redirect(url_for('mailbox'))
    
    # Get all users and categories for the form
    users = User.query.all()
    categories = EmailCategory.query.all()
    
    return render_template('compose_email.html', users=users, categories=categories)

@app.route('/email_summary')
@login_required
def email_summary():
    """Generate a summary of high priority emails."""
    high_priority_emails = Email.query.filter_by(user_id=current_user.id, is_urgent=True).all()
    
    if not high_priority_emails:
        return jsonify({'summary': "No high priority emails found."})
    
    # Prepare email data for the prompt
    email_data = []
    for email in high_priority_emails:
        email_data.append(f"Subject: {email.subject}\nContent: {email.content}")
    
    email_text = "\n\n===\n\n".join(email_data)
    
    prompt = f"""
    Generate a comprehensive summary of the following high priority emails.
    Group related topics together, highlight urgent action items, and provide a strategic overview.
    Format your response using markdown.
    
    HIGH PRIORITY EMAILS:
    {email_text}
    """
    
    try:
        response = model.generate_content(prompt)
        summary = response.text
        return jsonify({'summary': summary})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/process_email', methods=['POST'])
def api_process_email():
    """API endpoint to process an email."""
    if not request.is_json:
        return jsonify({'error': 'Request must be JSON'}), 400
    
    data = request.json
    subject = data.get('subject')
    content = data.get('content')
    sender = data.get('sender')
    recipient_id = data.get('recipient_id')
    
    if not all([subject, content, sender, recipient_id]):
        return jsonify({'error': 'Missing required fields'}), 400
    
    try:
        email = process_email(
            subject=subject,
            content=content,
            sender=sender,
            user_id=recipient_id
        )
        
        return jsonify({
            'id': email.id,
            'subject': email.subject,
            'is_urgent': email.is_urgent,
            'category': email.category_rel.name if email.category_rel else 'Uncategorized',
            'summary': email.summary
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# New route for email reply suggestions
@app.route('/suggest_reply/<int:email_id>', methods=['GET'])
@login_required
def suggest_reply(email_id):
    """Get suggested reply for an email."""
    email = Email.query.get_or_404(email_id)
    
    # Check if the email belongs to the current user
    if email.user_id != current_user.id:
        return jsonify({'success': False, 'error': 'Access denied'}), 403
    
    try:
        # Process the email with the reply suggester
        result = email_reply_suggester.process_email(email.content)
        
        return jsonify({
            'success': True,
            'intent': result['intent'],
            'topics': result['topics'],
            'response': result['response']
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/reply_to_email/<int:email_id>', methods=['GET', 'POST'])
@login_required
def reply_to_email(email_id):
    """Reply to an email."""
    email = Email.query.get_or_404(email_id)
    
    # Check if the email belongs to the current user
    if email.user_id != current_user.id:
        flash('Access denied')
        return redirect(url_for('mailbox'))
    
    if request.method == 'POST':
        content = request.form.get('content')
        subject = f"Re: {email.subject}"
        use_ai = 'use_ai' in request.form
        
        # Create new email as reply
        reply_email = Email(
            subject=subject,
            content=content,
            sender=current_user.username,
            user_id=User.query.filter_by(username=email.sender).first().id,
            is_urgent=email.is_urgent,
            category_id=email.category_id
        )
        
        db.session.add(reply_email)
        db.session.commit()
        
        flash('Reply sent')
        return redirect(url_for('mailbox'))
    
    # Get suggested reply
    suggested_reply = ""
    try:
        result = email_reply_suggester.process_email(email.content)
        suggested_reply = result['response']
    except Exception as e:
        flash(f"Could not generate suggested reply: {str(e)}")
    
    return render_template('reply_email.html', email=email, suggested_reply=suggested_reply)

# Meeting Scheduler Routes
@app.route('/meeting_scheduler')
@login_required
def meeting_scheduler_page():
    """View the meeting scheduler page."""
    # Get user's meetings - both created by them and ones they're attending
    created_meetings = Meeting.query.filter_by(creator_id=current_user.id).all()
    attending_meetings = Meeting.query.filter(Meeting.attendees.any(id=current_user.id)).all()
    
    # Combine and sort by date_time (newest first)
    all_meetings = created_meetings + attending_meetings
    all_meetings = sorted(all_meetings, key=lambda x: x.date_time, reverse=True)
    
    # Remove duplicates (meetings both created by and attended by the user)
    unique_meetings = []
    meeting_ids = set()
    for meeting in all_meetings:
        if meeting.id not in meeting_ids:
            unique_meetings.append(meeting)
            meeting_ids.add(meeting.id)
    
    return render_template('meet_scheduler.html', meetings=unique_meetings)

@app.route('/schedule_meeting', methods=['POST'])
@login_required
def schedule_meeting():
    """Schedule a meeting with natural language."""
    query = request.form.get('query')
    
    if not query:
        return jsonify({'error': 'No query provided'}), 400
    
    # Parse meeting details
    meeting_details = meeting_scheduler.parse_meeting_details(query)
    if not meeting_details:
        return jsonify({'error': 'Failed to parse meeting details'}), 400
    
    # Map attendees to users
    users, unmapped_attendees = meeting_scheduler.map_attendees_to_users(meeting_details['attendees'])
    
    # Get email addresses for Google Calendar
    email_addresses = [user.email for user in users]
    
    # Add the current user as an attendee if not already included
    current_user_email = current_user.email
    if current_user_email not in email_addresses:
        email_addresses.append(current_user_email)
    
    # Update meeting details with mapped emails
    meeting_details['attendees'] = email_addresses
    
    # Create calendar event
    result = create_calendar_event(meeting_details, current_user.id)
    if not result:
        return jsonify({'error': 'Failed to create calendar event'}), 500
    
    # Return the response
    response = {
        'success': True,
        'meeting_details': meeting_details,
        'meet_link': result['meet_link']
    }
    
    # Add warning about unmapped attendees if any
    if unmapped_attendees:
        response['unmapped_attendees'] = unmapped_attendees
    
    return jsonify(response)

@app.route('/meetings')
@login_required
def user_meetings():
    """View all meetings for the current user."""
    # Get user's meetings - both created by them and ones they're attending
    created_meetings = Meeting.query.filter_by(creator_id=current_user.id).all()
    attending_meetings = Meeting.query.filter(Meeting.attendees.any(id=current_user.id)).all()
    
    # Combine and sort by date_time (newest first)
    all_meetings = created_meetings + attending_meetings
    all_meetings = sorted(all_meetings, key=lambda x: x.date_time, reverse=True)
    
    # Remove duplicates (meetings both created by and attended by the user)
    unique_meetings = []
    meeting_ids = set()
    for meeting in all_meetings:
        if meeting.id not in meeting_ids:
            unique_meetings.append(meeting)
            meeting_ids.add(meeting.id)
    
    # Get current datetime for comparing with meeting dates
    now = datetime.datetime.now()
    
    return render_template('meetings.html', meetings=unique_meetings, now=now)

@app.route('/meeting/<int:meeting_id>')
@login_required
def view_meeting(meeting_id):
    """View a specific meeting."""
    meeting = Meeting.query.get_or_404(meeting_id)
    
    # Check if the user is the creator or an attendee
    if meeting.creator_id != current_user.id and current_user not in meeting.attendees:
        flash('Access denied')
        return redirect(url_for('user_meetings'))
    
    return render_template('meeting_detail.html', meeting=meeting)

with app.app_context():
    db.create_all()

if __name__ == '__main__':
    app.run(debug=True)
