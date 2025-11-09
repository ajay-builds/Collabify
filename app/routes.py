from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_user, logout_user, login_required, current_user
from app import db
from app.models import User, Job, Application, Notification, Conversation, Message, UserStatsView, JobStatsView, ApplicationStatsView, RecentActivityView, PopularJobsView, EmailValidationLog,validate_email
from werkzeug.security import generate_password_hash
from sqlalchemy import or_, and_, text
from functools import wraps

main = Blueprint('main', __name__)

# Admin required decorator
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or current_user.user_type != 'admin':
            flash('You need admin privileges to access this page.', 'error')
            return redirect(url_for('main.index'))
        return f(*args, **kwargs)
    return decorated_function

@main.route('/')
def index():
    return render_template('index.html')

@main.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        user_type = request.form.get('user_type')
        
        # Validate input
        if not all([username, email, password, user_type]):
            flash('All fields are required!', 'error')
            return redirect(url_for('main.register'))
        
        # Validate email format using Python validation
        if not validate_email(email):
            # Log validation attempt
            log = EmailValidationLog(
                email=email,
                is_valid=False,
                validation_message='Invalid email format',
                action_type='registration'
            )
            db.session.add(log)
            db.session.commit()
            
            flash('Invalid email format! Please enter a valid email address.', 'error')
            return redirect(url_for('main.register'))
        
        # Check if user already exists
        existing_user = User.query.filter_by(email=email).first()
        if existing_user:
            flash('Email already registered!', 'error')
            return redirect(url_for('main.register'))
        
        # Check if username already exists
        existing_username = User.query.filter_by(username=username).first()
        if existing_username:
            flash('Username already taken!', 'error')
            return redirect(url_for('main.register'))
        
        try:
            # Create new user
            user = User(
                username=username,
                email=email,
                user_type=user_type
            )
            user.set_password(password)
            
            db.session.add(user)
            db.session.commit()
            
            # Log successful validation
            log = EmailValidationLog(
                email=email,
                is_valid=True,
                validation_message='Email validated successfully',
                action_type='registration'
            )
            db.session.add(log)
            db.session.commit()
            
            flash('Registration successful! Please login.', 'success')
            return redirect(url_for('main.login'))
        except Exception as e:
            db.session.rollback()
            flash(f'An error occurred during registration: {str(e)}', 'error')
            return redirect(url_for('main.register'))
    
    return render_template('register.html')

@main.route('/login', methods=['GET', 'POST'])
def login():
    # If user is already logged in, redirect to dashboard
    if current_user.is_authenticated:
        if current_user.user_type == 'admin':
            return redirect(url_for('main.admin_dashboard'))
        return redirect(url_for('main.dashboard'))
    
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        
        # Validate input
        if not email or not password:
            flash('Email and password are required!', 'error')
            return render_template('login.html')
        
        # Validate email format
        if not validate_email(email):
            # Log validation attempt
            log = EmailValidationLog(
                email=email,
                is_valid=False,
                validation_message='Invalid email format',
                action_type='login'
            )
            db.session.add(log)
            db.session.commit()
            
            flash('Invalid email format!', 'error')
            return render_template('login.html')
        
        try:
            user = User.query.filter_by(email=email).first()
            
            if user is None:
                flash('Invalid email or password!', 'error')
                return render_template('login.html')
            
            if not user.check_password(password):
                flash('Invalid email or password!', 'error')
                return render_template('login.html')
            
            # Log successful validation
            log = EmailValidationLog(
                email=email,
                is_valid=True,
                validation_message='Login successful',
                action_type='login'
            )
            db.session.add(log)
            db.session.commit()
            
            # Login the user
            login_user(user)
            flash('Logged in successfully!', 'success')
            
            # Redirect based on user type
            if user.user_type == 'admin':
                return redirect(url_for('main.admin_dashboard'))
            
            # Redirect to next page or dashboard
            next_page = request.args.get('next')
            if next_page:
                return redirect(next_page)
            return redirect(url_for('main.dashboard'))
            
        except Exception as e:
            flash(f'An error occurred during login: {str(e)}', 'error')
            return render_template('login.html')
    
    return render_template('login.html')

@main.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('main.index'))

@main.route('/dashboard')
@login_required
def dashboard():
    try:
        if current_user.user_type == 'recruiter':
            jobs = Job.query.filter_by(recruiter_id=current_user.id).order_by(Job.created_at.desc()).all()
            return render_template('dashboard.html', jobs=jobs)
        else:  # freelancer
            # Get all open jobs
            jobs = Job.query.filter_by(status='open').order_by(Job.created_at.desc()).all()
            # Get user's applications
            applications = Application.query.filter_by(freelancer_id=current_user.id).all()
            applied_job_ids = [app.job_id for app in applications]
            return render_template('dashboard.html', jobs=jobs, applied_job_ids=applied_job_ids)
    except Exception as e:
        flash(f'Error loading dashboard: {str(e)}', 'error')
        return redirect(url_for('main.index'))

@main.route('/job/new', methods=['GET', 'POST'])
@login_required
def new_job():
    if current_user.user_type != 'recruiter':
        flash('Only recruiters can post jobs!', 'error')
        return redirect(url_for('main.dashboard'))
    
    if request.method == 'POST':
        try:
            job = Job(
                title=request.form.get('title'),
                description=request.form.get('description'),
                skills_required=request.form.get('skills_required'),
                budget=float(request.form.get('budget', 0)),
                duration=request.form.get('duration'),
                location=request.form.get('location'),
                recruiter_id=current_user.id
            )
            
            db.session.add(job)
            db.session.commit()
            
            flash('Job posted successfully!', 'success')
            return redirect(url_for('main.dashboard'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error posting job: {str(e)}', 'error')
            return render_template('jobform.html')
    
    return render_template('jobform.html')

@main.route('/job/<int:job_id>/apply', methods=['POST'])
@login_required
def apply_job(job_id):
    if current_user.user_type != 'freelancer':
        flash('Only freelancers can apply for jobs!', 'error')
        return redirect(url_for('main.dashboard'))
    
    job = Job.query.get_or_404(job_id)
    
    # Check if already applied
    existing_application = Application.query.filter_by(
        job_id=job_id,
        freelancer_id=current_user.id
    ).first()
    
    if existing_application:
        flash('You have already applied for this job!', 'warning')
        return redirect(url_for('main.dashboard'))
    
    try:
        application = Application(
            job_id=job_id,
            freelancer_id=current_user.id,
            cover_letter=request.form.get('cover_letter'),
            proposed_rate=float(request.form.get('proposed_rate', 0))
        )
        
        db.session.add(application)
        
        # Create notification for recruiter
        notification = Notification(
            user_id=job.recruiter_id,
            message=f'{current_user.username} applied for your job: {job.title}',
            type='application_received'
        )
        db.session.add(notification)
        
        db.session.commit()
        
        flash('Application submitted successfully!', 'success')
        return redirect(url_for('main.dashboard'))
    except Exception as e:
        db.session.rollback()
        flash(f'Error submitting application: {str(e)}', 'error')
        return redirect(url_for('main.dashboard'))

@main.route('/applications')
@login_required
def applications():
    try:
        if current_user.user_type == 'recruiter':
            # Get applications for recruiter's jobs
            job_ids = [job.id for job in current_user.jobs_posted]
            apps = Application.query.filter(Application.job_id.in_(job_ids)).order_by(Application.created_at.desc()).all()
        else:
            # Get freelancer's applications
            apps = Application.query.filter_by(freelancer_id=current_user.id).order_by(Application.created_at.desc()).all()
        
        return render_template('applications.html', applications=apps)
    except Exception as e:
        flash(f'Error loading applications: {str(e)}', 'error')
        return redirect(url_for('main.dashboard'))

@main.route('/application/<int:app_id>/<action>')
@login_required
def update_application(app_id, action):
    application = Application.query.get_or_404(app_id)
    
    # Verify the user is the job recruiter
    if application.job.recruiter_id != current_user.id:
        flash('Unauthorized action!', 'error')
        return redirect(url_for('main.applications'))
    
    if action == 'accept':
        application.status = 'accepted'
        message = f'Your application for {application.job.title} has been accepted!'
    elif action == 'reject':
        application.status = 'rejected'
        message = f'Your application for {application.job.title} has been rejected.'
    else:
        flash('Invalid action!', 'error')
        return redirect(url_for('main.applications'))
    
    try:
        # Create notification for freelancer
        notification = Notification(
            user_id=application.freelancer_id,
            message=message,
            type=f'application_{action}ed'
        )
        db.session.add(notification)
        db.session.commit()
        
        flash(f'Application {action}ed successfully!', 'success')
        return redirect(url_for('main.applications'))
    except Exception as e:
        db.session.rollback()
        flash(f'Error updating application: {str(e)}', 'error')
        return redirect(url_for('main.applications'))

@main.route('/notifications')
@login_required
def notifications():
    try:
        # Mark all notifications as read
        Notification.query.filter_by(user_id=current_user.id, is_read=False).update({'is_read': True})
        db.session.commit()
        
        # Get all notifications
        notifs = Notification.query.filter_by(user_id=current_user.id).order_by(Notification.created_at.desc()).all()
        return render_template('notifications.html', notifications=notifs)
    except Exception as e:
        db.session.rollback()
        flash(f'Error loading notifications: {str(e)}', 'error')
        return redirect(url_for('main.dashboard'))

# ============= CHAT ROUTES =============

@main.route('/messages')
@login_required
def messages():
    """Display all conversations for the current user"""
    try:
        # Get all conversations where user is either user1 or user2
        conversations = Conversation.query.filter(
            or_(
                Conversation.user1_id == current_user.id,
                Conversation.user2_id == current_user.id
            )
        ).order_by(Conversation.updated_at.desc()).all()
        
        return render_template('messages.html', conversations=conversations)
    except Exception as e:
        flash(f'Error loading messages: {str(e)}', 'error')
        return redirect(url_for('main.dashboard'))

@main.route('/messages/new/<int:user_id>')
@login_required
def new_conversation(user_id):
    """Start a new conversation with a user"""
    try:
        other_user = User.query.get_or_404(user_id)
        
        # Check if conversation already exists
        existing_conversation = Conversation.query.filter(
            or_(
                and_(Conversation.user1_id == current_user.id, Conversation.user2_id == user_id),
                and_(Conversation.user1_id == user_id, Conversation.user2_id == current_user.id)
            )
        ).first()
        
        if existing_conversation:
            return redirect(url_for('main.conversation', conversation_id=existing_conversation.id))
        
        # Create new conversation
        conversation = Conversation(
            user1_id=current_user.id,
            user2_id=user_id
        )
        db.session.add(conversation)
        db.session.commit()
        
        return redirect(url_for('main.conversation', conversation_id=conversation.id))
    except Exception as e:
        db.session.rollback()
        flash(f'Error starting conversation: {str(e)}', 'error')
        return redirect(url_for('main.messages'))

@main.route('/messages/<int:conversation_id>')
@login_required
def conversation(conversation_id):
    """Display a specific conversation"""
    try:
        conversation = Conversation.query.get_or_404(conversation_id)
        
        # Verify user is part of this conversation
        if conversation.user1_id != current_user.id and conversation.user2_id != current_user.id:
            flash('You do not have access to this conversation.', 'error')
            return redirect(url_for('main.messages'))
        
        # Get the other user
        other_user = conversation.get_other_user(current_user.id)
        
        # Get all messages in this conversation
        messages = conversation.messages.order_by(Message.created_at.asc()).all()
        
        # Mark received messages as read
        Message.query.filter_by(
            conversation_id=conversation_id,
            receiver_id=current_user.id,
            is_read=False
        ).update({'is_read': True})
        db.session.commit()
        
        return render_template('conversation.html', 
                             conversation=conversation, 
                             other_user=other_user, 
                             messages=messages)
    except Exception as e:
        db.session.rollback()
        flash(f'Error loading conversation: {str(e)}', 'error')
        return redirect(url_for('main.messages'))

@main.route('/messages/<int:conversation_id>/send', methods=['POST'])
@login_required
def send_message(conversation_id):
    """Send a message in a conversation"""
    try:
        conversation = Conversation.query.get_or_404(conversation_id)
        
        # Verify user is part of this conversation
        if conversation.user1_id != current_user.id and conversation.user2_id != current_user.id:
            flash('You do not have access to this conversation.', 'error')
            return redirect(url_for('main.messages'))
        
        # Get content from form
        content = request.form.get('content', '').strip()
        
        if not content:
            flash('Message content is required', 'error')
            return redirect(url_for('main.conversation', conversation_id=conversation_id))
        
        # Determine receiver
        receiver_id = conversation.user2_id if conversation.user1_id == current_user.id else conversation.user1_id
        
        # Create message
        message = Message(
            conversation_id=conversation_id,
            sender_id=current_user.id,
            receiver_id=receiver_id,
            content=content
        )
        
        db.session.add(message)
        
        # Update conversation timestamp
        from datetime import datetime
        conversation.updated_at = datetime.utcnow()
        
        # Create notification for receiver
        notification = Notification(
            user_id=receiver_id,
            message=f'New message from {current_user.username}',
            type='new_message'
        )
        db.session.add(notification)
        
        db.session.commit()
        
        flash('Message sent successfully!', 'success')
        return redirect(url_for('main.conversation', conversation_id=conversation_id))
        
    except Exception as e:
        db.session.rollback()
        flash(f'Error sending message: {str(e)}', 'error')
        return redirect(url_for('main.conversation', conversation_id=conversation_id))

@main.route('/messages/<int:conversation_id>/fetch')
@login_required
def fetch_messages(conversation_id):
    """Fetch new messages (for AJAX polling)"""
    try:
        conversation = Conversation.query.get_or_404(conversation_id)
        
        # Verify user is part of this conversation
        if conversation.user1_id != current_user.id and conversation.user2_id != current_user.id:
            return jsonify({'error': 'Unauthorized'}), 403
        
        # Get timestamp of last message client has
        last_message_id = request.args.get('last_message_id', 0, type=int)
        
        # Get new messages
        new_messages = Message.query.filter(
            Message.conversation_id == conversation_id,
            Message.id > last_message_id
        ).order_by(Message.created_at.asc()).all()
        
        # Mark received messages as read
        Message.query.filter_by(
            conversation_id=conversation_id,
            receiver_id=current_user.id,
            is_read=False
        ).update({'is_read': True})
        db.session.commit()
        
        messages_data = [{
            'id': msg.id,
            'content': msg.content,
            'sender_id': msg.sender_id,
            'sender_username': msg.sender.username,
            'created_at': msg.created_at.strftime('%Y-%m-%d %H:%M')
        } for msg in new_messages]
        
        return jsonify({'messages': messages_data})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ============= ADMIN DASHBOARD ROUTES =============

@main.route('/admin')
@login_required
@admin_required
def admin_dashboard():
    """Admin dashboard with statistics from database views"""
    try:
        # Get statistics from views
        user_stats = db.session.query(UserStatsView).all()
        job_stats = db.session.query(JobStatsView).all()
        app_stats = db.session.query(ApplicationStatsView).all()
        recent_activities = db.session.query(RecentActivityView).limit(20).all()
        popular_jobs = db.session.query(PopularJobsView).limit(10).all()
        
        # Get overall counts
        total_users = User.query.filter(User.user_type.in_(['freelancer', 'recruiter'])).count()
        total_jobs = Job.query.count()
        total_applications = Application.query.count()
        total_messages = Message.query.count()
        
        # Get recent email validation logs
        recent_validations = EmailValidationLog.query.order_by(
            EmailValidationLog.attempted_at.desc()
        ).limit(10).all()
        
        return render_template('admin_dashboard.html',
                             user_stats=user_stats,
                             job_stats=job_stats,
                             app_stats=app_stats,
                             recent_activities=recent_activities,
                             popular_jobs=popular_jobs,
                             total_users=total_users,
                             total_jobs=total_jobs,
                             total_applications=total_applications,
                             total_messages=total_messages,
                             recent_validations=recent_validations)
    except Exception as e:
        flash(f'Error loading admin dashboard: {str(e)}', 'error')
        return redirect(url_for('main.index'))


@main.route('/admin/users')
@login_required
@admin_required
def admin_users():
    """View all users"""
    try:
        users = User.query.filter(User.user_type != 'admin').order_by(User.created_at.desc()).all()
        return render_template('admin_users.html', users=users)
    except Exception as e:
        flash(f'Error loading users: {str(e)}', 'error')
        return redirect(url_for('main.admin_dashboard'))


@main.route('/admin/jobs')
@login_required
@admin_required
def admin_jobs():
    """View all jobs"""
    try:
        jobs = Job.query.order_by(Job.created_at.desc()).all()
        return render_template('admin_jobs.html', jobs=jobs)
    except Exception as e:
        flash(f'Error loading jobs: {str(e)}', 'error')
        return redirect(url_for('main.admin_dashboard'))


@main.route('/admin/applications')
@login_required
@admin_required
def admin_applications():
    """View all applications"""
    try:
        applications = Application.query.order_by(Application.created_at.desc()).all()
        return render_template('admin_applications.html', applications=applications)
    except Exception as e:
        flash(f'Error loading applications: {str(e)}', 'error')
        return redirect(url_for('main.admin_dashboard'))


@main.route('/admin/email-logs')
@login_required
@admin_required
def admin_email_logs():
    """View email validation logs"""
    try:
        logs = EmailValidationLog.query.order_by(EmailValidationLog.attempted_at.desc()).all()
        return render_template('admin_email_logs.html', logs=logs)
    except Exception as e:
        flash(f'Error loading email logs: {str(e)}', 'error')
        return redirect(url_for('main.admin_dashboard'))


@main.route('/admin/user/<int:user_id>/delete', methods=['POST'])
@login_required
@admin_required
def admin_delete_user(user_id):
    """Delete a user"""
    try:
        user = User.query.get_or_404(user_id)
        if user.user_type == 'admin':
            flash('Cannot delete admin users!', 'error')
            return redirect(url_for('main.admin_users'))
        
        db.session.delete(user)
        db.session.commit()
        flash(f'User {user.username} deleted successfully!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error deleting user: {str(e)}', 'error')
    
    return redirect(url_for('main.admin_users'))


@main.route('/admin/job/<int:job_id>/delete', methods=['POST'])
@login_required
@admin_required
def admin_delete_job(job_id):
    """Delete a job"""
    try:
        job = Job.query.get_or_404(job_id)
        db.session.delete(job)
        db.session.commit()
        flash(f'Job "{job.title}" deleted successfully!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error deleting job: {str(e)}', 'error')
    
    return redirect(url_for('main.admin_jobs'))