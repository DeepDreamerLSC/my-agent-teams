// --- Config ---
const API_BASE = '/api'
const BOARD_COLUMNS = ['pending', 'working', 'ready_for_merge', 'blocked', 'done']
const BOARD_LABELS = {
  pending: '待开始', working: '执行中', ready_for_merge: '待合入', blocked: '阻塞', done: '已完成',
}
const CURRENT_STATUS_LABELS = {
  pending: '待派发', dispatched: '已派发', working: '执行中', ready_for_merge: '待合入',
  blocked: '阻塞', done: '已完成', failed: '失败', timeout: '超时', cancelled: '已取消',
  merged: '已合入', archived: '已归档',
}

// --- Tab switching ---
document.querySelectorAll('.tab').forEach(btn => {
  btn.addEventListener('click', () => {
    document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'))
    document.querySelectorAll('.view').forEach(v => v.classList.remove('active'))
    btn.classList.add('active')
    document.getElementById(btn.dataset.tab).classList.add('active')
    window.dispatchEvent(new Event('resize'))
  })
})

// --- Data layer (aligned to backend: /api/board, /api/gantt, /api/agents) ---
async function fetchBoard() {
  try {
    const res = await fetch(`${API_BASE}/board`)
    if (!res.ok) throw new Error(`HTTP ${res.status}`)
    return await res.json()
  } catch { return null }
}

async function fetchGantt() {
  try {
    const res = await fetch(`${API_BASE}/gantt`)
    if (!res.ok) throw new Error(`HTTP ${res.status}`)
    return await res.json()
  } catch { return null }
}

async function fetchAgents() {
  try {
    const res = await fetch(`${API_BASE}/agents`)
    if (!res.ok) throw new Error(`HTTP ${res.status}`)
    return await res.json()
  } catch { return null }
}

// --- Kanban View ---
function renderKanban(boardPayload) {
  const board = document.getElementById('kanban-board')
  board.innerHTML = ''

  // Group tasks from payload.columns by board_status
  const grouped = {}
  BOARD_COLUMNS.forEach(s => { grouped[s] = [] })

  if (boardPayload && boardPayload.columns) {
    boardPayload.columns.forEach(col => {
      if (col.tasks && BOARD_COLUMNS.includes(col.key)) {
        grouped[col.key] = col.tasks
      }
    })
  }

  const totalTasks = BOARD_COLUMNS.reduce((sum, s) => sum + grouped[s].length, 0)

  BOARD_COLUMNS.forEach(status => {
    const col = document.createElement('div')
    col.className = `kanban-col col-${status}`

    const items = grouped[status]
    col.innerHTML = `
      <div class="kanban-col-header">
        <span>${BOARD_LABELS[status]}</span>
        <span class="count">${items.length}</span>
      </div>
    `

    items.forEach(task => {
      const currentStatus = task.current_status || status
      const showBadge = currentStatus !== status
      const badge = showBadge ? `<span class="card-badge badge-${currentStatus}">${CURRENT_STATUS_LABELS[currentStatus] || currentStatus}</span>` : ''

      const card = document.createElement('div')
      card.className = 'kanban-card'
      card.innerHTML = `
        <div class="card-title">${esc(task.title)}</div>
        ${badge}
        <div class="card-meta">
          ${task.project || ''} · ${formatTime(task.created_at)}
        </div>
        <span class="card-agent">${esc(task.assigned_agent)}</span>
        <span class="card-domain">${esc(task.domain)}</span>
      `
      col.appendChild(card)
    })

    board.appendChild(col)
  })

  document.getElementById('task-count').textContent = `共 ${totalTasks} 个任务`
}

// --- Gantt View ---
function renderGantt(ganttPayload) {
  const el = document.getElementById('gantt-chart')
  const items = (ganttPayload && ganttPayload.items) || []

  if (!items.length) {
    el.innerHTML = '<div class="empty-state">暂无甘特图数据</div>'
    return
  }

  const chart = echarts.init(el)
  const sorted = [...items].sort((a, b) => new Date(a.display_start_at || a.milestones.created) - new Date(b.display_start_at || b.milestones.created))

  const categories = sorted.map(t => t.title.length > 16 ? t.title.slice(0, 16) + '…' : t.title)
  const baseTime = Math.min(...sorted.map(t => new Date(t.milestones.created).getTime()))

  const phases = [
    { key: 'created', label: '创建', color: '#bfbfbf' },
    { key: 'dispatched', label: '派发', color: '#69b1ff' },
    { key: 'ack', label: '接单', color: '#1677ff' },
    { key: 'completed', label: '交付', color: '#52c41a' },
    { key: 'review_completed', label: '审查通过', color: '#722ed1' },
    { key: 'verify_completed', label: '验证通过', color: '#fa8c16' },
  ]

  const series = phases.map(phase => ({
    name: phase.label,
    type: 'custom',
    renderItem: renderGanttBar,
    data: sorted.map((t, i) => {
      const start = t.milestones[phase.key]
      const nextPhase = phases.slice(phases.indexOf(phase) + 1).find(p => t.milestones[p.key])
      const end = nextPhase ? t.milestones[nextPhase.key] : (start ? new Date(new Date(start).getTime() + 1800000).toISOString() : null)
      const startOffset = start ? (new Date(start).getTime() - baseTime) / 3600000 : null
      const endOffset = end ? (new Date(end).getTime() - baseTime) / 3600000 : null
      return {
        value: [i, startOffset, endOffset, start, end],
        itemStyle: { color: phase.color },
      }
    }),
  }))

  chart.setOption({
    tooltip: {
      formatter(params) {
        const t = sorted[params.value[0]]
        const phase = phases[params.seriesIndex]
        const start = params.value[3]
        const end = params.value[4]
        return `<b>${esc(t.title)}</b><br/>${phase.label}: ${formatTime(start)}${end ? ' → ' + formatTime(end) : ''}`
      },
    },
    legend: { data: phases.map(p => p.label), top: 0 },
    grid: { left: 180, right: 40, top: 40, bottom: 30 },
    xAxis: { type: 'value', name: '时间 (h)', axisLabel: { formatter: v => v.toFixed(1) } },
    yAxis: { type: 'category', data: categories, inverse: true, axisLabel: { fontSize: 11 } },
    series,
    dataZoom: [{ type: 'slider', xAxisIndex: 0 }],
  })

  window.addEventListener('resize', () => chart.resize())
}

function renderGanttBar(params, api) {
  const idx = api.value(0)
  const start = api.value(1)
  const end = api.value(2)
  if (start == null) return

  const categoryHeight = api.size([0, 1])[1]
  const barHeight = Math.max(categoryHeight * 0.6, 4)

  return {
    type: 'rect',
    shape: {
      x: api.coord([start, idx - 0.5 + (1 - barHeight / categoryHeight) / 2])[0],
      y: api.coord([0, idx])[1] - barHeight / 2,
      width: Math.max(api.coord([end, 0])[0] - api.coord([start, 0])[0], 2),
      height: barHeight,
    },
    style: api.style(),
  }
}

// --- Agent Stats View ---
function renderAgentStats(agentsPayload) {
  const agents = (agentsPayload && agentsPayload.agents) || []

  if (!agents.length) {
    document.getElementById('agent-tasks-chart').innerHTML = '<div class="empty-state">暂无 Agent 统计数据</div>'
    document.getElementById('agent-load-chart').innerHTML = ''
    return
  }

  const names = agents.map(s => s.agent_id)
  const completedCounts = agents.map(s => s.completed_task_count || 0)
  const loadCounts = agents.map(s => s.current_load_count || 0)
  const readyCounts = agents.map(s => s.ready_for_merge_count || 0)
  const workHours = agents.map(s => (s.total_tracked_work_seconds || 0) / 3600)

  // Task counts chart
  const taskChart = echarts.init(document.getElementById('agent-tasks-chart'))
  taskChart.setOption({
    title: { text: 'Agent 任务统计', left: 'center', textStyle: { fontSize: 14 } },
    tooltip: { trigger: 'axis' },
    legend: { data: ['已完成', '当前负载', '待合入'], top: 30 },
    grid: { left: 60, right: 20, top: 70, bottom: 30 },
    xAxis: { type: 'category', data: names },
    yAxis: { type: 'value', name: '任务数' },
    series: [
      { name: '已完成', type: 'bar', data: completedCounts, itemStyle: { color: '#52c41a' } },
      { name: '当前负载', type: 'bar', data: loadCounts, itemStyle: { color: '#1677ff' } },
      { name: '待合入', type: 'bar', data: readyCounts, itemStyle: { color: '#faad14' } },
    ],
  })

  // Work hours chart
  const loadChart = echarts.init(document.getElementById('agent-load-chart'))
  loadChart.setOption({
    title: { text: 'Agent 工作时长 (小时)', left: 'center', textStyle: { fontSize: 14 } },
    tooltip: { trigger: 'axis', formatter: p => `${p[0].name}: ${p[0].value.toFixed(1)}h` },
    grid: { left: 60, right: 20, top: 50, bottom: 30 },
    xAxis: { type: 'category', data: names },
    yAxis: { type: 'value', name: '小时' },
    series: [{ type: 'bar', data: workHours.map(v => Math.round(v * 10) / 10), itemStyle: { color: '#722ed1' } }],
  })

  window.addEventListener('resize', () => { taskChart.resize(); loadChart.resize() })
}

// --- Helpers ---
function esc(s) {
  if (!s) return ''
  const d = document.createElement('div')
  d.textContent = s
  return d.innerHTML
}

function formatTime(iso) {
  if (!iso) return '-'
  const d = new Date(iso)
  if (isNaN(d.getTime())) return '-'
  return `${d.getMonth() + 1}/${d.getDate()} ${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`
}

// --- Init ---
async function init() {
  const [boardPayload, ganttPayload, agentsPayload] = await Promise.all([
    fetchBoard(),
    fetchGantt(),
    fetchAgents(),
  ])

  document.getElementById('last-update').textContent = `更新: ${new Date().toLocaleTimeString()}`

  renderKanban(boardPayload)
  renderGantt(ganttPayload)
  renderAgentStats(agentsPayload)
}

init()
