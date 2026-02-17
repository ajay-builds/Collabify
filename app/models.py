from app import db, login_manager
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timezone
from sqlalchemy import text
import re

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Email validation function (used by trigger)
def validate_email(email):
    """Validate email format using regex"""
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None


# ============= MAIN MODELS =============

class User(UserMixin, db.Model):
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255))
    user_type = db.Column(db.String(20), nullable=False)  # 'freelancer', 'recruiter', or 'admin'
    created_at = db.Column(db.DateTime, default=timezone.utc)
    
    # Relationships
    jobs_posted = db.relationship('Job', backref='recruiter', lazy=True, foreign_keys='Job.recruiter_id')
    applications = db.relationship('Application', backref='freelancer', lazy=True)
    notifications = db.relationship('Notification', backref='user', lazy=True)
    
    # Chat relationships
    sent_messages = db.relationship('Message', foreign_keys='Message.sender_id', backref='sender', lazy='dynamic')
    received_messages = db.relationship('Message', foreign_keys='Message.receiver_id', backref='receiver', lazy='dynamic')
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
    
    @property
    def unread_messages_count(self):
        return Message.query.filter_by(receiver_id=self.id, is_read=False).count()
    
    def validate_email_format(self):
        """Validate email format"""
        return validate_email(self.email)


class Job(db.Model):
    __tablename__ = 'jobs'
    
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=False)
    skills_required = db.Column(db.String(500))
    budget = db.Column(db.Float)
    duration = db.Column(db.String(100))
    location = db.Column(db.String(100))
    status = db.Column(db.String(20), default='open')  # open, in_progress, completed, cancelled
    recruiter_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=timezone.utc)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=timezone.utc)
    
    # Relationships
    applications = db.relationship('Application', backref='job', lazy=True, cascade='all, delete-orphan')


class Application(db.Model):
    __tablename__ = 'applications'
    
    id = db.Column(db.Integer, primary_key=True)
    job_id = db.Column(db.Integer, db.ForeignKey('jobs.id'), nullable=False)
    freelancer_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    cover_letter = db.Column(db.Text)
    proposed_rate = db.Column(db.Float)
    status = db.Column(db.String(20), default='pending')  # pending, accepted, rejected
    created_at = db.Column(db.DateTime, default=timezone.utc)
    updated_at = db.Column(db.DateTime, default=timezone.utc, onupdate=timezone.utc)


class Notification(db.Model):
    __tablename__ = 'notifications'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    message = db.Column(db.String(500), nullable=False)
    type = db.Column(db.String(50))  # application_received, application_accepted, etc.
    is_read = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=timezone.utc)


class Conversation(db.Model):
    __tablename__ = 'conversations'
    
    id = db.Column(db.Integer, primary_key=True)
    user1_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    user2_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=timezone.utc)
    updated_at = db.Column(db.DateTime, default=timezone.utc, onupdate=timezone.utc)
    
    # Relationships
    messages = db.relationship('Message', backref='conversation', lazy='dynamic', cascade='all, delete-orphan')
    
    # Relationships to users
    user1 = db.relationship('User', foreign_keys=[user1_id])
    user2 = db.relationship('User', foreign_keys=[user2_id])
    
    def get_other_user(self, current_user_id):
        """Get the other user in the conversation"""
        if self.user1_id == current_user_id:
            return self.user2
        return self.user1
    
    def get_last_message(self):
        """Get the most recent message in the conversation"""
        return self.messages.order_by(Message.created_at.desc()).first()


class Message(db.Model):
    __tablename__ = 'messages'
    
    id = db.Column(db.Integer, primary_key=True)
    conversation_id = db.Column(db.Integer, db.ForeignKey('conversations.id'), nullable=False)
    sender_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    receiver_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    content = db.Column(db.Text, nullable=False)
    is_read = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=timezone.utc)
    
    def __repr__(self):
        return f'<Message from {self.sender_id} to {self.receiver_id}>'


# ============= EMAIL VALIDATION LOG TABLE =============

class EmailValidationLog(db.Model):
    """Log table for email validation attempts"""
    __tablename__ = 'email_validation_logs'
    
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), nullable=False)
    is_valid = db.Column(db.Boolean, nullable=False)
    validation_message = db.Column(db.String(255))
    attempted_at = db.Column(db.DateTime, default=timezone.utc)
    action_type = db.Column(db.String(20))  # 'registration' or 'login'
    
    def __repr__(self):
        return f'<EmailValidationLog {self.email} - Valid: {self.is_valid}>'


# ============= DATABASE VIEWS FOR ADMIN DASHBOARD =============

class UserStatsView(db.Model):
    """View for user statistics"""
    __tablename__ = 'user_stats_view'
    __table_args__ = {'info': dict(is_view=True)}
    
    user_type = db.Column(db.String(20), primary_key=True)
    total_users = db.Column(db.Integer)
    
    @staticmethod
    def create_view():
        """Create the database view for MySQL"""
        view_query = text("""
            CREATE OR REPLACE VIEW user_stats_view AS
            SELECT 
                user_type,
                COUNT(*) as total_users
            FROM users
            WHERE user_type IN ('freelancer', 'recruiter')
            GROUP BY user_type
        """)
        db.session.execute(view_query)
        db.session.commit()


class JobStatsView(db.Model):
    """View for job statistics"""
    __tablename__ = 'job_stats_view'
    __table_args__ = {'info': dict(is_view=True)}
    
    status = db.Column(db.String(20), primary_key=True)
    total_jobs = db.Column(db.Integer)
    avg_budget = db.Column(db.Float)
    
    @staticmethod
    def create_view():
        """Create the database view for MySQL"""
        view_query = text("""
            CREATE OR REPLACE VIEW job_stats_view AS
            SELECT 
                status,
                COUNT(*) as total_jobs,
                AVG(budget) as avg_budget
            FROM jobs
            GROUP BY status
        """)
        db.session.execute(view_query)
        db.session.commit()


class ApplicationStatsView(db.Model):
    """View for application statistics"""
    __tablename__ = 'application_stats_view'
    __table_args__ = {'info': dict(is_view=True)}
    
    status = db.Column(db.String(20), primary_key=True)
    total_applications = db.Column(db.Integer)
    avg_proposed_rate = db.Column(db.Float)
    
    @staticmethod
    def create_view():
        """Create the database view for MySQL"""
        view_query = text("""
            CREATE OR REPLACE VIEW application_stats_view AS
            SELECT 
                status,
                COUNT(*) as total_applications,
                AVG(proposed_rate) as avg_proposed_rate
            FROM applications
            GROUP BY status
        """)
        db.session.execute(view_query)
        db.session.commit()


class RecentActivityView(db.Model):
    """View for recent platform activity"""
    __tablename__ = 'recent_activity_view'
    __table_args__ = {'info': dict(is_view=True)}
    
    id = db.Column(db.String(50), primary_key=True)
    activity_type = db.Column(db.String(50))
    description = db.Column(db.String(500))
    username = db.Column(db.String(80))
    created_at = db.Column(db.DateTime)
    
    @staticmethod
    def create_view():
        """Create the database view for recent activities (MySQL)"""
        view_query = text("""
            CREATE OR REPLACE VIEW recent_activity_view AS
            SELECT 
                CONCAT('JOB_', j.id) as id,
                'job_posted' as activity_type,
                CONCAT('Posted job: ', j.title) as description,
                u.username,
                j.created_at
            FROM jobs j
            JOIN users u ON j.recruiter_id = u.id
            
            UNION ALL
            
            SELECT 
                CONCAT('APP_', a.id) as id,
                'application_submitted' as activity_type,
                CONCAT('Applied to: ', jo.title) as description,
                u.username,
                a.created_at
            FROM applications a
            JOIN jobs jo ON a.job_id = jo.id
            JOIN users u ON a.freelancer_id = u.id
            
            ORDER BY created_at DESC
            LIMIT 50
        """)
        db.session.execute(view_query)
        db.session.commit()


class PopularJobsView(db.Model):
    """View for most popular jobs (by application count)"""
    __tablename__ = 'popular_jobs_view'
    __table_args__ = {'info': dict(is_view=True)}
    
    job_id = db.Column(db.Integer, primary_key=True)
    job_title = db.Column(db.String(200))
    recruiter_name = db.Column(db.String(80))
    application_count = db.Column(db.Integer)
    budget = db.Column(db.Float)
    status = db.Column(db.String(20))
    
    @staticmethod
    def create_view():
        """Create the database view for popular jobs (MySQL)"""
        view_query = text("""
            CREATE OR REPLACE VIEW popular_jobs_view AS
            SELECT 
                j.id as job_id,
                j.title as job_title,
                u.username as recruiter_name,
                COUNT(a.id) as application_count,
                j.budget,
                j.status
            FROM jobs j
            LEFT JOIN applications a ON j.id = a.job_id
            JOIN users u ON j.recruiter_id = u.id
            GROUP BY j.id, j.title, u.username, j.budget, j.status
            ORDER BY application_count DESC
        """)
        db.session.execute(view_query)
        db.session.commit()


# ============= HELPER FUNCTIONS FOR VIEWS AND TRIGGERS =============

def create_all_views():
    """Create all database views"""
    try:
        UserStatsView.create_view()
        JobStatsView.create_view()
        ApplicationStatsView.create_view()
        RecentActivityView.create_view()
        PopularJobsView.create_view()
        print("✅ All database views created successfully!")
    except Exception as e:
        print(f"❌ Error creating views: {str(e)}")
        db.session.rollback()


def create_email_validation_trigger():
    """Create trigger for email validation (MySQL)"""
    try:
        # Drop existing triggers if they exist
        db.session.execute(text("DROP TRIGGER IF EXISTS validate_email_before_insert"))
        db.session.execute(text("DROP TRIGGER IF EXISTS validate_email_before_update"))
        
        # MySQL trigger for email validation on INSERT
        trigger_insert = text("""
            CREATE TRIGGER validate_email_before_insert
            BEFORE INSERT ON users
            FOR EACH ROW
            BEGIN
                IF NEW.email NOT REGEXP '^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\\.[A-Za-z]{2,}$' THEN
                    SIGNAL SQLSTATE '45000'
                    SET MESSAGE_TEXT = 'Invalid email format. Email must be in format: user@domain.com';
                END IF;
            END
        """)
        db.session.execute(trigger_insert)
        
        # MySQL trigger for email validation on UPDATE
        trigger_update = text("""
            CREATE TRIGGER validate_email_before_update
            BEFORE UPDATE ON users
            FOR EACH ROW
            BEGIN
                IF NEW.email NOT REGEXP '^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\\.[A-Za-z]{2,}$' THEN
                    SIGNAL SQLSTATE '45000'
                    SET MESSAGE_TEXT = 'Invalid email format. Email must be in format: user@domain.com';
                END IF;
            END
        """)
        db.session.execute(trigger_update)
        
        db.session.commit()
        print("✅ Email validation triggers created successfully!")
    except Exception as e:
        print(f"❌ Error creating triggers: {str(e)}")
        db.session.rollback()


def drop_all_views():
    """Drop all database views (for testing/reset)"""
    try:
        db.session.execute(text("DROP VIEW IF EXISTS user_stats_view"))
        db.session.execute(text("DROP VIEW IF EXISTS job_stats_view"))
        db.session.execute(text("DROP VIEW IF EXISTS application_stats_view"))
        db.session.execute(text("DROP VIEW IF EXISTS recent_activity_view"))
        db.session.execute(text("DROP VIEW IF EXISTS popular_jobs_view"))
        db.session.commit()
        print("✅ All views dropped successfully!")
    except Exception as e:
        print(f"❌ Error dropping views: {str(e)}")
        db.session.rollback()


def drop_all_triggers():
    """Drop all triggers (for testing/reset)"""
    try:
        db.session.execute(text("DROP TRIGGER IF EXISTS validate_email_before_insert"))
        db.session.execute(text("DROP TRIGGER IF EXISTS validate_email_before_update"))
        db.session.commit()
        print("✅ All triggers dropped successfully!")
    except Exception as e:
        print(f"❌ Error dropping triggers: {str(e)}")
        db.session.rollback()