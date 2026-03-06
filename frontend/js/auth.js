document.addEventListener('DOMContentLoaded', function() {
    // Role selection
    const roleBtns = document.querySelectorAll('.role-btn');
    const roleInput = document.getElementById('role');
    const providerFields = document.querySelectorAll('.provider-fields');
    
    roleBtns.forEach(btn => {
        btn.addEventListener('click', () => {
            roleBtns.forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            
            const role = btn.dataset.role;
            roleInput.value = role;
            
            // Show/hide provider fields
            providerFields.forEach(field => {
                field.classList.toggle('hidden', role === 'driver');
            });
        });
    });
    
    // Password toggle
    const togglePassword = document.querySelector('.toggle-password');
    const passwordInput = document.getElementById('password');
    
    if (togglePassword) {
        togglePassword.addEventListener('click', () => {
            const type = passwordInput.type === 'password' ? 'text' : 'password';
            passwordInput.type = type;
            togglePassword.querySelector('i').classList.toggle('fa-eye');
            togglePassword.querySelector('i').classList.toggle('fa-eye-slash');
        });
    }
    
    // File upload preview
    const fileInput = document.getElementById('profile_picture');
    const fileName = document.querySelector('.file-name');
    const imagePreview = document.getElementById('imagePreview');
    
    if (fileInput) {
        fileInput.addEventListener('change', (e) => {
            const file = e.target.files[0];
            if (file) {
                fileName.textContent = file.name;
                
                const reader = new FileReader();
                reader.onload = (e) => {
                    imagePreview.innerHTML = `<img src="${e.target.result}" alt="Preview">`;
                };
                reader.readAsDataURL(file);
            }
        });
    }
    
    // Location detection
    const detectBtn = document.getElementById('detectLocation');
    const locationStatus = document.getElementById('locationStatus');
    
    if (detectBtn) {
        detectBtn.addEventListener('click', async () => {
            locationStatus.textContent = 'Detecting location...';
            
            try {
                const position = await getCurrentPosition();
                const { lat, lng } = position;
                
                // Reverse geocode
                const address = await reverseGeocode(lat, lng);
                
                document.getElementById('latitude').value = lat;
                document.getElementById('longitude').value = lng;
                document.getElementById('location_name').value = address || `${lat.toFixed(4)}, ${lng.toFixed(4)}`;
                
                locationStatus.textContent = '✓ Location detected';
                locationStatus.style.color = 'var(--success)';
            } catch (error) {
                locationStatus.textContent = '✗ ' + error.message;
                locationStatus.style.color = 'var(--danger)';
            }
        });
    }
    
    // Form submission
    const form = document.getElementById('registerForm');
    if (form) {
        form.addEventListener('submit', async (e) => {
            e.preventDefault();
            
            const submitBtn = form.querySelector('button[type="submit"]');
            const spinner = submitBtn.querySelector('.spinner');
            const btnText = submitBtn.querySelector('span');
            const btnIcon = submitBtn.querySelector('i');
            
            // Show loading
            spinner.classList.remove('hidden');
            btnText.textContent = 'Creating Account...';
            btnIcon.classList.add('hidden');
            submitBtn.disabled = true;
            
            try {
                const formData = new FormData(form);
                
                const response = await fetch(`${API_BASE_URL}/auth/register`, {
                    method: 'POST',
                    body: formData
                });
                
                const data = await response.json();
                
                if (!response.ok) {
                    throw new Error(data.error || 'Registration failed');
                }
                
                // Store tokens
                setTokens(data.access_token, data.refresh_token);
                setUser(data.user);
                
                showToast('Registration successful!', 'success');
                
                // Redirect based on role
                const role = data.user.role;
                if (role === 'driver') {
                    window.location.href = 'dashboard_driver.html';
                } else if (role === 'mechanic' || role === 'shop_owner') {
                    window.location.href = 'dashboard_mechanic.html';
                } else if (role === 'admin') {
                    window.location.href = 'dashboard_admin.html';
                }
                
            } catch (error) {
                showToast(error.message, 'error');
                
                // Reset button
                spinner.classList.add('hidden');
                btnText.textContent = 'Create Account';
                btnIcon.classList.remove('hidden');
                submitBtn.disabled = false;
            }
        });
    }
});

// Show login form (toggle between login/register)
function showLogin() {
    // For simplicity, we'll use the same form but modify it
    const form = document.getElementById('registerForm');
    const header = document.querySelector('.auth-header h2');
    const footer = document.querySelector('.auth-footer');
    
    // This is a simplified version - in production, you'd have separate forms
    header.textContent = 'Welcome Back';
    form.innerHTML = `
        <div class="form-group">
            <label for="email">Email</label>
            <div class="input-wrapper">
                <i class="fas fa-envelope"></i>
                <input type="email" id="loginEmail" required placeholder="john@example.com">
            </div>
        </div>
        <div class="form-group">
            <label for="password">Password</label>
            <div class="input-wrapper">
                <i class="fas fa-lock"></i>
                <input type="password" id="loginPassword" required placeholder="••••••••">
            </div>
        </div>
        <button type="submit" class="btn-primary btn-full">
            <span>Login</span>
            <i class="fas fa-arrow-right"></i>
        </button>
    `;
    
    footer.innerHTML = `<p>Don't have an account? <a href="#" onclick="location.reload()">Register</a></p>`;
    
    form.onsubmit = async (e) => {
        e.preventDefault();
        
        try {
            const response = await fetch(`${API_BASE_URL}/auth/login`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    email: document.getElementById('loginEmail').value,
                    password: document.getElementById('loginPassword').value
                })
            });
            
            const data = await response.json();
            
            if (!response.ok) {
                throw new Error(data.error || 'Login failed');
            }
            
            setTokens(data.access_token, data.refresh_token);
            setUser(data.user);
            
            showToast('Login successful!', 'success');
            
            const role = data.user.role;
            if (role === 'driver') {
                window.location.href = 'dashboard_driver.html';
            } else if (role === 'mechanic' || role === 'shop_owner') {
                window.location.href = 'dashboard_mechanic.html';
            } else if (role === 'admin') {
                window.location.href = 'dashboard_admin.html';
            }
            
        } catch (error) {
            showToast(error.message, 'error');
        }
    };
}