from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_socketio import SocketIO
from flask_cors import CORS
from flask_migrate import Migrate
from flask_jwt_extended import JWTManager
from .config import Config

db = SQLAlchemy()
socketio = SocketIO(cors_allowed_origins="*")
migrate = Migrate()
jwt = JWTManager()

def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)
    
    # Initialize extensions
    db.init_app(app)
    socketio.init_app(app, async_mode='eventlet')
    migrate.init_app(app, db)
    jwt.init_app(app)
    CORS(app)
    
    # Create upload folders
    import os
    for folder in [app.config['UPLOAD_FOLDER'], app.config['ID_UPLOAD_FOLDER'], 
                   app.config['PASSPORT_UPLOAD_FOLDER'], app.config['PORTFOLIO_UPLOAD_FOLDER']]:
        os.makedirs(folder, exist_ok=True)
    
    # Register blueprints
    from .auth import auth_bp
    from .routes import api_bp
    from .chat import chat_bp
    from .admin_routes import admin_bp
    from .payments import payments_bp
    
    app.register_blueprint(auth_bp, url_prefix='/auth')
    app.register_blueprint(api_bp, url_prefix='/api')
    app.register_blueprint(chat_bp, url_prefix='/chat')
    app.register_blueprint(admin_bp, url_prefix='/admin')
    app.register_blueprint(payments_bp, url_prefix='/payments')
    
    # Create tables
    with app.app_context():
        db.create_all()
    
    return app
