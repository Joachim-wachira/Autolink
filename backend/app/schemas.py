from marshmallow import Schema, fields, validate, ValidationError

class UserRegistrationSchema(Schema):
    full_name = fields.String(required=True, validate=validate.Length(min=2, max=100))
    email = fields.Email(required=True)
    phone = fields.String(required=True, validate=validate.Length(min=10, max=20))
    password = fields.String(required=True, validate=validate.Length(min=6), load_only=True)
    role = fields.String(required=True, validate=validate.OneOf(['driver', 'mechanic', 'shop_owner']))
    business_name = fields.String(validate=validate.Length(max=100))
    specialization = fields.String(validate=validate.Length(max=200))
    latitude = fields.Float()
    longitude = fields.Float()
    location_name = fields.String(validate=validate.Length(max=200))

class UserLoginSchema(Schema):
    email = fields.Email(required=True)
    password = fields.String(required=True, load_only=True)

class MessageSchema(Schema):
    content = fields.String(required=True, validate=validate.Length(min=1, max=5000))
    receiver_id = fields.Integer(required=True)
    message_type = fields.String(validate=validate.OneOf(['text', 'image', 'location']), default='text')

class RatingSchema(Schema):
    ratee_id = fields.Integer(required=True)
    rating = fields.Integer(required=True, validate=validate.Range(min=1, max=5))
    review = fields.String(validate=validate.Length(max=1000))
    job_id = fields.String(required=True)

class LocationUpdateSchema(Schema):
    latitude = fields.Float(required=True)
    longitude = fields.Float(required=True)
    location_name = fields.String()