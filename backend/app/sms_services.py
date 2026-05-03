from twilio.rest import Client
from .config import Config

class SMSService:
    def __init__(self):
        self.client = None
        self.phone_number = Config.TWILIO_PHONE_NUMBER
        if Config.TWILIO_ACCOUNT_SID and Config.TWILIO_AUTH_TOKEN:
            self.client = Client(Config.TWILIO_ACCOUNT_SID, Config.TWILIO_AUTH_TOKEN)
    
    def is_configured(self):
        return self.client is not None
    
    def send_sms(self, to_phone, message):
        if not self.client:
            print(f"Would send SMS to {to_phone}: {message}")
            return False
        
        try:
            self.client.messages.create(
                body=message,
                from_=self.phone_number,
                to=to_phone
            )
            return True
        except Exception as e:
            print(f"SMS sending failed: {e}")
            return False
