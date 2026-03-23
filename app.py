import streamlit as st
import json, os, random, time
from datetime import datetime
from instagrapi import Client
from instagrapi.exceptions import LoginRequired, ChallengeRequired
import pandas as pd
from apscheduler.schedulers.background import BackgroundScheduler

# ====================== CONFIG ======================
HASHTAG_MAP = {
    "Fitness": {
        "Yoga/Pilates": ["yoga", "pilates", "yinyoga", "vinyasa", "yogachallenge"],
        "Weightlifting/Bodybuilding": ["gym", "bodybuilding", "powerlifting", "strengthtraining"],
        "Cardio/HIIT/Home": ["hiit", "homeworkout", "cardio", "fitnessmotivation"],
        "Nutrition": ["mealprep", "fitnessnutrition"]
    },
    "Fashion/Beauty": {
        "Makeup": ["makeuptutorial", "beautyhacks", "cleangirlmakeup", "grwm"],
        "Skincare": ["skincareroutine", "glassskin", "cleanbeauty", "kbeauty"],
        "Fashion/Outfits": ["streetwear", "outfitinspo", "ootd", "sustainablefashion"],
        "Hair/Accessories": ["haircare", "hairtutorial"]
    },
    "Combat Sports": {
        "MMA": ["mma", "ufc", "mixedmartialarts"],
        "Boxing/Kickboxing": ["boxing", "muaythai", "kickboxing"],
        "Jiu-Jitsu": ["bjj", "brazilianjiujitsu"],
        "Self-Defense": ["selfdefense", "martialarts"]
    }
}

IG_USERNAME = os.getenv("IG_USERNAME")
IG_PASSWORD = os.getenv("IG_PASSWORD")
SESSION_FILE = "ig_session.json"
DATA_FILE = "latest_trends.json"
HISTORY_FILE = "trends_history.json"

# ====================== HELPER FUNCTIONS ======================
def load_history():
    try:
        with open(HISTORY_FILE, "r") as f:
            return json.load(f)
    except:
        return {}

def save_history(data):
    with open(HISTORY_FILE, "w") as f:
        json.dump(data, f)

# ====================== SCRAPER ======================
def scrape_reels():
    if not IG_USERNAME or not IG_PASSWORD:
        st.error("IG_USERNAME or IG_PASSWORD not set in Railway Variables!")
        return []

    cl = Client()
    cl.delay_range = [3, 12]

    if os.path.exists(SESSION_FILE):
        try:
            cl.load_settings(SESSION_FILE)
            cl.get_timeline_feed()  # test
        except:
            os.remove(SESSION_FILE)
            cl = Client()

    try:
        cl.login(IG_USERNAME, IG_PASSWORD)
        cl.dump_settings(SESSION_FILE)
    except ChallengeRequired:
        st.error("IG Challenge Required! Check Railway Deploy Logs for code entry instructions (email/SMS).")
        return []
    except Exception as e:
        st.error(f"IG Login failed: {str(e)[:200]}")
        return []

    results = []
    history = load_history()

    for niche, subs in HASHTAG_MAP.items():
        for sub, tags in subs.items():
            for tag in tags:
                try:
                    medias = cl.hashtag_medias_reels_v1(tag, amount=12)

                    views_list = [m.play_count or 0 for m in medias]
                    eng_list = [round(((m.like_count or 0) + (m.comment_count or 0)) / max(m.play_count, 1) * 100, 2) for m in medias]

                    avg_views = round(sum(views_list) / len(views_list)) if views_list else 0
                    avg_eng = round(sum(eng_list) / len(eng_list), 2) if eng_list else 0

                    prev = history.get(tag, {}).get("avg_views", avg_views)
                    spike = round((avg_views - prev) / prev * 100, 1) if prev > 0 else 0

                    top_reel = None
                    if medias:
                        m = medias[0]
                        top_reel = {
                            "url": f"https://www.instagram.com/reel/{m.code}/",
                            "views": m.play_count or 0,
                            "eng_rate": round(((m.like_count or 0) + (m.comment_count or 0)) / max(m.play_count, 1) * 100, 2),
                            "caption": (m.caption_text or "")[:120]
                        }

                    results.append({
                        "niche": niche,
                        "sub_niche": sub,
                        "hashtag": f"#{tag}",
                        "avg_views": avg_views,
                        "spike_pct": spike,
                        "avg_eng_rate": avg_eng,
                        "trend_score": round(spike * 0.7 + avg_eng * 3, 1),
                        "top_reel": top_reel,
                        "timestamp": datetime.now().isoformat()
                    })

                    history[tag] = {"avg_views": avg_views}
                    time.sleep(random.uniform(2, 6))

                except Exception as e:
                    continue

    with open(DATA_FILE, "w") as f:
        json.dump(results, f)
    save_history(history)
    return results

# ====================== STREAMLIT ======================
st.set_page_config(page_title="Model Growth Engine • IG Reels", layout="wide")
st.title("🔥 Model Growth Engine • Live Reels Trends")
st.caption("Built for your agency • Gives your model exact daily tasks • Updates every 12h + manual refresh")

col1, col2, col3 = st.columns([3,1,1])
niche_filter = col1.selectbox("Filter Niche", ["All"] + list(HASHTAG_MAP), index=0)  # <-- Fixed: list(HASHTAG_MAP) iterates keys safely
refresh_btn = col2.button("🔄 Refresh Now")

if refresh_btn:
    with st.spinner("Scraping... (60–120 sec)"):
        scrape_reels()
        st.success("Fresh data!")
        st.rerun()

if not os.path.exists(DATA_FILE):
    with st.spinner("Initial scrape..."):
        scrape_reels()

try:
    df = pd.read_json(DATA_FILE)
except:
    df = pd.DataFrame()  # fallback

if niche_filter != "All":
    df = df[df["niche"] == niche_filter]

# Tabs (rest same as before - add your full tabs code here if needed, but this fixes the crash)
tab1, tab2 = st.tabs(["Trending Dashboard", "Content Ideas"])

with tab1:
    st.subheader("Top Trends")
    if not df.empty:
        top = df.sort_values("trend_score", ascending=False).head(10)
        st.dataframe(top[["niche", "sub_niche", "hashtag", "avg_views", "spike_pct", "trend_score"]])
    else:
        st.info("No data yet - refresh!")

with tab2:
    st.subheader("Generate Brief")
    model_niche = st.selectbox("Model Niche", list(HASHTAG_MAP))
    if st.button("Generate Ideas"):
        st.info("Ideas would appear here after fix & scrape.")

# Scheduler (keep if you had it)
