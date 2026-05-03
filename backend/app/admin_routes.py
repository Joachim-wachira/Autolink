from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from .models import User, Rating, PortfolioItem, Message, Notification
from . import db

admin_bp = Blueprint('admin', __name__)

def check_admin():
    current_user_id = get_jwt_identity()
    admin = User.query.get_or_404(current_user_id)
    if admin.role != 'admin':
        return False
    return True

@admin_bp.route('/users', methods=['GET'])
@jwt_required()
def get_all_users():
    if not check_admin():
        return jsonify({'error': 'Unauthorized'}), 403
    
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 50, type=int)
    role = request.args.get('role')
    status = request.args.get('status')
    
    query = User.query
    if role:
        query = query.filter_by(role=role)
    if status:
        query = query.filter_by(approval_status=status)
    
    users = query.paginate(page=page, per_page=per_page, error_out=False)
    
    return jsonify({
        'users': [u.to_dict(include_private=True) for u in users.items],
        'total': users.total,
        'pages': users.pages,
        'current_page': page
    }), 200

@admin_bp.route('/users/<int:user_id>/approve', methods=['POST'])
@jwt_required()
def approve_user(user_id):
    if not check_admin():
        return jsonify({'error': 'Unauthorized'}), 403
    
    user = User.query.get_or_404(user_id)
    action = request.json.get('action', 'approve')  # approve, reject, suspend
    
    if action == 'approve':
        user.approval_status = 'approved'
        user.is_verified = True
        message = f'User {user.full_name} approved and verified'
    elif action == 'reject':
        user.approval_status = 'rejected'
        message = f'User {user.full_name} rejected'
    elif action == 'suspend':
        user.approval_status = 'suspended'
        user.is_active = False
        message = f'User {user.full_name} suspended'
    elif action == 'reactivate':
        user.approval_status = 'approved'
        user.is_active = True
        message = f'User {user.full_name} reactivated'
    else:
        return jsonify({'error': 'Invalid action'}), 400
    
    db.session.commit()
    
    # Notify user
    notif = Notification(
        user_id=user.id,
        title=f'Account {action.capitalize()}d',
        body=f'Your account has been {action}d by the admin.',
        type='approval'
    )
    db.session.add(notif)
    db.session.commit()
    
    return jsonify({'message': message}), 200

@admin_bp.route('/users/<int:user_id>', methods=['DELETE'])
@jwt_required()
def delete_user(user_id):
    if not check_admin():
        return jsonify({'error': 'Unauthorized'}), 403
    
    user = User.query.get_or_404(user_id)
    db.session.delete(user)
    db.session.commit()
    
    return jsonify({'message': 'User deleted permanently'}), 200

@admin_bp.route('/portfolio', methods=['GET'])
@jwt_required()
def get_pending_portfolio():
    if not check_admin():
        return jsonify({'error': 'Unauthorized'}), 403
    
    items = PortfolioItem.query.filter_by(is_approved=False).order_by(PortfolioItem.created_at.desc()).all()
    return jsonify([{
        'id': item.id,
        'user': item.user.to_dict(),
        'title': item.title,
        'description': item.description,
        'file_url': item.file_url,
        'file_type': item.file_type,
        'created_at': item.created_at.isoformat()
    } for item in items]), 200

@admin_bp.route('/portfolio/<int:item_id>/approve', methods=['POST'])
@jwt_required()
def approve_portfolio(item_id):
    if not check_admin():
        return jsonify({'error': 'Unauthorized'}), 403
    
    item = PortfolioItem.query.get_or_404(item_id)
    item.is_approved = True
    item.admin_notes = request.json.get('notes', '')
    db.session.commit()
    
    # Notify user
    notif = Notification(
        user_id=item.user_id,
        title='Portfolio Item Approved',
        body=f'Your portfolio item "{item.title}" has been approved.',
        type='approval'
    )
    db.session.add(notif)
    db.session.commit()
    
    return jsonify({'message': 'Portfolio item approved'}), 200

@admin_bp.route('/portfolio/<int:item_id>', methods=['DELETE'])
@jwt_required()
def delete_portfolio(item_id):
    if not check_admin():
        return jsonify({'error': 'Unauthorized'}), 403
    
    item = PortfolioItem.query.get_or_404(item_id)
    db.session.delete(item)
    db.session.commit()
    
    return jsonify({'message': 'Portfolio item deleted'}), 200

@admin_bp.route('/ratings/<int:rating_id>', methods=['PUT'])
@jwt_required()
def moderate_rating(rating_id):
    if not check_admin():
        return jsonify({'error': 'Unauthorized'}), 403
    
    rating = Rating.query.get_or_404(rating_id)
    action = request.json.get('action')
    
    if action == 'hide':
        rating.is_active = False
    elif action == 'show':
        rating.is_active = True
    else:
        return jsonify({'error': 'Invalid action'}), 400
    
    db.session.commit()
    return jsonify({'message': f'Rating {action}n'}), 200

@admin_bp.route('/chats/<int:user1_id>/<int:user2_id>', methods=['GET'])
@jwt_required()
def view_conversation(user1_id, user2_id):
    if not check_admin():
        return jsonify({'error': 'Unauthorized'}), 403
    
    messages = Message.query.filter(
        ((Message.sender_id == user1_id) & (Message.receiver_id == user2_id)) |
        ((Message.sender_id == user2_id) & (Message.receiver_id == user1_id))
    ).order_by(Message.created_at.asc()).all()
    
    return jsonify([m.to_dict() for m in messages]), 200

@admin_bp.route('/stats', methods=['GET'])
@jwt_required()
def get_stats():
    if not check_admin():
        return jsonify({'error': 'Unauthorized'}), 403
    
    stats = {
        'total_users': User.query.count(),
        'drivers': User.query.filter_by(role='driver').count(),
        'mechanics': User.query.filter_by(role='mechanic').count(),
        'spareshops': User.query.filter_by(role='spareshop').count(),
        'pending_approvals': User.query.filter_by(approval_status='pending').count(),
        'online_users': User.query.filter_by(is_online=True).count(),
        'total_messages': Message.query.count(),
        'total_ratings': Rating.query.count(),
        'total_revenue': 0  # Will be updated with payment data
    }
    
    return jsonify(stats), 200

@admin_bp.route('/notifications', methods=['POST'])
@jwt_required()
def send_notification():
    if not check_admin():
        return jsonify({'error': 'Unauthorized'}), 403
    
    data = request.get_json()
    target = data.get('target', 'all')
    title = data.get('title')
    body = data.get('body')
    
    if not title or not body:
        return jsonify({'error': 'Title and body required'}), 400
    
    if target == 'all':
        users = User.query.filter_by(is_active=True).all()
    elif target == 'drivers':
        users = User.query.filter_by(role='driver', is_active=True).all()
    elif target == 'mechanics':
        users = User.query.filter_by(role='mechanic', is_active=True).all()
    elif target == 'spareshops':
        users = User.query.filter_by(role='spareshop', is_active=True).all()
    elif target == 'pending':
        users = User.query.filter_by(approval_status='pending').all()
    else:
        return jsonify({'error': 'Invalid target'}), 400
    
    for user in users:
        notif = Notification(
            user_id=user.id,
            title=title,
            body=body,
            type='admin'
        )
        db.session.add(notif)
    
    db.session.commit()
    return jsonify({'message': f'Notification sent to {len(users)} users'}), 200
