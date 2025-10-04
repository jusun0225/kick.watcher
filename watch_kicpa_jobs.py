# -*- coding: utf-8 -*-
import os, json, hashlib, requests
from urllib.parse import urljoin
from bs4 import BeautifulSoup

# 감시 대상 페이지 (KICPA 구인 관련 메뉴 루트)
KICPA_URL = "https://www.kicpa.or.kr/portal/default/kicpa/gnb/kr_pc/menu05/menu09/menu07.page"

# 상태 파일(중복 발송 방지)
STATE_FILE = os.environ.get("STATE_FILE", ".state/kicpa_state.json")

# ntfy 설정(폰 푸시)
NTFY_URL   = os.environ.get("NTFY_URL", "https://ntfy.sh")
NTFY_TOPIC = os.environ.get("NTFY_TOPIC")  # 예: jusun-kicpa-9am-2f7c

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; KICPA-Watcher/ntfy; +https://github.com/)"
}

MAX_ITEMS_TO_CHECK = int(os.environ.get("MAX_ITEMS", "60"))

def _ensure_state_dir():
    d = os.path.dirname(STATE_FILE)
    if d and not os.path.exists(d):
        os.makedirs(d, exist_ok=True)

def load_state():
    _ensure_state_dir()
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"sent_ids": []}

def save_state(state):
    _ensure_state_dir()
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)

def stable_id(url: str):
    h = hashlib.sha256()
    h.update(url.encode("utf-8"))
    return h.hexdigest()[:16]

def send_push(title: str, body: str):
    if not NTFY_TOPIC:
        print("NTFY_TOPIC not set; skip push"); return
    try:
        requests.post(
            f"{NTFY_URL.rstrip('/')}/{NTFY_TOPIC}",
            data=body.encode("utf-8"),
            headers={"Title": title},
            timeout=20
        )
    except Exception as e:
        print("ntfy push failed:", repr(e))

def format_push_list(items):
    # ntfy는 텍스트만 보내면 됨
    lines = []
    for it in items:
        lines.append(f"• {it['title']}\n{it['url']}")
    return "\n\n".join(lines)

def fetch_list():
    r = requests.get(KICPA_URL, headers=HEADERS, timeout=30)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")

    items = []
    for a in soup.select("a[href]"):
        title = a.get_text(strip=True)
        href = a.get("href", "")
        if not title or not href:
            continue
        link = urljoin(KICPA_URL, href)
        items.append({"title": title, "url": link})

    # 중복 제거
    dedup = {}
    for it in items:
        dedup[(it["title"], it["url"])] = it
    items = list(dedup.values())
    return items[:MAX_ITEMS_TO_CHECK]

def main():
    state = load_state()
    sent = set(state.get("sent_ids", []))

    candidates = fetch_list()

    # 키워드 필터 없이, 처음 보는 글이면 전부 알림
    new_hits = []
    for it in candidates:
        iid = stable_id(it["url"])
        if iid not in sent:
            it["id"] = iid
            new_hits.append(it)

    if new_hits:
        body = format_push_list(new_hits)
        send_push("[KICPA] 새 공고 감지", body)
        for it in new_hits:
            sent.add(it["id"])
        state["sent_ids"] = list(sent)
        save_state(state)
    else:
        print("no new posts")

if __name__ == "__main__":
    main()
