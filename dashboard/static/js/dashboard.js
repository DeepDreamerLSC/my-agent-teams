;(function () {
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
const MERGE_GATE_LABELS = {
  review_pending: '待审查',
  review_rejected: '审查驳回',
  quality_pending: '并行质控中',
  qa_pending: '待QA',
  qa_failed: 'QA未通过',
  pm_acceptance_pending: '待PM收口',
  closed: '已收口',
  blocked: '阻塞',
}
const QUALITY_GATE_MODE_LABELS = {
  single: '单门禁',
  serial: '串行',
  parallel: '并行',
}
const REVIEW_GATE_STATE_LABELS = {
  pending: '待审查',
  approved: '已通过',
  rejected: '已驳回',
  blocked: '阻塞',
  skipped: '跳过',
}
const QA_GATE_STATE_LABELS = {
  pending: '待QA',
  passed: '已通过',
  failed: '未通过',
  blocked: '阻塞',
  skipped: '跳过',
}
const CONTROL_PLANE_LABELS = {
  delivery_failed: '投递失败',
  session_unhealthy: '会话异常',
  auto_requeue: '自动回池',
  reassigned: '自动转派',
}
const INTEGRATION_QUEUE_STATE_LABELS = {
  queued: '待集成',
  metadata_missing: '缺少元数据',
  workspace_error: '工作区异常',
  blocked: '已阻塞',
  in_progress: '执行中',
  accepted: '已收口',
  merged: '已合入',
  closed: '已关闭',
  pending: '未入队',
  not_applicable: '不适用',
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
const GANTT_PHASES = [
  { key: 'pooled', label: '入池等待', color: '#1677ff' },
  { key: 'reserved', label: '已派发/预留', color: '#13c2c2' },
  { key: 'working', label: '执行中', color: '#722ed1' },
  { key: 'review', label: '审查', color: '#faad14' },
  { key: 'qa', label: 'QA', color: '#52c41a' },
  { key: 'pm_acceptance', label: 'PM收口', color: '#ff4d4f' },
]


const docRef = typeof document !== 'undefined' ? document : null
const detailDrawer = docRef ? docRef.getElementById('task-detail-drawer') : null
const detailBackdrop = docRef ? docRef.getElementById('task-detail-backdrop') : null
const detailCloseBtn = docRef ? docRef.getElementById('detail-close') : null
const detailTitle = docRef ? docRef.getElementById('detail-title') : null
const detailSubtitle = docRef ? docRef.getElementById('detail-subtitle') : null
const detailBody = docRef ? docRef.getElementById('detail-body') : null
const filterProject = docRef ? docRef.getElementById('filter-project') : null
const filterDomain = docRef ? docRef.getElementById('filter-domain') : null
const filterAgent = docRef ? docRef.getElementById('filter-agent') : null
const filterOwnerPm = docRef ? docRef.getElementById('filter-owner-pm') : null
const filterReviewLevel = docRef ? docRef.getElementById('filter-review-level') : null
const filterMergeGate = docRef ? docRef.getElementById('filter-merge-gate') : null
const filterReset = docRef ? docRef.getElementById('filter-reset') : null
const ganttRangeButtons = docRef ? Array.from(docRef.querySelectorAll('[data-gantt-range]')) : []
const ganttStartDate = docRef ? docRef.getElementById('gantt-start-date') : null
const ganttEndDate = docRef ? docRef.getElementById('gantt-end-date') : null
const ganttFilterHint = docRef ? docRef.getElementById('gantt-filter-hint') : null

let currentDetailTaskId = null
let latestBoardPayload = null
let latestGanttPayload = null

function initDashboardChart(el) {
  if (!el || typeof echarts === 'undefined') return null
  const existing = echarts.getInstanceByDom ? echarts.getInstanceByDom(el) : null
  return existing || echarts.init(el, 'dark')
}
let ganttFilterState = { mode: '7d', customStart: '', customEnd: '' }

// --- Tab switching ---
if (docRef) {
  document.querySelectorAll('.tab').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'))
      document.querySelectorAll('.view').forEach(v => v.classList.remove('active'))
      btn.classList.add('active')
      document.getElementById(btn.dataset.tab).classList.add('active')
      window.dispatchEvent(new Event('resize'))
    })
  })
}

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

async function fetchPool() {
  return fetchJson(`${API_BASE}/pool`)
}

async function fetchIntegrationQueue() {
  return fetchJson(`${API_BASE}/integration-queue`)
}

async function fetchPmInbox() {
  return fetchJson(`${API_BASE}/pm-inbox`)
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
    merge_gate_state: filterMergeGate?.value || '',
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
  if (filterMergeGate) {
    const current = filterMergeGate.value
    const values = buildFilterOptions(tasks, 'merge_gate_state')
    filterMergeGate.innerHTML = `<option value="">全部收口阶段</option>` + values.map(value => `<option value="${esc(value)}">${esc(MERGE_GATE_LABELS[value] || value)}</option>`).join('')
    if (values.includes(current)) filterMergeGate.value = current
  }
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
      const reviewLevelTag = task.review_level ? `<span class="card-review-level">审查:${esc(task.review_level)}</span>` : ''
      const gateTag = task.merge_gate_state ? `<span class="card-gate gate-${esc(String(task.merge_gate_state).toLowerCase())}">${esc(MERGE_GATE_LABELS[task.merge_gate_state] || task.merge_gate_state)}</span>` : ''

      const card = document.createElement('button')
      card.type = 'button'
      card.className = 'kanban-card'
      card.innerHTML = `
        <div class="card-title">${esc(task.title)}</div>
        ${badge}
        <div class="card-chain">Owner PM: ${esc(task.owner_pm || '-')} · Reviewer: ${esc(task.reviewer || '-')} · Integration: ${esc(task.integration_owner || '-')}</div>
        <div class="card-meta">
          ${esc(task.project || '')} · ${formatTime(task.created_at)}
        </div>
        <div class="card-meta">
          沟通记录：${commCount} · 当前状态停留：${formatDurationHours(statusHours)}
        </div>
        <div class="card-tags">
          <span class="card-agent">${esc(task.assigned_agent)}</span>
          <span class="card-domain">${esc(task.domain)}</span>
          ${gateTag}
          ${reviewLevelTag}
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
function startOfLocalDay(date) {
  return new Date(date.getFullYear(), date.getMonth(), date.getDate(), 0, 0, 0, 0)
}

function endOfLocalDay(date) {
  return new Date(date.getFullYear(), date.getMonth(), date.getDate(), 23, 59, 59, 999)
}

function parseLocalDateInput(value, endOfDay) {
  if (!value || !/^\d{4}-\d{2}-\d{2}$/.test(value)) return null
  const [year, month, day] = value.split('-').map(Number)
  const parsed = endOfDay
    ? new Date(year, month - 1, day, 23, 59, 59, 999)
    : new Date(year, month - 1, day, 0, 0, 0, 0)
  return Number.isNaN(parsed.getTime()) ? null : parsed
}

function getGanttDateRange(state = ganttFilterState, now = new Date()) {
  const mode = state.mode || 'all'
  if (mode === 'all') {
    return { start: null, end: null, label: '显示全部时间', warning: '' }
  }
  if (mode === 'custom') {
    const start = parseLocalDateInput(state.customStart, false)
    const end = parseLocalDateInput(state.customEnd, true)
    if (!start && !end) return { start: null, end: null, label: '自定义日期为空，显示全部时间', warning: '请选择自定义开始或结束日期' }
    if (start && end && start.getTime() > end.getTime()) {
      return { start: null, end: null, label: '自定义日期非法，显示全部时间', warning: '开始日期不能晚于结束日期' }
    }
    return { start, end, label: `自定义：${state.customStart || '不限'} 至 ${state.customEnd || '不限'}`, warning: '' }
  }

  const end = endOfLocalDay(now)
  const daysByMode = { today: 1, '3d': 3, '7d': 7, '30d': 30 }
  const labels = { today: '今天', '3d': '近三天', '7d': '近七天', '30d': '近一个月' }
  const days = daysByMode[mode] || 1
  const startBase = startOfLocalDay(now)
  const start = new Date(startBase.getTime())
  start.setDate(start.getDate() - (days - 1))
  return { start, end, label: labels[mode] || '今天', warning: '' }
}

function getTaskGanttIntervals(task) {
  const segments = Array.isArray(task?.phase_segments) ? task.phase_segments.filter(Boolean) : []
  if (segments.length) {
    return segments.map(segment => {
      const start = new Date(segment.start_at)
      const end = new Date(segment.end_at)
      if (Number.isNaN(start.getTime()) || Number.isNaN(end.getTime())) return null
      return { start, end }
    }).filter(Boolean)
  }
  const milestones = (task && task.milestones) || {}
  return GANTT_PHASES.map((phase, index) => {
    const start = milestones[phase.key]
    if (!start) return null
    const nextPhase = GANTT_PHASES.slice(index + 1).find(p => milestones[p.key])
    const startDate = new Date(start)
    const endDate = nextPhase ? new Date(milestones[nextPhase.key]) : new Date(startDate.getTime() + 1800000)
    if (Number.isNaN(startDate.getTime()) || Number.isNaN(endDate.getTime())) return null
    return { start: startDate, end: endDate }
  }).filter(Boolean)
}

function intervalIntersectsRange(interval, range) {
  const rangeStart = range.start ? range.start.getTime() : -Infinity
  const rangeEnd = range.end ? range.end.getTime() : Infinity
  return interval.end.getTime() >= rangeStart && interval.start.getTime() <= rangeEnd
}

function applyGanttTimeFilter(items, state = ganttFilterState, now = new Date()) {
  const range = getGanttDateRange(state, now)
  if (!range.start && !range.end) return { items: items || [], range }
  return {
    range,
    items: (items || []).filter(task => getTaskGanttIntervals(task).some(interval => intervalIntersectsRange(interval, range))),
  }
}

function setGanttFilterHint(range, count, total) {
  if (!ganttFilterHint) return
  const warning = range.warning ? `（${range.warning}）` : ''
  ganttFilterHint.textContent = `${range.label}${warning} · ${count}/${total} 个任务`
  ganttFilterHint.classList.toggle('warning', Boolean(range.warning))
}

function rerenderGanttFromState() {
  if (latestGanttPayload) renderGantt(latestGanttPayload)
}

function setGanttFilterMode(mode) {
  ganttFilterState = {
    ...ganttFilterState,
    mode,
    customStart: ganttStartDate?.value || ganttFilterState.customStart,
    customEnd: ganttEndDate?.value || ganttFilterState.customEnd,
  }
  ganttRangeButtons.forEach(btn => btn.classList.toggle('active', btn.dataset.ganttRange === mode))
  rerenderGanttFromState()
}

function bindGanttFilters() {
  ganttRangeButtons.forEach(btn => {
    btn.addEventListener('click', () => setGanttFilterMode(btn.dataset.ganttRange || 'all'))
  })
  ;[ganttStartDate, ganttEndDate].forEach(input => {
    if (!input) return
    input.addEventListener('change', () => {
      ganttFilterState = { ...ganttFilterState, mode: 'custom', customStart: ganttStartDate?.value || '', customEnd: ganttEndDate?.value || '' }
      ganttRangeButtons.forEach(btn => btn.classList.toggle('active', btn.dataset.ganttRange === 'custom'))
      rerenderGanttFromState()
    })
  })
}

function renderGantt(ganttPayload) {
  latestGanttPayload = ganttPayload
  const el = document.getElementById('gantt-chart')
  const allItems = (ganttPayload && ganttPayload.items) || []
  const filtered = applyGanttTimeFilter(allItems, ganttFilterState)
  const items = filtered.items
  setGanttFilterHint(filtered.range, items.length, allItems.length)

  if (!items.length) {
    const existing = echarts.getInstanceByDom ? echarts.getInstanceByDom(el) : null
    if (existing) existing.dispose()
    el.innerHTML = '<div class="empty-state">当前时间范围暂无甘特图数据</div>'
    return
  }

  const existingChart = echarts.getInstanceByDom ? echarts.getInstanceByDom(el) : null
  if (!existingChart) el.innerHTML = ''
  const chart = existingChart || initDashboardChart(el)
  const sorted = [...items].sort((a, b) => new Date(a.display_start_at || a.milestones.created) - new Date(b.display_start_at || b.milestones.created))

  const categories = sorted.map(t => t.title.length > 16 ? t.title.slice(0, 16) + '…' : t.title)
  const baseTime = Math.min(...sorted.map(t => {
    const segments = Array.isArray(t.phase_segments) ? t.phase_segments : []
    const firstStart = segments[0]?.start_at || t.display_start_at || t.milestones.created
    return new Date(firstStart).getTime()
  }))

  const phases = GANTT_PHASES

  const series = phases.map(phase => ({
    name: phase.label,
    type: 'custom',
    renderItem: renderGanttBar,
    data: sorted.map((t, i) => {
      const segment = (Array.isArray(t.phase_segments) ? t.phase_segments : []).find(item => item.key === phase.key)
      const start = segment?.start_at || null
      const end = segment?.end_at || null
      const startOffset = start ? (new Date(start).getTime() - baseTime) / 3600000 : null
      const endOffset = end ? (new Date(end).getTime() - baseTime) / 3600000 : null
      const durationHours = Number(segment?.duration_hours || 0)
      const isLongReviewWait = phase.key === 'completed' && durationHours > 24
      return {
        value: [i, startOffset, endOffset, start, end],
        itemStyle: { color: isLongReviewWait ? '#ff4d4f' : (segment?.color || phase.color) },
        segment,
      }
    }),
  }))

  chart.setOption({
    backgroundColor: 'transparent',
    tooltip: {
      formatter(params) {
        const t = sorted[params.value[0]]
        const phase = phases[params.seriesIndex]
        const start = params.value[3]
        const end = params.value[4]
        const segment = params.data?.segment || {}
        const precision = segment.precision === 'exact' ? 'exact' : 'inferred'
        return `<b>${esc(t.title)}</b><br/>${phase.label} [${precision}]: ${formatTime(start)}${end ? ' → ' + formatTime(end) : ''}`
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

  const taskChart = initDashboardChart(document.getElementById('agent-tasks-chart'))
  taskChart.setOption({
    backgroundColor: 'transparent',
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

  const loadChart = initDashboardChart(document.getElementById('agent-load-chart'))
  loadChart.setOption({
    backgroundColor: 'transparent',
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
  const poolStatus = payload.pool_status || null

  detailTitle.textContent = task.title || task.task_id || '任务详情'
  detailSubtitle.textContent = `${task.task_id || ''} · ${task.project || '-'} · ${task.domain || '-'}`
  detailBody.innerHTML = renderTaskDetailHtml({ task, durations, statusTimeline, communicationTimeline, poolStatus })
}

function renderTaskDetailHtml({ task = {}, durations = {}, statusTimeline = [], communicationTimeline = [], poolStatus = null }) {
  return `
    <section class="detail-section">
      <h3>基本信息</h3>
      <div class="detail-grid">
        ${detailItem('任务ID', task.task_id)}
        ${detailItem('当前状态', task.current_status)}
        ${detailItem('看板列', task.board_status)}
        ${detailItem('收口阶段', MERGE_GATE_LABELS[task.merge_gate_state] || task.merge_gate_state)}
        ${detailItem('质量门禁模式', QUALITY_GATE_MODE_LABELS[task.quality_gate_mode] || task.quality_gate_mode)}
        ${detailItem('审查子门禁', REVIEW_GATE_STATE_LABELS[task.review_gate_state] || task.review_gate_state)}
        ${detailItem('QA子门禁', QA_GATE_STATE_LABELS[task.qa_gate_state] || task.qa_gate_state)}
        ${detailItem('负责人', task.assigned_agent)}
        ${detailItem('Owner PM', task.owner_pm)}
        ${detailItem('Reviewer', task.reviewer)}
        ${detailItem('Integration Owner', task.integration_owner)}
        ${detailItem('控制面状态', CONTROL_PLANE_LABELS[task.control_plane_state] || task.control_plane_state)}
        ${detailItem('投递重试', task.dispatch_delivery_retry_count)}
        ${detailItem('会话健康', task.session_health)}
        ${detailItem('目标环境', task.target_environment)}
        ${detailItem('审查级别', task.review_level)}
        ${detailItem('返工原因', task.rework_reason)}
        ${detailItem('创建时间', formatTime(task.created_at))}
        ${detailItem('最近状态时间', formatTime(task.current_status_at))}
        ${detailItem('沟通记录数', task.communication_count ?? 0)}
      </div>
      <div class="detail-summary">${esc(task.summary || '无摘要')}</div>
    </section>

    ${renderPoolStatusHtml(poolStatus)}

    <section class="detail-section">
      <h3>工作区与集成</h3>
      <div class="detail-grid">
        ${detailItem('工作区模式', task.workspace_mode)}
        ${detailItem('工作区状态', task.workspace_status)}
        ${detailItem('工作区路径', task.workspace_path || task.worktree_path)}
        ${detailItem('工作分支', task.workspace_branch || task.result_branch)}
        ${detailItem('基线分支', task.workspace_base_ref)}
        ${detailItem('目标分支', task.integration_target_branch)}
        ${detailItem('Patch 路径', task.patch_path)}
        ${detailItem('Patch 状态', task.integration_artifact_state)}
        ${detailItem('集成队列状态', INTEGRATION_QUEUE_STATE_LABELS[task.integration_queue_state] || task.integration_queue_state)}
        ${detailItem('入队时间', formatTime(task.integration_queue_entered_at))}
        ${detailItem('工作区异常', task.workspace_error)}
        ${detailItem('集成阻塞', task.integration_blocker)}
      </div>
    </section>

    <section class="detail-section">
      <h3>阶段耗时</h3>
      <div class="detail-grid">
        ${detailItem('创建→派发', formatHours(durations.create_to_dispatch_hours))}
        ${detailItem('派发→ACK', formatHours(durations.dispatch_to_ack_hours))}
        ${detailItem('ACK→结果', formatHours(durations.ack_to_result_hours))}
        ${detailItem('结果→审查', formatHours(durations.result_to_review_hours))}
        ${detailItem('结果→QA', formatHours(durations.result_to_qa_hours))}
        ${detailItem('审查→验证', formatHours(durations.review_to_verify_hours))}
        ${detailItem('质控完成→当前', formatHours(durations.quality_to_acceptance_hours))}
        ${detailItem('验证→当前', formatHours(durations.verify_to_close_hours))}
        ${detailItem('总周期', formatHours(durations.total_cycle_hours))}
      </div>
    </section>

    <section class="detail-section">
      <h3>状态流转时间线</h3>
      ${renderTimelineHtml(statusTimeline, 'status')}
    </section>

    <section class="detail-section">
      <h3>沟通时间线</h3>
      ${renderTimelineHtml(communicationTimeline, 'communication')}
    </section>
  `
}

function renderPoolStatusHtml(poolStatus) {
  if (!poolStatus) return ''
  const blockers = poolStatus.blocked_reasons || []
  const eligible = poolStatus.eligible_agents || []
  const definitionBlockers = poolStatus.definition_blockers || []
  return `
    <section class="detail-section">
      <h3>任务池阻塞</h3>
      <div class="detail-grid">
        ${detailItem('卡住阶段', poolStatus.gate_stage || '-')}
        ${detailItem('等待时长', `${poolStatus.pool_wait_minutes || 0}m`)}
        ${detailItem('定义阻塞', definitionBlockers.join(', ') || '-')}
        ${detailItem('可认领 Agent', eligible.join(', ') || '-')}
        ${detailItem('阻塞原因', blockers.join(', ') || '-')}
        ${detailItem('下一步', poolStatus.next_action || '-')}
      </div>
    </section>
  `
}

function renderTimeline(items, mode) {
  return renderTimelineHtml(items, mode)
}

function sortTimelineItems(items) {
  return [...(items || [])].sort((a, b) => {
    const aTs = new Date(a?.happened_at || a?.observed_at || 0).getTime()
    const bTs = new Date(b?.happened_at || b?.observed_at || 0).getTime()
    if (aTs !== bTs) return aTs - bTs
    return String(a?.event_id || a?.event_type || '').localeCompare(String(b?.event_id || b?.event_type || ''), 'zh-CN')
  })
}

function renderTimelineHtml(items, mode) {
  if (!items || !items.length) {
    return '<div class="empty-state small">暂无记录</div>'
  }
  const lines = sortTimelineItems(items).map(item => {
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

;[filterProject, filterDomain, filterAgent, filterOwnerPm, filterReviewLevel, filterMergeGate].forEach(selectEl => {
  if (selectEl) {
    selectEl.addEventListener('change', () => {
      if (latestBoardPayload) renderKanban(latestBoardPayload)
    })
  }
})

if (filterReset) {
  filterReset.addEventListener('click', () => {
    ;[filterProject, filterDomain, filterAgent, filterOwnerPm, filterReviewLevel, filterMergeGate].forEach(selectEl => {
      if (selectEl) selectEl.value = ''
    })
    if (latestBoardPayload) renderKanban(latestBoardPayload)
  })
}

// --- Helpers ---
function esc(s) {
  if (!s) return ''
  if (!docRef) {
    return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;')
  }
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

function renderSummaryCards(container, cards) {
  if (!container) return
  container.innerHTML = cards.map(card => `
    <div class="summary-card">
      <div class="summary-value">${esc(String(card.value ?? '-'))}</div>
      <div class="summary-label">${esc(card.label)}</div>
    </div>
  `).join('')
}

function renderPoolView(payload) {
  const items = (payload && payload.items) || []
  const summary = (payload && payload.summary) || {}
  const summaryEl = document.getElementById('pool-summary')
  const tbody = document.querySelector('#pool-table tbody')
  const blocked = items.filter(item => !(item.eligible_agents || []).length).length
  renderSummaryCards(summaryEl, [
    { label: '池中任务', value: summary.pooled_count ?? items.length },
    { label: '可认领', value: summary.pool_ready_count ?? (items.length - blocked) },
    { label: '空闲Agent', value: summary.idle_agent_count ?? '-' },
    { label: '定义阻塞', value: summary.definition_blocked_count ?? '-' },
    { label: '产物异常', value: summary.artifact_invalid_count ?? '-' },
  ])
  if (!tbody) return
  tbody.innerHTML = items.length ? items.map(item => `
    <tr>
      <td>${esc(item.title || item.task_id)}</td>
      <td>${esc(item.priority || '-')}</td>
      <td>${esc(String(item.pool_wait_minutes || 0))}m</td>
      <td>${esc((item.claim_scope || []).join(', ') || '-')}</td>
      <td>${esc((item.eligible_agents || []).join(', ') || '-')}</td>
      <td>${esc((item.blocked_reasons || []).join(', ') || '-')}</td>
      <td>${esc(item.next_action || '-')}</td>
    </tr>
  `).join('') : '<tr><td colspan="7" class="empty-state small">暂无 pooled 任务</td></tr>'
}

function renderIntegrationQueueView(payload) {
  const items = (payload && payload.items) || []
  const summary = (payload && payload.summary) || {}
  const summaryEl = document.getElementById('integration-queue-summary')
  const tbody = document.querySelector('#integration-queue-table tbody')
  renderSummaryCards(summaryEl, [
    { label: '队列任务', value: summary.item_count ?? items.length },
    { label: '待集成', value: summary.queued_count ?? items.filter(item => item.state === 'queued').length },
    { label: '工作区异常', value: summary.workspace_error_count ?? items.filter(item => item.state === 'workspace_error').length },
    { label: '缺元数据', value: summary.metadata_missing_count ?? items.filter(item => item.state === 'metadata_missing').length },
    { label: '已收口', value: summary.accepted_count ?? items.filter(item => item.state === 'accepted').length },
  ])
  if (!tbody) return
  tbody.innerHTML = items.length ? items.map(item => `
    <tr>
      <td>${esc(item.title || item.task_id)}</td>
      <td>${esc(INTEGRATION_QUEUE_STATE_LABELS[item.state] || item.state || '-')}</td>
      <td>${esc(item.target_branch || '-')}</td>
      <td>${esc(item.workspace_branch || '-')}</td>
      <td>${esc(item.patch_exists ? (item.patch_path || '已生成') : (item.patch_path || '-'))}</td>
      <td>${esc(item.worktree_path || item.workspace_status || '-')}</td>
      <td>${esc(item.blocker || item.artifact_state || '-')}</td>
    </tr>
  `).join('') : '<tr><td colspan="7" class="empty-state small">暂无 integration queue 项目</td></tr>'
}

function renderPmInboxView(payload) {
  const items = (payload && payload.items) || []
  const summaryEl = document.getElementById('pm-inbox-summary')
  const tbody = document.querySelector('#pm-inbox-table tbody')
  renderSummaryCards(summaryEl, [
    { label: '待处理事项', value: items.length },
    { label: 'L3', value: items.filter(item => item.severity === 'L3').length },
    { label: 'L2', value: items.filter(item => item.severity === 'L2').length },
    { label: '最久等待(分)', value: items.reduce((max, item) => Math.max(max, Number(item.age_minutes || 0)), 0) },
  ])
  if (!tbody) return
  tbody.innerHTML = items.length ? items.map(item => `
    <tr>
      <td>${esc(item.severity || '-')}</td>
      <td>${esc(item.title || item.task_id)}</td>
      <td>${esc(item.reason_type || '-')}</td>
      <td>${esc(item.summary || '-')}</td>
      <td>${esc(String(item.age_minutes || 0))}m</td>
      <td>${esc(item.recommended_action || '-')}</td>
    </tr>
  `).join('') : '<tr><td colspan="6" class="empty-state small">暂无待 PM 处理事项</td></tr>'
}

// --- Analytics Data Layer ---
async function fetchAggregate() {
  return fetchJson(`${API_BASE}/tasks/aggregate`)
}

async function fetchDailyMetrics() {
  return fetchJson(`${API_BASE}/metrics/daily`)
}

// --- Analytics View ---
function renderAnalytics(aggregatePayload, dailyPayload, agentsPayload) {
  const agg = transformAggregateForAnalytics(aggregatePayload)
  const daily = transformDailyMetrics(dailyPayload)
  const agentEff = computeAgentEfficiency(agentsPayload)

  renderAnalyticsSummary(agg, daily)
  renderTrendChart(daily)
  renderAggregationCharts(agg)
  renderRoleEfficiencyChart(agentEff)
}

function renderAnalyticsSummary(agg, daily) {
  const metrics = daily.taskMetrics
  const latest = metrics && metrics.length ? metrics[metrics.length - 1] : null

  const totalEl = document.querySelector('#mc-total .metric-value')
  const doneEl = document.querySelector('#mc-done .metric-value')
  const rateEl = document.querySelector('#mc-rate .metric-value')
  const avgCycleEl = document.querySelector('#mc-avg-cycle .metric-value')
  const avgDevEl = document.querySelector('#mc-avg-dev .metric-value')
  const blockedEl = document.querySelector('#mc-blocked .metric-value')
  const poolWaitEl = document.querySelector('#mc-pool-wait .metric-value')
  const claimLatencyEl = document.querySelector('#mc-claim-latency .metric-value')
  const reviewWaitEl = document.querySelector('#mc-review-wait .metric-value')
  const reworkRateEl = document.querySelector('#mc-rework-rate .metric-value')

  if (agg) {
    if (totalEl) totalEl.textContent = agg.total
    if (doneEl) doneEl.textContent = agg.done
    if (rateEl) rateEl.textContent = (agg.completionRate * 100).toFixed(1) + '%'
    if (blockedEl) blockedEl.textContent = (agg.blockedRate * 100).toFixed(1) + '%'
    if (poolWaitEl) poolWaitEl.textContent = agg.collaborationMetrics?.avgPoolWaitMinutes != null ? `${Number(agg.collaborationMetrics.avgPoolWaitMinutes).toFixed(1)}m` : '-'
    if (claimLatencyEl) claimLatencyEl.textContent = agg.collaborationMetrics?.avgClaimLatencyMinutes != null ? `${Number(agg.collaborationMetrics.avgClaimLatencyMinutes).toFixed(1)}m` : '-'
    if (reviewWaitEl) reviewWaitEl.textContent = agg.collaborationMetrics?.avgReviewWaitHours != null ? `${Number(agg.collaborationMetrics.avgReviewWaitHours).toFixed(2)}h` : '-'
    if (reworkRateEl) reworkRateEl.textContent = agg.collaborationMetrics?.reworkRate != null ? `${(Number(agg.collaborationMetrics.reworkRate) * 100).toFixed(1)}%` : '-'

    const rateCard = document.getElementById('mc-rate')
    const blockedCard = document.getElementById('mc-blocked')
    if (rateCard) { rateCard.className = 'metric-card highlight ' + (agg.completionRate >= 0.7 ? 'good' : agg.completionRate >= 0.4 ? 'warn' : 'bad') }
    if (blockedCard) { blockedCard.className = 'metric-card ' + (agg.blockedRate <= 0.1 ? 'good' : agg.blockedRate <= 0.3 ? 'warn' : 'bad') }
  }

  if (latest) {
    if (avgCycleEl) avgCycleEl.textContent = formatSecondsCompact(latest.avg_cycle_seconds)
    if (avgDevEl) avgDevEl.textContent = formatSecondsCompact(latest.avg_ack_to_result_seconds)
  }
}

function renderTrendChart(daily) {
  const el = document.getElementById('trend-chart')
  const metrics = daily.taskMetrics || []
  if (!metrics.length) {
    el.innerHTML = '<div class="empty-state">暂无日指标数据</div>'
    return
  }

  const chart = initDashboardChart(el)
  const dates = metrics.map(m => m.metric_date || '')
  const completionRates = metrics.map(m => m.completion_rate != null ? (m.completion_rate * 100).toFixed(1) : null)
  const blockedRates = metrics.map(m => m.blocked_rate != null ? (m.blocked_rate * 100).toFixed(1) : null)
  const createdCounts = metrics.map(m => m.created_task_count || 0)
  const completedCounts = metrics.map(m => m.completed_task_count || 0)

  chart.setOption({
    backgroundColor: 'transparent',
    title: { text: '日指标趋势', left: 'center', textStyle: { fontSize: 14 } },
    tooltip: { trigger: 'axis' },
    legend: { data: ['完成率(%)', '阻塞率(%)', '创建数', '完成数'], top: 30 },
    grid: { left: 60, right: 60, top: 70, bottom: 30 },
    xAxis: { type: 'category', data: dates },
    yAxis: [
      { type: 'value', name: '%', max: 100 },
      { type: 'value', name: '任务数', position: 'right' },
    ],
    series: [
      { name: '完成率(%)', type: 'line', data: completionRates, smooth: true, itemStyle: { color: '#52c41a' } },
      { name: '阻塞率(%)', type: 'line', data: blockedRates, smooth: true, itemStyle: { color: '#ff4d4f' } },
      { name: '创建数', type: 'bar', yAxisIndex: 1, data: createdCounts, itemStyle: { color: '#69b1ff' } },
      { name: '完成数', type: 'bar', yAxisIndex: 1, data: completedCounts, itemStyle: { color: '#52c41a' } },
    ],
  })
  window.addEventListener('resize', () => chart.resize())
}

function renderAggregationCharts(agg) {
  const ownerPmEl = document.getElementById('owner-pm-chart')
  const domainEl = document.getElementById('domain-chart')

  const ownerPmData = agg ? agg.ownerPmCounts : {}
  const domainData = agg ? agg.domainCounts : {}

  renderDimensionChart(ownerPmEl, 'Owner PM 任务分布', ownerPmData)
  renderDimensionChart(domainEl, 'Domain 任务分布', domainData)
}

function renderDimensionChart(el, title, data) {
  if (!el) return
  const keys = Object.keys(data || {})
  if (!keys.length) {
    el.innerHTML = `<div class="empty-state">${title}：暂无数据</div>`
    return
  }
  const chart = initDashboardChart(el)
  const values = keys.map(k => data[k])
  const colors = ['#1677ff', '#52c41a', '#faad14', '#722ed1', '#ff4d4f', '#13c2c2', '#eb2f96']

  chart.setOption({
    backgroundColor: 'transparent',
    title: { text: title, left: 'center', textStyle: { fontSize: 14 } },
    tooltip: { trigger: 'item', formatter: '{b}: {c} ({d}%)' },
    legend: { orient: 'vertical', left: 'left', top: 40, type: 'scroll' },
    series: [{
      type: 'pie',
      radius: ['35%', '65%'],
      center: ['55%', '55%'],
      data: keys.map((k, i) => ({ name: k, value: values[i], itemStyle: { color: colors[i % colors.length] } })),
      label: { formatter: '{b}\n{c}', fontSize: 12 },
    }],
  })
  window.addEventListener('resize', () => chart.resize())
}

function renderRoleEfficiencyChart(agentEff) {
  const el = document.getElementById('role-efficiency-chart')
  if (!el) return
  if (!agentEff.length) {
    el.innerHTML = '<div class="empty-state">暂无角色效率数据</div>'
    return
  }

  const chart = initDashboardChart(el)
  const names = agentEff.map(a => a.agentId)
  const completed = agentEff.map(a => a.completed)
  const workHours = agentEff.map(a => Math.round(a.workHours * 10) / 10)
  const comms = agentEff.map(a => a.communications)

  chart.setOption({
    backgroundColor: 'transparent',
    title: { text: '角色效率对比', left: 'center', textStyle: { fontSize: 14 } },
    tooltip: { trigger: 'axis' },
    legend: { data: ['已完成任务', '工作时长(h)', '沟通记录'], top: 30 },
    grid: { left: 60, right: 60, top: 70, bottom: 30 },
    xAxis: { type: 'category', data: names },
    yAxis: [
      { type: 'value', name: '任务/沟通' },
      { type: 'value', name: '小时', position: 'right' },
    ],
    series: [
      { name: '已完成任务', type: 'bar', data: completed, itemStyle: { color: '#52c41a' } },
      { name: '工作时长(h)', type: 'bar', yAxisIndex: 1, data: workHours, itemStyle: { color: '#722ed1' } },
      { name: '沟通记录', type: 'bar', data: comms, itemStyle: { color: '#faad14' } },
    ],
  })
  window.addEventListener('resize', () => chart.resize())
}

// --- Init ---
async function init() {
  const [boardPayload, ganttPayload, agentsPayload, aggregatePayload, dailyPayload, poolPayload, integrationQueuePayload, pmInboxPayload] = await Promise.all([
    fetchBoard(),
    fetchGantt(),
    fetchAgents(),
    fetchAggregate(),
    fetchDailyMetrics(),
    fetchPool(),
    fetchIntegrationQueue(),
    fetchPmInbox(),
  ])

  document.getElementById('last-update').textContent = `更新: ${new Date().toLocaleTimeString()}`

  renderKanban(boardPayload)
  renderGantt(ganttPayload)
  renderAgentStats(agentsPayload)
  renderAnalytics(aggregatePayload, dailyPayload, agentsPayload)
  renderPoolView(poolPayload)
  renderIntegrationQueueView(integrationQueuePayload)
  renderPmInboxView(pmInboxPayload)
}

if (typeof window !== 'undefined' && typeof document !== 'undefined') {
  bindGanttFilters()
  init()
}

if (typeof module !== 'undefined' && module.exports) {
  module.exports = {
    sortTimelineItems,
    renderTimelineHtml,
    renderTaskDetailHtml,
    detailItem,
    formatHours,
    renderKanban,
    renderKanbanFilters,
    getActiveFilters,
    populateFilterSelect,
    GANTT_PHASES,
    getGanttDateRange,
    getTaskGanttIntervals,
    applyGanttTimeFilter,
    renderAnalytics,
    renderAnalyticsSummary,
    renderTrendChart,
    renderAggregationCharts,
    renderRoleEfficiencyChart,
    renderPoolView,
    renderIntegrationQueueView,
    renderPmInboxView,
  }
}
})()
