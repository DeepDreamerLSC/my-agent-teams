// Pure helpers extracted from dashboard.js for testability

const BOARD_COLUMNS = ['pending', 'working', 'ready_for_merge', 'blocked', 'done']

const BOARD_LABELS = {
  pending: '待开始',
  working: '执行中',
  ready_for_merge: '待合入',
  blocked: '阻塞',
  done: '已完成',
}

// Badge labels for current_status (raw task.json status)
const CURRENT_STATUS_LABELS = {
  pending: '待派发',
  pooled: '待认领',
  dispatched: '已派发',
  working: '执行中',
  ready_for_merge: '待合入',
  blocked: '阻塞',
  done: '已完成',
  failed: '失败',
  timeout: '超时',
  cancelled: '已取消',
  merged: '已合入',
  archived: '已归档',
}

// Gantt phases: key matches backend milestones keys, color/label for chart rendering
const GANTT_PHASES = [
  { key: 'created', label: '创建', color: '#bfbfbf' },
  { key: 'dispatched', label: '派发', color: '#69b1ff' },
  { key: 'ack', label: '接单', color: '#1677ff' },
  { key: 'completed', label: '交付', color: '#52c41a' },
  { key: 'review_completed', label: '审查通过', color: '#722ed1' },
  { key: 'verify_completed', label: '验证通过', color: '#fa8c16' },
]

// Map raw current_status to board_status (5 columns)
const STATUS_TO_BOARD = {
  pending: 'pending',
  pooled: 'pending',
  dispatched: 'pending',
  working: 'working',
  ready_for_merge: 'ready_for_merge',
  blocked: 'blocked',
  failed: 'blocked',
  cancelled: 'blocked',
  timeout: 'blocked',
  merged: 'done',
  archived: 'done',
  done: 'done',
}

function mapToBoardStatus(currentStatus) {
  return STATUS_TO_BOARD[currentStatus] || 'blocked'
}

function esc(s) {
  if (!s) return ''
  return s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;')
}

function formatTime(iso) {
  if (!iso) return '-'
  const d = new Date(iso)
  if (isNaN(d.getTime())) return '-'
  return `${d.getMonth() + 1}/${d.getDate()} ${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`
}

function groupByBoardStatus(tasks) {
  const grouped = {}
  BOARD_COLUMNS.forEach(s => { grouped[s] = [] })
  tasks.forEach(t => {
    const boardStatus = t.board_status || mapToBoardStatus(t.current_status || t.status)
    const col = BOARD_COLUMNS.includes(boardStatus) ? boardStatus : 'blocked'
    grouped[col].push({ ...t, board_status: col })
  })
  return grouped
}

function truncateTitle(title, maxLen) {
  if (!title) return ''
  return title.length > maxLen ? title.slice(0, maxLen) + '…' : title
}

// Transform /api/board payload columns into grouped map
function transformBoardPayload(payload) {
  const grouped = {}
  BOARD_COLUMNS.forEach(s => { grouped[s] = [] })
  if (!payload || !payload.columns) return grouped
  payload.columns.forEach(col => {
    if (col.tasks) {
      col.tasks.forEach(t => { grouped[col.key] = grouped[col.key] || []; grouped[col.key].push(t) })
    }
  })
  return grouped
}

// Transform /api/agents payload for chart rendering
function transformAgentPayload(payload) {
  if (!payload || !payload.agents) return []
  return payload.agents.map(a => ({
    agent_id: a.agent_id,
    completed_count: a.completed_task_count || 0,
    active_count: a.current_load_count || 0,
    total_work_seconds: a.total_tracked_work_seconds || 0,
    ready_for_merge_count: a.ready_for_merge_count || 0,
  }))
}

function hoursBetween(startIso, endIso) {
  if (!startIso || !endIso) return null
  const start = new Date(startIso)
  const end = new Date(endIso)
  if (Number.isNaN(start.getTime()) || Number.isNaN(end.getTime())) return null
  return Math.max((end.getTime() - start.getTime()) / 3600000, 0)
}

function formatDurationHours(value) {
  if (value == null || Number.isNaN(value)) return '-'
  if (value < 24) return `${value.toFixed(1)}h`
  const days = value / 24
  return `${days.toFixed(1)}d`
}

function buildFilterOptions(tasks, key) {
  const values = [...new Set((tasks || []).map(task => String(task?.[key] || '').trim()).filter(Boolean))]
  values.sort((a, b) => a.localeCompare(b, 'zh-CN'))
  return values
}

function applyTaskFilters(tasks, filters) {
  return (tasks || []).filter(task => {
    if (filters.project && task.project !== filters.project) return false
    if (filters.domain && task.domain !== filters.domain) return false
    if (filters.assigned_agent && task.assigned_agent !== filters.assigned_agent) return false
    if (filters.owner_pm && task.owner_pm !== filters.owner_pm) return false
    if (filters.review_level && task.review_level !== filters.review_level) return false
    return true
  })
}

// Export for Node.js test environment
if (typeof module !== 'undefined' && module.exports) {
  module.exports = {
    esc, formatTime, groupByBoardStatus, truncateTitle, mapToBoardStatus,
    transformBoardPayload, transformAgentPayload,
    hoursBetween, formatDurationHours, buildFilterOptions, applyTaskFilters,
    BOARD_COLUMNS, BOARD_LABELS, CURRENT_STATUS_LABELS, STATUS_TO_BOARD,
    GANTT_PHASES,
  }
}
