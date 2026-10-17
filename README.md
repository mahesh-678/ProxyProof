# ProxyProof — Bluetooth Attendance

A starter full-stack project for a BLE-based classroom attendance prototype:
- FastAPI backend with SQLite for easy local development
- React + Vite organiser dashboard with live polling
- Android Kotlin starter app structure and BLE implementation notes
- Rotating short-lived session tokens, device registration placeholders, attendance history, CSV export

> **Prototype security note:** BLE RSSI is only a rough proximity signal and cannot prove exact distance. Rotating tokens deter simple replay but do not prevent sophisticated relay attacks. Use this for a controlled demo, not as a sole high-stakes attendance control.

## Requirements
- Windows 11
- Python 3.11+
- Node.js LTS
- Android Studio for the Android app
- Two physical Android phones for BLE testing (organiser and student)
- No Linux installation is required.

## 1. Start the backend (Windows PowerShell)
Open PowerShell in `backend`:

```powershell
cd backend
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

API docs: `http://127.0.0.1:8000/docs`

The starter uses SQLite so you can run it immediately without installing PostgreSQL. The DB file is created at `backend/proxyproof.db`.

Demo accounts are created on first run:
- Organiser: `organiser@proxyproof.local` / `DemoPass123!`
- Student: `student@proxyproof.local` / `DemoPass123!`

Change these demo credentials before any real deployment.

## 2. Start the dashboard
Open a second PowerShell window:

```powershell
cd dashboard
npm install
npm run dev -- --host 0.0.0.0
```

Open the URL printed by Vite, usually `http://localhost:5173`.

The demo dashboard polls the backend every 3 seconds and can create/close sessions and view attendance. This is a starter UI, not a production-ready system.

## 3. Android app
Open Android Studio, choose **Open**, and select `mobile/ProxyProofAndroid`. Let Gradle sync. Use a physical Android device to run it.

The Android directory includes a minimal Kotlin BLE scanner/broadcaster example and a basic UI. BLE APIs require runtime permissions and real device testing; implementation details vary by Android version. The mobile sample is a starting point and is not yet wired to all backend endpoints.

## 4. LAN testing with a phone
If the backend runs on your Windows laptop and the Android phone is on the same Wi-Fi:
1. Find your laptop's local IPv4 address with `ipconfig`.
2. Replace `10.0.2.2` or `127.0.0.1` in the Android API base URL with the laptop's IPv4 address.
3. Ensure Windows Firewall allows Python on private networks if prompted.
4. Use only a trusted private network. Do not expose this demo server to the public internet.

## API overview
- `POST /auth/login`
- `POST /sessions`
- `POST /sessions/{session_id}/start`
- `POST /sessions/{session_id}/close`
- `GET /sessions/active`
- `POST /attendance/mark`
- `GET /attendance/history`
- `GET /attendance/export` (CSV)

## Important implementation limitations
- Demo authentication uses a simple bearer token model suitable only for local demonstration.
- Device approval is represented as a basic field and needs stronger administrative workflows.
- Rotating token generation/validation is implemented server-side for the prototype, but BLE broadcast integration and attendance request integration need end-to-end testing.
- The example RSSI threshold is configurable and should be calibrated in the room.
- Before production use: use HTTPS, strong password hashing, robust auth/session handling, CSRF protections where applicable, rate limits, audit logging, privacy notices, and a threat model.

## Suggested project demo
1. Log in as organiser in the dashboard.
2. Create a session for a course and duration.
3. Start the session.
4. Use `/docs` to test attendance API with a student ID and current token.
5. Verify the attendance table refreshes.
6. Close the session and export CSV.
7. Demonstrate BLE scan/broadcast separately on two Android phones, then integrate it with the API.

## GitHub
```powershell
git init
git add .
git commit -m "Initial ProxyProof Bluetooth attendance prototype"
```
Create an empty GitHub repository and add its remote URL before `git push`.
