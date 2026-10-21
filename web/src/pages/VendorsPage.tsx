import { useEffect, useState } from 'react'
import { api, type Vendor } from '../api/client'
import { Badge } from '../components/Badge'
import { normalizeTaxId } from '../lib/format'

export default function VendorsPage() {
  const [q, setQ] = useState('')
  const [rows, setRows] = useState<Vendor[]>([])
  const [dupes, setDupes] = useState<Vendor[][]>([])
  const [tab, setTab] = useState<'list' | 'dupes'>('list')
  const [msg, setMsg] = useState<string | null>(null)

  useEffect(() => { api.vendors(q).then(setRows).catch(e => setMsg(e.message)) }, [q])
  useEffect(() => { api.vendorDuplicates().then(setDupes).catch(() => {}) }, [])

  const retire = async (v: Vendor) => {
    try { const cr = await api.updateVendor(v.vendor_id, { vendor_id: v.vendor_id, legal_name: v.legal_name, tax_id: v.tax_id, country_code: v.country_code, payment_terms: v.payment_terms, default_cost_center_code: v.default_cost_center_code, status: 'RETIRED' }); setMsg(`Change request #${cr.id} queued (retire ${v.vendor_id})`) }
    catch (e) { setMsg((e as Error).message) }
  }

  return (
    <>
      <h1>Vendors</h1>
      <div className="panel">
        <div className="toolbar">
          <button className={tab === 'list' ? '' : 'secondary'} onClick={() => setTab('list')}>All vendors</button>
          <button className={tab === 'dupes' ? '' : 'secondary'} onClick={() => setTab('dupes')}>Duplicate candidates ({dupes.length})</button>
          {tab === 'list' && <input placeholder="Name, vendor id or tax id" value={q} onChange={e => setQ(e.target.value)} style={{ width: 300, marginLeft: 'auto' }} />}
        </div>
        {msg && <p className="muted">{msg}</p>}
        {tab === 'list' ? (
          <table>
            <thead><tr><th>Vendor</th><th>Legal name</th><th>Country</th><th>Tax id</th><th>Normalized</th><th>Default CC</th><th>Terms</th><th>Status</th><th></th></tr></thead>
            <tbody>
              {rows.map(v => (
                <tr key={v.vendor_id}>
                  <td className="mono">{v.vendor_id}</td><td>{v.legal_name}</td><td>{v.country_code}</td>
                  <td className="mono">{v.tax_id ?? '—'}</td><td className="mono muted">{v.tax_id_normalized ?? normalizeTaxId(v.tax_id) ?? '—'}</td>
                  <td className="mono">{v.default_cost_center_code ?? '—'}</td><td>{v.payment_terms}</td><td><Badge value={v.status} /></td>
                  <td>{v.status === 'ACTIVE' && <button className="danger" onClick={() => retire(v)}>Retire</button>}</td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          dupes.length === 0 ? <p className="muted">No duplicate candidates.</p> : dupes.map(g => (
            <div key={g[0].tax_id_normalized} className="panel">
              <h2>Tax id {g[0].tax_id_normalized}</h2>
              <table>
                <thead><tr><th>Vendor</th><th>Legal name</th><th>Tax id as entered</th><th>Source</th><th>Status</th></tr></thead>
                <tbody>{g.map(v => <tr key={v.vendor_id}><td className="mono">{v.vendor_id}</td><td>{v.legal_name}</td><td className="mono">{v.tax_id}</td><td>{v.source_system}</td><td><Badge value={v.status} /></td></tr>)}</tbody>
              </table>
            </div>
          ))
        )}
      </div>
    </>
  )
}
