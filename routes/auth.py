from flask import Blueprint, jsonify, request, render_template,redirect,flash,url_for,current_app
from models import db, User
from flask_login import login_user,logout_user,login_required,current_user
from sqlalchemy.exc import SQLAlchemyError
import logging,re
from itsdangerous import URLSafeTimedSerializer
from flask_mail import Mail, Message

auth = Blueprint('auth', __name__)
mail = Mail()

@auth.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '')

        # Input validation
        if not email or not password:
            flash('Email and password are required.', 'danger')
            return redirect(url_for('auth.login'))

        try:
            user = User.query.filter_by(email=email).first()

            if not user:
                flash('Invalid email or password.', 'danger')
                return redirect(url_for('auth.login'))

            if user.check_password(password):
                login_user(user)
                flash('Login successful!', 'success')
                return redirect(url_for('home.index'))
            else:
                flash('Invalid email or password.', 'danger')

        except Exception as e:
            logging.error(f"Login error: {str(e)}")
            flash('Something went wrong. Please try again later.', 'danger')

    return render_template('login.html')

@auth.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('auth.login'))

@auth.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        try:
            # Get form data
            name = request.form.get('name')  # Full name from hidden field
            email = request.form.get('email')
            phone = request.form.get('phone')
            password = request.form.get('password')
            password_confirmation = request.form.get('password_confirmation')
            
            try:
                first_name, last_name = name.strip().split(" ", 1)
            except ValueError:
                flash('Please enter both first and last name', 'danger')
                return redirect(url_for('auth.register'))

            # Validation
            if not all([name, email, phone, password, password_confirmation]):
                flash('All fields are required', 'danger')
                return redirect(url_for('auth.register'))

            # Email validation
            email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
            if not re.match(email_pattern, email):
                flash('Please enter a valid email address', 'danger')
                return redirect(url_for('auth.register'))

            # Phone validation
            phone_pattern = r'^\+?1?\d{9,15}$'
            if not re.match(phone_pattern, phone):
                flash('Please enter a valid phone number', 'danger')
                return redirect(url_for('auth.register'))

            # Check if email already exists
            if User.query.filter_by(email=email).first():
                flash('Email already registered', 'danger')
                return redirect(url_for('auth.register'))

            # Password validation
            if password != password_confirmation:
                flash('Passwords do not match', 'danger')
                return redirect(url_for('auth.register'))

            

            # Create new user
            user = User(
                first_name=first_name,
                last_name=last_name,
                email=email,
                phone=phone
            )
            user.set_password(password)
            
            # Save to database
            try:
                db.session.add(user)
                db.session.commit()
                login_user(user)

                flash('Account created successfully! Please login.', 'success')
                token = generate_verification_token(email)
                serializer = URLSafeTimedSerializer(current_app.config['SECRET_KEY'])
                email = serializer.loads(token, salt='email-verification', max_age=3600)  # Token expires after 1 hour
                verification_url = url_for('auth.verify_email_token', token=token, _external=True)
                msg = Message('Verify Your Email',
                  sender='info@bemyshipper.com',
                  recipients=[email])
                msg.body = f'Please click the following link to verify your email: {verification_url}'
                try:
                    mail.send(msg)
                    flash('Verification email has been sent!', 'success')
                    return redirect(url_for('dashboard.verify_email'))
                except Exception as e:
                    print(e)
                    flash('Error sending verification email. Please try again.', 'danger')

                return redirect(url_for('auth.login'))
            except SQLAlchemyError as e:
                db.session.rollback()
                print(e)
                flash('Database error occurred. Please try again.', 'danger')
                return redirect(url_for('auth.register'))

        except Exception as e:
            print(e)
            flash('An unexpected error occurred. Please try again.', 'danger')
            return redirect(url_for('auth.register'))

    # GET request - display registration form
    return render_template('register.html')



def generate_verification_token(email):
    serializer = URLSafeTimedSerializer(current_app.config['SECRET_KEY'])
    return serializer.dumps(email, salt='email-verification')

@auth.route('/verify-email/<token>')
@login_required
def verify_email_token(token):
    try:
        serializer = URLSafeTimedSerializer(current_app.config['SECRET_KEY'])
        email = serializer.loads(token, salt='email-verification', max_age=3600)  # Token expires after 1 hour
        
        user = User.query.filter_by(email=email).first()
        if user:
            user.isEmailVerified = True
            db.session.commit()
            flash('Email verified successfully!', 'success')
            return redirect(url_for('dashboard.membership'))
    except:
        flash('The verification link is invalid or has expired.', 'danger')
    
    return redirect(url_for('dashboard.verify_email'))

@auth.route('/resend-verification', methods=['POST'])
@login_required
def resend_verification():
    token = generate_verification_token(current_user.email)
    verification_url = url_for('auth.verify_email_token', token=token, _external=True)
    
    msg = Message('Verify Your Email',
                  sender='info@bemyshipper.com',
                  recipients=[current_user.email])
    msg.body = f'Please click the following link to verify your email: {verification_url}'
    
    try:
        mail.send(msg)
        flash('Verification email has been sent!', 'success')
    except Exception as e:
        print(e)
        flash('Error sending verification email. Please try again.', 'danger')
    
    return redirect(url_for('dashboard.verify_email'))

@auth.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        if not email:
            flash('Email is required', 'danger')
            return redirect(url_for('auth.forgot_password'))
        
        user = User.query.filter_by(email=email).first()
        if not user:
            flash('User not found', 'danger')
            return redirect(url_for('auth.forgot_password'))
        
        token = generate_verification_token(email)
        reset_url = url_for('auth.reset_password', token=token, _external=True)
        
        msg = Message('Reset Your Password',
                      sender='info@bemyshipper.com',
                        recipients=[email])
        msg.body = f'Please click the following link to reset your password: {reset_url}'

        try:
            mail.send(msg)
            flash('Password reset link has been sent to your email.', 'success')
        except Exception as e:
            print(e)
            flash('Error sending password reset email. Please try again.', 'danger')

        return redirect(url_for('auth.login'))
    
    return render_template('forgot_password.html')

@auth.route('/reset-password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    if request.method == 'POST':
        password = request.form.get('password')
        password_confirmation = request.form.get('password_confirmation')
        
        if not password or not password_confirmation:
            flash('Password and password confirmation are required', 'danger')
            return redirect(url_for('auth.reset_password', token=token))
        
        if password != password_confirmation:
            flash('Passwords do not match', 'danger')
            return redirect(url_for('auth.reset_password', token=token))
        
        try:
            serializer = URLSafeTimedSerializer(current_app.config['SECRET_KEY'])
            email = serializer.loads(token, salt='email-verification', max_age=3600) 
            user = User.query.filter_by(email=email).first()
            if user:
                user.set_password(password)
                db.session.commit()
                flash('Password reset successfully!', 'success')
                return redirect(url_for('auth.login'))
        except:
            flash('The reset link is invalid or has expired.', 'danger')
            return redirect(url_for('auth.forgot_password'))
    
    return render_template('reset_password.html', token=token)

