// API Configuration - Read from config.js (do not hardcode here)
const API_BASE_URL = typeof CONFIG !== 'undefined' 
    ? CONFIG.API_BASE_URL 
    : (window.location.hostname === 'localhost' 
        ? 'http://localhost:5000' 
        : 'https://autolink-backend.onrender.com');
const GOOGLE_MAPS_API_KEY = typeof CONFIG !== 'undefined' 
    ? CONFIG.GOOGLE_MAPS_API_KEY 
    : 'YOUR_API_KEY';

// Utility Functions
function showToast(message, type = 'info') {
    const container = document.querySelector('.toast-container') || createToastContainer();
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    
    const icons = {
        success: 'check-circle',
        error: 'exclamation-circle',
        info: 'info-circle'
    };
    
    toast.innerHTML = `
        <i class="fas fa-${icons[type]}"></i>
        <span>${message}</span>
    `;
    
    container.appendChild(toast);
    
    setTimeout(() => {
        toast.style.animation = 'slideIn 0.3s ease-out reverse';
        setTimeout(() => toast.remove(), 300);
    }, 5000);
}

function createToastContainer() {
    const container = document.createElement('div');
    container.className = 'toast-container';
    document.body.appendChild(container);
    return container;
}

function getToken() {
    return localStorage.getItem('access_token');
}

function getRefreshToken() {
    return localStorage.getItem('refresh_token');
}

function setTokens(access, refresh) {
    localStorage.setItem('access_token', access);
    localStorage.setItem('refresh_token', refresh);
}

function clearTokens() {
    localStorage.removeItem('access_token');
    localStorage.removeItem('refresh_token');
    localStorage.removeItem('user');
}

function getUser() {
    const user = localStorage.getItem('user');
    return user ? JSON.parse(user) : null;
}

function setUser(user) {
    localStorage.setItem('user', JSON.stringify(user));
}

// API Helper
async function apiRequest(endpoint, options = {}) {
    const url = `${API_BASE_URL}${endpoint}`;
    
    const defaultOptions = {
        headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${getToken()}`
        }
    };
    
    if (options.body && !(options.body instanceof FormData)) {
        options.body = JSON.stringify(options.body);
    }
    
    if (options.body instanceof FormData) {
        delete defaultOptions.headers['Content-Type'];
    }
    
    try {
        const response = await fetch(url, { ...defaultOptions, ...options });
        
        if (response.status === 401) {
            // Try to refresh token
            const refreshed = await refreshAccessToken();
            if (refreshed) {
                return apiRequest(endpoint, options);
            } else {
                logout();
                return null;
            }
        }
        
        const data = await response.json();
        
        if (!response.ok) {
            throw new Error(data.error || 'Request failed');
        }
        
        return data;
    } catch (error) {
        showToast(error.message, 'error');
        throw error;
    }
}

async function refreshAccessToken() {
    try {
        const response = await fetch(`${API_BASE_URL}/auth/refresh`, {
            method: 'POST',
            headers: {
                'Authorization': `Bearer ${getRefreshToken()}`
            }
        });
        
        if (response.ok) {
            const data = await response.json();
            localStorage.setItem('access_token', data.access_token);
            return true;
        }
        return false;
    } catch {
        return false;
    }
}

// Auth Functions
function checkAuth(requiredRole = null) {
    const token = getToken();
    const user = getUser();
    
    if (!token || !user) {
        window.location.href = 'register.html';
        return false;
    }
    
    if (requiredRole && user.role !== requiredRole && user.role !== 'admin') {
        showToast('Unauthorized access', 'error');
        window.location.href = 'index.html';
        return false;
    }
    
    // Update UI with user info
    const avatar = document.getElementById('userAvatar');
    if (avatar && user.profile_picture) {
        avatar.src = API_BASE_URL + user.profile_picture;
    }
    
    return true;
}

function logout() {
    apiRequest('/auth/logout', { method: 'POST' }).finally(() => {
        clearTokens();
        window.location.href = 'index.html';
    });
}

// Location Functions
function getCurrentPosition() {
    return new Promise((resolve, reject) => {
        if (!navigator.geolocation) {
            reject(new Error('Geolocation is not supported'));
            return;
        }
        
        navigator.geolocation.getCurrentPosition(
            position => resolve({
                lat: position.coords.latitude,
                lng: position.coords.longitude
            }),
            error => reject(error),
            { enableHighAccuracy: true, timeout: 10000 }
        );
    });
}

async function reverseGeocode(lat, lng) {
    try {
        const response = await fetch(
            `https://maps.googleapis.com/maps/api/geocode/json?latlng=${lat},${lng}&key=${GOOGLE_MAPS_API_KEY}`
        );
        const data = await response.json();
        
        if (data.results && data.results[0]) {
            return data.results[0].formatted_address;
        }
        return null;
    } catch (error) {
        console.error('Geocoding error:', error);
        return null;
    }
}

// Dashboard Functions
async function loadNearbyProviders() {
    const container = document.getElementById('providersList');
    if (!container) return;
    
    container.innerHTML = '<div class="skeleton" style="height: 200px;"></div>'.repeat(3);
    
    try {
        const position = await getCurrentPosition();
        const radius = document.getElementById('radiusSlider')?.value || 10;
        
        const data = await apiRequest(`/api/users/nearby?lat=${position.lat}&lng=${position.lng}&radius=${radius}`);
        
        renderProviders(data.providers, container);
    } catch (error) {
        container.innerHTML = '<p class="empty-state">Unable to load providers. Please enable location access.</p>';
    }
}

function renderProviders(providers, container) {
    if (!providers || providers.length === 0) {
        container.innerHTML = '<p class="empty-state">No providers found nearby.</p>';
        return;
    }
    
    container.innerHTML = providers.map(provider => `
        <div class="provider-card" onclick="openChat(${provider.id})">
            <div class="provider-header">
                <img src="${provider.profile_picture || 'assets/default-avatar.png'}" alt="${provider.full_name}">
                <div class="provider-info">
                    <h4>${provider.business_name || provider.full_name}</h4>
                    <div class="rating">
                        ${renderStars(provider.average_rating)}
                        <span>(${provider.average_rating.toFixed(1)})</span>
                    </div>
                </div>
            </div>
            <div class="provider-details">
                <p><i class="fas fa-map-marker-alt"></i> ${provider.location_name || 'Location not set'}</p>
                <p><i class="fas fa-road"></i> ${provider.distance} km away</p>
                ${provider.specialization ? `<p><i class="fas fa-wrench"></i> ${provider.specialization}</p>` : ''}
            </div>
            <div class="provider-actions">
                <button class="btn-chat" onclick="event.stopPropagation(); openChat(${provider.id})">
                    <i class="fas fa-comment"></i> Chat
                </button>
                <button class="btn-call" onclick="event.stopPropagation(); window.location.href='tel:${provider.phone}'">
                    <i class="fas fa-phone"></i> Call
                </button>
            </div>
        </div>
    `).join('');
}

function renderStars(rating) {
    const fullStars = Math.floor(rating);
    const hasHalf = rating % 1 >= 0.5;
    let html = '';
    
    for (let i = 0; i < fullStars; i++) {
        html += '<i class="fas fa-star"></i>';
    }
    if (hasHalf) {
        html += '<i class="fas fa-star-half-alt"></i>';
    }
    for (let i = fullStars + (hasHalf ? 1 : 0); i < 5; i++) {
        html += '<i class="far fa-star"></i>';
    }
    
    return html;
}

function setupFilters() {
    const radiusSlider = document.getElementById('radiusSlider');
    const radiusValue = document.getElementById('radiusValue');
    
    if (radiusSlider) {
        radiusSlider.addEventListener('input', (e) => {
            radiusValue.textContent = `${e.target.value} km`;
        });
        
        radiusSlider.addEventListener('change', loadNearbyProviders);
    }
    
    const searchTown = document.getElementById('searchTown');
    if (searchTown) {
        searchTown.addEventListener('input', debounce(async (e) => {
            const town = e.target.value;
            if (town.length < 2) return;
            
            try {
                const data = await apiRequest(`/api/users/search?town=${encodeURIComponent(town)}`);
                const container = document.getElementById('providersList');
                renderProviders(data, container);
            } catch (error) {
                console.error('Search error:', error);
            }
        }, 500));
    }
    
    // View toggle
    const viewToggle = document.querySelectorAll('.view-toggle button');
    viewToggle.forEach(btn => {
        btn.addEventListener('click', () => {
            viewToggle.forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            
            const view = btn.dataset.view;
            document.getElementById('providersList').classList.toggle('hidden', view === 'map');
            document.getElementById('mapView').classList.toggle('hidden', view === 'list');
            
            if (view === 'map') {
                initMap();
            }
        });
    });
}

function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}

// AI Assistant
function setupAIAssistant() {
    const modal = document.getElementById('aiModal');
    const btn = document.getElementById('aiAssistantBtn');
    const close = modal?.querySelector('.close-modal');
    const sendBtn = document.getElementById('sendAiMessage');
    const input = document.getElementById('aiInput');
    
    if (btn) {
        btn.addEventListener('click', () => {
            modal.classList.add('active');
        });
    }
    
    if (close) {
        close.addEventListener('click', () => {
            modal.classList.remove('active');
        });
    }
    
    if (sendBtn && input) {
        const sendMessage = async () => {
            const message = input.value.trim();
            if (!message) return;
            
            addAIMessage(message, 'user');
            input.value = '';
            
            // Show typing indicator
            const typingIndicator = document.createElement('div');
            typingIndicator.className = 'ai-message bot typing';
            typingIndicator.innerHTML = `
                <div class="message-avatar"><i class="fas fa-robot"></i></div>
                <div class="message-content"><div class="typing-indicator"><span></span><span></span><span></span></div></div>
            `;
            document.getElementById('aiMessages').appendChild(typingIndicator);
            
            try {
                const response = await apiRequest('/api/ai-assistant', {
                    method: 'POST',
                    body: { problem: message }
                });
                
                typingIndicator.remove();
                addAIMessage(response, 'bot');
            } catch (error) {
                typingIndicator.remove();
                addAIMessage('Sorry, I encountered an error. Please try again.', 'bot');
            }
        };
        
        sendBtn.addEventListener('click', sendMessage);
        input.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') sendMessage();
        });
    }
}

function addAIMessage(content, sender) {
    const container = document.getElementById('aiMessages');
    const messageDiv = document.createElement('div');
    messageDiv.className = `ai-message ${sender}`;
    
    if (sender === 'bot' && typeof content === 'object') {
        messageDiv.innerHTML = `
            <div class="message-avatar"><i class="fas fa-robot"></i></div>
            <div class="message-content">
                <p><strong>Possible Causes:</strong></p>
                <ul>${content.possible_causes.map(c => `<li>${c}</li>`).join('')}</ul>
                <p><strong>Safety Measures:</strong> ${content.safety_measures}</p>
                <p><strong>Urgency:</strong> <span style="color: ${getUrgencyColor(content.urgency_level)}">${content.urgency_level}</span></p>
                <p>${content.recommendation}</p>
            </div>
        `;
    } else {
        messageDiv.innerHTML = `
            <div class="message-avatar"><i class="fas fa-${sender === 'bot' ? 'robot' : 'user'}"></i></div>
            <div class="message-content"><p>${content}</p></div>
        `;
    }
    
    container.appendChild(messageDiv);
    container.scrollTop = container.scrollHeight;
}

function getUrgencyColor(urgency) {
    if (urgency.includes('Critical')) return '#ef4444';
    if (urgency.includes('High')) return '#f59e0b';
    if (urgency.includes('Medium')) return '#3b82f6';
    return '#10b981';
}

// Mechanic Dashboard Functions
function setupAvailabilityToggle() {
    const toggle = document.getElementById('availabilitySwitch');
    if (!toggle) return;
    
    toggle.addEventListener('change', async () => {
        try {
            await apiRequest('/api/availability', {
                method: 'PUT',
                body: {
                    is_available: toggle.checked,
                    is_online: toggle.checked
                }
            });
            showToast(`You are now ${toggle.checked ? 'available' : 'unavailable'}`, 'success');
        } catch (error) {
            toggle.checked = !toggle.checked;
        }
    });
}

async function loadMechanicStats() {
    try {
        const user = getUser();
        document.getElementById('avgRating').textContent = user.average_rating.toFixed(1);
        
        // Load conversations count
        const conversations = await apiRequest('/chat/conversations');
        document.getElementById('totalChats').textContent = conversations.length;
    } catch (error) {
        console.error('Failed to load stats:', error);
    }
}

// Admin Functions
function setupAdminNavigation() {
    const links = document.querySelectorAll('.admin-sidebar a');
    links.forEach(link => {
        link.addEventListener('click', (e) => {
            e.preventDefault();
            const section = link.dataset.section;
            
            links.forEach(l => l.classList.remove('active'));
            link.classList.add('active');
            
            document.querySelectorAll('.admin-section').forEach(s => s.classList.add('hidden'));
            document.getElementById(`${section}Section`).classList.remove('hidden');
            
            if (section === 'users') loadAdminUsers();
            if (section === 'chats') loadAdminChats();
        });
    });
}

async function loadAdminStats() {
    try {
        const stats = await apiRequest('/api/admin/stats');
        
        document.getElementById('totalUsers').textContent = stats.total_users;
        document.getElementById('totalDrivers').textContent = stats.drivers;
        document.getElementById('totalMechanics').textContent = stats.mechanics;
        document.getElementById('totalShops').textContent = stats.shop_owners;
        
        // Render chart
        renderActivityChart();
    } catch (error) {
        console.error('Failed to load stats:', error);
    }
}

function renderActivityChart() {
    const ctx = document.getElementById('activityChart');
    if (!ctx) return;
    
    new Chart(ctx, {
        type: 'line',
        data: {
            labels: ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'],
            datasets: [{
                label: 'Active Users',
                data: [65, 78, 90, 85, 95, 110, 105],
                borderColor: '#f59e0b',
                backgroundColor: 'rgba(245, 158, 11, 0.1)',
                tension: 0.4,
                fill: true
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { display: false }
            },
            scales: {
                y: {
                    grid: { color: 'rgba(255, 255, 255, 0.1)' },
                    ticks: { color: '#94a3b8' }
                },
                x: {
                    grid: { display: false },
                    ticks: { color: '#94a3b8' }
                }
            }
        }
    });
}

async function loadAdminUsers() {
    const tbody = document.getElementById('usersTable');
    if (!tbody) return;
    
    try {
        const data = await apiRequest('/api/admin/users');
        
        tbody.innerHTML = data.users.map(user => `
            <tr>
                <td>
                    <div class="user-cell">
                        <img src="${user.profile_picture || 'assets/default-avatar.png'}" alt="">
                        <div>
                            <div>${user.full_name}</div>
                            <small style="color: var(--text-secondary)">${user.email}</small>
                        </div>
                    </div>
                </td>
                <td>${user.role}</td>
                <td><span class="status-badge ${user.is_active ? 'active' : 'suspended'}">${user.is_active ? 'Active' : 'Suspended'}</span></td>
                <td>${new Date(user.created_at).toLocaleDateString()}</td>
                <td>
                    <div class="action-btns">
                        <button onclick="suspendUser(${user.id})" title="Suspend"><i class="fas fa-ban"></i></button>
                        <button onclick="deleteUser(${user.id})" class="btn-danger" title="Delete"><i class="fas fa-trash"></i></button>
                    </div>
                </td>
            </tr>
        `).join('');
    } catch (error) {
        tbody.innerHTML = '<tr><td colspan="5">Failed to load users</td></tr>';
    }
}

async function suspendUser(userId) {
    if (!confirm('Are you sure you want to suspend this user?')) return;
    
    try {
        await apiRequest(`/api/admin/users/${userId}/suspend`, { method: 'POST' });
        showToast('User suspended successfully', 'success');
        loadAdminUsers();
    } catch (error) {
        showToast('Failed to suspend user', 'error');
    }
}

async function deleteUser(userId) {
    if (!confirm('Are you sure you want to permanently delete this user? This cannot be undone.')) return;
    
    try {
        await apiRequest(`/api/admin/users/${userId}`, { method: 'DELETE' });
        showToast('User deleted successfully', 'success');
        loadAdminUsers();
    } catch (error) {
        showToast('Failed to delete user', 'error');
    }
}

async function sendNotification() {
    const target = document.getElementById('notificationTarget').value;
    const title = document.getElementById('notificationTitle').value;
    const body = document.getElementById('notificationBody').value;
    
    if (!title || !body) {
        showToast('Please fill in all fields', 'error');
        return;
    }
    
    try {
        await apiRequest('/api/admin/notifications', {
            method: 'POST',
            body: { target, title, body }
        });
        showToast('Notification sent successfully', 'success');
        document.getElementById('notificationTitle').value = '';
        document.getElementById('notificationBody').value = '';
    } catch (error) {
        showToast('Failed to send notification', 'error');
    }
}

// Chat Functions
let currentChatUser = null;
let socket = null;

function openChat(userId) {
    currentChatUser = userId;
    const modal = document.getElementById('chatModal');
    modal.classList.add('active');
    
    // Load user info
    apiRequest(`/api/users/${userId}`).then(user => {
        document.getElementById('chatUserName').textContent = user.full_name;
        document.getElementById('chatUserAvatar').src = user.profile_picture || 'assets/default-avatar.png';
        document.getElementById('callBtn').onclick = () => window.location.href = `tel:${user.phone}`;
        document.getElementById('navigateBtn').onclick = () => {
            window.open(`https://www.google.com/maps/dir/?api=1&destination=${user.latitude},${user.longitude}`, '_blank');
        };
    });
    
    // Initialize socket if not already
    if (!socket) {
        initSocket();
    }
    
    // Join chat room
    socket.emit('join_chat', { user_id: userId });
}

function initSocket() {
    socket = io(API_BASE_URL);
    
    socket.on('connect', () => {
        socket.emit('authenticate', { token: getToken() });
    });
    
    socket.on('authenticated', (data) => {
        if (data.status === 'success') {
            console.log('Socket authenticated');
        }
    });
    
    socket.on('chat_history', (data) => {
        const container = document.getElementById('chatMessages');
        container.innerHTML = '';
        data.messages.forEach(msg => appendMessage(msg));
    });
    
    socket.on('new_message', (message) => {
        appendMessage(message);
        // Play notification sound
        new Audio('assets/notification.mp3').play().catch(() => {});
    });
    
    socket.on('typing', () => {
        document.querySelector('.typing-indicator')?.classList.remove('hidden');
    });
    
    socket.on('stop_typing', () => {
        document.querySelector('.typing-indicator')?.classList.add('hidden');
    });
    
    socket.on('notification', (data) => {
        showToast(data.body, 'info');
        updateUnreadCount();
    });
}

function appendMessage(message) {
    const container = document.getElementById('chatMessages');
    const currentUser = getUser();
    const isSent = message.sender_id === currentUser.id;
    
    const messageDiv = document.createElement('div');
    messageDiv.className = `message ${isSent ? 'sent' : 'received'}`;
    messageDiv.innerHTML = `
        <div class="message-avatar">
            ${isSent ? '<i class="fas fa-user"></i>' : `<img src="${message.sender.profile_picture || 'assets/default-avatar.png'}" alt="">`}
        </div>
        <div>
            <div class="message-content">
                <p>${message.content}</p>
            </div>
            <div class="message-time">
                ${new Date(message.created_at).toLocaleTimeString()}
                ${isSent ? `<span class="read-receipt">${message.is_read ? '<i class="fas fa-check-double"></i>' : '<i class="fas fa-check"></i>'}</span>` : ''}
            </div>
        </div>
    `;
    
    container.appendChild(messageDiv);
    container.scrollTop = container.scrollHeight;
}

function sendChatMessage() {
    const input = document.getElementById('messageInput');
    const content = input.value.trim();
    
    if (!content || !currentChatUser) return;
    
    socket.emit('send_message', {
        receiver_id: currentChatUser,
        content: content,
        message_type: 'text'
    });
    
    input.value = '';
    socket.emit('stop_typing', { receiver_id: currentChatUser });
}

// Typing indicator
let typingTimeout;
function handleTyping() {
    if (!currentChatUser) return;
    
    socket.emit('typing', { receiver_id: currentChatUser });
    
    clearTimeout(typingTimeout);
    typingTimeout = setTimeout(() => {
        socket.emit('stop_typing', { receiver_id: currentChatUser });
    }, 1000);
}

// Event listeners for chat
document.addEventListener('DOMContentLoaded', () => {
    const messageInput = document.getElementById('messageInput');
    const sendButton = document.getElementById('sendMessage');
    
    if (messageInput) {
        messageInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') {
                sendChatMessage();
            } else {
                handleTyping();
            }
        });
    }
    
    if (sendButton) {
        sendButton.addEventListener('click', sendChatMessage);
    }
    
    // Close modals
    document.querySelectorAll('.close-modal').forEach(btn => {
        btn.addEventListener('click', () => {
            btn.closest('.modal').classList.remove('active');
        });
    });
    
    // Close modal on outside click
    document.querySelectorAll('.modal').forEach(modal => {
        modal.addEventListener('click', (e) => {
            if (e.target === modal) {
                modal.classList.remove('active');
            }
        });
    });
});

async function loadConversations() {
    try {
        const conversations = await apiRequest('/chat/conversations');
        const container = document.getElementById('conversationsList');
        
        if (!container) return;
        
        if (conversations.length === 0) {
            container.innerHTML = '<p class="empty-state">No conversations yet</p>';
            return;
        }
        
        container.innerHTML = conversations.map(conv => `
            <div class="conversation-item" onclick="openChat(${conv.user.id})">
                <img src="${conv.user.profile_picture || 'assets/default-avatar.png'}" alt="">
                <div class="conversation-info">
                    <h4>${conv.user.full_name}</h4>
                    <p>${conv.last_message ? conv.last_message.content : 'No messages'}</p>
                </div>
                <div class="conversation-meta">
                    <span class="time">${conv.last_message ? new Date(conv.last_message.created_at).toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'}) : ''}</span>
                    ${conv.unread_count > 0 ? `<span class="badge">${conv.unread_count}</span>` : ''}
                </div>
            </div>
        `).join('');
        
        // Update total unread count
        const totalUnread = conversations.reduce((sum, c) => sum + c.unread_count, 0);
        const badge = document.querySelector('#notificationsBtn .badge');
        if (badge) {
            badge.textContent = totalUnread;
            badge.classList.toggle('hidden', totalUnread === 0);
        }
    } catch (error) {
        console.error('Failed to load conversations:', error);
    }
}

function updateUnreadCount() {
    loadConversations();
}