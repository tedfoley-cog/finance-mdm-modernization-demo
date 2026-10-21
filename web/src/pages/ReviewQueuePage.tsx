import { useEffect, useState } from 'react'
import { api, type ChangeRequest } from '../api/client'
import { Badge } from '../components/Badge'
import { fmtDate } from '../lib/format'

export default function ReviewQueuePage() {
  const [status, setStatus] = useState('PENDING')
  const [rows, setRows] = useState<ChangeRequest[]>([])
  const [note, setNote] = useState<Record<number, string>>({})
  const [msg, setMsg] = useState<string | null>(null)
  const load = () => api.changeRequests(status === 'ALL' ? undefined : status).then(setRows).catch(e => setMsg(e.message))
  useEffect(() => { load() }, [status]) // eslint-disable-line react-hooks/exhaustive-deps

  const decide = async (cr: ChangeRequest, decision: 'APPROVE' | 'REJECT') => {
    try { await api.review(cr.id, decision, note[cr.id] ?? ''); setMsg(`#${cr.id} ${decision}D`); load() }
    catch (e) { setMsg((e as Error).message) }
  }

  return (
    <>
      <h1>Change request review</h1>
      <div className="panel">
        <div className="toolbar">
          {['PENDING', 'APPROVED', 'REJECTED', 'ALL'].map(s => <button key={s} className={status === s ? '' : 'secondary'} onClick={() => setStatus(s)}>{s}</button>)}
          <span className="muted" style={{ marginLeft: 'auto' }}>Four-eyes: the requester cannot approve their own change.</span>
        </div>
        {msg && <p className="muted">{msg}</p>}
        <table>
          <thead><tr><th>#</th><th>Entity</th><th>Key</th><th>Action</th><th>Payload</th><th>Requested</th><th>Status</th><th>Review</th></tr></thead>
          <tbody>
            {rows.map(cr => (
              <tr key={cr.id}>
                <td>{cr.id}</td><td>{cr.entity_type}</td><td className="mono">{cr.entity_key}</td><td>{cr.action}</td>
                <td className="mono" style={{ maxWidth: 360, whiteSpace: 'pre-wrap' }}>{cr.payload}</td>
                <td>{cr.requested_by}<br /><span className="muted">{fmtDate(cr.created_at)}</span></td>
                <td><Badge value={cr.status} />{cr.reviewed_by && <div className="muted">{cr.reviewed_by}: {cr.review_note || '—'}</div>}</td>
                <td>
                  {cr.status === 'PENDING' && (
                    <div style={{ display: 'flex', gap: 6, flexDirection: 'column' }}>
                      <input placeholder="Review note" value={note[cr.id] ?? ''} onChange={e => setNote({ ...note, [cr.id]: e.target.value })} />
                      <div style={{ display: 'flex', gap: 6 }}>
                        <button onClick={() => decide(cr, 'APPROVE')}>Approve</button>
                        <button className="danger" onClick={() => decide(cr, 'REJECT')}>Reject</button>
                      </div>
                    </div>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  )
}
