"""
Browser automation to post tweets on X without using the X API.
Uses Playwright + stealth to mimic a real browser session.
"""
import asyncio, json, os, random, logging
from playwright.async_api import async_playwright, Page, BrowserContext
from playwright_stealth import stealth_async
from config import COOKIE_FILE

logger = logging.getLogger(__name__)
TYPE_MIN = 30; TYPE_MAX = 90

class TwitterPoster:
 def __init__(self, cookie_file: str):
  self.cookie_file = cookie_file
  self.playwright = None; self.browser = None
  self.context: BrowserContext | None = None
  self.page: Page | None = None

 async def init_browser(self):
  self.playwright = await async_playwright().start()
  self.browser = await self.playwright.chromium.launch(headless=True, args=[
   "--no-sandbox", "--disable-setuid-sandbox", "--disable-dev-shm-usage",
   "--disable-blink-features=AutomationControlled", "--disable-infobars",
   "--window-position=0,0", "--ignore-certificate-errors"])
  self.context = await self.browser.new_context(viewport={"width": 1366, "height": 768},
   user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
   locale="en-US", timezone_id="Asia/Kolkata")
  if os.path.exists(self.cookie_file):
   try:
    with open(self.cookie_file, "r") as f:
     cookies = json.load(f)
    if cookies:
     await self.context.add_cookies(cookies)
     logger.info(f"Loaded {len(cookies)} cookies")
   except Exception as e: logger.warning(f"Cookie load failed: {e}")
  self.page = await self.context.new_page()
  await stealth_async(self.page)
  await self.page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

 async def check_login(self) -> bool:
  try:
   await self.page.goto("https://x.com/home", wait_until="networkidle", timeout=30000)
   await asyncio.sleep(random.uniform(2, 4))
   if "login" in self.page.url:
    logger.info("Not authenticated")
    return False
   try:
    await self.page.wait_for_selector('[data-testid="SideNav_NewTweet_Button"], a[href="/home"]', timeout=8000)
    logger.info("Login confirmed")
    return True
   except Exception:
    return False
  except Exception as e:
   logger.error(f"Check login error: {e}")
   return False

 async def login(self, email: str, password: str, username: str) -> bool:
  try:
   logger.info("Starting X login flow...")
   await self.page.goto("https://x.com/i/flow/login", wait_until="networkidle", timeout=30000)
   await asyncio.sleep(random.uniform(2, 4))

   email_input = await self.page.wait_for_selector('input[autocomplete="username"]', timeout=15000)
   await self._human_type(email_input, email)
   await asyncio.sleep(random.uniform(0.5, 1.5))

   for btn in await self.page.query_selector_all('button'):
    if (await btn.inner_text()).strip().lower() == "next":
     await btn.click(); break
   await asyncio.sleep(random.uniform(3, 5))

   try:
    username_field = await self.page.wait_for_selector('input[data-testid="ocfEnterTextTextInput"]', timeout=5000)
    if username_field:
     logger.info("Username verification step")
     await self._human_type(username_field, username)
     await asyncio.sleep(random.uniform(0.5, 1))
     for btn in await self.page.query_selector_all('button'):
      if (await btn.inner_text()).strip().lower() == "next":
       await btn.click(); break
     await asyncio.sleep(random.uniform(3, 5))
   except Exception:
    pass

   pw_input = await self.page.wait_for_selector('input[type="password"]', timeout=10000)
   await self._human_type(pw_input, password)
   await asyncio.sleep(random.uniform(0.5, 1.5))

   for btn in await self.page.query_selector_all('button'):
    if (await btn.inner_text()).strip().lower() == "log in":
     await btn.click(); break
   await asyncio.sleep(random.uniform(5, 8))
   await self.page.wait_for_load_state("networkidle")

   if "login" in self.page.url:
    logger.error("Still on login page — login may have failed")
    return False
   logger.info("Login successful!")
   await self._save_cookies()
   return True
  except Exception as e:
   logger.error(f"Login failed: {e}")
   return False

 async def post_tweet(self, text: str) -> bool:
  try:
   logger.info(f"Posting: {text[:60]}...")
   await self.page.goto("https://x.com/compose/post", wait_until="networkidle", timeout=30000)
   await asyncio.sleep(random.uniform(2, 4))
   composer = await self.page.wait_for_selector('[data-testid="tweetTextarea_0"]', timeout=15000)
   if not composer:
    logger.error("No composer found")
    return False
   await composer.click()
   await asyncio.sleep(random.uniform(0.3, 0.8))
   await self._human_type(composer, text)
   await asyncio.sleep(random.uniform(1.5, 3))
   post_btn = await self.page.wait_for_selector('[data-testid="tweetButton"]', timeout=8000)
   if not post_btn:
    logger.error("No Post button")
    return False
   await post_btn.click()
   logger.info("Clicked Post")
   await asyncio.sleep(random.uniform(3, 5))
   if "compose" not in self.page.url:
    logger.info("Tweet posted (redirected)")
    return True
   logger.info("Tweet posted (assumed success)")
   return True
  except Exception as e:
   logger.error(f"Post failed: {e}")
   return False

 async def _human_type(self, element, text: str):
  for char in text:
   await element.type(char, delay=random.randint(TYPE_MIN, TYPE_MAX))
   if random.random() < 0.05:
    await asyncio.sleep(random.uniform(0.3, 0.8))

 async def _save_cookies(self):
  try:
   cookies = await self.context.cookies()
   with open(self.cookie_file, "w") as f:
    json.dump(cookies, f, indent=2)
   logger.info(f"Saved {len(cookies)} cookies")
  except Exception as e:
   logger.error(f"Cookie save failed: {e}")

 async def close(self):
  try:
   if self.page: await self._save_cookies()
   if self.browser: await self.browser.close()
   if self.playwright: await self.playwright.stop()
   logger.info("Browser closed")
  except Exception as e:
   logger.error(f"Close error: {e}")
