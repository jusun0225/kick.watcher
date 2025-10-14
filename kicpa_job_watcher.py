# -*- coding: utf-8 -*-
"""
KICPA 채용공고 감시 시스템 (ntfy 버전)
- 모든 신규 공고 감지
- 중복 방지(state.json)
- GitHub Actions에서 10분마다 실행 가능
"""
import os, requests, json, hashlib, datetime
from bs4 import BeautifulSoup
from urllib.parse import urljoin

# ===== 설정 =====
URL = "https://www.kicpa.or.kr/portal/default/kicpa/gnb/kr_pc/menu05/menu09/menu07.page"
BASE = "https://www.kicpa.or.kr"
STATE_FILE = ".state/kicpa_jobs_state.json"

NTFY_URL = os.environ.get("NTFY_URL", "https://ntfy.sh")
NTFY_TOPIC = os.environ.get("NTFY_TOPIC", "jusun-kicpa-jobs")

HEADERS = {"User-Agent": "Mozilla/5.0 (KICPAJobWatcher/1.0)"}


# ===== 함수 =====
def load_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"seen_ids": []}


def save_state(state):
    os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def make_id(title, href):
    h = hashlib.sha256()
    h.update((title.strip() + "|" + href.strip()).encode("utf-8"))
    return h.hexdigest()[:16]


def fetch_job_list():
    r = requests.get(URL, headers=HEADERS, timeout=30)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")

    # 표 안의 링크 요소 추출
    items = []
    for a in soup.select("table a[href]"):
        title = a.get_text(strip=True)
        href = urljoin(BASE, a["href"])
        if title:
            items.append({"title": title, "url": href})
    return items


def send_push(title, body):
    try:
        requests.post(
            f"{NTFY_URL.rstrip('/')}/{NTFY_TOPIC}",
            data=body.encode("utf-8"),
            headers={"Title": title},
            timeout=10,
        )
    except Exception as e:
        print("ntfy error:", e)


# ===== 메인 =====
def main():
    now = datetime.datetime.utcnow() + datetime.timedelta(hours=9)
    print(f"[{now}] Checking KICPA job board...")

    state = load_state()
    seen = set(state.get("seen_ids", []))
    jobs = fetch_job_list()

    new_posts = []
    for j in jobs:
        jid = make_id(j["title"], j["url"])
        if jid not in seen:
            new_posts.append(j)
            seen.add(jid)

    if new_posts:
        body_lines = [f"• {j['title']}\n{j['url']}" for j in new_posts[:10]]
        body = "\n\n".join(body_lines)
        send_push("📢 KICPA 신규 채용공고", body)
        print("Sent alert for", len(new_posts), "new posts.")
    else:
        print("No new posts found.")

    save_state({"seen_ids": list(seen)})


if __name__ == "__main__":
    main()
