from datetime import datetime
from . import db
from werkzeug.security import generate_password_hash, check_password_hash
import json

class User(db.Model):
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    phone = db.Column(db.String(20), nullable=False, unique=True)
    password_hash = db.Column(db.String(255), nullable=False)
    
    # Role: driver, mechanic, spareshop, admin
    role = db.Column(db.String(20), nullable=False, index=True)
    
    # Approval status for mechanics and spareshops
    approval_status = db.Column(db.String(20), default='approved')  # approved, pending, rejected, suspended
    is_verified = db.Column(db.Boolean, default=False)  # Verification badge
    
    # Profile
    profile_picture = db.Column(db.String(500))
    is_online = db.Column(db.Boolean, default=False)
    last_seen = db.Column(db.DateTime, default=datetime.utcnow)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Location
    latitude = db.Column(db.Float)
    longitude = db.Column(db.Float)
    location_name = db.Column(db.String(200))
    
    # Mechanic/Spareshop specific
    business_name = db.Column(db.String(100))
    specialization = db.Column(db.JSON)  # ["Toyota", "Painting", "Wiring"]
    vehicle_brands = db.Column(db.JSON)  # ["Toyota", "Volkswagen"]
    service_types = db.Column(db.JSON)  # ["painting", "wiring", "mechanics", "towing", "tyres"]
    
    # Verification documents
    id_document = db.Column(db.String(500))  # URL to ID upload
    passport_photo = db.Column(db.String(500))  # URL to passport photo
    verification_notes = db.Column(db.Text)  # Admin notes
    
    # Availability
    is_available = db.Column(db.Boolean, default=True)
    
    # Portfolio (past works)
    portfolio_items = db.relationship('PortfolioItem', backref='user', lazy='dynamic', cascade='all, delete-orphan')
    
    # Relationships
    sent_messages = db.relationship('Message', foreign_keys='Message.sender_id', backref='sender', lazy='dynamic')
    received_messages = db.relationship('Message', foreign_keys='Message.receiver_id', backref='receiver', lazy='dynamic')
    ratings_given = db.relationship('Rating', foreign_keys='Rating.rater_id', backref='rater', lazy='dynamic')
    ratings_received = db.relationship('Rating', foreign_keys='Rating.ratee_id', backref='ratee', lazy='dynamic')
    notifications = db.relationship('Notification', backref='user', lazy='dynamic', cascade='all, delete-orphan')
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
    
    def to_dict(self, include_private=False):
        data = {
            'id': self.id,
            'full_name': self.full_name,
            'email': self.email,
            'phone': self.phone,
            'role': self.role,
            'approval_status': self.approval_status,
            'is_verified': self.is_verified,
            'profile_picture': self.profile_picture,
            'is_online': self.is_online,
            'is_available': self.is_available,
            'last_seen': self.last_seen.isoformat() if self.last_seen else None,
            'location_name': self.location_name,
            'latitude': self.latitude,
            'longitude': self.longitude,
            'business_name': self.business_name,
            'specialization': self.specialization,
            'vehicle_brands': self.vehicle_brands,
            'service_types': self.service_types,
            'average_rating': self.get_average_rating(),
            'created_at': self.created_at.isoformat() if self.created_at else None
        }
        
        if include_private and self.role in ['mechanic', 'spareshop']:
            data.update({
                'id_document': self.id_document,
                'passport_photo': self.passport_photo,
                'verification_notes': self.verification_notes
            })
        
        return data
    
    def get_average_rating(self):
        ratings = self.ratings_received.filter_by(is_active=True).all()
        if not ratings:
            return 0
        return sum(r.rating for r in ratings) / len(ratings)

class PortfolioItem(db.Model):
    __tablename__ = 'portfolio_items'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    title = db.Column(db.String(200))
    description = db.Column(db.Text)
    file_url = db.Column(db.String(500), nullable=False)
    file_type = db.Column(db.String(20))  # image, video
    is_approved = db.Column(db.Boolean, default=False)  # Admin approval
    admin_notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Message(db.Model):
    __tablename__ = 'messages'
    
    id = db.Column(db.Integer, primary_key=True)
    sender_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    receiver_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    content = db.Column(db.Text, nullable=False)
    message_type = db.Column(db.String(20), default='text')  # text, image, location
    file_url = db.Column(db.String(500))
    is_read = db.Column(db.Boolean, default=False)
    read_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    
    def to_dict(self):
        return {
            'id': self.id,
            'sender_id': self.sender_id,
            'receiver_id': self.receiver_id,
            'content': self.content,
            'message_type': self.message_type,
            'file_url': self.file_url,
            'is_read': self.is_read,
            'read_at': self.read_at.isoformat() if self.read_at else None,
            'created_at': self.created_at.isoformat(),
            'sender': {
                'id': self.sender.id,
                'full_name': self.sender.full_name,
                'profile_picture': self.sender.profile_picture,
                'role': self.sender.role
            }
        }

class Rating(db.Model):
    __tablename__ = 'ratings'
    
    id = db.Column(db.Integer, primary_key=True)
    rater_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    ratee_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    rating = db.Column(db.Integer, nullable=False)  # 1-5
    review = db.Column(db.Text)
    job_id = db.Column(db.String(100), nullable=False, unique=True)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id,
            'rater': self.rater.full_name,
            'rating': self.rating,
            'review': self.review,
            'created_at': self.created_at.isoformat()
        }

class Notification(db.Model):
    __tablename__ = 'notifications'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    title = db.Column(db.String(200), nullable=False)
    body = db.Column(db.Text, nullable=False)
    type = db.Column(db.String(50))  # chat, approval, system, admin, payment
    is_read = db.Column(db.Boolean, default=False)
    data = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Payment(db.Model):
    __tablename__ = 'payments'
    
    id = db.Column(db.Integer, primary_key=True)
    payer_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    payee_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    currency = db.Column(db.String(10), default='KES')
    status = db.Column(db.String(20), default='pending')  # pending, completed, failed, refunded
    payment_method = db.Column(db.String(50))
    transaction_id = db.Column(db.String(100))
    description = db.Column(db.String(200))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    completed_at = db.Column(db.DateTime)

class SMSVerification(db.Model):
    __tablename__ = 'sms_verifications'
    
    id = db.Column(db.Integer, primary_key=True)
    phone = db.Column(db.String(20), nullable=False, index=True)
    code = db.Column(db.String(10), nullable=False)
    purpose = db.Column(db.String(50))  # registration, password_reset
    is_used = db.Column(db.Boolean, default=False)
    expires_at = db.Column(db.DateTime, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class ServiceRequest(db.Model):
    __tablename__ = 'service_requests'
    
    id = db.Column(db.Integer, primary_key=True)
    driver_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    provider_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    status = db.Column(db.String(20), default='pending')  # pending, accepted, completed, cancelled
    description = db.Column(db.Text)
    location = db.Column(db.String(200))
    latitude = db.Column(db.Float)
    longitude = db.Column(db.Float)
    estimated_cost = db.Column(db.Float)
    final_cost = db.Column(db.Float)
    payment_status = db.Column(db.String(20), default='pending')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    completed_at = db.Column(db.DateTime)
