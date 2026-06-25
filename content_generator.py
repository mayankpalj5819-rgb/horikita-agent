"""
Generates tweets using the free Groq API.
Falls back to a curated pool if Groq is down or rate-limited.
"""
import json, os, random, logging, httpx
from config import (
 GROQ_API_KEY, GROQ_MODEL, GROQ_FALLBACK_MODEL,
 TOPICS, MAX_TWEET_LENGTH, HISTORY_FILE
)

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are a sharp, engaging tech-education influencer on X (Twitter).
Your audience: Indian students, JEE aspirants, IITians, tech professionals.

STYLE RULES:
- Keep every tweet under 260 characters.
- Use 1-2 emojis max. End with 1-2 relevant hashtags.
- Vary format: bullet-point lists, punchy statements, questions, fact + opinion.
- Never use filler words like "Hey guys", "Let's dive in".
- Sound like a knowledgeable senior, not a motivational speaker.
- Use REAL data points when possible (placement numbers, exam stats, ranking positions).
- No misinformation — if unsure, give opinion not fact.
- Never repeat the same tweet or very similar wording.
- Do NOT use quotation marks around the entire tweet.
- Output ONLY the tweet text, nothing else."""

FALLBACK_TWEETS = [
 "IIT Bombay's placement 2024: 300+ PPOs before final season even started.\n\nThe secret? Students start building projects in 2nd year, not 4th.\n\nStart early. Build publicly.\n\n#IIT #Placements",
 "JEE Advanced has negative marking for a reason.\n\nIt doesn't just test knowledge — it tests DECISION MAKING under pressure.\n\nTop 100 rankers attempt ~70% of questions, not 100%.\n\nAccuracy > Speed.\n\n#JEEAdvanced #IITJEE",
 "Google just made Gemma 3 open weight.\n\nWhat Indian students should realize:\n→ You can run a powerful LLM on a ₹40k laptop\n→ No cloud GPU bills\n→ Build AI apps for free\n\nThe playing field is level now.\n\n#AI #OpenSource",
 "NEP 2020 allows multiple entries/exits in degrees.\n\nBut most Indian universities still haven't implemented it properly.\n\nPolicy ≠ Practice.\n\nUntil UGC enforces it strictly, this remains on paper.\n\n#NEP2020 #EducationIndia",
 "Germany's public universities: ₹0 tuition for international students.\n\nLiving cost: ₹50-70k/month in smaller cities.\n\nCompare this to a private Indian university charging ₹15L/year.\n\nDo the math.\n\n#StudyAbroad #Germany",
 "IIT Madras produces more research papers per faculty than most Ivy League schools.\n\nBut research output ≠ teaching quality.\n\nMany IIT students learn more from YouTube than from lectures.\n\n#IITMadras #Research",
 "Unpopular opinion: Coding platforms don't prepare you for real software engineering.\n\nThey prepare you for interviews.\n\nReal engineering = reading docs, debugging stale code, writing tests, communicating.\n\n#Coding #TechCareers",
 "CAT 2024 had 66 questions in 120 minutes.\n\nThat's ~108 seconds per question.\n\nThe toppers don't solve everything — they skip strategically.\n\nSelection > Solution.\n\n#CAT2024 #MBA",
 "ISRO's Chandrayaan-3 budget: ₹615 crore.\n\nAvatar movie budget: ₹2,300 crore.\n\nIndia does more with less. Always has.\n\n#ISRO #Chandrayaan3 #Space",
 "IIT Delhi's incubation cell has spawned 100+ startups worth ₹5000+ crore.\n\nCampus startups > Campus placements (long term).\n\nIf you're at an IIT, build something. Don't just grind LeetCode.\n\n#Startups #IITDelhi",
 "AI can now generate full IIT-JEE level physics problems with solutions.\n\nTeachers who just copy-paste questions are obsolete.\n\nTeachers who mentor, guide thinking, and provide context? Irreplaceable.\n\n#AI #Education #JEE",
 "US MS in CS: ₹50-60 lakh total cost.\n\nStarting salary in US: ₹80-120 lakh/year.\n\nROI in 1-2 years if you land a good job.\n\nBut: H1B lottery is a gamble now.\n\nFactor that in.\n\n#MScUS #StudyAbroad #H1B",
 "The real skill gap in India isn't coding.\n\nIt's:\n→ Written communication\n→ System design thinking\n→ Reading and understanding research papers\n→ Asking good questions\n\nCoding is the easiest part to learn.\n\n#TechIndia #Skills",
 "GATE 2025 syllabus changed for CSE.\n\nNew additions: Machine Learning basics, Cloud Computing.\n\nRemoved: Some older architecture topics.\n\nPSUs still value GATE. Don't write it off.\n\n#GATE2025 #CSE",
 "Free AI resources that are genuinely good:\n1. Andrew Ng's courses (Coursera)\n2. HuggingFace NLP course\n3. Fast.ai\n4. 3Blue1Brown neural net series\n5. Andrej Karpathy's YouTube\n\nNo paid course needed to start.\n\n#AI #FreeResources",
 "Most JEE toppers don't study 16 hours a day.\n\nThey study 6-8 hours of DEEP FOCUS.\n\nDifference:\n→ 16 hrs with phone breaks = 4 hrs actual\n→ 6 hrs deep focus = 6 hrs actual\n\nQuality destroys quantity.\n\n#JEEMain #StudyTips",
 "AI will NOT replace engineers in the next 10 years.\n\nBut engineers who use AI WILL replace engineers who don't.\n\nAdapt or fade.\n\n#AI #TechCareers",
 "The best IIT professors are on YouTube, not in lecture halls.\n\nNPTEL channels, Vipin Sir, Mohit Tyagi.\n\nAccess is no longer the barrier. Discipline is.\n\n#NPTEL #IIT #FreeEducation",
 "Indian PhD stipend: ₹31,000-35,000/month.\n\nUS PhD stipend: ₹2,50,000-4,00,000/month + tuition waiver.\n\nThe gap is 10x. Not 2x. 10x.\n\nThis is why top Indian researchers go abroad.\n\n#PhD #BrainDrain",
 "JEE Main 2025 session 1: 12+ lakh registrations.\n\nOnly ~2.5 lakh will qualify for Advanced.\n\nThat's a 79% rejection rate BEFORE Advanced even starts.\n\nThe filter is brutal. Respect the process.\n\n#JEEMain2025 #Engineering",
 "Canada just tightened student visa rules.\n\n→ Caps on international students\n→ Stricter financial proof\n→ PGWP changes coming\n\nIf you're planning Canada for 2025-26, have a Plan B.\n\n#Canada #StudyAbroad",
 "Why most Indians fail at GRE verbal:\n\nThey memorize 3000 words without understanding USAGE.\n\nBetter approach:\n→ Read The Economist daily\n→ Learn words in context\n→ Practice sentence equivalence\n\n#GRE #StudyAbroad",
 "KVPY is India's most underrated exam.\n\nBenefits:\n→ Fellowship until PhD\n→ Direct IISc/IISER admission\n→ CV boost for foreign unis\n\nMost JEE students ignore it. Don't.\n\n#KVPY #IISc #Scholarship",
 "The Indian EdTech bubble burst. But real winners emerged:\n\n→ PhysicsWallah (profitable, affordable)\n→ Scaler (placement-focused)\n\nThe ones that burned VC money on marketing? Gone.\n\nSustainability > Growth.\n\n#EdTech #India",
 "HuggingFace is the GitHub of AI.\n\nEvery Indian CS student should:\n1. Create an account\n2. Fine-tune a small model\n3. Upload it as a Space\n4. Put it on resume\n\nIt takes 2 hours. Sets you apart.\n\n#HuggingFace #AI #Resume",
 "Top 5 mistakes JEE droppers make:\n1. Same strategy, more hours\n2. Ignoring weak subjects\n3. No test analysis after mocks\n4. Social isolation (burnout)\n5. Comparing with toppers\n\nA smart gap year ≠ a hard gap year.\n\n#JEEDropper #JEE",
 "AI-generated code is good for boilerplate.\n\nIt's terrible for:\n→ System architecture decisions\n→ Debugging race conditions\n→ Understanding business logic\n\nDon't confuse autocomplete with engineering.\n\n#AI #Programming",
 "Open source contribution tip for Indian students:\n\nDon't start with React/Linux kernel.\n\nStart with:\n→ Good first issues on GitHub\n→ Documentation fixes\n→ Test case writing\n\nSmall contributions build confidence.\n\n#OpenSource #GitHub",
 "IISc Bangalore accepts via JEE Advanced, KVPY, GATE/JAM.\n\nIt's NOT an IIT, but it's arguably India's best science institution.\n\n#IISc #Bangalore #Science",
 "The AI job market in India 2025:\n→ ML Engineers: ₹8-25 LPA (fresher)\n→ AI Researchers: ₹12-40 LPA\n→ Data Scientists: ₹6-20 LPA\n\nDon't chase titles. Build skills.\n\n#AIJobs #India #TechCareers",
]

class ContentGenerator:
 def __init__(self, api_key: str):
  self.api_key = api_key
  self.fallback_pool = list(FALLBACK_TWEETS)
  random.shuffle(self.fallback_pool)
  self.fallback_index = 0
  self.history = self._load_history()

 def _load_history(self) -> list:
  if os.path.exists(HISTORY_FILE):
   try:
    with open(HISTORY_FILE, "r", encoding="utf-8") as f:
     return json.load(f)
   except Exception:
    return []
  return []

 def _save_history(self):
  with open(HISTORY_FILE, "w", encoding="utf-8") as f:
   json.dump(self.history[-100:], f, ensure_ascii=False, indent=2)

 def _is_duplicate(self, tweet: str, threshold: float = 0.7) -> bool:
  new_words = set(tweet.lower().split())
  for old in self.history[-30:]:
   old_words = set(old.lower().split())
   if not old_words: continue
   overlap = len(new_words & old_words) / max(len(new_words), 1)
   if overlap > threshold: return True
  return False

 async def generate_tweet(self, recent: list = None) -> str:
  if self.api_key:
   for _ in range(3):
    tweet = await self._groq_generate(recent)
    if tweet and len(tweet) > 20:
     tweet = self._clean_tweet(tweet)
     if not self._is_duplicate(tweet):
      self.history.append(tweet)
      self._save_history()
      return tweet
    logger.info("Duplicate detected, regenerating...")

  logger.info("Using fallback tweet pool")
  for _ in range(len(self.fallback_pool)):
   tweet = self.fallback_pool[self.fallback_index % len(self.fallback_pool)]
   self.fallback_index += 1
   if not self._is_duplicate(tweet):
    self.history.append(tweet)
    self._save_history()
    return tweet
  return self.fallback_pool[0]

 async def _groq_generate(self, recent: list = None) -> str | None:
  topic = random.choice(TOPICS)
  user_msg = f"Write ONE tweet about: {topic}"
  if recent:
   user_msg += f"\n\nThese were posted recently — do NOT repeat:\n" + "\n".join(f"- {t[:80]}" for t in recent[-5:])

  payload = {"model": GROQ_MODEL, "messages": [
   {"role": "system", "content": SYSTEM_PROMPT},
   {"role": "user", "content": user_msg},
  ], "max_tokens": 120, "temperature": 0.95, "top_p": 0.9}

  try:
   async with httpx.AsyncClient(timeout=30) as client:
    resp = await client.post("https://api.groq.com/openai/v1/chat/completions",
     headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}, json=payload)
    if resp.status_code == 429:
     logger.warning("Groq rate limited, trying fallback model...")
     payload["model"] = GROQ_FALLBACK_MODEL
     resp = await client.post("https://api.groq.com/openai/v1/chat/completions",
      headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}, json=payload)
    if resp.status_code != 200:
     logger.error(f"Groq API error {resp.status_code}")
     return None
    return resp.json()["choices"][0]["message"]["content"].strip()
  except Exception as e:
   logger.error(f"Groq API error: {e}")
   return None

 def _clean_tweet(self, tweet: str) -> str:
  if (tweet.startswith('"') and tweet.endswith('"')) or (tweet.startswith("'") and tweet.endswith("'")):
   tweet = tweet[1:-1]
  lines = [line.strip() for line in tweet.split("\n")]
  tweet = "\n".join(lines).strip()
  if len(tweet) > MAX_TWEET_LENGTH:
   tweet = tweet[:MAX_TWEET_LENGTH - 3].rstrip() + "..."
  return tweet
