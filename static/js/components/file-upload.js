// File upload functionality

/**
 * Initializes drag and drop for file upload areas
 * @param {function} onUploadProgress - Optional callback for upload progress
 */
function initializeFileUploads(onUploadProgress) {
  const fileUploadAreas = document.querySelectorAll(".file-upload");

  fileUploadAreas.forEach((area) => {
    // Use a single fileInput variable per area
    const fileInput = area.querySelector('input[type="file"]');
    // Skip simulation upload area
    if (fileInput && fileInput.id === "simulation-logs") {
      return;
    }
    // Skip GCP credentials upload area to avoid double file picker
    if (area.id === "gcp-credentials-upload-area") {
      return;
    }
    // Add click handling
    area.addEventListener("click", () => {
      if (fileInput) {
        fileInput.click();
      }
    });

    // Initialize file input change listeners
    if (fileInput) {
      // Do not add a change handler here; let main.js handle it for simulation input
    }
  });
}

/**
 * Updates the text displayed in file upload area when files are selected
 * @param {HTMLElement} uploadArea - The file upload container element
 * @param {HTMLInputElement} fileInput - The file input element
 */
function updateFileUploadText(uploadArea, fileInput) {
  const textElement = uploadArea.querySelector(".file-upload-text");
  if (!textElement) return;

  if (fileInput.files.length > 0) {
    const fileNames = Array.from(fileInput.files)
      .map((f) => f.name)
      .join(", ");

    textElement.innerHTML = `<strong>Selected:</strong> ${fileNames}`;
  } else {
    // Reset to default text if no files selected
    textElement.innerHTML = `<strong>Click to upload</strong> or drag and drop your files`;
  }
}

/**
 * Adds Magic UI animation classes to file uploads
 */
function addMagicUIToFileUploads() {
  document.querySelectorAll(".file-upload").forEach((element) => {
    element.classList.add("magicui-upload-animate");
  });
}

/**
 * Uploads a file to the backend and tracks progress
 * @param {File} file - The file to upload
 * @param {function} onProgress - Callback for progress updates (0-100)
 * @param {string} mode - The mode for the upload (e.g., 'simulation', 'live')
 * @returns {Promise<object>} - The response from the backend
 */
function uploadLogFile(file, onProgress, mode = "simulation") {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open("POST", "/api/logs/ingest/file", true);

    xhr.upload.onprogress = function (e) {
      if (e.lengthComputable && onProgress) {
        const percent = Math.round((e.loaded / e.total) * 100);
        onProgress(percent);
      }
    };

    xhr.onload = function () {
      if (xhr.status >= 200 && xhr.status < 300) {
        try {
          resolve(JSON.parse(xhr.responseText));
        } catch (err) {
          reject(err);
        }
      } else {
        reject(new Error("Upload failed"));
      }
    };

    xhr.onerror = function () {
      reject(new Error("Network error during upload"));
    };

    const formData = new FormData();
    formData.append("file", file);
    formData.append("mode", mode);
    xhr.send(formData);
  });
}

/**
 * Uploads GCP credentials (service account JSON) and project ID to the backend and tracks progress
 * @param {File} file - The service account JSON file
 * @param {string} projectId - The GCP project ID
 * @param {function} onProgress - Callback for progress updates (0-100)
 * @param {string} mode - The mode for the upload (e.g., 'simulation', 'live')
 * @returns {Promise<object>} - The response from the backend
 */
function uploadGcpCredentials(file, projectId, onProgress, mode = "live") {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open("POST", "/api/logs/ingest/gcp", true);

    xhr.upload.onprogress = function (e) {
      if (e.lengthComputable && onProgress) {
        const percent = Math.round((e.loaded / e.total) * 100);
        onProgress(percent);
      }
    };

    xhr.onload = function () {
      if (xhr.status >= 200 && xhr.status < 300) {
        try {
          resolve(JSON.parse(xhr.responseText));
        } catch (err) {
          reject(err);
        }
      } else {
        let errMsg = "Upload failed";
        try {
          const resp = JSON.parse(xhr.responseText);
          if (resp.detail) errMsg = resp.detail;
        } catch {}
        reject(new Error(errMsg));
      }
    };

    xhr.onerror = function () {
      reject(new Error("Network error during upload"));
    };

    const formData = new FormData();
    formData.append("project_id", projectId);
    formData.append("service_account_file", file);
    formData.append("mode", mode);
    xhr.send(formData);
  });
}

// Export functions
export {
  initializeFileUploads,
  updateFileUploadText,
  addMagicUIToFileUploads,
  uploadLogFile,
  uploadGcpCredentials,
};
