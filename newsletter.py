from tavily import TavilyClient
from groq import Groq
import resend
import json
import os
import re
import time
from datetime import datetime
import pytz

# ── Config ────────────────────────────────────────────────────────────────────
TAVILY_API_KEY = os.environ["TAVILY_API_KEY"]
GROQ_API_KEY   = os.environ["GROQ_API_KEY"]
RESEND_API_KEY = os.environ["RESEND_API_KEY"]
FROM_EMAIL     = os.environ["FROM_EMAIL"]
FROM_NAME      = "Paid Social Edge"
SUBSCRIBERS_FILE = "subscribers.json"
GROQ_MODEL     = "llama-3.3-70b-versatile"

CST = pytz.timezone("US/Central")

SEARCH_QUERIES = [
    "Meta Facebook Instagram ads new features updates this week",
    "Google Ads YouTube advertising changes announcements this week",
    "TikTok ads new features advertising updates this week",
    "LinkedIn ads Pinterest Snapchat Reddit advertising news this week",
    "paid social advertising brand campaign case study results 2026",
    "digital advertising measurement attribution research report 2026",
    "ad tech programmatic advertising industry news acquisition 2026",
]

COMPILE_PROMPT = """Today is {today}.

You are a senior paid social strategist compiling the weekly "Paid Social Edge" briefing for a Fortune 100 company's paid social leadership team — Directors, VPs, and senior media buyers managing nine-figure media budgets. They are fluent in every platform. They need signal, not basics.

Below are raw search results gathered this week. Your job is to:
1. Identify the 5-8 most genuinely impactful stories for a senior paid social audience
2. Filter out noise, tips, evergreen content, and anything that does not change strategy
3. Write tight, intelligent summaries with real implications
4. Assign each a concrete "edge" - one specific action, test, or watch item

QUALITY BAR - include ONLY if ALL are true:
- Published in the last 7-10 days
- A VP of Paid Social at a Fortune 100 would want to know this
- Changes how you would structure, run, or measure campaigns - or reveals competitive intel
- Substantive enough to raise in a media strategy meeting

EXCLUDE:
- Tips, how-tos, beginner content
- Evergreen articles with fresh dates
- Platform PR with no actual product/policy change
- Stories with no paid social implication
- Anything a competent senior buyer already knows

SEARCH RESULTS:
{search_results}

OUTPUT: Return ONLY a valid JSON object. No markdown fences, no preamble, no explanation.

{{"week_of": "{today}", "opening_line": "1-2 punchy sentences capturing what defined this week in paid social. Written like a briefing memo opener, not a blog intro.", "items": [{{"category": "Meta Ads | Google/YouTube | TikTok | LinkedIn | Other Platform | Brand Campaign | Research & Data | Industry Move", "headline": "Sharp specific headline. No clickbait.", "summary": "2-4 sentences. What happened and why it matters for large-scale paid social. Be specific - include numbers, product names, or mechanics where available.", "edge": "One concrete action, test, or watch item for a Fortune 100 paid social team. Specific, not generic.", "source_url": "URL of the primary source", "source_name": "Publication or source name"}}]}}"""


def run_searches() -> str:
    tavily = TavilyClient(api_key=TAVILY_API_KEY)
    all_results = []
    for i, query in enumerate(SEARCH_QUERIES, 1):
        print(f"  -> Search {i}/{len(SEARCH_QUERIES)}: {query[:55]}...")
        try:
            resp = tavily.search(query=query, search_depth="advanced", max_results=5, include_raw_content=False)
            for r in resp.get("results", []):
                all_results.append(
                    f"TITLE: {r.get('title','')}\nURL: {r.get('url','')}\nDATE: {r.get('published_date','unknown')}\nBODY: {r.get('content','')[:600]}\n---"
                )
            time.sleep(0.5)
        except Exception as e:
            print(f"    Warning: Search failed: {e}")
    return "\n\n".join(all_results)


def compile_newsletter(search_results: str) -> dict:
    groq = Groq(api_key=GROQ_API_KEY)
    today = datetime.now(CST).strftime("%B %d, %Y")
    prompt = COMPILE_PROMPT.format(today=today, search_results=search_results)
    print("  -> Compiling with Groq (Llama 3.3 70B)...")
    response = groq.chat.completions.create(
        model=GROQ_MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3,
        max_tokens=3000,
    )
    raw = response.choices[0].message.content
    clean = re.sub(r"```(?:json)?|```", "", raw).strip()
    match = re.search(r"\{.*\}", clean, re.DOTALL)
    if not match:
        raise ValueError(f"No JSON found in response:\n{raw[:500]}")
    return json.loads(match.group())


def research_newsletter() -> dict:
    return compile_newsletter(run_searches())


CATEGORY_COLORS = {
    "Meta Ads": "#1877F2", "Google/YouTube": "#EA4335", "TikTok": "#2B2B2B",
    "LinkedIn": "#0A66C2", "Other Platform": "#6366F1", "Brand Campaign": "#7C3AED",
    "Research & Data": "#059669", "Industry Move": "#D97706",
}
DEFAULT_COLOR = "#4B5563"


def _item_html(item):
    cat = item.get("category", "Update")
    color = CATEGORY_COLORS.get(cat, DEFAULT_COLOR)
    url = item.get("source_url", "#")
    src = item.get("source_name", "Source")
    return f"""<table width="100%" cellpadding="0" cellspacing="0" border="0" style="background:#ffffff;border-radius:10px;border-left:4px solid {color};box-shadow:0 1px 4px rgba(0,0,0,0.07);margin-bottom:20px;"><tr><td style="padding:22px 26px;"><span style="display:inline-block;background:{color};color:#fff;font-size:10px;font-weight:700;letter-spacing:0.8px;padding:3px 10px;border-radius:20px;text-transform:uppercase;margin-bottom:12px;">{cat}</span><h3 style="margin:0 0 10px;font-size:16px;font-weight:700;color:#111827;line-height:1.45;">{item.get('headline','')}</h3><p style="margin:0 0 14px;font-size:14px;color:#374151;line-height:1.75;">{item.get('summary','')}</p><table cellpadding="0" cellspacing="0" border="0" width="100%" style="margin-bottom:14px;"><tr><td style="background:#F0FDF4;border-radius:7px;padding:11px 16px;"><span style="font-size:11px;font-weight:700;color:#059669;text-transform:uppercase;letter-spacing:0.6px;">Your Edge</span><p style="margin:5px 0 0;font-size:13px;color:#065F46;line-height:1.65;">{item.get('edge','')}</p></td></tr></table><a href="{url}" style="font-size:13px;color:{color};text-decoration:none;font-weight:600;">Read full story -> {src}</a></td></tr></table>"""


def build_email_html(data):
    now = datetime.now(CST)
    date_str = now.strftime("%B %d, %Y")
    week_num = now.isocalendar()[1]
    opening = data.get("opening_line", "Your weekly paid social intelligence briefing.")
    items_html = "\n".join(_item_html(i) for i in data.get("items", []))
    count = len(data.get("items", []))
    return f"""<!DOCTYPE html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Paid Social Edge Week {week_num}</title></head><body style="margin:0;padding:0;background:#ECEEF2;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;"><table width="100%" cellpadding="0" cellspacing="0" border="0"><tr><td align="center" style="padding:36px 16px;"><table width="620" cellpadding="0" cellspacing="0" border="0" style="max-width:620px;width:100%;"><tr><td style="background:linear-gradient(135deg,#0F0C29 0%,#1a1060 50%,#24243e 100%);border-radius:12px 12px 0 0;padding:36px 40px 32px;"><p style="margin:0 0 6px;font-size:11px;font-weight:700;letter-spacing:2.5px;text-transform:uppercase;color:#818CF8;">WEEK {week_num} &nbsp;·&nbsp; {date_str} &nbsp;·&nbsp; {count} STORIES</p><h1 style="margin:0 0 14px;font-size:30px;font-weight:800;color:#ffffff;letter-spacing:-0.5px;">Paid Social Edge</h1><p style="margin:0;font-size:15px;color:#C7D2FE;line-height:1.7;max-width:480px;">{opening}</p></td></tr><tr><td style="background:#4F46E5;height:3px;"></td></tr><tr><td style="background:#ECEEF2;padding:28px 16px 8px;">{items_html}</td></tr><tr><td style="background:#1F2937;border-radius:0 0 12px 12px;padding:24px 40px;text-align:center;"><p style="margin:0 0 6px;font-size:13px;color:#9CA3AF;font-weight:500;">Paid Social Edge</p><p style="margin:0;font-size:12px;color:#6B7280;line-height:1.6;">Delivered every Tuesday at 6 AM CST</p></td></tr></table></td></tr></table></body></html>"""


def send_newsletter(html, subject):
    resend.api_key = RESEND_API_KEY
    with open(SUBSCRIBERS_FILE) as f:
        subs = json.load(f)
    emails = subs.get("emails", [])
    if not emails:
        print("Warning: No subscribers found.")
        return
    sent, failed = 0, 0
    for email in emails:
        try:
            resend.Emails.send({"from": f"{FROM_NAME} <{FROM_EMAIL}>", "to": email, "subject": subject, "html": html})
            print(f"  Sent: {email}")
            sent += 1
            time.sleep(0.2)
        except Exception as e:
            print(f"  Failed: {email} - {e}")
            failed += 1
    print(f"\nSent {sent}/{len(emails)} | Failed: {failed}")


def main():
    print("Researching this week's paid social landscape...")
    data = research_newsletter()
    n = len(data.get("items", []))
    print(f"Compiled {n} stories")
    html = build_email_html(data)
    week_no = datetime.now(CST).isocalendar()[1]
    opening = data.get("opening_line", "")[:70].rstrip()
    subject = f"Paid Social Edge - Week {week_no} | {opening}"
    print(f"Subject: {subject}")
    send_newsletter(html, subject)


if __name__ == "__main__":
    main()
