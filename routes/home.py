from flask import Blueprint, jsonify, request, render_template,redirect,flash,url_for,current_app,send_from_directory
from models import db, User,Trip, Notification, Message
from flask_login import current_user, login_required
from datetime import datetime
from sqlalchemy import func
from routes.trips import update_trip_status_by_date
from routes.orders import update_order_status_by_date

home = Blueprint('home', __name__)

@home.route('/')
def index():
    # Get current date
    current_date = datetime.now().date()
    
    # Get active users
    users = User.query.filter_by(badge_status="active").limit(6).all()
    trips = []
    
    for user in users:
        # Only get trips with future traveling dates
        user_trips = Trip.query.filter(
            Trip.user_id == user.id,
            Trip.traveling_date >= current_date
        ).order_by(Trip.created_at.desc()).limit(1).all()
        trips.extend(user_trips)

    if current_user.is_authenticated:
        return render_template('index.html', user=current_user, trips=trips)
    else:
        return render_template('index.html', user=None, trips=trips)

@home.route("/trips")
def trips():
    # Get filter parameters
    from_location = request.args.get('from', '').lower()
    to_location = request.args.get('to', '').lower()
    date_str = request.args.get('date')
    verified_only = request.args.get('verified') == 'on'

    # Start with base query
    query = Trip.query

    # Apply filters
    if from_location:
        query = query.filter(Trip.traveling_from.ilike(f'%{from_location}%'))
    if to_location:
        query = query.filter(Trip.traveling_to.ilike(f'%{to_location}%'))
    if date_str:
        date = datetime.strptime(date_str, '%Y-%m-%d').date()
        query = query.filter(func.date(Trip.traveling_date) == date)
    if verified_only:
        query = query.join(Trip.user).filter(User.badge_status == 'active')

    # Get all trips and update their status if needed
    trips = query.order_by(Trip.created_at.desc()).all()
    status_updated = False
    for trip in trips:
        if update_trip_status_by_date(trip):
            status_updated = True
    
    if status_updated:
        db.session.commit()

    # Filter out inactive trips
    active_trips = [trip for trip in trips if trip.status != 'inactive']
    
    return render_template('trips.html', user=current_user if current_user.is_authenticated else None, trips=active_trips)

@home.route('/select-service')
def select_service():
    return render_template('services.html',user=current_user)

@home.route('/public/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(current_app.config['UPLOAD_FOLDER'], filename)

@home.route("/about")
def about():
    return render_template('about.html', user=current_user)

@home.route("/contact")
def contact():
    return render_template('contact.html' , user=current_user)

@home.route("/testimonials")
def testimonials():
    return render_template('testimonials.html', user=current_user)

@home.route("/faq")
def faq():
    return render_template('faqs.html', user=current_user)

@home.route("/terms-and-conditions")
def terms_and_conditions():
    return render_template('terms_and_conditions.html', user=current_user)

@home.route("/privacy-policy")
def privacy_policy():
    return render_template('privacy_policy.html', user=current_user)

@home.route('/check-unread-messages')
@login_required
def check_unread_messages():
    try:
        # Get unread notifications for current user
        notifications = Notification.query.filter_by(
            user_id=current_user.id,
            read=False
        ).order_by(Notification.created_at.desc()).all()
        
        messages = []
        for notification in notifications:
            message = notification.message
            sender = User.query.get(message.sender_id)
            
            messages.append({
                'id': message.id,
                'contact_id': message.contact_id,
                'content': message.content[:50] + '...' if len(message.content) > 50 else message.content,
                'sender_name': f"{sender.first_name} {sender.last_name}",
                'timestamp': message.created_at.strftime("%Y-%m-%d %H:%M")
            })
        
        return jsonify({
            'unread_count': len(notifications),
            'messages': messages
        })
        
    except Exception as e:
        print(f"Error checking messages: {str(e)}")
        return jsonify({'error': 'Failed to check messages'}), 500

@home.route('/mark-message-read/<int:notification_id>', methods=['POST'])
@login_required
def mark_message_read(notification_id):
    try:
        notification = Notification.query.filter_by(
            id=notification_id,
            user_id=current_user.id
        ).first()
        
        if notification:
            notification.read = True
            db.session.commit()
            return jsonify({'success': True})
        
        return jsonify({'error': 'Notification not found'}), 404
        
    except Exception as e:
        print(f"Error marking message as read: {str(e)}")
        return jsonify({'error': 'Failed to mark message as read'}), 500
    
@home.route('/robots.txt',methods=['GET'])
def robots():
    print(current_app.static_folder)
    return send_from_directory(current_app.static_folder, request.path[1:])

@home.route('/sitemap.xml',methods=['GET'])
def sitemap():
    return send_from_directory(current_app.static_folder, request.path[1:])