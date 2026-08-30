;(function () {
const API = '/api/collaboration'
const doc = typeof document !== 'undefined' ? document : null
const STAGE_GROUPS = [
  { key: 'development', label: '开发中', stages: ['created', 'development', 'unknown'] },
  { key: 'review', label: '审查 / 修复', stages: ['review', 'fix', 'rereview', 'review_approved'] },
  { key: 'merge_gate', label: 'Merge Gate', stages: ['merge_gate', 'merge_ready'] },
  { key: 'blocked', label: '阻塞', stages: ['blocked', 'merge_blocked'] },
  { key: 'done', label: '已合入', stages: ['merged', 'completed'] },
]
const STAGE_LABELS = {
  created: '已创建', development: '开发中', review: '待审', fix: '修复中', rereview: '复审中',
  review_approved: '审查通过', merge_gate: '门禁运行中', merge_ready: '可合入',
  merge_blocked: '门禁阻塞', blocked: '阻塞', merged: '已合入', completed: '已完成', unknown: '未知',
}
const EVENT_LABELS = {
  TASK_CREATED: '任务创建', TASK_STARTED: '开始开发', TASK_PROGRESS: '进展', TASK_BLOCKED: '任务阻塞',
  TASK_COMPLETED: '开发完成', READY_FOR_REVIEW: '提交审查', CHANGES_REQUESTED: '要求修改',
  FIX_READY: '修复待复审', APPROVED: '审查批准', MERGE_GATE_RUNNING: 'Merge Gate 运行',
  MERGE_READY: '允许合入', GATE_BLOCKED: '门禁阻塞', MERGED: '已合入',
  MESSAGE_SENT: '消息已发送', MESSAGE_DELIVERED: '消息已送达', CALLBACK_RECEIVED: '回调已收到',
  ARTIFACT_CREATED: '产物创建', LOCAL_CI_COMPLETED: 'Local CI 完成',
  AUTHORIZATION_REQUESTED: '请求授权', AUTHORIZATION_ROUTED: '授权已路由',
  AUTHORIZATION_GRANTED: '授权已允许', AUTHORIZATION_DENIED: '授权已拒绝',
  AUTHORIZATION_EXPIRED: '授权已过期',
  AUTHORIZATION_PLATFORM_MANUAL_REQUIRED: '平台需人工点击',
  AUTHORIZATION_CONSUMED: '授权已使用',
  INBOX_ROUTED: 'Inbox 已转发', INBOX_ACKED: 'Inbox 已确认', INBOX_ESCALATED: 'Inbox 已升级',
}
const AUTH_LEVELS = {
  L0_AUTO: 'L0 自动', L1_REVIEWER_COORDINATOR: 'L1 委托', L2_OWNER: 'L2 Owner',
}
const INBOX_STATUS_ORDER = ['RECEIVED', 'VALIDATED', 'DEDUPED', 'ROUTED', 'ACKED', 'ESCALATED']

let state = {
  payload: null,
  lastEventId: null,
  knownEventIds: new Set(),
  eventSource: null,
  pollTimer: null,
  reconnectTimer: null,
  refreshTimer: null,
  overviewTimer: null,
}

function esc(value) {
  return String(value == null ? '' : value)
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;').replace(/'/g, '&#039;')
}

function formatTime(value) {
  if (!value) return '-'
  const parsed = new Date(value)
  return Number.isNaN(parsed.getTime()) ? esc(value) : parsed.toLocaleString('zh-CN', { hour12: false })
}

function formatDuration(seconds) {
  if (seconds == null || Number.isNaN(Number(seconds))) return '-'
  const total = Math.max(0, Math.round(Number(seconds)))
  if (total < 60) return `${total} 秒`
  const minutes = Math.floor(total / 60)
  if (minutes < 60) return `${minutes} 分钟`
  const hours = Math.floor(minutes / 60)
  const rest = minutes % 60
  return `${hours} 小时${rest ? ` ${rest} 分` : ''}`
}

function summarizeRevision(revision) {
  revision = revision || {}
  const pr = revision.pr_number ? `PR #${revision.pr_number}` : '无 PR'
  const head = revision.head_sha ? String(revision.head_sha).slice(0, 8) : '无 HEAD'
  const mergeable = revision.mergeable === true ? 'mergeable' : revision.mergeable === false ? '不可合入' : '未确认'
  return `${pr} · ${head} · ${mergeable}`
}

function buildQuery(filters, afterEventId) {
  const params = new URLSearchParams()
  Object.entries(filters || {}).forEach(([key, value]) => { if (value) params.set(key, value) })
  if (afterEventId) params.set('after_event_id', afterEventId)
  const query = params.toString()
  return query ? `?${query}` : ''
}

function groupTasks(tasks) {
  const result = Object.fromEntries(STAGE_GROUPS.map(group => [group.key, []]))
  ;(tasks || []).forEach(task => {
    const group = STAGE_GROUPS.find(item => item.stages.includes(task.stage)) || STAGE_GROUPS[0]
    result[group.key].push(task)
  })
  return result
}

function mergeTaskEventsById(knownIds, events) {
  const added = []
  ;(events || []).forEach(event => {
    if (!event || !event.event_id || knownIds.has(event.event_id)) return
    knownIds.add(event.event_id)
    added.push(event)
  })
  return added
}

function authorizationActions(item, role) {
  if (!item || item.status !== 'PENDING') return { allow: false, deny: false }
  if (item.authorization_kind === 'codex_platform' || item.capability_status === 'platform_manual_required') {
    return { allow: role === 'owner', deny: role === 'owner', platformManual: true }
  }
  if (item.authorization_level === 'L1_REVIEWER_COORDINATOR') {
    return { allow: ['reviewer', 'coordinator', 'owner'].includes(role), deny: ['reviewer', 'coordinator', 'owner'].includes(role) }
  }
  if (item.authorization_level === 'L2_OWNER') return { allow: role === 'owner', deny: role === 'owner' }
  return { allow: false, deny: false }
}

function inboxStatusTrace(item) {
  const route = String(item?.route_status || '').toUpperCase()
  return INBOX_STATUS_ORDER.map(status => {
    const active = status === 'RECEIVED'
      || status === 'VALIDATED'
      || status === 'DEDUPED'
      || (route === 'ROUTED' && status === 'ROUTED')
      || (route === 'ACKED' && ['ROUTED', 'ACKED'].includes(status))
      || (route === 'ESCALATED' && status === 'ESCALATED')
    return `<span class="collab-trace-chip ${active ? 'is-active' : ''}">${esc(status)}</span>`
  }).join('')
}

function summarizeInboxItem(item) {
  const target = item?.target_task_id ? ` → ${item.target_task_id}` : ''
  return `${EVENT_LABELS[item?.event_type] || item?.event_type || '事件'} · ${item?.task_id || '-'}${target}`
}

function currentFilters() {
  if (!doc) return {}
  return {
    project: doc.getElementById('collab-filter-project')?.value || '',
    role: doc.getElementById('collab-filter-role')?.value || '',
    status: doc.getElementById('collab-filter-status')?.value || '',
    pr: doc.getElementById('collab-filter-pr')?.value || '',
    risk: doc.getElementById('collab-filter-risk')?.value || '',
  }
}

async function fetchJson(url, options) {
  const response = await fetch(url, options)
  const payload = await response.json().catch(() => ({}))
  if (!response.ok) throw new Error(payload?.error?.message || `HTTP ${response.status}`)
  return payload
}

function populateSelect(id, values, label) {
  const select = doc?.getElementById(id)
  if (!select) return
  const current = select.value
  select.innerHTML = `<option value="">${esc(label)}</option>` + (values || []).map(value => `<option value="${esc(value)}">${esc(STAGE_LABELS[value] || value)}</option>`).join('')
  if ((values || []).includes(current)) select.value = current
}

function renderSummary(summary) {
  const root = doc?.getElementById('collab-summary')
  if (!root) return
  const taskCount = doc.getElementById('task-count')
  if (taskCount) {
    taskCount.dataset.collaborationCount = String(Number(summary?.task_count || 0))
    if (doc.getElementById('collaboration')?.classList.contains('active')) {
      taskCount.textContent = `共 ${Number(summary?.task_count || 0)} 个任务`
    }
  }
  const cards = [
    ['task_count', '任务', ''], ['running_count', '运行中', ''], ['review_count', '待审 / 复审', ''],
    ['blocked_count', '阻塞', 'is-alert'], ['merge_ready_count', '可合入', 'is-ready'],
    ['stuck_count', '卡住', 'is-alert'], ['pending_authorization_count', '待授权', ''],
    ['pending_event_count', '待处理事件', ''], ['human_decision_count', '待人工决定', 'is-alert'],
  ]
  root.innerHTML = cards.map(([key, label, cls]) => `
    <div class="collab-summary-card ${cls}"><div class="collab-summary-value">${Number(summary?.[key] || 0)}</div><div class="collab-summary-label">${label}</div></div>
  `).join('')
}

function chip(text, kind) { return `<span class="collab-chip ${kind || ''}">${esc(text)}</span>` }

function renderBoard(tasks) {
  const root = doc?.getElementById('collab-board')
  if (!root) return
  const grouped = groupTasks(tasks)
  root.innerHTML = STAGE_GROUPS.map(group => {
    const cards = grouped[group.key].map(task => {
      const reviewType = task.review?.event_type
      const ciGood = task.local_ci?.fresh
      const gateGood = task.merge_gate?.allowed
      const auth = Number(task.authorization_pending || 0)
      const agents = (task.agents || []).map(item => `${item.role || 'agent'}:${item.agent_id || '-'}`).join(' · ')
      return `<button type="button" class="collab-task risk-${esc(task.risk_level)} ${task.stuck ? 'is-stuck' : ''}" data-project="${esc(task.project_id)}" data-task="${esc(task.task_id)}">
        <div class="collab-task-title">${esc(task.title)}</div>
        <div class="collab-task-meta">${esc(task.project_name)} · ${esc(STAGE_LABELS[task.stage] || task.stage)}</div>
        <div class="collab-task-meta">${esc(agents || '暂无 Agent 绑定')}</div>
        <div class="collab-task-meta">${esc(summarizeRevision(task.revision))}</div>
        <div class="collab-chip-row">
          ${chip(reviewType === 'APPROVED' ? '审查通过' : reviewType === 'CHANGES_REQUESTED' ? '需修改' : '待审查', reviewType === 'APPROVED' ? 'is-good' : 'is-warn')}
          ${chip(ciGood ? 'CI 新鲜' : 'CI 缺失/过期', ciGood ? 'is-good' : 'is-warn')}
          ${chip(gateGood ? '可合入' : '门禁未就绪', gateGood ? 'is-good' : 'is-bad')}
          ${task.stuck ? chip('卡住', 'is-bad') : ''}${auth ? chip(`待授权 ${auth}`, 'is-warn') : ''}
        </div>
      </button>`
    }).join('') || '<div class="collab-empty">暂无任务</div>'
    return `<div class="collab-column"><div class="collab-column-heading"><span>${group.label}</span><span class="collab-column-count">${grouped[group.key].length}</span></div>${cards}</div>`
  }).join('')
  root.querySelectorAll('[data-task]').forEach(button => button.addEventListener('click', () => openDetail(button.dataset.project, button.dataset.task)))
}

function renderBottlenecks(payload) {
  const root = doc?.getElementById('collab-bottlenecks')
  if (!root) return
  const stuck = payload?.bottlenecks?.stuck_tasks || []
  const stages = Object.entries(payload?.bottlenecks?.by_stage || {}).map(([name, count]) => chip(`${STAGE_LABELS[name] || name} ${count}`)).join('')
  const waiting = Number(payload?.bottlenecks?.dependency_wait_count || 0)
  root.innerHTML = `<div class="collab-chip-row" style="margin-bottom:12px">${stages}${chip(`依赖等待 ${waiting}`, waiting ? 'is-warn' : '')}</div>` + (stuck.map(item => `
    <div class="collab-stuck-item"><div class="collab-stuck-title">${esc(item.title)} · ${esc(item.task_id)}</div><div class="collab-stuck-reason">${(item.reasons || []).map(esc).join('；')}</div><div class="collab-event-meta"><span>最后活动 ${formatTime(item.facts?.last_activity_at)}</span><span>已等待 ${formatDuration(item.facts?.age_seconds)}</span></div></div>
  `).join('') || '<div class="collab-empty">当前没有命中卡住规则的任务</div>')
}

function renderEvents(events) {
  const root = doc?.getElementById('collab-events')
  if (!root) return
  root.innerHTML = (events || []).map(event => {
    const payload = event.payload || {}
    return `<div class="collab-event-item"><div class="collab-event-title">${esc(EVENT_LABELS[payload.event_type] || payload.event_type)} · ${esc(payload.task_id)}</div><div class="collab-event-summary">${esc(payload.summary || '仅记录状态与引用')}</div><div class="collab-event-meta"><span>${esc(payload.actor?.role || '')} / ${esc(payload.actor?.id || '')}</span><span>${formatTime(payload.created_at)}</span></div>${event.rejection_reason ? `<div class="collab-chip-row">${chip(event.rejection_reason, 'is-bad')}</div>` : ''}</div>`
  }).join('') || '<div class="collab-empty">暂无规范事件</div>'
}

function renderFocus(focus) {
  const root = doc?.getElementById('collab-focus')
  if (!root) return
  if (!focus?.active) {
    root.innerHTML = '<div class="collab-empty">当前没有专注租约，非 immediate 事件可直接排空。</div>'
    return
  }
  const lease = focus.lease || {}
  root.innerHTML = `<div class="collab-focus-card">
    <div class="collab-focus-main">
      <div class="collab-focus-title">当前专注 ${esc(lease.focus_task_id || lease.operation || lease.scope_id || 'main')}</div>
      <div class="collab-focus-meta">操作 ${esc(lease.operation || '-')} · HEAD ${esc(lease.head_sha ? String(lease.head_sha).slice(0, 12) : '未绑定')} · ${lease.critical_section ? 'Critical Section' : '非关键区'}</div>
    </div>
    <div class="collab-focus-side">
      <div>下个安全检查点 ${esc(lease.next_safe_checkpoint || '-')}</div>
      <div>过期时间 ${formatTime(lease.expires_at)}</div>
    </div>
  </div>`
}

function renderInboxSummary(summary) {
  const root = doc?.getElementById('collab-inbox-summary')
  if (!root) return
  root.innerHTML = [
    chip(`待处理 ${Number(summary?.pending_count || 0)}`, Number(summary?.pending_count || 0) ? 'is-warn' : ''),
    chip(`最高优先级 ${summary?.highest_priority || 'P3'}`, summary?.highest_priority === 'P0' ? 'is-bad' : summary?.highest_priority === 'P1' ? 'is-warn' : ''),
    chip(`最老等待 ${formatDuration(summary?.oldest_wait_seconds)}`, Number(summary?.oldest_wait_seconds || 0) > 0 ? 'is-warn' : ''),
    chip(`需人工 ${Number(summary?.human_required_count || 0)}`, Number(summary?.human_required_count || 0) ? 'is-bad' : ''),
  ].join('')
}

function renderInboxList(id, items, empty) {
  const root = doc?.getElementById(id)
  if (!root) return
  root.innerHTML = (items || []).map(item => `<div class="collab-event-item">
    <div class="collab-event-title">${esc(summarizeInboxItem(item))}</div>
    <div class="collab-event-summary">${esc(item.route_reason || item.summary || '仅记录摘要与路由决定')}</div>
    <div class="collab-event-meta"><span>${esc(item.priority || 'P3')} / ${esc(item.route_status || '-')}</span><span>${formatTime(item.updated_at || item.received_at || item.occurred_at)}</span></div>
    <div class="collab-chip-row">${inboxStatusTrace(item)}</div>
  </div>`).join('') || `<div class="collab-empty">${esc(empty)}</div>`
}

function renderInboxTrace(items) {
  const root = doc?.getElementById('collab-inbox-trace')
  if (!root) return
  root.innerHTML = (items || []).map(item => `<div class="collab-event-item">
    <div class="collab-event-title">${esc(summarizeInboxItem(item))}</div>
    <div class="collab-event-summary">${esc(item.summary || item.route_reason || '仅记录安全投影')}</div>
    <div class="collab-chip-row">${inboxStatusTrace(item)}</div>
    <div class="collab-event-meta"><span>${esc(item.classification || '-')} / ${esc(item.requires_human ? 'requires_human' : 'auto')}</span><span>${formatTime(item.received_at || item.occurred_at)}</span></div>
  </div>`).join('') || '<div class="collab-empty">暂无 Inbox 审计轨迹</div>'
}

function renderTopology(topology) {
  const root = doc?.getElementById('collab-topology')
  if (!root) return
  if (!topology?.nodes?.length) { root.innerHTML = '<div class="collab-empty">暂无拓扑数据</div>'; return }
  if (typeof echarts === 'undefined') { root.innerHTML = `<div class="collab-empty">${topology.nodes.length} 个节点，${topology.edges.length} 条边</div>`; return }
  const chart = echarts.getInstanceByDom(root) || echarts.init(root, 'dark')
  const categories = [{ name: '项目' }, { name: '需求' }, { name: '任务' }, { name: 'Agent' }]
  const category = { project: 0, requirement: 1, task: 2, agent: 3 }
  const colors = ['#60a5fa', '#a78bfa', '#22d3ee', '#34d399']
  chart.setOption({
    backgroundColor: 'transparent', tooltip: { formatter: params => esc(params.data?.label || params.data?.name || '') },
    legend: [{ data: categories.map(item => item.name), textStyle: { color: '#9db4d1' } }],
    series: [{ type: 'graph', layout: 'force', roam: true, categories,
      force: { repulsion: 260, edgeLength: [60, 150] }, label: { show: true, color: '#dff8ff', fontSize: 10 },
      data: topology.nodes.map(node => ({ id: node.id, name: node.label, label: node.label, category: category[node.kind] ?? 2, symbolSize: node.kind === 'task' ? 42 : 30, itemStyle: { color: node.stuck ? '#fb7185' : colors[category[node.kind] ?? 2] } })),
      links: topology.edges.map(edge => ({ source: edge.source, target: edge.target, value: edge.kind, lineStyle: { color: edge.kind === 'depends_on' ? '#fbbf24' : '#44647e', curveness: edge.kind === 'depends_on' ? .12 : 0 } })),
      emphasis: { focus: 'adjacency' }, edgeSymbol: ['none', 'arrow'], edgeSymbolSize: 6,
    }],
  })
}

function renderTimeline(items) {
  const root = doc?.getElementById('collab-timeline')
  if (!root) return
  const rows = (items || []).filter(item => item.started_at)
  if (!rows.length) { root.innerHTML = '<div class="collab-empty">暂无执行区间</div>'; return }
  if (typeof echarts === 'undefined') { root.innerHTML = rows.map(item => `<div class="collab-stuck-item">${esc(item.title)} · ${formatTime(item.started_at)}</div>`).join(''); return }
  const chart = echarts.getInstanceByDom(root) || echarts.init(root, 'dark')
  const stageColors = { development: '#22d3ee', review: '#a78bfa', fix: '#fb7185', rereview: '#fbbf24', review_approved: '#34d399', merge_gate: '#60a5fa', merge_ready: '#34d399', blocked: '#fb7185', merge_blocked: '#fb7185' }
  const now = Date.now()
  const data = []
  rows.forEach((item, rowIndex) => (item.segments || []).forEach(segment => {
    const start = new Date(segment.started_at).getTime()
    const end = segment.ended_at ? new Date(segment.ended_at).getTime() : now
    if (Number.isFinite(start) && Number.isFinite(end)) data.push({ value: [rowIndex, start, Math.max(start + 1000, end), segment.stage], itemStyle: { color: stageColors[segment.stage] || '#64748b' } })
  }))
  chart.setOption({
    backgroundColor: 'transparent', grid: { left: 120, right: 24, top: 28, bottom: 45 },
    tooltip: { formatter: params => `${esc(STAGE_LABELS[params.value[3]] || params.value[3])}<br>${new Date(params.value[1]).toLocaleString()} → ${new Date(params.value[2]).toLocaleString()}` },
    xAxis: { type: 'time', axisLabel: { color: '#7d90ad' }, splitLine: { lineStyle: { color: 'rgba(125,211,252,.08)' } } },
    yAxis: { type: 'category', data: rows.map(item => item.title), axisLabel: { color: '#9db4d1', width: 105, overflow: 'truncate' } },
    dataZoom: [{ type: 'inside' }, { type: 'slider', height: 16, bottom: 5 }],
    series: [{ type: 'custom', data, encode: { x: [1, 2], y: 0 }, renderItem(params, api) {
      const categoryIndex = api.value(0); const start = api.coord([api.value(1), categoryIndex]); const end = api.coord([api.value(2), categoryIndex]);
      const height = Math.min(16, api.size([0, 1])[1] * .55)
      return { type: 'rect', shape: { x: start[0], y: start[1] - height / 2, width: Math.max(2, end[0] - start[0]), height, r: 4 }, style: api.style() }
    }}],
  })
}

function renderAuthorizations(items) {
  const body = doc?.getElementById('collab-auth-body')
  if (!body) return
  const role = doc.getElementById('collab-approver-role')?.value || 'owner'
  body.innerHTML = (items || []).map(item => {
    const actions = authorizationActions(item, role)
    const targets = (item.exact_targets || []).map(target => `<span class="collab-auth-target">${esc(target)}</span>`).join('')
    const manualPlatform = item.authorization_kind === 'codex_platform' || item.capability_status === 'platform_manual_required'
    return `<tr><td>${chip(AUTH_LEVELS[item.authorization_level] || item.authorization_level, item.authorization_level === 'L2_OWNER' ? 'is-bad' : item.authorization_level === 'L1_REVIEWER_COORDINATOR' ? 'is-warn' : 'is-good')}<div class="collab-muted">${esc(item.status)}</div></td>
      <td><strong>${esc(item.action || '未知操作')}</strong><div class="collab-muted">${esc(item.request_id)} · ${esc(item.requester?.id || '')}</div><div class="collab-muted">有效期至 ${formatTime(item.expires_at)}</div></td>
      <td><div>${esc(item.environment)} / ${esc(item.target_scope)}</div><div class="collab-auth-targets">${targets || '<span class="collab-muted">缺少精确目标</span>'}</div><div class="collab-muted">HEAD ${esc(item.head_sha ? String(item.head_sha).slice(0, 12) : '未绑定')} · digest ${esc(item.command_or_action_digest ? String(item.command_or_action_digest).slice(0, 12) : '-')}</div></td>
      <td>${esc(item.routing_reason || '')}<div class="collab-muted">${esc(item.policy_version || '')} · ${esc(item.matched_rule_id || '默认 fail-closed')}</div><div class="collab-muted">${manualPlatform ? 'Codex 原生 sandbox/tool approval 仍需平台人工点击' : esc(item.authorization_kind || 'text')}</div></td>
      <td>${manualPlatform && actions.allow ? `<button class="collab-action allow" data-auth-platform="${esc(item.request_id)}" data-digest="${esc(item.command_or_action_digest || '')}" data-decision="GRANT">记录平台已允许</button><button class="collab-action deny" data-auth-platform="${esc(item.request_id)}" data-digest="${esc(item.command_or_action_digest || '')}" data-decision="DENY">记录平台已拒绝</button>` : actions.allow ? `<button class="collab-action allow" data-auth="${esc(item.request_id)}" data-decision="GRANT">允许</button>` : ''}${!manualPlatform && actions.deny ? `<button class="collab-action deny" data-auth="${esc(item.request_id)}" data-decision="DENY">拒绝</button>` : ''}${manualPlatform && !actions.allow ? '<span class="collab-muted">仅 Owner 可记录平台点击结果</span>' : (!manualPlatform && !actions.allow && !actions.deny ? '<span class="collab-muted">不可由当前角色处理</span>' : '')}</td></tr>`
  }).join('') || '<tr><td colspan="5" class="collab-empty">暂无授权请求</td></tr>'
  body.querySelectorAll('[data-auth]').forEach(button => button.addEventListener('click', () => decideAuthorization(button.dataset.auth, button.dataset.decision)))
  body.querySelectorAll('[data-auth-platform]').forEach(button => button.addEventListener('click', () => recordPlatformDecision(button.dataset.authPlatform, button.dataset.decision, button.dataset.digest)))
}

function renderPolicy(policy) {
  const root = doc?.getElementById('collab-policy-rules')
  if (!root) return
  root.innerHTML = (policy?.rules || []).map(rule => `<label class="collab-policy-rule"><input type="checkbox" data-policy-rule="${esc(rule.rule_id)}" ${rule.enabled ? 'checked' : ''}><span><strong>${esc(AUTH_LEVELS[rule.level] || rule.level)} · ${esc(rule.action)}</strong><p>${esc(rule.description)}</p><p>${esc(rule.environments.join(', '))} / ${esc(rule.target_scopes.join(', '))}</p></span></label>`).join('')
  root.querySelectorAll('[data-policy-rule]').forEach(input => input.addEventListener('change', () => updatePolicy(input.dataset.policyRule, input.checked)))
}

function detailRow(label, value) { return `<div class="collab-detail-row"><span>${esc(label)}</span><span>${value == null || value === '' ? '-' : esc(value)}</span></div>` }

function renderTaskDetailHtml(payload) {
  const task = payload.task || {}
  const revision = task.revision || {}
  const review = payload.review || {}
  const ci = payload.local_ci || {}
  const gate = payload.merge_gate || {}
  const findings = review.finding_counts || {}
  const messages = (payload.messages || []).map(item => `<div class="collab-stuck-item"><div class="collab-stuck-title">${esc(item.delivery_id)} · ${esc(item.status)}</div><div class="collab-stuck-reason">${esc(item.summary || '仅保留摘要与 ACK 元数据')}</div><div class="collab-event-meta"><span>ACK ${esc(item.ack_id || '-')}</span><span>Callback ${esc(item.callback_id || '-')}</span></div></div>`).join('') || '<div class="collab-empty">暂无消息投递记录</div>'
  const artifacts = (payload.artifacts || []).map(item => `<div class="collab-stuck-item"><div class="collab-stuck-title">${esc(item.kind)} · ${esc(item.summary || item.artifact_id || '')}</div><div class="collab-stuck-reason">${/^https?:\/\//.test(String(item.uri || '')) ? `<a class="collab-link" href="${esc(item.uri)}" target="_blank" rel="noreferrer">${esc(item.uri)}</a>` : esc(item.uri || '-')}</div></div>`).join('') || '<div class="collab-empty">暂无产物引用</div>'
  const trace = (payload.events || []).map(item => `<div class="collab-trace-item"><strong>${esc(EVENT_LABELS[item.event_type] || item.event_type)} · ${formatTime(item.created_at)}</strong><p>${esc(item.summary || '仅记录状态与引用')}</p>${item.rejection_reason ? chip(item.rejection_reason, 'is-bad') : ''}</div>`).join('') || '<div class="collab-empty">暂无事件</div>'
  const auth = (payload.authorizations || []).map(item => `<div class="collab-stuck-item"><div class="collab-stuck-title">${esc(AUTH_LEVELS[item.authorization_level] || item.authorization_level)} · ${esc(item.action)} · ${esc(item.status)}</div><div class="collab-stuck-reason">${esc(item.routing_reason || '')}</div><div class="collab-event-meta"><span>${esc(item.authorization_kind || 'text')}</span><span>${esc(item.capability_status || 'text_route_available')}</span></div></div>`).join('') || '<div class="collab-empty">暂无授权请求</div>'
  const inbox = (payload.inbox || []).map(item => `<div class="collab-stuck-item"><div class="collab-stuck-title">${esc(summarizeInboxItem(item))}</div><div class="collab-stuck-reason">${esc(item.route_reason || item.summary || '仅记录状态与引用')}</div><div class="collab-chip-row">${inboxStatusTrace(item)}</div></div>`).join('') || '<div class="collab-empty">暂无 Inbox 记录</div>'
  return `<div class="collab-detail-grid">
    <section class="collab-detail-card"><h3>当前状态</h3>${detailRow('项目 / 任务', `${task.project_id} / ${task.task_id}`)}${detailRow('阶段', STAGE_LABELS[task.stage] || task.stage)}${detailRow('运行状态', task.runtime_status)}${detailRow('开始', formatTime(task.started_at))}${detailRow('完成', formatTime(task.completed_at))}${detailRow('耗时', formatDuration(task.duration_seconds))}${detailRow('最后活动', formatTime(task.last_activity_at))}</section>
    <section class="collab-detail-card"><h3>PR / 冻结身份</h3>${detailRow('PR', revision.pr_number ? `#${revision.pr_number} ${revision.pr_state || ''}` : '-')}${detailRow('源分支', revision.source_branch)}${detailRow('HEAD', revision.head_sha)}${detailRow('Base', revision.base_sha || revision.base_branch)}${detailRow('Merge Base', revision.merge_base_sha)}${detailRow('Mergeable', revision.mergeable === true ? '是' : revision.mergeable === false ? '否' : '未知')}</section>
    <section class="collab-detail-card"><h3>独立审查</h3>${detailRow('结论', review.event_type ? EVENT_LABELS[review.event_type] : '未审')}${detailRow('批准人', review.approver)}${detailRow('P0 / P1 / P2', `${findings.P0 || 0} / ${findings.P1 || 0} / ${findings.P2 || 0}`)}${detailRow('时间', formatTime(review.event_at))}</section>
    <section class="collab-detail-card"><h3>Local CI / Merge Gate</h3>${detailRow('run_id', ci.run_id)}${detailRow('CI 状态', ci.status)}${detailRow('CI 新鲜', ci.fresh ? '是（24h 内）' : '否')}${detailRow('证据', ci.evidence_uri)}${detailRow('Gate', gate.event_type ? EVENT_LABELS[gate.event_type] : gate.state)}${detailRow('允许执行', gate.allowed ? '是' : '否')}${detailRow('阻断', (gate.blocking_checks || []).join('；'))}</section>
  </div>
  <section class="collab-detail-card"><h3>消息投递 / ACK / 回调</h3>${messages}</section>
  <section class="collab-detail-card"><h3>产物、报告与截图引用</h3>${artifacts}</section>
  <section class="collab-detail-card"><h3>分层授权</h3>${auth}</section>
  <section class="collab-detail-card"><h3>Inbox 路由 / ACK 轨迹</h3>${inbox}</section>
  <section class="collab-detail-card"><h3>状态时间线</h3><div class="collab-trace">${trace}</div></section>
  <div class="collab-boundary">隐私投影：${esc(payload.privacy?.projection || '')}；默认排除 ${(payload.privacy?.excluded || []).map(esc).join('、')}。</div>`
}

async function openDetail(projectId, taskId) {
  const drawer = doc?.getElementById('collab-detail-drawer'); const backdrop = doc?.getElementById('collab-detail-backdrop'); const body = doc?.getElementById('collab-detail-body')
  if (!drawer || !backdrop || !body) return
  drawer.classList.remove('hidden'); backdrop.classList.remove('hidden'); drawer.setAttribute('aria-hidden', 'false')
  doc.getElementById('collab-detail-title').textContent = taskId
  doc.getElementById('collab-detail-subtitle').textContent = `${projectId} · 安全投影`
  body.innerHTML = '<div class="collab-empty">加载中...</div>'
  try { body.innerHTML = renderTaskDetailHtml(await fetchJson(`${API}/tasks/${encodeURIComponent(taskId)}?project=${encodeURIComponent(projectId)}`)) }
  catch (error) { body.innerHTML = `<div class="collab-alert">${esc(error.message)}</div>` }
}

function closeDetail() {
  doc?.getElementById('collab-detail-drawer')?.classList.add('hidden'); doc?.getElementById('collab-detail-backdrop')?.classList.add('hidden'); doc?.getElementById('collab-detail-drawer')?.setAttribute('aria-hidden', 'true')
}

async function decideAuthorization(requestId, decision) {
  const approverId = doc.getElementById('collab-approver-id')?.value.trim()
  const role = doc.getElementById('collab-approver-role')?.value
  const reason = typeof window !== 'undefined' ? window.prompt(decision === 'GRANT' ? '请填写允许理由' : '请填写拒绝理由', '') : ''
  if (reason == null) return
  try {
    await fetchJson(`${API}/authorizations/${encodeURIComponent(requestId)}/decision`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ decision, approver: { id: approverId || role, role }, reason }) })
    await refreshOverview()
  } catch (error) { showAlert(error.message) }
}

async function recordPlatformDecision(requestId, decision, observedDigest) {
  const approverId = doc.getElementById('collab-approver-id')?.value.trim()
  const role = doc.getElementById('collab-approver-role')?.value
  const reason = typeof window !== 'undefined' ? window.prompt(decision === 'GRANT' ? '请填写平台已允许的记录说明' : '请填写平台已拒绝的记录说明', '') : ''
  if (reason == null) return
  try {
    await fetchJson(`${API}/authorizations/${encodeURIComponent(requestId)}/platform-decision`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ decision, approver: { id: approverId || role, role }, reason, observed_digest: observedDigest }) })
    await refreshOverview()
  } catch (error) { showAlert(error.message) }
}

async function updatePolicy(ruleId, enabled) {
  const ownerId = doc.getElementById('collab-approver-id')?.value.trim() || 'owner'
  try {
    const policy = await fetchJson(`${API}/authorization-policy/${encodeURIComponent(ruleId)}`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ enabled, actor: { id: ownerId, role: 'owner' } }) })
    renderPolicy(policy)
  } catch (error) { showAlert(error.message); await loadPolicy() }
}

function showAlert(message) {
  const root = doc?.getElementById('collab-alert'); if (!root) return
  root.textContent = message; root.classList.remove('hidden')
  setTimeout(() => root.classList.add('hidden'), 6000)
}

function render(payload) {
  state.payload = payload
  renderSummary(payload.summary)
  renderBoard(payload.tasks)
  renderTopology(payload.topology)
  renderTimeline(payload.timeline)
  renderBottlenecks(payload)
  renderEvents(payload.recent_events)
  renderAuthorizations(payload.authorizations)
  renderFocus(payload.inbox?.focus)
  renderInboxSummary(payload.inbox?.summary)
  renderInboxList('collab-human-decisions', payload.inbox?.human_decisions, '当前没有等待人工决定的事件')
  renderInboxList('collab-auto-forwarded', payload.inbox?.auto_forwarded, '当前没有自动转发事件')
  renderInboxTrace(payload.inbox?.items)
  const source = doc?.getElementById('collab-source-freshness')
  if (source) source.textContent = `事实源：SQLite · 最近活动 ${formatTime(payload.source?.freshness)}`
  populateSelect('collab-filter-project', payload.filters?.projects, '全部项目')
  populateSelect('collab-filter-role', payload.filters?.roles, '全部角色')
  populateSelect('collab-filter-status', payload.filters?.statuses, '全部状态')
  populateSelect('collab-filter-risk', payload.filters?.risks, '全部风险')
  mergeTaskEventsById(state.knownEventIds, payload.recent_events)
  if (!state.lastEventId && payload.recent_events?.length) state.lastEventId = payload.recent_events[0].event_id
}

async function refreshOverview() {
  try { render(await fetchJson(`${API}/overview${buildQuery(currentFilters())}`)) }
  catch (error) { showAlert(`协作看板加载失败：${error.message}`); setRealtime('error', '数据加载失败') }
}

async function loadPolicy() {
  try { renderPolicy(await fetchJson(`${API}/authorization-policy`)) }
  catch (error) { showAlert(`授权策略加载失败：${error.message}`) }
}

function setRealtime(mode, label) {
  const badge = doc?.getElementById('collab-live'); if (!badge) return
  badge.className = `collab-live is-${mode}`; badge.textContent = label
}

function scheduleRefresh() {
  clearTimeout(state.refreshTimer)
  state.refreshTimer = setTimeout(refreshOverview, 250)
}

function stopPolling() { if (state.pollTimer) clearInterval(state.pollTimer); state.pollTimer = null }
function stopSse() { if (state.eventSource) state.eventSource.close(); state.eventSource = null }

async function pollOnce() {
  try {
    const filters = currentFilters(); const query = buildQuery({ project: filters.project }, state.lastEventId)
    const payload = await fetchJson(`${API}/event-log${query}`)
    if (payload.cursor_reset) state.lastEventId = null
    const added = mergeTaskEventsById(state.knownEventIds, payload.events)
    if (payload.last_event_id) state.lastEventId = payload.last_event_id
    if (added.length) scheduleRefresh()
    else await refreshOverview()
    setRealtime('polling', 'SSE 断开 · 增量轮询中')
  } catch (error) { setRealtime('error', '实时更新不可用'); showAlert(error.message) }
}

function startPolling() {
  stopPolling(); pollOnce(); state.pollTimer = setInterval(pollOnce, 4000)
  clearTimeout(state.reconnectTimer); state.reconnectTimer = setTimeout(connectSse, 30000)
}

function connectSse() {
  if (!doc || typeof EventSource === 'undefined') { startPolling(); return }
  stopSse(); stopPolling(); clearTimeout(state.reconnectTimer)
  setRealtime('connecting', '正在连接实时事件')
  const filters = currentFilters(); const source = new EventSource(`${API}/events${buildQuery({ project: filters.project }, state.lastEventId)}`)
  state.eventSource = source
  source.onopen = () => setRealtime('live', 'SSE 实时更新')
  source.addEventListener('agent_event', event => {
    state.lastEventId = event.lastEventId || state.lastEventId
    try { if (mergeTaskEventsById(state.knownEventIds, [JSON.parse(event.data)]).length) scheduleRefresh() } catch (_) {}
  })
  source.addEventListener('cursor_reset', () => { state.lastEventId = null; state.knownEventIds.clear(); scheduleRefresh() })
  source.onerror = () => { stopSse(); startPolling() }
}

function resetFilters() {
  ['collab-filter-project', 'collab-filter-role', 'collab-filter-status', 'collab-filter-pr', 'collab-filter-risk'].forEach(id => { const element = doc.getElementById(id); if (element) element.value = '' })
  state.lastEventId = null; state.knownEventIds.clear(); refreshOverview(); connectSse()
}

function bind() {
  if (!doc?.getElementById('collaboration')) return
  doc.getElementById('collab-refresh')?.addEventListener('click', refreshOverview)
  doc.getElementById('collab-filter-reset')?.addEventListener('click', resetFilters)
  ;['collab-filter-project', 'collab-filter-role', 'collab-filter-status', 'collab-filter-pr', 'collab-filter-risk'].forEach(id => doc.getElementById(id)?.addEventListener('change', () => { state.lastEventId = null; state.knownEventIds.clear(); refreshOverview(); connectSse() }))
  doc.getElementById('collab-approver-role')?.addEventListener('change', () => renderAuthorizations(state.payload?.authorizations || []))
  doc.getElementById('collab-detail-close')?.addEventListener('click', closeDetail)
  doc.getElementById('collab-detail-backdrop')?.addEventListener('click', closeDetail)
  window.addEventListener('resize', () => { ['collab-topology', 'collab-timeline'].forEach(id => { const element = doc.getElementById(id); if (element && typeof echarts !== 'undefined') echarts.getInstanceByDom(element)?.resize() }) })
  refreshOverview(); loadPolicy(); connectSse()
  clearInterval(state.overviewTimer); state.overviewTimer = setInterval(refreshOverview, 10000)
}

if (typeof window !== 'undefined' && doc) bind()
if (typeof module !== 'undefined' && module.exports) module.exports = { buildQuery, groupTasks, summarizeRevision, authorizationActions, mergeTaskEventsById, formatDuration, renderTaskDetailHtml, STAGE_GROUPS, inboxStatusTrace, summarizeInboxItem }
})()
