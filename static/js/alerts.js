// Alerts handling functionality

/**
 * Fetches alerts from the server
 * @param {number} limit - Maximum number of alerts to fetch
 * @returns {Promise<Array>} Array of alert objects
 */
async function fetchAlerts(limit = 10) {
    try {
        const response = await fetch(`/api/alerts?limit=${limit}`);
        if (!response.ok) {
            throw new Error('Failed to fetch alerts');
        }
        
        return await response.json();
    } catch (error) {
        console.error('Error fetching alerts:', error);
        return [];
    }
}

/**
 * Renders alerts in the specified container
 * @param {Array} alerts - Array of alert objects
 * @param {HTMLElement} container - Container element to render alerts in
 */
function renderAlerts(alerts, container) {
    if (!container) return;
    
    // Clear the container
    container.innerHTML = '';
    
    if (!alerts || alerts.length === 0) {
        container.innerHTML = '<div class="no-alerts">No alerts detected</div>';
        return;
    }
    
    // Create and append alert elements
    alerts.forEach(alert => {
        const alertElement = createAlertElement(alert);
        container.appendChild(alertElement);
    });
}

/**
 * Creates an HTML element for an alert
 * @param {Object} alert - Alert object
 * @returns {HTMLElement} Alert element
 */
function createAlertElement(alert) {
    const alertElement = document.createElement('div');
    alertElement.className = `alert alert-${alert.severity || 'info'}`;
    alertElement.dataset.id = alert.id;
    
    alertElement.innerHTML = `
        <div class="alert-header">
            <h3>${alert.title}</h3>
            <span class="alert-time">${formatTime(alert.timestamp)}</span>
        </div>
        <p class="alert-message">${alert.message}</p>
        <div class="alert-footer">
            <span class="alert-source">${alert.source}</span>
            <button class="alert-action" data-action="view">View Details</button>
        </div>
    `;
    
    // Add event listener for action button
    const actionButton = alertElement.querySelector('.alert-action');
    if (actionButton) {
        actionButton.addEventListener('click', () => {
            showAlertDetails(alert);
        });
    }
    
    return alertElement;
}

/**
 * Formats a timestamp
 * @param {string|number} timestamp - Timestamp to format
 * @returns {string} Formatted time string
 */
function formatTime(timestamp) {
    const date = new Date(timestamp);
    return date.toLocaleString();
}

/**
 * Shows detailed information for an alert
 * @param {Object} alert - Alert object
 */
function showAlertDetails(alert) {
    // Implement alert details view
    console.log('Showing details for alert:', alert);
    
    // Example: Create modal or navigate to details page
    window.location.href = `/alerts/${alert.id}`;
}

// Export functions
export { fetchAlerts, renderAlerts };
