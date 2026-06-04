# DataForge Dashboard — UI Edge States



---

## Purpose

This document defines exactly what the operator sees in three edge states for every dashboard page:

- **Empty** — pipeline has not yet ingested any data (first boot, no events in DB)
- **Loading** — a fetch/poll is in-flight or WebSocket is connecting
- **Error** — backend unreachable, API returned 5xx, or WebSocket dropped

Defining these now prevents ad-hoc UI decisions during M9 implementation under time pressure. Every state described here maps directly to a React component condition.

---

## Global Conventions

These rules apply to all 7 pages unless a page overrides them.

| Convention | Rule |
|---|---|
| **Loading indicator** | Skeleton cards (gray animated pulse) for card-type components; spinner overlay for table-type components |
| **Error banner** | Full-width red banner at top of main content area. Shows: error message + last-known-good timestamp. Never replaces the full page — stale data stays visible beneath the banner |
| **Empty illustration** | Centered icon + heading + subtext. No data tables, no charts. Single CTA if relevant |
| **Skeleton color** | `#E0E0E0` animated pulse, matches DataForge gray palette |
| **Error color** | `#FFEBEE` background · `#C62828` text · border `#EF9A9A` |
| **Empty color** | `#F5F5F5` background · `#9E9E9E` icon · `#555` heading |
| **Last-known-good** | Stored in React state on each successful fetch. Displayed in error banner as "Last successful update: HH:MM:SS" |
| **Retry behavior** | Polling endpoints: auto-retry on next poll interval. WebSocket: exponential backoff 1s→2s→4s→8s then show error |
| **Timeout threshold** | REST: 10s timeout → error state. WebSocket: 30s no message → reconnect attempt |

---

## Page 01 — Home

**API:** `GET /api/v1/summary` (30s) + `GET /api/v1/alerts/recent?limit=5` (5s)

### Empty State
**Trigger:** `/api/v1/summary` returns `active_sensors: 0`, `anomaly_count_1h: 0`, `system_status: "idle"`

**What the user sees:**
- StatusBand: **amber** — "System Idle"
- SummaryCards: all 4 cards show `—` (em dash) instead of values, gray subtext: "No data yet"
- CriticalAlertBanner: **hidden** (not rendered)
- RecentAlertsList: replaced by centered placeholder:
  ```
  📡  Waiting for first events...
  Pipeline is starting up. Data will appear here once
  the Kafka stream begins ingesting events.
  ```
- QuickNav buttons: visible and functional

### Loading State
**Trigger:** fetch in-flight on page mount or poll cycle

**What the user sees:**
- StatusBand: shows last known status (or gray "Loading..." on first load)
- SummaryCards: 4 skeleton cards (gray pulse animation, same dimensions as real cards)
- RecentAlertsList: 3 skeleton rows (gray bars, varying widths)
- LastUpdated timestamp: "Updating..."

### Error State
**Trigger:** `/api/v1/summary` returns 5xx or times out after 10s

**What the user sees:**
- **Red error banner** (full width, below StatusBand):
  ```
  ⚠ Unable to reach backend — Last successful update: 14:32:05
  Retrying in 5s...
  ```
- StatusBand: turns **red** — "Connection Error"
- SummaryCards: stale values remain visible with reduced opacity (0.5)
- RecentAlertsList: stale rows remain visible with reduced opacity (0.5)
- CriticalAlertBanner: hidden during error state

---

## Page 02 — Live Stream

**API:** `WS /api/v1/ws/stream` (persistent) + `GET /api/v1/stream/info` (on load)

### Empty State
**Trigger:** WebSocket connected but zero events received in last 60s

**What the user sees:**
- ConnectionStatus: **green dot** (connected, but quiet)
- ThroughputCounter: `0 evt/s`
- FilterBar: visible and functional
- LiveEventTable: replaced by centered placeholder:
  ```
  📡  Stream connected — waiting for events
  No events have arrived in the last 60 seconds.
  The pipeline may still be warming up.
  ```
- EventCounter: `Total: 0 · Filtered: 0 · Showing: 0`

### Loading State
**Trigger:** WebSocket handshake in progress (page mount, reconnect attempt)

**What the user sees:**
- ConnectionStatus: **amber dot** — "Connecting..."
- ThroughputCounter: `— evt/s`
- LiveEventTable: single skeleton row with pulse animation
- PauseButton: disabled (grayed out)
- Banner: `Establishing WebSocket connection...`

### Error State
**Trigger:** WebSocket closes unexpectedly or fails to connect after 3 attempts (8s total)

**What the user sees:**
- ConnectionStatus: **red dot** — "Disconnected"
- **Red error banner:**
  ```
  ⚠ Stream disconnected — Last event received: 14:32:05
  Reconnecting... (attempt 3/5)
  ```
- LiveEventTable: last 200 buffered events remain visible, grayed out
- PauseButton: replaced by **"Reconnect"** button (manual trigger)
- ThroughputCounter: frozen at last value, gray italic

---

## Page 03 — Fusion Monitor

**API:** `GET /api/v1/fusion/sensors` (10s) + `GET /api/v1/fusion/events` (on demand) + `WS /api/v1/ws/fusion`

### Empty State
**Trigger:** `/api/v1/fusion/sensors` returns empty array or all sensors `status: "offline"`

**What the user sees:**
- All 4 SensorCards: gray, show `—` for all metrics, badge: **"Offline"** (gray)
- ContributionBars: all bars at 0%, labels grayed
- DataLossAlert: hidden
- FusedEventsTable: replaced by:
  ```
  🔀  No fusion data available
  Sensor streams have not connected yet.
  Waiting for Kafka + Spark pipeline to start.
  ```

### Loading State
**Trigger:** 10s poll in-flight

**What the user sees:**
- 4 SensorCards: skeleton (gray pulse for quality badge, metric values, bar)
- ContributionBars: skeleton bars (gray, varying widths)
- FusedEventsTable: 3 skeleton rows

### Error State
**Trigger:** `/api/v1/fusion/sensors` returns 5xx or times out

**What the user sees:**
- **Red error banner:**
  ```
  ⚠ Fusion data unavailable — Last sync: 14:32:05
  Backend returned an error. Retrying in 10s...
  ```
- SensorCards: stale values at 0.5 opacity
- ContributionBars: stale bars at 0.5 opacity
- DataLossAlert: hidden during error state

---

## Page 04 — AI Alerts

**API:** `GET /api/v1/alerts` (5s) + `GET /api/v1/alerts/summary` (5s)

### Empty State
**Trigger:** `/api/v1/alerts` returns empty array AND `/api/v1/alerts/summary` returns all counts = 0

**What the user sees:**
- SummaryCards: `0` for Active, `0` for Critical, `0` for Closed Today (shown in green — good state)
- FilterBar: visible and functional
- AlertTable: replaced by centered placeholder:
  ```
  ✅  No alerts
  The AI model has not flagged any anomalies yet.
  This could mean the pipeline is starting up, or the
  system is operating normally.
  ```
- No pagination

### Loading State
**Trigger:** 5s poll in-flight

**What the user sees:**
- SummaryCards: 3 skeleton cards
- AlertTable: 5 skeleton rows (with skeleton cells for each column)
- FilterBar: visible and functional (not disabled)

### Error State
**Trigger:** `/api/v1/alerts` returns 5xx or times out

**What the user sees:**
- **Red error banner:**
  ```
  ⚠ Alert data unavailable — Last update: 14:32:05
  Could not reach backend. Retrying in 5s...
  ```
- SummaryCards: stale values at 0.5 opacity
- AlertTable: stale rows remain visible at 0.5 opacity
- Action buttons (View XAI, Acknowledge): **disabled** during error state, grayed out with tooltip: "Actions unavailable while offline"

---

## Page 05 — XAI Panel

**API:** `GET /api/v1/alerts/{id}/xai` (on demand — triggered by row click in AI Alerts)

### Empty State
**Trigger:** User navigates directly to `/xai` without an `event_id` query param

**What the user sees:**
- EventSummaryBand: empty, shows placeholder:
  ```
  No event selected
  ```
- PlainLanguageBox: hidden
- SHAPBarChart: hidden
- FeatureDetailTable: hidden
- Full-page centered message:
  ```
  🧠  No event selected
  Click "View XAI" on any alert in the AI Alerts page
  to see the explanation for that event.
  [→ Go to AI Alerts]  (button)
  ```

### Loading State
**Trigger:** XAI fetch in-flight after row click

**What the user sees:**
- EventSummaryBand: real event metadata shown immediately (from the row click payload — event_id, timestamp, sensor, label, risk_score are already known)
- RiskGauge: real value shown immediately
- PlainLanguageBox: skeleton (2 gray lines)
- SHAPBarChart: 4 skeleton bars (gray, varying widths)
- FeatureDetailTable: 4 skeleton rows

### Error State
**Trigger:** `/api/v1/alerts/{id}/xai` returns 404 (no XAI data for this event yet) or 5xx

**404 — XAI not yet generated:**
```
🧠  Explanation not available yet
The AI model has flagged this event but the XAI module
has not processed it yet. Check back in a few seconds.
[↻ Retry]  (button)
```

**5xx — Backend error:**
- **Red error banner:**
  ```
  ⚠ Could not load explanation — event_id: EVT-00482
  Backend error. Please try again.
  [↻ Retry]
  ```
- EventSummaryBand: real values remain visible
- PlainLanguageBox, SHAPBarChart, FeatureDetailTable: hidden

---

## Page 06 — Performance Metrics

**API:** `GET /api/v1/performance` (10s) + `GET /api/v1/performance/thresholds` (on load)

### Empty State
**Trigger:** `/api/v1/performance` returns empty time-series (no data points in selected range)

**What the user sees:**
- KPICards: show `—` for all 4 metrics, badge: **"No data"** (gray)
- LatencyLineChart: empty chart area with message: `No data in selected time range`
- ThroughputBarChart: empty chart area with message: `No data in selected time range`
- SensorPerfTable: replaced by:
  ```
  📊  No performance data
  No events have been processed in the selected time range.
  Try selecting a wider range or wait for the pipeline to start.
  ```
- TimeRangeSelector: visible and functional

### Loading State
**Trigger:** 10s poll in-flight or time range changed

**What the user sees:**
- KPICards: 4 skeleton cards
- LatencyLineChart: gray skeleton rectangle (same dimensions as chart)
- ThroughputBarChart: gray skeleton rectangle
- SensorPerfTable: 4 skeleton rows

### Error State
**Trigger:** `/api/v1/performance` returns 5xx or times out

**What the user sees:**
- **Red error banner:**
  ```
  ⚠ Performance data unavailable — Last update: 14:32:05
  Retrying in 10s...
  ```
- KPICards: stale values at 0.5 opacity, badge changes to **"Stale"** (amber)
- Charts: stale charts at 0.5 opacity with "Stale data" watermark
- SensorPerfTable: stale rows at 0.5 opacity

---

## Page 07 — Reports

**API:** `GET /api/v1/reports` (on demand) + `GET /api/v1/reports/export` (on button click)

### Empty State
**Trigger:** `/api/v1/reports` returns empty results for selected date range

**What the user sees:**
- SummaryCards: all show `0`
- AnomalyTrendChart: empty chart with message: `No anomalies in selected period`
- TopEventsTable: replaced by:
  ```
  📄  No events found
  No anomalies were recorded in the selected date range.
  Try adjusting the filters or selecting a wider date range.
  ```
- SensorPerfTable: all zeros
- Export buttons: **disabled** — tooltip: "No data to export"

### Loading State
**Trigger:** Report fetch in-flight after filter change or page load

**What the user sees:**
- SummaryCards: 4 skeleton cards
- AnomalyTrendChart: gray skeleton rectangle
- TopEventsTable: 5 skeleton rows
- SensorPerfTable: 4 skeleton rows
- Export buttons: **disabled** with spinner icon during fetch

### Error State
**Trigger:** `/api/v1/reports` returns 5xx or times out

**What the user sees:**
- **Red error banner:**
  ```
  ⚠ Report data unavailable
  Could not fetch report for the selected date range.
  Please try again. [↻ Retry]
  ```
- SummaryCards, charts, tables: hidden (no stale data for reports — stale report data is misleading)
- Export buttons: **disabled** — tooltip: "Data unavailable"

**Export-specific error** (triggered when PDF/CSV generation fails):
- Inline error below export buttons:
  ```
  ⚠ Export failed. Please try again.
  ```
- Does not affect the rest of the page

---

## React Implementation Notes

These notes are for Beyza's reference during M9 implementation.

### State Shape (per page)

```javascript
// Suggested React state shape for each polling component
const [dataState, setDataState] = useState({
  status: 'idle',        // 'idle' | 'loading' | 'success' | 'error' | 'empty'
  data: null,            // actual API response
  lastUpdated: null,     // timestamp of last successful fetch (Date object)
  error: null,           // error message string
});
```

### Skeleton Component Pattern

```jsx
// Reusable skeleton for card-type components
const SkeletonCard = () => (
  <div className="skeleton-card" style={{
    background: 'linear-gradient(90deg, #E0E0E0 25%, #F5F5F5 50%, #E0E0E0 75%)',
    backgroundSize: '200% 100%',
    animation: 'shimmer 1.5s infinite',
    borderRadius: '6px',
    height: '80px'
  }} />
);
```

### Error Banner Component Pattern

```jsx
const ErrorBanner = ({ message, lastUpdated, onRetry }) => (
  <div style={{ background: '#FFEBEE', border: '1px solid #EF9A9A',
    color: '#C62828', padding: '8px 16px', fontSize: '12px',
    display: 'flex', alignItems: 'center', gap: '8px' }}>
    <span>⚠</span>
    <span>{message}</span>
    {lastUpdated && (
      <span style={{ color: '#888' }}>
        Last successful update: {lastUpdated.toLocaleTimeString()}
      </span>
    )}
    {onRetry && <button onClick={onRetry}>↻ Retry</button>}
  </div>
);
```

### WebSocket Reconnect Logic (Live Stream)

```javascript
// Exponential backoff: 1s → 2s → 4s → 8s → error state
const BACKOFF = [1000, 2000, 4000, 8000];
let attempt = 0;

function reconnect() {
  if (attempt >= BACKOFF.length) {
    setDataState(s => ({ ...s, status: 'error' }));
    return;
  }
  setTimeout(() => {
    connectWebSocket();
    attempt++;
  }, BACKOFF[attempt]);
}
```

---

## Summary Table

| Page | Empty trigger | Loading trigger | Error trigger |
|---|---|---|---|
| Home | `active_sensors=0` + `anomaly_count=0` | Poll in-flight | `/api/v1/summary` 5xx / timeout |
| Live Stream | 0 events in 60s (WS connected) | WS handshake in progress | WS drops after 3 reconnect attempts |
| Fusion Monitor | All sensors offline | 10s poll in-flight | `/api/v1/fusion/sensors` 5xx / timeout |
| AI Alerts | Empty alert array + all counts=0 | 5s poll in-flight | `/api/v1/alerts` 5xx / timeout |
| XAI Panel | No `event_id` param | XAI fetch in-flight | 404 (not ready) or 5xx |
| Performance | Empty time-series for range | 10s poll in-flight | `/api/v1/performance` 5xx / timeout |
| Reports | Empty results for date range | Report fetch in-flight | `/api/v1/reports` 5xx / timeout |

---

*Draft v1 prepared May 2026 by Beyza Ülkümen.*
*To be committed to `/services/dashboard/specs/ui_states.md` on GitHub (M1W3T15).*
