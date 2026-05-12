"""
Biweekly Paid Social Edge Brief

Purpose:
A short, high-quality paid social signal brief.

Focus:
- Quality of research
- Interesting updates
- Sharp insights
- Strong write-up
- No Dell angle
- No forced actions
- No "what to monitor"
- No generic advice

Token-safe version:
- No refinement call by default
- Smaller search payload
- Smaller Groq max_tokens
- Groq JSON mode + validation
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

# Set RUN_EVEN_WEEKS_ONLY=true in GitHub Actions if this brief should run only on even weeks.
RUN_EVEN_WEEKS_ONLY = os.environ.get("RUN_EVEN_WEEKS_ONLY", "false").lower() == "true"

# Keep this false unless you upgrade Groq token limits.
# The previous run failed because refinement pushed you over the daily token limit.
USE_REFINEMENT = os.environ.get("USE_REFINEMENT", "false").lower() == "true"


# ── Biweekly gate ─────────────────────────────────────────────────────────────

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

            # If rate limit is hit, do not keep retrying aggressively.
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


# ── Query prompt ──────────────────────────────────────────────────────────────

def build_query_prompt(today: str) -> str:
    return f"""
Today is {today}.

Create search queries for a short, high-quality paid social signal brief.

The goal is not to create a generic marketing newsletter.
The goal is to find genuinely useful recent signals, updates, research findings, platform shifts, competitive moves, measurement changes, creative patterns, or practitioner insights.

The output should be useful because the research is strong, not because it forces advice.

Look for:
- meaningful paid social platform changes
- platform automation or AI changes
- measurement, attribution, incrementality, MMM, privacy, or signal-quality updates
- creative testing patterns or ad format shifts
- credible research reports
- real campaign examples
- competitor or category advertising moves
- buyer behavior research
- ad tech and media buying changes
- practitioner observations with real examples or data

Avoid:
- generic best practices
- SEO listicles
- surface-level trend pieces
- "how to improve ROI" articles
- weak opinion pieces
- platform promotional content with no real detail

Use a mix of:
- recent platform/news queries
- source-specific queries
- research/report queries
- measurement queries
- creative/platform queries
- practitioner/teardown queries

Return JSON only with this schema:

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


# ── Brief prompt ──────────────────────────────────────────────────────────────

def build_brief_prompt(today: str, search_results: str) -> str:
    return f"""
Today is {today}.

You are writing a short paid social signal brief.

This is not a generic newsletter.
This is not an action-plan email.
This is not a company-specific memo.

Your only job:
Find the strongest 3 to 5 research-backed signals from the raw search results and write them clearly.

Raw search results:
{search_results}

A strong signal can be:
- a real platform update
- a paid social measurement shift
- a credible research finding
- a campaign or creative pattern
- a competitor/category move
- a buyer behavior insight
- an ad tech/media buying change
- a practitioner observation with real detail
- an unusual or under-discussed implication

Selection bar:
Only include something if it has at least one of:
- a concrete detail
- a named platform or source
- a specific change
- a data point
- a real example
- a credible research finding
- a mechanism that explains why it matters
- a non-obvious implication

Hard filter out:
- generic marketing advice
- repeated common knowledge
- SEO articles
- vague trend commentary
- thin platform promotion
- anything that only says “AI improves performance”
- anything that requires a forced action to make it seem useful

Time logic:
- Prefer the last 14 to 30 days for news/platform updates.
- Allow 60 to 90 days for strong research reports.
- Do not include old evergreen content unless it became newly relevant.

Writing style:
- concise
- specific
- interesting
- plainspoken
- non-corporate
- no buzzwords
- no forced advice
- no “the team should”
- no “brands must”
- no “marketers need to”
- no generic endings

For each signal, write a mini write-up.
Do not use rigid sections like “action,” “monitor,” or “company angle.”
The write-up should explain what happened, why it is interesting, and what makes it worth reading.

If only 2 strong signals exist, include only 2.
Do not pad.

Return JSON only with this schema:

{{
  "period": "{today}",
  "headline": "A short headline for this cycle's brief",
  "intro": "2-3 sentences summarizing the main pattern across the strongest signals. No generic phrasing.",
  "signals": [
    {{
      "title": "Specific signal title",
      "signal_type": "Platform Shift | Measurement | Creative | Research | Competitor/Category | AI/Automation | Buyer Behavior | Ad Tech",
      "source_name": "Source name",
      "source_url": "Direct URL",
      "recency": "Date or recency",
      "writeup": "A concise but thoughtful mini write-up. 90-150 words. Explain the actual detail, why it is interesting, and why it is worth reading. No forced advice."
    }}
  ],
  "best_links": [
    {{
      "title": "Source title",
      "url": "URL"
    }}
  ]
}}
"""


# ── Optional refinement prompt ────────────────────────────────────────────────

def build_refinement_prompt(draft_json: dict, evidence: str) -> str:
    draft_text = json.dumps(draft_json, ensure_ascii=False, indent=2)

    return f"""
Edit this paid social signal brief.

Reviewer feedback to solve:
- The brief should focus on quality of research, updates, insight, and writing.
- It should not force actions.
- It should not sound like generic advice.
- It should not include company-specific angles.
- It should not feel templatey.

Draft JSON:
{draft_text}

Evidence:
{evidence}

Editing rules:
1. Keep the exact same JSON schema.
2. Remove generic phrases.
3. Make each signal more specific and interesting.
4. Every signal write-up should include a concrete detail, mechanism, source detail, or non-obvious implication.
5. Do not invent facts.
6. Do not add action items.
7. Do not use “marketers should,” “brands must,” “teams need to,” “leverage,” “unlock,” or “drive ROI.”
8. If a signal is weak, make it shorter or remove it.
9. Keep the tone clean and readable.

Return JSON only with this schema:

{{
  "period": "Date",
  "headline": "Brief headline",
  "intro": "2-3 sentence intro",
  "signals": [
    {{
      "title": "Specific signal title",
      "signal_type": "Platform Shift | Measurement | Creative | Research | Competitor/Category | AI/Automation | Buyer Behavior | Ad Tech",
      "source_name": "Source name",
      "source_url": "Direct URL",
      "recency": "Date or recency",
      "writeup": "90-150 word mini write-up"
    }}
  ],
  "best_links": [
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
        "paid social advertising platform updates Meta LinkedIn TikTok Reddit Google last 30 days",
        "Meta ads LinkedIn ads Reddit ads TikTok ads new features advertisers recent",
        "paid social measurement attribution incrementality MMM privacy update recent",
        "AI automation advertising platform campaign optimization creative testing recent",
        "paid social creative testing formats research recent",
        "B2B buyer behavior technology marketing research report recent",
        "AdExchanger Digiday Marketing Brew paid social advertising platform changes",
        "Think with Google IAB LinkedIn B2B Institute paid social research recent"
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
                chunks_per_source=2,
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

CAT_COLORS = {
    "Platform Shift":       "#1877F2",
    "Measurement":          "#059669",
    "Creative":             "#7C3AED",
    "Competitor/Category":  "#DC2626",
    "Research":             "#D97706",
    "AI/Automation":        "#0891B2",
    "Buyer Behavior":       "#0A66C2",
    "Ad Tech":              "#4F46E5",
}
DEF_COLOR = "#4B5563"


def signal_html(s: dict, idx: int) -> str:
    signal_type = s.get("signal_type", "Signal")
    color = CAT_COLORS.get(signal_type, DEF_COLOR)

    title = esc(s.get("title", ""))
    src = esc(s.get("source_name", "Source"))
    url = esc(s.get("source_url", "#"))
    rec = esc(s.get("recency", ""))
    writeup = esc(s.get("writeup", ""))

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
              {esc(signal_type)}
            </span>
          </td>
          <td align="right">
            <span style="font-size:11px;color:#9CA3AF;">{rec}</span>
          </td>
        </tr>
      </table>

      <h3 style="margin:11px 0 9px;font-size:15.5px;font-weight:750;color:#111827;line-height:1.4;">
        {idx}. {title}
      </h3>

      <p style="margin:0 0 13px;font-size:13.8px;color:#374151;line-height:1.75;">
        {writeup}
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
            url = esc(item.get("url", "#"))
        else:
            title = esc(str(item))
            url = esc(str(item))

        rows += (
            f'<tr><td style="padding:4px 0;">'
            f'<a href="{url}" style="font-size:13px;color:#4F46E5;text-decoration:none;word-break:break-all;">'
            f'{title}</a></td></tr>'
        )

    return f"""
<div style="margin-bottom:18px;">
  <p style="margin:0 0 8px;font-size:11px;font-weight:700;color:#6B7280;
             text-transform:uppercase;letter-spacing:.8px;">Best links</p>
  <table cellpadding="0" cellspacing="0" border="0">{rows}</table>
</div>"""


def build_brief_html(data: dict) -> str:
    now      = datetime.now(CST)
    date_str = now.strftime("%B %d, %Y")
    week_num = now.isocalendar()[1]
    n        = len(data.get("signals", []))

    headline = esc(data.get("headline", "Paid Social Edge"))
    intro = esc(data.get("intro", ""))

    signals_html = "\n".join(
        signal_html(s, i + 1)
        for i, s in enumerate(data.get("signals", []))
    )

    links_section = links_html(data.get("best_links", []))

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
        Signal Brief &nbsp;·&nbsp; Week {week_num} &nbsp;·&nbsp; {esc(date_str)} &nbsp;·&nbsp; {n} signals
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
      {signals_html}
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
        Paid Social Edge &nbsp;·&nbsp; High-signal research for paid social operators
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
            max_tokens=900,
            temperature=0.5
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

    print("\n[Phase 3] Compiling signal brief...")
    data = call_groq_json(
        prompt=build_brief_prompt(today, raw[:9000]),
        required_keys=[
            "period",
            "headline",
            "intro",
            "signals",
            "best_links"
        ],
        step_name="Brief compilation",
        max_tokens=2200,
        temperature=0.25,
        repair_context=raw[:2500]
    )

    # Optional refinement, off by default to avoid Groq token-limit failures.
    if USE_REFINEMENT:
        try:
            print("\n[Phase 4] Refining signal brief...")
            data = call_groq_json(
                prompt=build_refinement_prompt(data, raw[:7000]),
                required_keys=[
                    "period",
                    "headline",
                    "intro",
                    "signals",
                    "best_links"
                ],
                step_name="Brief refinement",
                max_tokens=1600,
                temperature=0.2,
                repair_context=raw[:2000]
            )
        except Exception as e:
            print(f"Refinement failed, using compiled draft instead. Error: {e}")
    else:
        print("\n[Phase 4] Skipping refinement to save Groq tokens.")

    n = len(data.get("signals", []))
    print(f"Compiled {n} signals.")

    html = build_brief_html(data)
    week_no = datetime.now(CST).isocalendar()[1]
    subject = f"Paid Social Edge — {n} signals | Wk {week_no}"
    subject = compact_text(subject, 70)

    print(f"Subject: {subject}")
    send(html, subject)


if __name__ == "__main__":
    main()
