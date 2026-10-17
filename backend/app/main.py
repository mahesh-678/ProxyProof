from __future__ import annotations

import csv
import io
import os
import secrets
import sqlite3
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, Header, HTTPException, Query
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

load_dotenv()
APP_DIR = Path(__file__).resolve().parent.parent
DB_PATH = Path(os.getenv("DATABASE_PATH", str(APP_DIR / "proxyproof.db")))
if not DB_PATH.is_absolute():
    DB_PATH = APP_DIR / DB_PATH
ROTATION_SECONDS = max(3, int(os.getenv("TOKEN_ROTATION_SECONDS", "45")))
MAX_RSSI = int(os.getenv("MAX_ATTENDANCE_RSSI", "-75"))

app = FastAPI(title="ProxyProof API", version="0.1.0",
              description="Educational BLE attendance prototype. Not production hardened.")
security = HTTPBearer(
    scheme_name="BearerAuth",
    description="Enter your demo token"
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True, allow_methods=["*"], allow_headers=["*"],
)

def connect():
    con = sqlite3.connect(DB_PATH, check_same_thread=False)
    con.row_factory = sqlite3.Row
    return con

def now_iso():
    return datetime.now(timezone.utc).isoformat()

def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with connect() as con:
        con.executescript("""
        PRAGMA foreign_keys = ON;
        CREATE TABLE IF NOT EXISTS users (
            id TEXT PRIMARY KEY, name TEXT NOT NULL, email TEXT UNIQUE NOT NULL,
            role TEXT NOT NULL CHECK(role IN ('ORGANISER','STUDENT')),
            demo_token TEXT UNIQUE NOT NULL
        );
        CREATE TABLE IF NOT EXISTS devices (
            id TEXT PRIMARY KEY, user_id TEXT NOT NULL UNIQUE REFERENCES users(id),
            device_name TEXT NOT NULL, approved INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS sessions (
            id TEXT PRIMARY KEY, organiser_id TEXT NOT NULL REFERENCES users(id),
            course_name TEXT NOT NULL, duration_seconds INTEGER NOT NULL,
            created_at TEXT NOT NULL, started_at TEXT, expires_at TEXT, status TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS attendance (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL REFERENCES sessions(id),
            student_id TEXT NOT NULL REFERENCES users(id),
            marked_at TEXT NOT NULL, rssi INTEGER, verification_status TEXT NOT NULL,
            UNIQUE(session_id, student_id)
        );
        CREATE TABLE IF NOT EXISTS audit_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT, action TEXT NOT NULL,
            actor_id TEXT, details TEXT, created_at TEXT NOT NULL
        );
        """)
        demo_users = [
            ("org-demo", "Demo Organiser", "organiser@proxyproof.local", "ORGANISER", "demo-organiser-token"),
            ("student-demo", "Demo Student", "student@proxyproof.local", "STUDENT", "demo-student-token"),
        ]
        for row in demo_users:
            con.execute("INSERT OR IGNORE INTO users(id,name,email,role,demo_token) VALUES(?,?,?,?,?)", row)
        con.execute("""INSERT OR IGNORE INTO devices(id,user_id,device_name,approved,created_at)
                       VALUES(?,?,?,?,?)""",
                    ("device-student-demo", "student-demo", "Demo Android", 1, now_iso()))

@app.on_event("startup")
def startup():
    init_db()

def get_user(
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    token = credentials.credentials.strip()

    with connect() as con:
        row = con.execute(
            "SELECT id,name,email,role FROM users WHERE demo_token=?",
            (token,)
        ).fetchone()

    if not row:
        raise HTTPException(status_code=401, detail="Invalid demo token")

    return dict(row)

def require_role(role):
    def check(user=Depends(get_user)):
        if user["role"] != role:
            raise HTTPException(403, f"{role} role required")
        return user
    return check

class LoginRequest(BaseModel):
    email: str
class SessionCreate(BaseModel):
    course_name: str = Field(min_length=2, max_length=100)
    duration_seconds: int = Field(default=300, ge=30, le=3600)
class MarkRequest(BaseModel):
    session_id: str
    student_id: str = "student-demo"
    token: str
    rssi: int = Field(ge=-127, le=20)
class DeviceRequest(BaseModel):
    device_name: str = Field(min_length=1, max_length=100)

@app.get("/")
def root():
    return {"app": "ProxyProof", "status": "ok", "docs": "/docs"}

@app.get("/health")
def health():
    return {"status": "ok"}

@app.post("/auth/login")
def login(body: LoginRequest):
    with connect() as con:
        row = con.execute("SELECT id,name,email,role,demo_token FROM users WHERE lower(email)=lower(?)",
                          (body.email,)).fetchone()
    if not row:
        raise HTTPException(401, "Unknown demo account. See README.")
    return {"user": {"id": row["id"], "name": row["name"], "email": row["email"], "role": row["role"]},
            "access_token": row["demo_token"], "token_type": "bearer"}

@app.post("/devices/register")
def register_device(body: DeviceRequest, user=Depends(require_role("STUDENT"))):
    with connect() as con:
        existing = con.execute("SELECT id FROM devices WHERE user_id=?", (user["id"],)).fetchone()
        if existing:
            con.execute("UPDATE devices SET device_name=?,approved=0,created_at=? WHERE user_id=?",
                        (body.device_name, now_iso(), user["id"]))
            action = "device_change_pending"
        else:
            con.execute("INSERT INTO devices(id,user_id,device_name,approved,created_at) VALUES(?,?,?,?,?)",
                        (secrets.token_hex(8), user["id"], body.device_name, 0, now_iso()))
            action = "device_registration_pending"
        con.execute("INSERT INTO audit_log(action,actor_id,details,created_at) VALUES(?,?,?,?)",
                    (action, user["id"], body.device_name, now_iso()))
    return {"status": "pending_approval", "message": "Organiser approval is required."}

@app.post("/sessions")
def create_session(body: SessionCreate, user=Depends(require_role("ORGANISER"))):
    session_id = "pp-" + secrets.token_hex(5)
    with connect() as con:
        con.execute("""INSERT INTO sessions(id,organiser_id,course_name,duration_seconds,created_at,status)
                       VALUES(?,?,?,?,?,?)""",
                    (session_id, user["id"], body.course_name, body.duration_seconds, now_iso(), "CREATED"))
        con.execute("INSERT INTO audit_log(action,actor_id,details,created_at) VALUES(?,?,?,?)",
                    ("session_created", user["id"], session_id, now_iso()))
    return {"id": session_id, "course_name": body.course_name, "duration_seconds": body.duration_seconds,
            "status": "CREATED"}

@app.post("/sessions/{session_id}/start")
def start_session(session_id: str, user=Depends(require_role("ORGANISER"))):
    now = time.time()
    with connect() as con:
        row = con.execute("SELECT * FROM sessions WHERE id=? AND organiser_id=?", (session_id, user["id"])).fetchone()
        if not row:
            raise HTTPException(404, "Session not found")
        if row["status"] == "CLOSED":
            raise HTTPException(409, "Session is already closed")
        started = now_iso()
        expires = datetime.fromtimestamp(now + row["duration_seconds"], timezone.utc).isoformat()
        con.execute("UPDATE sessions SET started_at=?,expires_at=?,status='ACTIVE' WHERE id=?",
                    (started, expires, session_id))
        con.execute("INSERT INTO audit_log(action,actor_id,details,created_at) VALUES(?,?,?,?)",
                    ("session_started", user["id"], session_id, now_iso()))
    return {"id": session_id, "status": "ACTIVE", "started_at": started, "expires_at": expires,
            "rotation_seconds": ROTATION_SECONDS}

@app.post("/sessions/{session_id}/close")
def close_session(session_id: str, user=Depends(require_role("ORGANISER"))):
    with connect() as con:
        row = con.execute("SELECT id FROM sessions WHERE id=? AND organiser_id=?", (session_id, user["id"])).fetchone()
        if not row:
            raise HTTPException(404, "Session not found")
        con.execute("UPDATE sessions SET status='CLOSED' WHERE id=?", (session_id,))
        con.execute("INSERT INTO audit_log(action,actor_id,details,created_at) VALUES(?,?,?,?)",
                    ("session_closed", user["id"], session_id, now_iso()))
    return {"id": session_id, "status": "CLOSED"}

@app.get("/sessions/active")
def active_sessions(user=Depends(get_user)):
    with connect() as con:
        rows = con.execute("""SELECT s.id,s.course_name,s.status,s.created_at,s.started_at,s.expires_at,
            (SELECT COUNT(*) FROM attendance a WHERE a.session_id=s.id) AS present_count
            FROM sessions s WHERE s.status IN ('ACTIVE','CREATED') ORDER BY s.created_at DESC""").fetchall()
    return [dict(r) for r in rows]

def current_demo_token(session_id: str, epoch=None):
    # Prototype token: time-bucket token. Production should use a keyed MAC and stronger auth.
    bucket = int(time.time() if epoch is None else epoch) // ROTATION_SECONDS
    import hashlib
    return hashlib.sha256(f"proxyproof-demo:{session_id}:{bucket}".encode()).hexdigest()[:12].upper()

@app.get("/sessions/{session_id}/token")
def session_token(session_id: str, user=Depends(require_role("ORGANISER"))):
    # For demo broadcast integration only. This endpoint exposes the current token to the organiser.
    with connect() as con:
        row = con.execute("SELECT status,expires_at FROM sessions WHERE id=? AND organiser_id=?",
                          (session_id, user["id"])).fetchone()
    if not row:
        raise HTTPException(404, "Session not found")
    if row["status"] != "ACTIVE":
        raise HTTPException(409, "Session is not active")
    if row["expires_at"] and datetime.fromisoformat(row["expires_at"]) < datetime.now(timezone.utc):
        raise HTTPException(410, "Session expired")
    return {"session_id": session_id, "token": current_demo_token(session_id),
            "valid_for_seconds": ROTATION_SECONDS}

@app.post("/attendance/mark")
def mark_attendance(body: MarkRequest, user=Depends(get_user)):
    if user["role"] != "STUDENT":
        raise HTTPException(403, "Student role required")
    # The student identity is taken from the authenticated account, not from body.student_id.
    with connect() as con:
        session = con.execute("SELECT * FROM sessions WHERE id=?", (body.session_id,)).fetchone()
        if not session:
            raise HTTPException(404, "Session not found")
        if session["status"] != "ACTIVE":
            raise HTTPException(409, "Session is not active")
        if session["expires_at"] and datetime.fromisoformat(session["expires_at"]) < datetime.now(timezone.utc):
            con.execute("UPDATE sessions SET status='EXPIRED' WHERE id=?", (body.session_id,))
            raise HTTPException(410, "Session expired")
        device = con.execute("SELECT approved FROM devices WHERE user_id=?", (user["id"],)).fetchone()
        if not device or not device["approved"]:
            raise HTTPException(403, "Registered device is not approved")
        if body.rssi < MAX_RSSI:
            raise HTTPException(403, f"Signal too weak (RSSI must be >= {MAX_RSSI} dBm)")
        expected = current_demo_token(body.session_id)
        if not secrets.compare_digest(body.token.upper(), expected):
            raise HTTPException(401, "Token invalid or expired")
        try:
            con.execute("""INSERT INTO attendance(session_id,student_id,marked_at,rssi,verification_status)
                           VALUES(?,?,?,?,?)""",
                        (body.session_id, user["id"], now_iso(), body.rssi, "VERIFIED_DEMO"))
        except sqlite3.IntegrityError:
            raise HTTPException(409, "Attendance already marked for this session")
        con.execute("INSERT INTO audit_log(action,actor_id,details,created_at) VALUES(?,?,?,?)",
                    ("attendance_marked", user["id"], body.session_id, now_iso()))
    return {"status": "present", "session_id": body.session_id, "student_id": user["id"],
            "marked_at": now_iso()}

@app.get("/attendance/history")
def history(session_id: Optional[str] = None, user=Depends(get_user)):
    with connect() as con:
        if user["role"] == "ORGANISER":
            if session_id:
                rows = con.execute("""SELECT a.session_id,a.student_id,u.name,a.marked_at,a.rssi,a.verification_status
                    FROM attendance a JOIN users u ON u.id=a.student_id WHERE a.session_id=? ORDER BY a.marked_at""",
                    (session_id,)).fetchall()
            else:
                rows = con.execute("""SELECT a.session_id,a.student_id,u.name,a.marked_at,a.rssi,a.verification_status
                    FROM attendance a JOIN users u ON u.id=a.student_id ORDER BY a.marked_at DESC""").fetchall()
        else:
            rows = con.execute("""SELECT a.session_id,a.student_id,u.name,a.marked_at,a.rssi,a.verification_status
                FROM attendance a JOIN users u ON u.id=a.student_id WHERE a.student_id=? ORDER BY a.marked_at DESC""",
                (user["id"],)).fetchall()
    return [dict(r) for r in rows]

@app.get("/attendance/export")
def export_csv(session_id: Optional[str] = None, user=Depends(require_role("ORGANISER"))):
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Session ID", "Student ID", "Student Name", "Marked At", "RSSI", "Verification"])
    with connect() as con:
        if session_id:
            rows = con.execute("""SELECT a.session_id,a.student_id,u.name,a.marked_at,a.rssi,a.verification_status
                FROM attendance a JOIN users u ON u.id=a.student_id WHERE a.session_id=? ORDER BY a.marked_at""",
                (session_id,)).fetchall()
        else:
            rows = con.execute("""SELECT a.session_id,a.student_id,u.name,a.marked_at,a.rssi,a.verification_status
                FROM attendance a JOIN users u ON u.id=a.student_id ORDER BY a.marked_at DESC""").fetchall()
    for r in rows:
        writer.writerow([r["session_id"], r["student_id"], r["name"], r["marked_at"], r["rssi"], r["verification_status"]])
    output.seek(0)
    return StreamingResponse(iter([output.getvalue()]), media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="proxyproof-attendance.csv"'})

@app.get("/dashboard/summary")
def summary(user=Depends(require_role("ORGANISER"))):
    with connect() as con:
        sessions = con.execute("SELECT COUNT(*) FROM sessions").fetchone()[0]
        active = con.execute("SELECT COUNT(*) FROM sessions WHERE status='ACTIVE'").fetchone()[0]
        present = con.execute("SELECT COUNT(*) FROM attendance").fetchone()[0]
    return {"sessions": sessions, "active_sessions": active, "attendance_marks": present}
