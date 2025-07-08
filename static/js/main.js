// Main JavaScript entry point
import {
  initializeFileUploads,
  addMagicUIToFileUploads,
  uploadLogFile,
  updateFileUploadText,
  uploadGcpCredentials,
} from "./components/file-upload.js";
import {
  initializeModeSwitch,
  addMagicUIToModeSwitch,
} from "./components/mode-switch.js";
import { handleFormSubmit } from "./components/form-handlers.js";

// Initialize all components when DOM is fully loaded
document.addEventListener("DOMContentLoaded", function () {
  // Initialize mode switch functionality
  initializeModeSwitch();

  // Add progress bar to simulation upload section
  const simSection = document.getElementById("simulation-upload-section");
  let progressBar = document.createElement("div");
  progressBar.id = "upload-progress-bar";
  progressBar.style.display = "none";
  progressBar.style.height = "8px";
  progressBar.style.background = "#e5e7eb";
  progressBar.style.borderRadius = "4px";
  progressBar.style.margin = "10px 0 0 0";
  progressBar.innerHTML =
    '<div id="upload-progress-inner" style="height:100%;width:0;background:#10b981;border-radius:4px;transition:width 0.2s;"></div>';
  simSection.appendChild(progressBar);

  // Add status message below progress bar
  let uploadStatus = document.createElement("div");
  uploadStatus.id = "upload-status-message";
  uploadStatus.style.margin = "8px 0 0 0";
  uploadStatus.style.fontSize = "0.98rem";
  uploadStatus.style.fontWeight = "500";
  simSection.appendChild(uploadStatus);

  // Initialize file upload functionality with progress callback
  initializeFileUploads((progress) => {
    if (progress === 0) {
      progressBar.style.display = "block";
      document.getElementById("upload-progress-inner").style.width = "0";
      uploadStatus.textContent = "";
    }
  });

  // Prevent default form submission for the upload area
  if (simSection) {
    simSection.addEventListener("submit", function (e) {
      e.preventDefault();
    });
  }

  // Listen for file selection in simulation mode
  const simulationLogsInput = document.getElementById("simulation-logs");
  simulationLogsInput.addEventListener("change", async function () {
    console.log("Simulation file input change handler fired");
    if (simulationLogsInput.files.length > 0) {
      // Update file upload text to show filename
      const uploadArea = simulationLogsInput.closest(".file-upload");
      if (uploadArea) {
        updateFileUploadText(uploadArea, simulationLogsInput);
      }
      // Only upload the first file for now
      const file = simulationLogsInput.files[0];
      progressBar.style.display = "block";
      document.getElementById("upload-progress-inner").style.width = "0";
      uploadStatus.textContent = "";
      try {
        // Send mode as FormData
        const modeToggle = document.getElementById("mode-toggle-checkbox");
        const isSimulationMode = modeToggle && modeToggle.checked;
        const mode = isSimulationMode ? "simulation" : "live";
        await uploadLogFile(
          file,
          (percent) => {
            document.getElementById("upload-progress-inner").style.width =
              percent + "%";
          },
          mode,
        );
        uploadStatus.textContent = "Upload successful! Log pipeline started.";
        uploadStatus.style.color = "#10b981";
        // Set flag to indicate a log file was uploaded
        window.simulationLogUploaded = true;
        // Reset file input so the same file can be uploaded again
        simulationLogsInput.value = "";
        // Reset file upload text
        if (uploadArea) {
          const textElement = uploadArea.querySelector(".file-upload-text");
          if (textElement) {
            textElement.innerHTML =
              "<strong>Click to upload</strong> or drag and drop your files";
          }
        }
      } catch (err) {
        uploadStatus.textContent = "Upload failed: " + err.message;
        uploadStatus.style.color = "#dc2626";
        window.simulationLogUploaded = false;
      }
      setTimeout(() => {
        progressBar.style.display = "none";
        document.getElementById("upload-progress-inner").style.width = "0";
      }, 2000);
    } else {
      window.simulationLogUploaded = false;
    }
  });

  // Add monitoring status message div if not present
  let monitoringStatus = document.getElementById("monitoring-status-message");
  if (!monitoringStatus) {
    monitoringStatus = document.createElement("div");
    monitoringStatus.id = "monitoring-status-message";
    monitoringStatus.style.marginTop = "0.5rem";
    simSection.appendChild(monitoringStatus);
  }

  // Add progress bar and status message to GCP credentials upload area (live mode)
  const gcpCredentialsUploadArea = document.getElementById(
    "gcp-credentials-upload-area",
  );
  if (gcpCredentialsUploadArea) {
    let gcpProgressBar = document.getElementById("gcp-upload-progress-bar");
    if (!gcpProgressBar) {
      gcpProgressBar = document.createElement("div");
      gcpProgressBar.id = "gcp-upload-progress-bar";
      gcpProgressBar.style.display = "none";
      gcpProgressBar.style.height = "8px";
      gcpProgressBar.style.background = "#e5e7eb";
      gcpProgressBar.style.borderRadius = "4px";
      gcpProgressBar.style.margin = "10px 0 0 0";
      gcpProgressBar.innerHTML =
        '<div id="gcp-upload-progress-inner" style="height:100%;width:0;background:#10b981;border-radius:4px;transition:width 0.2s;"></div>';
      gcpCredentialsUploadArea.appendChild(gcpProgressBar);
    }
    let gcpUploadStatus = document.getElementById("gcp-upload-status");
    if (!gcpUploadStatus) {
      gcpUploadStatus = document.createElement("div");
      gcpUploadStatus.id = "gcp-upload-status";
      gcpUploadStatus.style.margin = "8px 0 0 0";
      gcpUploadStatus.style.fontSize = "0.98rem";
      gcpUploadStatus.style.fontWeight = "500";
      gcpCredentialsUploadArea.appendChild(gcpUploadStatus);
    }
  }

  // --- Live Mode Logic Rebuild ---
  function setupLiveMode() {
    const gcpUploadArea = document.getElementById(
      "gcp-credentials-upload-area",
    );
    const gcpFileInput = document.getElementById("gcp-credentials");
    const gcpFilenameSpan = document.getElementById("gcp-credentials-filename");
    const projectIdSelect = document.getElementById("project-id");
    const statusMsg = document.getElementById("gcp-live-status");
    let gcpCredentialsFile = null;

    if (gcpUploadArea && gcpFileInput) {
      gcpUploadArea.addEventListener("click", function (e) {
        if (e.target !== gcpFileInput) {
          gcpFileInput.value = ""; // Reset so same file can be re-selected
          gcpFileInput.click();
        }
      });
      gcpFileInput.addEventListener("change", async function () {
        if (gcpFileInput.files.length > 0) {
          gcpCredentialsFile = gcpFileInput.files[0];
          gcpFilenameSpan.textContent =
            "File selected: " + gcpCredentialsFile.name;
          gcpFilenameSpan.style.color = "#10b981";
          statusMsg.textContent = "Validating credentials...";
          statusMsg.style.color = "#374151";
          // Validate credentials
          const formData = new FormData();
          formData.append("service_account_file", gcpCredentialsFile);
          try {
            const resp = await fetch("/api/gcp/validate-credentials", {
              method: "POST",
              body: formData,
            });
            const data = await resp.json();
            if (!resp.ok || !data.success) {
              statusMsg.textContent =
                "Validation failed: " + (data.message || "Invalid credentials");
              statusMsg.style.color = "#dc2626";
              projectIdSelect.innerHTML =
                '<option value="" disabled selected>Select a project</option>';
              projectIdSelect.disabled = true;
              return;
            }
            statusMsg.textContent =
              "Validation successful. Fetching projects...";
            statusMsg.style.color = "#10b981";
            // Fetch projects
            const projectsForm = new FormData();
            projectsForm.append("service_account_file", gcpCredentialsFile);
            try {
              const projectsResp = await fetch("/api/gcp/projects", {
                method: "POST",
                body: projectsForm,
              });
              const projectsData = await projectsResp.json();
              if (!projectsResp.ok || !projectsData.success) {
                statusMsg.textContent =
                  "Failed to fetch projects: " +
                  (projectsData.message || "Unknown error");
                statusMsg.style.color = "#dc2626";
                projectIdSelect.innerHTML =
                  '<option value="" disabled selected>Select a project</option>';
                projectIdSelect.disabled = true;
                return;
              }
              // Populate project ID dropdown
              projectIdSelect.innerHTML =
                '<option value="" disabled selected>Select a project</option>';
              projectsData.projects.forEach((proj) => {
                const opt = document.createElement("option");
                opt.value = proj.projectId;
                opt.textContent = `${proj.name} (${proj.projectId})`;
                projectIdSelect.appendChild(opt);
              });
              projectIdSelect.disabled = false;
              statusMsg.textContent = "Projects loaded. Select a project.";
              statusMsg.style.color = "#10b981";
            } catch (err) {
              statusMsg.textContent =
                "Failed to fetch projects: " + (err.message || err);
              statusMsg.style.color = "#dc2626";
              projectIdSelect.innerHTML =
                '<option value="" disabled selected>Select a project</option>';
              projectIdSelect.disabled = true;
            }
          } catch (err) {
            statusMsg.textContent =
              "Validation failed: " + (err.message || err);
            statusMsg.style.color = "#dc2626";
            projectIdSelect.innerHTML =
              '<option value="" disabled selected>Select a project</option>';
            projectIdSelect.disabled = true;
          }
        } else {
          gcpCredentialsFile = null;
          gcpFilenameSpan.textContent = "No file selected.";
          gcpFilenameSpan.style.color = "#dc2626";
          statusMsg.textContent = "";
        }
      });
    }
  }

  // Call setupLiveMode after DOMContentLoaded
  setupLiveMode();

  // Wire up the shiny button for simulation and live mode
  const setupSubmitBtn = document.getElementById("setup-submit");
  const gcpUploadSpinner = document.getElementById("gcp-upload-spinner");
  if (setupSubmitBtn) {
    setupSubmitBtn.addEventListener("click", async function (e) {
      e.preventDefault();
      const modeToggle = document.getElementById("mode-toggle-checkbox");
      const isSimulationMode = modeToggle && modeToggle.checked;
      const mode = isSimulationMode ? "simulation" : "live";
      const monitoringStatus = document.getElementById(
        "monitoring-status-message",
      );
      monitoringStatus.textContent = "";
      monitoringStatus.style.color = "#374151";

      if (!isSimulationMode) {
        // Live GCP Logs mode
        const gcpFileInput = document.getElementById("gcp-credentials");
        const projectIdInput = document.getElementById("project-id");
        const gcpUploadStatus = document.getElementById("gcp-upload-status");
        const gcpProgressBar = document.getElementById(
          "gcp-upload-progress-bar",
        );
        const gcpProgressInner = document.getElementById(
          "gcp-upload-progress-inner",
        );
        setupSubmitBtn.disabled = true;
        if (!gcpFileInput || gcpFileInput.files.length === 0) {
          monitoringStatus.textContent =
            "Please select a service account JSON file.";
          monitoringStatus.style.color = "#dc2626";
          setupSubmitBtn.disabled = false;
          return;
        }
        if (!projectIdInput || !projectIdInput.value) {
          monitoringStatus.textContent = "Please select a GCP project.";
          monitoringStatus.style.color = "#dc2626";
          setupSubmitBtn.disabled = false;
          return;
        }
        // Ingest logs from GCP, send mode as FormData
        try {
          if (gcpProgressBar) gcpProgressBar.style.display = "block";
          if (gcpProgressInner) gcpProgressInner.style.width = "0";
          await uploadGcpCredentials(
            gcpFileInput.files[0],
            projectIdInput.value,
            (percent) => {
              if (gcpProgressInner)
                gcpProgressInner.style.width = percent + "%";
            },
            mode,
          );
          if (gcpUploadStatus) {
            gcpUploadStatus.textContent =
              "Logs fetched and ingested successfully!";
            gcpUploadStatus.style.color = "#10b981";
          }
        } catch (err) {
          monitoringStatus.textContent =
            "GCP log ingestion failed: " + (err.message || err);
          monitoringStatus.style.color = "#dc2626";
          setupSubmitBtn.disabled = false;
          if (gcpProgressBar) gcpProgressBar.style.display = "none";
          if (gcpProgressInner) gcpProgressInner.style.width = "0";
          return;
        } finally {
          if (gcpProgressBar) gcpProgressBar.style.display = "none";
          if (gcpProgressInner) gcpProgressInner.style.width = "0";
        }
        // Now run anomaly detection
        monitoringStatus.textContent = "Running anomaly detection...";
        monitoringStatus.style.color = "#374151";
        await runMonitoringPipeline(mode);
        setupSubmitBtn.disabled = false;
      } else {
        // Log Simulation mode
        if (!window.simulationLogUploaded) {
          monitoringStatus.textContent =
            "Please upload a log file for simulation.";
          monitoringStatus.style.color = "#dc2626";
          return;
        }
        monitoringStatus.textContent = "Running anomaly detection...";
        monitoringStatus.style.color = "#374151";
        await runMonitoringPipeline(mode);
        // Reset the flag after monitoring is run
        window.simulationLogUploaded = false;
      }
    });
  }

  // Mode switch: show/hide correct RCA output area
  const modeToggle = document.getElementById("mode-toggle-checkbox");
  const simStatusDiv = document.getElementById("monitoring-status-message-simulation");
  const liveStatusDiv = document.getElementById("monitoring-status-message-live");
  // Add debug borders to status divs for visibility
  simStatusDiv.style.border = "2px dashed red";
  liveStatusDiv.style.border = "2px dashed blue";
  
  function updateOutputVisibility() {
    if (modeToggle && modeToggle.checked) {
      // Simulation mode
      simStatusDiv.style.display = "";
      liveStatusDiv.style.display = "none";
      liveStatusDiv.innerHTML = "";
    } else {
      simStatusDiv.style.display = "none";
      liveStatusDiv.style.display = "";
      simStatusDiv.innerHTML = "";
    }
  }
  if (modeToggle) {
    modeToggle.addEventListener("change", updateOutputVisibility);
    updateOutputVisibility();
  }

  // Implement runMonitoringPipeline to GET from the correct endpoint and update the correct status div
  async function runMonitoringPipeline(mode) {
    const monitoringStatus = document.getElementById(
      mode === "simulation"
        ? "monitoring-status-message-simulation"
        : "monitoring-status-message-live"
    );
    monitoringStatus.classList.add("show");
    monitoringStatus.innerHTML =
      '<strong>Running RCA analysis...</strong><br><div id="rca-reports"></div>';
    monitoringStatus.style.color = "#374151";
    const rcaReportsDiv = monitoringStatus.querySelector("#rca-reports");
    let reportCount = 0;
    let done = false;
    // Collect parameters for GET
    const alertEmail = localStorage.getItem("alertEmail") || "";
    const lookback = 1000; // You can make this dynamic if needed
    const apiKey = "";
    // Use separate endpoints for simulation and live
    const endpoint = mode === "simulation"
      ? "/api/monitor/start-simulation"
      : "/api/monitor/start-live";
    const url = `${endpoint}?email=${encodeURIComponent(alertEmail)}&lookback=${lookback}&api_key=${encodeURIComponent(apiKey)}`;
    return new Promise((resolve, reject) => {
      const evtSource = new EventSource(url);
      evtSource.onmessage = function (event) {
        try {
          const data = JSON.parse(event.data);
          if (data.done) {
            done = true;
            if (reportCount === 0) {
              monitoringStatus.classList.add("show");
              monitoringStatus.innerHTML += "<br><strong>No anomalies detected.</strong>";
            } else {
              monitoringStatus.classList.add("show");
              monitoringStatus.innerHTML += `<br><strong>RCA complete! Total reports: ${data.total_alerts}</strong>`;
            }
            evtSource.close();
            resolve();
            return;
          }
          reportCount++;
          const report = data;
          console.log("Received RCA report:", report); // Debug log
          const reportDiv = document.createElement("div");
          reportDiv.style.marginBottom = "1em";
          reportDiv.style.padding = "0.5em";
          reportDiv.style.border = "1px solid #e5e7eb";
          reportDiv.style.borderRadius = "6px";
          reportDiv.innerHTML =
            `<b>Report #${reportCount}: ${report.title}</b><br>` +
            `<b>Severity:</b> ${report.severity}<br>` +
            `<b>Summary:</b> ${report.issue_summary}<br>` +
            `<b>Root Cause:</b> ${report.root_cause_analysis}<br>` +
            `<b>Impact:</b> ${report.impact_assessment}<br>` +
            `<b>Suggested Actions:</b> ${(report.suggested_actions || []).join(", ")}<br>`;
          rcaReportsDiv.appendChild(reportDiv);
          console.log("Appended reportDiv to rcaReportsDiv. Current HTML:", rcaReportsDiv.innerHTML);
        } catch (err) {
          monitoringStatus.classList.add("show");
          monitoringStatus.innerHTML += "<br>Error parsing RCA report.";
        }
      };
      evtSource.onerror = function (err) {
        if (!done) {
          monitoringStatus.classList.add("show");
          monitoringStatus.innerHTML += "<br>Error receiving RCA reports.";
          evtSource.close();
          reject(err);
        }
      };
    });
  }

  // Add form submission handler
  const setupForm = document.getElementById("setup-form");
  if (setupForm) {
    setupForm.addEventListener("submit", handleFormSubmit);
  }

  // Store alert email in localStorage after setup
  async function handleFormSubmit(e) {
    const alertEmailInput = document.getElementById("alert-email");
    if (alertEmailInput && alertEmailInput.value) {
      localStorage.setItem("alertEmail", alertEmailInput.value);
    }
  }

  // Apply Magic UI effects
  addMagicUIToFileUploads();
  addMagicUIToModeSwitch();

  // Add handler for Send Test Alert Email button
  const sendTestAlertBtn = document.getElementById("send-test-alert-btn");
  if (sendTestAlertBtn) {
    sendTestAlertBtn.addEventListener("click", async function () {
      const alertEmailInput = document.getElementById("alert-email");
      const email = alertEmailInput ? alertEmailInput.value : "";
      if (!email) {
        alert("Please enter a valid email address for alerts.");
        return;
      }
      sendTestAlertBtn.disabled = true;
      sendTestAlertBtn.querySelector("span").textContent = "Sending...";
      let statusMsg = document.getElementById("test-alert-status-message");
      if (!statusMsg) {
        statusMsg = document.createElement("div");
        statusMsg.id = "test-alert-status-message";
        statusMsg.style.marginTop = "0.5rem";
        sendTestAlertBtn.parentNode.appendChild(statusMsg);
      }
      statusMsg.textContent = "";
      statusMsg.style.color = "#374151";
      try {
        // Use separate endpoints for simulation and live
        const modeToggle = document.getElementById("mode-toggle-checkbox");
        const isSimulationMode = modeToggle && modeToggle.checked;
        const endpoint = isSimulationMode
          ? "/api/alerts/send-test-simulation"
          : "/api/alerts/send-test-live";
        const response = await fetch(endpoint, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ email }),
        });
        const result = await response.json();
        if (response.ok && result.success) {
          statusMsg.textContent = result.message;
          statusMsg.style.color = "#10b981";
        } else {
          statusMsg.textContent = result.message || "Failed to send test alert email.";
          statusMsg.style.color = "#dc2626";
        }
      } catch (err) {
        statusMsg.textContent = "Error: " + err.message;
        statusMsg.style.color = "#dc2626";
      } finally {
        sendTestAlertBtn.disabled = false;
        sendTestAlertBtn.querySelector("span").textContent = "Send Test Alert Email";
      }
    });
  }
});
