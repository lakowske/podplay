// PodPlay Authentication JavaScript

document.addEventListener('DOMContentLoaded', function() {
    // Load CSRF token for forms
    loadCSRFToken();
    
    // Setup dynamic domain selection
    setupDynamicDomain();
    
    // Setup form validation
    setupFormValidation();
});

function loadCSRFToken() {
    // Find all forms with CSRF token placeholders
    const forms = document.querySelectorAll('form');
    
    forms.forEach(form => {
        const csrfInput = form.querySelector('input[name="csrf_token"]');
        if (csrfInput && csrfInput.value === '{CSRF_TOKEN}') {
            // Fetch CSRF token from server
            fetch('/cgi-bin/csrf-token.py')
                .then(response => response.json())
                .then(data => {
                    csrfInput.value = data.csrf_token;
                })
                .catch(error => {
                    console.error('Failed to load CSRF token:', error);
                    // Generate a fallback token (not secure, but better than nothing)
                    csrfInput.value = 'fallback-' + Date.now() + '-' + Math.random().toString(36);
                });
        }
    });
}

function setupDynamicDomain() {
    // Get current domain from hostname and update domain selectors and placeholders
    const currentDomain = window.location.hostname;
    
    // Update domain select options
    const domainSelect = document.querySelector('select[name="domain"]');
    if (domainSelect) {
        // Clear existing options and add current domain
        domainSelect.innerHTML = '';
        const option = document.createElement('option');
        option.value = currentDomain;
        option.textContent = currentDomain;
        option.selected = true;
        domainSelect.appendChild(option);
    }
    
    // Update email placeholders with current domain
    const emailInputs = document.querySelectorAll('input[placeholder*="@"]');
    emailInputs.forEach(input => {
        if (input.placeholder.includes('@lab.sethlakowske.com')) {
            input.placeholder = input.placeholder.replace('@lab.sethlakowske.com', `@${currentDomain}`);
        }
    });
}

function setupFormValidation() {
    // Password confirmation validation
    const passwordFields = document.querySelectorAll('input[type="password"]');
    const forms = document.querySelectorAll('form');
    
    forms.forEach(form => {
        const password = form.querySelector('input[name="password"]');
        const confirmPassword = form.querySelector('input[name="confirm_password"]');
        
        if (password && confirmPassword) {
            // Real-time validation feedback
            confirmPassword.addEventListener('input', function() {
                if (this.value && password.value !== this.value) {
                    this.setCustomValidity('Passwords do not match');
                    this.classList.add('error');
                } else {
                    this.setCustomValidity('');
                    this.classList.remove('error');
                }
            });
            
            password.addEventListener('input', function() {
                if (confirmPassword.value && this.value !== confirmPassword.value) {
                    confirmPassword.setCustomValidity('Passwords do not match');
                    confirmPassword.classList.add('error');
                } else {
                    confirmPassword.setCustomValidity('');
                    confirmPassword.classList.remove('error');
                }
            });
        }
    });
    
    // Username validation
    const usernameField = document.querySelector('input[name="username"]');
    if (usernameField) {
        usernameField.addEventListener('input', function() {
            const value = this.value;
            const pattern = /^[a-zA-Z0-9_.-]+$/;
            
            if (value && !pattern.test(value)) {
                this.setCustomValidity('Username can only contain letters, numbers, dots, dashes and underscores');
                this.classList.add('error');
            } else if (value && value.length < 3) {
                this.setCustomValidity('Username must be at least 3 characters');
                this.classList.add('error');
            } else {
                this.setCustomValidity('');
                this.classList.remove('error');
            }
        });
    }
    
    // Email validation
    const emailField = document.querySelector('input[name="email"]');
    if (emailField) {
        emailField.addEventListener('input', function() {
            const value = this.value;
            const emailPattern = /^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$/;
            
            if (value && !emailPattern.test(value)) {
                this.setCustomValidity('Please enter a valid email address');
                this.classList.add('error');
            } else {
                this.setCustomValidity('');
                this.classList.remove('error');
            }
        });
    }
    
    // Password strength indicator
    const passwordField = document.querySelector('input[name="password"]');
    if (passwordField) {
        passwordField.addEventListener('input', function() {
            showPasswordStrength(this);
        });
    }
}

function showPasswordStrength(passwordField) {
    const password = passwordField.value;
    let strength = 0;
    let message = '';
    
    // Check length
    if (password.length >= 8) strength++;
    if (password.length >= 12) strength++;
    
    // Check character types
    if (/[a-z]/.test(password)) strength++;
    if (/[A-Z]/.test(password)) strength++;
    if (/[0-9]/.test(password)) strength++;
    if (/[^a-zA-Z0-9]/.test(password)) strength++;
    
    // Remove existing strength indicator
    const existingIndicator = passwordField.parentNode.querySelector('.password-strength');
    if (existingIndicator) {
        existingIndicator.remove();
    }
    
    if (password.length > 0) {
        const indicator = document.createElement('div');
        indicator.className = 'password-strength';
        
        if (strength <= 2) {
            indicator.className += ' weak';
            message = 'Weak password';
        } else if (strength <= 4) {
            indicator.className += ' medium';
            message = 'Medium strength';
        } else {
            indicator.className += ' strong';
            message = 'Strong password';
        }
        
        indicator.textContent = message;
        passwordField.parentNode.appendChild(indicator);
    }
}

// Utility functions
function validateForm(form) {
    // General form validation
    const requiredFields = form.querySelectorAll('[required]');
    let isValid = true;
    
    requiredFields.forEach(field => {
        if (!field.value.trim()) {
            field.classList.add('error');
            isValid = false;
        } else {
            field.classList.remove('error');
        }
    });
    
    // Check for any custom validation errors
    const invalidFields = form.querySelectorAll(':invalid');
    if (invalidFields.length > 0) {
        isValid = false;
    }
    
    return isValid;
}

function showMessage(message, type = 'info') {
    const messageDiv = document.createElement('div');
    messageDiv.className = `message ${type}`;
    messageDiv.textContent = message;
    
    // Insert at top of auth container
    const authContainer = document.querySelector('.auth-container');
    if (authContainer) {
        authContainer.insertBefore(messageDiv, authContainer.firstChild);
        
        // Auto-remove after 5 seconds
        setTimeout(() => {
            messageDiv.remove();
        }, 5000);
    }
}

// Handle URL parameters (for reset password token)
function getUrlParameter(name) {
    const urlParams = new URLSearchParams(window.location.search);
    return urlParams.get(name);
}

// Set up token from URL for reset password page
if (window.location.pathname.includes('reset-password.html')) {
    document.addEventListener('DOMContentLoaded', function() {
        const token = getUrlParameter('token');
        const tokenInput = document.querySelector('input[name="token"]');
        if (token && tokenInput) {
            tokenInput.value = token;
        }
    });
}