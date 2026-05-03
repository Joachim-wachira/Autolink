import requests
from flask import current_app

def reverse_geocode(lat, lng):
    try:
        api_key = current_app.config['GOOGLE_MAPS_API_KEY']
        if not api_key:
            return None
            
        url = f"https://maps.googleapis.com/maps/api/geocode/json?latlng={lat},{lng}&key={api_key}"
        response = requests.get(url)
        data = response.json()
        
        if data['status'] == 'OK':
            return data['results'][0]['formatted_address']
        return None
    except Exception as e:
        print(f"Geocoding error: {e}")
        return None
