"""
Monthly Operator Deep Dive
Runs every other Tuesday (odd ISO weeks), 6 AM CST — alternates with brief.py
One topic. Deep research. Dell application. Practical playbook.
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

# ── Monthly topic rotation ────────────────────────────────────────────────────
# Rotates through topics by cycle (every 2 weeks). 12 topics = 24 weeks before repeat.
TOPICS = [
    {
        "title": "Meta Automation and Where Human Edge Remains",
        "focus": "Advantage+ campaigns, automated bidding, ASC, and where manual control still outperforms automation on Meta",
        "queries": [
            "Meta Advantage Plus campaign performance vs manual 2024 2025 case study",
            "Facebook ads automation Advantage shopping campaign results data",
            "Meta ASC automated placements creative performance research",
            "when to use manual bidding vs automated Meta ads paid social",
            "Meta Advantage Plus audience targeting B2B enterprise results",
        ]
    },
    {
        "title": "LinkedIn Ads for B2B Demand Generation",
        "focus": "LinkedIn campaign structure, targeting depth, lead quality, ABM, and what actually drives pipeline for enterprise B2B",
        "queries": [
            "LinkedIn ads B2B demand generation case study results 2024 2025",
            "LinkedIn thought leader ads performance data research",
            "LinkedIn ABM account based marketing paid social case study",
            "LinkedIn ads lead quality vs lead volume B2B research",
            "LinkedIn document ads conversation ads performance benchmark 2024 2025",
        ]
    },
    {
        "title": "Paid Social Creative Testing Systems",
        "focus": "How to build a systematic creative testing program: hypothesis-driven testing, velocity, signals vs noise, and what drives real performance lift",
        "queries": [
            "paid social creative testing framework methodology case study",
            "Meta ads creative testing systematic approach results data",
            "creative fatigue detection paid social benchmarks research",
            "ad creative testing velocity how many tests per week paid social",
            "paid social creative testing B2B enterprise case study results",
        ]
    },
    {
        "title": "Lead Quality vs Lead Volume in B2B Paid Social",
        "focus": "How to optimize for pipeline quality instead of CPL, lead scoring integration, downstream conversion data, and real examples",
        "queries": [
            "B2B paid social lead quality optimization case study 2023 2024 2025",
            "lead quality vs lead volume paid social optimization research",
            "Salesforce CRM integration paid social lead scoring optimization",
            "B2B paid social CPL vs pipeline quality measurement framework",
            "enterprise technology lead quality paid social case study",
        ]
    },
    {
        "title": "Incrementality and Attribution for Paid Social",
        "focus": "How to measure true incrementality, geo holdout tests, conversion lift studies, and what good attribution looks like for paid social",
        "queries": [
            "paid social incrementality testing methodology case study 2024 2025",
            "Meta conversion lift study results incremental ROAS research",
            "geo holdout test paid social incrementality measurement",
            "B2B paid social attribution model comparison last click vs data driven",
            "paid social incrementality measurement enterprise B2B research",
        ]
    },
    {
        "title": "Competitor Paid Social Teardown: Dell vs HP vs Lenovo vs Apple",
        "focus": "How Dell's main competitors run paid social: messaging, creative formats, audience targeting signals, landing page strategy, and gaps Dell can exploit",
        "queries": [
            "Dell HP Lenovo Apple Microsoft paid social advertising strategy 2024 2025",
            "enterprise technology B2B advertising campaign examples 2024 2025",
            "HP Lenovo laptop advertising paid social creative strategy",
            "Apple enterprise B2B advertising campaign 2024 2025",
            "Dell advertising creative strategy competitive positioning 2024 2025",
        ]
    },
    {
        "title": "How Enterprise Buyers Research Technology Purchases",
        "focus": "The actual B2B buyer journey for enterprise tech: what content they consume, which channels influence them, and how paid social fits into a long purchase cycle",
        "queries": [
            "enterprise B2B technology buyer journey research 2024 2025",
            "how CIOs IT buyers research technology purchase decision research",
            "B2B buyer behavior digital channels influence Gartner Forrester research",
            "enterprise technology purchase cycle paid media influence research",
            "LinkedIn B2B Institute enterprise buyer behavior research report",
        ]
    },
    {
        "title": "Upper-Funnel Paid Social Measurement",
        "focus": "How to measure brand and awareness campaigns in paid social: brand lift, search lift, attribution for long-cycle B2B, and practical frameworks",
        "queries": [
            "upper funnel paid social measurement framework brand lift B2B",
            "brand awareness paid social measurement attribution case study",
            "LinkedIn brand lift study enterprise B2B results data",
            "paid social awareness to conversion measurement methodology research",
            "MMM media mix modeling paid social brand measurement enterprise",
        ]
    },
    {
        "title": "AI Creative Workflows in Paid Social",
        "focus": "How teams are actually using AI for creative production, iteration, testing, and personalization in paid social — what works and what is still hype",
        "queries": [
            "AI creative production paid social advertising workflow case study 2024 2025",
            "AI generated ad creative performance vs human creative research data",
            "paid social AI creative automation Meta Google tools practical results",
            "AI ad creative tools workflow case study enterprise brand 2024 2025",
            "dynamic creative optimization AI paid social performance research",
        ]
    },
    {
        "title": "In-House Media Buying Operating Models",
        "focus": "How Fortune 500 brands structure in-house paid social teams, what they keep vs outsource, how they build internal expertise, and lessons for Dell",
        "queries": [
            "in-house media buying model Fortune 500 brand case study research",
            "in-house vs agency paid social performance comparison research 2023 2024 2025",
            "brand in-house programmatic paid media team structure case study",
            "P&G Unilever enterprise in-house media buying model results research",
            "in-house paid social team best practices operating model guide",
        ]
    },
    {
        "title": "Reddit as a B2B Research and Trust Channel",
        "focus": "How B2B buyers use Reddit in their purchase research, what paid and organic Reddit strategy looks like for enterprise tech, and case studies",
        "queries": [
            "Reddit B2B advertising case study enterprise technology 2023 2024 2025",
            "Reddit ads B2B lead generation results data research",
            "Reddit organic community B2B technology buyer research influence",
            "Reddit advertising enterprise software technology case study performance",
            "Reddit paid social B2B demand generation results benchmark",
        ]
    },
    {
        "title": "ABM Paid Social Sequencing",
        "focus": "How to build account-based paid social campaigns: audience layers, sequencing logic, cross-platform coordination, and pipeline impact measurement",
        "queries": [
            "ABM account based marketing paid social campaign case study 2023 2024 2025",
            "LinkedIn ABM sequencing strategy B2B enterprise results",
            "account based marketing paid social cross channel sequencing research",
            "ABM paid social pipeline influence measurement attribution case study",
            "B2B ABM advertising campaign structure LinkedIn Meta results data",
        ]
    },
]


def get_topic_for_cycle() -> dict:
    # Rotate by week number — new topic every odd week
    week = datetime.now(CST).isocalendar()[1]
  # if week % 2 == 0:
    #    print(f"Week {week} is even — skipping. Deep dive runs on odd weeks only.")
     #   exit(0)
    cycle = (week // 2) % len(TOPICS)
    return TOPICS[cycle]


# ── Prompt ────────────────────────────────────────────────────────────────────
DEEP_DIVE_PROMPT = """Today is {today}.

You are a senior paid social operator building a deep learning memo for yourself.

Context: You work on Dell's in-house paid social team. Dell sells enterprise B2B solutions, consumer laptops/PCs, and gaming products (Alienware). Main competitors: HP, Lenovo, Apple, Microsoft.

This Month's Topic: {topic_title}
Focus area: {topic_focus}

RAW RESEARCH RESULTS:
{search_results}

YOUR TASK:
Produce a practical operator deep dive on this topic. Your goal is to help build genuine paid social judgment — not a content summary. You are writing this for yourself as an operator, not for an audience.

Use the research provided, but also apply your own knowledge of paid social best practices, platforms, and effectiveness research. If the search results are thin on a subtopic, say so clearly. Do not invent sources or fabricate data.

QUALITY BAR:
- Only cite sources that are genuinely useful — not just any source with a matching title
- Prefer: research reports, effectiveness case studies, platform technical documentation, practitioner teardowns
- Flag paywalled sources clearly as [PAYWALLED]
- For platform case studies: treat as useful for ideas, not as proof
- Do NOT pad the output. If fewer good sources exist, include fewer.

OUTPUT: Return ONLY valid JSON. No markdown fences, no preamble.

{{
  "topic": "{topic_title}",
  "why_it_matters_for_dell": "2–3 sentences. Why this topic is specifically relevant to Dell paid social — B2B, consumer, gaming, measurement, competitive, or operational angle.",
  "best_materials": [
    {{
      "title": "Title of article, study, or resource",
      "source": "Publication or platform name",
      "date": "Date or recency",
      "url": "URL",
      "type": "Research | Case Study | Platform Source | Practitioner Teardown | Competitor Example",
      "paywalled": false,
      "one_line": "One sentence on why this is worth reading."
    }}
  ],
  "key_lessons": [
    "Lesson 1 — actual insight, not a summary. Something actionable.",
    "Lesson 2",
    "Lesson 3",
    "Lesson 4",
    "Lesson 5"
  ],
  "case_examples": [
    {{
      "brand": "Brand name",
      "what_they_did": "Specific description of what they did in paid social — format, targeting, structure, or measurement approach.",
      "useful_lesson": "The transferable lesson — what this reveals about paid social mechanics or strategy.",
      "dell_application": "How this could apply to Dell specifically."
    }}
  ],
  "dell_application": {{
    "b2b": "How this applies to Dell B2B / enterprise paid social. If not applicable, omit this field.",
    "consumer": "How this applies to Dell.com / consumer campaigns. If not applicable, omit.",
    "gaming": "How this applies to Alienware / gaming. If not applicable, omit.",
    "measurement": "Measurement or attribution angle for Dell. If not applicable, omit.",
    "creative_testing": "Creative testing angle for Dell. If not applicable, omit.",
    "in_house_ops": "In-house operations angle for Dell. If not applicable, omit."
  }},
  "playbook": {{
    "what_to_test": ["test idea 1", "test idea 2", "test idea 3"],
    "what_to_measure": ["metric or signal 1", "metric or signal 2"],
    "what_to_avoid": ["pitfall 1", "pitfall 2"]
  }},
  "internal_asset_idea": "One specific internal asset that could be created from this learning, and what it would contain. Be specific.",
  "personal_skill_takeaway": "One thing to practice, read, or learn next to get sharper on this topic."
}}"""


# ── Research ──────────────────────────────────────────────────────────────────
def run_searches(queries: list) -> str:
    tavily  = TavilyClient(api_key=TAVILY_API_KEY)
    results = []
    for i, q in enumerate(queries, 1):
        print(f"  [{i}/{len(queries)}] {q[:65]}...")
        try:
            r = tavily.search(q, search_depth="advanced", max_results=5, include_raw_content=False)
            for item in r.get("results", []):
                results.append(
                    f"TITLE: {item.get('title','')}\n"
                    f"URL:   {item.get('url','')}\n"
                    f"DATE:  {item.get('published_date','unknown')}\n"
                    f"BODY:  {item.get('content','')[:700]}\n---"
                )
            time.sleep(0.5)
        except Exception as e:
            print(f"    Search error: {e}")
    return "\n\n".join(results)


def compile_deep_dive(raw: str, topic: dict) -> dict:
    groq   = Groq(api_key=GROQ_API_KEY)
    today  = datetime.now(CST).strftime("%B %d, %Y")
    prompt = DEEP_DIVE_PROMPT.format(
        today=today,
        topic_title=topic["title"],
        topic_focus=topic["focus"],
        search_results=raw,
    )
    print("  Compiling with Groq...")
    resp = groq.chat.completions.create(
        model=MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.2,
        max_tokens=4000,
    )
    raw_text = resp.choices[0].message.content
    clean    = re.sub(r"```(?:json)?|```", "", raw_text).strip()
    m = re.search(r"\{.*\}", clean, re.DOTALL)
    if not m:
        raise ValueError(f"No JSON:\n{raw_text[:400]}")
    return json.loads(m.group())


# ── Email HTML ────────────────────────────────────────────────────────────────
TYPE_COLORS = {
    "Research":              "#059669",
    "Case Study":            "#7C3AED",
    "Platform Source":       "#1877F2",
    "Practitioner Teardown": "#D97706",
    "Competitor Example":    "#DC2626",
}


def material_html(m: dict) -> str:
    typ   = m.get("type", "Source")
    color = TYPE_COLORS.get(typ, "#4B5563")
    pw    = " 🔒" if m.get("paywalled") else ""
    return f"""
<tr><td style="padding:10px 0;border-bottom:1px solid #F3F4F6;">
  <span style="background:{color};color:#fff;font-size:10px;font-weight:700;
               padding:2px 8px;border-radius:12px;text-transform:uppercase;
               letter-spacing:.5px;">{typ}</span>
  <span style="font-size:11px;color:#9CA3AF;margin-left:8px;">{m.get('date','')}{pw}</span>
  <p style="margin:5px 0 2px;font-size:13.5px;font-weight:600;color:#111827;">
    <a href="{m.get('url','#')}" style="color:#111827;text-decoration:none;">{m.get('title','')}</a>
    &nbsp;<span style="font-size:12px;color:#6B7280;">— {m.get('source','')}</span>
  </p>
  <p style="margin:0;font-size:12.5px;color:#6B7280;">{m.get('one_line','')}</p>
</td></tr>"""


def case_html(c: dict) -> str:
    return f"""
<div style="background:#FAFAFA;border-radius:8px;padding:16px 18px;margin-bottom:14px;
             border:1px solid #E5E7EB;">
  <p style="margin:0 0 6px;font-size:13px;font-weight:700;color:#111827;">{c.get('brand','')}</p>
  <p style="margin:0 0 5px;font-size:13px;color:#374151;line-height:1.65;">
    <strong>What they did:</strong> {c.get('what_they_did','')}
  </p>
  <p style="margin:0 0 5px;font-size:13px;color:#374151;line-height:1.65;">
    <strong>Lesson:</strong> {c.get('useful_lesson','')}
  </p>
  <p style="margin:0;font-size:13px;color:#1D4ED8;line-height:1.65;">
    <strong>Dell:</strong> {c.get('dell_application','')}
  </p>
</div>"""


def section(title: str, content: str, bg: str = "#ffffff") -> str:
    return f"""
<tr><td style="background:{bg};padding:20px 24px;border-bottom:1px solid #F3F4F6;">
  <p style="margin:0 0 12px;font-size:11px;font-weight:700;color:#6B7280;
             text-transform:uppercase;letter-spacing:.9px;">{title}</p>
  {content}
</td></tr>"""


def build_deep_dive_html(data: dict, topic: dict) -> str:
    now      = datetime.now(CST)
    date_str = now.strftime("%B %d, %Y")
    month    = now.strftime("%B %Y")

    # Materials
    mats_html = f'<table width="100%" cellpadding="0" cellspacing="0">{"".join(material_html(m) for m in data.get("best_materials",[]))}</table>'

    # Key lessons
    lessons   = data.get("key_lessons", [])
    les_html  = "<ul style='margin:0;padding-left:18px;'>" + "".join(
        f'<li style="margin-bottom:9px;font-size:13.5px;color:#374151;line-height:1.7;">{l}</li>'
        for l in lessons) + "</ul>"

    # Case examples
    cases_html = "".join(case_html(c) for c in data.get("case_examples", []))

    # Dell application
    dell_app   = data.get("dell_application", {})
    app_items  = [(k.replace("_", " ").title(), v) for k, v in dell_app.items() if v]
    app_html   = "".join(
        f'<p style="margin:0 0 10px;font-size:13.5px;color:#374151;line-height:1.7;">'
        f'<strong style="color:#1E40AF;">{k}:</strong> {v}</p>'
        for k, v in app_items
    )

    # Playbook
    pb     = data.get("playbook", {})
    def pb_list(items, color):
        return "<ul style='margin:0 0 12px;padding-left:18px;'>" + "".join(
            f'<li style="margin-bottom:6px;font-size:13.5px;color:{color};line-height:1.65;">{i}</li>'
            for i in items) + "</ul>"

    pb_html = (
        f'<p style="margin:0 0 4px;font-size:11px;font-weight:700;color:#059669;text-transform:uppercase;letter-spacing:.7px;">What to Test</p>'
        f'{pb_list(pb.get("what_to_test",[]), "#065F46")}'
        f'<p style="margin:0 0 4px;font-size:11px;font-weight:700;color:#D97706;text-transform:uppercase;letter-spacing:.7px;">What to Measure</p>'
        f'{pb_list(pb.get("what_to_measure",[]), "#92400E")}'
        f'<p style="margin:0 0 4px;font-size:11px;font-weight:700;color:#DC2626;text-transform:uppercase;letter-spacing:.7px;">What to Avoid</p>'
        f'{pb_list(pb.get("what_to_avoid",[]), "#991B1B")}'
    )

    return f"""<!DOCTYPE html><html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Operator Deep Dive — {month}</title></head>
<body style="margin:0;padding:0;background:#F3F4F6;
             font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;">
<table width="100%" cellpadding="0" cellspacing="0"><tr><td align="center" style="padding:32px 16px;">
<table width="620" cellpadding="0" cellspacing="0" style="max-width:620px;width:100%;">

  <!-- Header -->
  <tr><td style="background:linear-gradient(135deg,#064E3B 0%,#065F46 50%,#047857 100%);
                  border-radius:12px 12px 0 0;padding:32px 36px 28px;">
    <p style="margin:0 0 5px;font-size:10px;font-weight:700;letter-spacing:2.5px;
               color:#6EE7B7;text-transform:uppercase;">
      Monthly Deep Dive &nbsp;·&nbsp; {month}
    </p>
    <h1 style="margin:0 0 10px;font-size:14px;font-weight:600;color:#A7F3D0;letter-spacing:.3px;">
      Operator Deep Dive
    </h1>
    <h2 style="margin:0 0 14px;font-size:22px;font-weight:800;color:#ffffff;line-height:1.3;">
      {data.get('topic', topic['title'])}
    </h2>
    <p style="margin:0;font-size:13.5px;color:#D1FAE5;line-height:1.7;">
      {data.get('why_it_matters_for_dell','')}
    </p>
  </td></tr>
  <tr><td style="background:#059669;height:3px;"></td></tr>

  <!-- Body sections -->
  <tr><td>
  <table width="100%" cellpadding="0" cellspacing="0">

    {section("Best Materials", mats_html)}

    {section("Key Lessons", les_html, "#FAFAFA")}

    {section("Case Examples", cases_html if cases_html else "<p style='color:#9CA3AF;font-size:13px;'>No strong case examples found this cycle.</p>")}

    {section("Dell Application", app_html, "#FAFAFA")}

    {section("Practical Playbook", pb_html)}

    <tr><td style="background:#EFF6FF;padding:18px 24px;border-bottom:1px solid #F3F4F6;">
      <p style="margin:0 0 8px;font-size:11px;font-weight:700;color:#1D4ED8;
                 text-transform:uppercase;letter-spacing:.8px;">Internal Asset Idea</p>
      <p style="margin:0;font-size:13.5px;color:#1E40AF;line-height:1.7;">
        {data.get('internal_asset_idea','')}
      </p>
    </td></tr>

    <tr><td style="background:#FEF3C7;padding:18px 24px;">
      <p style="margin:0 0 8px;font-size:11px;font-weight:700;color:#D97706;
                 text-transform:uppercase;letter-spacing:.8px;">Personal Skill Takeaway</p>
      <p style="margin:0;font-size:13.5px;color:#92400E;line-height:1.7;">
        {data.get('personal_skill_takeaway','')}
      </p>
    </td></tr>

  </table>
  </td></tr>

  <!-- Footer -->
  <tr><td style="background:#111827;border-radius:0 0 12px 12px;padding:18px 36px;text-align:center;">
    <p style="margin:0;font-size:12px;color:#6B7280;line-height:1.6;">
      Paid Social Edge &nbsp;·&nbsp; Monthly Operator Deep Dive &nbsp;·&nbsp;
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
    topic   = get_topic_for_cycle()
    month   = datetime.now(CST).strftime("%B %d, %Y")
    print(f"Monthly deep dive topic: {topic['title']}")

    raw     = run_searches(topic["queries"])
    data    = compile_deep_dive(raw, topic)

    html    = build_deep_dive_html(data, topic)
    # Short subject: under 60 chars
    short   = topic["title"][:42] + ("…" if len(topic["title"]) > 42 else "")
    subject = f"Deep Dive — {short} | {month}"
    print(f"Subject: {subject}")
    send(html, subject)


if __name__ == "__main__":
    main()
