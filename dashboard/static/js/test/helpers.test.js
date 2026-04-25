const {
  esc, formatTime, groupByBoardStatus, truncateTitle, mapToBoardStatus,
  transformBoardPayload, transformAgentPayload,
  BOARD_COLUMNS, BOARD_LABELS, CURRENT_STATUS_LABELS, STATUS_TO_BOARD,
  GANTT_PHASES,
} = require('../helpers')

const assert = (condition, msg) => { if (!condition) throw new Error(`FAIL: ${msg}`) }
const assertEqual = (a, b, msg) => assert(a === b, `${msg}: expected "${b}", got "${a}"`)

function runTests() {
  let passed = 0, failed = 0

  function test(name, fn) {
    try { fn(); passed++; console.log(`  ✓ ${name}`) }
    catch (e) { failed++; console.log(`  ✗ ${name}: ${e.message}`) }
  }

  console.log('\nhelpers.js tests:')

  // --- esc ---
  test('esc escapes HTML entities', () => {
    assertEqual(esc('<script>alert("xss")</script>'), '&lt;script&gt;alert(&quot;xss&quot;)&lt;/script&gt;', 'esc html')
  })

  test('esc returns empty for null/undefined', () => {
    assertEqual(esc(null), '', 'esc null')
    assertEqual(esc(undefined), '', 'esc undefined')
  })

  test('esc passes through safe text', () => {
    assertEqual(esc('hello world'), 'hello world', 'esc safe')
  })

  // --- formatTime ---
  test('formatTime returns formatted date', () => {
    const result = formatTime('2026-04-24T13:17:25+08:00')
    assert(result === '4/24 13:17', `formatTime: expected "4/24 13:17", got "${result}"`)
  })

  test('formatTime returns - for null/invalid', () => {
    assertEqual(formatTime(null), '-', 'null')
    assertEqual(formatTime('not-a-date'), '-', 'invalid')
  })

  // --- mapToBoardStatus (5-column mapping) ---
  test('mapToBoardStatus: dispatched → pending', () => {
    assertEqual(mapToBoardStatus('dispatched'), 'pending', 'dispatched')
  })

  test('mapToBoardStatus: failed/cancelled/timeout → blocked', () => {
    assertEqual(mapToBoardStatus('failed'), 'blocked', 'failed')
    assertEqual(mapToBoardStatus('cancelled'), 'blocked', 'cancelled')
    assertEqual(mapToBoardStatus('timeout'), 'blocked', 'timeout')
  })

  test('mapToBoardStatus: merged/archived → done', () => {
    assertEqual(mapToBoardStatus('merged'), 'done', 'merged')
    assertEqual(mapToBoardStatus('archived'), 'done', 'archived')
  })

  test('mapToBoardStatus: unknown → blocked', () => {
    assertEqual(mapToBoardStatus('unknown_status'), 'blocked', 'unknown')
  })

  test('mapToBoardStatus: direct mappings pass through', () => {
    assertEqual(mapToBoardStatus('pending'), 'pending', 'pending')
    assertEqual(mapToBoardStatus('working'), 'working', 'working')
    assertEqual(mapToBoardStatus('ready_for_merge'), 'ready_for_merge', 'rfm')
    assertEqual(mapToBoardStatus('blocked'), 'blocked', 'blocked')
    assertEqual(mapToBoardStatus('done'), 'done', 'done')
  })

  // --- groupByBoardStatus ---
  test('groupByBoardStatus maps dispatched to pending column', () => {
    const tasks = [
      { status: 'dispatched', current_status: 'dispatched', title: 'A' },
    ]
    const grouped = groupByBoardStatus(tasks)
    assertEqual(grouped.pending.length, 1, 'dispatched in pending')
    assertEqual(grouped.pending[0].board_status, 'pending', 'board_status set')
    assertEqual(grouped.pending[0].current_status, 'dispatched', 'current_status preserved')
  })

  test('groupByBoardStatus uses board_status when provided', () => {
    const tasks = [
      { board_status: 'working', current_status: 'dispatched', title: 'B' },
    ]
    const grouped = groupByBoardStatus(tasks)
    assertEqual(grouped.working.length, 1, 'uses board_status')
  })

  test('groupByBoardStatus has exactly 5 columns', () => {
    assertEqual(BOARD_COLUMNS.length, 5, '5 columns')
    assert(!BOARD_COLUMNS.includes('dispatched'), 'no dispatched column')
  })

  test('groupByBoardStatus maps failed to blocked', () => {
    const grouped = groupByBoardStatus([{ current_status: 'failed', title: 'X' }])
    assertEqual(grouped.blocked.length, 1, 'failed in blocked')
  })

  // --- transformBoardPayload ---
  test('transformBoardPayload groups by column key', () => {
    const payload = {
      columns: [
        { key: 'pending', label: 'pending', count: 1, tasks: [{ task_id: 'T1', title: 'Task 1', current_status: 'dispatched' }] },
        { key: 'working', label: 'working', count: 1, tasks: [{ task_id: 'T2', title: 'Task 2', current_status: 'working' }] },
      ],
    }
    const grouped = transformBoardPayload(payload)
    assertEqual(grouped.pending.length, 1, 'pending tasks')
    assertEqual(grouped.working.length, 1, 'working tasks')
    assertEqual(grouped.done.length, 0, 'done empty')
  })

  test('transformBoardPayload handles null payload', () => {
    const grouped = transformBoardPayload(null)
    BOARD_COLUMNS.forEach(s => assertEqual(grouped[s].length, 0, `${s} empty`))
  })

  // --- transformAgentPayload ---
  test('transformAgentPayload maps field names', () => {
    const payload = {
      agents: [{
        agent_id: 'fe-1',
        completed_task_count: 5,
        current_load_count: 2,
        total_tracked_work_seconds: 7200,
        ready_for_merge_count: 3,
      }],
    }
    const result = transformAgentPayload(payload)
    assertEqual(result.length, 1, 'one agent')
    assertEqual(result[0].completed_count, 5, 'completed_count')
    assertEqual(result[0].active_count, 2, 'active_count')
    assertEqual(result[0].total_work_seconds, 7200, 'work_seconds')
    assertEqual(result[0].ready_for_merge_count, 3, 'rfm count')
  })

  test('transformAgentPayload handles null payload', () => {
    const result = transformAgentPayload(null)
    assertEqual(result.length, 0, 'empty on null')
  })

  // --- truncateTitle ---
  test('truncateTitle truncates long titles', () => {
    assertEqual(truncateTitle('这是一个很长的任务标题超过限制', 10), '这是一个很长的任务标…', 'truncate')
  })

  test('truncateTitle passes short titles through', () => {
    assertEqual(truncateTitle('短标题', 10), '短标题', 'short title')
  })

  test('truncateTitle handles null/empty', () => {
    assertEqual(truncateTitle(null, 10), '', 'null title')
    assertEqual(truncateTitle('', 10), '', 'empty title')
  })

  // --- BOARD_LABELS / STATUS_TO_BOARD consistency ---
  test('BOARD_LABELS has all 5 columns', () => {
    BOARD_COLUMNS.forEach(s => {
      assert(BOARD_LABELS[s], `BOARD_LABELS missing ${s}`)
    })
  })

  test('STATUS_TO_BOARD covers all current_status values', () => {
    const expected = ['pending', 'dispatched', 'working', 'ready_for_merge', 'blocked', 'done', 'failed', 'cancelled', 'timeout', 'merged', 'archived']
    expected.forEach(s => {
      const mapped = STATUS_TO_BOARD[s]
      assert(BOARD_COLUMNS.includes(mapped), `${s} → ${mapped} not in BOARD_COLUMNS`)
    })
  })

  // --- GANTT_PHASES consistency ---
  test('GANTT_PHASES has 6 phases with valid structure', () => {
    assertEqual(GANTT_PHASES.length, 6, '6 phases')
    GANTT_PHASES.forEach(p => {
      assert(p.key && p.label && p.color, `phase ${p.key} missing key/label/color`)
    })
  })

  test('GANTT_PHASES all colors are unique', () => {
    const colors = GANTT_PHASES.map(p => p.color)
    assertEqual(new Set(colors).size, colors.length, 'all colors unique')
  })

  test('GANTT_PHASES all labels are unique', () => {
    const labels = GANTT_PHASES.map(p => p.label)
    assertEqual(new Set(labels).size, labels.length, 'all labels unique')
  })

  test('GANTT_PHASES keys match backend milestone names', () => {
    const expectedKeys = ['created', 'dispatched', 'ack', 'completed', 'review_completed', 'verify_completed']
    const actualKeys = GANTT_PHASES.map(p => p.key)
    expectedKeys.forEach((k, i) => {
      assertEqual(actualKeys[i], k, `phase ${i} key`)
    })
  })

  test('GANTT_PHASES labels are distinct and not ambiguous', () => {
    // No two labels should be substrings of each other
    for (let i = 0; i < GANTT_PHASES.length; i++) {
      for (let j = i + 1; j < GANTT_PHASES.length; j++) {
        const a = GANTT_PHASES[i].label
        const b = GANTT_PHASES[j].label
        assert(a !== b, `labels "${a}" and "${b}" are identical`)
      }
    }
  })

  console.log(`\nResults: ${passed} passed, ${failed} failed`)
  if (failed > 0) process.exit(1)
}

runTests()
