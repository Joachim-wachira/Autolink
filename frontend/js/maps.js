let map = null;
let markers = [];
let directionsService = null;
let directionsRenderer = null;

function initMap() {
    const mapElement = document.getElementById('map');
    if (!mapElement || typeof google === 'undefined') return;
    
    // Default to Nairobi if no location
    const defaultLocation = { lat: -1.2921, lng: 36.8219 };
    
    map = new google.maps.Map(mapElement, {
        center: defaultLocation,
        zoom: 13,
        styles: [
            {
                "featureType": "all",
                "elementType": "geometry",
                "stylers": [{"color": "#242f3e"}]
            },
            {
                "featureType": "all",
                "elementType": "labels.text.stroke",
                "stylers": [{"visibility": "off"}]
            },
            {
                "featureType": "all",
                "elementType": "labels.text.fill",
                "stylers": [{"color": "#746855"}]
            },
            {
                "featureType": "administrative.locality",
                "elementType": "labels.text.fill",
                "stylers": [{"color": "#d59563"}]
            },
            {
                "featureType": "poi",
                "elementType": "labels.text.fill",
                "stylers": [{"color": "#d59563"}]
            },
            {
                "featureType": "poi.park",
                "elementType": "geometry",
                "stylers": [{"color": "#263c3f"}]
            },
            {
                "featureType": "poi.park",
                "elementType": "labels.text.fill",
                "stylers": [{"color": "#6b9a76"}]
            },
            {
                "featureType": "road",
                "elementType": "geometry",
                "stylers": [{"color": "#38414e"}]
            },
            {
                "featureType": "road",
                "elementType": "geometry.stroke",
                "stylers": [{"color": "#212a37"}]
            },
            {
                "featureType": "road",
                "elementType": "labels.text.fill",
                "stylers": [{"color": "#9ca5b3"}]
            },
            {
                "featureType": "road.highway",
                "elementType": "geometry",
                "stylers": [{"color": "#746855"}]
            },
            {
                "featureType": "road.highway",
                "elementType": "geometry.stroke",
                "stylers": [{"color": "#1f2835"}]
            },
            {
                "featureType": "road.highway",
                "elementType": "labels.text.fill",
                "stylers": [{"color": "#f3d19c"}]
            },
            {
                "featureType": "transit",
                "elementType": "geometry",
                "stylers": [{"color": "#2f3948"}]
            },
            {
                "featureType": "transit.station",
                "elementType": "labels.text.fill",
                "stylers": [{"color": "#d59563"}]
            },
            {
                "featureType": "water",
                "elementType": "geometry",
                "stylers": [{"color": "#17263c"}]
            },
            {
                "featureType": "water",
                "elementType": "labels.text.fill",
                "stylers": [{"color": "#515c6d"}]
            },
            {
                "featureType": "water",
                "elementType": "labels.text.stroke",
                "stylers": [{"visibility": "off"}]
            }
        ]
    });
    
    directionsService = new google.maps.DirectionsService();
    directionsRenderer = new google.maps.DirectionsRenderer({
        map: map,
        suppressMarkers: true
    });
    
    // Try to get user location
    if (navigator.geolocation) {
        navigator.geolocation.getCurrentPosition(
            (position) => {
                const pos = {
                    lat: position.coords.latitude,
                    lng: position.coords.longitude
                };
                map.setCenter(pos);
                addMarker(pos, 'You are here', 'driver');
            },
            () => {
                console.log('Error: The Geolocation service failed.');
            }
        );
    }
    
    // Load nearby providers
    loadProvidersOnMap();
}

function addMarker(position, title, type, userData = null) {
    const icon = {
        path: google.maps.SymbolPath.CIRCLE,
        scale: type === 'driver' ? 10 : 12,
        fillColor: type === 'driver' ? '#3b82f6' : '#f59e0b',
        fillOpacity: 1,
        strokeColor: '#fff',
        strokeWeight: 2
    };
    
    const marker = new google.maps.Marker({
        position: position,
        map: map,
        title: title,
        icon: icon,
        animation: google.maps.Animation.DROP
    });
    
    if (userData) {
        const infoWindow = new google.maps.InfoWindow({
            content: `
                <div style="color: #333; padding: 10px; max-width: 200px;">
                    <h4 style="margin: 0 0 5px 0;">${userData.business_name || userData.full_name}</h4>
                    <p style="margin: 0; font-size: 12px;">${userData.specialization || 'Mechanic'}</p>
                    <p style="margin: 5px 0 0 0; font-size: 12px; color: #666;">
                        Rating: ${userData.average_rating.toFixed(1)} ⭐
                    </p>
                    <button onclick="openChat(${userData.id})" style="
                        margin-top: 10px;
                        padding: 5px 10px;
                        background: #f59e0b;
                        border: none;
                        border-radius: 5px;
                        cursor: pointer;
                        width: 100%;
                    ">Chat</button>
                </div>
            `
        });
        
        marker.addListener('click', () => {
            infoWindow.open(map, marker);
        });
    }
    
    markers.push(marker);
    return marker;
}

function clearMarkers() {
    markers.forEach(marker => marker.setMap(null));
    markers = [];
}

async function loadProvidersOnMap() {
    try {
        const position = await getCurrentPosition();
        const data = await apiRequest(`/api/users/nearby?lat=${position.lat}&lng=${position.lng}&radius=10`);
        
        clearMarkers();
        
        // Add user marker
        addMarker({ lat: position.lat, lng: position.lng }, 'You', 'driver');
        
        // Add provider markers
        data.providers.forEach(provider => {
            if (provider.latitude && provider.longitude) {
                addMarker(
                    { lat: provider.latitude, lng: provider.longitude },
                    provider.business_name || provider.full_name,
                    'provider',
                    provider
                );
            }
        });
        
    } catch (error) {
        console.error('Failed to load providers on map:', error);
    }
}

function calculateRoute(origin, destination) {
    if (!directionsService || !directionsRenderer) return;
    
    directionsService.route(
        {
            origin: origin,
            destination: destination,
            travelMode: google.maps.TravelMode.DRIVING
        },
        (response, status) => {
            if (status === 'OK') {
                directionsRenderer.setDirections(response);
                
                const route = response.routes[0];
                const leg = route.legs[0];
                
                showToast(`Distance: ${leg.distance.text}, Duration: ${leg.duration.text}`, 'info');
            } else {
                showToast('Directions request failed due to ' + status, 'error');
            }
        }
    );
}

// Initialize map when API is loaded
window.initMap = initMap;