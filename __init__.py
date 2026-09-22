from flask import Flask, request, render_template
from flask_cors import CORS
from flask_login import LoginManager
import os
from flask_mail import Mail, Message
from flask_socketio import SocketIO, emit, join_room
import stripe
from routes import init_routes
from dotenv import load_dotenv
from flask_migrate import Migrate
from models import db,User

load_dotenv()

def create_app():
    app = Flask(__name__,static_folder="assets",template_folder="templates")
   
    mail = Mail()
    migrate = Migrate(app, db)
    stripe.api_key = os.getenv('STRIPE_SECRET_KEY')

    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///app.db'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['SECRET_KEY'] = 'your_secret_key_here'
    app.config['JWT_SECRET_KEY'] = 'your_jwt_secret_key_here' 
    app.config['UPLOAD_FOLDER'] = os.path.join(os.getcwd(), 'public/uploads')
    app.config['MAIL_SERVER'] = os.getenv('MAIL_HOST')
    app.config['MAIL_PORT'] = os.getenv('MAIL_PORT')
    app.config['MAIL_USERNAME'] = os.getenv('MAIL_USERNAME')
    app.config['MAIL_PASSWORD'] = os.getenv('MAIL_PASSWORD')
    app.config['MAIL_USE_TLS'] = os.getenv('MAIL_ENCRYPTION') == 'tls'
    app.config['MAIL_USE_SSL'] = os.getenv('MAIL_ENCRYPTION') == 'ssl'
    app.config['MAIL_DEFAULT_SENDER'] = os.getenv('MAIL_USERNAME')
    app.config['MAX_CONTENT_LENGTH'] = 25 * 1024 * 1024 
    app.config['UPLOAD_FOLDER'] = os.path.join('static', 'uploads')
    
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True) 
    
    CORS(app, resources={
        r"/*": {
            "origins": ["https://bemyshipper.com","https://stage.bemyshipper.com", "http://stage.bemyshipper.com","http://127.0.0.1:5087"],
            "allow_headers": ["Content-Type"],
            "methods": ["GET", "POST", "OPTIONS"]
        }
    })

    socketio = SocketIO(
        app,
        cors_allowed_origins=["https://bemyshipper.com","https://stage.bemyshipper.com", "http://stage.bemyshipper.com","http://127.0.0.1:5087"],
        async_mode='threading',
        ping_timeout=60,
        ping_interval=25,
        logger=True,
        engineio_logger=True
    )

    login_manager = LoginManager()
    login_manager.login_view = 'auth.login'
    login_manager.init_app(app)
    mail.init_app(app)
    
    if not os.path.exists(app.config['UPLOAD_FOLDER']):
        os.makedirs(app.config['UPLOAD_FOLDER'])

    db.init_app(app)

    with app.app_context():
        db.create_all()
       
    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))
    
    @app.errorhandler(404)
    def page_not_found(e):
        return render_template('404.html'), 404
    
    init_routes(app)

    return app,socketio