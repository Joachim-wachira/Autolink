from flask import Blueprint, request, jsonify
from flask_socketio import emit, join_room, leave_room
from flask_jwt_extended import jwt_required, get_jwt_identity
from . import socketio, db
from .models import User, Message, ChatRoom, Notification
from datetime import datetime
import json

chat_bp = Blueprint('chat', __name__)

# Store online users
online_users = {}

@socketio.on('connect')
def handle_connect():
    print('Client connected')

@socketio.on('disconnect')
def handle_disconnect():
    user_id = online_users.get(request.sid)
    if user_id:
        user = User.query.get(user_id)
        if user:
            user.is_online = False
            user.last_seen = datetime.utcnow()
            db.session.commit()
            # Notify others
            emit('user_offline', {'user_id': user_id}, broadcast=True)
        del online_users[request.sid]
    print('Client disconnected')

@socketio.on('authenticate')
def handle_authenticate(data):
    from flask_jwt_extended import decode_token
    try:
        token = data.get('token')
        decoded = decode_token(token)
        user_id = decoded['sub']
        
        user = User.query.get(user_id)
        if user:
            online_users[request.sid] = user_id
            user.is_online = True
            user.last_seen = datetime.utcnow()
            db.session.commit()
            
            join_room(f"user_{user_id}")
            emit('authenticated', {'status': 'success', 'user_id': user_id})
            emit('user_online', {'user_id': user_id}, broadcast=True)
    except Exception as e:
        emit('authenticated', {'status': 'error', 'message': str(e)})

@socketio.on('join_chat')
def handle_join_chat(data):
    user_id = online_users.get(request.sid)
    if not user_id:
        return
    
    other_user_id = data.get('user_id')
    room_id = f"chat_{min(user_id, other_user_id)}_{max(user_id, other_user_id)}"
    join_room(room_id)
    
    # Mark messages as read
    Message.query.filter_by(
        sender_id=other_user_id,
        receiver_id=user_id,
        is_read=False
    ).update({
        'is_read': True,
        'read_at': datetime.utcnow()
    })
    db.session.commit()
    
    # Get chat history
    messages = Message.query.filter(
        ((Message.sender_id == user_id) & (Message.receiver_id == other_user_id)) |
        ((Message.sender_id == other_user_id) & (Message.receiver_id == user_id))
    ).order_by(Message.created_at.asc()).all()
    
    emit('chat_history', {'messages': [m.to_dict() for m in messages]})

@socketio.on('send_message')
def handle_send_message(data):
    user_id = online_users.get(request.sid)
    if not user_id:
        emit('error', {'message': 'Not authenticated'})
        return
    
    receiver_id = data.get('receiver_id')
    content = data.get('content')
    message_type = data.get('message_type', 'text')
    
    # Save message
    message = Message(
        sender_id=user_id,
        receiver_id=receiver_id,
        content=content,
        message_type=message_type
    )
    db.session.add(message)
    db.session.commit()
    
    room_id = f"chat_{min(user_id, receiver_id)}_{max(user_id, receiver_id)}"
    
    # Send to receiver if online
    emit('new_message', message.to_dict(), room=room_id)
    
    # Send notification to receiver
    receiver_room = f"user_{receiver_id}"
    emit('notification', {
        'type': 'chat',
        'title': 'New Message',
        'body': f"You have a new message",
        'data': {'sender_id': user_id, 'message_id': message.id}
    }, room=receiver_room)
    
    # Create notification record
    notification = Notification(
        user_id=receiver_id,
        title='New Message',
        body='You have received a new message',
        type='chat',
        data=json.dumps({'sender_id': user_id})
    )
    db.session.add(notification)
    db.session.commit()

@socketio.on('typing')
def handle_typing(data):
    user_id = online_users.get(request.sid)
    if user_id:
        receiver_id = data.get('receiver_id')
        room_id = f"chat_{min(user_id, receiver_id)}_{max(user_id, receiver_id)}"
        emit('typing', {'user_id': user_id}, room=room_id, include_self=False)

@socketio.on('stop_typing')
def handle_stop_typing(data):
    user_id = online_users.get(request.sid)
    if user_id:
        receiver_id = data.get('receiver_id')
        room_id = f"chat_{min(user_id, receiver_id)}_{max(user_id, receiver_id)}"
        emit('stop_typing', {'user_id': user_id}, room=room_id, include_self=False)

@chat_bp.route('/conversations', methods=['GET'])
@jwt_required()
def get_conversations():
    current_user_id = get_jwt_identity()
    
    # Get unique conversations
    sent_to = db.session.query(Message.receiver_id).filter(
        Message.sender_id == current_user_id
    ).distinct().all()
    
    received_from = db.session.query(Message.sender_id).filter(
        Message.receiver_id == current_user_id
    ).distinct().all()
    
    user_ids = set([r[0] for r in sent_to] + [r[0] for r in received_from])
    
    conversations = []
    for uid in user_ids:
        user = User.query.get(uid)
        if user:
            last_message = Message.query.filter(
                ((Message.sender_id == current_user_id) & (Message.receiver_id == uid)) |
                ((Message.sender_id == uid) & (Message.receiver_id == current_user_id))
            ).order_by(Message.created_at.desc()).first()
            
            unread_count = Message.query.filter_by(
                sender_id=uid,
                receiver_id=current_user_id,
                is_read=False
            ).count()
            
            conversations.append({
                'user': user.to_dict(),
                'last_message': last_message.to_dict() if last_message else None,
                'unread_count': unread_count
            })
    
    conversations.sort(key=lambda x: x['last_message']['created_at'] if x['last_message'] else '', reverse=True)
    return jsonify(conversations), 200