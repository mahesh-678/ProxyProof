import React, { useEffect, useState } from 'react'
import { createRoot } from 'react-dom/client'
import './style.css'

const API = 'http://127.0.0.1:8000'
const ORG_TOKEN = 'demo-organiser-token'

function App() {
  const [course, setCourse] = useState('Computer Networks')
  const [duration, setDuration] = useState(300)
  const [sessions, setSessions] = useState([])
  const [summary, setSummary] = useState({sessions: 0, active_sessions: 0, attendance_marks: 0})
  const [message, setMessage] = useState('Connecting to API…')
  const headers = { 'Content-Type': 'application/json', Authorization: `Bearer ${ORG_TOKEN}` }

  async function refresh() {
    try {
      const [s, sum] = await Promise.all([
        fetch(`${API}/sessions/active`, { headers }).then(r => { if (!r.ok) throw new Error('API request failed'); return r.json() }),
        fetch(`${API}/dashboard/summary`, { headers }).then(r => r.json())
      ])
      setSessions(s); setSummary(sum); setMessage('Connected')
    } catch (e) { setMessage('Backend not running — start FastAPI in the backend folder.') }
  }
  useEffect(() => { refresh(); const id = setInterval(refresh, 3000); return () => clearInterval(id) }, [])

  async function createSession() {
    try {
      const r = await fetch(`${API}/sessions`, { method: 'POST', headers, body: JSON.stringify({course_name: course, duration_seconds: Number(duration)}) })
      const data = await r.json()
      if (!r.ok) throw new Error(data.detail || 'Could not create session')
      setMessage(`Created session ${data.id}`); refresh()
    } catch (e) { setMessage(e.message) }
  }
  async function action(id, verb) {
    try {
      const r = await fetch(`${API}/sessions/${id}/${verb}`, { method: 'POST', headers })
      const data = await r.json()
      if (!r.ok) throw new Error(data.detail || 'Request failed')
      setMessage(`${id}: ${data.status}`); refresh()
    } catch (e) { setMessage(e.message) }
  }

  return <div className="app">
    <header><div><span className="brand-mark">P</span><div><h1>ProxyProof</h1><p>Bluetooth Attendance Console</p></div></div><span className="status"><i/> {message}</span></header>
    <section className="hero"><div><p className="eyebrow">ORGANISER WORKSPACE</p><h2>Attendance, verified.</h2><p>Manage sessions and monitor attendance from one place.</p></div><div className="hero-badge">BLE <span>●</span></div></section>
    <section className="stats">
      <article><span>Total sessions</span><strong>{summary.sessions}</strong></article>
      <article><span>Active sessions</span><strong>{summary.active_sessions}</strong></article>
      <article><span>Attendance marks</span><strong>{summary.attendance_marks}</strong></article>
    </section>
    <section className="panel">
      <div className="panel-title"><div><h3>Create attendance session</h3><p>Start a time-limited classroom check-in.</p></div></div>
      <div className="form"><label>Course or class<input value={course} onChange={e => setCourse(e.target.value)} /></label><label>Duration<select value={duration} onChange={e => setDuration(e.target.value)}><option value="60">1 minute (test)</option><option value="300">5 minutes</option><option value="600">10 minutes</option><option value="1800">30 minutes</option></select></label><button onClick={createSession}>＋ Create session</button></div>
    </section>
    <section className="panel">
      <div className="panel-title"><div><h3>Attendance sessions</h3><p>Automatically refreshes every three seconds.</p></div><button className="secondary" onClick={refresh}>Refresh</button></div>
      {sessions.length === 0 ? <div className="empty">No active or draft sessions yet. Create one above.</div> :
        <div className="table-wrap"><table><thead><tr><th>Course</th><th>Session ID</th><th>Status</th><th>Present</th><th>Actions</th></tr></thead><tbody>
          {sessions.map(s => <tr key={s.id}><td>{s.course_name}</td><td className="mono">{s.id}</td><td><span className={`pill ${s.status.toLowerCase()}`}>{s.status}</span></td><td>{s.present_count}</td><td className="actions">{s.status === 'CREATED' && <button onClick={() => action(s.id,'start')}>Start</button>}{s.status === 'ACTIVE' && <><button className="secondary" onClick={() => window.open(`${API}/attendance/export?session_id=${s.id}`, '_blank')}>Export CSV</button><button className="danger" onClick={() => action(s.id,'close')}>Close</button></>}</td></tr>)}
        </tbody></table></div>}
    </section>
    <footer>ProxyProof prototype · BLE signal strength is an estimate, not proof of exact distance.</footer>
  </div>
}
createRoot(document.getElementById('root')).render(<App />)
