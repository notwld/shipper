from datetime import datetime
from flask import Blueprint, jsonify, request, render_template, redirect, flash, url_for
from flask_login import current_user, login_required
from models import db, Trip, User,Order,AcceptedOrder,Contact
from sqlalchemy.exc import SQLAlchemyError
from werkzeug.exceptions import BadRequest
import re
from functools import wraps
trip = Blueprint('trip', __name__)

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

def validate_location(location):
    """Validate location string."""
    if not location or not isinstance(location, str):
        raise ValueError("Location must be a non-empty string")
    if len(location) > 200:
        raise ValueError("Location name cannot exceed 200 characters")
    if not re.match(r'^[a-zA-Z0-9\s\-,.()/]+$', location):
        raise ValueError("Location contains invalid characters. Only letters, numbers, spaces, and basic punctuation (,-./()) are allowed")
    return location.strip()

def validate_date(date_str):
    """Validate and parse date string."""
    try:
        travel_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        if travel_date < datetime.now().date():
            raise ValueError("Travel date cannot be in the past")
        return travel_date
    except ValueError as e:
        raise ValueError("Invalid date format or date is in the past")

def validate_weight(weight_str):
    """Validate weight value."""
    try:
        weight = float(weight_str)
        if weight <= 0 or weight > 500: 
            raise ValueError("Weight must be between 0 and 500 kg")
        return weight
    except ValueError:
        raise ValueError("Weight must be a valid number")

@trip.route('/create-trip', methods=['GET', 'POST'])
@email_verified_required
@account_verified_required
@login_required
def create_trip():
    """Handle trip creation form submission."""
    if request.method == 'GET':
        return render_template('trip_form.html', user=current_user)
    
    try:

        traveling_from = validate_location(request.form.get('departure'))
        traveling_to = validate_location(request.form.get('arrival'))
        
        if traveling_from.lower() == traveling_to.lower():
            raise ValueError("Departure and arrival locations cannot be the same")

        traveling_date = validate_date(request.form.get('departure_date'))
        weight = validate_weight(request.form.get('space'))
        comments = request.form.get('description', '').strip()

        if comments and len(comments) > 1000:  
            raise ValueError("Comments cannot exceed 1000 characters")

        new_trip = Trip(
            traveling_from=traveling_from,
            traveling_to=traveling_to,
            traveling_date=traveling_date,
            weight=weight,
            user_id=current_user.id,
            comments=comments if comments else None
        )

        db.session.add(new_trip)
        db.session.commit()

        flash('Trip created successfully!', 'success')
        return redirect(url_for('dashboard.dashboard_home', trip_id=new_trip.id))

    except ValueError as e:
        flash(str(e), 'error')
        return redirect(url_for('trip.create_trip'))
    except SQLAlchemyError as e:
        db.session.rollback()
        flash('An error occurred while saving your trip. Please try again.', 'error')
        return redirect(url_for('trip.create_trip'))
    except Exception as e:
        db.session.rollback()
        flash('An unexpected error occurred. Please try again.', 'error')
        return redirect(url_for('trip.create_trip'))
    

def update_trip_status_by_date(trip):
    """Update trip status based on date."""
    if trip.status != 'inactive':  # Only check active trips
        if trip.traveling_date < datetime.now().date():
            trip.status = 'inactive'
            return True
    return False

@trip.route('/trip/<int:trip_id>')
@login_required
def view_trip(trip_id):
    """Display trip details."""
    trip = Trip.query.get(trip_id)
    if not trip:
        raise BadRequest("Trip not found")
        
    # Update trip status based on date
    if update_trip_status_by_date(trip):
        db.session.commit()
        
    accepted_orders = AcceptedOrder.query.filter_by(trip_id=trip_id).all()
    formatted_accepted_orders = []
    for _order in accepted_orders:
        trip = Trip.query.get(_order.trip_id)
        contact = Contact.query.get(_order.contact_id)
        
        if not trip or not contact:
            continue
            
        initiator = User.query.get(contact.initiator_id)
        recipient = User.query.get(contact.recipient_id)
        
        formatted_accepted_orders.append({
            "trip": {
                "id": trip.id,
                "traveling_from": trip.traveling_from,
                "traveling_to": trip.traveling_to,
                "traveling_date": trip.traveling_date.strftime("%Y-%m-%d"),
                "weight": trip.weight,
                "comments": trip.comments
            },
            "recipient": {
                "id": initiator.id,
                "first_name": initiator.first_name,
                "last_name": initiator.last_name,
                "email": initiator.email
            },
            "traveler": {
                "id": recipient.id,
                "first_name": recipient.first_name,
                "last_name": recipient.last_name,
                "email": recipient.email
            },
            "acceptance_condition": {
                "id": _order.id,
                "status": _order.status,
                "created_at": _order.created_at.strftime("%Y-%m-%d %H:%M:%S"),
                "attribute_type": _order.attribute_type,
                "weight": _order.weight,
                "price_per_kg": _order.price_per_kg,
                "product_details": _order.product_details,
                "total_price": _order.total_price
            }
        })
    
    orders = Order.query.all()
    return render_template('trip_details.html', user=current_user, trip=trip, orders=orders, accepted_orders=formatted_accepted_orders)

@trip.route('/accepted-orders/<int:trip_id>')
@login_required
def view_accepted_orders(trip_id):
    accepted_orders = AcceptedOrder.query.filter_by(trip_id=trip_id).all()
    data = []
    for order in accepted_orders:
        # Remove .first() as query.get() already returns a single object
        trip = Trip.query.get(order.trip_id)
        contact = Contact.query.get(order.contact_id)
        
        if not trip or not contact:
            continue
            
        initiator = User.query.get(contact.initiator_id)
        recipient = User.query.get(contact.recipient_id)
        
        data.append({
            "trip": {
                "id": trip.id,
                "traveling_from": trip.traveling_from,
                "traveling_to": trip.traveling_to,
                "traveling_date": trip.traveling_date.strftime("%Y-%m-%d"),
                "weight": trip.weight,
                "comments": trip.comments
            },
            "traveler": {
                "id": initiator.id,
                "first_name": initiator.first_name,
                "last_name": initiator.last_name,
                "email": initiator.email
            },
            "recipient": {
                "id": recipient.id,
                "first_name": recipient.first_name,
                "last_name": recipient.last_name,
                "email": recipient.email
            },
            "acceptance_condition": {
                "id": order.id,
                "status": order.status,
                "created_at": order.created_at.strftime("%Y-%m-%d %H:%M:%S"),
                "attribute_type": order.attribute_type,
                "weight": order.weight,
                "price_per_kg": order.price_per_kg,
                "product_details": order.product_details,
                "total_price": order.total_price
                
            }
        })

    return jsonify(data)

@trip.route('/trip/update-status/<int:trip_id>/<status>')
@login_required
def update_trip_status(trip_id, status):
    """Update trip status."""
    try:
        trip = Trip.query.get(trip_id)
        if not trip:
            raise BadRequest("Trip not found")
        trip.status = status
        db.session.commit()
        flash('Trip status updated successfully!',
              'success')
        return redirect(url_for('dashboard.dashboard_home', trip_id=trip.id))
    except SQLAlchemyError as e:
        db.session.rollback()
        flash('An error occurred while updating trip status. Please try again.', 'error')
        return redirect(url_for('dashboard.dashboard_home', trip_id=trip.id))
    except Exception as e:
        db.session.rollback()
        flash('An unexpected error occurred. Please try again.', 'error')
        return redirect(url_for('dashboard.dashboard_home', trip_id=trip.id))

@trip.route('/trip/update/<int:trip_id>', methods=['POST'])
@login_required
def update_trip(trip_id):
    """Update trip details."""
    try:
        trip = Trip.query.get_or_404(trip_id)
        
        # Verify ownership
        if trip.user_id != current_user.id:
            return jsonify({'error': 'Unauthorized'}), 401

        data = request.get_json()

        # Validate and update fields
        if 'traveling_date' in data:
            try:
                trip.traveling_date = validate_date(data['traveling_date'])
            except ValueError as e:
                return jsonify({'error': str(e)}), 400

        if 'weight' in data:
            try:
                trip.weight = validate_weight(data['weight'])
            except ValueError as e:
                return jsonify({'error': str(e)}), 400

        db.session.commit()

        return jsonify({
            'id': trip.id,
            'traveling_date': trip.traveling_date.strftime('%Y-%m-%d'),
            'weight': trip.weight,
            'message': 'Trip updated successfully'
        }), 200

    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': 'Failed to update trip'}), 500