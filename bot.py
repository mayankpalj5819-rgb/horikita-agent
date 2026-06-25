"""X Auto-Poster — X API v2 via OAuth 1.0a (requests_oauthlib)."""
import os, json, random, logging
import httpx
from requests_oauthlib import OAuth1Session

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s", datefmt="%H:%M:%S")
log = logging.getLogger(__name__)

# ── X API Credentials ──
API_KEY = os.environ["X_API_KEY"]
API_SECRET = os.environ["X_API_SECRET"]
ACCESS_TOKEN = os.environ["X_ACCESS_TOKEN"]
ACCESS_SECRET = os.environ["X_ACCESS_SECRET"]
GROQ_KEY = os.environ["GROQ_API_KEY"]

HISTORY_FILE = "data/tweet_history.json"
os.makedirs("data", exist_ok=True)

TOPICS = [
 "IITs — rankings, campus culture, placements, research, notable alumni",
 "JEE Advanced & JEE Main — strategies, topper tips, subject weightage",
 "AI breakthroughs — new models, tools, tutorials, AI in education",
 "Machine Learning & Data Science — projects, Kaggle, career paths India",
 "Study abroad — US/UK/Canada/Germany admissions, GRE/TOEFL/IELTS tips",
 "Tech careers India — product vs service, startup salaries, FAANG prep",
 "Coding culture — competitive programming, open source, hackathons",
 "EdTech — Indian edtech, online courses, UPSC prep, AI tutors",
 "Science & research — ISRO/DRDO, Indian researchers, Nobel laureates",
 "Exams — CAT, GATE, UGC NET, Olympiads, KVPY strategy",
]

SYSTEM_PROMPT = """You are a sharp tech-education influencer on X. Audience: Indian students, JEE aspirants, IITians.
Rules: Under 260 chars. 1-2 emojis max. 1-2 relevant hashtags. Use real data. No filler. Output ONLY the tweet."""

FALLBACK = [
 "IIT Bombay placements 2024: 300+ PPOs before finals. Secret? Students build projects from 2nd year, not 4th. Start early. #IIT #Placements",
 "JEE Advanced tests decision-making under pressure, not just knowledge. Top rankers attempt ~70% of questions, not 100%. Accuracy > Speed. #JEEAdvanced",
 "Free AI resources for Indian students: Andrew Ng (Coursera), HuggingFace NLP, Fast.ai, 3Blue1Brown, Karpathy YouTube. Zero cost. #AI #FreeLearning",
 "ISRO Chandrayaan-3: ₹615 crore. Avatar movie: ₹2,300 crore. India does more with less. Always has. #ISRO #Space",
 "Germany public universities: ₹0 tuition. Living: ₹50-70k/month. Compare to ₹15L/year private Indian unis. Do the math. #StudyAbroad #Germany",
 "Most JEE toppers study 6-8 hours of DEEP FOCUS, not 16 hours. Quality destroys quantity. Phone breaks kill real study time. #JEE #StudyTips",
 "AI won't replace engineers in 10 years. But engineers who USE AI will replace those who don't. Same as calculators vs mathematicians. #AI",
 "CAT 2024: 66 questions, 120 minutes. Toppers skip strategically. Selection > Solution. #CAT2024 #MBA",
 "HuggingFace = GitHub of AI. Every CS student: make account → fine-tune model → deploy Space → add resume. 2 hours. Sets you apart. #AI #Resume",
 "Indian PhD stipend: ₹35k/month. US PhD: ₹3 lakh/month + tuition waiver. 10x gap. Brain drain math. #PhD #Research",
]


def load_history():
    try:
        with open(HISTORY_FILE) as f: return json.load(f)
    except: return []

def save_history(h):
    with open(HISTORY_FILE, "w") as f: json.dump(h[-50:], f)

def is_duplicate(tweet, history, threshold=0.6):
    new_words = set(tweet.lower().split())
    for old in history[-20:]:
        overlap = len(new_words & set(old.lower().split())) / max(len(new_words), 1)
        if overlap > threshold: return True
    return False


def generate_tweet(history):
    if GROQ_KEY:
        for _ in range(3):
            topic = random.choice(TOPICS)
            user_msg = f"Write ONE tweet about: {topic}"
            if history:
                user_msg += "\n\nRecent tweets (DON'T repeat):\n" + "\n".join(f"- {t[:80]}" for t in history[-5:])
            try:
                r = httpx.post("https://api.groq.com/openai/v1/chat/completions",
                    headers={"Authorization": f"Bearer {GROQ_KEY}", "Content-Type": "application/json"},
                    json={"model": "llama-3.3-70b-versatile", "max_tokens": 120, "temperature": 0.95,
                          "messages": [{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": user_msg}]},
                    timeout=25)
                if r.status_code == 200:
                    tweet = r.json()["choices"][0]["message"]["content"].strip()
                    tweet = tweet.strip('"').strip("'")
                    if len(tweet) < 20: continue
                    if not is_duplicate(tweet, history):
                        return tweet[:275]
            except: continue

    pool = list(FALLBACK); random.shuffle(pool)
    for t in pool:
        if not is_duplicate(t, history): return t[:275]
    return pool[0][:275]


def post_tweet(text):
    """Post via X API v2 using requests_oauthlib (proper OAuth)."""
    oauth = OAuth1Session(
        client_key=API_KEY,
        client_secret=API_SECRET,
        resource_owner_key=ACCESS_TOKEN,
        resource_owner_secret=ACCESS_SECRET,
    )
    
    r = oauth.post("https://api.twitter.com/2/tweets", json={"text": text}, timeout=20)
    
    if r.status_code in (200, 201):
        tweet_id = r.json().get("data", {}).get("id", "unknown")
        log.info(f"✅ Posted! ID: {tweet_id}")
        return True
    else:
        log.error(f"❌ X API {r.status_code}: {r.text[:400]}")
        return False


def main():
    log.info("🦞 X Bot (API v2) starting...")
    history = load_history()
    tweet = generate_tweet(history)
    log.info(f"Tweet ({len(tweet)} chars): {tweet[:60]}...")
    
    ok = post_tweet(tweet)
    if ok:
        history.append(tweet)
        save_history(history)
        log.info(f"Done! Total: {len(history)} posts")
    else:
        exit(1)

if __name__ == "__main__":
    main()
