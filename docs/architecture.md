# Architecture

- Android phones use BLE advertising/scanning for a proximity signal.
- FastAPI validates accounts, active sessions, time-limited demo tokens and RSSI policy.
- SQLite is used for a zero-setup local prototype. PostgreSQL can replace it later.
- React dashboard polls summary/session endpoints every three seconds.
- Attendance rows have a unique `(session_id, student_id)` constraint.

The current Android sample demonstrates BLE discovery only; it intentionally does not claim that it is already integrated with the API.
