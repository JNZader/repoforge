"""
server.py - Serve generated docs (Docsify) or skills/agents browser.

Two modes:
  1. docs  → serves a Docsify docs/ folder as static files (index.html + .md files)
  2. skills → opens a browser-based viewer for SKILL.md / AGENT.md files

Usage via CLI:
  repoforge docs --serve -o docs
  repoforge skills --serve -o .claude
"""

import os
import json
import mimetypes
from pathlib import Path
from http.server import HTTPServer, BaseHTTPRequestHandler, SimpleHTTPRequestHandler
import urllib.parse
import threading
import webbrowser


def serve_docs(output_dir: str = "docs", port: int = 8000, open_browser: bool = True):
    """
    Serve a Docsify docs folder as static files.
    Works with any folder containing index.html + .md files.
    """
    out = Path(output_dir).resolve()
    if not out.exists():
        raise FileNotFoundError(f"Docs directory not found: {out}\n"
                                f"Run \'repoforge docs -o {output_dir}\' first.")

    if not (out / "index.html").exists():
        raise FileNotFoundError(f"No index.html found in {out}\n"
                                f"Make sure you ran \'repoforge docs\' first.")

    # Use SimpleHTTPRequestHandler with custom directory
    import functools
    handler = functools.partial(
        _StaticHandler, directory=str(out)
    )

    server = HTTPServer(("localhost", port), handler)
    url = f"http://localhost:{port}"

    print(f"📖  Serving docs at {url}")
    print(f"    Directory: {out}")
    print(f"    Press Ctrl+C to stop.\n")

    if open_browser:
        threading.Timer(0.4, lambda: webbrowser.open(url)).start()

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n👋 Server stopped.")


def serve_skills(output_dir: str = ".claude", port: int = 8765, open_browser: bool = True):
    """
    Serve a browser-based viewer for SKILL.md and AGENT.md files.
    """
    out = Path(output_dir).resolve()
    if not out.exists():
        raise FileNotFoundError(f"Skills directory not found: {out}\n"
                                f"Run \'repoforge skills -o {output_dir}\' first.")

    handler = _make_skills_handler(out)
    server = HTTPServer(("localhost", port), handler)
    url = f"http://localhost:{port}"

    print(f"⚒   RepoForge skills browser at {url}")
    print(f"    Directory: {out}")
    print(f"    Press Ctrl+C to stop.\n")

    if open_browser:
        threading.Timer(0.4, lambda: webbrowser.open(url)).start()

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n👋 Server stopped.")


# ---------------------------------------------------------------------------
# Static file handler for Docsify (handles .md as text/plain for Docsify JS)
# ---------------------------------------------------------------------------

class _StaticHandler(SimpleHTTPRequestHandler):
    def log_message(self, format, *args):
        pass  # silence access log

    def guess_type(self, path):
        # Docsify needs .md served as text/plain (not application/octet-stream)
        if str(path).endswith(".md"):
            return "text/plain; charset=utf-8"
        return super().guess_type(path)

    def end_headers(self):
        # Allow Docsify to load files cross-origin in some setups
        self.send_header("Access-Control-Allow-Origin", "*")
        super().end_headers()


# ---------------------------------------------------------------------------
# Skills/Agents viewer (custom handler with JSON API)
# ---------------------------------------------------------------------------

def _make_skills_handler(out: Path):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, format, *args):
            pass

        def do_GET(self):
            parsed = urllib.parse.urlparse(self.path)
            path = parsed.path

            if path in ("/", ""):
                self._html(_build_skills_html())
            elif path == "/api/files":
                self._json(_build_tree(out))
            elif path.startswith("/api/content"):
                qs = urllib.parse.parse_qs(parsed.query)
                rel = qs.get("path", [""])[0]
                self._content(rel)
            else:
                self._respond(404, "text/plain", b"Not found")

        def _html(self, html: str):
            self._respond(200, "text/html; charset=utf-8", html.encode())

        def _json(self, data):
            self._respond(200, "application/json", json.dumps(data).encode())

        def _content(self, rel_path: str):
            target = (out / rel_path).resolve()
            if not str(target).startswith(str(out)):
                self._respond(404, "text/plain", b"Not found")
                return
            if not target.exists():
                self._respond(404, "text/plain", b"Not found")
                return
            content = target.read_text(errors="replace")
            self._respond(200, "text/plain; charset=utf-8", content.encode())

        def _respond(self, code, ct, body: bytes):
            self.send_response(code)
            self.send_header("Content-Type", ct)
            self.send_header("Content-Length", len(body))
            self.end_headers()
            self.wfile.write(body)

    return Handler


def _build_tree(out: Path) -> list:
    result = []
    for entry in sorted(out.rglob("*.md")):
        rel = str(entry.relative_to(out))
        parts = Path(rel).parts
        result.append({
            "path": rel.replace(os.sep, "/"),
            "name": entry.name,
            "parts": list(parts),
            "is_skill": "skills" in parts,
            "is_agent": "agents" in parts,
        })
    return result


def _build_skills_html() -> str:
    return """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>RepoForge — Skills Browser</title>
<style>
  :root {
    --bg:#0f1117;--surface:#1a1d27;--border:#2a2d3e;
    --text:#e2e8f0;--muted:#64748b;--accent:#6366f1;
    --skill:#10b981;--agent:#f59e0b;
    --font:'JetBrains Mono','Fira Code',monospace;
  }
  *{box-sizing:border-box;margin:0;padding:0}
  body{background:var(--bg);color:var(--text);font-family:var(--font);display:flex;height:100vh;overflow:hidden}
  #sidebar{width:280px;min-width:280px;background:var(--surface);border-right:1px solid var(--border);display:flex;flex-direction:column;overflow:hidden}
  #hdr{padding:14px 16px;border-bottom:1px solid var(--border)}
  #hdr h1{font-size:13px;color:var(--accent);letter-spacing:.1em;text-transform:uppercase}
  #hdr p{font-size:10px;color:var(--muted);margin-top:3px}
  #tree{flex:1;overflow-y:auto;padding:6px 0}
  .sec{font-size:9px;color:var(--muted);text-transform:uppercase;letter-spacing:.1em;padding:10px 14px 3px}
  .item{display:flex;align-items:center;gap:7px;padding:5px 14px;cursor:pointer;font-size:11px;color:var(--muted);border-left:2px solid transparent;transition:background .1s}
  .item:hover{background:rgba(99,102,241,.08);color:var(--text)}
  .item.active{background:rgba(99,102,241,.15);color:var(--text);border-left-color:var(--accent)}
  .badge{font-size:8px;padding:1px 4px;border-radius:3px;font-weight:700}
  .bs{background:rgba(16,185,129,.2);color:var(--skill)}
  .ba{background:rgba(245,158,11,.2);color:var(--agent)}
  .nm{flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
  .dr{color:var(--muted);font-size:9px}
  #main{flex:1;display:flex;flex-direction:column;overflow:hidden}
  #toolbar{padding:10px 18px;border-bottom:1px solid var(--border);display:flex;align-items:center;gap:10px;background:var(--surface)}
  #cf{font-size:11px;color:var(--muted);flex:1}
  #cpb{font-size:10px;padding:3px 10px;background:var(--accent);color:#fff;border:none;border-radius:4px;cursor:pointer;font-family:var(--font)}
  #ca{flex:1;overflow-y:auto;padding:24px 28px}
  #ren{font-size:13px;line-height:1.8}
  #ren h1{font-size:18px;color:var(--accent);margin-bottom:14px;padding-bottom:6px;border-bottom:1px solid var(--border)}
  #ren h2{font-size:13px;color:var(--text);margin:18px 0 6px}
  #ren h3{font-size:11px;color:var(--muted);margin:12px 0 5px;text-transform:uppercase;letter-spacing:.05em}
  #ren p{color:#94a3b8;margin-bottom:8px}
  #ren code{background:var(--border);padding:1px 4px;border-radius:3px;font-size:11px;color:var(--skill)}
  #ren pre{background:var(--surface);border:1px solid var(--border);border-radius:5px;padding:12px;margin:8px 0;overflow-x:auto}
  #ren pre code{background:none;color:var(--text);padding:0}
  #ren ul,#ren ol{padding-left:18px;color:#94a3b8;margin-bottom:8px}
  #ren li{margin-bottom:3px}
  .fm{background:var(--surface);border:1px solid var(--border);border-radius:5px;padding:12px;margin-bottom:18px;font-size:11px}
  .fk{color:var(--agent)}.fv{color:var(--skill)}
  #empty{display:flex;align-items:center;justify-content:center;height:100%;color:var(--muted);font-size:12px;flex-direction:column;gap:6px}
  #empty .big{font-size:28px}
</style>
</head>
<body>
<div id="sidebar">
  <div id="hdr"><h1>⚒ RepoForge</h1><p>Skills &amp; Agents browser</p></div>
  <div id="tree"></div>
</div>
<div id="main">
  <div id="toolbar">
    <span id="cf">Select a file</span>
    <button id="cpb" onclick="cp()">Copy</button>
  </div>
  <div id="ca">
    <div id="empty"><div class="big">⚒</div><div>Select a skill or agent to view</div></div>
    <div id="ren" style="display:none"></div>
  </div>
</div>
<script>
let cur='';
async function init(){
  const r=await fetch('/api/files');
  const f=await r.json();
  const tr=document.getElementById('tree');
  const sk=f.filter(x=>x.is_skill),ag=f.filter(x=>x.is_agent),ot=f.filter(x=>!x.is_skill&&!x.is_agent);
  let h='';
  if(sk.length){h+='<div class="sec">Skills</div>';sk.forEach(x=>h+=item(x,'s'))}
  if(ag.length){h+='<div class="sec">Agents</div>';ag.forEach(x=>h+=item(x,'a'))}
  if(ot.length){h+='<div class="sec">Other</div>';ot.forEach(x=>h+=item(x,''))}
  tr.innerHTML=h;
}
function item(f,t){
  const b=t?`<span class="badge b${t}">${t==='s'?'skill':'agent'}</span>`:'';
  const d=f.parts.length>1?f.parts.slice(0,-1).join('/')+'/':'';
  return `<div class="item" onclick="load('${f.path}')" data-p="${f.path}">${b}<span class="nm" title="${f.path}">${f.name}</span><span class="dr">${d}</span></div>`;
}
async function load(p){
  document.querySelectorAll('.item').forEach(e=>e.classList.toggle('active',e.dataset.p===p));
  document.getElementById('cf').textContent=p;
  const r=await fetch('/api/content?path='+encodeURIComponent(p));
  cur=await r.text();
  document.getElementById('empty').style.display='none';
  const ren=document.getElementById('ren');
  ren.style.display='block';
  ren.innerHTML=md(cur);
}
function md(t){
  let fm='',body=t;
  const m=t.match(/^---\\n([\\s\\S]*?)\\n---\\n?/);
  if(m){
    fm='<div class="fm">'+m[1].split('\n').map(l=>{const[k,...v]=l.split(':');return`<div><span class="fk">${k}:</span> <span class="fv">${v.join(':').trim()}</span></div>`}).join('')+'</div>';
    body=t.slice(m[0].length);
  }
  body=body
    .replace(/```(\w*)\n([\s\S]*?)```/g,'<pre><code>$2</code></pre>')
    .replace(/^### (.+)$/gm,'<h3>$1</h3>')
    .replace(/^## (.+)$/gm,'<h2>$1</h2>')
    .replace(/^# (.+)$/gm,'<h1>$1</h1>')
    .replace(/`([^`]+)`/g,'<code>$1</code>')
    .replace(/^[-*] (.+)$/gm,'<li>$1</li>')
    .replace(/^\d+\. (.+)$/gm,'<li>$1</li>')
    .replace(/(<li>[\s\S]*?<\/li>\n?)+/g,m=>'<ul>'+m+'</ul>')
    .replace(/\*\*(.+?)\*\*/g,'<strong>$1</strong>')
    .replace(/\n\n/g,'</p><p>');
  return fm+'<p>'+body+'</p>';
}
function cp(){navigator.clipboard.writeText(cur).then(()=>{const b=document.getElementById('cpb');b.textContent='✓ Copied';setTimeout(()=>b.textContent='Copy',1500)})}
init();
</script>
</body>
</html>"""
