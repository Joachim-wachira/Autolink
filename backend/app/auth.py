from flask import Blueprint, request, jsonify
from flask_jwt_extended import create_access_token, create_refresh_token, jwt_required, get_jwt_identity
from .models import User, SMSVerification, Notification
from . import db
from .sms_service import SMSService
import os
from werkzeug.utils import secure_filename
from datetime import datetime, timedelta
import random

auth_bp = Blueprint('auth', __name__)
sms_service = SMSService()

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'pdf'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@auth_bp.route('/register', methods=['POST'])
def register():
    try:
        data = request.form.to_dict()
        
        # Validate required fields
        required = ['full_name', 'email', 'phone', 'password', 'role']
        for field in required:
            if not data.get(field):
                return jsonify({'error': f'{field} is required'}), 400
        
        role = data['role']
        
        # Check if email exists
        if User.query.filter_by(email=data['email']).first():
            return jsonify({'error': 'Email already registered'}), 409
        
        # Check if phone exists
        if User.query.filter_by(phone=data['phone']).first():
            return jsonify({'error': 'Phone number already registered'}), 409
        
        # Create user
        user = User(
            full_name=data['full_name'],
            email=data['email'],
            phone=data['phone'],
            role=role,
            business_name=data.get('business_name'),
            location_name=data.get('location_name'),
            latitude=data.get('latitude', type=float),
            longitude=data.get('longitude', type=float)
        )
        user.set_password(data['password'])
        
        # Handle specializations for mechanics/spareshops
        if role in ['mechanic', 'spareshop']:
            user.approval_status = 'pending'
            user.vehicle_brands = request.form.getlist('vehicle_brands[]') or []
            user.service_types = request.form.getlist('service_types[]') or []
            user.specialization = {
                'vehicle_brands': user.vehicle_brands,
                'service_types': user.service_types
            }
            
            # Handle ID document upload
            if 'id_document' in request.files:
                file = request.files['id_document']
                if file and allowed_file(file.filename):
                    filename = secure_filename(f"id_{data['phone']}_{file.filename}")
                    filepath = os.path.join('uploads/ids', filename)
                    file.save(filepath)
                    user.id_document = f"/uploads/ids/{filename}"
            
            # Handle passport photo upload
            if 'passport_photo' in request.files:
                file = request.files['passport_photo']
                if file and allowed_file(file.filename):
                    filename = secure_filename(f"passport_{data['phone']}_{file.filename}")
                    filepath = os.path.join('uploads/passports', filename)
                    file.save(filepath)
                    user.passport_photo = f"/uploads/passports/{filename}"
        
        # Handle profile picture
        if 'profile_picture' in request.files:
            file = request.files['profile_picture']
            if file and allowed_file(file.filename):
                filename = secure_filename(f"profile_{data['phone']}_{file.filename}")
                filepath = os.path.join('uploads', filename)
                file.save(filepath)
                user.profile_picture = f"/uploads/{filename}"
        
        db.session.add(user)
        db.session.commit()
        
        # Send notification to admins about pending approval
        if role in ['mechanic', 'spareshop']:
            admins = User.query.filter_by(role='admin').all()
            for admin in admins:
                notif = Notification(
                    user_id=admin.id,
                    title='New Provider Registration',
                    body=f'{user.full_name} ({role}) has registered and is pending approval.',
                    type='approval',
                    data=json.dumps({'user_id': user.id, 'type': 'pending_approval'})
                )
                db.session.add(notif)
            db.session.commit()
        
        # Generate tokens
        access_token = create_access_token(identity=user.id)
        refresh_token = create_refresh_token(identity=user.id)
        
        message = 'Registration successful.'
        if role in ['mechanic', 'spareshop']:
            message = 'Registration successful. Your account is pending admin verification.'
        
        return jsonify({
            'message': message,
            'user': user.to_dict(),
            'access_token': access_token,
            'refresh_token': refresh_token
        }), 201
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@auth_bp.route('/login', methods=['POST'])
def login():
    try:
        data = request.get_json()
        
        if not data or not data.get('email') or not data.get('password'):
            return jsonify({'error': 'Email and password are required'}), 400
        
        user = User.query.filter_by(email=data['email']).first()
        
        if not user or not user.check_password(data['password']):
            return jsonify({'error': 'Invalid email or password'}), 401
        
        if not user.is_active:
            return jsonify({'error': 'Account has been suspended'}), 403
        
        # Check approval status for mechanics and spareshops
        if user.role in ['mechanic', 'spareshop']:
            if user.approval_status == 'pending':
                return jsonify({
                    'error': 'Your account is pending admin approval. Please wait for verification.',
                    'approval_status': 'pending'
                }), 403
            elif user.approval_status == 'rejected':
                return jsonify({
                    'error': 'Your account has been rejected. Please contact support.',
                    'approval_status': 'rejected'
                }), 403
            elif user.approval_status == 'suspended':
                return jsonify({
                    'error': 'Your account has been suspended. Please contact support.',
                    'approval_status': 'suspended'
                }), 403
        
        # Update online status
        user.is_online = True
        user.last_seen = datetime.utcnow()
        db.session.commit()
        
        access_token = create_access_token(identity=user.id)
        refresh_token = create_refresh_token(identity=user.id)
        
        return jsonify({
            'user': user.to_dict(),
            'access_token': access_token,
            'refresh_token': refresh_token
        }), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@auth_bp.route('/send-sms-code', methods=['POST'])
def send_sms_code():
    try:
        data = request.get_json()
        phone = data.get('phone')
        purpose = data.get('purpose', 'registration')
        
        if not phone:
            return jsonify({'error': 'Phone number is required'}), 400
        
        # Generate 6-digit code
        code = ''.join([str(random.randint(0, 9)) for _ in range(6)])
        
        # Save to database
        verification = SMSVerification(
            phone=phone,
            code=code,
            purpose=purpose,
            expires_at=datetime.utcnow() + timedelta(minutes=10)
        )
        db.session.add(verification)
        db.session.commit()
        
        # Send SMS (mock if Twilio not configured)
        if sms_service.is_configured():
            sms_service.send_sms(phone, f'Your Mech verification code is: {code}. Valid for 10 minutes.')
        else:
            print(f"SMS Code for {phone}: {code}")  # For development
        
        return jsonify({'message': 'Verification code sent', 'code': code if not sms_service.is_configured() else None}), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@auth_bp.route('/verify-sms-code', methods=['POST'])
def verify_sms_code():
    try:
        data = request.get_json()
        phone = data.get('phone')
        code = data.get('code')
        
        if not phone or not code:
            return jsonify({'error': 'Phone and code are required'}), 400
        
        verification = SMSVerification.query.filter_by(
            phone=phone,
            code=code,
            is_used=False
        ).order_by(SMSVerification.created_at.desc()).first()
        
        if not verification:
            return jsonify({'error': 'Invalid code'}), 400
        
        if verification.expires_at < datetime.utcnow():
            return jsonify({'error': 'Code has expired'}), 400
        
        verification.is_used = True
        db.session.commit()
        
        return jsonify({'message': 'Phone verified successfully'}), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@auth_bp.route('/refresh', methods=['POST'])
@jwt_required(refresh=True)
def refresh():
    current_user_id = get_jwt_identity()
    access_token = create_access_token(identity=current_user_id)
    return jsonify({'access_token': access_token}), 200

@auth_bp.route('/logout', methods=['POST'])
@jwt_required()
def logout():
    current_user_id = get_jwt_identity()
    user = User.query.get(current_user_id)
    if user:
        user.is_online = False
        user.last_seen = datetime.utcnow()
        db.session.commit()
    return jsonify({'message': 'Logged out successfully'}), 200

@auth_bp.route('/me', methods=['GET'])
@jwt_required()
def get_current_user():
    current_user_id = get_jwt_identity()
    user = User.query.get_or_404(current_user_id)
    return jsonify(user.to_dict(include_private=True)), 200

@auth_bp.route('/update-profile', methods=['PUT'])
@jwt_required()
def update_profile():
    try:
        current_user_id = get_jwt_identity()
        user = User.query.get_or_404(current_user_id)
        data = request.form.to_dict()
        
        # Update fields
        if 'full_name' in data:
            user.full_name = data['full_name']
        if 'phone' in data:
            # Check if phone is taken by another user
            existing = User.query.filter_by(phone=data['phone']).first()
            if existing and existing.id != user.id:
                return jsonify({'error': 'Phone number already in use'}), 409
            user.phone = data['phone']
        if 'business_name' in data:
            user.business_name = data['business_name']
        if 'location_name' in data:
            user.location_name = data['location_name']
        if 'latitude' in data:
            user.latitude = float(data['latitude'])
        if 'longitude' in data:
            user.longitude = float(data['longitude'])
        
        # Update specializations
        if 'vehicle_brands[]' in request.form:
            user.vehicle_brands = request.form.getlist('vehicle_brands[]')
            user.specialization['vehicle_brands'] = user.vehicle_brands
        if 'service_types[]' in request.form:
            user.service_types = request.form.getlist('service_types[]')
            user.specialization['service_types'] = user.service_types
        
        # Handle profile picture update
        if 'profile_picture' in request.files:
            file = request.files['profile_picture']
            if file and allowed_file(file.filename):
                filename = secure_filename(f"profile_{user.phone}_{file.filename}")
                filepath = os.path.join('uploads', filename)
                file.save(filepath)
                user.profile_picture = f"/uploads/{filename}"
        
        db.session.commit()
        return jsonify({'message': 'Profile updated', 'user': user.to_dict(include_private=True)}), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500
