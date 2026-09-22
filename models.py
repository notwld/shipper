from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin
from datetime import datetime, timedelta

db = SQLAlchemy()

class User(UserMixin, db.Model):
    __tablename__ = 'user'
    id = db.Column(db.Integer, primary_key=True)
    first_name = db.Column(db.String(100), nullable=False)
    last_name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100), nullable=False, unique=True)
    phone = db.Column(db.String(20), nullable=False)
    password = db.Column(db.String(200), nullable=False)
    role = db.Column(db.String(50), nullable=False, default='user')
    isEmailVerified = db.Column(db.Boolean, default=False)
    isAccountVerified = db.Column(db.Boolean, default=False)
    hasVerifiedBadge = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    stripe_customer_id = db.Column(db.String(100), unique=True, nullable=True)
    subscription_status = db.Column(db.String(20), default='inactive')
    badge_status = db.Column(db.String(20), default='inactive')
    subscription_start = db.Column(db.DateTime, nullable=True)
    badge_start = db.Column(db.DateTime, nullable=True)
    profile_picture = db.Column(db.String(200), nullable=True)
    
    contacts = db.relationship('Contact', foreign_keys='Contact.initiator_id', backref='initiator', lazy=True)
    contacts_received = db.relationship('Contact', foreign_keys='Contact.recipient_id', backref='recipient', lazy=True)
    orders = db.relationship('Order', backref='user', lazy=True)
    trips = db.relationship('Trip', backref='user', lazy=True)

    
    def set_password(self, password):
        self.password = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password, password)

    def __repr__(self):
        return f'<User {self.username}>'
    
class Order(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    earliest_date = db.Column(db.Date, nullable=False)  # Earliest date to receive the order
    last_date = db.Column(db.Date, nullable=False)  # Last date to receive the order
    order_from_location = db.Column(db.String(200), nullable=False)  # The location to order from
    deliverer_location = db.Column(db.String(200), nullable=False)  # Deliverer's location
    weight = db.Column(db.Float, nullable=False)  # Weight of the order
    comments = db.Column(db.Text, nullable=True)  # Optional comments

    # Images, max 4
    image1 = db.Column(db.String(200), nullable=True)
    image2 = db.Column(db.String(200), nullable=True)
    image3 = db.Column(db.String(200), nullable=True)
    image4 = db.Column(db.String(200), nullable=True)
    status = db.Column(db.String(20), default='active', nullable=True)  # Order status
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)  # The user placing the order
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)  # Order creation timestamp

    def __init__(self, earliest_date, last_date, order_from_location, deliverer_location, weight, user_id, comments=None, images=None):
        self.earliest_date = earliest_date
        self.last_date = last_date
        self.order_from_location = order_from_location
        self.deliverer_location = deliverer_location
        self.weight = weight
        self.user_id = user_id
        self.comments = comments
        if images:
            if len(images) > 4:
                raise ValueError("Maximum 4 images allowed")
            if len(images) > 0: self.image1 = images[0]
            if len(images) > 1: self.image2 = images[1]
            if len(images) > 2: self.image3 = images[2]
            if len(images) > 3: self.image4 = images[3]


class Trip(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    traveling_from = db.Column(db.String(200), nullable=False)  # Traveling from location
    traveling_to = db.Column(db.String(200), nullable=False)  # Traveling to location
    traveling_date = db.Column(db.Date, nullable=False)  # Date of the trip
    weight = db.Column(db.Float, nullable=False)  # Weight limit
    comments = db.Column(db.Text, nullable=True)  # Optional comments
    status = db.Column(db.String(20), default='active', nullable=True)  # Trip status
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)  # The user who created the trip
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)  # Trip creation timestamp

    def __init__(self, traveling_from, traveling_to, traveling_date, weight, user_id, comments=None):
        self.traveling_from = traveling_from
        self.traveling_to = traveling_to
        self.traveling_date = traveling_date
        self.weight = weight
        self.user_id = user_id
        self.comments = comments


class Contact(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    initiator_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    recipient_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    status = db.Column(db.String(20), default='INIT', nullable=False)
    order_id = db.Column(db.Integer, db.ForeignKey('order.id'), nullable=True)
    trip_id = db.Column(db.Integer, db.ForeignKey('trip.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    def __init__(self, initiator_id, recipient_id, status=None, order_id=None, trip_id=None):
        self.initiator_id = initiator_id
        self.recipient_id = recipient_id
        self.status = status
        self.order_id = order_id
        self.trip_id = trip_id


class Message(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    contact_id = db.Column(db.Integer, db.ForeignKey('contact.id'), nullable=False)
    sender_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    # Add relationships
    contact = db.relationship('Contact', backref='messages')
    sender = db.relationship('User', backref='messages_sent')

    def to_dict(self):
        return {
            'id': self.id,
            'contact_id': self.contact_id,
            'sender_id': self.sender_id,
            'content': self.content,
            'created_at': self.created_at.isoformat()
        }
    
class SecretKey(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    slug = db.Column(db.String(100), nullable=False, unique=True, default='default')
    key = db.Column(db.String(100), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    def __init__(self, name, slug, key):
        self.name = name
        self.slug = slug
        self.key = key

    def __repr__(self):
        return f'<SecretKey {self.id}>'
    
import uuid


class AcceptedOrder(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    uuid = db.Column(db.String(50), unique=True, nullable=False, default=lambda: str(uuid.uuid4())[:10])  
    order_id = db.Column(db.Integer, db.ForeignKey('order.id'), nullable=True)
    trip_id = db.Column(db.Integer, db.ForeignKey('trip.id'), nullable=True)
    contact_id = db.Column(db.Integer, db.ForeignKey('contact.id'), nullable=False)
    attribute_type = db.Column(db.String(50), nullable=False) 
    weight = db.Column(db.Float, nullable=True)
    price_per_kg = db.Column(db.Float, nullable=True)
    product_details = db.Column(db.Text, nullable=True)
    total_price = db.Column(db.Float, nullable=False)
    status = db.Column(db.String(20), default='pending')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Add relationship
    contact = db.relationship('Contact', backref='accepted_orders')

    def __repr__(self):
        return f'<AcceptedOrder {self.id}>'

class Notification(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    message_id = db.Column(db.Integer, db.ForeignKey('message.id'), nullable=False)
    read = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Add relationships
    user = db.relationship('User', backref='notifications')
    message = db.relationship('Message', backref='notifications')