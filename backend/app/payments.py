from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
import stripe
from .config import Config
from .models import Payment, User, Notification
from . import db

payments_bp = Blueprint('payments', __name__)
stripe.api_key = Config.STRIPE_SECRET_KEY

@payments_bp.route('/config', methods=['GET'])
@jwt_required()
def get_config():
    return jsonify({'publishableKey': Config.STRIPE_PUBLISHABLE_KEY}), 200

@payments_bp.route('/create-payment-intent', methods=['POST'])
@jwt_required()
def create_payment():
    try:
        current_user_id = get_jwt_identity()
        data = request.get_json()
        
        # Create payment record
        payment = Payment(
            payer_id=current_user_id,
            payee_id=data['provider_id'],
            amount=Config.CONNECTION_FEE,
            currency='KES',
            description=f'Connection fee for service with provider {data["provider_id"]}'
        )
        db.session.add(payment)
        db.session.flush()
        
        # Create Stripe PaymentIntent
        intent = stripe.PaymentIntent.create(
            amount=int(Config.CONNECTION_FEE * 100),  # Convert to cents
            currency='kes',
            metadata={'payment_id': payment.id}
        )
        
        payment.transaction_id = intent.id
        db.session.commit()
        
        return jsonify({
            'clientSecret': intent.client_secret,
            'payment_id': payment.id
        }), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 400

@payments_bp.route('/webhook', methods=['POST'])
def webhook():
    payload = request.get_data()
    sig_header = request.headers.get('Stripe-Signature')
    
    try:
        event = stripe.Webhook.construct_event(payload, sig_header, webhook_secret)
    except ValueError:
        return jsonify({'error': 'Invalid payload'}), 400
    except stripe.error.SignatureVerificationError:
        return jsonify({'error': 'Invalid signature'}), 400
    
    if event['type'] == 'payment_intent.succeeded':
        payment_intent = event['data']['object']
        payment_id = payment_intent['metadata']['payment_id']
        
        payment = Payment.query.get(payment_id)
        if payment:
            payment.status = 'completed'
            payment.completed_at = datetime.utcnow()
            db.session.commit()
            
            # Notify provider
            notif = Notification(
                user_id=payment.payee_id,
                title='Payment Received',
                body=f'You received KES {payment.amount} for a service connection.',
                type='payment'
            )
            db.session.add(notif)
            db.session.commit()
    
    return jsonify({'status': 'success'}), 200
