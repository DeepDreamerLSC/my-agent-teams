// --- Config ---
const API_BASE = '/api'
const BOARD_COLUMNS = ['pending', 'working', 'ready_for_merge', 'blocked', 'done']
const BOARD_LABELS = {
  pending: '待开始', working: '执行中', ready_for_merge: '待合入', blocked: '阻塞', done: '已完成',
}
const CURRENT_STATUS_LABELS = {
  pending: '待派发', pooled: '待认领', dispatched: '已派发', working: '执行中', ready_for_merge: '待合入',
  blocked: '阻塞', done: '已完成', failed: '失败', timeout: '超时', cancelled: '已取消',
  merged: '已合入', archived: '已归档',
}
const EVENT_TYPE_LABELS = {
  created: '创建',
  status_transition: '状态流转',
  ack: 'ACK',
  result: '结果提交',
  review_completed: '审查完成',
  verify_completed: '验证完成',
  task_announce: '任务公告',
  question: '提问',
  answer: '回答',
  decision: '决策',
  task_done: '任务同步',
  notify: '系统通知',
  dispatch: '派发事件',
  nudge: '强制唤醒',
}

const detailDrawer = document.getElementById('task-detail-drawer')
const detailBackdrop = document.getElementById('task-detail-backdrop')
const detailCloseBtn = document.getElementById('detail-close')
const detailTitle = document.getElementById('detail-title')
const detailSubtitle = document.getElementById('detail-subtitle')
const detailBody = document.getElementById('detail-body')
const filterProject = document.getElementById('filter-project')
const filterDomain = document.getElementById('filter-domain')
const filterAgent = document.getElementById('filter-agent')
const filterOwnerPm = document.getElementById('filter-owner-pm')
const filterReviewLevel = document.getElementById('filter-review-level')
const filterReset = document.getElementById('filter-reset')

let currentDetailTaskId = null
let latestBoardPayload = null

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

if (detailCloseBtn) detailCloseBtn.addEventListener('click', closeTaskDetail)
if (detailBackdrop) detailBackdrop.addEventListener('click', closeTaskDetail)

// --- Data layer ---
async function fetchJson(url) {
  try {
    const res = await fetch(url)
    if (!res.ok) throw new Error(`HTTP ${res.status}`)
    return await res.json()
  } catch {
    return null
  }
}

async function fetchBoard() {
  return fetchJson(`${API_BASE}/board`)
}

async function fetchGantt() {
  return fetchJson(`${API_BASE}/gantt`)
}

async function fetchAgents() {
  return fetchJson(`${API_BASE}/agents`)
}

async function fetchTaskDetail(taskId) {
  return fetchJson(`${API_BASE}/tasks/${encodeURIComponent(taskId)}/detail`)
}

function getActiveFilters() {
  return {
    project: filterProject?.value || '',
    domain: filterDomain?.value || '',
    assigned_agent: filterAgent?.value || '',
    owner_pm: filterOwnerPm?.value || '',
    review_level: filterReviewLevel?.value || '',
  }
}

function populateFilterSelect(selectEl, values, placeholder) {
  if (!selectEl) return
  const current = selectEl.value
  selectEl.innerHTML = `<option value="">${placeholder}</option>` + values.map(value => `<option value="${esc(value)}">${esc(value)}</option>`).join('')
  if (values.includes(current)) {
    selectEl.value = current
  }
}

function renderKanbanFilters(tasks) {
  populateFilterSelect(filterProject, buildFilterOptions(tasks, 'project'), '全部项目')
  populateFilterSelect(filterDomain, buildFilterOptions(tasks, 'domain'), '全部领域')
  populateFilterSelect(filterAgent, buildFilterOptions(tasks, 'assigned_agent'), '全部负责人')
  populateFilterSelect(filterOwnerPm, buildFilterOptions(tasks, 'owner_pm'), '全部 Owner PM')
  populateFilterSelect(filterReviewLevel, buildFilterOptions(tasks, 'review_level'), '全部审查级别')
}

// --- Kanban View ---
function renderKanban(boardPayload) {
  latestBoardPayload = boardPayload
  const board = document.getElementById('kanban-board')
  board.innerHTML = ''

  const grouped = {}
  BOARD_COLUMNS.forEach(s => { grouped[s] = [] })
  const allTasks = []

  if (boardPayload && boardPayload.columns) {
    boardPayload.columns.forEach(col => {
      if (col.tasks && BOARD_COLUMNS.includes(col.key)) {
        grouped[col.key] = col.tasks
        allTasks.push(...col.tasks)
      }
    })
  }

  renderKanbanFilters(allTasks)
  const filters = getActiveFilters()
  BOARD_COLUMNS.forEach(status => {
    grouped[status] = applyTaskFilters(grouped[status], filters)
  })
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
      const commCount = Number(task.communication_count || 0)
      const statusHours = hoursBetween(task.current_status_at || task.created_at, new Date().toISOString())
      const priorityTag = task.priority ? `<span class="card-priority priority-${esc(String(task.priority).toLowerCase())}">${esc(task.priority)}</span>` : ''
      const envTag = task.target_environment ? `<span class="card-env">${esc(task.target_environment)}</span>` : ''

      const card = document.createElement('button')
      card.type = 'button'
      card.className = 'kanban-card'
      card.innerHTML = `
        <div class="card-title">${esc(task.title)}</div>
        ${badge}
        <div class="card-chain">Owner PM: ${esc(task.owner_pm || '-')} · Reviewer: ${esc(task.reviewer || '-')} · Integration: ${esc(task.integration_owner || '-')}</div>
        <div class="card-meta">
          ${task.project || ''} · ${formatTime(task.created_at)}
        </div>
        <div class="card-meta">
          沟通记录：${commCount} · 当前状态停留：${formatDurationHours(statusHours)}
        </div>
        <div class="card-tags">
          <span class="card-agent">${esc(task.assigned_agent)}</span>
          <span class="card-domain">${esc(task.domain)}</span>
          ${priorityTag}
          ${envTag}
        </div>
      `
      card.addEventListener('click', () => openTaskDetail(task.task_id))
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

// --- Task Detail Drawer ---
async function openTaskDetail(taskId) {
  currentDetailTaskId = taskId
  detailTitle.textContent = '任务详情'
  detailSubtitle.textContent = taskId
  detailBody.innerHTML = '<div class="empty-state">加载中...</div>'
  detailDrawer.classList.remove('hidden')
  detailBackdrop.classList.remove('hidden')
  detailDrawer.setAttribute('aria-hidden', 'false')

  const payload = await fetchTaskDetail(taskId)
  if (!payload || !payload.task) {
    detailBody.innerHTML = '<div class="empty-state">任务详情加载失败</div>'
    return
  }
  renderTaskDetail(payload)
}

function closeTaskDetail() {
  detailDrawer.classList.add('hidden')
  detailBackdrop.classList.add('hidden')
  detailDrawer.setAttribute('aria-hidden', 'true')
  currentDetailTaskId = null
}

function renderTaskDetail(payload) {
  const task = payload.task || {}
  const durations = payload.durations || {}
  const statusTimeline = payload.status_timeline || []
  const communicationTimeline = payload.communication_timeline || []

  detailTitle.textContent = task.title || task.task_id || '任务详情'
  detailSubtitle.textContent = `${task.task_id || ''} · ${task.project || '-'} · ${task.domain || '-'}`
  detailBody.innerHTML = `
    <section class="detail-section">
      <h3>基本信息</h3>
      <div class="detail-grid">
        ${detailItem('任务ID', task.task_id)}
        ${detailItem('当前状态', task.current_status)}
        ${detailItem('看板列', task.board_status)}
        ${detailItem('负责人', task.assigned_agent)}
        ${detailItem('Owner PM', task.owner_pm)}
        ${detailItem('Reviewer', task.reviewer)}
        ${detailItem('创建时间', formatTime(task.created_at))}
        ${detailItem('最近状态时间', formatTime(task.current_status_at))}
        ${detailItem('沟通记录数', task.communication_count ?? 0)}
      </div>
      <div class="detail-summary">${esc(task.summary || '无摘要')}</div>
    </section>

    <section class="detail-section">
      <h3>阶段耗时</h3>
      <div class="detail-grid">
        ${detailItem('创建→派发', formatHours(durations.create_to_dispatch_hours))}
        ${detailItem('派发→ACK', formatHours(durations.dispatch_to_ack_hours))}
        ${detailItem('ACK→结果', formatHours(durations.ack_to_result_hours))}
        ${detailItem('结果→审查', formatHours(durations.result_to_review_hours))}
        ${detailItem('审查→验证', formatHours(durations.review_to_verify_hours))}
        ${detailItem('验证→当前', formatHours(durations.verify_to_close_hours))}
        ${detailItem('总周期', formatHours(durations.total_cycle_hours))}
      </div>
    </section>

    <section class="detail-section">
      <h3>状态流转时间线</h3>
      ${renderTimeline(statusTimeline, 'status')}
    </section>

    <section class="detail-section">
      <h3>沟通时间线</h3>
      ${renderTimeline(communicationTimeline, 'communication')}
    </section>
  `
}

function renderTimeline(items, mode) {
  if (!items || !items.length) {
    return '<div class="empty-state small">暂无记录</div>'
  }
  const lines = items.map(item => {
    const when = formatTime(item.happened_at || item.observed_at)
    if (mode === 'status') {
      return `
        <div class="timeline-item status">
          <div class="timeline-time">${when}</div>
          <div class="timeline-content">
            <div class="timeline-title">${esc(EVENT_TYPE_LABELS[item.event_type] || item.event_type)}</div>
            <div class="timeline-meta">${esc(item.source || '')}${item.status_from || item.status_to ? ` · ${esc(item.status_from || '-') } → ${esc(item.status_to || '-')}` : ''}</div>
            <div class="timeline-text">${esc(item.summary || '')}</div>
          </div>
        </div>
      `
    }
    return `
      <div class="timeline-item communication">
        <div class="timeline-time">${when}</div>
        <div class="timeline-content">
          <div class="timeline-title">${esc(EVENT_TYPE_LABELS[item.event_type] || item.event_type)} · ${esc(item.from_actor || '-')} → ${esc(item.to_actor || '-')}</div>
          <div class="timeline-meta">${esc(item.channel || '')}${item.severity ? ` · severity=${esc(item.severity)}` : ''}${item.priority ? ` · priority=${esc(item.priority)}` : ''}</div>
          <div class="timeline-text">${esc(item.message_text || '')}</div>
        </div>
      </div>
    `
  })
  return `<div class="timeline-list">${lines.join('')}</div>`
}

function detailItem(label, value) {
  return `
    <div class="detail-item">
      <div class="detail-label">${esc(label)}</div>
      <div class="detail-value">${esc(value == null || value === '' ? '-' : String(value))}</div>
    </div>
  `
}

;[filterProject, filterDomain, filterAgent, filterOwnerPm, filterReviewLevel].forEach(selectEl => {
  if (selectEl) {
    selectEl.addEventListener('change', () => {
      if (latestBoardPayload) renderKanban(latestBoardPayload)
    })
  }
})

if (filterReset) {
  filterReset.addEventListener('click', () => {
    ;[filterProject, filterDomain, filterAgent, filterOwnerPm, filterReviewLevel].forEach(selectEl => {
      if (selectEl) selectEl.value = ''
    })
    if (latestBoardPayload) renderKanban(latestBoardPayload)
  })
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

function formatHours(value) {
  if (value == null || Number.isNaN(value)) return '-'
  return `${Number(value).toFixed(2)}h`
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
