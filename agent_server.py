"""GHA Agent — Full Playwright agent server for GitHub Actions with public tunnel"""
import os, json, asyncio, subprocess, tempfile
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, HTMLResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from openai import OpenAI
from playwright.async_api import async_playwright
import httpx
from pathlib import Path

app = FastAPI(title="GHA Agent")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

# ── Config (from GH Secrets) ──
GROQ_KEY = os.environ["GROQ_KEY"]
NVIDIA_KEY = os.environ.get("NVIDIA_KEY", "")
NVIDIA = OpenAI(base_url="https://integrate.api.nvidia.com/v1", api_key=NVIDIA_KEY) if NVIDIA_KEY else None
memory = []

SYSTEM_PROMPT = """You are an AI agent with real browser access. You can:
- web_search(query) — search the internet
- navigate(url) — open a webpage
- click(text) — click an element by text
- screenshot — capture the visible page
- get_text — extract text from current page
- execute_python(code) — run Python code
- execute_bash(cmd) — run bash commands

Use these tools to answer questions with real, live information. Chain multiple tools.
Be concise. The browser tab stays open between calls."""

# ── Browser state ──
browser = None; page = None; pw = None

async def get_browser():
    global browser, page, pw
    if pw is None:
        pw = await async_playwright().start()
        browser = await pw.chromium.launch(headless=True, args=[
            "--no-sandbox", "--disable-setuid-sandbox", "--disable-dev-shm-usage"])
        page = await browser.new_page(viewport={"width":1366,"height":768})
        print("🌐 Browser ready")
    return page

# ── Tools ──
async def web_search(query, n=5):
    try:
        from duckduckgo_search import DDGS
        r = [{"title":x.get("title",""),"url":x.get("href",""),"snippet":x.get("body","")[:200]}
             for x in DDGS().text(query, max_results=min(n,8))]
        return {"results":r,"count":len(r)}
    except Exception as e: return {"error":str(e)}

async def navigate(url):
    p = await get_browser()
    await p.goto(url, wait_until="load", timeout=30000)
    return {"url":p.url, "title":await p.title()}

async def click(text):
    p = await get_browser()
    try:
        await p.click(f'text="{text}"', timeout=5000)
        await asyncio.sleep(1)
        return {"clicked":text, "url":p.url}
    except:
        try:
            await p.click(f':has-text("{text}")', timeout=5000)
            return {"clicked":text, "url":p.url}
        except Exception as e:
            return {"error":str(e)}

async def screenshot():
    p = await get_browser()
    import base64
    b = await p.screenshot(type="png")
    return {"image_base64": "data:image/png;base64," + base64.b64encode(b).decode()}

async def get_text():
    p = await get_browser()
    t = await p.inner_text("body")
    return {"text": t[:4000], "title": await p.title()}

async def execute_python(code, timeout=10):
    try:
        with tempfile.NamedTemporaryFile(mode='w',suffix='.py',delete=False) as f:
            f.write(code); tmp=f.name
        r = subprocess.run(["python3",tmp],capture_output=True,text=True,timeout=timeout)
        os.unlink(tmp)
        return {"stdout":r.stdout[:3000],"stderr":r.stderr[:1000],"ok":r.returncode==0}
    except Exception as e: return {"error":str(e)}

async def execute_bash(cmd):
    if any(b in cmd.lower() for b in ["rm -rf","sudo","shutdown","reboot"]):
        return {"error":"Blocked"}
    try:
        r = subprocess.run(cmd,shell=True,capture_output=True,text=True,timeout=15)
        return {"output":(r.stdout+r.stderr)[:3000]}
    except Exception as e: return {"error":str(e)}

TOOLS = {
    "web_search": web_search, "navigate": navigate, "click": click,
    "screenshot": screenshot, "get_text": get_text,
    "execute_python": execute_python, "execute_bash": execute_bash,
}

# ── LLM ──
async def call_llm(messages, tools_schema):
    # Groq primary
    try:
        r = httpx.post("https://api.groq.com/openai/v1/chat/completions",
            headers={"Authorization":f"Bearer {GROQ_KEY}","Content-Type":"application/json"},
            json={"model":"llama-3.3-70b-versatile","messages":messages,"tools":tools_schema,
                  "tool_choice":"auto","temperature":0.7,"max_tokens":2048}, timeout=30)
        if r.status_code == 200:
            c = r.json()["choices"][0]
            return c["message"].get("content",""), c["message"].get("tool_calls")
    except Exception as e: print(f"Groq fail: {e}")

    # Nvidia fallback
    if NVIDIA:
        try:
            r = NVIDIA.chat.completions.create(model="meta/llama-3.1-8b-instruct",
                messages=messages, tools=tools_schema, tool_choice="auto", temperature=0.7, max_tokens=2048)
            c = r.choices[0]
            tcs = [{"id":tc.id,"type":"function","function":{"name":tc.function.name,"arguments":tc.function.arguments}}
                   for tc in c.message.tool_calls] if c.message.tool_calls else None
            return c.message.content or "", tcs
        except Exception as e: print(f"Nvidia fail: {e}")

    return "Both LLMs failed.", None

# ── API ──
@app.get("/", response_class=HTMLResponse)
async def ui():
    p = Path(__file__).parent / "ui.html"
    return p.read_text() if p.exists() else "<h1>UI not found</h1>"

@app.post("/chat")
async def chat(req: Request):
    data = await req.json()
    msg = data.get("message","")
    memory.append({"role":"user","content":msg})

    tools_schema = [
        {"type":"function","function":{"name":"web_search","description":"Search the web","parameters":{"type":"object","properties":{"query":{"type":"string"},"n":{"type":"integer"}},"required":["query"]}}},
        {"type":"function","function":{"name":"navigate","description":"Open a URL","parameters":{"type":"object","properties":{"url":{"type":"string"}},"required":["url"]}}},
        {"type":"function","function":{"name":"click","description":"Click element by text","parameters":{"type":"object","properties":{"text":{"type":"string"}},"required":["text"]}}},
        {"type":"function","function":{"name":"screenshot","description":"Take screenshot of current page","parameters":{"type":"object","properties":{}}}},
        {"type":"function","function":{"name":"get_text","description":"Get text from current page","parameters":{"type":"object","properties":{}}}},
        {"type":"function","function":{"name":"execute_python","description":"Run Python code","parameters":{"type":"object","properties":{"code":{"type":"string"}},"required":["code"]}}},
        {"type":"function","function":{"name":"execute_bash","description":"Run bash command","parameters":{"type":"object","properties":{"cmd":{"type":"string"}},"required":["cmd"]}}},
    ]

    msgs = [{"role":"system","content":SYSTEM_PROMPT}] + memory[-12:]

    for _ in range(6):
        content, tool_calls = await call_llm(msgs, tools_schema)
        if not tool_calls:
            memory.append({"role":"assistant","content":content or ""})
            return {"response": content or "Done.", "tools_used": False}

        msgs.append({"role":"assistant","content":content or "", "tool_calls":tool_calls})
        for tc in tool_calls:
            fn = tc["function"]
            name = fn["name"]
            args = json.loads(fn.get("arguments","{}"))
            tool = TOOLS.get(name)
            if tool:
                result = await tool(**args)
            else:
                result = {"error": f"Unknown tool: {name}"}
            msgs.append({"role":"tool","tool_call_id":tc["id"],
                        "content":json.dumps(result,default=str)[:2000]})

    memory.append({"role":"assistant","content":"Round limit reached."})
    return {"response":"Round limit reached — please try a more specific question.","tools_used":True}

@app.post("/clear")
async def clear(): memory.clear(); return {"ok":True}

@app.get("/ping")
async def ping(): return {"ok":True}

if __name__ == "__main__":
    import uvicorn, threading, time

    # Tunnel setup
    def start_tunnel():
        time.sleep(3)
        import socket
        # Try bore first
        try:
            import urllib.request, shutil
            if not os.path.exists("/tmp/bore"):
                urllib.request.urlretrieve(
                    "https://github.com/ekzhang/bore/releases/download/v0.5.2/bore-x86_64-unknown-linux-musl",
                    "/tmp/bore")
                os.chmod("/tmp/bore", 0o755)
            r = subprocess.run(["/tmp/bore","local","7860","--to","bore.pub"],
                             capture_output=True, text=True, timeout=8)
            for line in r.stderr.split('\n'):
                if 'bore.pub' in line:
                    print(f"\n\n🔗 PUBLIC URL: http://{line.strip()}\n\n")
                    return
        except: pass

        # Fallback: serveo
        try:
            r = subprocess.run(
                "ssh -o StrictHostKeyChecking=no -o ServerAliveInterval=30 -R 80:localhost:7860 serveo.net 2>&1",
                shell=True, capture_output=True, text=True, timeout=10)
            for line in (r.stdout + r.stderr).split('\n'):
                if 'serveo.net' in line and 'Forwarding' in line:
                    url = line.strip().split()[-1]
                    print(f"\n\n🔗 PUBLIC URL: {url}\n\n")
                    return
        except: pass

        print("\n\n⚠️ No tunnel could be established. Use local port 7860.\n\n")

    threading.Thread(target=start_tunnel, daemon=True).start()
    print("🌸 GHA Agent starting on :7860")
    uvicorn.run(app, host="0.0.0.0", port=7860, log_level="warning")
