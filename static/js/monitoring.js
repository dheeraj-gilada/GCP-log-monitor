// Monitoring dashboard functionality

import { fetchAlerts, renderAlerts } from './alerts.js';

// Constants
const REFRESH_INTERVAL = 30000; // 30 seconds
let refreshTimer = null;

/**
 * Initializes the monitoring dashboard
 */
async function initMonitoringDashboard() {
    // Initialize components
    initMetricsPanel();
    await refreshAlerts();
    initLogStream();
    setupRefreshInterval();
    
    // Add event listeners
    document.getElementById('refresh-btn')?.addEventListener('click', refreshDashboard);
    document.getElementById('auto-refresh')?.addEventListener('change', toggleAutoRefresh);
}

/**
 * Refreshes all dashboard components
 */
async function refreshDashboard() {
    await Promise.all([
        refreshMetrics(),
        refreshAlerts(),
        refreshLogStream()
    ]);
    
    updateLastRefreshedTime();
}

/**
 * Updates the last refreshed timestamp
 */
function updateLastRefreshedTime() {
    const refreshTimeElement = document.getElementById('last-refreshed');
    if (refreshTimeElement) {
        const now = new Date();
        refreshTimeElement.textContent = now.toLocaleTimeString();
    }
}

/**
 * Initializes the metrics panel
 */
function initMetricsPanel() {
    console.log('Initializing metrics panel');
    refreshMetrics();
}

/**
 * Refreshes metrics data
 */
async function refreshMetrics() {
    try {
        const response = await fetch('/api/metrics');
        if (!response.ok) throw new Error('Failed to fetch metrics');
        
        const metrics = await response.json();
        renderMetrics(metrics);
    } catch (error) {
        console.error('Error refreshing metrics:', error);
    }
}

/**
 * Renders metrics data in the UI
 * @param {Object} metrics - Metrics data
 */
function renderMetrics(metrics) {
    // Example implementation - update with your actual metrics
    const elements = {
        logCount: document.getElementById('log-count'),
        errorRate: document.getElementById('error-rate'),
        processingTime: document.getElementById('processing-time'),
        anomalyCount: document.getElementById('anomaly-count')
    };
    
    // Update DOM elements if they exist
    if (elements.logCount) elements.logCount.textContent = metrics.logCount || 0;
    if (elements.errorRate) elements.errorRate.textContent = `${metrics.errorRate || 0}%`;
    if (elements.processingTime) elements.processingTime.textContent = `${metrics.avgProcessingTime || 0}ms`;
    if (elements.anomalyCount) elements.anomalyCount.textContent = metrics.anomalyCount || 0;
}

/**
 * Refreshes alerts
 */
async function refreshAlerts() {
    const alertsContainer = document.getElementById('alerts-container');
    if (!alertsContainer) return;
    
    const alerts = await fetchAlerts(5);
    renderAlerts(alerts, alertsContainer);
}

/**
 * Initializes the log stream
 */
function initLogStream() {
    console.log('Initializing log stream');
    refreshLogStream();
}

/**
 * Refreshes the log stream
 */
async function refreshLogStream() {
    try {
        const logContainer = document.getElementById('log-stream');
        if (!logContainer) return;
        
        const response = await fetch('/api/logs/recent?limit=10');
        if (!response.ok) throw new Error('Failed to fetch logs');
        
        const logs = await response.json();
        renderLogs(logs, logContainer);
    } catch (error) {
        console.error('Error refreshing log stream:', error);
    }
}

/**
 * Renders logs in the log container
 * @param {Array} logs - Array of log objects
 * @param {HTMLElement} container - Container element
 */
function renderLogs(logs, container) {
    // Clear container or prepare for new logs
    
    logs.forEach(log => {
        const logElement = createLogElement(log);
        container.appendChild(logElement);
    });
    
    // Auto-scroll to bottom
    container.scrollTop = container.scrollHeight;
}

/**
 * Creates an HTML element for a log entry
 * @param {Object} log - Log object
 * @returns {HTMLElement} Log element
 */
function createLogElement(log) {
    const logElement = document.createElement('div');
    logElement.className = `log-entry log-${log.severity.toLowerCase()}`;
    
    logElement.innerHTML = `
        <span class="log-time">${new Date(log.timestamp).toLocaleTimeString()}</span>
        <span class="log-severity">${log.severity}</span>
        <span class="log-message">${log.message}</span>
    `;
    
    return logElement;
}

/**
 * Sets up auto-refresh interval
 */
function setupRefreshInterval() {
    const autoRefreshCheckbox = document.getElementById('auto-refresh');
    if (autoRefreshCheckbox && autoRefreshCheckbox.checked) {
        startAutoRefresh();
    }
}

/**
 * Starts auto-refresh timer
 */
function startAutoRefresh() {
    if (refreshTimer) clearInterval(refreshTimer);
    refreshTimer = setInterval(refreshDashboard, REFRESH_INTERVAL);
}

/**
 * Stops auto-refresh timer
 */
function stopAutoRefresh() {
    if (refreshTimer) {
        clearInterval(refreshTimer);
        refreshTimer = null;
    }
}

/**
 * Toggles auto-refresh based on checkbox state
 */
function toggleAutoRefresh(e) {
    if (e.target.checked) {
        startAutoRefresh();
    } else {
        stopAutoRefresh();
    }
}

// Initialize on page load
document.addEventListener('DOMContentLoaded', initMonitoringDashboard);

// Export functions for use in other modules
export {
    refreshDashboard,
    refreshMetrics,
    refreshAlerts,
    refreshLogStream
};
