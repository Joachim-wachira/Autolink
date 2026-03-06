import requests
from flask import current_app

def reverse_geocode(lat, lng):
    """Convert coordinates to human-readable address using Google Maps API"""
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

def get_distance_matrix(origins, destinations):
    """Get distance matrix from Google Maps API"""
    try:
        api_key = current_app.config['GOOGLE_MAPS_API_KEY']
        if not api_key:
            return None
            
        origins_str = '|'.join([f"{lat},{lng}" for lat, lng in origins])
        destinations_str = '|'.join([f"{lat},{lng}" for lat, lng in destinations])
        
        url = f"https://maps.googleapis.com/maps/api/distancematrix/json?origins={origins_str}&destinations={destinations_str}&key={api_key}"
        response = requests.get(url)
        return response.json()
    except Exception as e:
        print(f"Distance matrix error: {e}")
        return None

# AI Car Assistant responses
CAR_PROBLEMS = {
    'engine': {
        'keywords': ['engine', 'won\'t start', 'cranking', 'turning over', 'stalling'],
        'causes': ['Dead battery', 'Faulty starter motor', 'Fuel pump issues', 'Ignition system failure'],
        'safety': 'Do not attempt to jump start if you smell fuel. Check for leaks first.',
        'urgency': 'High - Do not drive until inspected'
    },
    'brakes': {
        'keywords': ['brake', 'squealing', 'grinding', 'soft pedal', 'pulling'],
        'causes': ['Worn brake pads', 'Low brake fluid', 'Air in brake lines', 'Warped rotors'],
        'safety': 'Reduce speed gradually. Use engine braking. Do not drive at high speeds.',
        'urgency': 'Critical - Stop driving immediately'
    },
    'overheating': {
        'keywords': ['overheating', 'temperature', 'coolant', 'steam', 'hot'],
        'causes': ['Low coolant level', 'Faulty thermostat', 'Water pump failure', 'Radiator blockage'],
        'safety': 'Turn off AC, turn on heater to max, pull over safely. Do not open radiator cap when hot.',
        'urgency': 'High - Stop driving immediately to prevent engine damage'
    },
    'tire': {
        'keywords': ['tire', 'flat', 'puncture', 'vibration', 'pulling'],
        'causes': ['Puncture', 'Slow leak', 'Uneven wear', 'Wheel misalignment'],
        'safety': 'If flat, pull over safely. Do not drive on flat tire. Use hazard lights.',
        'urgency': 'Medium - Can drive slowly to nearest service station if not completely flat'
    },
    'transmission': {
        'keywords': ['transmission', 'gear', 'slipping', 'jerking', 'delay'],
        'causes': ['Low transmission fluid', 'Worn clutch', 'Solenoid issues', 'Software problems'],
        'safety': 'Avoid sudden acceleration. Drive in lower gears if automatic.',
        'urgency': 'Medium-High - Schedule service soon to prevent costly repairs'
    },
    'electrical': {
        'keywords': ['battery', 'light', 'electrical', 'fuse', 'dim'],
        'causes': ['Weak battery', 'Alternator failure', 'Corroded terminals', 'Parasitic drain'],
        'safety': 'Check battery terminals for corrosion. Keep jumper cables available.',
        'urgency': 'Medium - May strand you if battery dies completely'
    }
}

def get_ai_assistant_response(problem_description):
    """Rule-based AI car assistant"""
    problem_lower = problem_description.lower()
    
    for category, data in CAR_PROBLEMS.items():
        if any(keyword in problem_lower for keyword in data['keywords']):
            return {
                'category': category,
                'possible_causes': data['causes'],
                'safety_measures': data['safety'],
                'urgency_level': data['urgency'],
                'recommendation': 'Based on your description, I recommend finding a certified mechanic nearby using our map feature.'
            }
    
    # Default response
    return {
        'category': 'unknown',
        'possible_causes': ['Requires professional diagnosis'],
        'safety_measures': 'If the vehicle feels unsafe to drive, do not drive it. Use hazard lights and pull over safely.',
        'urgency_level': 'Unknown - Please consult a mechanic',
        'recommendation': 'I recommend describing the issue in more detail or consulting with a mechanic through our chat feature.'
    }