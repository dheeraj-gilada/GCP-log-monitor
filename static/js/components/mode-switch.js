// Mode switch functionality

/**
 * Initializes the mode switch toggle between live and simulation modes
 */
function initializeModeSwitch() {
    const liveModeRadio = document.getElementById('live-mode');
    const simulationModeRadio = document.getElementById('simulation-mode');
    const gcpCredentialsSection = document.getElementById('gcp-credentials-section');
    const simulationUploadSection = document.getElementById('simulation-upload-section');

    if (!liveModeRadio || !simulationModeRadio) {
        return; // Exit if elements don't exist
    }

    // Set initial state
    handleModeSwitch();

    // Add event listeners
    liveModeRadio.addEventListener('change', handleModeSwitch);
    simulationModeRadio.addEventListener('change', handleModeSwitch);

    /**
     * Handles the visibility of sections based on selected mode
     */
    function handleModeSwitch() {
        if (liveModeRadio.checked) {
            gcpCredentialsSection.classList.remove('hidden');
            simulationUploadSection.classList.add('hidden');
        } else {
            gcpCredentialsSection.classList.add('hidden');
            simulationUploadSection.classList.remove('hidden');
        }
    }
}

/**
 * Adds Magic UI animation classes to mode switch elements
 */
function addMagicUIToModeSwitch() {
    document.querySelectorAll('.mode-switch').forEach(element => {
        element.classList.add('magicui-mode-animate');
    });
}

// Export functions
export { initializeModeSwitch, addMagicUIToModeSwitch }; 