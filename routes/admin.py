from datetime import datetime
from flask import Blueprint, jsonify, request, render_template,redirect,flash,url_for,current_app,send_file
from models import db, User,Order,Trip,Message,Contact,SecretKey,AcceptedOrder,Notification
from flask_login import login_user,logout_user,login_required,current_user
from sqlalchemy.exc import SQLAlchemyError
import logging,re
from itsdangerous import URLSafeTimedSerializer
import stripe
import pandas as pd
from io import BytesIO

admin = Blueprint('admin', __name__)

@admin.route('/admin', methods=['GET', 'POST'])
def admin_dashboard():
    if current_user.is_authenticated and current_user.role.lower() == 'admin':
        # Get basic stats
        total_users = User.query.count()
        total_trips = Trip.query.count()
        verified_users = int(User.query.filter_by(subscription_status="active").count())
        membership_revenue = 0  # Initialize default value
        
        membership_price_id = SecretKey.query.filter_by(slug='stripe-membership-price-id').first()
        if membership_price_id:
            try:
                price = stripe.Price.retrieve(membership_price_id.key)
                membership_revenue = float(((verified_users) * price.unit_amount) / 100)
            except Exception as e:
                logging.error(f"Error retrieving Stripe membership price: {str(e)}")
                # Keep default value of 0

        # Get top users with most orders
        top_users = db.session.query(
            User,
            db.func.count(Order.id).label('order_count')
        ).join(Order).group_by(User).order_by(
            db.text('order_count DESC')
        ).limit(5).all()

        # Monthly orders data for chart - SQLite version
        monthly_orders = db.session.query(
            db.func.strftime('%Y-%m', Order.created_at).label('month'),
            db.func.count(Order.id).label('count')
        ).group_by('month').order_by('month').limit(6).all()
        accepted_orders = AcceptedOrder.query.filter_by().all()
        data = []
        for order in accepted_orders:
            
            contact = Contact.query.get(order.contact_id)
            trip = Trip.query.get(contact.trip_id)
            if not trip or not contact:
                continue
                
            initiator = User.query.get(contact.initiator_id)
            recipient = User.query.get(contact.recipient_id)
            
            data.append({
                "order_code": order.uuid,
                "trip": {
                    "id": trip.id,
                    "traveling_from": trip.traveling_from,
                    "traveling_to": trip.traveling_to,
                    "traveling_date": trip.traveling_date.strftime("%Y-%m-%d"),
                    "weight": trip.weight,
                    "comments": trip.comments
                },
                "traveler": {
                    "id": recipient.id,
                    "first_name": recipient.first_name,
                    "last_name": recipient.last_name,
                    "email": recipient.email,              
                },
                "recipient": {
                    "id": initiator.id,
                    "first_name": initiator.first_name,
                    "last_name": initiator.last_name,
                    "email": initiator.email
                },
                "acceptance_condition": {
                    "id": order.id,
                    "status": order.status,
                    "created_at": order.created_at.strftime("%Y-%m-%d %H:%M:%S"),
                    "weight": order.weight,
                    "price_per_kg": order.price_per_kg,
                    "product_details": order.product_details,
                    "attribute_type": order.attribute_type,
                    "total_price": order.total_price
                }

            })
        print(data)
        return render_template('admin/dashboard.html', 
            user=current_user,
            total_users=total_users,
            total_orders=len(data),
            total_trips=total_trips,
            verified_users=verified_users,
            membership_revenue=membership_revenue,
            top_users=top_users,
            monthly_orders=monthly_orders,
            accepted_orders=data
        )
    else:
        if request.method == 'POST':
            email = request.form.get('email', '').strip()
            password = request.form.get('password', '')

            # Input validation
            if not email or not password:
                flash('Email and password are required.', 'danger')
                return redirect(url_for('admin.admin_dashboard'))

            try:
                user = User.query.filter_by(email=email).first()

                if not user:
                    flash('Invalid email or password.', 'danger')
                    return redirect(url_for('admin.admin_dashboard'))

                if user.check_password(password):
                    if user.role.lower() == 'admin':
                        login_user(user)
                        flash('Login successful!', 'success')
                        return redirect(url_for('admin.admin_dashboard'))
                    else:
                        flash('You are not authorized to access this page.', 'danger')
                        return redirect(url_for('admin.admin_dashboard'))
                else:
                    flash('Invalid email or password.', 'danger')

            except Exception as e:
                logging.error(f"Login error: {str(e)}")
                flash('Something went wrong. Please try again later.', 'danger')
        else:
            return render_template('admin/login.html')
    flash('You are not authorized to access this page.', 'danger')
    return redirect(url_for('admin.admin_dashboard'))
    

@admin.route('/admin/logout')
def admin_logout():
    logout_user()
    return redirect(url_for('admin.admin_dashboard'))

@admin.route('/admin/users')
def admin_users():
    if current_user.is_authenticated and current_user.role.lower() == 'admin':
        all_users = User.query.all()
        return render_template('admin/users.html', user=current_user, users=[
            {
                'id': user.id,
                'first_name': user.first_name,
                'last_name': user.last_name,
                'isEmailVerified': user.isEmailVerified,
                'isAccountVerified': user.isAccountVerified,
                'email': user.email,
                'phone': user.phone,
                'role': user.role,
                'badge_status': user.badge_status,
                'orders': len(user.orders),
                'trips': len(user.trips),
            } for user in all_users

        ])
    else:
        return redirect(url_for('admin.admin_dashboard'))
    
@admin.route('/admin/update-user/<int:id>', methods=['POST'])
def update_user(id):
    if not (current_user.is_authenticated and current_user.role.lower() == 'admin'):
        return jsonify({'error': 'Unauthorized'}), 401

    try:
        user = User.query.get_or_404(id)
        data = request.get_json()

        user.first_name = data.get('first_name', user.first_name)
        user.last_name = data.get('last_name', user.last_name)
        user.email = data.get('email', user.email)
        user.phone = data.get('phone', user.phone)
        user.role = data.get('role', user.role)

        # Update password only if provided
        new_password = data.get('new_password')
        if new_password and new_password.strip():
            user.set_password(new_password)

        db.session.commit()

        return jsonify({
            'id': int(user.id),
            'first_name': user.first_name,
            'last_name': user.last_name,
            'email': user.email,
            'phone': user.phone,
            'role': user.role,
            'isEmailVerified': user.isEmailVerified,
            'isAccountVerified': user.isAccountVerified,
            'orders': len(user.orders),
            'trips': len(user.trips)
        }), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@admin.route('/admin/delete-user/<int:user_id>', methods=['DELETE'])
def delete_user(user_id):
    try:
        # Delete regular orders
        orders = Order.query.filter_by(user_id=user_id).all()
        for order in orders:
            db.session.delete(order)

        # Delete trips
        trips = Trip.query.filter_by(user_id=user_id).all()
        for trip in trips:
            db.session.delete(trip)

        # Delete contacts and their associated messages and accepted orders
        contacts = Contact.query.filter((Contact.initiator_id == user_id) | (Contact.recipient_id == user_id)).all()
        for contact in contacts:
            # Delete accepted orders associated with this contact
            accepted_orders = AcceptedOrder.query.filter_by(contact_id=contact.id).all()
            for accepted_order in accepted_orders:
                db.session.delete(accepted_order)
            
            # Delete notifications for messages in this contact
            messages = Message.query.filter_by(contact_id=contact.id).all()
            for message in messages:
                # Delete notifications associated with this message
                notifications = Notification.query.filter_by(message_id=message.id).all()
                for notification in notifications:
                    db.session.delete(notification)
                # Delete the message
                db.session.delete(message)
            
            # Delete the contact
            db.session.delete(contact)

        # Delete any remaining notifications for the user
        user_notifications = Notification.query.filter_by(user_id=user_id).all()
        for notification in user_notifications:
            db.session.delete(notification)

        # Finally delete the user
        user = User.query.get_or_404(user_id)
        db.session.delete(user)
        db.session.commit()
        return jsonify({'message': 'User deleted successfully'}), 200
    except Exception as e:
        print(e)
        db.session.rollback()
        return jsonify({'error': str(e)}), 500
    
@admin.route('/admin/orders')
def admin_orders():
    if current_user.is_authenticated and current_user.role.lower() == 'admin':
        all_orders = Order.query.all()
        return render_template('admin/orders.html', user=current_user, orders=[
            {
                'id': order.id,
                'user_id': order.user_id,
                'earliest_date': order.earliest_date.strftime('%Y-%m-%d'),
                'last_date': order.last_date.strftime('%Y-%m-%d'),
                'order_from_location': order.order_from_location,
                'deliverer_location': order.deliverer_location,
                'weight': order.weight,
                'comments': order.comments,
                'created_at': order.created_at.strftime('%Y-%m-%d %H:%M:%S'),
                'user_name': f"{order.user.first_name} {order.user.last_name}",
                'user_email': order.user.email
            } for order in all_orders
        ])
    else:
        return redirect(url_for('admin.admin_dashboard'))

@admin.route('/admin/update-order/<int:id>', methods=['POST'])
def update_order(id):
    if not (current_user.is_authenticated and current_user.role.lower() == 'admin'):
        return jsonify({'error': 'Unauthorized'}), 401

    try:
        order = Order.query.get_or_404(id)
        data = request.get_json()

        order.earliest_date = datetime.strptime(data['earliest_date'], '%Y-%m-%d').date()
        order.last_date = datetime.strptime(data['last_date'], '%Y-%m-%d').date()
        order.order_from_location = data['order_from_location']
        order.deliverer_location = data['deliverer_location']
        order.weight = float(data['weight'])
        order.comments = data['comments']

        db.session.commit()

        return jsonify({
            'id': order.id,
            'earliest_date': order.earliest_date.strftime('%Y-%m-%d'),
            'last_date': order.last_date.strftime('%Y-%m-%d'),
            'order_from_location': order.order_from_location,
            'deliverer_location': order.deliverer_location,
            'weight': order.weight,
            'comments': order.comments,
            'user_name': f"{order.user.first_name} {order.user.last_name}",
            'user_email': order.user.email,
            'created_at': order.created_at.strftime('%Y-%m-%d %H:%M:%S')
        }), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@admin.route('/admin/delete-order/<int:order_id>', methods=['DELETE'])
def delete_order(order_id):
    try:
        order = Order.query.get_or_404(order_id)
        db.session.delete(order)
        db.session.commit()
        return jsonify({'message': 'Order deleted successfully'}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500
    
@admin.route('/admin/settings')
def admin_settings():
    if current_user.is_authenticated and current_user.role.lower() == 'admin':
        all_keys = SecretKey.query.all()
        return render_template('admin/settings.html', user=current_user, keys=[
            {
                'id': key.id,
                'name': key.name,
                'slug': key.slug,
                'key': key.key,
                'created_at': key.created_at.strftime('%Y-%m-%d %H:%M:%S'),
                'updated_at': key.updated_at.strftime('%Y-%m-%d %H:%M:%S')
            } for key in all_keys
        ])
    else:
        return redirect(url_for('admin.admin_dashboard'))

@admin.route('/admin/create-key', methods=['POST'])
def create_key():
    if not (current_user.is_authenticated and current_user.role.lower() == 'admin'):
        return jsonify({'error': 'Unauthorized'}), 401

    try:
        data = request.get_json()
        new_key = SecretKey(key=data['key'])
        new_key.name = data['name']
        new_key.slug = data['slug']
        
        db.session.add(new_key)
        db.session.commit()

        return jsonify({
            'id': new_key.id,
            'name': new_key.name,
            'slug': new_key.slug,
            'key': new_key.key,
            'created_at': new_key.created_at.strftime('%Y-%m-%d %H:%M:%S'),
            'updated_at': new_key.updated_at.strftime('%Y-%m-%d %H:%M:%S')
        }), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@admin.route('/admin/delete-key/<int:key_id>', methods=['DELETE'])
def delete_key(key_id):
    try:
        key = SecretKey.query.get_or_404(key_id)
        db.session.delete(key)
        db.session.commit()
        return jsonify({'message': 'Key deleted successfully'}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500
    
@admin.route('/admin/update-key/<int:key_id>', methods=['POST'])
def update_key(key_id):
    if not (current_user.is_authenticated and current_user.role.lower() == 'admin'):
        return jsonify({'error': 'Unauthorized'}), 401

    try:
        key = SecretKey.query.get_or_404(key_id)
        data = request.get_json()

        key.name = data['name']
        key.slug = data['slug']
        key.key = data['key']

        db.session.commit()

        return jsonify({
            'id': key.id,
            'name': key.name,
            'slug': key.slug,
            'key': key.key,
            'created_at': key.created_at.strftime('%Y-%m-%d %H:%M:%S'),
            'updated_at': key.updated_at.strftime('%Y-%m-%d %H:%M:%S')
        }), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

                                
        

@admin.route('/admin/trips')
def admin_trips():
    if current_user.is_authenticated and current_user.role.lower() == 'admin':
        all_trips = Trip.query.all()
        return render_template('admin/trips.html', user=current_user, trips=[
            {
                'id': trip.id,
                'user_id': trip.user_id,
                'traveling_date': trip.traveling_date.strftime('%Y-%m-%d'),
                'traveling_from': trip.traveling_from,
                'traveling_to': trip.traveling_to,
                'weight': trip.weight,
                'comments': trip.comments,
                'created_at': trip.created_at.strftime('%Y-%m-%d %H:%M:%S'),
                'user_name': f"{trip.user.first_name} {trip.user.last_name}",
                'user_email': trip.user.email
            } for trip in all_trips
        ])
    else:
        return redirect(url_for('admin.admin_dashboard'))

@admin.route('/admin/update-trip/<int:id>', methods=['POST'])
def update_trip(id):
    if not (current_user.is_authenticated and current_user.role.lower() == 'admin'):
        return jsonify({'error': 'Unauthorized'}), 401

    try:
        trip = Trip.query.get_or_404(id)
        data = request.get_json()

        trip.traveling_date = datetime.strptime(data['traveling_date'], '%Y-%m-%d').date()
        trip.traveling_from = data['traveling_from']
        trip.traveling_to = data['traveling_to']
        trip.weight = float(data['weight'])
        trip.comments = data['comments']

        db.session.commit()

        return jsonify({
            'id': trip.id,
            'traveling_date': trip.traveling_date.strftime('%Y-%m-%d'),
            'traveling_from': trip.traveling_from,
            'traveling_to': trip.traveling_to,
            'weight': trip.weight,
            'comments': trip.comments,
            'user_name': f"{trip.user.first_name} {trip.user.last_name}",
            'user_email': trip.user.email,
            'created_at': trip.created_at.strftime('%Y-%m-%d %H:%M:%S')
        }), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@admin.route('/admin/delete-trip/<int:trip_id>', methods=['DELETE'])
def delete_trip(trip_id):
    try:
        trip = Trip.query.get_or_404(trip_id)
        db.session.delete(trip)
        db.session.commit()
        return jsonify({'message': 'Trip deleted successfully'}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500
    

@admin.route('/admin/export-deals')
@login_required
def export_deals():
    if current_user.is_authenticated and current_user.role.lower() == 'admin':
        accepted_orders = AcceptedOrder.query.all()
        data = []
        
        for order in accepted_orders:
            contact = Contact.query.get(order.contact_id)
            trip = Trip.query.get(contact.trip_id) if contact else None
            if not trip or not contact:
                continue

            initiator = User.query.get(contact.initiator_id)
            recipient = User.query.get(contact.recipient_id)

            data.append({
                "Order Code": order.uuid,
                "Trip ID": trip.id,
                "Traveling From": trip.traveling_from,
                "Traveling To": trip.traveling_to,
                "Traveling Date": trip.traveling_date.strftime("%Y-%m-%d"),
                "Trip Weight": trip.weight,
                "Trip Comments": trip.comments,
                "Traveler ID": recipient.id,
                "Traveler First Name": recipient.first_name,
                "Traveler Last Name": recipient.last_name,
                "Traveler Email": recipient.email,
                "Recipient ID": initiator.id,
                "Recipient First Name": initiator.first_name,
                "Recipient Last Name": initiator.last_name,
                "Recipient Email": initiator.email,
                "Order Status": order.status,
                "Order Created At": order.created_at.strftime("%Y-%m-%d %H:%M:%S"),
                "Order Weight": order.weight,
                "Price Per KG": order.price_per_kg,
                "Product Details": order.product_details,
                "Attribute Type": order.attribute_type,
                "Total Price": order.total_price,
            })

        # Convert to DataFrame
        df = pd.DataFrame(data)

        # Create Excel in memory
        output = BytesIO()
        writer = pd.ExcelWriter(output, engine='xlsxwriter')
        df.to_excel(writer, sheet_name='Deals', index=False)
        writer.close()
        output.seek(0)

        return send_file(
            output,
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            as_attachment=True,
            download_name="BEMYSHIPPER-Deals.xlsx"
        )

    return redirect(url_for('admin.admin_dashboard'))
