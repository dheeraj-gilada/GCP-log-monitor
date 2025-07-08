// Form validation and handling

/**
 * Validates the setup form inputs
 * @returns {boolean} True if form is valid, false otherwise
 */
function validateForm() {
    const projectId = document.getElementById('project-id').value.trim();
    const alertEmail = document.getElementById('alert-email').value.trim();
    
    if (!projectId) {
        showStatus('Please enter a Project ID', 'error');
        return false;
    }
    
    if (!alertEmail || !isValidEmail(alertEmail)) {
        showStatus('Please enter a valid email address', 'error');
        return false;
    }
    
    const liveModeRadio = document.getElementById('live-mode');
    const gcpCredentialsInput = document.getElementById('gcp-credentials');
    const simulationLogsInput = document.getElementById('simulation-logs');
    
    if (liveModeRadio.checked && !gcpCredentialsInput.files.length) {
        showStatus('Please upload GCP credentials for live mode', 'error');
        return false;
    }
    
    if (!liveModeRadio.checked && !simulationLogsInput.files.length) {
        showStatus('Please upload log files for simulation mode', 'error');
        return false;
    }
    
    return true;
}

/**
 * Validates an email address format
 * @param {string} email - Email address to validate
 * @returns {boolean} True if email format is valid, false otherwise
 */
function isValidEmail(email) {
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    return emailRegex.test(email);
}

/**
 * Shows a status message
 * @param {string} message - Message to display
 * @param {string} type - Message type (success, error)
 */
function showStatus(message, type) {
    const statusElement = document.getElementById('setup-status');
    statusElement.textContent = message;
    statusElement.className = `status-message ${type} show`;
    
    setTimeout(() => {
        statusElement.classList.remove('show');
    }, 5000);
}

/**
 * Handles form submission
 * @param {Event} e - Submit event
 */
async function handleFormSubmit(e) {
    e.preventDefault();
    
    if (!validateForm()) {
        return;
    }
    
    const submitBtn = document.getElementById('setup-submit');
    
    // Show loading state
    submitBtn.classList.add('loading');
    submitBtn.disabled = true;
    
    try {
        const formData = new FormData();
        const liveModeRadio = document.getElementById('live-mode');
        const gcpCredentialsInput = document.getElementById('gcp-credentials');
        const simulationLogsInput = document.getElementById('simulation-logs');
        
        formData.append('mode', liveModeRadio.checked ? 'live' : 'simulation');
        formData.append('project_id', document.getElementById('project-id').value);
        formData.append('log_filter', document.getElementById('log-filter').value);
        formData.append('alert_email', document.getElementById('alert-email').value);
        
        if (liveModeRadio.checked && gcpCredentialsInput.files.length) {
            formData.append('gcp_credentials', gcpCredentialsInput.files[0]);
        }
        
        if (!liveModeRadio.checked && simulationLogsInput.files.length) {
            for (let file of simulationLogsInput.files) {
                formData.append('simulation_logs', file);
            }
        }
        
        const response = await fetch('/api/setup', {
            method: 'POST',
            body: formData
        });
        
        const result = await response.json();
        
        if (response.ok) {
            showStatus('Setup successful! Redirecting to dashboard...', 'success');
            setTimeout(() => {
                window.location.href = '/dashboard';
            }, 2000);
        } else {
            showStatus(result.message || 'Setup failed. Please try again.', 'error');
        }
    } catch (error) {
        console.error('Setup error:', error);
        showStatus('Network error. Please check your connection and try again.', 'error');
    } finally {
        submitBtn.classList.remove('loading');
        submitBtn.disabled = false;
    }
}

// Export functions
export { validateForm, showStatus, handleFormSubmit }; 