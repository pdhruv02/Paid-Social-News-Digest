"""
Paid Social Edge — Operator Deep Dive
Runs on odd ISO weeks, Tuesday 6 AM CST

Philosophy:
  Find one genuinely interesting thing. Write about it with depth and specifics.
  No template sections. No redundancy. Editorial opinion, not box-filling.
  Every sentence must earn its place.
"""

from tavily import TavilyClient
from groq import Groq
import resend
import json, os, re, time
import html as html_lib
from datetime import datetime
import pytz

TAVILY_API_KEY   = os.environ["TAVILY_API_KEY"]
GROQ_API_KEY     = os.environ["GROQ_API_KEY"]
RESEND_API_KEY   = os.environ["RESEND_API_KEY"]
FROM_EMAIL       = os.environ["FROM_EMAIL"]
FROM_NAME        = "Paid Social Edge"
SUBSCRIBERS_FILE = "subscribers.json"
MODEL            = os.environ.get("GROQ_MODEL", "llama-3.3-70b-versatile")
CST              = pytz.timezone("US/Central")

def check_week():
    week = datetime.now(CST).isocalendar()[1]
    #if week % 2 == 0:
      #  print(f"Week {week} is even — skipping. Brief runs this week.")
       # exit(0)
    print(f"Week {week} (odd) — running deep dive.")

def esc(v) -> str:
    return html_lib.escape(str(v), quote=True) if v else ""

def clean_url(u) -> str:
    return str(u).strip() if u else "#"

def compact(text, n: int) -> str:
    text = re.sub(r"\s+", " ", str(text or "")).strip()
    return text[:n].rsplit(" ", 1)[0] + "..." if len(text) > n else text

def safe_list(v):
    return v if isinstance(v, list) else ([str(v)] if v else [])

def extract_json(raw: str) -> dict:
    clean = re.sub(r"```(?:json)?|```", "", raw or "").strip()
    try:
        return json.loads(clean)
    except json.JSONDecodeError:
        pass
    m = re.search(r"\{.*\}", clean, re.DOTALL)
    if not m:
        raise ValueError(f"No JSON found:\n{raw[:600]}")
    try:
        return json.loads(m.group())
    except json.JSONDecodeError:
        fragment = m.group()
        lines = fragment.split("\n")
        for i in range(len(lines)-1, 0, -1):
            candidate = "\n".join(lines[:i]).rstrip().rstrip(",") + "\n}"
            try:
                return json.loads(candidate)
            except json.JSONDecodeError:
                continue
    raise ValueError("JSON recovery failed.")

def call_groq(prompt: str, max_tokens: int = 1800, temp: float = 0.25) -> dict:
    client = Groq(api_key=GROQ_API_KEY)
    for attempt in range(3):
        try:
            if attempt > 0:
                wait = 20 * attempt
                print(f"  Retry {attempt}/2 — waiting {wait}s...")
                time.sleep(wait)
            resp = client.chat.completions.create(
                model=MODEL,
                messages=[{"role": "user", "content": prompt}],
                temperature=temp,
                max_tokens=max_tokens,
            )
            raw = resp.choices[0].message.content
            print(f"  Groq: {len(raw)} chars, finish={resp.choices[0].finish_reason}")
            return extract_json(raw)
        except (ValueError, json.JSONDecodeError) as e:
            print(f"  JSON error attempt {attempt+1}: {e}")
            if attempt == 2: raise
        except Exception as e:
            if "rate_limit" in str(e).lower() or "429" in str(e):
                print("  Rate limit — retrying..."); continue
            raise
    raise RuntimeError("Groq failed after 3 attempts.")

def search_batch(queries: list, max_results: int = 4, label: str = "") -> str:
    tavily = TavilyClient(api_key=TAVILY_API_KEY)
    seen, results = set(), []
    for i, q in enumerate(queries, 1):
        q = str(q).strip()
        if not q: continue
        print(f"  [{label} {i}/{len(queries)}] {q[:80]}...")
        try:
            r = tavily.search(q, search_depth="advanced", max_results=max_results, include_raw_content=False)
            for item in r.get("results", []):
                url = item.get("url", "").strip()
                if not url or url in seen: continue
                seen.add(url)
                results.append(
                    f"QUERY: {q}\nTITLE: {item.get('title','')}\nURL: {url}\n"
                    f"DATE: {item.get('published_date','unknown')}\n"
                    f"BODY: {compact(item.get('content',''), 500)}\n---"
                )
            time.sleep(0.4)
        except Exception as e:
            print(f"    Search error: {e}")
    return "\n\n".join(results)

FALLBACK_QUERIES = [
    "paid social platform change Meta LinkedIn TikTok Reddit Google Ads 2025 2026",
    "AI automation advertising creative testing case study results data",
    "B2B paid social case study results pipeline attribution enterprise technology",
    "paid social measurement incrementality attribution MMM research 2024 2025",
    "HP Lenovo Apple Microsoft enterprise advertising campaign messaging 2025 2026",
    "WARC Effie LinkedIn B2B Institute paid social effectiveness case study",
    "AdExchanger Digiday Marketing Brew paid social research insight 2025 2026",
    "paid social creative testing practitioner teardown results specific",
]

DISCOVERY_PROMPT = """Today is {today}.

Generate 10 diverse search queries for a high-quality paid social research newsletter.

Reader: Senior paid social practitioner at a large enterprise tech company. B2B + consumer + gaming. Cares about platform mechanics, creative testing, measurement, competitor patterns, AI in advertising, in-house operating models.

Use reader context for relevance only. Do NOT make the newsletter company-specific.

Do NOT generate queries from a fixed list. Cast wide across:
- Recent platform changes (last 30-60 days)
- AI and automation in paid advertising  
- Competitor ad strategy and messaging
- Case studies with specific results (last 1-3 years)
- Research on measurement, attribution, buyer behavior
- Practitioner teardowns and operator lessons

Return ONLY valid JSON:
{{"queries": ["query 1", "query 2", "query 3", "query 4", "query 5", "query 6", "query 7", "query 8", "query 9", "query 10"]}}"""

SELECTION_PROMPT = """Today is {today}.

You are editor of a high-quality paid social newsletter. You have completed a broad research scan.

Raw results:
{landscape}

Find the single most interesting, specific, non-obvious thing worth writing about.

Do NOT pick a broad topic. Pick a specific angle or finding.
Do NOT pick something just because there is lots of material.
Do NOT force a topic the evidence does not support.

A strong opportunity has at least one of:
- A specific result with a number or mechanism attached
- A platform change with a real operational implication  
- A tension or contradiction in the data
- A competitor move that reveals a pattern
- A practitioner finding that challenges a common assumption
- A measurement shift that changes how you'd run campaigns

Issue shapes: Signal Brief | Case Teardown | Competitor Watch | Research Breakdown | Platform Shift | Measurement Warning | Creative Lesson | Operator Lesson | Contrarian Take

Return ONLY valid JSON:
{{
  "issue_shape": "the format",
  "headline": "10 words max. The actual story. Specific, not generic.",
  "core_finding": "The single most specific interesting thing. Must include a concrete detail — a number, named company, mechanism, or specific result.",
  "what_to_avoid_writing": "The obvious, boring angle on this same material you are deliberately NOT writing.",
  "follow_up_queries": ["5-7 targeted queries for specific evidence, numbers, mechanisms, examples"]
}}"""

WRITER_PROMPT = """Today is {today}.

Write one issue of a high-quality paid social newsletter.

Shape: {issue_shape}
Headline: {headline}
Core finding: {core_finding}
Angle to avoid: {what_to_avoid}

Deep research:
{deep}

Landscape research:
{landscape}

Reader: Senior paid social practitioner. Enterprise tech. B2B + consumer + gaming. Real craft: campaign decisions, creative, measurement, platform mechanics, competitor patterns. (Use for relevance only — do NOT write as a company memo.)

━━ MANDATORY WRITING RULES ━━

SPECIFICITY REQUIRED. Every claim needs at least one of: specific number, named company, named feature, specific mechanism, direct finding. No specifics = cut the sentence.

FORBIDDEN PHRASES (symptoms of generic writing — do not use):
"requires a deep understanding" / "has the potential to" / "operators can leverage X to improve Y" / "it's crucial to understand" / "by leveraging this technology" / "this can help improve ROI" / "in today's landscape" / "as X continues to evolve" / any sentence that works for any industry

EDITORIAL OPINION REQUIRED. Don't just summarize. Tell the reader what you think this means.
Use: "The more interesting implication is..." / "What this actually reveals is..." / "The non-obvious read here is..."

NO REDUNDANCY. Each field has one job. If you said it once, don't say it again differently.

THE TEST: Would a senior practitioner think "I didn't know that" or "that changes how I'd approach this"? If not, go deeper.

━━ OUTPUT FIELDS ━━

"the_lead": 2-3 sentences. The most interesting specific thing. Not context-setting. Not "AI is changing advertising." The actual surprising thing. Written like you're telling a sharp colleague at lunch.

"the_depth": 4-6 sentences. Specific numbers, named sources, mechanisms, examples. What does the evidence actually show? What makes this more than a surface observation? This is the main substance.

"the_implication": 2-3 sentences. Genuine editorial judgment. What does a practitioner actually do differently because of this? Not "consider testing X" — what specifically changes and why? If uncertain, say so honestly.

"the_watch": 1-2 sentences. One specific narrow thing to watch or test. Not a category. An actual thing.

"the_honest_caveat": 1-2 sentences. Where could this be wrong? What would change the read? Be honest — don't manufacture a caveat.

"sources": 3-6 most useful sources. Genuinely useful, not just vaguely related. One line on what makes each specifically worth reading.

"subject_line": Under 60 characters. Specific. The actual story.

Return ONLY valid JSON:
{{
  "subject_line": "...",
  "headline": "...",
  "issue_shape": "...",
  "the_lead": "...",
  "the_depth": "...",
  "the_implication": "...",
  "the_watch": "...",
  "the_honest_caveat": "...",
  "sources": [{{"title": "...", "url": "...", "source_name": "...", "date_or_recency": "...", "why_this_one": "..."}}]
}}"""

def build_html(data: dict) -> str:
    now      = datetime.now(CST)
    date_str = now.strftime("%B %d, %Y")
    week_num = now.isocalendar()[1]

    shape   = esc(data.get("issue_shape", "Deep Dive"))
    headline= esc(data.get("headline", "Paid Social Edge"))
    lead    = esc(data.get("the_lead", ""))
    depth   = esc(data.get("the_depth", ""))
    impl    = esc(data.get("the_implication", ""))
    watch   = esc(data.get("the_watch", ""))
    caveat  = esc(data.get("the_honest_caveat", ""))
    sources = safe_list(data.get("sources", []))

    src_html = ""
    for s in sources:
        if not isinstance(s, dict): continue
        url   = clean_url(s.get("url","#"))
        title = esc(s.get("title", url))
        sname = esc(s.get("source_name",""))
        date  = esc(s.get("date_or_recency",""))
        why   = esc(s.get("why_this_one",""))
        meta  = f"{sname}{' · ' if sname and date else ''}{date}"
        src_html += f"""<div style="padding:13px 0;border-bottom:1px solid #E5E7EB;">
  <p style="margin:0 0 2px;font-size:11.5px;color:#9CA3AF;">{meta}</p>
  <p style="margin:0 0 4px;font-size:13.5px;font-weight:600;color:#111827;">
    <a href="{esc(url)}" style="color:#111827;text-decoration:none;">{title}</a></p>
  <p style="margin:0 0 4px;font-size:12.5px;color:#6B7280;line-height:1.55;">{why}</p>
  <a href="{esc(url)}" style="font-size:12px;color:#2563EB;text-decoration:none;">Read →</a>
</div>"""

    if not src_html:
        src_html = '<p style="font-size:13px;color:#9CA3AF;">No sources this cycle.</p>'

    def prose_block(label: str, text: str, label_color: str = "#9CA3AF",
                    text_color: str = "#374151", bg: str = "#FFFFFF",
                    font_size: str = "14px") -> str:
        return f"""<tr><td style="background:{bg};padding:20px 28px;" bgcolor="{bg}">
  <p style="margin:0 0 8px;font-size:10px;font-weight:800;color:{label_color};
             text-transform:uppercase;letter-spacing:1px;">{label}</p>
  <p style="margin:0;font-size:{font_size};line-height:1.85;color:{text_color};">{text}</p>
</td></tr>"""

    return f"""<!DOCTYPE html><html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{headline}</title></head>
<body style="margin:0;padding:0;background:#F3F4F6;" bgcolor="#F3F4F6">
<table width="100%" bgcolor="#F3F4F6" style="background:#F3F4F6;
  font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;">
<tr><td align="center" style="padding:32px 16px;">
<table width="620" cellpadding="0" cellspacing="0" style="max-width:620px;width:100%;">

  <tr><td style="background:#064E3B;border-radius:14px 14px 0 0;padding:34px 36px 30px;" bgcolor="#064E3B">
    <p style="margin:0 0 10px;font-size:10px;font-weight:800;letter-spacing:2.5px;
               color:#6EE7B7;text-transform:uppercase;">
      Operator Deep Dive &nbsp;·&nbsp; Week {week_num} &nbsp;·&nbsp; {esc(date_str)}</p>
    <p style="margin:0 0 12px;font-size:10.5px;font-weight:700;color:#34D399;
               text-transform:uppercase;letter-spacing:1px;">{shape}</p>
    <h1 style="margin:0;font-size:22px;line-height:1.3;font-weight:800;color:#FFFFFF;">{headline}</h1>
  </td></tr>
  <tr><td style="background:#10B981;height:3px;"></td></tr>

  <tr><td style="background:#FFFFFF;padding:26px 28px 20px;" bgcolor="#FFFFFF">
    <p style="margin:0;font-size:16px;line-height:1.8;color:#111827;font-weight:500;">{lead}</p>
  </td></tr>

  {prose_block("The depth", depth)}

  <tr><td style="background:#ECFDF5;padding:20px 28px;" bgcolor="#ECFDF5">
    <p style="margin:0 0 8px;font-size:10px;font-weight:800;color:#065F46;
               text-transform:uppercase;letter-spacing:1px;">What this actually means</p>
    <p style="margin:0;font-size:14px;line-height:1.85;color:#065F46;">{impl}</p>
  </td></tr>

  <tr><td style="background:#FFFFFF;padding:20px 28px 0 28px;" bgcolor="#FFFFFF">
    <p style="margin:0 0 6px;font-size:10px;font-weight:800;color:#1D4ED8;
               text-transform:uppercase;letter-spacing:1px;">Worth watching</p>
    <p style="margin:0 0 20px;font-size:13.5px;line-height:1.75;color:#1E3A8A;">{watch}</p>
    <p style="margin:0 0 6px;font-size:10px;font-weight:800;color:#92400E;
               text-transform:uppercase;letter-spacing:1px;">Honest caveat</p>
    <p style="margin:0 0 20px;font-size:13.5px;line-height:1.75;color:#78350F;">{caveat}</p>
  </td></tr>

  <tr><td style="background:#FAFAFA;padding:20px 28px;border-top:1px solid #E5E7EB;" bgcolor="#FAFAFA">
    <p style="margin:0 0 4px;font-size:10px;font-weight:800;color:#9CA3AF;
               text-transform:uppercase;letter-spacing:1px;">Sources</p>
    {src_html}
  </td></tr>

  <tr><td style="background:#111827;border-radius:0 0 14px 14px;padding:18px 28px;
                  text-align:center;" bgcolor="#111827">
    <p style="margin:0;font-size:12px;color:#6B7280;">
      Paid Social Edge &nbsp;·&nbsp; Operator Deep Dive &nbsp;·&nbsp; Every other Tuesday</p>
  </td></tr>

</table></td></tr></table></body></html>"""

def send_email(html: str, subject: str):
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

def main():
    check_week()
    today = datetime.now(CST).strftime("%B %d, %Y")

    print("\n[Phase 1] Generating discovery queries...")
    try:
        qdata   = call_groq(DISCOVERY_PROMPT.format(today=today), max_tokens=700, temp=0.4)
        queries = qdata.get("queries", [])
        if not queries: raise ValueError("Empty")
    except Exception as e:
        print(f"  Fallback queries. ({e})")
        queries = FALLBACK_QUERIES

    print(f"  {len(queries)} queries.")

    print("\n[Phase 2] Discovery search...")
    landscape = search_batch(queries, max_results=4, label="D")
    if not landscape.strip():
        raise RuntimeError("No Tavily results.")

    print("\n[Phase 3] Selecting angle...")
    time.sleep(6)
    sel = call_groq(SELECTION_PROMPT.format(today=today, landscape=landscape[:9000]),
                    max_tokens=900, temp=0.25)
    shape    = sel.get("issue_shape", "Research Issue")
    headline = sel.get("headline", "Paid Social Edge")
    finding  = sel.get("core_finding", "")
    avoid    = sel.get("what_to_avoid_writing", "")
    followups= sel.get("follow_up_queries", queries[:5])
    print(f"  Shape: {shape} | Headline: {headline}")

    print("\n[Phase 4] Deep research...")
    time.sleep(5)
    deep = search_batch(followups, max_results=4, label="R")

    print("\n[Phase 5] Writing issue...")
    time.sleep(10)
    data = call_groq(
        WRITER_PROMPT.format(today=today, issue_shape=shape, headline=headline,
                             core_finding=finding, what_to_avoid=avoid,
                             deep=deep[:7000], landscape=landscape[:3000]),
        max_tokens=2200, temp=0.25
    )

    subject = compact(data.get("subject_line") or f"Deep Dive: {headline}", 60)
    html    = build_html(data)
    print(f"\nSubject: {subject}")
    print("[Phase 6] Sending...")
    send_email(html, subject)

if __name__ == "__main__":
    main()
