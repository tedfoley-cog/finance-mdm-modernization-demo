export interface Vendor { vendor_id: string; legal_name: string; tax_id: string | null; tax_id_normalized: string | null; country_code: string; payment_terms: string; default_cost_center_code: string | null; status: string; source_system: string; golden_record_id: string | null; updated_at: string }
export interface CostCenter { entity_code: string; cost_center_code: string; description: string; parent_cost_center_code: string | null; manager_employee_id: string | null; profit_center_code: string | null; valid_from: string; valid_to: string | null; status: string; source_system: string; updated_at: string }
export interface GLAccount { account_number: string; description: string; account_type: string; status: string }
export interface ChangeRequest { id: number; entity_type: string; entity_key: string; action: string; payload: string; requested_by: string; status: string; reviewed_by: string | null; review_note: string | null; created_at: string; reviewed_at: string | null }
export interface PublishRun { id: number; entity_type: string; record_count: number; s3_key: string; checksum: string; bytes_written: number; status: string; created_at: string }
export interface ImpactSummary { pending_change_requests: number; vendors: number; cost_centers: number; gl_accounts: number; last_publish: PublishRun | null }

const BASE = import.meta.env.VITE_API_BASE ?? '/api'

async function http<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, { headers: { 'Content-Type': 'application/json' }, ...init })
  if (!res.ok) {
    const body = await res.json().catch(() => ({}))
    throw new Error(body.detail ? (typeof body.detail === 'string' ? body.detail : JSON.stringify(body.detail)) : res.statusText)
  }
  return res.status === 204 ? (undefined as T) : res.json()
}

export function currentSteward(): string { return localStorage.getItem('steward') ?? 'steward.a' }
export function setSteward(id: string) { localStorage.setItem('steward', id) }

export const api = {
  vendors: (q?: string) => http<Vendor[]>(`/vendors${q ? `?q=${encodeURIComponent(q)}` : ''}`),
  vendorDuplicates: () => http<Vendor[][]>('/vendors/duplicates'),
  createVendor: (v: Partial<Vendor>) => http<ChangeRequest>('/vendors', { method: 'POST', body: JSON.stringify({ ...v, requested_by: currentSteward() }) }),
  updateVendor: (id: string, v: Partial<Vendor>) => http<ChangeRequest>(`/vendors/${id}`, { method: 'PUT', body: JSON.stringify({ ...v, requested_by: currentSteward() }) }),
  costCenters: (entity?: string, q?: string) => http<CostCenter[]>(`/cost-centers?${new URLSearchParams({ ...(entity ? { entity_code: entity } : {}), ...(q ? { q } : {}) })}`),
  costCenterChildren: (entity: string, code: string) => http<CostCenter[]>(`/cost-centers/${entity}/${code}/children`),
  createCostCenter: (cc: Partial<CostCenter>) => http<ChangeRequest>('/cost-centers', { method: 'POST', body: JSON.stringify({ ...cc, requested_by: currentSteward() }) }),
  glAccounts: () => http<GLAccount[]>('/gl-accounts'),
  changeRequests: (status?: string) => http<ChangeRequest[]>(`/change-requests${status ? `?status=${status}` : ''}`),
  review: (id: number, decision: 'APPROVE' | 'REJECT', note: string) => http<ChangeRequest>(`/change-requests/${id}/review`, { method: 'POST', body: JSON.stringify({ reviewer: currentSteward(), decision, note: note || null }) }),
  publish: (entity_type: string) => http<PublishRun>('/publish', { method: 'POST', body: JSON.stringify({ entity_type, requested_by: currentSteward() }) }),
  publishRuns: () => http<PublishRun[]>('/publish/runs'),
  publishSummary: () => http<ImpactSummary>('/publish/summary'),
}
