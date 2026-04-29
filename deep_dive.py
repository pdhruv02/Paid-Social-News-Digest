"""
Biweekly Operator Deep Dive — Paid Social Edge
Runs on odd ISO weeks, Tuesday 6 AM CST

Phase 1: Broad landscape scan across quality sources
Phase 2: AI selects best topic based on what material actually exists
Phase 3: Targeted deep research on that topic
Phase 4: Compile into operator-grade learning memo
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

# ── Week gate: odd weeks only ─────────────────────────────────────────────────
def check_week():
    week = datetime.now(CST).isocalendar()[1]
   # if week % 2 == 0:
    #    print(f"Week {week} is even — deep dive skips. Brief runs this week.")
        exit(0)
    print(f"Week {week} (odd) — running deep dive.")

# ── Possible topics ───────────────────────────────────────────────────────────
# These are candidates, not a rotation schedule.
# The AI picks whichever one has the strongest available material this cycle.
TOPIC_CANDIDATES = """
- Meta automation and where human edge remains (Advantage+, ASC, automated bidding)
- LinkedIn Ads for B2B demand generation (targeting, lead quality, pipeline influence)
- Reddit as a B2B research and trust channel (organic influence, paid, community strategy)
- Paid social creative testing systems (hypothesis-driven testing, velocity, signals vs noise)
- Lead quality vs lead volume in B2B paid social (CPL vs pipeline, downstream conversion)
- Incrementality and attribution for paid social (geo holdout, lift studies, true ROAS)
- MMM for paid social teams (media mix modeling, budget allocation, cross-channel)
- ABM paid social sequencing (account-based, LinkedIn + Meta coordination, pipeline)
- In-house media buying operating models (Fortune 500 in-house, structure, what to keep vs outsource)
- AI creative workflows in paid social (production, iteration, testing, personalization)
- Competitor paid social teardown: Dell vs HP vs Lenovo vs Apple vs Microsoft
- How enterprise buyers research technology purchases (B2B buyer journey, digital touchpoints)
- Upper-funnel paid social measurement (brand lift, search lift, awareness attribution)
- Creative fatigue and testing velocity (refresh cadence, fatigue signals, testing backlog)
- Building a paid social testing roadmap (prioritization, structure, hypothesis bank)
- AI PC messaging and competitive positioning (Dell XPS/Inspiron AI PCs vs competition)
- Gaming paid social creative strategy (Alienware, gaming audience, platform mix)
- Landing page and offer strategy for paid social (post-click experience, conversion, B2B offers)
"""

# ── Phase 1: Landscape scan queries ──────────────────────────────────────────
# Cast wide across high-quality sources — let the material tell us what's strong
LANDSCAPE_QUERIES = [
    "LinkedIn B2B Institute WARC Effie paid social case study effectiveness 2023 2024 2025",
    "Think with Google IPA paid social B2B case study results",
    "Meta LinkedIn Reddit paid social B2B enterprise case study 2024 2025",
    "AdExchanger Digiday Marketing Brew paid social strategy research 2024 2025",
    "Dell HP Lenovo Apple enterprise technology advertising campaign 2024 2025",
    "paid social measurement incrementality attribution research 2024 2025",
    "B2B buyer behavior enterprise technology digital paid media 2024 2025",
    "paid social creative testing brand campaign results data 2024 2025",
]

# ── Phase 1 prompt: topic selection ──────────────────────────────────────────
TOPIC_SELECTION_PROMPT = """Today is {today}.

You are deciding what topic to deep-dive on this week for a biweekly operator memo focused on Dell's paid social team.

Context: You work on Dell's in-house paid social team. Dell sells enterprise B2B IT solutions, consumer laptops/PCs, and gaming products (Alienware). Main competitors: HP, Lenovo, Apple, Microsoft.

Below are raw search results from a broad scan across paid social case study sources, research databases, and industry publications.

RAW LANDSCAPE RESULTS:
{landscape_results}

CANDIDATE TOPICS (these are possibilities, not a mandatory list — you can also pick a related topic if the material strongly suggests something else):
{topics}

YOUR TASK:
Based purely on what material actually exists in these results, select the ONE topic that:
1. Has the strongest available material (real case studies, research reports, or practitioner examples — not just opinion)
2. Is most useful for Dell paid social right now
3. Has enough substance for a meaningful 8–12 minute learning memo

Do NOT pick a topic just because it sounds good. Pick based on what the material supports.
If the results are thin overall, pick the topic with even modest quality material over one with nothing.

Return ONLY valid JSON. No markdown, no preamble.

{{
  "selected_topic": "exact topic name",
  "selection_rationale": "1–2 sentences on why this topic has the strongest material available right now",
  "focus_angle": "The specific angle or question to focus on — more specific than just the topic name",
  "suggested_search_queries": [
    "5–7 targeted search queries to find the best material on this specific topic",
    "Mix of: source-specific queries (WARC, Effie, LinkedIn B2B Institute, Think with Google), case study queries, competitor queries, practitioner queries",
    "query 3", "query 4", "query 5", "query 6", "query 7"
  ]
}}"""

# ── Phase 3 prompt: compile deep dive ────────────────────────────────────────
DEEP_DIVE_PROMPT = """Today is {today}.

You are writing a biweekly operator deep dive for yourself — a senior paid social practitioner on Dell's in-house team.

Dell context:
- Sells enterprise B2B (servers, storage, IT solutions), consumer laptops/PCs (XPS, Inspiron, Latitude), and gaming (Alienware)
- Competes with HP, Lenovo, Apple, Microsoft
- In-house model — you care about what makes internal teams sharper
- B2B has long purchase cycles, multiple stakeholders, LinkedIn + Reddit + search heavy
- Consumer and gaming are more direct-response, Meta + YouTube + TikTok heavy

This edition topic: {topic}
Focus angle: {focus_angle}

RAW RESEARCH RESULTS (from targeted sources):
{deep_results}

ALSO AVAILABLE — landscape scan results from earlier:
{landscape_results}

YOUR TASK:
Write a practical operator deep dive. This is not a news brief. It is a learning document.
Your goal: help build genuine paid social judgment on this topic.

RESEARCH WINDOW GUIDANCE (apply per source type):
- Tactical paid social material: prefer last 3 years
- Platform case studies: prefer last 3 years
- Marketing effectiveness cases (WARC, Effie, IPA): last 5–10 years allowed if still relevant — explain why
- Research reports: last 3–5 years
- Practitioner teardowns: last 3 years preferred
- Competitor examples: current or recently visible

SOURCE QUALITY RULES:
- Prioritize: original research, effectiveness databases (WARC/Effie/IPA), LinkedIn B2B Institute, Think with Google, IAB reports, strong practitioner teardowns, competitor examples
- Be careful with: platform promotional case studies (useful for ideas, not as proof), generic thought leadership, SEO blogs, unsupported claims
- Mark paywalled sources clearly as [PAYWALLED]
- If a source is only partially accessible, say so — do not pretend to have read the full piece
- If material is thin on a subtopic, say so. Do not invent or pad.

OUTPUT: Return ONLY valid JSON. No markdown fences, no preamble, no explanation.

{{
  "topic": "{topic}",
  "focus_angle": "{focus_angle}",
  "why_it_matters_for_dell": "2–3 sentences. Specific to Dell — B2B, consumer, gaming, measurement, competitive, or operational angle. Not generic.",
  "best_materials": [
    {{
      "title": "Title",
      "source": "Publication or platform",
      "date": "Date or recency (e.g. 2024, Q1 2025, Last 3 years)",
      "url": "URL",
      "type": "Research | Case Study | Platform Source | Practitioner Teardown | Competitor Example",
      "paywalled": false,
      "why_worth_reading": "One sentence on what makes this worth reading."
    }}
  ],
  "key_lessons": [
    "Actual insight — something that changes how you think or act. Not a summary.",
    "Lesson 2",
    "Lesson 3",
    "Lesson 4",
    "Lesson 5"
  ],
  "case_examples": [
    {{
      "brand": "Brand name",
      "what_they_did": "Specific — what format, targeting approach, structure, measurement, or creative architecture they used.",
      "useful_lesson": "The transferable insight. What does this reveal about how paid social actually works?",
      "dell_application": "How this could apply specifically to Dell — which segment, which platform, which use case."
    }}
  ],
  "dell_application": {{
    "b2b": "Only include if there is a real connection. How this applies to Dell enterprise/B2B paid social.",
    "consumer": "Only if real connection. Dell.com / consumer campaigns.",
    "gaming": "Only if real connection. Alienware / gaming.",
    "measurement": "Only if real connection. Measurement, attribution, or signal quality angle.",
    "creative_testing": "Only if real connection. Creative testing or format strategy.",
    "in_house_ops": "Only if real connection. In-house team operations or capability building."
  }},
  "playbook": {{
    "what_to_test": ["Specific test idea 1", "Specific test idea 2", "Specific test idea 3"],
    "what_to_measure": ["Specific metric or signal 1", "Metric 2"],
    "what_to_avoid": ["Specific pitfall 1", "Pitfall 2"]
  }},
  "internal_asset_idea": "One specific asset to build from this learning. Be concrete: what it would contain, what format, who would use it.",
  "personal_skill_takeaway": "One thing to practice, read, or learn next to compound on this topic."
}}"""


# ── Research helpers ──────────────────────────────────────────────────────────
def search_batch(queries: list, max_results: int = 5, label: str = "") -> str:
    tavily  = TavilyClient(api_key=TAVILY_API_KEY)
    results = []
    for i, q in enumerate(queries, 1):
        tag = f"[{label} {i}/{len(queries)}]" if label else f"[{i}/{len(queries)}]"
        print(f"  {tag} {q[:65]}...")
        try:
            r = tavily.search(q, search_depth="advanced", max_results=max_results,
                              include_raw_content=False)
            for item in r.get("results", []):
                results.append(
                    f"TITLE: {item.get('title','')}\n"
                    f"URL:   {item.get('url','')}\n"
                    f"DATE:  {item.get('published_date','unknown')}\n"
                    f"BODY:  {item.get('content','')[:350]}\n---"
                )
            time.sleep(0.4)
        except Exception as e:
            print(f"    Search error: {e}")
    return "\n\n".join(results)


def call_groq(prompt: str, max_tokens: int = 1500) -> dict:
    groq_client = Groq(api_key=GROQ_API_KEY)
    for attempt in range(3):
        try:
            if attempt > 0:
                print(f"  Retry {attempt}/2 after rate limit pause...")
                time.sleep(15 * attempt)
            resp  = groq_client.chat.completions.create(
                model=MODEL,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.2,
                max_tokens=max_tokens,
            )
            raw   = resp.choices[0].message.content
            clean = re.sub(r"```(?:json)?|```", "", raw).strip()
            # Find the outermost JSON object
            m = re.search(r"\{.*\}", clean, re.DOTALL)
            if not m:
                raise ValueError(f"No JSON found. Raw output:\n{raw[:400]}")
            return json.loads(m.group())
        except json.JSONDecodeError as e:
            print(f"  JSON parse error (attempt {attempt+1}): {e}")
            if attempt == 2:
                raise
        except Exception as e:
            if "rate_limit" in str(e).lower() or "429" in str(e):
                print(f"  Rate limit hit — waiting before retry...")
                continue
            raise
    raise RuntimeError("Groq call failed after 3 attempts")


# ── Email HTML ────────────────────────────────────────────────────────────────
TYPE_COLORS = {
    "Research":              "#059669",
    "Case Study":            "#7C3AED",
    "Platform Source":       "#1877F2",
    "Practitioner Teardown": "#D97706",
    "Competitor Example":    "#DC2626",
}


def material_row(m: dict) -> str:
    typ   = m.get("type", "Source")
    color = TYPE_COLORS.get(typ, "#4B5563")
    pw    = " 🔒 PAYWALLED" if m.get("paywalled") else ""
    return f"""
<tr><td style="padding:11px 0;border-bottom:1px solid #F3F4F6;">
  <table width="100%" cellpadding="0" cellspacing="0"><tr>
    <td><span style="background:{color};color:#fff;font-size:10px;font-weight:700;
                 padding:2px 9px;border-radius:12px;text-transform:uppercase;">{typ}</span>
        <span style="font-size:11px;color:#9CA3AF;margin-left:8px;">{m.get('date','')}{pw}</span>
    </td>
  </tr></table>
  <p style="margin:5px 0 2px;font-size:13.5px;font-weight:600;color:#111827;">
    <a href="{m.get('url','#')}" style="color:#111827;text-decoration:none;">{m.get('title','')}</a>
    <span style="font-weight:400;color:#6B7280;"> — {m.get('source','')}</span>
  </p>
  <p style="margin:0;font-size:12.5px;color:#6B7280;line-height:1.6;">{m.get('why_worth_reading','')}</p>
</td></tr>"""


def case_block(c: dict) -> str:
    return f"""
<div style="background:#FAFAFA;border-radius:8px;padding:16px 18px;margin-bottom:14px;border:1px solid #E5E7EB;">
  <p style="margin:0 0 8px;font-size:13px;font-weight:700;color:#111827;">{c.get('brand','')}</p>
  <p style="margin:0 0 6px;font-size:13px;color:#374151;line-height:1.7;">
    <strong>What they did:</strong> {c.get('what_they_did','')}
  </p>
  <p style="margin:0 0 6px;font-size:13px;color:#374151;line-height:1.7;">
    <strong>Lesson:</strong> {c.get('useful_lesson','')}
  </p>
  <p style="margin:0;font-size:13px;color:#1E3A8A;line-height:1.7;">
    <strong>Dell:</strong> {c.get('dell_application','')}
  </p>
</div>"""


def ul(items: list, color: str = "#374151") -> str:
    return "<ul style='margin:0;padding-left:18px;'>" + "".join(
        f'<li style="margin-bottom:8px;font-size:13.5px;color:{color};line-height:1.7;">{i}</li>'
        for i in items) + "</ul>"


def row(label: str, content: str, bg: str = "#fff") -> str:
    return f"""
<tr><td style="background:{bg};padding:20px 24px 18px;border-bottom:1px solid #F3F4F6;">
  <p style="margin:0 0 12px;font-size:10.5px;font-weight:700;color:#9CA3AF;
             text-transform:uppercase;letter-spacing:1px;">{label}</p>
  {content}
</td></tr>"""


def build_html(data: dict) -> str:
    now      = datetime.now(CST)
    date_str = now.strftime("%B %d, %Y")
    week_num = now.isocalendar()[1]

    mats_html = f'<table width="100%" cellpadding="0" cellspacing="0">{"".join(material_row(m) for m in data.get("best_materials",[]))}</table>'

    lessons_html = ul(data.get("key_lessons", []))

    cases_html = "".join(case_block(c) for c in data.get("case_examples", []))
    if not cases_html:
        cases_html = '<p style="font-size:13px;color:#9CA3AF;">No strong case examples found this cycle.</p>'

    dell_app  = data.get("dell_application", {})
    app_html  = "".join(
        f'<p style="margin:0 0 10px;font-size:13.5px;color:#374151;line-height:1.7;">'
        f'<strong style="color:#1E3A8A;">{k.replace("_"," ").title()}:</strong> {v}</p>'
        for k, v in dell_app.items() if v and v.strip()
    )

    pb = data.get("playbook", {})
    pb_html = (
        f'<p style="margin:0 0 5px;font-size:11px;font-weight:700;color:#059669;text-transform:uppercase;letter-spacing:.7px;">What to Test</p>'
        f'{ul(pb.get("what_to_test",[]), "#065F46")}'
        f'<p style="margin:12px 0 5px;font-size:11px;font-weight:700;color:#D97706;text-transform:uppercase;letter-spacing:.7px;">What to Measure</p>'
        f'{ul(pb.get("what_to_measure",[]), "#92400E")}'
        f'<p style="margin:12px 0 5px;font-size:11px;font-weight:700;color:#DC2626;text-transform:uppercase;letter-spacing:.7px;">What to Avoid</p>'
        f'{ul(pb.get("what_to_avoid",[]), "#991B1B")}'
    )

    return f"""<!DOCTYPE html><html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Operator Deep Dive — {date_str}</title></head>
<body style="margin:0;padding:0;background:#F3F4F6;" bgcolor="#F3F4F6">
<table width="100%" bgcolor="#F3F4F6" style="background:#F3F4F6;
             font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;">
<table width="100%" cellpadding="0" cellspacing="0"><tr><td align="center" style="padding:32px 16px;">
<table width="620" cellpadding="0" cellspacing="0" style="max-width:620px;width:100%;">

  <tr><td style="background:#065F46;border-radius:12px 12px 0 0;padding:32px 36px 28px;"
        bgcolor="#065F46">
    <p style="margin:0 0 5px;font-size:10px;font-weight:700;letter-spacing:2.5px;
               color:#6EE7B7;text-transform:uppercase;">
      Operator Deep Dive &nbsp;·&nbsp; Week {week_num} &nbsp;·&nbsp; {date_str}
    </p>
    <h2 style="margin:0 0 14px;font-size:22px;font-weight:800;color:#fff;line-height:1.3;">
      {data.get('topic','')}
    </h2>
    <p style="margin:0 0 8px;font-size:11px;font-weight:700;color:#34D399;text-transform:uppercase;letter-spacing:.8px;">
      Focus this edition
    </p>
    <p style="margin:0 0 14px;font-size:13.5px;color:#D1FAE5;line-height:1.7;">
      {data.get('focus_angle','')}
    </p>
    <p style="margin:0;font-size:13.5px;color:#A7F3D0;line-height:1.7;font-style:italic;">
      {data.get('why_it_matters_for_dell','')}
    </p>
  </td></tr>
  <tr><td style="background:#059669;height:3px;"></td></tr>

  <tr><td><table width="100%" cellpadding="0" cellspacing="0">
    {row("Best Materials", mats_html)}
    {row("Key Lessons", lessons_html, "#FAFAFA")}
    {row("Case Examples", cases_html)}
    {row("Dell Application", app_html, "#FAFAFA")}
    {row("Practical Playbook", pb_html)}
    <tr><td style="background:#EFF6FF;padding:18px 24px;border-bottom:1px solid #F3F4F6;" bgcolor="#EFF6FF">
      <p style="margin:0 0 6px;font-size:10.5px;font-weight:700;color:#1D4ED8;text-transform:uppercase;letter-spacing:1px;">Internal Asset Idea</p>
      <p style="margin:0;font-size:13.5px;color:#1E40AF;line-height:1.7;">{data.get('internal_asset_idea','')}</p>
    </td></tr>
    <tr><td style="background:#FEF3C7;padding:18px 24px;" bgcolor="#FEF3C7">
      <p style="margin:0 0 6px;font-size:10.5px;font-weight:700;color:#D97706;text-transform:uppercase;letter-spacing:1px;">Personal Skill Takeaway</p>
      <p style="margin:0;font-size:13.5px;color:#92400E;line-height:1.7;">{data.get('personal_skill_takeaway','')}</p>
    </td></tr>
  </table></td></tr>

  <tr><td style="background:#111827;border-radius:0 0 12px 12px;padding:18px 36px;text-align:center;" bgcolor="#111827">
    <p style="margin:0;font-size:12px;color:#6B7280;">
      Paid Social Edge &nbsp;·&nbsp; Operator Deep Dive &nbsp;·&nbsp; Dell Paid Social
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
    check_week()
    today = datetime.now(CST).strftime("%B %d, %Y")

    # Phase 1: Landscape scan
    print("\n[Phase 1] Landscape scan across quality sources...")
    landscape_raw = search_batch(LANDSCAPE_QUERIES, max_results=4, label="Scan")

    # Phase 2: AI selects topic based on available material
    print("\n[Phase 2] Pausing to avoid rate limits...")
    time.sleep(8)
    print("[Phase 2] Selecting best topic based on available material...")
    selection_prompt = TOPIC_SELECTION_PROMPT.format(
        today=today,
        landscape_results=landscape_raw[:8000],   # trim to fit Groq context
        topics=TOPIC_CANDIDATES,
    )
    selection = call_groq(selection_prompt, max_tokens=800)
    topic       = selection["selected_topic"]
    focus_angle = selection["focus_angle"]
    rationale   = selection["selection_rationale"]
    queries     = selection["suggested_search_queries"]
    print(f"  Selected topic: {topic}")
    print(f"  Rationale: {rationale}")

    # Phase 3: Deep targeted research on selected topic
    print(f"\n[Phase 3] Deep research on: {topic}...")
    time.sleep(5)
    deep_raw = search_batch(queries, max_results=4, label="Deep")

    # Phase 4: Compile
    print("\n[Phase 4] Pausing before compile call...")
    time.sleep(10)
    print("[Phase 4] Compiling operator memo...")
    deep_prompt = DEEP_DIVE_PROMPT.format(
        today=today,
        topic=topic,
        focus_angle=focus_angle,
        deep_results=deep_raw[:3500],
        landscape_results=landscape_raw[:1500],
    )
    data = call_groq(deep_prompt, max_tokens=2000)

    html    = build_html(data)
    short   = topic[:40] + ("…" if len(topic) > 40 else "")
    subject = f"Deep Dive: {short}"
    print(f"Subject: {subject}")
    send(html, subject)


if __name__ == "__main__":
    main()
