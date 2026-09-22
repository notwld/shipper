from flask import Blueprint, jsonify, request, render_template,redirect,flash,url_for,current_app,send_from_directory
from models import db, User,Contact,Message,SecretKey,AcceptedOrder,Trip,Order
from flask_login import current_user, login_required
from functools import wraps
import stripe
from datetime import datetime, timedelta
from flask_mail import Mail, Message as msg
from routes.trips import update_trip_status_by_date
from routes.orders import update_order_status_by_date
from werkzeug.utils import secure_filename
import os
dashboard = Blueprint('dashboard', __name__)
mail = Mail()

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

@dashboard.route('/dashboard')
@email_verified_required
@login_required
def dashboard_home():
    orders = current_user.orders
    trips = current_user.trips

    # Update status of orders and trips
    status_updated = False
    for order in orders:
        if update_order_status_by_date(order):
            status_updated = True
    
    for trip in trips:
        if update_trip_status_by_date(trip):
            status_updated = True
    
    if status_updated:
        db.session.commit()

    # Initialize default values
    badge_price = 0
    badge_name = "Verification Badge"
    
    try:
        badge_price_id = SecretKey.query.filter_by(slug='stripe-verify-badge-price-id').first()
        if badge_price_id:
            badge_price_obj = stripe.Price.retrieve(badge_price_id.key)
            badge_price = badge_price_obj.unit_amount/100
            product = stripe.Product.retrieve(badge_price_obj.product)
            badge_name = product.name
    except Exception as e:
        print(f"Error retrieving Stripe price: {str(e)}")
        # Keep default values

    # Check badge expiration
    days_remaining = None
    if current_user.badge_start:
        expiration_date = current_user.badge_start + timedelta(days=30)
        days_remaining = (expiration_date - datetime.now()).days
        
        if days_remaining <= 0:
            current_user.badge_status = 'inactive'
            current_user.badge_start = None
            db.session.commit()
            days_remaining = None

    # Check membership expiration
    membership_days_remaining = None
    if current_user.subscription_start:
        expiration_date = current_user.subscription_start + timedelta(days=30)
        membership_days_remaining = (expiration_date - datetime.now()).days
        
        if membership_days_remaining <= 0:
            current_user.subscription_status = 'inactive'
            current_user.isAccountVerified = False
            current_user.subscription_start = None
            db.session.commit()
            membership_days_remaining = None

    contacts = Contact.query.filter((Contact.initiator_id == current_user.id) | (Contact.recipient_id == current_user.id)).all()
    contacts_data = []
    for contact in contacts:
        if contact.initiator_id == current_user.id:
            user = User.query.get(contact.recipient_id)
        else:
            user = User.query.get(contact.initiator_id)
        contacts_data.append({
            'id': contact.id,
            'user_id': user.id,
            'name': f"{user.first_name} {user.last_name}",
            'email': user.email,
            'trip_id': contact.trip_id,
            'badge_status': user.badge_status
        })

    return render_template('dashboard.html', 
                         user=current_user,
                         contacts=contacts_data,
                         orders=orders, 
                         trips=trips, 
                         badge_price=badge_price,
                         badge_name=badge_name,
                         days_remaining=days_remaining,
                         membership_days_remaining=membership_days_remaining)


@dashboard.route('/verify-email')
@login_required
def verify_email():
    if current_user.isEmailVerified:
        return redirect(url_for('dashboard.dashboard_home'))
    return render_template('verify_email.html',user=current_user)

@dashboard.route('/contact', methods=['POST'])
@account_verified_required
@login_required
def contact():
    try:
        user = User.query.filter_by(email=current_user.email).first()
        initiator_id = user.id
        data = request.get_json()
        receiver_id = data.get('user_id')
        order_id = data.get('order_id')
        if not all([receiver_id, order_id]):
            return jsonify({'error': 'Missing required fields'}), 400
        contact = Contact(initiator_id=initiator_id, recipient_id=receiver_id, order_id=order_id)
        db.session.add(contact)
        db.session.commit()
    except Exception as e:
        return jsonify({'error': 'An unexpected error occurred'}), 500
    return jsonify({'message': 'Contact created successfully'}), 201

@dashboard.route('/contact/<string:type>', methods=['GET'])
@account_verified_required
@login_required
def get_contacts(type):
    user = User.query.filter_by(email=current_user.email).first()
    print(type)
    if(type=="order"):
        contacts = Contact.query.filter_by(initiator_id=user.id).all()
        if not contacts:
            return jsonify({'error': 'No contacts found'}), 404
        contacts_data = []
        for contact in contacts:
            recipient = User.query.filter_by(id=contact.recipient_id).first()
            contacts_data.append({
                'id': contact.id,
                'my_id': user.id,
                'initiator_id': user.id,
                'recipient_id': recipient.id,
                'initiator_name': user.first_name + " " + user.last_name,
                'recipient_name': recipient.first_name + " " + recipient.last_name,
            
            })
        return jsonify(contacts_data), 200
    else:
        contacts = Contact.query.filter_by(recipient_id=user.id).all()
        if not contacts:
            return jsonify({'error': 'No contacts found'}), 404
        contacts_data = []
        for contact in contacts:
            initiator = User.query.filter_by(id=contact.initiator_id).first()
            contacts_data.append({
                'id': contact.id,
                'my_id': user.id,
                'initiator_id': initiator.id,
                'recipient_id': user.id,
                'initiator_name': initiator.first_name + " " + initiator.last_name,
                'recipient_name': user.first_name + " " + user.last_name,
            })
        
        return jsonify(contacts_data), 200
    
@dashboard.route('/chat/order/<int:id>', methods=['GET'])
@account_verified_required
@login_required
def chat(id):
    # Find the contact where either user is involved
    contact = Contact.query.filter(
        ((Contact.initiator_id == current_user.id) & (Contact.recipient_id == id)) |
        ((Contact.initiator_id == id) & (Contact.recipient_id == current_user.id))
    ).first()
    
    if not contact:
        flash('Chat not found.', 'error')
        return redirect(url_for('dashboard.dashboard_home'))
    
    # Check if current user is either the initiator or recipient
    if contact.initiator_id != current_user.id and contact.recipient_id != current_user.id:
        flash('You do not have permission to access this chat.', 'error')
        return redirect(url_for('dashboard.dashboard_home'))
    
    # Get the other user's info
    other_user = User.query.get(id)
    if not other_user:
        flash('Chat participant not found.', 'error')
        return redirect(url_for('dashboard.dashboard_home'))

    # Get messages
    messages = Message.query.filter_by(contact_id=contact.id).order_by(Message.created_at).all()

    return render_template("chat.html", 
                         contact=contact, 
                         user=other_user, 
                         messages=messages, 
                         current_user=current_user)

@dashboard.route('/chat/trip/<int:id>', methods=['GET'])
@account_verified_required
@login_required
def chattrip(id):
    # Find the contact where either user is involved
    contact = Contact.query.filter(
        ((Contact.initiator_id == current_user.id) & (Contact.recipient_id == id)) |
        ((Contact.initiator_id == id) & (Contact.recipient_id == current_user.id))
    ).first()
    
    if not contact:
        flash('Chat not found.', 'error')
        return redirect(url_for('dashboard.dashboard_home'))
    
    # Check if current user is either the initiator or recipient
    if contact.initiator_id != current_user.id and contact.recipient_id != current_user.id:
        flash('You do not have permission to access this chat.', 'error')
        return redirect(url_for('dashboard.dashboard_home'))
    
    # Get the other user's info
    other_user = User.query.get(id)
    if not other_user:
        flash('Chat participant not found.', 'error')
        return redirect(url_for('dashboard.dashboard_home'))

    # Get messages
    messages = Message.query.filter_by(contact_id=contact.id).order_by(Message.created_at).all()

    return render_template("chat.html", 
                         contact=contact, 
                         user=other_user, 
                         messages=messages, 
                         current_user=current_user)

@dashboard.route('/membership')
@email_verified_required
@login_required
def membership():
    try:
        membership_price_id = SecretKey.query.filter_by(slug='stripe-membership-price-id').first()
        price = stripe.Price.retrieve(membership_price_id.key)
        print(price)
    except Exception as e:
        print(e)
        flash('An error occurred while retrieving membership price', 'danger')
        return redirect(url_for('dashboard.dashboard_home'))
    return render_template('membership.html', price=price.unit_amount/100,user=current_user)

@dashboard.route('/create-checkout-session', methods=['POST'])
@email_verified_required
@login_required
def create_checkout_session():
    
    try:
        if not current_user.stripe_customer_id:
            customer = stripe.Customer.create(
                email=current_user.email,
                name=f"{current_user.first_name} {current_user.last_name}",
                metadata={
                    "user_id": current_user.id
                }
            )
            # Save customer ID to database
            current_user.stripe_customer_id = customer.id
            db.session.commit()
        else:
            customer = stripe.Customer.retrieve(current_user.stripe_customer_id)
        membership_price_id = SecretKey.query.filter_by(slug='stripe-membership-price-id').first()
        checkout_session = stripe.checkout.Session.create(
            customer=customer.id,
            payment_method_types=['card'],
            line_items=[{
                'price': membership_price_id.key,
                'quantity': 1,
            }],
            mode='payment',
            success_url=url_for('dashboard.handle_subscription_success', _external=True) + '?session_id={CHECKOUT_SESSION_ID}',
            cancel_url=url_for('dashboard.membership', _external=True),
        )
        return jsonify({'url': checkout_session.url})
    except Exception as e:
        print(e)
        return jsonify({'error': str(e)}), 500
    
@dashboard.route('/handle-subscription-success')
@email_verified_required
@login_required
def handle_subscription_success():
    session_id = request.args.get('session_id')
    if not session_id:
        return jsonify({'error': 'Session ID is required'}), 400
    
    try:
        checkout_session = stripe.checkout.Session.retrieve(session_id)
        if checkout_session.payment_status == 'paid':
            current_user.subscription_status = 'active'
            current_user.isAccountVerified = True
            current_user.subscription_start = datetime.now()
            db.session.commit()
        return redirect(url_for('dashboard.subscription_success'))
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@dashboard.route('/subscription-success')
# @account_verified_required
@login_required
def subscription_success():
    return render_template('payment_success.html',user=current_user)

@dashboard.route('/verify-badge-checkout', methods=['POST'])
@email_verified_required
@account_verified_required
@login_required
def create_badge_checkout_session():
    try:
        if not current_user.stripe_customer_id:
            customer = stripe.Customer.create(
                email=current_user.email,
                name=f"{current_user.first_name} {current_user.last_name}",
                metadata={"user_id": current_user.id}
            )
            current_user.stripe_customer_id = customer.id
            db.session.commit()
        else:
            customer = stripe.Customer.retrieve(current_user.stripe_customer_id)
            
        badge_price_id = SecretKey.query.filter_by(slug='stripe-verify-badge-price-id').first()
        
        checkout_session = stripe.checkout.Session.create(
            customer=customer.id,
            payment_method_types=['card'],
            line_items=[{
                'price': badge_price_id.key,
                'quantity': 1,
            }],
            mode='payment',
            success_url=url_for('dashboard.handle_badge_success', _external=True) + '?session_id={CHECKOUT_SESSION_ID}',
            cancel_url=url_for('dashboard.dashboard_home', _external=True),
        )
        return jsonify({'url': checkout_session.url})
    except Exception as e:
        print(e)
        return jsonify({'error': str(e)}), 500

@dashboard.route('/handle-badge-success')
@email_verified_required
@login_required
def handle_badge_success():
    session_id = request.args.get('session_id')
    if not session_id:
        return jsonify({'error': 'Session ID is required'}), 400
    
    try:
        checkout_session = stripe.checkout.Session.retrieve(session_id)
        if checkout_session.payment_status == 'paid':
            current_user.badge_status = 'active'
            current_user.badge_start = datetime.now()
            db.session.commit()
        return redirect(url_for('dashboard.subscription_success'))
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    

@dashboard.route('/cancel-badge', methods=['POST'])
@email_verified_required
@login_required
def cancel_badge():
    try:
        if current_user.badge_status == 'active':
            current_user.badge_status = 'inactive'
            current_user.badge_start = None
            db.session.commit()
            return jsonify({'success': True, 'message': 'Badge cancelled successfully'})
        else:
            return jsonify({'success': False, 'error': 'No active badge found'}), 400
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500
    
@dashboard.route('/history', methods=['GET'])
@login_required
def history():
    # Get accepted orders where current user is either the initiator or recipient
    accepted_orders = AcceptedOrder.query.join(Contact).filter(
        db.or_(
            Contact.initiator_id == current_user.id,
            Contact.recipient_id == current_user.id
        )
    ).all()

    data = []
    for order in accepted_orders:
        contact = order.contact  # Use the relationship defined in the model
        
        # Get the trip associated with this order
        trip = Trip.query.get(order.trip_id) if order.trip_id else None
        # Get the order details if it exists
        order_details = Order.query.get(order.order_id) if order.order_id else None
        
        initiator = User.query.get(contact.initiator_id)
        recipient = User.query.get(contact.recipient_id)
        print(order.uuid)
        order_data = {
            "id": order.id,
            "uuid": order.uuid,
            "status": order.status,
            "created_at": order.created_at.strftime("%Y-%m-%d %H:%M:%S"),
            "attribute_type": order.attribute_type,
            "weight": order.weight,
            "price_per_kg": order.price_per_kg,
            "product_details": order.product_details,
            "total_price": order.total_price,
            "trip": {
                "id": trip.id,
                "traveling_from": trip.traveling_from,
                "traveling_to": trip.traveling_to,
                "traveling_date": trip.traveling_date.strftime("%Y-%m-%d"),
                "weight": trip.weight,
                "comments": trip.comments
            } if trip else None,
            "order": {
                "id": order_details.id,
                "order_from_location": order_details.order_from_location,
                "deliverer_location": order_details.deliverer_location,
                "earliest_date": order_details.earliest_date.strftime("%Y-%m-%d"),
                "last_date": order_details.last_date.strftime("%Y-%m-%d"),
                "weight": order_details.weight,
                "comments": order_details.comments
            } if order_details else None,
            "initiator": {
                "id": initiator.id,
                "name": f"{initiator.first_name} {initiator.last_name}",
                "email": initiator.email
            },
            "recipient": {
                "id": recipient.id,
                "name": f"{recipient.first_name} {recipient.last_name}",
                "email": recipient.email
            }
        }
        data.append(order_data)

    return render_template('history.html', orders=data,user=current_user)



@dashboard.route('/contact-trip-creator/<int:id>', methods=['GET'])
@login_required 
@email_verified_required
@account_verified_required
def inbox(id):
    try:
        trip = Trip.query.get(id)
        if not trip:
            flash('Trip not found.', 'error')
            return redirect(url_for('dashboard.dashboard_home'))

        initiator_id = current_user.id
        receiver_id = trip.user_id

        # Prevent self-messaging
        if initiator_id == receiver_id:
            flash('You cannot contact yourself.', 'error')
            return redirect(url_for('dashboard.dashboard_home'))

        # Check if contact already exists between these users
        existing_contact = Contact.query.filter(
            ((Contact.initiator_id == initiator_id) & (Contact.recipient_id == receiver_id)) |
            ((Contact.initiator_id == receiver_id) & (Contact.recipient_id == initiator_id))
        ).first()

        initiator = User.query.get(initiator_id)
        receiver = User.query.get(receiver_id)
        
        if not receiver:
            flash('Recipient user not found.', 'error')
            return redirect(url_for('dashboard.dashboard_home'))

        # Create new contact if it doesn't exist
        if not existing_contact:
            contact = Contact(initiator_id=initiator_id, recipient_id=receiver_id, trip_id=trip.id)
            db.session.add(contact)
            db.session.commit()
            contact_id = contact.id
        else:
            contact_id = existing_contact.id

        # Generate URL after we have a valid contact_id
        chat_url = url_for('dashboard.inbox_msgs', id=contact_id, _external=True)

        # Send email notification
        m = msg("You have new messages!", sender='info@bemyshipper.com', recipients=[receiver.email])
        m.body = f"""Hi {receiver.first_name},

                {initiator.first_name} {initiator.last_name} has contacted you regarding your trip from {trip.traveling_from} to {trip.traveling_to} on {trip.traveling_date.strftime('%Y-%m-%d')}.

                Please click the following link to view the message:
                {chat_url}

                Best,
                BeMyShipper Team"""

        try:
            mail.send(m)
        except Exception as e:
            print(f"Email error: {e}")
            flash('Message received but email notification failed.', 'warning')

        # Redirect to chat
        return redirect(url_for('dashboard.inbox_msgs', id=contact_id))

    except Exception as e:
        print(f"Error in contact-trip-creator: {e}")
        flash('An unexpected error occurred. Please try again later.', 'danger')
        return redirect(url_for('dashboard.dashboard_home'))


@dashboard.route('/inbox/<int:id>', methods=['GET'])
@email_verified_required
@login_required
def inbox_msgs(id):
    # Find the contact
    contact = Contact.query.get(id)
    
    if not contact:
        flash('Chat not found.', 'error')
        return redirect(url_for('dashboard.dashboard_home'))
    
    # Check if current user is either the initiator or recipient
    if contact.initiator_id != current_user.id and contact.recipient_id != current_user.id:
        flash('You do not have permission to access this chat.', 'error')
        return redirect(url_for('dashboard.dashboard_home'))
    
    # Get the other user's ID (the one who isn't the current user)
    other_user_id = contact.recipient_id if contact.initiator_id == current_user.id else contact.initiator_id
    
    # Get the other user's info
    other_user = User.query.get(other_user_id)
    if not other_user:
        flash('Chat participant not found.', 'error')
        return redirect(url_for('dashboard.dashboard_home'))

    # Get messages
    messages = Message.query.filter_by(contact_id=contact.id).order_by(Message.created_at).all()

    return render_template("chat.html", 
                         contact=contact, 
                         user=other_user, 
                         messages=messages, 
                         current_user=current_user)

@dashboard.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    return render_template('profile.html', user=current_user)

@dashboard.route('/update-profile', methods=['POST'])
@login_required
def update_profile():
    try:
        # Get form data
        first_name = request.form.get('first_name')
        last_name = request.form.get('last_name')
        email = request.form.get('email')
        phone = request.form.get('phone')

        # Validate email uniqueness if it's changed
        if email != current_user.email:
            existing_user = User.query.filter_by(email=email).first()
            if existing_user:
                flash('Email already exists', 'danger')
                return redirect(url_for('dashboard.profile'))

        # Update user information
        current_user.first_name = first_name
        current_user.last_name = last_name
        current_user.email = email
        current_user.phone = phone

        db.session.commit()
        flash('Profile updated successfully', 'success')
    except Exception as e:
        db.session.rollback()
        flash('An error occurred while updating profile', 'danger')
        print(f"Error updating profile: {str(e)}")

    return redirect(url_for('dashboard.profile'))

@dashboard.route('/update-password', methods=['POST'])
@login_required
def update_password():
    try:
        current_password = request.form.get('current_password')
        new_password = request.form.get('new_password')
        confirm_password = request.form.get('confirm_password')

        # Verify current password
        if not current_user.check_password(current_password):
            flash('Current password is incorrect', 'danger')
            return redirect(url_for('dashboard.profile'))
        
        if len(new_password) < 6:
            flash('Password must be at least 6 characters', 'danger')
            return redirect(url_for('dashboard.profile'))

        # Check if new passwords match
        if new_password != confirm_password:
            flash('New passwords do not match', 'danger')
            return redirect(url_for('dashboard.profile'))
        # Update password
        current_user.set_password(new_password)
        db.session.commit()
        flash('Password updated successfully', 'success')
    except Exception as e:
        db.session.rollback()
        flash('An error occurred while updating password', 'danger')
        print(f"Error updating password: {str(e)}")

    return redirect(url_for('dashboard.profile'))

@dashboard.route('/update-profile-picture', methods=['POST'])
@login_required
def update_profile_picture():
    if 'profile_picture' not in request.files:
        flash('No file selected', 'danger')
        return redirect(url_for('dashboard.profile'))
    
    file = request.files['profile_picture']
    if file.filename == '':
        flash('No file selected', 'danger')
        return redirect(url_for('dashboard.profile'))
    
    if file and allowed_file(file.filename):
        # Delete old profile picture if it exists
        if current_user.profile_picture:
            try:
                old_file_path = os.path.join(current_app.config['UPLOAD_FOLDER'], current_user.profile_picture)
                if os.path.exists(old_file_path):
                    os.remove(old_file_path)
            except Exception as e:
                print(f"Error deleting old profile picture: {e}")

        filename = secure_filename(file.filename)
        # Add timestamp to filename to prevent caching issues
        filename = f"{int(datetime.utcnow().timestamp())}_{filename}"
        file.save(os.path.join(current_app.config['UPLOAD_FOLDER'], filename))
        
        try:
            current_user.profile_picture = filename
            db.session.commit()
            flash('Profile picture updated successfully!', 'success')
        except Exception as e:
            db.session.rollback()
            flash('Error updating profile picture', 'danger')
            print(f"Database error: {e}")
            
    return redirect(url_for('dashboard.profile'))

def allowed_file(filename):
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS
           
@dashboard.route('/assets/uploads/<filename>', methods=['GET'])
def get_profile_picture(filename):
    return send_from_directory(current_app.config['UPLOAD_FOLDER'], filename)
