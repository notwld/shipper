import os
from datetime import datetime
from werkzeug.utils import secure_filename
from flask import Blueprint, jsonify, request, render_template, redirect, flash, url_for, current_app
from models import db, User, Order,Trip
from flask_login import current_user, login_required
from functools import wraps
order = Blueprint('order', __name__)

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

def account_verified_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.isAccountVerified:
            flash('Please complete your membership verification to access this feature.', 'warning')
            return redirect(url_for('dashboard.membership'))
        return f(*args, **kwargs)
    return decorated_function

def email_verified_required(f):
    @wraps(f)
    @login_required  # Make sure user is logged in first
    def decorated_function(*args, **kwargs):
        if not current_user.isEmailVerified:
            flash('Please verify your email address to access this page.', 'warning')
            return redirect(url_for('dashboard.verify_email'))
        return f(*args, **kwargs)
    return decorated_function

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def save_file(file):
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        # Generate unique filename using timestamp
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        unique_filename = f"{timestamp}_{filename}"
        file_path = os.path.join(current_app.config['UPLOAD_FOLDER'], unique_filename)
        file.save(file_path)
        return unique_filename
    return None

@order.route('/create-order', methods=['GET', 'POST'])
@email_verified_required
@account_verified_required
@login_required
def create_order():
    if request.method == 'POST':
        try:
            earliest_date = request.form.get('receive_earliest_date')
            last_date = request.form.get('receive_last_date')
            departure = request.form.get('departure')
            arrival = request.form.get('arrival')
            space = request.form.get('space')
            description = request.form.get('description')

            if not all([earliest_date, last_date, departure, arrival, space]):
                flash('All required fields must be filled', 'danger')
                return redirect(url_for('order.create_order'))

            try:
                earliest_date = datetime.strptime(earliest_date, '%Y-%m-%d').date()
                last_date = datetime.strptime(last_date, '%Y-%m-%d').date()
            except ValueError:
                flash('Invalid date format', 'danger')
                return redirect(url_for('order.create_order'))

            if earliest_date > last_date:
                flash('Earliest date cannot be later than last date', 'danger')
                return redirect(url_for('order.create_order'))

            if earliest_date < datetime.now().date():
                flash('Earliest date cannot be in the past', 'danger')
                return redirect(url_for('order.create_order'))

            try:
                weight = float(space)
                if weight <= 0:
                    raise ValueError
            except ValueError:
                flash('Please enter a valid weight', 'danger')
                return redirect(url_for('order.create_order'))


            images = []
            attachments = request.files.getlist('attachments[]')
            
            for file in attachments:
                if file.filename:  
                    if not allowed_file(file.filename):
                        flash('Invalid file type. Only images (png, jpg, jpeg, gif) are allowed', 'danger')
                        return redirect(url_for('order.create_order'))
                    
                    filename = save_file(file)
                    if filename:
                        images.append(filename)

            try:
                new_order = Order(
                    earliest_date=earliest_date,
                    last_date=last_date,
                    order_from_location=departure,
                    deliverer_location=arrival,
                    weight=weight,
                    user_id=current_user.id,
                    comments=description,
                    images=images
                )

                db.session.add(new_order)
                db.session.commit()

                flash('Order created successfully!', 'success')
                return redirect(url_for('dashboard.dashboard_home'))

            except ValueError as e:
                flash(str(e), 'danger')
                return redirect(url_for('order.create_order'))
            
            except Exception as e:
                db.session.rollback()
                current_app.logger.error(f"Error creating order: {str(e)}")
                flash('Error creating order. Please try again.', 'danger')
                return redirect(url_for('order.create_order'))

        except Exception as e:
            current_app.logger.error(f"Unexpected error: {str(e)}")
            flash('An unexpected error occurred. Please try again.', 'danger')
            return redirect(url_for('order.create_order'))

    return render_template('order_form.html', user=current_user)

def update_order_status_by_date(order):
    """Update order status based on date."""
    if order.status != 'inactive':  # Only check active orders
        if order.last_date < datetime.now().date():
            order.status = 'inactive'
            return True
    return False

@order.route('/order/<int:order_id>')
@login_required
def view_order(order_id):
    order = Order.query.get(order_id)
    if not order:
        flash('Order not found', 'danger')
        return redirect(url_for('dashboard.dashboard_home'))

    # Update order status based on date
    if update_order_status_by_date(order):
        db.session.commit()

    trips = Trip.query.all()
    return render_template('order_detail.html', user=current_user, order=order, trips=trips)

@order.route('/order/update-status/<int:order_id>/<status>')
@login_required
def update_order_status(order_id, status):
    order = Order.query.get(order_id)
    if not order:
        flash('Order not found', 'danger')
        return redirect(url_for('dashboard.dashboard_home'))

    if status not in ['active', 'inactive', 'completed']:
        flash('Invalid status', 'danger')
        return redirect(url_for('dashboard.dashboard_home'))

    order.status = status
    db.session.commit()
    flash('Order status updated successfully!', 'success')
    return redirect(url_for('dashboard.dashboard_home', order_id=order_id))

