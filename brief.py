"""
Biweekly Paid Social Edge Brief
Runs every 2 weeks (even ISO week numbers), Tuesday 6 AM CST
3-5 strongest signals only. Dell-focused. No filler.
"""

from tavily import TavilyClient
from groq import Groq
import resend
import json, os, re, time
from datetime import datetime
import pytz

# ── Config ────────────────────────────────────────────────────────────────────
TAVILY_API_KEY   = os.environ["TAVILY_API_KEY"]
GROQ_API_KEY     = os.environ["GROQ_API_KEY"]
RESEND_API_KEY   = os.environ["RESEND_API_KEY"]
FROM_EMAIL       = os.environ["FROM_EMAIL"]
FROM_NAME        = "Paid Social Edge"
SUBSCRIBERS_FILE = "subscribers.json"
MODEL            = "llama-3.3-70b-versatile"
CST              = pytz.timezone("US/Central")

# ── Biweekly gate: only run on even ISO week numbers ─────────────────────────
def should_run_today() -> bool:
    week = datetime.now(CST).isocalendar()[1]
    if week % 2 != 0:
        print(f"Week {week} is odd — skipping this cycle. Next brief runs week {week+1}.")
        return False
    return True

# ── Searches ──────────────────────────────────────────────────────────────────
SEARCH_QUERIES = [
    "Meta Facebook Instagram ads algorithm changes updates last 2 weeks",
    "LinkedIn ads B2B targeting changes announcements recent",
    "TikTok Reddit ads new features changes recent",
    "Google YouTube ads paid social cross-channel news recent",
    "AI automation paid social advertising platform changes 2025 2026",
    "paid social measurement attribution incrementality signal loss update",
    "Dell HP Lenovo Apple Microsoft enterprise technology advertising campaign 2025 2026",
    "B2B enterprise buyer behavior research technology purchase paid social",
    "paid social creative testing formats best practice research recent",
    "ad tech programmatic measurement industry news acquisition recent",
]

# ── Prompt ────────────────────────────────────────────────────────────────────
BRIEF_PROMPT = """Today is {today}. You are a senior paid social operator building an intelligence brief for yourself.

Context: You work on Dell's in-house paid social team. Dell sells laptops, PCs, enterprise hardware, gaming rigs (Alienware), monitors, and B2B IT solutions. Your audience includes enterprise IT buyers, SMB buyers, consumers, and gamers. Your competitors include HP, Lenovo, Apple, and Microsoft.

You are NOT writing a generic newsletter. You are filtering raw search results to find only signals that genuinely matter for paid social strategy, creative, measurement, or competitive positioning — specifically through the lens of someone running Dell's paid social.

RAW SEARCH RESULTS:
{search_results}

YOUR TASK:
From these results, identify the 3–5 strongest signals from the last 14–30 days (allow up to 60–90 days for research reports if highly relevant).

A strong signal is one that:
- Changes how you would run, structure, or measure a paid social campaign
- Reveals something meaningful about platform mechanics, buyer behavior, or competitor activity
- Contains actual data, a real case, or a specific platform change — not opinion or tips
- Is relevant to B2B, enterprise tech, or the specific platforms Dell uses most (Meta, LinkedIn, Google, Reddit, TikTok)

HARD FILTER. Exclude anything that is:
- Generic marketing advice or tips
- Platform promotional content with no real change underneath
- Evergreen content with a recent date
- Opinion pieces with no data or examples
- Something a competent senior buyer already knows
- Not relevant to Dell's business or paid social channels

If fewer than 3 genuinely strong signals exist in the results, output fewer. Do NOT pad with weak items.

OUTPUT: Return ONLY valid JSON. No markdown fences, no preamble.

{{
  "period": "{today}",
  "executive_summary": ["bullet 1 — one key theme or development", "bullet 2", "bullet 3"],
  "signals": [
    {{
      "title": "Short signal title — specific and direct",
      "category": "Platform Change | Measurement | Creative | Competitor | Research | AI/Automation | Buyer Behavior",
      "source_name": "e.g. LinkedIn Engineering Blog, Search Engine Land, Marketing Brew",
      "source_url": "direct URL",
      "recency": "e.g. April 22, 2026 or Last week",
      "why_it_matters": "2–3 sentences. What actually happened and why it matters for paid social strategy, creative, or measurement. Be specific.",
      "dell_angle": "1–2 sentences. How this could matter specifically for Dell paid social — B2B, consumer, gaming, measurement, competitive, or operational.",
      "action": "One concrete thing to do: test, monitor, investigate, save, or bring to a team discussion. Specific."
    }}
  ],
  "act_on": ["specific thing 1", "specific thing 2"],
  "monitor": ["thing to watch 1", "thing to watch 2"],
  "best_links": ["url1", "url2", "url3"]
}}"""

# ── Research ──────────────────────────────────────────────────────────────────
def run_searches() -> str:
    tavily = TavilyClient(api_key=TAVILY_API_KEY)
    results = []
    for i, q in enumerate(SEARCH_QUERIES, 1):
        print(f"  [{i}/{len(SEARCH_QUERIES)}] {q[:60]}...")
        try:
            r = tavily.search(q, search_depth="advanced", max_results=4, include_raw_content=False)
            for item in r.get("results", []):
                results.append(
                    f"TITLE: {item.get('title','')}\n"
                    f"URL:   {item.get('url','')}\n"
                    f"DATE:  {item.get('published_date','unknown')}\n"
                    f"BODY:  {item.get('content','')[:500]}\n---"
                )
            time.sleep(0.4)
        except Exception as e:
            print(f"    Search error: {e}")
    return "\n\n".join(results)


def compile_brief(raw: str) -> dict:
    groq   = Groq(api_key=GROQ_API_KEY)
    today  = datetime.now(CST).strftime("%B %d, %Y")
    prompt = BRIEF_PROMPT.format(today=today, search_results=raw)
    print("  Compiling with Groq...")
    resp = groq.chat.completions.create(
        model=MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.2,
        max_tokens=3500,
    )
    raw_text = resp.choices[0].message.content
    clean = re.sub(r"```(?:json)?|```", "", raw_text).strip()
    m = re.search(r"\{.*\}", clean, re.DOTALL)
    if not m:
        raise ValueError(f"No JSON in response:\n{raw_text[:400]}")
    return json.loads(m.group())


# ── Email HTML ────────────────────────────────────────────────────────────────
CAT_COLORS = {
    "Platform Change": "#1877F2",
    "Measurement":     "#059669",
    "Creative":        "#7C3AED",
    "Competitor":      "#DC2626",
    "Research":        "#D97706",
    "AI/Automation":   "#0891B2",
    "Buyer Behavior":  "#0A66C2",
}
DEF_COLOR = "#4B5563"


def signal_html(s: dict, idx: int) -> str:
    cat   = s.get("category", "Update")
    color = CAT_COLORS.get(cat, DEF_COLOR)
    url   = s.get("source_url", "#")
    src   = s.get("source_name", "Source")
    rec   = s.get("recency", "")
    return f"""
<table width="100%" cellpadding="0" cellspacing="0" border="0"
       style="background:#ffffff;border-radius:10px;margin-bottom:18px;
              border-left:4px solid {color};box-shadow:0 1px 4px rgba(0,0,0,.06);">
  <tr><td style="padding:20px 24px;">
    <table width="100%" cellpadding="0" cellspacing="0" border="0"><tr>
      <td><span style="background:{color};color:#fff;font-size:10px;font-weight:700;
               letter-spacing:.7px;padding:2px 9px;border-radius:20px;text-transform:uppercase;">{cat}</span></td>
      <td align="right"><span style="font-size:11px;color:#9CA3AF;">{rec}</span></td>
    </tr></table>
    <h3 style="margin:10px 0 8px;font-size:15px;font-weight:700;color:#111827;line-height:1.4;">
      Signal {idx}: {s.get('title','')}
    </h3>
    <p style="margin:0 0 10px;font-size:13.5px;color:#374151;line-height:1.75;">
      <strong>Why it matters:</strong> {s.get('why_it_matters','')}
    </p>
    <p style="margin:0 0 12px;font-size:13.5px;color:#374151;line-height:1.75;">
      <strong>Dell angle:</strong> {s.get('dell_angle','')}
    </p>
    <div style="background:#EFF6FF;border-radius:7px;padding:10px 14px;margin-bottom:12px;">
      <span style="font-size:11px;font-weight:700;color:#1D4ED8;text-transform:uppercase;letter-spacing:.6px;">Action</span>
      <p style="margin:4px 0 0;font-size:13px;color:#1E40AF;line-height:1.6;">{s.get('action','')}</p>
    </div>
    <a href="{url}" style="font-size:12.5px;color:{color};text-decoration:none;font-weight:600;">
      {src} →
    </a>
  </td></tr>
</table>"""


def bullets_html(items: list, label: str, color: str) -> str:
    if not items:
        return ""
    lis = "".join(f'<li style="margin-bottom:6px;font-size:13.5px;color:#374151;line-height:1.65;">{i}</li>' for i in items)
    return f"""
<div style="margin-bottom:18px;">
  <p style="margin:0 0 8px;font-size:11px;font-weight:700;color:{color};
             text-transform:uppercase;letter-spacing:.8px;">{label}</p>
  <ul style="margin:0;padding-left:18px;">{lis}</ul>
</div>"""


def links_html(urls: list) -> str:
    if not urls:
        return ""
    rows = "".join(
        f'<tr><td style="padding:4px 0;"><a href="{u}" style="font-size:13px;color:#4F46E5;'
        f'text-decoration:none;word-break:break-all;">{u}</a></td></tr>'
        for u in urls
    )
    return f"""
<div style="margin-bottom:18px;">
  <p style="margin:0 0 8px;font-size:11px;font-weight:700;color:#6B7280;
             text-transform:uppercase;letter-spacing:.8px;">Best Links to Read</p>
  <table cellpadding="0" cellspacing="0" border="0">{rows}</table>
</div>"""


def build_brief_html(data: dict) -> str:
    now      = datetime.now(CST)
    date_str = now.strftime("%B %d, %Y")
    week_num = now.isocalendar()[1]
    n        = len(data.get("signals", []))

    exec_sum = data.get("executive_summary", [])
    exec_html = "".join(
        f'<li style="margin-bottom:7px;font-size:14px;color:#C7D2FE;line-height:1.7;">{b}</li>'
        for b in exec_sum
    )

    signals_html = "\n".join(signal_html(s, i+1) for i, s in enumerate(data.get("signals", [])))
    act_html     = bullets_html(data.get("act_on", []),   "What I would act on",  "#059669")
    mon_html     = bullets_html(data.get("monitor", []),  "What I would monitor", "#D97706")
    lnk_html     = links_html(data.get("best_links", []))

    return f"""<!DOCTYPE html><html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Paid Social Edge Brief — {date_str}</title></head>
<body style="margin:0;padding:0;background:#F3F4F6;
             font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;">
<table width="100%" cellpadding="0" cellspacing="0"><tr><td align="center" style="padding:32px 16px;">
<table width="600" cellpadding="0" cellspacing="0" style="max-width:600px;width:100%;">

  <!-- Header -->
  <tr><td style="background:linear-gradient(135deg,#0F172A 0%,#1E1B4B 60%,#312E81 100%);
                  border-radius:12px 12px 0 0;padding:32px 36px 28px;">
    <p style="margin:0 0 5px;font-size:10px;font-weight:700;letter-spacing:2.5px;
               color:#818CF8;text-transform:uppercase;">
      Biweekly Brief &nbsp;·&nbsp; Week {week_num} &nbsp;·&nbsp; {date_str} &nbsp;·&nbsp; {n} signals
    </p>
    <h1 style="margin:0 0 16px;font-size:26px;font-weight:800;color:#fff;letter-spacing:-.3px;">
      Paid Social Edge
    </h1>
    <p style="margin:0 0 6px;font-size:10px;font-weight:700;color:#6366F1;
               text-transform:uppercase;letter-spacing:1px;">This Cycle</p>
    <ul style="margin:0;padding-left:16px;">{exec_html}</ul>
  </td></tr>
  <tr><td style="background:#4F46E5;height:3px;"></td></tr>

  <!-- Signals -->
  <tr><td style="background:#F3F4F6;padding:24px 16px 4px;">
    {signals_html}
  </td></tr>

  <!-- Act / Monitor / Links -->
  <tr><td style="background:#ffffff;border-radius:0;padding:20px 24px;">
    {act_html}
    {mon_html}
    {lnk_html}
  </td></tr>

  <!-- Footer -->
  <tr><td style="background:#111827;border-radius:0 0 12px 12px;padding:20px 36px;text-align:center;">
    <p style="margin:0;font-size:12px;color:#6B7280;line-height:1.6;">
      Paid Social Edge &nbsp;·&nbsp; Biweekly brief for Dell paid social &nbsp;·&nbsp;
      Research via Tavily + Llama 3.3
    </p>
  </td></tr>

</table></td></tr></table></body></html>"""


# ── Send ──────────────────────────────────────────────────────────────────────
def send(html: str, subject: str):
    resend.api_key = RESEND_API_KEY
    with open(SUBSCRIBERS_FILE) as f:
        subs = json.load(f)
    emails = subs.get("emails", [])
    if not emails:
        print("No subscribers."); return
    sent = failed = 0
    for email in emails:
        try:
            resend.Emails.send({"from": f"{FROM_NAME} <{FROM_EMAIL}>",
                                "to": email, "subject": subject, "html": html})
            print(f"  Sent: {email}"); sent += 1; time.sleep(0.2)
        except Exception as e:
            print(f"  Failed: {email} — {e}"); failed += 1
    print(f"Done. {sent} sent / {failed} failed.")


# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    if not should_run_today():
        return

    print("Running biweekly brief searches...")
    raw    = run_searches()
    data   = compile_brief(raw)
    n      = len(data.get("signals", []))
    print(f"Compiled {n} signals.")

    html     = build_brief_html(data)
    week_no  = datetime.now(CST).isocalendar()[1]
    # Short subject line: under 60 chars
    subject  = f"Paid Social Edge — {n} signals | Wk {week_no}"
    print(f"Subject: {subject}")
    send(html, subject)


if __name__ == "__main__":
    main()
