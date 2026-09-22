"""Local development server. Use: python run.py"""
import os

from dotenv import load_dotenv
from flask import request

from app import app
from application import socketio
from models import db, User, SecretKey

load_dotenv()

if __name__ == "__main__":
    with app.app_context():
        admin = User.query.filter_by(email="admin@bemyshipper.com").first()
        if not admin:
            admin = User(
                first_name="Cellou",
                last_name="Tounkara",
                email="admin@bemyshipper.com",
                phone="+1234567890",
                role="admin",
                isEmailVerified=True,
                isAccountVerified=True,
                hasVerifiedBadge=True,
            )
            admin.set_password("okok123123")
            db.session.add(admin)
            db.session.commit()
            print("Admin user created successfully")
        else:
            admin.role = "admin"
            admin.set_password("okok123123")
            db.session.add(admin)
            db.session.commit()
            print("Admin user already exists")

        membership_price = SecretKey.query.filter_by(slug="stripe-membership-price-id").first()
        if not membership_price:
            membership_price = SecretKey(
                name="Membership Price ID",
                slug="stripe-membership-price-id",
                key="price_1OqXXXXXXXXXXXXXX",
            )
            db.session.add(membership_price)
            print("Membership price slug created successfully")
        else:
            print("Membership price slug already exists")

        badge_price = SecretKey.query.filter_by(slug="stripe-verify-badge-price-id").first()
        if not badge_price:
            badge_price = SecretKey(
                name="Verification Badge Price ID",
                slug="stripe-verify-badge-price-id",
                key="price_1OqXXXXXXXXXXXXXX",
            )
            db.session.add(badge_price)
            print("Badge price slug created successfully")
        else:
            print("Badge price slug already exists")

        db.session.commit()

    @app.context_processor
    def inject_canonical_url():
        return {"canonical_url": f"https://{request.host}{request.path}"}

    socketio.run(
        app,
        host="0.0.0.0",
        debug=True,
        port=os.getenv("PORT"),
        allow_unsafe_werkzeug=True,
    )
