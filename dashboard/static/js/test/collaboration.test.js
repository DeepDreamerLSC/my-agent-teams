const {
  buildQuery,
  groupTasks,
  summarizeRevision,
  authorizationActions,
  mergeTaskEventsById,
  formatDuration,
  renderTaskDetailHtml,
  inboxStatusTrace,
  summarizeInboxItem,
  STAGE_GROUPS,
} = require('../collaboration')

const assert = (condition, message) => { if (!condition) throw new Error(`FAIL: ${message}`) }
const equal = (actual, expected, message) => assert(actual === expected, `${message}: expected ${expected}, got ${actual}`)

function runTests() {
  let passed = 0
  let failed = 0
  function test(name, fn) {
    try { fn(); passed++; console.log(`  ✓ ${name}`) }
    catch (error) { failed++; console.log(`  ✗ ${name}: ${error.message}`) }
  }

  console.log('\ncollaboration.js tests:')

  test('groups the five collaboration flow columns', () => {
    const grouped = groupTasks([
      { task_id: 'dev', stage: 'development' },
      { task_id: 'review', stage: 'rereview' },
      { task_id: 'gate', stage: 'merge_ready' },
      { task_id: 'blocked', stage: 'merge_blocked' },
      { task_id: 'done', stage: 'merged' },
    ])
    equal(STAGE_GROUPS.length, 5, 'five groups')
    equal(grouped.development[0].task_id, 'dev', 'development')
    equal(grouped.review[0].task_id, 'review', 'rereview')
    equal(grouped.merge_gate[0].task_id, 'gate', 'merge gate')
    equal(grouped.blocked[0].task_id, 'blocked', 'blocked')
    equal(grouped.done[0].task_id, 'done', 'done')
  })

  test('builds scoped polling and SSE cursor queries', () => {
    const query = buildQuery({ project: 'alpha', role: 'reviewer', empty: '' }, 'evt-42')
    assert(query.includes('project=alpha'), 'project filter')
    assert(query.includes('role=reviewer'), 'role filter')
    assert(query.includes('after_event_id=evt-42'), 'event cursor')
    assert(!query.includes('empty='), 'empty filter excluded')
  })

  test('deduplicates reconnected event batches by event_id', () => {
    const known = new Set(['evt-1'])
    const added = mergeTaskEventsById(known, [{ event_id: 'evt-1' }, { event_id: 'evt-2' }])
    equal(added.length, 1, 'one added')
    equal(added[0].event_id, 'evt-2', 'new event retained')
    equal(known.size, 2, 'cursor set updated')
  })

  test('enforces delegated authorization roles in the UI affordance', () => {
    const l1 = { status: 'PENDING', authorization_level: 'L1_REVIEWER_COORDINATOR' }
    const l2 = { status: 'PENDING', authorization_level: 'L2_OWNER' }
    const platform = { status: 'PENDING', authorization_kind: 'codex_platform', capability_status: 'platform_manual_required' }
    assert(authorizationActions(l1, 'reviewer').allow, 'reviewer handles L1')
    assert(!authorizationActions(l2, 'reviewer').allow, 'reviewer cannot handle L2')
    assert(authorizationActions(l2, 'owner').allow, 'owner handles L2')
    assert(authorizationActions(platform, 'owner').platformManual, 'platform approval marked manual')
    assert(!authorizationActions(platform, 'reviewer').allow, 'reviewer cannot record platform click')
    assert(!authorizationActions({ ...l2, status: 'GRANTED' }, 'owner').allow, 'terminal request has no action')
  })

  test('renders only the safe detail projection and escapes HTML', () => {
    const html = renderTaskDetailHtml({
      task: {
        project_id: 'alpha', task_id: '<script>bad()</script>', stage: 'review',
        revision: { head_sha: 'a'.repeat(40) }, merge_gate: {}, messages: [], artifacts: [], authorizations: [],
      },
      review: {}, local_ci: {}, merge_gate: {}, messages: [], artifacts: [], authorizations: [], events: [],
      privacy: { projection: 'summary_and_references', excluded: ['完整 prompt'] },
      prompt: 'SECRET-PROMPT', tool_output: 'SECRET-TOOL',
    })
    assert(html.includes('&lt;script&gt;bad()&lt;/script&gt;'), 'task id escaped')
    assert(!html.includes('SECRET-PROMPT'), 'prompt excluded')
    assert(!html.includes('SECRET-TOOL'), 'tool output excluded')
  })

  test('formats revision identity and durations', () => {
    equal(summarizeRevision({ pr_number: 7, head_sha: 'abcdef123456', mergeable: true }), 'PR #7 · abcdef12 · mergeable', 'revision')
    equal(formatDuration(3660), '1 小时 1 分', 'duration')
  })

  test('renders inbox route traces from safe status only', () => {
    const routed = inboxStatusTrace({ route_status: 'ROUTED' })
    const acked = inboxStatusTrace({ route_status: 'ACKED' })
    assert(routed.includes('ROUTED'), 'route status included')
    assert(acked.includes('ACKED'), 'ack status included')
    assert(!routed.includes('payload'), 'no payload rendering')
  })

  test('summarizes inbox routing targets compactly', () => {
    equal(
      summarizeInboxItem({ event_type: 'FIX_READY', task_id: 'PR175', target_task_id: 'reviewer-1' }),
      '修复待复审 · PR175 → reviewer-1',
      'target summary'
    )
  })

  console.log(`\n${passed} passed, ${failed} failed`)
  if (failed) process.exit(1)
}

runTests()
