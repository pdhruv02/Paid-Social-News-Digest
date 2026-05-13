"""
Biweekly Paid Social Edge Brief

Purpose:
A short paid social / advertising update brief.

Goal:
Find recent updates, changes, launches, research, findings, or industry moves
from roughly the last 14 days. Stretch to 30 days only if the item is strong.

No Dell angle.
No forced actions.
No "what to monitor."
No over-structured prompt.
No refinement call by default.
"""

from tavily import TavilyClient
from groq import Groq
import resend
import json
import os
import re
import time
import html as html_lib
from datetime import datetime
import pytz


# ── Config ────────────────────────────────────────────────────────────────────

TAVILY_API_KEY   = os.environ["TAVILY_API_KEY"]
GROQ_API_KEY     = os.environ["GROQ_API_KEY"]
RESEND_API_KEY   = os.environ["RESEND_API_KEY"]
FROM_EMAIL       = os.environ["FROM_EMAIL"]

FROM_NAME        = "Paid Social Edge"
SUBSCRIBERS_FILE = "subscribers.json"
MODEL            = os.environ.get("GROQ_MODEL", "llama-3.3-70b-versatile")
CST              = pytz.timezone("US/Central")

# Set RUN_EVEN_WEEKS_ONLY=true in GitHub Actions if this brief should run only on even ISO weeks.
RUN_EVEN_WEEKS_ONLY = os.environ.get("RUN_EVEN_WEEKS_ONLY", "false").lower() == "true"


# ── Week gate ─────────────────────────────────────────────────────────────────

def should_run_today() -> bool:
    week = datetime.now(CST).isocalendar()[1]

    if RUN_EVEN_WEEKS_ONLY and week % 2 != 0:
        print(f"Week {week} is odd — skipping this signal brief.")
        return False

    print(f"Week {week} — running Paid Social Edge signal brief.")
    return True


# ── Helpers ───────────────────────────────────────────────────────────────────

def esc(value) -> str:
    if value is None:
        return ""
    return html_lib.escape(str(value), quote=True)


def clean_url(url: str) -> str:
    if not url:
        return "#"
    return str(url).strip()


def compact_text(text: str, max_chars: int) -> str:
    if not text:
        return ""

    text = re.sub(r"\s+", " ", str(text)).strip()

    if len(text) <= max_chars:
        return text

    return text[:max_chars].rsplit(" ", 1)[0] + "..."


def get_json_text(raw: str) -> str:
    if not raw:
        raise ValueError("Empty model output.")

    clean = re.sub(r"```(?:json)?|```", "", raw).strip()

    try:
        json.loads(clean)
        return clean
    except Exception:
        pass

    match = re.search(r"\{.*\}", clean, re.DOTALL)

    if not match:
        raise ValueError(f"No JSON object found in model output:\n{raw[:800]}")

    return match.group()


def validate_keys(data: dict, required_keys: list, step_name: str):
    missing = [k for k in required_keys if k not in data]

    if missing:
        raise ValueError(f"{step_name} missing required keys: {missing}")


def call_groq_json(
    prompt: str,
    required_keys: list,
    step_name: str,
    max_tokens: int = 2200,
    temperature: float = 0.25,
    repair_context: str = ""
) -> dict:
    groq_client = Groq(api_key=GROQ_API_KEY)

    system_message = (
        "You are a JSON API. Return exactly one valid JSON object. "
        "No markdown. No preamble. No copied source text outside JSON. "
        "Use double quotes for all JSON strings."
    )

    last_error = None
    current_prompt = prompt

    for attempt in range(3):
        try:
            if attempt > 0:
                wait = 10 * attempt
                print(f"  Retrying {step_name} after {wait}s...")
                time.sleep(wait)

            resp = groq_client.chat.completions.create(
                model=MODEL,
                messages=[
                    {"role": "system", "content": system_message},
                    {"role": "user", "content": current_prompt},
                ],
                temperature=temperature,
                max_tokens=max_tokens,
                response_format={"type": "json_object"},
            )

            raw_text = resp.choices[0].message.content or ""
            data = json.loads(get_json_text(raw_text))
            validate_keys(data, required_keys, step_name)
            return data

        except Exception as e:
            last_error = e
            print(f"  {step_name} JSON attempt {attempt + 1} failed: {e}")

            err = str(e).lower()
            if "rate limit" in err or "rate_limit" in err or "429" in err:
                raise

            current_prompt = f"""
The previous response failed JSON validation.

Error:
{str(e)}

Required top-level keys:
{required_keys}

Return one valid JSON object only. No markdown. No explanation.

Original task:
{prompt}

Additional context:
{repair_context[:2500]}
"""

    raise RuntimeError(f"{step_name} failed after 3 attempts. Last error: {last_error}")


# ── Prompts ───────────────────────────────────────────────────────────────────

def build_query_prompt(today: str) -> str:
    return f"""
Today is {today}.

Create search queries for a short paid social and advertising update brief.

The brief should find recent updates, changes, launches, research, findings, or notable moves from roughly the last 14 days. Use 30 days only if the item is genuinely strong.

Priority goes to things that could matter to paid social operators: ad platform changes, media buying shifts, creator/influencer product changes, measurement updates, automation or AI changes, ad format launches, privacy/signal changes, credible research, or notable campaign/category moves.

Do not look for generic marketing advice or evergreen best practices.

Use credible sources when possible. Examples include official platform blogs, platform business/help centers, AdExchanger, Digiday, Marketing Brew, eMarketer, The Information, Search Engine Land, Social Media Today, IAB, Think with Google, LinkedIn B2B Institute, Reddit for Business, Meta for Business, TikTok Business, YouTube/Google Ads updates, WARC, Effie, Campaign, The Drum, and strong practitioner sources.

These are examples, not a required list.

Return JSON only:

{{
  "queries": [
    "query 1",
    "query 2",
    "query 3",
    "query 4",
    "query 5",
    "query 6",
    "query 7",
    "query 8"
  ]
}}
"""


def build_brief_prompt(today: str, search_results: str) -> str:
    return f"""
Today is {today}.

Write a short paid social and advertising update brief from the research below.

Goal:
Find the few recent updates, changes, launches, research findings, or industry moves that are actually worth knowing.

Default time window:
Last 14 days.

Stretch window:
Last 30 days only if the item is unusually useful, credible, or important.

Raw research results:
{search_results}

Prioritize recent platform-level or market-level changes that could matter to paid social operators. This includes ad platform updates, media buying changes, creator/influencer product changes, measurement or attribution changes, automation/AI changes, privacy/signal changes, ad format launches, credible research findings, or notable campaign/category moves.

Skip generic marketing advice, evergreen best practices, weak platform announcements, SEO posts, vague trend pieces, and anything that is only interesting because it is recent.

Write 3 to 5 items max. If only 2 are strong, include only 2.

Each item should be a short mini-note, not an action plan. Explain what changed, why it caught your attention, and why it is worth reading.

Keep the writing simple, specific, and natural.

Return JSON only:

{{
  "period": "{today}",
  "headline": "A short headline for this brief",
  "intro": "2-3 sentences summarizing what stood out this cycle.",
  "items": [
    {{
      "title": "Specific update title",
      "label": "Platform | Measurement | Creative | Research | Brand/Category | AI/Automation | Creator/Influencer | Media/Ad Tech | Other",
      "source_name": "Source name",
      "source_url": "Direct URL",
      "date": "Date or recency",
      "note": "90-150 words. Explain what changed, why it caught attention, and why it is worth reading. No forced advice."
    }}
  ],
  "links": [
    {{
      "title": "Source title",
      "url": "URL"
    }}
  ]
}}
"""


# ── Search ────────────────────────────────────────────────────────────────────

def fallback_queries() -> list:
    return [
        "paid social advertising platform updates Meta LinkedIn TikTok Reddit Google last 14 days",
        "ad platform updates media buying measurement attribution last 30 days",
        "creator influencer marketing platform launch ads recent",
        "AI automation advertising platform update recent",
        "paid social measurement privacy signal loss update recent",
        "Meta LinkedIn Reddit TikTok YouTube ads update recent",
        "AdExchanger Digiday Marketing Brew advertising platform changes recent",
        "IAB eMarketer Think with Google paid media advertising research recent"
    ]


def run_searches(queries: list) -> str:
    tavily = TavilyClient(api_key=TAVILY_API_KEY)
    results = []
    seen_urls = set()

    for i, q in enumerate(queries, 1):
        q = str(q).strip()

        if not q:
            continue

        print(f"  [{i}/{len(queries)}] {q[:80]}...")

        try:
            response = tavily.search(
                query=q,
                search_depth="advanced",
                max_results=3,
                include_raw_content=False,
                include_answer=False,
                timeout=45
            )

            for item in response.get("results", []):
                url = item.get("url", "").strip()

                if not url or url in seen_urls:
                    continue

                seen_urls.add(url)

                results.append(
                    f"QUERY: {q}\n"
                    f"TITLE: {item.get('title','')}\n"
                    f"URL: {url}\n"
                    f"DATE: {item.get('published_date','unknown')}\n"
                    f"SCORE: {item.get('score','')}\n"
                    f"BODY: {compact_text(item.get('content',''), 700)}\n"
                    f"---"
                )

            time.sleep(0.4)

        except Exception as e:
            print(f"    Search error: {e}")

    return "\n\n".join(results)


# ── Email HTML ────────────────────────────────────────────────────────────────

LABEL_COLORS = {
    "Platform":           "#1877F2",
    "Measurement":        "#059669",
    "Creative":           "#7C3AED",
    "Research":           "#D97706",
    "Brand/Category":     "#DC2626",
    "AI/Automation":      "#0891B2",
    "Creator/Influencer": "#BE185D",
    "Media/Ad Tech":      "#4F46E5",
    "Other":              "#4B5563",
}
DEF_COLOR = "#4B5563"


def item_html(item: dict, idx: int) -> str:
    label = item.get("label", "Other")
    color = LABEL_COLORS.get(label, DEF_COLOR)

    title = esc(item.get("title", ""))
    src = esc(item.get("source_name", "Source"))
    url = esc(clean_url(item.get("source_url", "#")))
    date = esc(item.get("date", ""))
    note = esc(item.get("note", ""))

    return f"""
<table width="100%" cellpadding="0" cellspacing="0" border="0"
       style="background:#ffffff;border-radius:10px;margin-bottom:18px;
              border-left:4px solid {color};box-shadow:0 1px 4px rgba(0,0,0,.06);">
  <tr>
    <td style="padding:20px 24px;">
      <table width="100%" cellpadding="0" cellspacing="0" border="0">
        <tr>
          <td>
            <span style="background:{color};color:#fff;font-size:10px;font-weight:700;
                 letter-spacing:.7px;padding:2px 9px;border-radius:20px;text-transform:uppercase;">
              {esc(label)}
            </span>
          </td>
          <td align="right">
            <span style="font-size:11px;color:#9CA3AF;">{date}</span>
          </td>
        </tr>
      </table>

      <h3 style="margin:11px 0 9px;font-size:15.5px;font-weight:750;color:#111827;line-height:1.4;">
        {idx}. {title}
      </h3>

      <p style="margin:0 0 13px;font-size:13.8px;color:#374151;line-height:1.75;">
        {note}
      </p>

      <a href="{url}" style="font-size:12.5px;color:{color};text-decoration:none;font-weight:600;">
        {src} →
      </a>
    </td>
  </tr>
</table>"""


def links_html(items: list) -> str:
    if not items:
        return ""

    rows = ""

    for item in items:
        if isinstance(item, dict):
            title = esc(item.get("title", item.get("url", "")))
            url = esc(clean_url(item.get("url", "#")))
        else:
            title = esc(str(item))
            url = esc(clean_url(str(item)))

        rows += (
            f'<tr><td style="padding:4px 0;">'
            f'<a href="{url}" style="font-size:13px;color:#4F46E5;text-decoration:none;word-break:break-all;">'
            f'{title}</a></td></tr>'
        )

    return f"""
<div style="margin-bottom:18px;">
  <p style="margin:0 0 8px;font-size:11px;font-weight:700;color:#6B7280;
             text-transform:uppercase;letter-spacing:.8px;">Links</p>
  <table cellpadding="0" cellspacing="0" border="0">{rows}</table>
</div>"""


def build_brief_html(data: dict) -> str:
    now      = datetime.now(CST)
    date_str = now.strftime("%B %d, %Y")
    week_num = now.isocalendar()[1]
    n        = len(data.get("items", []))

    headline = esc(data.get("headline", "Paid Social Edge"))
    intro = esc(data.get("intro", ""))

    items_html = "\n".join(
        item_html(item, i + 1)
        for i, item in enumerate(data.get("items", []))
    )

    links_section = links_html(data.get("links", []))

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Paid Social Edge Brief — {esc(date_str)}</title>
</head>

<body style="margin:0;padding:0;background:#F3F4F6;" bgcolor="#F3F4F6">
<table width="100%" bgcolor="#F3F4F6" style="background:#F3F4F6;
             font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;">
<tr>
<td align="center" style="padding:32px 16px;">
<table width="620" cellpadding="0" cellspacing="0" style="max-width:620px;width:100%;">

  <tr>
    <td style="background:#1E1B4B;border-radius:12px 12px 0 0;padding:32px 36px 28px;"
        bgcolor="#1E1B4B">
      <p style="margin:0 0 5px;font-size:10px;font-weight:700;letter-spacing:2.5px;
                 color:#818CF8;text-transform:uppercase;">
        Update Brief &nbsp;·&nbsp; Week {week_num} &nbsp;·&nbsp; {esc(date_str)} &nbsp;·&nbsp; {n} items
      </p>

      <h1 style="margin:0 0 12px;font-size:25px;font-weight:800;color:#fff;letter-spacing:-.3px;">
        {headline}
      </h1>

      <p style="margin:0;font-size:14px;color:#C7D2FE;line-height:1.7;">
        {intro}
      </p>
    </td>
  </tr>

  <tr>
    <td style="background:#4F46E5;height:3px;"></td>
  </tr>

  <tr>
    <td style="background:#F3F4F6;padding:24px 16px 4px;">
      {items_html}
    </td>
  </tr>

  <tr>
    <td style="background:#ffffff;border-radius:0;padding:20px 24px;">
      {links_section}
    </td>
  </tr>

  <tr>
    <td style="background:#111827;border-radius:0 0 12px 12px;padding:20px 36px;text-align:center;" bgcolor="#111827">
      <p style="margin:0;font-size:12px;color:#6B7280;line-height:1.6;">
        Paid Social Edge &nbsp;·&nbsp; Recent updates worth knowing
      </p>
    </td>
  </tr>

</table>
</td>
</tr>
</table>
</body>
</html>"""


# ── Send ──────────────────────────────────────────────────────────────────────

def send(html: str, subject: str):
    resend.api_key = RESEND_API_KEY

    with open(SUBSCRIBERS_FILE) as f:
        subs = json.load(f)

    emails = subs.get("emails", [])

    if not emails:
        print("No subscribers.")
        return

    sent = 0
    failed = 0

    for email in emails:
        try:
            resend.Emails.send({
                "from": f"{FROM_NAME} <{FROM_EMAIL}>",
                "to": email,
                "subject": subject,
                "html": html
            })

            print(f"  Sent: {email}")
            sent += 1
            time.sleep(0.2)

        except Exception as e:
            print(f"  Failed: {email} — {e}")
            failed += 1

    print(f"Done. {sent} sent / {failed} failed.")


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    if not should_run_today():
        return

    today = datetime.now(CST).strftime("%B %d, %Y")

    print("\n[Phase 1] Generating search queries...")

    try:
        query_data = call_groq_json(
            prompt=build_query_prompt(today),
            required_keys=["queries"],
            step_name="Query generation",
            max_tokens=800,
            temperature=0.45
        )

        queries = query_data.get("queries", [])

        if not isinstance(queries, list) or not queries:
            raise ValueError("queries must be a non-empty list")

    except Exception as e:
        print(f"Query generation failed, using fallback queries. Error: {e}")
        queries = fallback_queries()

    print("\nSearch queries:")
    for q in queries:
        print(f"  - {q}")

    print("\n[Phase 2] Running searches...")
    raw = run_searches(queries)

    if not raw.strip():
        raise RuntimeError("No search results returned from Tavily.")

    print("\n[Phase 3] Compiling update brief...")

    data = call_groq_json(
        prompt=build_brief_prompt(today, raw[:9000]),
        required_keys=[
            "period",
            "headline",
            "intro",
            "items",
            "links"
        ],
        step_name="Brief compilation",
        max_tokens=2200,
        temperature=0.25,
        repair_context=raw[:2500]
    )

    n = len(data.get("items", []))
    print(f"Compiled {n} items.")

    html = build_brief_html(data)
    week_no = datetime.now(CST).isocalendar()[1]
    subject = f"Paid Social Edge — {n} updates | Wk {week_no}"
    subject = compact_text(subject, 70)

    print(f"Subject: {subject}")
    send(html, subject)


if __name__ == "__main__":
    main()
