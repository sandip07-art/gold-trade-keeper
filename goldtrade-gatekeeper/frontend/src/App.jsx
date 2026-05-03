import { useState, useEffect, useCallback, useRef } from 'react'
import { getDecision, getLogs, ingestSimulate, exportLogsUrl } from './api/client'

// ── Constants ────────────────────────────────────────────────────────────────
const REFRESH_INTERVAL = 15_000
const LABEL_FAVORABLE   = 'CONDITIONS FAVORABLE'
const LABEL_UNFAVORABLE = 'CONDITIONS UNFAVORABLE'

// ── Helpers ──────────────────────────────────────────────────────────────────

function decisionClass(d) {
  if (!d) return 'loading'
  if (d === LABEL_FAVORABLE)   return 'allowed'
  if (d === LABEL_UNFAVORABLE) return 'blocked'
  return 'no-trade'
}

function decisionIcon(d) {
  if (d === LABEL_FAVORABLE)   return '✓'
  if (d === LABEL_UNFAVORABLE) return '✗'
  if (d === 'NO TRADE')        return '–'
  return '…'
}

function fmt(n, dec = 2) {
  if (n == null) return '—'
  return Number(n).toFixed(dec)
}

function fmtTime(iso) {
  if (!iso) return '—'
  return new Date(iso).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })
}

function fmtDateTime(iso) {
  if (!iso) return '—'
  return new Date(iso).toLocaleString([], {
    month: 'short', day: 'numeric',
    hour: '2-digit', minute: '2-digit', second: '2-digit',
  })
}

function biasClass(bias) {
  if (!bias) return 'neutral'
  if (bias.includes('SELL')) return 'sell'
  if (bias.includes('BUY'))  return 'buy'
  return 'neutral'
}

// ── Sub-components ───────────────────────────────────────────────────────────

function StatusBanner({ decision, bias, timestamp, price, dxyprice }) {
  return (
    <div className={`status-banner ${decisionClass(decision)}`}>
      <div className="status-main">
        <span className="status-label">GATE STATUS</span>
        <span className="status-text" style={{ fontSize: decision && decision.length > 16 ? '1.7rem' : '2.6rem' }}>
          {decision || 'LOADING…'}
        </span>
        <span className="status-meta">
          {timestamp ? `Last evaluated ${fmtTime(timestamp)}` : 'Waiting for data…'}
          {price    ? ` · XAUUSD ${fmt(price, 2)}`  : ''}
          {dxyprice ? ` · DXY ${fmt(dxyprice, 3)}`  : ''}
        </span>
      </div>
      <div className={`status-icon ${decision === LABEL_FAVORABLE ? 'pulse' : ''}`}>
        {decisionIcon(decision)}
      </div>
    </div>
  )
}

function AlertBanner({ show }) {
  if (!show) return null
  return (
    <div className="alert-banner">
      <span>🟢</span>
      CONDITIONS FAVORABLE — All gates clear. Entry may be considered.
    </div>
  )
}

function SessionCard({ session }) {
  const ok = session && session !== 'OUTSIDE'
  return (
    <div className="metric-card">
      <div className="metric-label">SESSION</div>
      <div className="metric-value" style={{ color: ok ? 'var(--green)' : 'var(--red)', fontSize: '1.1rem' }}>
        {session || '—'}
      </div>
      <div className="metric-sub">London 07–10 · New York 12–16 UTC</div>
    </div>
  )
}

function VolatilityCard({ atr, atrAvg, volState, atrRatio, volConfirmed, stabilityCandles }) {
  const isExpansion = volState === 'EXPANSION'
  const pct = atrAvg > 0 ? Math.min((atr / (atrAvg * 1.5)) * 100, 140) : 0

  return (
    <div className="metric-card">
      <div className="metric-label">VOLATILITY</div>
      <div className="row mt-4">
        <span className="metric-value" style={{ color: isExpansion ? 'var(--green)' : 'var(--red)', fontSize: '1.05rem' }}>
          {volState || '—'}
        </span>
        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: 3 }}>
          <span className={`chip ${isExpansion ? 'chip-green' : 'chip-red'}`}>
            {isExpansion ? 'ATR EXP' : 'FLAT'}
          </span>
          {isExpansion && (
            <span className={`chip ${volConfirmed ? 'chip-green' : 'chip-gold'}`} style={{ fontSize: '0.55rem' }}>
              {volConfirmed ? `✓ STABLE ×${stabilityCandles}` : `⏳ PENDING`}
            </span>
          )}
        </div>
      </div>
      <div className="atr-bar-track mt-8">
        <div className={`atr-bar-fill ${isExpansion ? 'expansion' : ''}`}
             style={{ width: `${Math.min(pct, 100)}%` }} />
        <div className="atr-bar-threshold" style={{ left: '66.7%' }} title="1.5× threshold" />
      </div>
      <div className="metric-sub mt-4">
        ATR {fmt(atr, 2)} · Avg {fmt(atrAvg, 2)} · Ratio {fmt(atrRatio, 2)}×
      </div>
    </div>
  )
}

function BiasCard({ bias, dxyRaw, dxyConfirmed, dxyPending, dxyMomentum }) {
  const bc = biasClass(bias)
  const barColor = bc === 'sell' ? 'var(--red)' : bc === 'buy' ? 'var(--green)' : 'var(--text-dim)'
  const barWidth  = bc === 'neutral' ? '50%' : '82%'
  const momOk = dxyMomentum?.momentum_ok
  const currRange = dxyMomentum?.curr_range
  const avgRange  = dxyMomentum?.avg_range

  return (
    <div className="metric-card">
      <div className="metric-label">DXY BIAS → GOLD</div>
      <div className="row mt-4" style={{ alignItems: 'flex-start', gap: 6 }}>
        <div className={`bias-text ${bc}`} style={{ flex: 1, fontSize: '0.88rem' }}>
          {bias || '—'}
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: 3 }}>
          {/* Momentum chip */}
          <span className={`chip ${momOk ? 'chip-green' : 'chip-muted'}`} style={{ fontSize: '0.55rem' }}>
            {momOk ? '⚡ MOMENTUM' : '○ NO MOMENTUM'}
          </span>
          {/* Stability chip */}
          {dxyRaw !== 'NEUTRAL' && (
            <span className={`chip ${dxyConfirmed ? 'chip-green' : 'chip-gold'}`} style={{ fontSize: '0.55rem' }}>
              {dxyConfirmed ? '✓ CONFIRMED' : dxyPending ? '⏳ BUILDING' : '○ UNSET'}
            </span>
          )}
        </div>
      </div>
      <div className="bias-bar mt-8">
        <div className="bias-bar-fill" style={{ width: barWidth, background: barColor }} />
      </div>
      <div className="metric-sub mt-4">
        {bc === 'sell'    && 'DXY broke prev high — bearish momentum'}
        {bc === 'buy'     && 'DXY broke prev low — bullish momentum'}
        {bc === 'neutral' && (dxyPending
          ? `Raw: ${dxyRaw} — waiting for candle confirmation`
          : 'DXY range-bound or momentum insufficient')}
        {(currRange != null && avgRange != null) && (
          <span style={{ display: 'block', marginTop: 2 }}>
            Range {fmt(currRange, 4)} vs avg {fmt(avgRange, 4)} {momOk ? '✓' : '✗'}
          </span>
        )}
      </div>
    </div>
  )
}

function RiskCard({ tradesToday, maxTrades, dailyLoss, maxLoss }) {
  const tradesOk = tradesToday < maxTrades
  const lossOk   = dailyLoss   < maxLoss
  const tradesPct = maxTrades ? (tradesToday / maxTrades) * 100 : 0
  const lossPct   = maxLoss   ? (dailyLoss  / maxLoss)   * 100 : 0

  return (
    <div className="metric-card">
      <div className="metric-label">RISK ENFORCER</div>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 10, marginTop: 10 }}>
        <div>
          <div className="row">
            <span style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>Trades today</span>
            <span style={{ color: tradesOk ? 'var(--green)' : 'var(--red)', fontWeight: 700 }}>
              {tradesToday} / {maxTrades}
            </span>
          </div>
          <div className="atr-bar-track mt-4" style={{ height: 4 }}>
            <div className="atr-bar-fill" style={{
              width: `${Math.min(tradesPct, 100)}%`,
              background: tradesOk ? 'var(--green)' : 'var(--red)',
            }} />
          </div>
        </div>
        <div>
          <div className="row">
            <span style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>Daily loss</span>
            <span style={{ color: lossOk ? 'var(--green)' : 'var(--red)', fontWeight: 700 }}>
              {fmt(dailyLoss, 2)}% / {maxLoss}%
            </span>
          </div>
          <div className="atr-bar-track mt-4" style={{ height: 4 }}>
            <div className="atr-bar-fill" style={{
              width: `${Math.min(lossPct, 100)}%`,
              background: lossOk ? 'var(--green)' : 'var(--red)',
            }} />
          </div>
        </div>
      </div>
      <div className="metric-sub mt-8">Risk/trade: 1% · Max daily loss: {maxLoss}%</div>
    </div>
  )
}

function PriceCard({ xauusd, dxy }) {
  return (
    <div className="metric-card">
      <div className="metric-label">MARKET PRICES</div>
      <div className="price-ticker mt-4">
        <span className="price-sym">XAU/USD</span>
        <span className="price-val">{fmt(xauusd, 2)}</span>
      </div>
      <div style={{ marginTop: 8, display: 'flex', alignItems: 'baseline', gap: 6 }}>
        <span className="price-sym">DXY</span>
        <span style={{ fontSize: '1.1rem', fontWeight: 700, color: 'var(--text)' }}>
          {fmt(dxy, 3)}
        </span>
      </div>
    </div>
  )
}

function ReasonsPanel({ reasons, decision }) {
  if (!reasons || reasons.length === 0) return null
  const isFavorable = decision === LABEL_FAVORABLE

  return (
    <div className="card" style={{ marginBottom: 16 }}>
      <div className="card-title">
        {isFavorable ? '✓ ALL GATES PASSED' : '✗ GATE BLOCK DETAILS'}
      </div>
      <ul className="reasons-list">
        {reasons.map((r, i) => (
          <li key={i} className="reason-item">
            <span className={isFavorable ? 'reason-dot-green' : 'reason-dot-red'}>
              {isFavorable ? '✓' : '▸'}
            </span>
            {r}
          </li>
        ))}
      </ul>
    </div>
  )
}

// ── Historical Confidence Badge ──────────────────────────────────────────────

function DataConfidenceBadge({ confidence, note, sampleSize }) {
  const colorMap = { HIGH: 'var(--green)', MEDIUM: 'var(--amber)', LOW: 'var(--text-muted)' }
  const bgMap    = { HIGH: 'rgba(34,197,94,0.10)', MEDIUM: 'rgba(245,158,11,0.10)', LOW: 'rgba(107,122,154,0.08)' }
  const bdMap    = { HIGH: 'rgba(34,197,94,0.25)', MEDIUM: 'rgba(245,158,11,0.25)', LOW: 'var(--border)' }
  const dotMap   = { HIGH: '◆', MEDIUM: '◈', LOW: '◇' }

  return (
    <div style={{
      display: 'inline-flex', alignItems: 'center', gap: 8,
      background: bgMap[confidence], border: `1px solid ${bdMap[confidence]}`,
      borderRadius: 100, padding: '5px 12px',
    }}>
      <span style={{ color: colorMap[confidence], fontSize: '0.7rem', fontWeight: 800 }}>
        {dotMap[confidence]} DATA CONFIDENCE: {confidence}
      </span>
      <span style={{ color: 'var(--text-dim)', fontSize: '0.62rem' }}>
        ({sampleSize} trades)
      </span>
    </div>
  )
}

function SystemView({ advisory, historical }) {
  if (!advisory) return null
  const { summary, confidence, playbook } = advisory

  return (
    <div className="card mt-16">
      <div className="card-title">◈ SYSTEM VIEW — ADVISORY ENGINE</div>
      <div className="advisory-card">
        <div className="row mb-16">
          <span style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>
            Contextual interpretation only. Non-controlling.
          </span>
          <span className={`confidence-badge confidence-${confidence}`}>
            {confidence === 'HIGH' && '◆ '} SIGNAL CONFIDENCE: {confidence}
          </span>
        </div>

        {summary && <div className="advisory-summary">{summary}</div>}

        {playbook?.length > 0 && (
          <>
            <div style={{ fontSize: '0.65rem', color: 'var(--text-muted)', letterSpacing: '0.1em', textTransform: 'uppercase', marginBottom: 8, marginTop: 14 }}>
              PLAYBOOK
            </div>
            <ul className="playbook-list">
              {playbook.map((p, i) => (
                <li key={i} className="playbook-item">
                  <span className="playbook-arrow">›</span>{p}
                </li>
              ))}
            </ul>
          </>
        )}

        {historical ? (
          <>
            <hr className="divider" />
            <div className="row" style={{ marginBottom: 10 }}>
              <div>
                <div style={{ fontSize: '0.65rem', color: 'var(--text-muted)', letterSpacing: '0.1em', textTransform: 'uppercase' }}>
                  HISTORICAL CONTEXT
                </div>
                <div style={{ fontSize: '0.68rem', color: 'var(--text-dim)', marginTop: 2 }}>
                  {historical.context?.session} · {historical.context?.vol_state} · {historical.context?.dxy_state}
                </div>
              </div>
              <DataConfidenceBadge
                confidence={historical.data_confidence}
                note={historical.confidence_note}
                sampleSize={historical.sample_size}
              />
            </div>

            {historical.confidence_note && (
              <div style={{
                fontSize: '0.7rem', color: 'var(--text-dim)', fontStyle: 'italic',
                background: 'rgba(255,255,255,0.02)', borderRadius: 6, padding: '8px 12px',
                marginBottom: 14, borderLeft: `2px solid ${
                  historical.data_confidence === 'HIGH' ? 'var(--green)' :
                  historical.data_confidence === 'MEDIUM' ? 'var(--amber)' : 'var(--text-dim)'
                }`
              }}>
                {historical.confidence_note}
              </div>
            )}

            <div className="hist-grid">
              <div className="hist-stat">
                <div className="hist-stat-value" style={{
                  color: historical.win_rate >= 60 ? 'var(--green)' : historical.win_rate >= 45 ? 'var(--amber)' : 'var(--red)'
                }}>
                  {fmt(historical.win_rate, 1)}%
                </div>
                <div className="hist-stat-label">Win Rate</div>
              </div>
              <div className="hist-stat">
                <div className="hist-stat-value" style={{
                  color: historical.avg_rr >= 2 ? 'var(--green)' : historical.avg_rr >= 1 ? 'var(--amber)' : 'var(--red)'
                }}>
                  {fmt(historical.avg_rr, 2)}
                </div>
                <div className="hist-stat-label">Avg R:R</div>
              </div>
              <div className="hist-stat">
                <div className="hist-stat-value" style={{ color: 'var(--text-muted)' }}>
                  {historical.sample_size}
                </div>
                <div className="hist-stat-label">Samples</div>
              </div>
            </div>
          </>
        ) : (
          <div style={{ fontSize: '0.72rem', color: 'var(--text-dim)', marginTop: 12, fontStyle: 'italic' }}>
            Historical stats unavailable — need ≥20 trades logged with identical context
          </div>
        )}
      </div>
    </div>
  )
}

function DecisionChip({ d }) {
  if (d === LABEL_FAVORABLE)   return <span className="chip chip-green"  style={{ fontSize: '0.58rem' }}>FAVORABLE</span>
  if (d === LABEL_UNFAVORABLE) return <span className="chip chip-red"    style={{ fontSize: '0.58rem' }}>UNFAVORABLE</span>
  return                               <span className="chip chip-muted"  style={{ fontSize: '0.58rem' }}>{d}</span>
}

function LogTable({ logs }) {
  if (!logs || logs.length === 0) {
    return (
      <div style={{ textAlign: 'center', padding: '32px', color: 'var(--text-dim)', fontSize: '0.8rem' }}>
        No decisions logged yet. Click "Refresh Gate" to evaluate.
      </div>
    )
  }
  return (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>
            <th>#</th>
            <th>TIME</th>
            <th>GATE</th>
            <th>BIAS</th>
            <th>MOM</th>
            <th>STABLE</th>
            <th>SESSION</th>
            <th>VOL</th>
            <th>ATR</th>
            <th>TRADES</th>
            <th>REASONS</th>
          </tr>
        </thead>
        <tbody>
          {logs.map(l => {
            const m = l.metrics || {}
            const momOk = m.dxy_momentum?.momentum_ok
            return (
              <tr key={l.id}>
                <td style={{ color: 'var(--text-dim)' }}>{l.id}</td>
                <td style={{ color: 'var(--text-muted)', whiteSpace: 'nowrap' }}>{fmtDateTime(l.timestamp)}</td>
                <td><DecisionChip d={l.decision} /></td>
                <td style={{ fontSize: '0.68rem', color: biasClass(l.bias) === 'sell' ? 'var(--red)' : biasClass(l.bias) === 'buy' ? 'var(--green)' : 'var(--text-muted)' }}>
                  {(l.bias || '—').replace(' → GOLD SELL','').replace(' → GOLD BUY','')}
                </td>
                <td>
                  <span style={{ fontSize: '0.7rem' }}>
                    {momOk === true ? <span style={{ color: 'var(--green)' }}>⚡</span>
                     : momOk === false ? <span style={{ color: 'var(--text-dim)' }}>○</span>
                     : '—'}
                  </span>
                </td>
                <td>
                  <span style={{ fontSize: '0.7rem' }}>
                    {m.vol_confirmed === true
                      ? <span style={{ color: 'var(--green)' }}>✓</span>
                      : <span style={{ color: 'var(--amber)' }}>⏳</span>}
                  </span>
                </td>
                <td>
                  <span className={`chip ${m.session !== 'OUTSIDE' ? 'chip-blue' : 'chip-muted'}`}>
                    {m.session || '—'}
                  </span>
                </td>
                <td>
                  <span className={`chip ${m.vol_state === 'EXPANSION' ? 'chip-green' : 'chip-red'}`}>
                    {m.vol_state || '—'}
                  </span>
                </td>
                <td style={{ color: 'var(--text-muted)' }}>
                  {fmt(m.atr, 2)} / {fmt(m.atr_avg, 2)}
                </td>
                <td style={{ color: 'var(--text-muted)' }}>
                  {m.trades_today ?? '—'} / 3
                </td>
                <td style={{ fontSize: '0.67rem', color: 'var(--text-muted)', maxWidth: 200 }}>
                  {(l.reasons || []).join(' · ')}
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}

// ── Main App ─────────────────────────────────────────────────────────────────

export default function App() {
  const [decision, setDecision] = useState(null)
  const [logs, setLogs]         = useState([])
  const [loading, setLoading]   = useState(false)
  const [simulating, setSimulating] = useState(false)
  const [strictMode, setStrictMode] = useState(false)
  const [error, setError]       = useState(null)
  const [lastUpdate, setLastUpdate] = useState(null)
  const [showAlert, setShowAlert]   = useState(false)
  const prevDecisionRef = useRef(null)
  const timerRef = useRef(null)

  const fetchDecision = useCallback(async (showLoad = false) => {
    if (showLoad) setLoading(true)
    setError(null)
    try {
      const data = await getDecision(strictMode)
      if (data.error) {
        setError(data.error)
        setDecision(null)
      } else {
        if (prevDecisionRef.current !== LABEL_FAVORABLE && data.decision === LABEL_FAVORABLE) {
          setShowAlert(true)
          setTimeout(() => setShowAlert(false), 8000)
        }
        prevDecisionRef.current = data.decision
        setDecision(data)
      }
      setLastUpdate(new Date())
    } catch (e) {
      setError(`Cannot connect to backend: ${e.message}. Is the API running on :8000?`)
    } finally {
      if (showLoad) setLoading(false)
    }
  }, [strictMode])

  const fetchLogs = useCallback(async () => {
    try { setLogs(await getLogs(50)) } catch { /* silent */ }
  }, [])

  const handleSimulate = async () => {
    setSimulating(true)
    try {
      await ingestSimulate()
      await fetchDecision(true)
      await fetchLogs()
    } catch (e) {
      setError(`Simulate failed: ${e.message}`)
    } finally {
      setSimulating(false)
    }
  }

  useEffect(() => {
    fetchDecision(true)
    fetchLogs()
    timerRef.current = setInterval(() => { fetchDecision(); fetchLogs() }, REFRESH_INTERVAL)
    return () => clearInterval(timerRef.current)
  }, [fetchDecision, fetchLogs])

  const metrics  = decision?.metrics  || {}
  const advisory = decision?.advisory
  const historical = decision?.historical

  return (
    <div className="app">
      {/* Topbar */}
      <header className="topbar">
        <div className="topbar-brand">
          <span style={{ fontSize: '1.1rem' }}>⚡</span>
          GOLDTRADE GATEKEEPER
          <span>/ XAUUSD</span>
        </div>
        <div className="topbar-right">
          <div className="toggle-wrap">
            <label className="toggle">
              <input type="checkbox" checked={strictMode}
                onChange={e => { setStrictMode(e.target.checked); setTimeout(() => fetchDecision(true), 50) }} />
              <span className="toggle-slider" />
            </label>
            STRICT MODE
          </div>
          <button className="btn-ghost btn-sm" onClick={() => { fetchDecision(true); fetchLogs() }} disabled={loading}>
            {loading ? <><span className="spin" /> Evaluating…</> : '↻ Refresh Gate'}
          </button>
          <button className="btn-ghost btn-sm" onClick={handleSimulate} disabled={simulating}>
            {simulating ? <><span className="spin" /> Simulating…</> : '⚙ Inject Sim Data'}
          </button>
          <a href={exportLogsUrl()} download>
            <button className="btn-ghost btn-sm">↓ Export CSV</button>
          </a>
        </div>
      </header>

      <main className="main">
        <AlertBanner show={showAlert} />

        {error && (
          <div className="card mb-20" style={{ borderColor: 'rgba(239,68,68,0.3)', background: 'rgba(239,68,68,0.05)' }}>
            <div style={{ color: 'var(--red)', fontWeight: 700, marginBottom: 4 }}>⚠ Backend Error</div>
            <div style={{ fontSize: '0.78rem', color: 'var(--text-muted)' }}>{error}</div>
            <div style={{ fontSize: '0.72rem', color: 'var(--text-dim)', marginTop: 8 }}>
              Run: <code style={{ background: 'var(--surface2)', padding: '2px 6px', borderRadius: 4 }}>
                cd backend && python seed.py
              </code> then start the API.
            </div>
          </div>
        )}

        <StatusBanner
          decision={decision?.decision}
          bias={decision?.bias}
          timestamp={decision?.timestamp}
          price={metrics.xauusd_price}
          dxyprice={metrics.dxy_price}
        />

        <div className="section-title">MARKET CONDITIONS</div>
        <div className="grid-4 mb-20">
          <SessionCard session={metrics.session} />
          <VolatilityCard
            atr={metrics.atr}
            atrAvg={metrics.atr_avg}
            volState={metrics.vol_state}
            atrRatio={metrics.atr_ratio}
            volConfirmed={metrics.vol_confirmed}
            stabilityCandles={metrics.stability_candles}
          />
          <BiasCard
            bias={metrics.dxy_state}
            dxyRaw={metrics.dxy_raw}
            dxyConfirmed={metrics.dxy_confirmed}
            dxyPending={metrics.dxy_pending}
            dxyMomentum={metrics.dxy_momentum}
          />
          <RiskCard
            tradesToday={metrics.trades_today ?? 0}
            maxTrades={3}
            dailyLoss={metrics.daily_loss_pct ?? 0}
            maxLoss={2}
          />
        </div>

        <div className="grid-2">
          <ReasonsPanel reasons={decision?.reasons} decision={decision?.decision} />
          <PriceCard xauusd={metrics.xauusd_price} dxy={metrics.dxy_price} />
        </div>

        <SystemView advisory={advisory} historical={historical} />

        <div className="section-title mt-20">DECISION LOG — LAST 50</div>
        <div className="card">
          <LogTable logs={logs} />
        </div>

        <div style={{ textAlign: 'center', padding: '24px 0 12px', color: 'var(--text-dim)', fontSize: '0.65rem', letterSpacing: '0.08em' }}>
          GOLDTRADE GATEKEEPER v1.1 · Rule-based discipline enforcer · No AI prediction
          {lastUpdate && ` · Updated ${lastUpdate.toLocaleTimeString()}`}
        </div>
      </main>
    </div>
  )
}

function decisionIcon(d) {
  if (d === 'TRADE ALLOWED') return '✓'
  if (d === 'BLOCKED')       return '✗'
  if (d === 'NO TRADE')      return '–'
  return '…'
}

function fmt(n, dec = 2) {
  if (n == null) return '—'
  return Number(n).toFixed(dec)
}

function fmtTime(iso) {
  if (!iso) return '—'
  const d = new Date(iso)
  return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })
}

function fmtDateTime(iso) {
  if (!iso) return '—'
  const d = new Date(iso)
  return d.toLocaleString([], {
    month: 'short', day: 'numeric',
    hour: '2-digit', minute: '2-digit', second: '2-digit',
  })
}

function biasClass(bias) {
  if (!bias) return 'neutral'
  if (bias.includes('SELL')) return 'sell'
  if (bias.includes('BUY'))  return 'buy'
  return 'neutral'
}

// ── Sub-components ───────────────────────────────────────────────────────────

function StatusBanner({ decision, bias, timestamp, price, dxyprice }) {
  return (
    <div className={`status-banner ${decisionClass(decision)}`}>
      <div className="status-main">
        <span className="status-label">GATE STATUS</span>
        <span className="status-text">{decision || 'LOADING…'}</span>
        <span className="status-meta">
          {timestamp ? `Last evaluated ${fmtTime(timestamp)}` : 'Waiting for data…'}
          {price ? ` · XAUUSD ${fmt(price, 2)}` : ''}
          {dxyprice ? ` · DXY ${fmt(dxyprice, 3)}` : ''}
        </span>
      </div>
      <div className={`status-icon ${decision === 'TRADE ALLOWED' ? 'pulse' : ''}`}>
        {decisionIcon(decision)}
      </div>
    </div>
  )
}

function AlertBanner({ show }) {
  if (!show) return null
  return (
    <div className="alert-banner">
      <span>🟢</span>
      GATE OPEN — All conditions satisfied. Entry may be considered.
    </div>
  )
}

function MetricCard({ label, value, sub, colorClass }) {
  return (
    <div className="metric-card">
      <div className="metric-label">{label}</div>
      <div className={`metric-value ${colorClass || ''}`}>{value}</div>
      {sub && <div className="metric-sub">{sub}</div>}
    </div>
  )
}

function SessionCard({ session }) {
  const ok = session && session !== 'OUTSIDE'
  return (
    <div className="metric-card">
      <div className="metric-label">SESSION</div>
      <div className={`metric-value ${ok ? 'text-green' : ''}`}
           style={{ color: ok ? 'var(--green)' : 'var(--red)', fontSize: '1.1rem' }}>
        {session || '—'}
      </div>
      <div className="metric-sub">
        London 07–10 · New York 12–16 UTC
      </div>
    </div>
  )
}

function VolatilityCard({ atr, atrAvg, volState, atrRatio }) {
  const isExpansion = volState === 'EXPANSION'
  const pct = atrAvg > 0 ? Math.min((atr / (atrAvg * 1.5)) * 100, 140) : 0
  const thresholdPct = Math.min(100, 100)

  return (
    <div className="metric-card">
      <div className="metric-label">VOLATILITY</div>
      <div className="row mt-4">
        <span className={`metric-value`} style={{ color: isExpansion ? 'var(--green)' : 'var(--red)', fontSize: '1.1rem' }}>
          {volState || '—'}
        </span>
        <span className={`chip ${isExpansion ? 'chip-green' : 'chip-red'}`}>
          {isExpansion ? 'ATR EXP' : 'FLAT'}
        </span>
      </div>
      <div className="atr-bar-wrap mt-8">
        <div className="atr-bar-track">
          <div
            className={`atr-bar-fill ${isExpansion ? 'expansion' : ''}`}
            style={{ width: `${Math.min(pct, 100)}%` }}
          />
          <div className="atr-bar-threshold" style={{ left: '66.7%' }} title="1.5× threshold" />
        </div>
      </div>
      <div className="metric-sub mt-4">
        ATR {fmt(atr, 2)} · Avg {fmt(atrAvg, 2)} · Ratio {fmt(atrRatio, 2)}×
      </div>
    </div>
  )
}

function BiasCard({ bias }) {
  const bc = biasClass(bias)
  const barColor = bc === 'sell' ? 'var(--red)' : bc === 'buy' ? 'var(--green)' : 'var(--text-dim)'
  const barWidth = bc === 'neutral' ? '50%' : '82%'

  return (
    <div className="metric-card">
      <div className="metric-label">DXY BIAS → GOLD</div>
      <div className={`bias-text ${bc} mt-4`}>{bias || '—'}</div>
      <div className="bias-bar mt-8">
        <div className="bias-bar-fill" style={{ width: barWidth, background: barColor }} />
      </div>
      <div className="metric-sub mt-4">
        {bc === 'sell'    && 'DXY broke prev high with bullish body'}
        {bc === 'buy'     && 'DXY broke prev low with bearish body'}
        {bc === 'neutral' && 'DXY within previous candle range'}
      </div>
    </div>
  )
}

function RiskCard({ tradesToday, maxTrades, dailyLoss, maxLoss }) {
  const tradesOk = tradesToday < maxTrades
  const lossOk   = dailyLoss   < maxLoss
  const tradesPct = maxTrades ? (tradesToday / maxTrades) * 100 : 0
  const lossPct   = maxLoss   ? (dailyLoss  / maxLoss)   * 100 : 0

  return (
    <div className="metric-card">
      <div className="metric-label">RISK ENFORCER</div>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 10, marginTop: 10 }}>
        <div>
          <div className="row">
            <span style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>Trades today</span>
            <span style={{ color: tradesOk ? 'var(--green)' : 'var(--red)', fontWeight: 700 }}>
              {tradesToday} / {maxTrades}
            </span>
          </div>
          <div className="atr-bar-track mt-4" style={{ height: 4 }}>
            <div className="atr-bar-fill" style={{
              width: `${Math.min(tradesPct, 100)}%`,
              background: tradesOk ? 'var(--green)' : 'var(--red)',
            }} />
          </div>
        </div>
        <div>
          <div className="row">
            <span style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>Daily loss</span>
            <span style={{ color: lossOk ? 'var(--green)' : 'var(--red)', fontWeight: 700 }}>
              {fmt(dailyLoss, 2)}% / {maxLoss}%
            </span>
          </div>
          <div className="atr-bar-track mt-4" style={{ height: 4 }}>
            <div className="atr-bar-fill" style={{
              width: `${Math.min(lossPct, 100)}%`,
              background: lossOk ? 'var(--green)' : 'var(--red)',
            }} />
          </div>
        </div>
      </div>
      <div className="metric-sub mt-8">Risk/trade: 1% · Max daily loss: {maxLoss}%</div>
    </div>
  )
}

function PriceCard({ xauusd, dxy }) {
  return (
    <div className="metric-card">
      <div className="metric-label">MARKET PRICES</div>
      <div className="price-ticker mt-4">
        <span className="price-sym">XAU/USD</span>
        <span className="price-val">{fmt(xauusd, 2)}</span>
      </div>
      <div style={{ marginTop: 8, display: 'flex', alignItems: 'baseline', gap: 6 }}>
        <span className="price-sym">DXY</span>
        <span style={{ fontSize: '1.1rem', fontWeight: 700, color: 'var(--text)' }}>
          {fmt(dxy, 3)}
        </span>
      </div>
    </div>
  )
}

function ReasonsPanel({ reasons, decision }) {
  if (!reasons || reasons.length === 0) return null
  const isBlocked = decision === 'BLOCKED'

  return (
    <div className="card" style={{ marginBottom: 16 }}>
      <div className="card-title">
        {isBlocked ? '🚫 BLOCK REASONS' : '✓ GATE PASS REASONS'}
      </div>
      <ul className="reasons-list">
        {reasons.map((r, i) => (
          <li key={i} className="reason-item">
            <span className={isBlocked ? 'reason-dot-red' : 'reason-dot-green'}>
              {isBlocked ? '▸' : '✓'}
            </span>
            {r}
          </li>
        ))}
      </ul>
    </div>
  )
}

function SystemView({ advisory, historical }) {
  if (!advisory) return null

  const { summary, confidence, playbook } = advisory

  return (
    <div className="card mt-16">
      <div className="card-title">
        ◈ SYSTEM VIEW — ADVISORY ENGINE
      </div>
      <div className="advisory-card">
        <div className="row mb-16">
          <span style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>Contextual interpretation only. Non-controlling.</span>
          <span className={`confidence-badge confidence-${confidence}`}>
            {confidence === 'HIGH' && '◆'} CONFIDENCE: {confidence}
          </span>
        </div>

        {summary && (
          <div className="advisory-summary">{summary}</div>
        )}

        {playbook && playbook.length > 0 && (
          <>
            <div style={{ fontSize: '0.65rem', color: 'var(--text-muted)', letterSpacing: '0.1em', textTransform: 'uppercase', marginBottom: 8 }}>
              PLAYBOOK
            </div>
            <ul className="playbook-list">
              {playbook.map((p, i) => (
                <li key={i} className="playbook-item">
                  <span className="playbook-arrow">›</span>
                  {p}
                </li>
              ))}
            </ul>
          </>
        )}

        {historical && (
          <>
            <hr className="divider" />
            <div style={{ fontSize: '0.65rem', color: 'var(--text-muted)', letterSpacing: '0.1em', textTransform: 'uppercase', marginBottom: 4 }}>
              HISTORICAL CONTEXT — {historical.context?.session} · {historical.context?.vol_state}
            </div>
            <div style={{ fontSize: '0.68rem', color: 'var(--text-dim)', marginBottom: 12 }}>
              Based on {historical.sample_size} trades with this exact context
            </div>
            <div className="hist-grid">
              <div className="hist-stat">
                <div className="hist-stat-value" style={{
                  color: historical.win_rate >= 60 ? 'var(--green)' : historical.win_rate >= 45 ? 'var(--amber)' : 'var(--red)'
                }}>
                  {fmt(historical.win_rate, 1)}%
                </div>
                <div className="hist-stat-label">Win Rate</div>
              </div>
              <div className="hist-stat">
                <div className="hist-stat-value" style={{
                  color: historical.avg_rr >= 2 ? 'var(--green)' : historical.avg_rr >= 1 ? 'var(--amber)' : 'var(--red)'
                }}>
                  {fmt(historical.avg_rr, 2)}
                </div>
                <div className="hist-stat-label">Avg R:R</div>
              </div>
              <div className="hist-stat">
                <div className="hist-stat-value" style={{ color: 'var(--text-muted)' }}>
                  {historical.sample_size}
                </div>
                <div className="hist-stat-label">Samples</div>
              </div>
            </div>
          </>
        )}

        {!historical && (
          <div style={{ fontSize: '0.72rem', color: 'var(--text-dim)', marginTop: 12, fontStyle: 'italic' }}>
            Historical stats unavailable — need ≥20 trades with identical context (session + volatility + DXY state)
          </div>
        )}
      </div>
    </div>
  )
}

function DecisionChip({ d }) {
  if (d === 'TRADE ALLOWED') return <span className="chip chip-green">{d}</span>
  if (d === 'BLOCKED')       return <span className="chip chip-red">{d}</span>
  return <span className="chip chip-muted">{d}</span>
}

function LogTable({ logs }) {
  if (!logs || logs.length === 0) {
    return (
      <div style={{ textAlign: 'center', padding: '32px', color: 'var(--text-dim)', fontSize: '0.8rem' }}>
        No decisions logged yet. Click "Refresh Gate" to evaluate.
      </div>
    )
  }

  return (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>
            <th>#</th>
            <th>TIME</th>
            <th>DECISION</th>
            <th>BIAS</th>
            <th>SESSION</th>
            <th>VOL</th>
            <th>ATR</th>
            <th>TRADES</th>
            <th>STRICT</th>
            <th>REASONS</th>
          </tr>
        </thead>
        <tbody>
          {logs.map(l => {
            const m = l.metrics || {}
            return (
              <tr key={l.id}>
                <td style={{ color: 'var(--text-dim)' }}>{l.id}</td>
                <td style={{ color: 'var(--text-muted)', whiteSpace: 'nowrap' }}>{fmtDateTime(l.timestamp)}</td>
                <td><DecisionChip d={l.decision} /></td>
                <td style={{ fontSize: '0.68rem', color: biasClass(l.bias) === 'sell' ? 'var(--red)' : biasClass(l.bias) === 'buy' ? 'var(--green)' : 'var(--text-muted)' }}>
                  {l.bias || '—'}
                </td>
                <td>
                  <span className={`chip ${m.session !== 'OUTSIDE' ? 'chip-blue' : 'chip-muted'}`}>
                    {m.session || '—'}
                  </span>
                </td>
                <td>
                  <span className={`chip ${m.vol_state === 'EXPANSION' ? 'chip-green' : 'chip-red'}`}>
                    {m.vol_state || '—'}
                  </span>
                </td>
                <td style={{ color: 'var(--text-muted)' }}>
                  {fmt(m.atr, 2)} / {fmt(m.atr_avg, 2)}
                </td>
                <td style={{ color: 'var(--text-muted)' }}>
                  {m.trades_today ?? '—'} / 3
                </td>
                <td>
                  {l.strict_mode
                    ? <span className="chip chip-gold">ON</span>
                    : <span style={{ color: 'var(--text-dim)', fontSize: '0.65rem' }}>off</span>
                  }
                </td>
                <td style={{ fontSize: '0.68rem', color: 'var(--text-muted)', maxWidth: 200 }}>
                  {(l.reasons || []).join(' · ')}
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}

// ── Main App ─────────────────────────────────────────────────────────────────

export default function App() {
  const [decision, setDecision] = useState(null)
  const [logs, setLogs]         = useState([])
  const [loading, setLoading]   = useState(false)
  const [simulating, setSimulating] = useState(false)
  const [strictMode, setStrictMode] = useState(false)
  const [error, setError]       = useState(null)
  const [lastUpdate, setLastUpdate] = useState(null)
  const [prevDecision, setPrevDecision] = useState(null)
  const [showAlert, setShowAlert] = useState(false)
  const timerRef = useRef(null)

  const fetchDecision = useCallback(async (showLoad = false) => {
    if (showLoad) setLoading(true)
    setError(null)
    try {
      const data = await getDecision(strictMode)
      if (data.error) {
        setError(data.error)
        setDecision(null)
      } else {
        setPrevDecision(prev => {
          if (prev !== 'TRADE ALLOWED' && data.decision === 'TRADE ALLOWED') {
            setShowAlert(true)
            setTimeout(() => setShowAlert(false), 8000)
          }
          return data.decision
        })
        setDecision(data)
      }
      setLastUpdate(new Date())
    } catch (e) {
      setError(`Cannot connect to backend: ${e.message}. Is the API running on :8000?`)
    } finally {
      if (showLoad) setLoading(false)
    }
  }, [strictMode])

  const fetchLogs = useCallback(async () => {
    try {
      const data = await getLogs(50)
      setLogs(data)
    } catch { /* silent */ }
  }, [])

  const handleSimulate = async () => {
    setSimulating(true)
    try {
      await ingestSimulate()
      await fetchDecision(true)
      await fetchLogs()
    } catch (e) {
      setError(`Simulate failed: ${e.message}`)
    } finally {
      setSimulating(false)
    }
  }

  // Initial + interval refresh
  useEffect(() => {
    fetchDecision(true)
    fetchLogs()
    timerRef.current = setInterval(() => {
      fetchDecision()
      fetchLogs()
    }, REFRESH_INTERVAL)
    return () => clearInterval(timerRef.current)
  }, [fetchDecision, fetchLogs])

  const metrics = decision?.metrics || {}
  const advisory = decision?.advisory
  const historical = decision?.historical

  return (
    <div className="app">
      {/* Topbar */}
      <header className="topbar">
        <div className="topbar-brand">
          <span style={{ fontSize: '1.1rem' }}>⚡</span>
          GOLDTRADE GATEKEEPER
          <span>/ XAUUSD</span>
        </div>
        <div className="topbar-right">
          <div className="toggle-wrap">
            <label className="toggle">
              <input
                type="checkbox"
                checked={strictMode}
                onChange={e => {
                  setStrictMode(e.target.checked)
                  setTimeout(() => fetchDecision(true), 50)
                }}
              />
              <span className="toggle-slider" />
            </label>
            STRICT MODE
          </div>

          <button
            className="btn-ghost btn-sm"
            onClick={() => { fetchDecision(true); fetchLogs() }}
            disabled={loading}
          >
            {loading ? <><span className="spin" /> Evaluating…</> : '↻ Refresh Gate'}
          </button>

          <button
            className="btn-ghost btn-sm"
            onClick={handleSimulate}
            disabled={simulating}
          >
            {simulating ? <><span className="spin" /> Simulating…</> : '⚙ Inject Sim Data'}
          </button>

          <a href={exportLogsUrl()} download>
            <button className="btn-ghost btn-sm">↓ Export CSV</button>
          </a>
        </div>
      </header>

      <main className="main">
        {/* Alert banner */}
        <AlertBanner show={showAlert} />

        {/* Error state */}
        {error && (
          <div className="card mb-20" style={{ borderColor: 'rgba(239,68,68,0.3)', background: 'rgba(239,68,68,0.05)' }}>
            <div style={{ color: 'var(--red)', fontWeight: 700, marginBottom: 4 }}>⚠ Backend Error</div>
            <div style={{ fontSize: '0.78rem', color: 'var(--text-muted)' }}>{error}</div>
            <div style={{ fontSize: '0.72rem', color: 'var(--text-dim)', marginTop: 8 }}>
              Run: <code style={{ background: 'var(--surface2)', padding: '2px 6px', borderRadius: 4 }}>cd backend && python seed.py</code>, then restart the API.
            </div>
          </div>
        )}

        {/* Status Banner */}
        <StatusBanner
          decision={decision?.decision}
          bias={decision?.bias}
          timestamp={decision?.timestamp}
          price={metrics.xauusd_price}
          dxyprice={metrics.dxy_price}
        />

        {/* Metrics Grid */}
        <div className="section-title">MARKET CONDITIONS</div>
        <div className="grid-4 mb-20">
          <SessionCard session={metrics.session} />
          <VolatilityCard
            atr={metrics.atr}
            atrAvg={metrics.atr_avg}
            volState={metrics.vol_state}
            atrRatio={metrics.atr_ratio}
          />
          <BiasCard bias={metrics.dxy_state} />
          <RiskCard
            tradesToday={metrics.trades_today ?? 0}
            maxTrades={3}
            dailyLoss={metrics.daily_loss_pct ?? 0}
            maxLoss={2}
          />
        </div>

        {/* Reasons + Prices */}
        <div className="grid-2">
          <div>
            <ReasonsPanel reasons={decision?.reasons} decision={decision?.decision} />
          </div>
          <div>
            <PriceCard xauusd={metrics.xauusd_price} dxy={metrics.dxy_price} />
          </div>
        </div>

        {/* System View — Advisory + Historical */}
        <SystemView advisory={advisory} historical={historical} />

        {/* Decision Log */}
        <div className="section-title mt-20">DECISION LOG — LAST 50</div>
        <div className="card">
          <LogTable logs={logs} />
        </div>

        {/* Footer */}
        <div style={{ textAlign: 'center', padding: '24px 0 12px', color: 'var(--text-dim)', fontSize: '0.65rem', letterSpacing: '0.08em' }}>
          GOLDTRADE GATEKEEPER v1.0 · Rule-based discipline enforcer · No AI prediction
          {lastUpdate && ` · Updated ${lastUpdate.toLocaleTimeString()}`}
        </div>
      </main>
    </div>
  )
}
