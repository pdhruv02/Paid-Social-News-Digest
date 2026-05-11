"""
Paid Social Edge — Source-Led Deep Dive Newsletter
Runs on odd ISO weeks, Tuesday 6 AM CST

Core logic:
Phase 1: AI generates broad discovery queries
Phase 2: Tavily searches broadly
Phase 3: AI finds the strongest "golden thread" from the evidence
Phase 4: Tavily does targeted source-deepening research with raw content
Phase 5: AI writes an article-style paid social deep dive
Phase 6: AI refines the draft to remove generic/template writing
Phase 7: Email is sent via Resend

No fixed topic list.
No forced case studies.
No forced "operator lessons / what to test" template.
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

# Set this to true in GitHub Actions env if you want odd-week gating.
RUN_ODD_WEEKS_ONLY = os.environ.get("RUN_ODD_WEEKS_ONLY", "false").lower() == "true"


# ── Week gate ─────────────────────────────────────────────────────────────────

def check_week():
    week = datetime.now(CST).isocalendar()[1]

    # if RUN_ODD_WEEKS_ONLY and week % 2 == 0:
      #  print(f"Week {week} is even — skipping this deep dive run.")
    #    exit(0)

    print(f"Week {week} — running Paid Social Edge deep dive.")


# ── Helpers ───────────────────────────────────────────────────────────────────

def esc(value) -> str:
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
    clean = re.sub(r"```(?:json)?|```", "", raw or "").strip()
    match = re.search(r"\{.*\}", clean, re.DOTALL)

    if not match:
        raise ValueError(f"No JSON object found in model output:\n{raw[:900]}")

    return json.loads(match.group())


def call_groq(prompt: str, max_tokens: int = 2200, temperature: float = 0.25) -> dict:
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

You are creating search queries for a high-quality paid social deep dive newsletter.

Private reader context:
- The reader works in paid social at a large technology company.

Important:
This context is only for relevance filtering.
The newsletter should not sound company-specific.
Do not write queries only about one company.
Do not assume the issue topic before research.

Your job:
Generate diverse discovery queries that can surface rare, specific, non-obvious material.

Avoid generic searches like:
- "AI paid social best practices"
- "paid social trends"
- "how to improve ROI with ads"

Instead, search for materials that are likely to contain, "likely" not necessarily or always, these are just examples:
- Specific campaign mechanics
- Case studies with actual detail
- Research reports with data
- Practitioner teardowns
- Competitor messaging patterns
- Measurement debates
- Creative testing systems
- Platform automation changes with strategic consequences
- Buyer behavior evidence
- In-house media operating lessons

Include some source-specific queries using sources like:
- Effie
- WARC
- IPA
- Stratechery
- Think with Google
- LinkedIn B2B Institute
- Reddit for Business
- Meta for Business
- TikTok Business
- YouTube Works
- IAB
- AdExchanger
- Digiday
- Marketing Brew
- eMarketer
- practitioner teardown sources

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
    "query 10",
    "query 11",
    "query 12"
  ]
}}
"""


def build_story_selection_prompt(today: str, landscape_results: str) -> str:
    return f"""
Today is {today}.

You are the editor of a paid social deep dive newsletter.

Your job is NOT to choose a broad topic.
Your job is to find the strongest "golden thread" from the research results.

A golden thread is a specific, interesting, evidence-backed angle that can become a genuinely useful read.

Raw landscape results:
{landscape_results}

Private reader context:
- The reader works in paid social at a large technology company.
- They care about practical paid social judgment, not generic marketing commentary.

Editorial standard:
The issue should feel like a smart paid social essay or field note, not a template.

Do NOT select an angle like:
- "AI can improve creative testing"
- "Measurement is important"
- "B2B buyers need trust"
- "Creative testing improves performance"
- "Platform automation is changing paid social"

Those are too broad and generic.

A good angle looks more like:
- "The hidden risk in AI creative testing is not volume — it is losing the buyer language that made the ad work."
- "Why lead-gen efficiency can hide quality decay when the conversion signal is too shallow."
- "The interesting thing about competitor AI PC ads is not the product claim, but which user anxiety they choose to reduce."
- "The case study is less useful for its result and more useful for how the campaign connected creative input to downstream signal."

Selection rules:
1. Prefer source material with concrete details, not broad advice.
2. Prefer one strong source plus 2 supporting sources over 8 weak sources.
3. Prefer surprising or under-discussed angles.
4. Reject sources that only say obvious things.
5. If the evidence is weak, say so and choose a narrower issue.
6. Do not force a case study if the case study is thin.
7. Do not make the issue sound like it is teaching any specific company what to do.

Return ONLY valid JSON.

{{
  "should_publish": true,
  "issue_mode": "Deep Read | Case Teardown | Research Breakdown | Competitor Pattern | Measurement Note | Creative Analysis | Buyer Behavior Note | Platform Shift",
  "headline": "Specific headline, not a generic topic",
  "subhead": "One sentence explaining the sharp angle",
  "golden_thread": "The specific insight this issue will explore",
  "why_this_is_interesting": "Why this is not a generic newsletter topic",
  "source_bar": "Strong | Medium | Thin",
  "editorial_warning": "What the writer must avoid so the issue does not become generic",
  "primary_sources_to_use": [
    {{
      "title": "Source title",
      "source": "Source name",
      "url": "URL",
      "date_or_recency": "Date or recency",
      "specific_detail": "The concrete detail that makes this source useful"
    }}
  ],
  "targeted_search_queries": [
    "5 to 8 queries that deepen this exact golden thread, not the broad topic"
  ]
}}
"""


def build_writer_prompt(
    today: str,
    issue_mode: str,
    headline: str,
    subhead: str,
    golden_thread: str,
    why_interesting: str,
    editorial_warning: str,
    deep_results: str,
    landscape_results: str
) -> str:
    return f"""
Today is {today}.

You are writing a high-quality paid social deep dive newsletter.

This should read like a sharp paid social essay, not a template.
It should be specific, interesting, evidence-led, and useful.

Issue mode:
{issue_mode}

Headline:
{headline}

Subhead:
{subhead}

Golden thread:
{golden_thread}

Why this is interesting:
{why_interesting}

Editorial warning:
{editorial_warning}

Targeted research results:
{deep_results}

Earlier landscape results:
{landscape_results}

Private reader context:
- The reader works in paid social at a large technology company.
- They care about campaign decisions, creative testing, measurement quality, buyer behavior, platform automation, competitor patterns, and in-house team capability.
- Relevant categories include enterprise tech, consumer tech, gaming, B2B demand generation, AI PCs, and performance media.

Voice:
- Write like a smart external paid social newsletter.
- Do not sound like a corporate memo.
- Do not teach any specific company what it “must” do.
- Do not overuse company names.
- Be analytical, plainspoken, and precise.
- Make the reader feel like they learned something specific.

Strict anti-generic rules:
Do NOT write lines like:
- "This can improve ROI."
- "This requires a deep understanding of the technology and its limitations."
- "Operators should monitor effectiveness."
- "AI can optimize campaigns."
- "This helps brands reach the right audience."
- "Testing is important."
- "Measurement is critical."
- "Creative is key."

Every paragraph must include at least one of:
- A concrete source detail
- A specific mechanism
- A specific tension or tradeoff
- A named platform behavior
- A real campaign/case detail
- A buyer behavior detail
- A measurement caveat
- A non-obvious implication

Do not summarize sources one by one.
Synthesize them into a narrative.

If a source is promotional, say what can and cannot be learned from it.
If evidence is thin, say so.
Do not overclaim.

Return ONLY valid JSON.

{{
  "subject_line": "Email subject line under 70 characters",
  "eyebrow": "Short label like Creative Analysis, Measurement Note, Case Teardown, etc.",
  "title": "{headline}",
  "subtitle": "{subhead}",
  "publish_quality": "Strong | Medium | Thin",
  "opening_hook": "A strong 2-3 sentence opening. It should create curiosity, not summarize the topic generically.",
  "the_interesting_part": [
    {{
      "section_title": "Specific section title",
      "body": "A detailed paragraph with concrete details and actual insight. No generic filler."
    }},
    {{
      "section_title": "Specific section title",
      "body": "Another detailed paragraph that adds a new idea, not a repeat."
    }},
    {{
      "section_title": "Specific section title",
      "body": "Another detailed paragraph that adds a new idea, not a repeat."
    }}
  ],
  "source_trail": [
    {{
      "title": "Source title",
      "source": "Source name",
      "date_or_recency": "Date or recency",
      "url": "URL",
      "what_is_useful_here": "Specific detail from the source that is actually useful.",
      "how_to_read_it": "How to interpret this source carefully."
    }}
  ],
  "operator_read/summary": [
    "A specific operator-level takeaway. Must be concrete and non-obvious.",
    "A second operator-level takeaway that adds a different idea.",
    "A third operator-level takeaway that adds a different idea."
  ],
  "best_links": [
    {{
      "title": "Title",
      "url": "URL"
    }}
  ]
}}
"""


def build_refinement_prompt(draft_json: dict, deep_results: str) -> str:
    draft_text = json.dumps(draft_json, ensure_ascii=False, indent=2)

    return f"""
You are editing a paid social newsletter draft.

The previous reviewer feedback was:
- The writing felt repetitive.
- It sounded templatey.
- The points were too basic.
- Lines like "requires a deep understanding of the technology and its limitations" say nothing.
- The final output needs actual depth, specific findings, and interesting material.

Your job:
Rewrite the draft JSON below so it becomes more specific, less repetitive, and more interesting.

Draft JSON:
{draft_text}

Research evidence available:
{deep_results}

Editing rules:
1. Remove generic lines.
2. Every section must add a new idea.
3. Do not repeat the main takeaway in different words.
4. Add concrete mechanisms, examples, source details, tensions, or caveats wherever possible.
5. If a point could apply to any paid social topic, rewrite it or remove it.
6. Do not add unsupported claims.
7. Keep the same JSON schema.
8. Keep the tone like a sharp external paid social newsletter.
9. Do not make it sound company-specific.
10. Do not use corporate phrases like "must prioritize," "leverage," "unlock," "drive ROI," or "deep understanding."

Return ONLY valid JSON using the exact same schema as the draft.
"""


# ── Research functions ────────────────────────────────────────────────────────

def search_batch(
    queries: list,
    max_results: int = 5,
    label: str = "",
    include_raw_content: bool = False,
    body_limit: int = 900
) -> str:
    tavily = TavilyClient(api_key=TAVILY_API_KEY)
    seen_urls = set()
    results = []

    for i, q in enumerate(queries, 1):
        q = str(q).strip()
        if not q:
            continue

        tag = f"[{label} {i}/{len(queries)}]" if label else f"[{i}/{len(queries)}]"
        print(f"  {tag} {q[:95]}...")

        try:
            response = tavily.search(
                q,
                search_depth="advanced",
                max_results=max_results,
                include_raw_content=include_raw_content
            )

            for item in response.get("results", []):
                url = item.get("url", "").strip()
                if not url or url in seen_urls:
                    continue

                seen_urls.add(url)

                title = item.get("title", "")
                published_date = item.get("published_date", "unknown")

                raw_content = item.get("raw_content") or ""
                snippet_content = item.get("content") or ""
                content = raw_content if raw_content else snippet_content

                results.append(
                    f"QUERY: {q}\n"
                    f"TITLE: {title}\n"
                    f"URL: {url}\n"
                    f"DATE: {published_date}\n"
                    f"BODY: {compact_text(content, body_limit)}\n"
                    f"---"
                )

            time.sleep(0.4)

        except Exception as e:
            print(f"    Search error: {e}")

    return "\n\n".join(results)


def fallback_discovery_queries() -> list:
    return [
        "paid social case study with results B2B technology",
        "paid social advertising teardown B2B case study",
        "site:thinkwithgoogle.com advertising effectiveness case study paid social technology",
        "site:effie.org technology advertising case study effectiveness digital media",
        "site:warc.com paid social effectiveness case study technology marketing",
        "site:business.reddit.com success stories technology B2B paid media",
        "AI creative testing advertising case study CRM buyer language",
        "paid social incrementality attribution geo lift case study",
        "HP Lenovo Apple Microsoft AI PC advertising campaign messaging analysis",
        "B2B buyer behavior enterprise technology digital advertising research",
        "in-house media buying paid social operating model case study"
    ]


# ── HTML rendering ────────────────────────────────────────────────────────────

def paragraph(text: str, color: str = "#374151", size: str = "14px") -> str:
    return f"""
<p style="margin:0 0 13px;font-size:{size};line-height:1.75;color:{color};">
  {esc(text)}
</p>
"""


def section(label: str, content: str, bg: str = "#FFFFFF") -> str:
    return f"""
<tr>
  <td style="background:{bg};padding:24px 28px;border-bottom:1px solid #F3F4F6;">
    <p style="margin:0 0 13px;font-size:10.5px;font-weight:800;color:#9CA3AF;
              text-transform:uppercase;letter-spacing:1px;">{esc(label)}</p>
    {content}
  </td>
</tr>
"""


def bullet_list(items: list, color: str = "#374151") -> str:
    items = [i for i in safe_list(items) if str(i).strip()]
    if not items:
        return '<p style="margin:0;font-size:13px;color:#9CA3AF;">No items included.</p>'

    return (
        "<ul style='margin:0;padding-left:19px;'>"
        + "".join(
            f'<li style="margin-bottom:9px;font-size:13.5px;color:{color};line-height:1.7;">{esc(i)}</li>'
            for i in items
        )
        + "</ul>"
    )


def interesting_sections_html(items: list) -> str:
    items = [i for i in safe_list(items) if isinstance(i, dict)]
    if not items:
        return '<p style="margin:0;font-size:13px;color:#9CA3AF;">No sections included.</p>'

    html = ""

    for item in items:
        title = item.get("section_title", "")
        body = item.get("body", "")

        html += f"""
<div style="margin-bottom:20px;">
  <h3 style="margin:0 0 8px;font-size:16px;line-height:1.35;color:#111827;">
    {esc(title)}
  </h3>
  {paragraph(body)}
</div>
"""

    return html


def source_trail_html(items: list) -> str:
    items = [i for i in safe_list(items) if isinstance(i, dict)]
    if not items:
        return '<p style="margin:0;font-size:13px;color:#9CA3AF;">No source trail included.</p>'

    html = ""

    for item in items:
        title = item.get("title", "")
        source = item.get("source", "")
        date = item.get("date_or_recency", "")
        url = clean_url(item.get("url", "#"))
        useful = item.get("what_is_useful_here", "")
        how = item.get("how_to_read_it", "")

        html += f"""
<div style="padding:15px 0;border-bottom:1px solid #E5E7EB;">
  <p style="margin:0 0 5px;font-size:12px;color:#6B7280;">
    <strong>{esc(source)}</strong>{' · ' if source and date else ''}{esc(date)}
  </p>

  <p style="margin:0 0 7px;font-size:14px;line-height:1.55;color:#111827;font-weight:700;">
    <a href="{esc(url)}" style="color:#111827;text-decoration:none;">{esc(title)}</a>
  </p>

  <p style="margin:0 0 7px;font-size:13.5px;line-height:1.65;color:#374151;">
    <strong>Useful detail:</strong> {esc(useful)}
  </p>

  <p style="margin:0 0 8px;font-size:13px;line-height:1.65;color:#6B7280;">
    <strong>How to read it:</strong> {esc(how)}
  </p>

  <p style="margin:0;font-size:12.5px;">
    <a href="{esc(url)}" style="color:#2563EB;text-decoration:none;">Read source →</a>
  </p>
</div>
"""

    return html


def links_html(items: list) -> str:
    items = [i for i in safe_list(items) if isinstance(i, dict) and i.get("url")]

    if not items:
        return '<p style="margin:0;font-size:13px;color:#9CA3AF;">No links included.</p>'

    return (
        "<ul style='margin:0;padding-left:18px;'>"
        + "".join(
            f'<li style="margin-bottom:8px;font-size:13px;line-height:1.6;">'
            f'<a href="{esc(clean_url(i.get("url")))}" style="color:#2563EB;text-decoration:none;">'
            f'{esc(i.get("title", i.get("url")))}</a></li>'
            for i in items
        )
        + "</ul>"
    )


def read_this_first_html(item: dict) -> str:
    if not isinstance(item, dict) or not item.get("url"):
        return '<p style="margin:0;font-size:13px;color:#9CA3AF;">No single best link selected.</p>'

    return f"""
<p style="margin:0 0 8px;font-size:14px;font-weight:700;line-height:1.5;color:#111827;">
  <a href="{esc(clean_url(item.get("url")))}" style="color:#111827;text-decoration:none;">
    {esc(item.get("title", "Read this source"))}
  </a>
</p>
<p style="margin:0;font-size:13.5px;line-height:1.7;color:#374151;">
  {esc(item.get("why", ""))}
</p>
"""


def build_html(data: dict) -> str:
    now = datetime.now(CST)
    date_str = now.strftime("%B %d, %Y")
    week_num = now.isocalendar()[1]

    eyebrow = data.get("eyebrow", "Deep Read")
    title = data.get("title", "Paid Social Edge")
    subtitle = data.get("subtitle", "")
    publish_quality = data.get("publish_quality", "")
    opening_hook = data.get("opening_hook", "")

    interesting_part = data.get("the_interesting_part", [])
    source_trail = data.get("source_trail", [])
    operator_read = data.get("operator_read", [])
    questions = data.get("questions_worth_asking", [])
    caveats = data.get("what_not_to_overclaim", [])
    read_first = data.get("read_this_first", {})
    best_links = data.get("best_links", [])

    opening_html = paragraph(opening_hook, "#374151", "14.5px")

    quality_note = ""
    if publish_quality:
        quality_note = f"""
<p style="margin:10px 0 0;font-size:11px;color:#A7F3D0;letter-spacing:.4px;text-transform:uppercase;font-weight:700;">
  Source bar: {esc(publish_quality)}
</p>
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
      <table width="660" cellpadding="0" cellspacing="0" style="max-width:660px;width:100%;">

        <tr>
          <td style="background:#111827;border-radius:14px 14px 0 0;padding:34px 38px 30px;" bgcolor="#111827">
            <p style="margin:0 0 8px;font-size:10px;font-weight:800;letter-spacing:2.3px;color:#93C5FD;text-transform:uppercase;">
              Paid Social Edge · Week {week_num} · {esc(date_str)}
            </p>

            <p style="margin:0 0 10px;font-size:11px;font-weight:800;color:#6EE7B7;text-transform:uppercase;letter-spacing:1px;">
              {esc(eyebrow)}
            </p>

            <h1 style="margin:0 0 14px;font-size:25px;line-height:1.24;font-weight:850;color:#FFFFFF;">
              {esc(title)}
            </h1>

            <p style="margin:0;font-size:14.5px;line-height:1.65;color:#D1D5DB;">
              {esc(subtitle)}
            </p>

            {quality_note}
          </td>
        </tr>

        <tr>
          <td style="background:#2563EB;height:4px;"></td>
        </tr>

        {section("Opening", opening_html)}
        {section("The interesting part", interesting_sections_html(interesting_part), "#FAFAFA")}
        {section("Source trail", source_trail_html(source_trail))}
        {section("Operator read", bullet_list(operator_read), "#F9FAFB")}
        {section("Questions worth asking", bullet_list(questions, "#1E3A8A"), "#EFF6FF")}
        {section("What not to overclaim", bullet_list(caveats, "#991B1B"), "#FEF2F2")}
        {section("Read this first", read_this_first_html(read_first), "#ECFDF5")}
        {section("Best links", links_html(best_links))}

        <tr>
          <td style="background:#111827;border-radius:0 0 14px 14px;padding:18px 36px;text-align:center;" bgcolor="#111827">
            <p style="margin:0;font-size:12px;color:#9CA3AF;">
              Paid Social Edge · Source-led research for paid social operators
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

    print("\n[Phase 1] Generating discovery queries...")
    query_prompt = build_discovery_query_prompt(today)

    try:
        query_data = call_groq(query_prompt, max_tokens=1100, temperature=0.55)
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
    landscape_raw = search_batch(
        discovery_queries,
        max_results=4,
        label="Discovery",
        include_raw_content=False,
        body_limit=850
    )

    if not landscape_raw.strip():
        raise RuntimeError("No search results returned from Tavily.")

    print("\n[Phase 3] Selecting golden thread from evidence...")
    time.sleep(5)

    selection_prompt = build_story_selection_prompt(
        today=today,
        landscape_results=landscape_raw[:12000]
    )

    selection = call_groq(selection_prompt, max_tokens=1700, temperature=0.25)

    issue_mode = selection.get("issue_mode", "Deep Read")
    headline = selection.get("headline", "Paid Social Edge")
    subhead = selection.get("subhead", "")
    golden_thread = selection.get("golden_thread", "")
    why_interesting = selection.get("why_this_is_interesting", "")
    editorial_warning = selection.get("editorial_warning", "")
    targeted_queries = selection.get("targeted_search_queries", [])

    if not targeted_queries:
        targeted_queries = discovery_queries[:6]

    print(f"\nIssue mode: {issue_mode}")
    print(f"Headline: {headline}")
    print(f"Golden thread: {golden_thread}")
    print(f"Source bar: {selection.get('source_bar', 'unknown')}")
    print(f"Editorial warning: {editorial_warning}")

    print("\n[Phase 4] Targeted deep search with raw content...")
    time.sleep(5)

    deep_raw = search_batch(
        targeted_queries,
        max_results=5,
        label="Deep",
        include_raw_content=True,
        body_limit=2400
    )

    if not deep_raw.strip():
        print("No targeted results returned. Falling back to landscape material.")
        deep_raw = landscape_raw

    print("\n[Phase 5] Writing article-style deep dive...")
    time.sleep(8)

    writer_prompt = build_writer_prompt(
        today=today,
        issue_mode=issue_mode,
        headline=headline,
        subhead=subhead,
        golden_thread=golden_thread,
        why_interesting=why_interesting,
        editorial_warning=editorial_warning,
        deep_results=deep_raw[:16000],
        landscape_results=landscape_raw[:5000]
    )

    draft = call_groq(writer_prompt, max_tokens=3600, temperature=0.28)

    print("\n[Phase 6] Refining to remove generic/template writing...")
    time.sleep(5)

    refinement_prompt = build_refinement_prompt(
        draft_json=draft,
        deep_results=deep_raw[:14000]
    )

    data = call_groq(refinement_prompt, max_tokens=3600, temperature=0.22)

    subject = data.get("subject_line") or f"Paid Social Edge: {data.get('title', headline)}"
    subject = compact_text(subject, 70)

    html = build_html(data)

    print(f"\nSubject: {subject}")
    print("[Phase 7] Sending email...")
    send_email(html, subject)


if __name__ == "__main__":
    main()
