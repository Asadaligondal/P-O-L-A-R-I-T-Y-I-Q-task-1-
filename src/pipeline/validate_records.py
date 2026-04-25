"""
Step 1: Automated cross-checks against public endpoints.

- LinkedIn URL: HTTP GET; records status and whether response looks like a login wall.
- SEC EDGAR: POST to SEC full-text search index (best-effort; API may change).
- Google News: RSS feed item count for the family office name (no scraping).

Requires outbound HTTPS. Set SEC_USER_AGENT per https://www.sec.gov/os/webmaster-faq#code-support
"""
from __future__ import annotations

import os
import time
import urllib.parse
import xml.etree.ElementTree as ET
from typing import Any

import pandas as pd
import requests

from .text_utils import clean_str

SEC_SEARCH_URL = "https://efts.sec.gov/LATEST/search-index"
GOOGLE_NEWS_RSS = "https://news.google.com/rss/search"


def _http_headers() -> dict[str, str]:
    ua = clean_str(os.environ.get("SEC_USER_AGENT", ""))
    if not ua:
        ua = "FamilyOfficeDatasetBot/1.0 (replace-with-your-email@domain.invalid)"
    return {"User-Agent": ua, "Accept": "application/json", "Content-Type": "application/json"}


def _rss_headers() -> dict[str, str]:
    return {"User-Agent": _http_headers()["User-Agent"]}


def check_linkedin_url(url: str, timeout: float = 12.0) -> dict[str, Any]:
    u = clean_str(url)
    if not u or "linkedin.com" not in u.lower():
        return {"linkedin_http_status": "", "linkedin_resolves": "n/a", "linkedin_note": "no_url"}
    try:
        r = requests.get(u, timeout=timeout, allow_redirects=True, headers=_rss_headers())
        final = (r.url or "").lower()
        body_preview = (r.text or "")[:2000].lower()
        login_wall = "authwall" in final or "login" in final or "sign in" in body_preview
        ok = r.status_code == 200 and not login_wall
        note = "login_or_authwall" if login_wall else "http_ok" if r.status_code == 200 else f"http_{r.status_code}"
        return {
            "linkedin_http_status": str(r.status_code),
            "linkedin_resolves": "yes" if ok else "no",
            "linkedin_note": note,
        }
    except requests.RequestException as e:
        return {"linkedin_http_status": "error", "linkedin_resolves": "error", "linkedin_note": str(e)[:200]}


def sec_search_hit_count(query: str, timeout: float = 20.0) -> dict[str, Any]:
    q = clean_str(query)
    if not q:
        return {"sec_hit_count": "", "sec_note": "empty_query"}
    payload = {"keysTyped": q, "navigator": True, "from": "0", "size": "25"}
    try:
        r = requests.post(SEC_SEARCH_URL, json=payload, headers=_http_headers(), timeout=timeout)
        if r.status_code != 200:
            return {"sec_hit_count": "", "sec_note": f"http_{r.status_code}"}
        data = r.json()
        hits = data.get("hits") or {}
        total = hits.get("total")
        count = 0
        if isinstance(total, dict) and "value" in total:
            count = int(total["value"])
        elif isinstance(total, int):
            count = total
        if count == 0:
            count = len(hits.get("hits", []) or [])
        return {"sec_hit_count": str(count), "sec_note": "ok"}
    except Exception as e:
        return {"sec_hit_count": "", "sec_note": str(e)[:200]}


def google_news_item_count(query: str, timeout: float = 15.0) -> dict[str, Any]:
    q = clean_str(query)
    if not q:
        return {"news_rss_items": "", "news_note": "empty_query"}
    params = {"q": q, "hl": "en-US", "gl": "US", "ceid": "US:en"}
    url = f"{GOOGLE_NEWS_RSS}?{urllib.parse.urlencode(params)}"
    try:
        r = requests.get(url, timeout=timeout, headers=_rss_headers())
        if r.status_code != 200:
            return {"news_rss_items": "", "news_note": f"http_{r.status_code}"}
        root = ET.fromstring(r.content)
        items = root.findall(".//item")
        return {"news_rss_items": str(len(items)), "news_note": "ok"}
    except Exception as e:
        return {"news_rss_items": "", "news_note": str(e)[:200]}


def programmatic_confidence_simple(li_res: str, sec_hits: str, news_items: str) -> str:
    li = clean_str(li_res).lower()
    try:
        sec_n = int(sec_hits) if clean_str(sec_hits).isdigit() else 0
    except ValueError:
        sec_n = 0
    try:
        news_n = int(news_items) if clean_str(news_items).isdigit() else 0
    except ValueError:
        news_n = 0
    score = 0
    if li == "yes":
        score += 2
    if sec_n > 0:
        score += 1
    if news_n > 0:
        score += 1
    if score >= 3:
        return "AUTO_HIGH"
    if score >= 1:
        return "AUTO_MEDIUM"
    return "AUTO_LOW"


def run_validation_columns(df: pd.DataFrame, pause_sec: float = 0.35) -> pd.DataFrame:
    out = df.copy()
    li_status: list[str] = []
    li_ok: list[str] = []
    li_note: list[str] = []
    sec_cnt: list[str] = []
    sec_note: list[str] = []
    news_cnt: list[str] = []
    news_note: list[str] = []
    auto_conf: list[str] = []

    for _, row in out.iterrows():
        li = check_linkedin_url(clean_str(row.get("Principal LinkedIn", "")))
        li_status.append(li["linkedin_http_status"])
        li_ok.append(li["linkedin_resolves"])
        li_note.append(li["linkedin_note"])

        name = clean_str(row.get("FO Name", ""))
        se = sec_search_hit_count(name)
        sec_cnt.append(se["sec_hit_count"])
        sec_note.append(se["sec_note"])

        gn = google_news_item_count(f'"{name}" family office')
        news_cnt.append(gn["news_rss_items"])
        news_note.append(gn["news_note"])

        auto_conf.append(programmatic_confidence_simple(li["linkedin_resolves"], se["sec_hit_count"], gn["news_rss_items"]))
        time.sleep(pause_sec)

    out["linkedin_http_status"] = li_status
    out["linkedin_resolves"] = li_ok
    out["linkedin_check_note"] = li_note
    out["sec_edgar_hit_count"] = sec_cnt
    out["sec_check_note"] = sec_note
    out["google_news_rss_item_count"] = news_cnt
    out["google_news_check_note"] = news_note
    out["programmatic_confidence"] = auto_conf
    return out


def add_skipped_validation_columns(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    n = len(out)
    out["linkedin_http_status"] = [""] * n
    out["linkedin_resolves"] = ["skipped"] * n
    out["linkedin_check_note"] = ["skipped"] * n
    out["sec_edgar_hit_count"] = [""] * n
    out["sec_check_note"] = ["skipped"] * n
    out["google_news_rss_item_count"] = [""] * n
    out["google_news_check_note"] = ["skipped"] * n
    out["programmatic_confidence"] = ["SKIPPED"] * n
    return out
