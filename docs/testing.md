# Test checklist

1. Start the API and open `/docs`.
2. Log in as organiser using `organiser@proxyproof.local`.
3. Create and start a session.
4. Log in as student using `student@proxyproof.local`.
5. Register a device, then approve it in the database only for local demo testing (`devices.approved=1`).
6. Get the current token with the organiser token endpoint.
7. Submit a mark request with the student bearer token and a plausible RSSI.
8. Confirm duplicate attendance is rejected.
9. Close the session and confirm new marks are rejected.
10. Export CSV from the organiser dashboard.

Use physical Android phones to test BLE. The included mobile sample is a BLE marker demo, not end-to-end attendance.
