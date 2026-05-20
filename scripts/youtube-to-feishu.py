#!/usr/bin/env python3
"""YouTube summaries → Feishu Wiki (append to category pages) + Index Base."""
import json, sys, os, subprocess, tempfile
from datetime import datetime

BASE_TOKEN = "VslVbO4S9aiI6Gsj3CtcfmO8nxc"
INDEX_TABLE = "tblAOqvbxXcvtOF2"
WIKI_SPACE = "7641411626268101813"

# Category page tokens: cat_name -> (node_token, obj_token)
# obj_tokens are refreshed at runtime
CATEGORY_PAGES = {
    "AI行业与公司": ("GI6Iwf8nviCjhzkSfEhcIbvxnjb", "RBSPdDj8JotIQYxA1lMctdETnsd"),
    "模型发布与评测": ("UxjywwJd9i0cFlkHmpxcd3jbnUe", "UDSbdGAYLomuESx6q84ctxAanuf"),
    "政策与安全": ("Bz21wwOyOixoukkzy3scTJAqnFb", "IupidSHNcokUZqxIrIecHLATnne"),
    "AI核心技术": ("Yvtjw4YqEi46R5kPbG2cwdE1nmy", ""),
    "论文精读": ("TsTxwjG9diQ6zGkwkJIcehCvn7f", ""),
    "对谈与观点": ("EwJ4w4Opmi4QaokRNTxclMhMnxb", ""),
    "工程与部署": ("JRU8w2qUOiHDFNk6y7WcCK77ncc", ""),
    "工具与框架": ("H2H4wEl1Qithf8kVB7HcaUzUnEg", ""),
}

CLASSIFY = [
    (["NVIDIA","OpenAI","Google","Meta","Microsoft","Anthropic","公司","创业","投资","$","估值","市场"], "AI行业与公司"),
    (["GPT","Claude","Gemini","LLaMA","Qwen","DeepSeek","发布","评测","benchmark","新模型"], "模型发布与评测"),
    (["safety","Alignment","regulation","policy","人类","灵魂","风险","伦理"], "政策与安全"),
    (["transformer","architecture","training","self-play","RL","attention","预训练","微调","推理","scaling","roofline","AlphaGo"], "AI核心技术"),
    (["paper","论文","research","Arxiv"], "论文精读"),
    (["podcast","对谈","观点","访谈","对话","讨论"], "对谈与观点"),
    (["deploy","inference","工程","部署","serving","serv","scale","production"], "工程与部署"),
    (["tool","框架","FFmpeg","yt-dlp","pipeline"], "工具与框架"),
]

def classify(title, summary):
    t = (title + " " + (summary or "")).lower()
    for kw, cat in CLASSIFY:
        if any(k.lower() in t for k in kw):
            return cat
    return "AI核心技术"

def translate(text, context="内容"):
    if not text or len(text) < 10: return text
    if sum(1 for c in text if '\u4e00' <= c <= '\u9fff') > len(text)*0.3: return text
    key = os.environ.get("OPENAI_API_KEY")
    if not key: return text
    prompt = f"请将以下{context}翻译成中文。要求：1.保持技术术语准确 2.专业流畅的中文表达\n\n原文：\n{text[:4000]}"
    try:
        p = json.dumps({"model":"gpt-5.4","messages":[{"role":"user","content":prompt}]})
        r = subprocess.run(["curl","-s","-X","POST","https://3aa.ai/v1/chat/completions",
            "-H","Content-Type: application/json","-H",f"Authorization: Bearer {key}","-d",p],
            capture_output=True, text=True, timeout=120)
        if r.returncode != 0: return text
        return json.loads(r.stdout)["choices"][0]["message"]["content"]
    except: return text

def run_lark(cmd, cwd=None):
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=30, cwd=cwd)
        idx = r.stdout.find("{")
        return json.loads(r.stdout[idx:]) if idx >= 0 else None
    except Exception as e:
        print(f"  [WARN] {e}", file=sys.stderr)
        return None

def main():
    if len(sys.argv) < 2:
        print("Usage: youtube-to-feishu.py <summary_json>", file=sys.stderr); sys.exit(1)

    with open(sys.argv[1]) as f:
        items = json.load(f).get("items", [])

    # Refresh category page obj_tokens
    for cat in CATEGORY_PAGES:
        nt, _ = CATEGORY_PAGES[cat]
        r = run_lark(["lark-cli","api","GET","wiki/v2/spaces/get_node",
            "--params",json.dumps({"token":nt}),"--as","user"])
        if r and r.get("code") == 0:
            CATEGORY_PAGES[cat] = (nt, r["data"]["node"]["obj_token"])

    written = 0; skipped = 0
    for item in items:
        if not item.get("has_transcript"): continue
        title, url, summary = item["title"], item["url"], item["summary"]
        cat = classify(title, summary)
        cat_obj = CATEGORY_PAGES.get(cat, ("",""))[1]
        if not cat_obj:
            cat_obj = list(CATEGORY_PAGES.values())[0][1]

        # Dedup by YouTube URL in index
        r = run_lark(["lark-cli","base","+record-search","--base-token",BASE_TOKEN,
            "--table-id",INDEX_TABLE,"--as","user","--format","json",
            "--json",json.dumps({"keyword":url,"search_fields":["链接"]})])
        if r and r.get("ok") and len(r.get("data",{}).get("record_id_list",[])) > 0:
            skipped += 1; continue

        print(f"\n📝 {title[:50]}", file=sys.stderr)
        print(f"   分类: {cat}", file=sys.stderr)

        # Translate
        print(f"   翻译标题...", file=sys.stderr)
        t_title = translate(title, "YouTube 视频标题")
        print(f"   翻译摘要...", file=sys.stderr)
        t_summary = translate(summary, "YouTube 视频摘要")
        dt = datetime.now().strftime('%Y-%m-%d %H:%M')

        # Append entry to category page
        entry = f"""

---

### {t_title}

- **频道**: {item.get('channel','?')} | **时长**: {item.get('duration','?')}  
  **视频**: [{url}]({url})

{t_summary}

*—— {dt}*"""

        with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False, dir='/tmp') as f:
            f.write(entry); p = f.name
        run_lark(["lark-cli","docs","+update","--doc",cat_obj,
            "--mode","append","--as","user","--markdown",f"@{os.path.basename(p)}"], cwd="/tmp")
        os.unlink(p)

        # Add index record
        run_lark(["lark-cli","base","+record-upsert","--base-token",BASE_TOKEN,
            "--table-id",INDEX_TABLE,"--as","user",
            "--json",json.dumps({"标题":t_title[:80],"链接":url,
                "来源":item.get("channel","YouTube"),"类别":cat,
                "阅读状态":"📌 待读","重要程度":"⭐⭐","摘要":t_summary[:500]})])
        written += 1
        print(f"    ✅ 已追加到 {cat} 页面", file=sys.stderr)

    print(f"\n📊 新增{written} / 跳过{skipped} (重复)", file=sys.stderr)

if __name__ == "__main__":
    main()
