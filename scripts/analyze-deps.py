#!/usr/bin/env python3
"""analyze-deps.py — 分析任务依赖链，找出最长阻塞链和根阻塞者"""
import json, os, sys
from pathlib import Path
from collections import defaultdict, deque

TASKS_ROOT = os.environ.get('TASKS_ROOT', Path(__file__).resolve().parents[1] / 'tasks')

def load_tasks():
    tasks = {}
    for tf in Path(TASKS_ROOT).glob('*/task.json'):
        try:
            d = json.loads(tf.read_text())
            tid = d.get('id', tf.parent.name)
            tasks[tid] = {
                'id': tid, 'title': d.get('title', tid),
                'status': d.get('status', ''),
                'assigned_agent': d.get('assigned_agent', ''),
                'depends_on': d.get('depends_on', []) or [],
                'blocks': d.get('blocks', []) or [],
            }
        except: pass
    return tasks

def find_blocking_chains(tasks):
    blocked = {tid: t for tid, t in tasks.items() if t['status'] == 'blocked'}
    if not blocked: return [], {}
    blocked_by = defaultdict(list)
    for tid, t in tasks.items():
        for dep_id in t.get('depends_on', []):
            if dep_id in tasks:
                blocked_by[tid].append(dep_id)
    chains, roots = [], defaultdict(list)
    for tid, t in blocked.items():
        visited, q = set(), deque([(tid, [tid])])
        longest = []
        while q:
            node, path = q.popleft()
            if node in visited: continue
            visited.add(node)
            blockers = blocked_by.get(node, [])
            if not blockers:
                if len(path) > len(longest): longest = path
            else:
                for b in blockers: q.append((b, path + [b]))
        if longest:
            root = longest[-1]
            root_status = tasks.get(root, {}).get('status', '?')
            root_title = tasks.get(root, {}).get('title', root)
            chains.append({'task': t['title'], 'task_id': tid, 'chain': longest,
                'length': len(longest), 'root': root,
                'root_title': root_title, 'root_status': root_status})
            roots[root].append(tid)
    chains.sort(key=lambda x: x['length'], reverse=True)
    return chains, dict(roots)

def format_output(chains, roots, mode='text'):
    if not chains: return "✅ 当前无 blocked 任务"
    lines = [f"🔗 阻塞链分析（{len(chains)} 个 blocked 任务）", ""]
    seen_roots = set()
    for c in chains[:5]:
        if c['root'] in seen_roots: continue
        seen_roots.add(c['root'])
        chain_str = ' ← '.join(c['chain'])
        lines.append(f"根: {c['root_title'][:40]} [{c['root_status']}]")
        lines.append(f"链: {chain_str[:120]}")
        lines.append(f"阻塞 {len(roots.get(c['root'],[]))} 个下游")
        lines.append("")
    if len(seen_roots) < len(roots):
        lines.append(f"... 还有 {len(roots)-len(seen_roots)} 个阻塞根节点")
    return '\n'.join(lines)

def generate_mermaid(tasks):
    lines = ['flowchart TD']
    lines.append('    classDef blocked fill:#ff4444,color:white')
    lines.append('    classDef working fill:#ff9900,color:white')
    lines.append('    classDef done fill:#44bb44,color:white')
    
    node_ids = {}
    for i, (tid, t) in enumerate(tasks.items()):
        deps = t.get('depends_on', [])
        blocked_by = [ot for ot, otv in tasks.items() if tid in otv.get('depends_on', [])]
        if deps or blocked_by:
            safe_id = f"T{i}"
            node_ids[tid] = safe_id
            status = t['status']
            label = t['title'][:40].replace('"', '')
            cls = 'blocked' if status == 'blocked' else ('done' if status == 'done' else 'working')
            lines.append(f'    {safe_id}["{label}"]')
            lines.append(f'    class {safe_id} {cls}')
    
    if not node_ids:
        lines.append('    T0["尚无依赖关系数据"] ~~~ T1["等待任务间添加 depends_on 字段"]')
        lines.append('    class T0,T1 working')
        return '\n'.join(lines)
    
    for tid, t in tasks.items():
        if tid not in node_ids: continue
        for dep in t.get('depends_on', []):
            if dep in node_ids:
                lines.append(f'    {node_ids[dep]} --> {node_ids[tid]}')
    return '\n'.join(lines)

if __name__ == '__main__':
    tasks = load_tasks()
    mode = sys.argv[1] if len(sys.argv) > 1 else 'text'
    if mode == 'mermaid':
        print(generate_mermaid(tasks))
    else:
        chains, roots = find_blocking_chains(tasks)
        print(format_output(chains, roots, mode))
