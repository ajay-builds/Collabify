from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
# from flask_migrate import Migrate
import os
from dotenv import load_dotenv

# Initialize extensions
db = SQLAlchemy()
login_manager = LoginManager()

def create_app():
    # Load environment variables
    load_dotenv()
    
    # Create Flask app
    app = Flask(__name__)
    
    # Configure app
    app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'dev-secret-key')
    app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL')
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    
    # Initialize extensions with app
    db.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = 'main.login'
    login_manager.login_message = 'Please login to access this page.'
    
    # Register blueprints
    from app.routes import main
    app.register_blueprint(main)
    
    # Create database tables, views, and triggers
    with app.app_context():
        db.create_all()
        
        # Import after db is initialized
        from app.models import create_all_views, create_email_validation_trigger
        
        # Create database views for admin dashboard
        create_all_views()
        
        # Create email validation triggers
        create_email_validation_trigger()
        
        # Create default admin user if not exists
        from app.models import User
        admin = User.query.filter_by(email='admin@colabify.com').first()
        if not admin:
            admin = User(
                username='admin',
                email='admin@colabify.com',
                user_type='admin'
            )
            admin.set_password('admin123')  # Change this in production!
            db.session.add(admin)
            db.session.commit()
            print("✅ Default admin user created: admin@colabify.com / admin123")
    
    return app