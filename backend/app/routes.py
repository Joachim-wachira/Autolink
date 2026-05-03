from flask import Blueprint, request, jsonify, send_from_directory
from flask_jwt_extended import jwt_required, get_jwt_identity
from sqlalchemy import func, or_
from math import radians, cos, sin, asin, sqrt
from .models import User, Rating, Notification, PortfolioItem, ServiceRequest
from . import db

api_bp = Blueprint('api', __name__)

def haversine(lon1, lat1, lon2, lat2):
    lon1, lat1, lon2, lat2 = map(radians, [lon1, lat1, lon2, lat2])
    dlon = lon2 - lon1
    dlat = lat2 - lat1
    a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
    c = 2 * asin(sqrt(a))
    r = 6371
    return c * r

@api_bp.route('/uploads/<path:filename>')
def uploaded_file(filename):
    return send_from_directory('uploads', filename)

@api_bp.route('/users/nearby', methods=['GET'])
@jwt_required()
def get_nearby_providers():
    current_user_id = get_jwt_identity()
    user = User.query.get_or_404(current_user_id)
    
    role = request.args.get('role', 'mechanic')
    radius = float(request.args.get('radius', 10))
    lat = float(request.args.get('lat', user.latitude or 0))
    lng = float(request.args.get('lng', user.longitude or 0))
    
    # Filter by specialization if provided
    vehicle_brand = request.args.get('vehicle_brand')
    service_type = request.args.get('service_type')
    
    providers = User.query.filter(
        User.role.in_(['mechanic', 'spareshop']),
        User.is_active == True,
        User.approval_status == 'approved',
        User.is_available == True,
        User.latitude != None,
        User.longitude != None,
        User.id != current_user_id
    )
    
    if vehicle_brand:
        providers = providers.filter(User.vehicle_brands.contains([vehicle_brand]))
    if service_type:
        providers = providers.filter(User.service_types.contains([service_type]))
    
    nearby = []
    for provider in providers.all():
        distance = haversine(lng, lat, provider.longitude, provider.latitude)
        if distance <= radius:
            provider_data = provider.to_dict()
            provider_data['distance'] = round(distance, 2)
            nearby.append(provider_data)
    
    nearby.sort(key=lambda x: x['distance'])
    
    return jsonify({'providers': nearby, 'center': {'lat': lat, 'lng': lng}, 'radius': radius}), 200

@api_bp.route('/users/search', methods=['GET'])
@jwt_required()
def search_users():
    town = request.args.get('town', '').lower()
    vehicle_brand = request.args.get('vehicle_brand')
    service_type = request.args.get('service_type')
    
    query = User.query.filter(
        User.role.in_(['mechanic', 'spareshop']),
        User.is_active == True,
        User.approval_status == 'approved'
    )
    
    if town:
        query = query.filter(func.lower(User.location_name).contains(town))
    if vehicle_brand:
        query = query.filter(User.vehicle_brands.contains([vehicle_brand]))
    if service_type:
        query = query.filter(User.service_types.contains([service_type]))
    
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
    ratings = Rating.query.filter_by(ratee_id=user_id, is_active=True).order_by(Rating.created_at.desc()).all()
    return jsonify([r.to_dict() for r in ratings]), 200

@api_bp.route('/users/<int:user_id>/portfolio', methods=['GET'])
@jwt_required()
def get_user_portfolio(user_id):
    items = PortfolioItem.query.filter_by(user_id=user_id, is_approved=True).order_by(PortfolioItem.created_at.desc()).all()
    return jsonify([{
        'id': item.id,
        'title': item.title,
        'description': item.description,
        'file_url': item.file_url,
        'file_type': item.file_type,
        'created_at': item.created_at.isoformat()
    } for item in items]), 200

@api_bp.route('/ratings', methods=['POST'])
@jwt_required()
def create_rating():
    try:
        data = request.get_json()
        current_user_id = get_jwt_identity()
        
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
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 400

@api_bp.route('/location', methods=['PUT'])
@jwt_required()
def update_location():
    try:
        data = request.get_json()
        current_user_id = get_jwt_identity()
        user = User.query.get_or_404(current_user_id)
        
        user.latitude = data['latitude']
        user.longitude = data['longitude']
        if 'location_name' in data:
            user.location_name = data['location_name']
        
        db.session.commit()
        
        return jsonify({
            'message': 'Location updated',
            'location': {'lat': user.latitude, 'lng': user.longitude, 'name': user.location_name}
        }), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 400

@api_bp.route('/availability', methods=['PUT'])
@jwt_required()
def update_availability():
    current_user_id = get_jwt_identity()
    user = User.query.get_or_404(current_user_id)
    
    data = request.get_json()
    user.is_available = data.get('is_available', user.is_available)
    user.is_online = data.get('is_online', user.is_online)
    
    db.session.commit()
    
    return jsonify({'is_available': user.is_available, 'is_online': user.is_online}), 200

@api_bp.route('/portfolio', methods=['POST'])
@jwt_required()
def upload_portfolio():
    try:
        current_user_id = get_jwt_identity()
        
        if 'file' not in request.files:
            return jsonify({'error': 'No file provided'}), 400
        
        file = request.files['file']
        if not file or not allowed_file(file.filename):
            return jsonify({'error': 'Invalid file'}), 400
        
        filename = secure_filename(f"portfolio_{current_user_id}_{file.filename}")
        filepath = os.path.join('uploads/portfolios', filename)
        file.save(filepath)
        
        item = PortfolioItem(
            user_id=current_user_id,
            title=request.form.get('title', ''),
            description=request.form.get('description', ''),
            file_url=f"/uploads/portfolios/{filename}",
            file_type='image' if file.filename.rsplit('.', 1)[1].lower() in {'png', 'jpg', 'jpeg', 'gif'} else 'video',
            is_approved=False  # Requires admin approval
        )
        
        db.session.add(item)
        db.session.commit()
        
        return jsonify({'message': 'Portfolio item uploaded. Pending admin approval.', 'item': {
            'id': item.id,
            'title': item.title,
            'file_url': item.file_url,
            'is_approved': item.is_approved
        }}), 201
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@api_bp.route('/service-requests', methods=['POST'])
@jwt_required()
def create_service_request():
    try:
        current_user_id = get_jwt_identity()
        data = request.get_json()
        
        request_obj = ServiceRequest(
            driver_id=current_user_id,
            provider_id=data['provider_id'],
            description=data.get('description', ''),
            location=data.get('location'),
            latitude=data.get('latitude'),
            longitude=data.get('longitude'),
            estimated_cost=data.get('estimated_cost')
        )
        
        db.session.add(request_obj)
        db.session.commit()
        
        # Create notification for provider
        notif = Notification(
            user_id=data['provider_id'],
            title='New Service Request',
            body=f'You have a new service request from {User.query.get(current_user_id).full_name}',
            type='service_request',
            data=json.dumps({'request_id': request_obj.id})
        )
        db.session.add(notif)
        db.session.commit()
        
        return jsonify({'message': 'Service request created', 'request_id': request_obj.id}), 201
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@api_bp.route('/notifications', methods=['GET'])
@jwt_required()
def get_notifications():
    current_user_id = get_jwt_identity()
    notifications = Notification.query.filter_by(user_id=current_user_id, is_read=False).order_by(Notification.created_at.desc()).all()
    return jsonify([{
        'id': n.id,
        'title': n.title,
        'body': n.body,
        'type': n.type,
        'is_read': n.is_read,
        'created_at': n.created_at.isoformat()
    } for n in notifications]), 200

@api_bp.route('/notifications/<int:notification_id>/read', methods=['POST'])
@jwt_required()
def mark_notification_read(notification_id):
    current_user_id = get_jwt_identity()
    notification = Notification.query.filter_by(id=notification_id, user_id=current_user_id).first_or_404()
    notification.is_read = True
    db.session.commit()
    return jsonify({'message': 'Marked as read'}), 200
