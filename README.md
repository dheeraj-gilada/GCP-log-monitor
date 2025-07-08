# GCP Log Monitoring System

A modern, LLM-powered log monitoring and root cause analysis (RCA) platform for Google Cloud Platform (GCP) environments. Features real-time and simulation modes, anomaly detection, RCA via OpenAI, and alerting via email.

---

## Architecture Overview

- **Backend:** FastAPI, Redis (separate DBs for simulation/live), optional TimescaleDB, OpenAI LLM for RCA
- **Frontend:** Modern web UI (HTML/JS/CSS), real-time streaming of RCA results
- **Agents:**
  - **Agent 1:** Groups anomalies by similarity/proximity
  - **Agent 2:** Performs RCA on each group, generates structured reports
- **Alerting:** Sends RCA reports via email (SMTP)
- **Modes:**
  - **Simulation:** Upload and analyze sample logs
  - **Live:** Ingest logs from GCP projects using service account credentials

---

## Setup Instructions

### 1. Clone the Repository
```bash
git clone <your-repo-url>
cd GCP-log-monitoring
```

### 2. Environment Variables
- Copy the example file and fill in your secrets:
```bash
cp .env.example .env
# Edit .env and set your OpenAI API key, SMTP credentials, and any custom Redis/DB URLs
```

### 3. Install Dependencies (for local/dev)
```bash
pip install -r requirements.txt
```

### 4. Docker Setup (Recommended)
- Build and run with Docker Compose:
```bash
docker-compose build
docker-compose up
```
- The app will be available at [http://localhost:8000](http://localhost:8000)

### 5. GCP Credentials
- For live mode, upload a GCP service account JSON with `logging.viewer` permissions.
- Select your GCP project in the UI.

### 6. OpenAI API Key
- Required for RCA (LLM) features. Set `OPENAI_API_KEY` in your `.env`.

### 7. SMTP/Email
- Set `SMTP_USER`, `SMTP_PASS`, and `SMTP_SENDER` in your `.env` to enable alert emails.

---

## Sample Logs and Expected Outputs

- **Sample logs:** See `gcp-sample-logs/` for example GCP log files.
- **Expected output:**
  - Anomalies are detected and grouped
  - RCA reports are streamed to the frontend and shown in the UI
  - Alert emails are sent with structured RCA details

---

## Assumptions, Limitations, and Future Improvements

- **Assumptions:**
  - User provides valid GCP credentials and has access to logs
  - OpenAI API key is valid and has sufficient quota
  - SMTP credentials are correct for sending emails
- **Limitations:**
  - RCA quality depends on LLM and log quality
  - Only GCP logs are supported out of the box
  - TimescaleDB is optional and not required for core features
- **Future Improvements:**
  - Support for more cloud providers (AWS, Azure)
  - More advanced alerting and notification channels
  - UI/UX enhancements and dashboarding
  - Pluggable ML/AI backends

---

## Full Setup: From Clone to Run

1. **Clone the repo:**
   ```bash
   git clone <your-repo-url>
   cd GCP-log-monitoring
   ```
2. **Copy and edit .env:**
   ```bash
   cp .env.example .env
   # Edit .env and fill in required secrets
   ```
3. **(Optional) Install Python dependencies:**
   ```bash
   pip install -r requirements.txt
   ```
4. **Build and run with Docker Compose:**
   ```bash
   docker-compose build
   docker-compose up
   ```
5. **Access the app:**
   - Open [http://localhost:8000](http://localhost:8000) in your browser
6. **For live GCP logs:**
   - Upload your GCP service account JSON in the UI
   - Select your GCP project
7. **For simulation mode:**
   - Upload sample logs from `gcp-sample-logs/`
8. **Monitor, analyze, and receive RCA reports and alerts!**

---

For questions, issues, or contributions, please open an issue or pull request on GitHub.
