/** Cost center codes are 6 numeric characters (see api/app/validators.py). Pads short legacy inputs. */
export const COST_CENTER_CODE_WIDTH = 6
export const COST_CENTER_CODE_PATTERN = /^[0-9]{6}$/

export function padCostCenterCode(raw: string): string {
  return raw.trim().padStart(COST_CENTER_CODE_WIDTH, '0')
}

/** Mirrors api/app/validators.py:normalize_tax_id for client-side duplicate hints. */
export function normalizeTaxId(raw: string | null | undefined): string | null {
  if (!raw) return null
  const v = raw.replace(/[\s\-.]/g, '').toUpperCase()
  return v || null
}

export function fmtDate(iso: string | null | undefined): string {
  if (!iso) return '—'
  return new Date(iso).toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short' })
}
