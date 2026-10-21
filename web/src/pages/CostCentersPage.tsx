import { useEffect, useState } from 'react'
import { api, type CostCenter } from '../api/client'
import { Badge } from '../components/Badge'
import { COST_CENTER_CODE_PATTERN, fmtDate, padCostCenterCode } from '../lib/format'

export default function CostCentersPage() {
  const [entity, setEntity] = useState('US01')
  const [q, setQ] = useState('')
  const [rows, setRows] = useState<CostCenter[]>([])
  const [selected, setSelected] = useState<CostCenter | null>(null)
  const [children, setChildren] = useState<CostCenter[]>([])
  const [showForm, setShowForm] = useState(false)
  const [msg, setMsg] = useState<string | null>(null)

  const load = () => api.costCenters(entity, q).then(setRows).catch(e => setMsg(e.message))
  useEffect(() => { load() }, [entity, q]) // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => { if (selected) api.costCenterChildren(selected.entity_code, selected.cost_center_code).then(setChildren) }, [selected])

  return (
    <>
      <h1>Cost centers</h1>
      <div className="panel">
        <div className="toolbar">
          <select value={entity} onChange={e => setEntity(e.target.value)}>
            {['US01', 'US02', 'DE01', 'GB01', 'IN01', 'BR01', 'JP01', 'AU01'].map(e => <option key={e}>{e}</option>)}
          </select>
          <input placeholder="Search code or description" value={q} onChange={e => setQ(e.target.value)} style={{ width: 280 }} />
          <span className="muted">{rows.length} rows</span>
          <button style={{ marginLeft: 'auto' }} onClick={() => setShowForm(s => !s)}>New cost center</button>
        </div>
        {msg && <p className="error">{msg}</p>}
        {showForm && <NewCostCenterForm entity={entity} onDone={m => { setMsg(m); setShowForm(false) }} />}
        <div className="grid2">
          <table>
            <thead><tr><th>Code</th><th>Description</th><th>Parent</th><th>Profit ctr</th><th>Status</th></tr></thead>
            <tbody>
              {rows.map(r => (
                <tr key={r.cost_center_code} className="clickable" onClick={() => setSelected(r)}>
                  <td className="mono">{r.cost_center_code}</td><td>{r.description}</td>
                  <td className="mono">{r.parent_cost_center_code ?? '—'}</td><td className="mono">{r.profit_center_code ?? '—'}</td>
                  <td><Badge value={r.status} /></td>
                </tr>
              ))}
            </tbody>
          </table>
          <div>
            {selected ? (
              <>
                <h2>{selected.entity_code} / {selected.cost_center_code}</h2>
                <dl className="kv">
                  <dt>Description</dt><dd>{selected.description}</dd>
                  <dt>Manager</dt><dd className="mono">{selected.manager_employee_id ?? '—'}</dd>
                  <dt>Valid</dt><dd>{selected.valid_from} → {selected.valid_to ?? 'open'}</dd>
                  <dt>Source</dt><dd>{selected.source_system}</dd>
                  <dt>Updated</dt><dd>{fmtDate(selected.updated_at)}</dd>
                </dl>
                <h2 style={{ marginTop: 16 }}>Children ({children.length})</h2>
                <ul className="mono">{children.map(c => <li key={c.cost_center_code}>{c.cost_center_code} — {c.description}</li>)}</ul>
              </>
            ) : <p className="muted">Select a cost center to see its hierarchy.</p>}
          </div>
        </div>
      </div>
    </>
  )
}

function NewCostCenterForm({ entity, onDone }: { entity: string; onDone: (msg: string) => void }) {
  const [form, setForm] = useState({ cost_center_code: '', description: '', parent_cost_center_code: '', manager_employee_id: '', profit_center_code: '' })
  const [err, setErr] = useState<string | null>(null)
  const set = (k: keyof typeof form) => (e: React.ChangeEvent<HTMLInputElement>) => setForm({ ...form, [k]: e.target.value })
  const submit = async (e: React.FormEvent) => {
    e.preventDefault()
    const code = padCostCenterCode(form.cost_center_code)
    if (!COST_CENTER_CODE_PATTERN.test(code)) { setErr('Cost center code must be 6 digits'); return }
    try {
      const cr = await api.createCostCenter({ entity_code: entity, ...form, cost_center_code: code, parent_cost_center_code: form.parent_cost_center_code || null, manager_employee_id: form.manager_employee_id || null, profit_center_code: form.profit_center_code || null })
      onDone(`Change request #${cr.id} queued for approval`)
    } catch (ex) { setErr((ex as Error).message) }
  }
  return (
    <form className="panel form" onSubmit={submit}>
      <label>Cost center code (6 digits)<input className="mono" maxLength={6} value={form.cost_center_code} onChange={set('cost_center_code')} required /></label>
      <label>Parent code<input className="mono" maxLength={6} value={form.parent_cost_center_code} onChange={set('parent_cost_center_code')} /></label>
      <label className="full">Description<input value={form.description} onChange={set('description')} required maxLength={120} /></label>
      <label>Manager employee id<input value={form.manager_employee_id} onChange={set('manager_employee_id')} /></label>
      <label>Profit center<input value={form.profit_center_code} onChange={set('profit_center_code')} /></label>
      {err && <p className="error full">{err}</p>}
      <div className="full"><button type="submit">Submit for approval</button></div>
    </form>
  )
}
