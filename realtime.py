"""Socket.IO event handlers — imported by app.py after create_app()."""
import uuid

from application import socketio
from flask_socketio import emit, join_room, rooms
from models import Contact, Message, db, User, AcceptedOrder, Notification
from flask import request, current_app
from flask_mail import Message as msg

online_users = {}
typing_users = {}

@socketio.on("send_message")
def handle_send_message(data):
    recipient_id = str(data["recipient_id"])
    message_content = data["message"]
    sender_id = str(data["sender_id"])

    print(f"Sending message - From: {sender_id}, To: {recipient_id}")

    try:
        contact = Contact.query.filter(
            ((Contact.initiator_id == sender_id) & (Contact.recipient_id == recipient_id))
            | ((Contact.initiator_id == recipient_id) & (Contact.recipient_id == sender_id))
        ).first()

        if contact:
            new_message = Message(
                contact_id=contact.id,
                sender_id=sender_id,
                content=message_content,
            )
            db.session.add(new_message)
            db.session.commit()

            notification = Notification(
                user_id=int(recipient_id),
                message_id=new_message.id,
            )
            db.session.add(notification)
            db.session.commit()

            message_data = {
                "message": new_message.content,
                "sender_id": new_message.sender_id,
                "timestamp": new_message.created_at.isoformat(),
            }

            emit("receive_message", message_data, room=recipient_id)
    except Exception as e:
        db.session.rollback()
        print(f"Error sending message: {str(e)}")
        emit("message_error", {"error": "Failed to send message"}, room=request.sid)


@socketio.on("join")
def handle_join(data):
    username = data["username"]
    user_id = str(data["user_id"])
    print(f"User {username} (ID: {user_id}) joining chat")
    join_room(user_id)

    current_rooms = rooms()
    print(f"User {username} is in rooms: {current_rooms}")

    online_users[user_id] = True
    emit("user_status", {"user_id": user_id, "status": "online"}, broadcast=True)


@socketio.on("disconnect")
def handle_disconnect():
    current_rooms = rooms()
    print(f"User disconnecting from rooms: {current_rooms}")

    for user_id in list(online_users.keys()):
        if user_id in online_users:
            del online_users[user_id]
            emit("user_status", {"user_id": user_id, "status": "offline"}, broadcast=True)


@socketio.on("typing")
def handle_typing(data):
    user_id = str(data["user_id"])
    recipient_id = str(data["recipient_id"])
    is_typing = data["is_typing"]

    print(f"Typing event - From: {user_id}, To: {recipient_id}, Status: {is_typing}")

    emit(
        "user_typing",
        {"user_id": user_id, "is_typing": is_typing},
        room=recipient_id,
    )


@socketio.on("place_order")
def handle_place_order(data):
    try:
        print(f"Received order data: {data}")
        sender_id = str(data["sender_id"])
        recipient_id = str(data["recipient_id"])
        contact = Contact.query.filter(
            ((Contact.initiator_id == sender_id) & (Contact.recipient_id == recipient_id))
            | ((Contact.initiator_id == recipient_id) & (Contact.recipient_id == sender_id))
        ).first()
        if not contact:
            raise Exception("Contact not found")
        new_order = AcceptedOrder(
            uuid=str(uuid.uuid4())[:5],
            contact_id=contact.id,
            attribute_type=data["attribute_type"],
            weight=float(data.get("weight", 0)) if data.get("weight") else None,
            price_per_kg=float(data.get("price_per_kg", 0)) if data.get("price_per_kg") else None,
            product_details=data.get("product_details"),
            total_price=float(data["total_price"]),
            trip_id=contact.order_id,
            status="pending",
        )

        db.session.add(new_order)
        db.session.commit()

        data["id"] = new_order.id

        print(f"Emitting order to rooms: {recipient_id} and {sender_id}")
        emit("receive_order", data, room=recipient_id)
        emit("receive_order", data, room=sender_id)

    except Exception as e:
        print(f"Error placing order: {str(e)}")
        emit("order_error", {"message": "Failed to place order"}, room=request.sid)


@socketio.on("respond_to_order")
def handle_order_response(data):
    try:
        print(f"Received order response: {data}")

        order = AcceptedOrder.query.filter_by(id=data["order_id"]).first()
        if order:
            order.status = data["response"]
            db.session.commit()

            contact = Contact.query.get(order.contact_id)

            if contact:
                initiator_id = str(contact.initiator_id)
                recipient_id = str(contact.recipient_id)
                initiator = User.query.get(initiator_id)
                recipient = User.query.get(recipient_id)
                print(f"Contact found: {contact.id}")
                print(f"Initiator: {initiator_id}, Recipient: {recipient_id}")

                status_data = {
                    "order_id": data["order_id"],
                    "status": data["response"],
                }
                m = msg(
                    subject="Order Update",
                    sender="info@bemyshipper.com",
                    recipients=[initiator.email, recipient.email],
                    body=f"""Order Code# {order.uuid} (This is confedential)\n\n
                            Traveler: {recipient.first_name} {recipient.last_name}\n
                            Recipient: {initiator.first_name} {initiator.last_name}\n\n
                            Order Details:\n
                            Type: {order.attribute_type}\n
                            Weight: {order.weight}\n
                            Price per kg: {order.price_per_kg}\n
                            Product Details: {order.product_details}\n
                            Total Price: ${order.total_price}\n\n
                            Status: was {data['response']} by traveler\n\n
                            For more details, visit the your BeMyShipper dashboard!
                    """,
                )
                try:
                    current_app.extensions["mail"].send(m)
                except Exception as e:
                    print(f"Error sending email: {str(e)}")
                print(f"Emitting status update to rooms: {initiator_id} and {recipient_id}")
                emit("order_status_update", status_data, room=initiator_id)
                emit("order_status_update", status_data, room=recipient_id)

            else:
                print("Contact not found")
        else:
            print("Order not found")

    except Exception as e:
        print(f"Error handling order response: {str(e)}")
        emit("order_error", {"message": "Failed to respond to order"}, room=request.sid)
