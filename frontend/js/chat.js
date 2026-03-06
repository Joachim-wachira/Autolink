// Chat-specific functionality
class ChatManager {
    constructor() {
        this.socket = null;
        this.currentRoom = null;
        this.typingTimeout = null;
        this.reconnectAttempts = 0;
        this.maxReconnectAttempts = 5;
    }
    
    init() {
        this.connect();
        this.setupEventListeners();
    }
    
    connect() {
        const token = getToken();
        if (!token) return;
        
        this.socket = io(API_BASE_URL, {
            transports: ['websocket'],
            auth: { token }
        });
        
        this.socket.on('connect', () => {
            console.log('Connected to chat server');
            this.reconnectAttempts = 0;
            this.authenticate();
        });
        
        this.socket.on('disconnect', () => {
            console.log('Disconnected from chat server');
            this.attemptReconnect();
        });
        
        this.socket.on('connect_error', (error) => {
            console.error('Connection error:', error);
            this.attemptReconnect();
        });
        
        this.setupSocketEvents();
    }
    
    authenticate() {
        this.socket.emit('authenticate', { token: getToken() });
    }
    
    setupSocketEvents() {
        this.socket.on('authenticated', (response) => {
            if (response.status === 'success') {
                console.log('Chat authenticated');
                this.loadConversations();
            }
        });
        
        this.socket.on('new_message', (message) => {
            this.handleNewMessage(message);
        });
        
        this.socket.on('typing', (data) => {
            this.showTypingIndicator(data.user_id);
        });
        
        this.socket.on('stop_typing', () => {
            this.hideTypingIndicator();
        });
        
        this.socket.on('user_online', (data) => {
            this.updateUserStatus(data.user_id, true);
        });
        
        this.socket.on('user_offline', (data) => {
            this.updateUserStatus(data.user_id, false);
        });
    }
    
    setupEventListeners() {
        // Send message on Enter
        const messageInput = document.getElementById('messageInput');
        if (messageInput) {
            messageInput.addEventListener('keypress', (e) => {
                if (e.key === 'Enter') {
                    this.sendMessage();
                } else {
                    this.handleTyping();
                }
            });
        }
        
        // Send button
        const sendBtn = document.getElementById('sendMessage');
        if (sendBtn) {
            sendBtn.addEventListener('click', () => this.sendMessage());
        }
    }
    
    handleTyping() {
        if (!this.currentRoom) return;
        
        this.socket.emit('typing', { receiver_id: this.currentRoom });
        
        clearTimeout(this.typingTimeout);
        this.typingTimeout = setTimeout(() => {
            this.socket.emit('stop_typing', { receiver_id: this.currentRoom });
        }, 1000);
    }
    
    sendMessage() {
        const input = document.getElementById('messageInput');
        const content = input.value.trim();
        
        if (!content || !this.currentRoom) return;
        
        const message = {
            receiver_id: this.currentRoom,
            content: content,
            message_type: 'text',
            temp_id: Date.now()
        };
        
        // Optimistic UI update
        this.appendMessage({
            ...message,
            sender_id: getUser().id,
            created_at: new Date().toISOString(),
            is_read: false
        }, true);
        
        this.socket.emit('send_message', message);
        input.value = '';
        this.socket.emit('stop_typing', { receiver_id: this.currentRoom });
    }
    
    appendMessage(message, isSent = false) {
        const container = document.getElementById('chatMessages');
        if (!container) return;
        
        const currentUser = getUser();
        const isOwnMessage = message.sender_id === currentUser.id;
        
        const messageEl = document.createElement('div');
        messageEl.className = `message ${isOwnMessage ? 'sent' : 'received'}`;
        messageEl.dataset.messageId = message.id;
        
        const time = new Date(message.created_at).toLocaleTimeString([], {
            hour: '2-digit',
            minute: '2-digit'
        });
        
        messageEl.innerHTML = `
            <div class="message-avatar">
                ${isOwnMessage ? 
                    '<i class="fas fa-user"></i>' : 
                    `<img src="${message.sender?.profile_picture || 'assets/default-avatar.png'}" alt="">`
                }
            </div>
            <div>
                <div class="message-content">
                    <p>${this.escapeHtml(message.content)}</p>
                </div>
                <div class="message-time">
                    ${time}
                    ${isOwnMessage ? `
                        <span class="read-receipt">
                            ${message.is_read ? 
                                '<i class="fas fa-check-double" style="color: var(--accent);"></i>' : 
                                '<i class="fas fa-check"></i>'
                            }
                        </span>
                    ` : ''}
                </div>
            </div>
        `;
        
        container.appendChild(messageEl);
        container.scrollTop = container.scrollHeight;
        
        // Animate in
        requestAnimationFrame(() => {
            messageEl.style.opacity = '0';
            messageEl.style.transform = 'translateY(10px)';
            setTimeout(() => {
                messageEl.style.transition = 'all 0.3s ease';
                messageEl.style.opacity = '1';
                messageEl.style.transform = 'translateY(0)';
            }, 10);
        });
    }
    
    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
    
    showTypingIndicator(userId) {
        const indicator = document.querySelector('.typing-indicator');
        if (indicator) {
            indicator.classList.remove('hidden');
        }
    }
    
    hideTypingIndicator() {
        const indicator = document.querySelector('.typing-indicator');
        if (indicator) {
            indicator.classList.add('hidden');
        }
    }
    
    updateUserStatus(userId, isOnline) {
        const statusEl = document.getElementById('chatUserStatus');
        if (statusEl && this.currentRoom === userId) {
            statusEl.textContent = isOnline ? 'Online' : 'Offline';
            statusEl.className = `status ${isOnline ? 'online' : 'offline'}`;
        }
    }
    
    attemptReconnect() {
        if (this.reconnectAttempts < this.maxReconnectAttempts) {
            this.reconnectAttempts++;
            setTimeout(() => this.connect(), 2000 * this.reconnectAttempts);
        }
    }
    
    joinRoom(userId) {
        this.currentRoom = userId;
        this.socket.emit('join_chat', { user_id: userId });
    }
    
    handleNewMessage(message) {
        // If we're in the chat with this user, append the message
        if (this.currentRoom === message.sender_id || this.currentRoom === message.receiver_id) {
            this.appendMessage(message);
            
            // Mark as read if we're the receiver
            if (message.receiver_id === getUser().id) {
                this.socket.emit('mark_read', { message_id: message.id });
            }
        } else {
            // Show notification
            showToast(`New message from ${message.sender.full_name}`, 'info');
            this.updateUnreadCount();
        }
    }
    
    async loadConversations() {
        try {
            const conversations = await apiRequest('/chat/conversations');
            this.renderConversations(conversations);
        } catch (error) {
            console.error('Failed to load conversations:', error);
        }
    }
    
    renderConversations(conversations) {
        const container = document.getElementById('conversationsList');
        if (!container) return;
        
        if (conversations.length === 0) {
            container.innerHTML = '<p class="empty-state">No conversations yet. Start by finding a mechanic!</p>';
            return;
        }
        
        container.innerHTML = conversations.map(conv => {
            const isOnline = conv.user.is_online;
            const lastMessage = conv.last_message;
            const time = lastMessage ? 
                new Date(lastMessage.created_at).toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'}) : 
                '';
            
            return `
                <div class="conversation-item" onclick="chatManager.openChat(${conv.user.id})">
                    <div style="position: relative;">
                        <img src="${conv.user.profile_picture || 'assets/default-avatar.png'}" alt="">
                        <span class="online-indicator ${isOnline ? 'online' : ''}"></span>
                    </div>
                    <div class="conversation-info">
                        <h4>${conv.user.full_name}</h4>
                        <p>${lastMessage ? lastMessage.content.substring(0, 30) + '...' : 'No messages yet'}</p>
                    </div>
                    <div class="conversation-meta">
                        <span class="time">${time}</span>
                        ${conv.unread_count > 0 ? `<span class="badge">${conv.unread_count}</span>` : ''}
                    </div>
                </div>
            `;
        }).join('');
    }
    
    openChat(userId) {
        this.joinRoom(userId);
        
        // Load user info
        apiRequest(`/api/users/${userId}`).then(user => {
            document.getElementById('chatUserName').textContent = user.full_name;
            document.getElementById('chatUserAvatar').src = user.profile_picture || 'assets/default-avatar.png';
            
            const statusEl = document.getElementById('chatUserStatus');
            statusEl.textContent = user.is_online ? 'Online' : 'Offline';
            statusEl.className = `status ${user.is_online ? 'online' : 'offline'}`;
            
            // Setup call and navigate buttons
            document.getElementById('callBtn').onclick = () => {
                window.location.href = `tel:${user.phone}`;
            };
            
            document.getElementById('navigateBtn').onclick = () => {
                if (user.latitude && user.longitude) {
                    window.open(`https://www.google.com/maps/dir/?api=1&destination=${user.latitude},${user.longitude}`, '_blank');
                } else {
                    showToast('Location not available for this user', 'error');
                }
            };
        });
        
        // Show modal
        document.getElementById('chatModal').classList.add('active');
    }
    
    updateUnreadCount() {
        this.loadConversations();
    }
}

// Initialize chat manager
const chatManager = new ChatManager();