from flask import Blueprint, request, jsonify, send_from_directory
from flask_jwt_extended import jwt_required, get_jwt_identity
from sqlalchemy import func, or_
from math import radians, cos, sin, asin, sqrt
from .models import User, Rating, Notification, Message
from . import db
from .schemas import RatingSchema, LocationUpdateSchema
from marshmallow import ValidationError
from datetime import datetime

api_bp = Blueprint('api', __name__)

def haversine(lon1, lat1, lon2, lat2):
    """Calculate the great circle distance between two points on earth (specified in decimal degrees)"""
    lon1, lat1, lon2, lat2 = map(radians, [lon1, lat1, lon2, lat2])
    dlon = lon2 - lon1
    dlat = lat2 - lat1
    a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
    c = 2 * asin(sqrt(a))
    r = 6371  # Radius of earth in kilometers
    return c * r

@api_bp.route('/uploads/<path:filename>')
def uploaded_file(filename):
    return send_from_directory('uploads', filename)

@api_bp.route('/users/nearby', methods=['GET'])
@jwt_required()
def get_nearby_users():
    current_user_id = get_jwt_identity()
    user = User.query.get_or_404(current_user_id)
    
    role = request.args.get('role', 'mechanic')
    radius = float(request.args.get('radius', 10))  # Default 10km
    lat = float(request.args.get('lat', user.latitude or 0))
    lng = float(request.args.get('lng', user.longitude or 0))
    
    # Query mechanics/shop owners within radius
    providers = User.query.filter(
        User.role.in_(['mechanic', 'shop_owner']),
        User.is_active == True,
        User.is_available == True,
        User.id != current_user_id
    ).all()
    
    nearby = []
    for provider in providers:
        if provider.latitude and provider.longitude:
            distance = haversine(lng, lat, provider.longitude, provider.latitude)
            if distance <= radius:
                provider_data = provider.to_dict()
                provider_data['distance'] = round(distance, 2)
                nearby.append(provider_data)
    
    # Sort by distance
    nearby.sort(key=lambda x: x['distance'])
    
    return jsonify({
        'providers': nearby,
        'center': {'lat': lat, 'lng': lng},
        'radius': radius
    }), 200

@api_bp.route('/users/search', methods=['GET'])
@jwt_required()
def search_users():
    town = request.args.get('town', '').lower()
    role = request.args.get('role', 'mechanic')
    
    query = User.query.filter(
        User.role.in_(['mechanic', 'shop_owner']),
        User.is_active == True
    )
    
    if town:
        query = query.filter(func.lower(User.location_name).contains(town))
    
    users = query.all()
    return jsonify([u.to_dict() for u in users]), 200

@api_bp.route('/users/<int:user_id>', methods=['GET'])
@jwt_required()
def get_user(user_id):
    user = User.query.get_or_404(user_id)
    return jsonify(user.to_dict()), 200

@api_bp.route('/users/<int:user_id>/ratings', methods=['GET'])
@jwt_required()
def get_user_ratings(user_id):
    ratings = Rating.query.filter_by(ratee_id=user_id).order_by(Rating.created_at.desc()).all()
    return jsonify([r.to_dict() for r in ratings]), 200

@api_bp.route('/ratings', methods=['POST'])
@jwt_required()
def create_rating():
    try:
        schema = RatingSchema()
        data = schema.load(request.get_json())
        
        current_user_id = get_jwt_identity()
        
        # Check if already rated this job
        existing = Rating.query.filter_by(job_id=data['job_id']).first()
        if existing:
            return jsonify({'error': 'You have already rated this job'}), 409
        
        rating = Rating(
            rater_id=current_user_id,
            ratee_id=data['ratee_id'],
            rating=data['rating'],
            review=data.get('review', ''),
            job_id=data['job_id']
        )
        
        db.session.add(rating)
        db.session.commit()
        
        return jsonify({'message': 'Rating submitted successfully'}), 201
        
    except ValidationError as err:
        return jsonify({'error': err.messages}), 400

@api_bp.route('/location', methods=['PUT'])
@jwt_required()
def update_location():
    try:
        schema = LocationUpdateSchema()
        data = schema.load(request.get_json())
        
        current_user_id = get_jwt_identity()
        user = User.query.get_or_404(current_user_id)
        
        user.latitude = data['latitude']
        user.longitude = data['longitude']
        if 'location_name' in data:
            user.location_name = data['location_name']
        
        db.session.commit()
        
        return jsonify({
            'message': 'Location updated',
            'location': {
                'lat': user.latitude,
                'lng': user.longitude,
                'name': user.location_name
            }
        }), 200
        
    except ValidationError as err:
        return jsonify({'error': err.messages}), 400

@api_bp.route('/availability', methods=['PUT'])
@jwt_required()
def update_availability():
    current_user_id = get_jwt_identity()
    user = User.query.get_or_404(current_user_id)
    
    data = request.get_json()
    user.is_available = data.get('is_available', user.is_available)
    user.is_online = data.get('is_online', user.is_online)
    
    db.session.commit()
    
    return jsonify({
        'is_available': user.is_available,
        'is_online': user.is_online
    }), 200

@api_bp.route('/admin/users', methods=['GET'])
@jwt_required()
def get_all_users():
    current_user_id = get_jwt_identity()
    admin = User.query.get_or_404(current_user_id)
    
    if admin.role != 'admin':
        return jsonify({'error': 'Unauthorized'}), 403
    
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 50, type=int)
    
    users = User.query.paginate(page=page, per_page=per_page, error_out=False)
    
    return jsonify({
        'users': [u.to_dict() for u in users.items],
        'total': users.total,
        'pages': users.pages,
        'current_page': page
    }), 200

@api_bp.route('/admin/users/<int:user_id>/suspend', methods=['POST'])
@jwt_required()
def suspend_user(user_id):
    current_user_id = get_jwt_identity()
    admin = User.query.get_or_404(current_user_id)
    
    if admin.role != 'admin':
        return jsonify({'error': 'Unauthorized'}), 403
    
    user = User.query.get_or_404(user_id)
    user.is_active = False
    db.session.commit()
    
    return jsonify({'message': f'User {user.full_name} suspended'}), 200

@api_bp.route('/admin/users/<int:user_id>', methods=['DELETE'])
@jwt_required()
def delete_user(user_id):
    current_user_id = get_jwt_identity()
    admin = User.query.get_or_404(current_user_id)
    
    if admin.role != 'admin':
        return jsonify({'error': 'Unauthorized'}), 403
    
    user = User.query.get_or_404(user_id)
    db.session.delete(user)
    db.session.commit()
    
    return jsonify({'message': 'User deleted permanently'}), 200

@api_bp.route('/admin/stats', methods=['GET'])
@jwt_required()
def get_stats():
    current_user_id = get_jwt_identity()
    admin = User.query.get_or_404(current_user_id)
    
    if admin.role != 'admin':
        return jsonify({'error': 'Unauthorized'}), 403
    
    stats = {
        'total_users': User.query.count(),
        'drivers': User.query.filter_by(role='driver').count(),
        'mechanics': User.query.filter_by(role='mechanic').count(),
        'shop_owners': User.query.filter_by(role='shop_owner').count(),
        'online_users': User.query.filter_by(is_online=True).count(),
        'total_messages': Message.query.count(),
        'total_ratings': Rating.query.count()
    }
    
    return jsonify(stats), 200

@api_bp.route('/notifications', methods=['GET'])
@jwt_required()
def get_notifications():
    current_user_id = get_jwt_identity()
    notifications = Notification.query.filter_by(
        user_id=current_user_id,
        is_read=False
    ).order_by(Notification.created_at.desc()).all()
    
    return jsonify([n.to_dict() for n in notifications]), 200

@api_bp.route('/notifications/<int:notification_id>/read', methods=['POST'])
@jwt_required()
def mark_notification_read(notification_id):
    current_user_id = get_jwt_identity()
    notification = Notification.query.filter_by(
        id=notification_id,
        user_id=current_user_id
    ).first_or_404()
    
    notification.is_read = True
    db.session.commit()
    
    return jsonify({'message': 'Marked as read'}), 200