"""
X Auto-Poster Bot — Gradio dashboard + background posting thread.
Posts AI-generated tech/education tweets every ~10 min with jitter.
"""
import asyncio, logging, random, threading, time
from datetime import datetime
import gradio as gr
from config import (GROQ_API_KEY, X_EMAIL, X_PASSWORD, X_USERNAME, BASE_INTERVAL, JITTER_RANGE)
from content_generator import ContentGenerator
from twitter_poster import TwitterPoster

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s", datefmt="%H:%M:%S")
logger = logging.getLogger(__name__)

state = {
 "status": "stopped", "last_tweet": "No tweets posted yet",
 "post_count": 0, "next_post_in": "N/A", "uptime_start": None,
 "logs": [], "running": False, "lock": threading.Lock(),
}

def add_log(msg: str):
 ts = datetime.now().strftime("%H:%M:%S")
 with state["lock"]:
  state["logs"].append(f"[{ts}] {msg}")
  if len(state["logs"]) > 200: state["logs"] = state["logs"][-200:]
 logger.info(msg)

def get_uptime() -> str:
 if not state["uptime_start"]: return "N/A"
 delta = time.time() - state["uptime_start"]
 return f"{int(delta//3600)}h {int((delta%3600)//60)}m {int(delta%60)}s"

async def _bot_loop():
 add_log("Initializing browser...")
 poster = TwitterPoster("/data/cookies.json")
 await poster.init_browser()
 add_log("Browser ready")
 logged_in = await poster.check_login()

 if not logged_in:
  if X_EMAIL and X_PASSWORD and X_USERNAME:
   add_log("No valid session — logging in...")
   ok = await poster.login(X_EMAIL, X_PASSWORD, X_USERNAME)
   if not ok:
    add_log("LOGIN FAILED — check X credentials in Space secrets")
    with state["lock"]: state["status"] = "login_failed"
    await poster.close(); return
   add_log("Login successful!")
  else:
   add_log("No X credentials found. Set X_EMAIL, X_PASSWORD, X_USERNAME as Space secrets.")
   with state["lock"]: state["status"] = "no_credentials"
   await poster.close(); return

 generator = ContentGenerator(GROQ_API_KEY)
 with state["lock"]:
  state["status"] = "running"
  state["uptime_start"] = time.time()
 add_log(f"Bot started — posting every ~{BASE_INTERVAL//60} min with jitter")

 while state["running"]:
  try:
   add_log("Generating tweet via Groq...")
   tweet = await generator.generate_tweet()
   if len(tweet) > 280: tweet = tweet[:277].rstrip() + "..."
   add_log(f"Generated ({len(tweet)} chars): {tweet[:70]}...")
   add_log("Posting to X...")
   success = await poster.post_tweet(tweet)
   if success:
    with state["lock"]:
     state["last_tweet"] = tweet
     state["post_count"] += 1
    add_log(f"✅ Post #{state['post_count']} successful!")
   else:
    add_log("❌ Post failed — checking session...")
    still_in = await poster.check_login()
    if not still_in and X_EMAIL and X_PASSWORD and X_USERNAME:
     add_log("Session expired — re-logging...")
     re_ok = await poster.login(X_EMAIL, X_PASSWORD, X_USERNAME)
     if re_ok: add_log("Re-login successful")
     else:
      add_log("Re-login FAILED — stopping"); break

   wait = max(BASE_INTERVAL + random.randint(-JITTER_RANGE, JITTER_RANGE), 300)
   for i in range(wait):
    if not state["running"]: break
    mins = (wait - i) // 60; secs = (wait - i) % 60
    with state["lock"]: state["next_post_in"] = f"{mins}m {secs}s"
    await asyncio.sleep(1)
  except Exception as e:
   add_log(f"Loop error: {e}")
   with state["lock"]: state["status"] = f"error: {str(e)[:60]}"
   await asyncio.sleep(60)

 await poster.close()
 with state["lock"]:
  state["status"] = "stopped"; state["next_post_in"] = "N/A"; state["uptime_start"] = None
 add_log("Bot stopped")

def _run_bot_thread():
 loop = asyncio.new_event_loop(); asyncio.set_event_loop(loop)
 try: loop.run_until_complete(_bot_loop())
 finally: loop.close()

def start_bot():
 if state["running"]: return "⚠️ Bot is already running!"
 state["running"] = True
 t = threading.Thread(target=_run_bot_thread, daemon=True); t.start()
 return "🚀 Bot starting..."

def stop_bot():
 if not state["running"]: return "⚠️ Bot is not running."
 state["running"] = False; return "🛑 Stopping bot..."

async def manual_post():
 if state["running"]: return "Stop the scheduled bot first before doing a manual post.", state["last_tweet"]
 add_log("Manual post requested...")
 poster = TwitterPoster("/data/cookies.json"); generator = ContentGenerator(GROQ_API_KEY)
 try:
  await poster.init_browser()
  logged_in = await poster.check_login()
  if not logged_in:
   if X_EMAIL and X_PASSWORD and X_USERNAME:
    add_log("Logging in for manual post...")
    ok = await poster.login(X_EMAIL, X_PASSWORD, X_USERNAME)
    if not ok: await poster.close(); return "Login failed.", state["last_tweet"]
   else: await poster.close(); return "No credentials.", state["last_tweet"]
  tweet = await generator.generate_tweet()
  if len(tweet) > 280: tweet = tweet[:277].rstrip() + "..."
  success = await poster.post_tweet(tweet); await poster.close()
  if success:
   with state["lock"]: state["last_tweet"] = tweet; state["post_count"] += 1
   add_log(f"Manual post #{state['post_count']} successful!")
   return "✅ Manual post successful!", tweet
  add_log("Manual post failed"); return "❌ Manual post failed.", state["last_tweet"]
 except Exception as e: add_log(f"Manual post error: {e}"); return f"Error: {e}", state["last_tweet"]

def full_refresh():
 with state["lock"]:
  status = state["status"]; last = state["last_tweet"]; count = str(state["post_count"])
  next_in = state["next_post_in"]; uptime = get_uptime()
  logs = "\n".join(state["logs"][-30:])
 if status == "running": badge = "🟢 Running"
 elif "error" in status or "fail" in status: badge = "🔴 " + status
 elif status == "stopped": badge = "⚪ Stopped"
 else: badge = "🟡 " + status
 clean = status.replace("🟢 ", "").replace("🔴 ", "").replace("🟡 ", "").replace("⚪ ", "")
 header = f'<div class="header-bar"><div class="header-title">⚡ X Auto-Poster</div><div class="header-status">{badge}</div></div>'
 stats = f"""<div style="display:grid;grid-template-columns:repeat(4,1fr);gap:12px;">
 <div class="stat-card"><div class="stat-value">{count}</div><div class="stat-label">Posts</div></div>
 <div class="stat-card"><div class="stat-value">{next_in}</div><div class="stat-label">Next Post</div></div>
 <div class="stat-card"><div class="stat-value">{uptime}</div><div class="stat-label">Uptime</div></div>
 <div class="stat-card"><div class="stat-value" style="font-size:16px;">{clean}</div><div class="stat-label">Status</div></div>
 </div>"""
 tweet = f'<div class="tweet-box">{last}</div>'
 log = f'<div class="log-box">{logs if logs else "Waiting for bot to start..."}</div>'
 return header, stats, tweet, log

CUSTOM_CSS = """
.gradio-container { max-width:900px !important; background:#0d1117 !important; color:#c9d1d9 !important; font-family:'JetBrains Mono','Fira Code',monospace !important; }
.gr-block,.gr-box,.gr-form { background:#161b22 !important; border:1px solid #30363d !important; border-radius:8px !important; }
.gr-button-primary { background:#238636 !important; border:1px solid #2ea043 !important; color:#fff !important; font-weight:700 !important; }
.gr-button-secondary { background:#21262d !important; border:1px solid #30363d !important; color:#c9d1d9 !important; }
.gr-button-danger,.gr-button-stop { background:#da3633 !important; border:1px solid #f85149 !important; color:#fff !important; }
.gr-label { color:#8b949e !important; font-size:12px !important; text-transform:uppercase !important; letter-spacing:1px !important; }
.stat-card { background:#161b22; border:1px solid #30363d; border-radius:8px; padding:16px; text-align:center; }
.stat-value { font-size:28px; font-weight:800; color:#58a6ff; }
.stat-label { font-size:11px; color:#8b949e; text-transform:uppercase; letter-spacing:1px; margin-top:4px; }
.tweet-box { background:#0d1117; border:1px solid #30363d; border-radius:12px; padding:16px; font-size:15px; line-height:1.6; min-height:80px; color:#e6edf3; white-space:pre-wrap; }
.log-box { background:#010409; border:1px solid #21262d; border-radius:8px; padding:12px; font-size:12px; font-family:'JetBrains Mono','Fira Code',monospace; max-height:300px; overflow-y:auto; white-space:pre-wrap; color:#8b949e; }
.header-bar { display:flex; align-items:center; justify-content:space-between; padding:16px 0; border-bottom:1px solid #21262d; margin-bottom:20px; }
.header-title { font-size:24px; font-weight:800; color:#e6edf3; }
.header-status { font-size:14px; padding:6px 14px; border-radius:20px; background:#161b22; border:1px solid #30363d; }
"""

with gr.Blocks(css=CUSTOM_CSS, title="X Auto-Poster Bot") as demo:
 start_btn = gr.Button("🚀 Start Bot", variant="primary")
 stop_btn = gr.Button("🛑 Stop Bot", variant="stop")
 manual_btn = gr.Button("📤 Manual Post", variant="secondary")
 manual_result = gr.Textbox(visible=False)
 header_html = gr.HTML()
 stats_html = gr.HTML()
 tweet_html = gr.HTML()
 log_html = gr.HTML()

 start_btn.click(fn=start_bot, inputs=[], outputs=[manual_result])
 stop_btn.click(fn=stop_bot, inputs=[], outputs=[manual_result])
 manual_btn.click(fn=manual_post, inputs=[], outputs=[manual_result, gr.Textbox(visible=False)])

 timer = gr.Timer(value=3, active=True)
 timer.tick(fn=full_refresh, inputs=[], outputs=[header_html, stats_html, tweet_html, log_html])

if __name__ == "__main__":
 logger.info(f"Groq: {'✅' if GROQ_API_KEY else '❌ set GROQ_API_KEY'}")
 logger.info(f"X creds: {'✅' if X_EMAIL else '❌ set X_EMAIL, X_PASSWORD, X_USERNAME'}")
 demo.launch(server_name="0.0.0.0", server_port=7860)
