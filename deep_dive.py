"""
Paid Social Edge — Evidence-Led Paid Social Newsletter
Runs on odd ISO weeks, Tuesday 6 AM CST

Core logic:
Phase 1: AI generates diverse discovery queries
Phase 2: Tavily searches broadly
Phase 3: AI decides what this issue should be based on evidence
Phase 4: Tavily performs targeted follow-up research
Phase 5: AI writes a flexible, high-quality operator newsletter
Phase 6: Email is sent via Resend

No memory file.
No fixed topic list.
No forced case studies.
No Dell-branded teaching tone.
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


# ── Optional week gate: odd weeks only ─────────────────────────────────────────

def check_week():
    """
    Keeps this as a biweekly run using odd ISO weeks.
    If your scheduler already controls cadence, comment out check_week()
    inside main().
    """
    week = datetime.now(CST).isocalendar()[1]
    #if week % 2 == 0:
     #   print(f"Week {week} is even — skipping this biweekly run.")
     #   exit(0)
    print(f"Week {week} is odd — running Paid Social Edge issue.")


# ── Helpers ───────────────────────────────────────────────────────────────────

def esc(value) -> str:
    """Escape text for safe email HTML."""
    if value is None:
        return ""
    return html_lib.escape(str(value), quote=True)


def clean_url(url: str) -> str:
    if not url:
        return "#"
    return str(url).strip()


def safe_list(value):
    if isinstance(value, list):
        return value
    if value is None:
        return []
    return [str(value)]


def compact_text(text: str, max_chars: int) -> str:
    if not text:
        return ""
    text = re.sub(r"\s+", " ", str(text)).strip()
    if len(text) <= max_chars:
        return text
    return text[:max_chars].rsplit(" ", 1)[0] + "..."


def extract_json(raw: str) -> dict:
    """
    Extract JSON object from model output.
    Handles accidental markdown fences or small preambles.
    """
    clean = re.sub(r"```(?:json)?|```", "", raw or "").strip()
    match = re.search(r"\{.*\}", clean, re.DOTALL)

    if not match:
        raise ValueError(f"No JSON object found in model output:\n{raw[:800]}")

    return json.loads(match.group())


def call_groq(prompt: str, max_tokens: int = 1800, temperature: float = 0.25) -> dict:
    groq_client = Groq(api_key=GROQ_API_KEY)

    for attempt in range(3):
        try:
            if attempt > 0:
                wait = 15 * attempt
                print(f"  Retry {attempt}/2 after {wait}s pause...")
                time.sleep(wait)

            resp = groq_client.chat.completions.create(
                model=MODEL,
                messages=[{"role": "user", "content": prompt}],
                temperature=temperature,
                max_tokens=max_tokens,
            )

            raw = resp.choices[0].message.content
            return extract_json(raw)

        except json.JSONDecodeError as e:
            print(f"  JSON parse error attempt {attempt + 1}: {e}")
            if attempt == 2:
                raise

        except Exception as e:
            err = str(e).lower()
            if "rate_limit" in err or "429" in err:
                print("  Rate limit hit — retrying after pause...")
                continue
            raise

    raise RuntimeError("Groq call failed after 3 attempts.")


# ── Prompts ───────────────────────────────────────────────────────────────────

def build_discovery_query_prompt(today: str) -> str:
    return f"""
Today is {today}.

You are creating search queries for a high-quality paid social research newsletter.

Private reader context:
- The reader works in paid social at a large technology company.
- They care about paid social strategy, creative testing, measurement, attribution, platform automation, B2B buyer behavior, competitor messaging, AI workflows, and in-house media operations.
- Relevant categories include enterprise technology, consumer PCs/laptops, gaming, AI PCs, B2B demand generation, and performance media.

Important:
This private context is only for relevance filtering.
Do NOT make the newsletter sound company-specific.
Do NOT write as if you are teaching the reader's company what to do.
Do NOT overuse company names unless discussing public examples.

Your job:
Generate broad, diverse discovery queries for this run.

Do NOT generate queries from a fixed syllabus.
Do NOT only search for case studies.
Do NOT only search for LinkedIn or B2B.
Do NOT assume what the issue will be about.

The goal is to discover what is worth writing about this time.

Cover different evidence types:
- Platform changes
- AI and automation in advertising
- Competitor activity and messaging
- Case studies or campaign examples
- Research reports
- Practitioner/operator teardowns
- Buyer behavior
- Measurement and attribution
- Creative strategy
- In-house media or operating model shifts

Use a mix of recent and evergreen-oriented queries.
Some queries should look for recent developments.
Some should look for strong case studies or research from the last few years.

Return ONLY valid JSON.

{{
  "queries": [
    "query 1",
    "query 2",
    "query 3",
    "query 4",
    "query 5",
    "query 6",
    "query 7",
    "query 8",
    "query 9",
    "query 10"
  ]
}}
"""


def build_issue_selection_prompt(today: str, landscape_results: str) -> str:
    return f"""
Today is {today}.

You are not choosing from a fixed topic list.

You are acting as the editor of a high-quality paid social operator newsletter.

The goal is not to create a generic marketing newsletter.
The goal is to discover the most useful paid social learning opportunity from this research run.

Private reader context:
- The reader works in paid social at a large technology company.
- They care about creative, measurement, platform automation, competitor positioning, B2B buyer behavior, campaign testing, and in-house media operations.
- Relevant categories include enterprise technology, consumer PCs/laptops, gaming, AI PCs, and B2B demand generation.

Important voice rule:
Use the private reader context only to judge relevance.
Do NOT write the issue as if it is teaching the reader's company what to do.
Do NOT say things like “the team must,” “the company should,” “this proves the team needs to,” or similar.
The final issue should feel like a smart external newsletter for paid social operators.

Raw research results:
{landscape_results}

Your task:
Look across the raw results and decide what this issue should actually be about.

Do NOT force a topic.
Do NOT pick the broadest or most obvious theme.
Do NOT choose something just because there is a lot of material on it.
Do NOT write about a generic evergreen topic unless the sources found in this run reveal a useful angle.
Do NOT force a case study.
Do NOT force a platform update.
Do NOT force company-specific relevance if the connection is weak.

Instead, identify the strongest research opportunity from this specific run.

A strong opportunity may come from:
- A meaningful platform change
- A strong case study
- A competitor messaging pattern
- A new research report
- A practitioner teardown
- A buyer behavior insight
- A measurement or attribution warning
- A creative testing lesson
- An AI/automation shift
- A surprising connection across multiple sources
- A useful warning about an overhyped idea

Ask yourself:
1. What would be genuinely useful for a paid social operator?
2. What feels specific to the sources found this time?
3. What is not just a generic topic anyone could write about?
4. What would make the reader think differently, test differently, measure differently, or explain something better?
5. What would be worth reading even if the reader is busy?

Choose the issue shape based on the evidence.

Possible issue shapes:
- Signal Brief
- Case Teardown
- Competitor Watch
- Research Breakdown
- Operator Lesson
- Platform Shift Memo
- Measurement Warning
- Creative Swipe File
- Buyer Behavior Note
- In-House Ops Memo

These are not mandatory categories.
Use a different shape if the evidence calls for it.

If the raw results are weak:
- Do not pretend there is a major insight.
- Choose a smaller but useful angle.
- Clearly say the evidence is thin.

Return ONLY valid JSON.

{{
  "issue_shape": "The format this issue should take",
  "issue_title": "Specific title, not a broad generic topic",
  "core_angle": "The sharp question or learning this issue should focus on",
  "why_this_issue": "Why this is the most useful opportunity from this research run",
  "what_not_to_do": "What obvious or generic angle you are intentionally avoiding",
  "evidence_to_use": [
    {{
      "title": "Source title",
      "source": "Source name",
      "url": "URL",
      "date_or_recency": "Date or recency",
      "why_it_matters": "Why this source supports the issue"
    }}
  ],
  "targeted_search_queries": [
    "5 to 8 follow-up queries to deepen this exact issue angle"
  ]
}}
"""


def build_issue_writer_prompt(
    today: str,
    issue_shape: str,
    issue_title: str,
    core_angle: str,
    why_this_issue: str,
    what_not_to_do: str,
    deep_results: str,
    landscape_results: str
) -> str:
    return f"""
Today is {today}.

You are writing a high-quality paid social operator newsletter.

This is not a generic marketing newsletter.
This is not a company memo.
This is not a fixed-format deep dive.
This issue should follow the evidence and the selected issue shape.

Issue shape:
{issue_shape}

Issue title:
{issue_title}

Core angle:
{core_angle}

Why this issue was selected:
{why_this_issue}

Obvious/generic angle to avoid:
{what_not_to_do}

Raw targeted research:
{deep_results}

Earlier landscape results:
{landscape_results}

Private reader context:
- The reader works in paid social at a large technology company.
- They care about campaign decisions, creative testing, measurement quality, buyer behavior, platform automation, competitor patterns, and in-house team capability.
- Relevant categories include enterprise tech, consumer tech, gaming, B2B demand generation, AI PCs, and performance media.

Very important voice rules:
- Do NOT write as if you are teaching the reader's company what to do.
- Do NOT say “the team must,” “the company should,” “the brand needs to,” or similar.
- Do NOT overuse any specific company name.
- Do NOT make the output sound like an internal strategy memo directed at leadership.
- Write like a smart external paid social newsletter: analytical, practical, sharp, and respectful.
- Use phrases like “a useful takeaway,” “one practical implication,” “where this applies,” “worth testing,” “worth watching,” or “the operator lesson.”
- Keep the tone confident but not prescriptive.
- Make the reader feel smarter, not judged.

Your goal:
Write a useful, sharp, operator-grade research issue.

The output should help the reader do at least one of these:
- Think better about paid social strategy
- Test better creative
- Understand platform changes
- Improve measurement judgment
- Understand buyers better
- Spot competitor patterns
- Build a useful internal asset
- Make better paid social decisions

Rules:
- Do not force sections that do not fit.
- Do not force case studies if the case material is weak.
- Do not force B2B, consumer, gaming, measurement, creative, and ops sections if only some are relevant.
- Do not summarize every source one by one unless that is useful.
- Do not overstate platform promotional case studies.
- Mark paywalled or partially accessible sources clearly.
- If evidence is thin, say so.
- Prefer sharp judgment over completeness.
- Be specific and practical.
- Avoid generic marketing language.
- Avoid corporate-sounding recommendations.

Return ONLY valid JSON.

{{
  "issue_shape": "{issue_shape}",
  "title": "{issue_title}",
  "core_angle": "{core_angle}",
  "opening": "Short 2-3 sentence setup explaining why this matters.",
  "main_takeaway": "The one big idea the reader should remember.",
  "what_was_found": [
    {{
      "source": "Source name",
      "date_or_recency": "Date or recency",
      "url": "URL",
      "finding": "What was found",
      "why_it_matters": "Why this matters for paid social"
    }}
  ],
  "operator_lessons": [
    "Practical lesson 1",
    "Practical lesson 2",
    "Practical lesson 3"
  ],
  "practical_implication": "Specific application for paid social operators. Keep this practical and avoid company-specific prescriptions.",
  "what_to_test_or_monitor": [
    "Specific test, question, or monitoring idea 1",
    "Specific test, question, or monitoring idea 2"
  ],
  "what_not_to_overlearn": [
    "Caveat or limitation 1",
    "Caveat or limitation 2"
  ],
  "internal_asset_idea": "One useful asset this could become, if applicable.",
  "best_links": [
    {{
      "title": "Title",
      "url": "URL"
    }}
  ],
  "subject_line": "Email subject line under 70 characters"
}}
"""


# ── Research functions ────────────────────────────────────────────────────────

def search_batch(queries: list, max_results: int = 5, label: str = "") -> str:
    tavily = TavilyClient(api_key=TAVILY_API_KEY)
    seen_urls = set()
    results = []

    for i, q in enumerate(queries, 1):
        q = str(q).strip()
        if not q:
            continue

        tag = f"[{label} {i}/{len(queries)}]" if label else f"[{i}/{len(queries)}]"
        print(f"  {tag} {q[:90]}...")

        try:
            response = tavily.search(
                q,
                search_depth="advanced",
                max_results=max_results,
                include_raw_content=False
            )

            for item in response.get("results", []):
                url = item.get("url", "").strip()
                if not url or url in seen_urls:
                    continue

                seen_urls.add(url)

                title = item.get("title", "")
                published_date = item.get("published_date", "unknown")
                content = item.get("content", "")

                results.append(
                    f"QUERY: {q}\n"
                    f"TITLE: {title}\n"
                    f"URL: {url}\n"
                    f"DATE: {published_date}\n"
                    f"BODY: {compact_text(content, 650)}\n"
                    f"---"
                )

            time.sleep(0.4)

        except Exception as e:
            print(f"    Search error: {e}")

    return "\n\n".join(results)


def fallback_discovery_queries() -> list:
    return [
        "latest paid social advertising platform updates Meta LinkedIn Reddit TikTok Google Ads",
        "AI automation advertising paid social campaign management creative optimization",
        "paid social measurement attribution incrementality MMM research report",
        "B2B buyer behavior enterprise technology marketing research report",
        "paid social creative testing case study campaign teardown",
        "HP Lenovo Apple Microsoft AI PC advertising campaign messaging",
        "LinkedIn Ads Reddit Ads Meta Ads B2B case study campaign results",
        "AdExchanger Digiday Marketing Brew paid social AI advertising automation",
        "Think with Google IAB WARC Effie advertising effectiveness case study digital media",
        "paid social practitioner teardown LinkedIn Meta Reddit creative measurement"
    ]


# ── Email HTML ────────────────────────────────────────────────────────────────

def bullet_list(items: list, color: str = "#374151") -> str:
    items = [i for i in safe_list(items) if str(i).strip()]
    if not items:
        return '<p style="margin:0;font-size:13px;color:#9CA3AF;">No strong points included this cycle.</p>'

    return (
        "<ul style='margin:0;padding-left:18px;'>"
        + "".join(
            f'<li style="margin-bottom:8px;font-size:13.5px;color:{color};line-height:1.7;">{esc(i)}</li>'
            for i in items
        )
        + "</ul>"
    )


def section(label: str, content: str, bg: str = "#FFFFFF") -> str:
    return f"""
<tr>
  <td style="background:{bg};padding:22px 26px;border-bottom:1px solid #F3F4F6;">
    <p style="margin:0 0 12px;font-size:10.5px;font-weight:800;color:#9CA3AF;
              text-transform:uppercase;letter-spacing:1px;">{esc(label)}</p>
    {content}
  </td>
</tr>
"""


def finding_block(item: dict) -> str:
    source = esc(item.get("source", ""))
    date = esc(item.get("date_or_recency", ""))
    url = clean_url(item.get("url", "#"))
    finding = esc(item.get("finding", ""))
    why = esc(item.get("why_it_matters", ""))

    return f"""
<div style="padding:15px 0;border-bottom:1px solid #E5E7EB;">
  <p style="margin:0 0 4px;font-size:12px;color:#6B7280;">
    <strong>{source}</strong>{' · ' if source and date else ''}{date}
  </p>
  <p style="margin:0 0 8px;font-size:13.5px;line-height:1.65;color:#111827;">
    {finding}
  </p>
  <p style="margin:0 0 8px;font-size:13px;line-height:1.65;color:#4B5563;">
    <strong>Why it matters:</strong> {why}
  </p>
  <p style="margin:0;font-size:12.5px;">
    <a href="{esc(url)}" style="color:#2563EB;text-decoration:none;">Read source →</a>
  </p>
</div>
"""


def findings_html(items: list) -> str:
    items = safe_list(items)
    if not items:
        return '<p style="margin:0;font-size:13px;color:#9CA3AF;">No strong evidence found this cycle.</p>'

    return "".join(finding_block(i) for i in items if isinstance(i, dict))


def links_html(items: list) -> str:
    items = safe_list(items)
    clean_items = [i for i in items if isinstance(i, dict) and i.get("url")]

    if not clean_items:
        return '<p style="margin:0;font-size:13px;color:#9CA3AF;">No links included.</p>'

    return (
        "<ul style='margin:0;padding-left:18px;'>"
        + "".join(
            f'<li style="margin-bottom:8px;font-size:13px;line-height:1.6;">'
            f'<a href="{esc(clean_url(i.get("url")))}" style="color:#2563EB;text-decoration:none;">'
            f'{esc(i.get("title", i.get("url")))}</a></li>'
            for i in clean_items
        )
        + "</ul>"
    )


def build_html(data: dict) -> str:
    now = datetime.now(CST)
    date_str = now.strftime("%B %d, %Y")
    week_num = now.isocalendar()[1]

    title = data.get("title", "Paid Social Edge")
    issue_shape = data.get("issue_shape", "Research Issue")
    core_angle = data.get("core_angle", "")

    opening = data.get("opening", "")
    main_takeaway = data.get("main_takeaway", "")
    practical_implication = data.get("practical_implication", "")
    internal_asset = data.get("internal_asset_idea", "")

    findings = data.get("what_was_found", [])
    lessons = data.get("operator_lessons", [])
    tests = data.get("what_to_test_or_monitor", [])
    caveats = data.get("what_not_to_overlearn", [])
    links = data.get("best_links", [])

    opening_html = f"""
<p style="margin:0;font-size:14px;line-height:1.75;color:#374151;">{esc(opening)}</p>
"""

    takeaway_html = f"""
<p style="margin:0;font-size:15px;line-height:1.75;color:#065F46;font-weight:700;">{esc(main_takeaway)}</p>
"""

    implication_html = f"""
<p style="margin:0;font-size:13.5px;line-height:1.75;color:#1E3A8A;">{esc(practical_implication)}</p>
"""

    asset_html = f"""
<p style="margin:0;font-size:13.5px;line-height:1.75;color:#92400E;">{esc(internal_asset)}</p>
"""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>{esc(title)}</title>
</head>

<body style="margin:0;padding:0;background:#F3F4F6;" bgcolor="#F3F4F6">
<table width="100%" bgcolor="#F3F4F6" style="background:#F3F4F6;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;">
  <tr>
    <td align="center" style="padding:32px 16px;">
      <table width="640" cellpadding="0" cellspacing="0" style="max-width:640px;width:100%;">

        <tr>
          <td style="background:#064E3B;border-radius:14px 14px 0 0;padding:34px 36px 30px;" bgcolor="#064E3B">
            <p style="margin:0 0 8px;font-size:10px;font-weight:800;letter-spacing:2.3px;color:#6EE7B7;text-transform:uppercase;">
              Paid Social Edge · Week {week_num} · {esc(date_str)}
            </p>

            <p style="margin:0 0 10px;font-size:11px;font-weight:800;color:#34D399;text-transform:uppercase;letter-spacing:1px;">
              {esc(issue_shape)}
            </p>

            <h1 style="margin:0 0 16px;font-size:24px;line-height:1.25;font-weight:850;color:#FFFFFF;">
              {esc(title)}
            </h1>

            <p style="margin:0;font-size:14px;line-height:1.65;color:#D1FAE5;">
              {esc(core_angle)}
            </p>
          </td>
        </tr>

        <tr>
          <td style="background:#10B981;height:4px;"></td>
        </tr>

        {section("Why this matters", opening_html)}
        {section("Main takeaway", takeaway_html, "#ECFDF5")}
        {section("What was found", findings_html(findings))}
        {section("Operator lessons", bullet_list(lessons), "#FAFAFA")}
        {section("Practical implication", implication_html, "#EFF6FF")}
        {section("What to test or monitor", bullet_list(tests, "#065F46"))}
        {section("What not to overlearn", bullet_list(caveats, "#991B1B"), "#FEF2F2")}
        {section("Internal asset idea", asset_html, "#FEF3C7")}
        {section("Best links", links_html(links))}

        <tr>
          <td style="background:#111827;border-radius:0 0 14px 14px;padding:18px 36px;text-align:center;" bgcolor="#111827">
            <p style="margin:0;font-size:12px;color:#9CA3AF;">
              Paid Social Edge · Evidence-led research for paid social operators
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

def send_email(html: str, subject: str):
    resend.api_key = RESEND_API_KEY

    with open(SUBSCRIBERS_FILE) as f:
        subs = json.load(f)

    emails = subs.get("emails", [])
    if not emails:
        print("No subscribers found.")
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
    check_week()

    today = datetime.now(CST).strftime("%B %d, %Y")

    print("\n[Phase 1] Generating diverse discovery queries...")
    query_prompt = build_discovery_query_prompt(today)

    try:
        query_data = call_groq(query_prompt, max_tokens=900, temperature=0.45)
        discovery_queries = query_data.get("queries", [])
        if not discovery_queries:
            raise ValueError("No queries returned by model.")
    except Exception as e:
        print(f"  Query generation failed, using fallback queries. Error: {e}")
        discovery_queries = fallback_discovery_queries()

    print("\nDiscovery queries:")
    for q in discovery_queries:
        print(f"  - {q}")

    print("\n[Phase 2] Broad discovery search...")
    landscape_raw = search_batch(discovery_queries, max_results=4, label="Discovery")

    if not landscape_raw.strip():
        raise RuntimeError("No search results returned from Tavily.")

    print("\n[Phase 3] Selecting issue shape and angle from evidence...")
    time.sleep(5)

    selection_prompt = build_issue_selection_prompt(
        today=today,
        landscape_results=landscape_raw[:10000]
    )

    selection = call_groq(selection_prompt, max_tokens=1400, temperature=0.25)

    issue_shape = selection.get("issue_shape", "Research Issue")
    issue_title = selection.get("issue_title", "Paid Social Edge")
    core_angle = selection.get("core_angle", "")
    why_this_issue = selection.get("why_this_issue", "")
    what_not_to_do = selection.get("what_not_to_do", "")
    targeted_queries = selection.get("targeted_search_queries", [])

    if not targeted_queries:
        targeted_queries = discovery_queries[:5]

    print(f"\nSelected issue shape: {issue_shape}")
    print(f"Selected title: {issue_title}")
    print(f"Core angle: {core_angle}")
    print(f"Why this issue: {why_this_issue}")
    print(f"Avoiding: {what_not_to_do}")

    print("\n[Phase 4] Targeted follow-up search...")
    time.sleep(5)
    deep_raw = search_batch(targeted_queries, max_results=4, label="Targeted")

    print("\n[Phase 5] Writing final research issue...")
    time.sleep(8)

    writer_prompt = build_issue_writer_prompt(
        today=today,
        issue_shape=issue_shape,
        issue_title=issue_title,
        core_angle=core_angle,
        why_this_issue=why_this_issue,
        what_not_to_do=what_not_to_do,
        deep_results=deep_raw[:9000],
        landscape_results=landscape_raw[:3500]
    )

    data = call_groq(writer_prompt, max_tokens=2600, temperature=0.25)

    subject = data.get("subject_line") or f"Paid Social Edge: {data.get('title', issue_title)}"
    subject = compact_text(subject, 70)

    html = build_html(data)

    print(f"\nSubject: {subject}")
    print("[Phase 6] Sending email...")
    send_email(html, subject)


if __name__ == "__main__":
    main()
