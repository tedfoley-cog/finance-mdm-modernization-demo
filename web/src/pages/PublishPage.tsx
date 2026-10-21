import { useEffect, useState } from 'react'
import { api, type ImpactSummary, type PublishRun } from '../api/client'
import { Badge } from '../components/Badge'
import { fmtDate } from '../lib/format'

export default function PublishPage() {
  const [runs, setRuns] = useState<PublishRun[]>([])
  const [summary, setSummary] = useState<ImpactSummary | null>(null)
  const [msg, setMsg] = useState<string | null>(null)
  const load = () => { api.publishRuns().then(setRuns); api.publishSummary().then(setSummary) }
  useEffect(load, [])
  const publish = async (t: string) => {
    try { const r = await api.publish(t); setMsg(`Published ${r.record_count} ${t} records to ${r.s3_key}`); load() }
    catch (e) { setMsg((e as Error).message) }
  }
  return (
    <>
      <h1>Publish golden records</h1>
      <div className="panel">
        {summary && (
          <div className="stats">
            <div className="stat"><b>{summary.cost_centers}</b>active cost centers</div>
            <div className="stat"><b>{summary.vendors}</b>active vendors</div>
            <div className="stat"><b>{summary.gl_accounts}</b>GL accounts</div>
            <div className="stat"><b>{summary.pending_change_requests}</b>pending change requests</div>
            <div className="stat"><b>{summary.last_publish ? summary.last_publish.entity_type : '—'}</b>last publish<div className="muted">{fmtDate(summary.last_publish?.created_at)}</div></div>
          </div>
        )}
      </div>
      <div className="panel">
        <div className="toolbar">
          {['vendor', 'cost_center', 'gl_account'].map(t => <button key={t} onClick={() => publish(t)}>Publish {t.replace('_', ' ')}s</button>)}
          <span className="muted">Writes JSONL to the publish bucket; the S3 event triggers the Snowflake landing load.</span>
        </div>
        {msg && <p className="muted mono">{msg}</p>}
        <table>
          <thead><tr><th>Run</th><th>Entity</th><th>Records</th><th>S3 key</th><th>Checksum</th><th>Status</th><th>Published</th></tr></thead>
          <tbody>{runs.map(r => <tr key={r.id}><td>{r.id}</td><td>{r.entity_type}</td><td>{r.record_count}</td><td className="mono">{r.s3_key}</td><td className="mono">{r.checksum.slice(0, 12)}…</td><td><Badge value={r.status} /></td><td>{fmtDate(r.created_at)}</td></tr>)}</tbody>
        </table>
      </div>
    </>
  )
}
