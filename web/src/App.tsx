import { useState } from 'react'
import { currentSteward, setSteward } from './api/client'
import VendorsPage from './pages/VendorsPage'
import CostCentersPage from './pages/CostCentersPage'
import ReviewQueuePage from './pages/ReviewQueuePage'
import PublishPage from './pages/PublishPage'

type Page = 'vendors' | 'cost-centers' | 'review' | 'publish'
const PAGES: { id: Page; label: string }[] = [
  { id: 'cost-centers', label: 'Cost centers' },
  { id: 'vendors', label: 'Vendors' },
  { id: 'review', label: 'Review queue' },
  { id: 'publish', label: 'Publish' },
]

export default function App() {
  const [page, setPage] = useState<Page>((location.hash.replace('#', '') as Page) || 'cost-centers')
  const [steward, setStewardState] = useState(currentSteward())
  const go = (p: Page) => { location.hash = p; setPage(p) }
  const env = import.meta.env.VITE_MDM_ENV ?? 'dev'
  return (
    <>
      <header className="topbar">
        <span className="brand">LedgerCore MDM</span>
        <span className="env">{env.toUpperCase()}</span>
        <nav>{PAGES.map(p => <a key={p.id} href={`#${p.id}`} className={page === p.id ? 'active' : ''} onClick={e => { e.preventDefault(); go(p.id) }}>{p.label}</a>)}</nav>
        <span style={{ marginLeft: 'auto', fontSize: 12 }}>
          Steward&nbsp;
          <select value={steward} onChange={e => { setSteward(e.target.value); setStewardState(e.target.value) }} style={{ padding: '2px 4px' }}>
            <option value="steward.a">steward.a (requester)</option>
            <option value="steward.b">steward.b (approver)</option>
          </select>
        </span>
      </header>
      <main>
        {page === 'vendors' && <VendorsPage />}
        {page === 'cost-centers' && <CostCentersPage />}
        {page === 'review' && <ReviewQueuePage />}
        {page === 'publish' && <PublishPage />}
      </main>
    </>
  )
}
