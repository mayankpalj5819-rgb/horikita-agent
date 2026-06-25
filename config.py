import os

GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
X_EMAIL = os.environ.get("X_EMAIL", "")
X_PASSWORD = os.environ.get("X_PASSWORD", "")
X_USERNAME = os.environ.get("X_USERNAME", "")

COOKIE_FILE = "/data/cookies.json"
LOG_FILE = "/data/bot.log"
HISTORY_FILE = "/data/tweet_history.json"

BASE_INTERVAL = 600
JITTER_RANGE = 120

GROQ_MODEL = "llama-3.3-70b-versatile"
GROQ_FALLBACK_MODEL = "llama-3.1-8b-instant"

TOPICS = [
 "IITs — rankings, campus culture, placements, research output, notable alumni, fest highlights",
 "JEE Advanced & JEE Main — preparation strategies, pattern analysis, topper tips, subject-wise weightage",
 "Artificial Intelligence — latest breakthroughs, new models, tools, tutorials, AI in education",
 "Machine Learning & Data Science — practical projects, Kaggle, career paths in India",
 "Education in India — NEP 2020 updates, UGC changes, state vs central universities, skill gap",
 "Study abroad — US/UK/Canada/Germany admissions, GRE/TOEFL/IELTS tips, scholarships for Indians",
 "Tech careers in India — product vs service companies, startup salaries, remote work, FAANG prep",
 "Coding culture — competitive programming (Codeforces, LeetCode), open source, hackathons in India",
 "Science & research — Indian researchers, ISRO/DRDO updates, Nobel connections, lab-to-market",
 "EdTech — Indian edtech landscape, online courses, UPSC prep tech, AI tutors",
 "IIT-specific — each IIT's unique strength (IITB coding, IITM research, IITD design, IITKGP heritage)",
 "Exams beyond JEE — CAT, GATE, UGC NET, Olympiads, KVPY — strategy and updates",
]

MAX_TWEET_LENGTH = 275
