"""
Paid Social Edge — Article-Led Deep Dive Newsletter
Runs on odd ISO weeks, Tuesday 6 AM CST

Core logic:
Phase 1: AI generates broad discovery queries
Phase 2: Tavily searches broadly
Phase 3: AI finds one strong editorial angle / golden thread
Phase 4: Tavily does targeted deep research with raw content
Phase 5: AI writes one article-style newsletter
Phase 6: AI edits the article to remove generic/template writing
Phase 7: Email is sent via Resend

Design principle:
No fixed newsletter sections except:
1. Header
2. Article body
3. Sources

No forced “operator lessons.”
No forced “what to test.”
No forced “practical implication.”
No forced “what not to overlearn.”
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

# Set RUN_ODD_WEEKS_ONLY=true in GitHub Actions if you want odd-week gating.
RUN_ODD_WEEKS_ONLY = os.environ.get("RUN_ODD_WEEKS_ONLY", "false").lower() == "true"


# ── Week gate ─────────────────────────────────────────────────────────────────

def check_week():
    week = datetime.now(CST).isocalendar()[1]

    # if RUN_ODD_WEEKS_ONLY and week % 2 == 0:
     #   print(f"Week {week} is even — skipping this deep dive run.")
     #   exit(0)

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


def call_groq(prompt: str, max_tokens: int = 2400, temperature: float = 0.25) -> dict:
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

You are generating discovery search queries for a high-quality paid social deep dive newsletter.

Private reader context:
- The reader works in paid social at a large technology company.
- They care about strategy, creative testing, measurement, attribution, platform automation, B2B buyer behavior, competitor messaging, AI workflows, and in-house media operations.
- Relevant areas include enterprise tech, consumer tech, gaming, AI PCs, B2B demand generation, and performance media.

This context is only for relevance filtering.
The newsletter should NOT sound company-specific.

Goal:
Find rare, useful, specific source material that could become an interesting paid social article.

Avoid generic searches like:
- paid social trends
- AI marketing best practices
- how to improve ROI with ads

Search for material likely to contain:
- specific campaign mechanics
- detailed case studies
- advertising effectiveness examples
- creative testing systems
- measurement caveats
- buyer behavior research
- competitor messaging patterns
- practitioner teardowns
- platform automation shifts
- in-house media operating lessons

Include a mix of:
- broad discovery queries
- source-specific queries
- case-study queries
- research/report queries
- competitor/message queries
- measurement/creative queries

Useful sources may include:
Effie, WARC, IPA, Think with Google, LinkedIn B2B Institute, Reddit for Business, Meta for Business, TikTok Business, YouTube Works, IAB, AdExchanger, Digiday, Marketing Brew, eMarketer, and credible practitioner teardown sources.

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
Your job is to find one strong editorial angle from the research results.

A good issue should feel like:
- a sharp paid social essay
- a field note from useful research
- a source-led analysis
- a thoughtful teardown
- a specific idea worth reading

A bad issue feels like:
- a template
- generic best practices
- a broad trend summary
- “AI improves ROI”
- “creative testing matters”
- “measurement is important”
- “B2B buyers need trust”

Raw discovery results:
{landscape_results}

Private reader context:
- The reader works in paid social at a large technology company.
- They care about practical paid social judgment, not generic marketing commentary.
- Relevant areas include B2B, consumer tech, gaming, AI PCs, creative testing, measurement, platform automation, buyer behavior, competitor messaging, and in-house media operations.

Editorial standard:
Choose an angle only if the source material gives you something specific to say.

A strong angle might come from:
- one unusually detailed case study
- a tension across multiple sources
- a competitor messaging pattern
- a measurement caveat that operators miss
- a platform change with second-order consequences
- a buyer behavior finding with practical implications
- a creative testing system with actual mechanics
- a campaign detail that reveals a bigger lesson

Do NOT force a case study.
Do NOT force a platform update.
Do NOT force a brand/company-specific angle.
Do NOT write about the broadest topic just because it has the most sources.

Return ONLY valid JSON.

{{
  "should_publish": true,
  "headline": "Specific headline, not a generic topic",
  "subhead": "One sentence explaining the sharp angle",
  "golden_thread": "The specific insight this issue will explore",
  "why_this_is_interesting": "Why this is worth reading and not generic",
  "source_bar": "Strong | Medium | Thin",
  "editorial_warning": "What the writer must avoid so the issue does not become generic",
  "best_seed_sources": [
    {{
      "title": "Source title",
      "source": "Source name",
      "url": "URL",
      "date_or_recency": "Date or recency",
      "specific_detail": "The concrete detail that makes this source useful"
    }}
  ],
  "targeted_search_queries": [
    "5 to 8 queries that deepen this exact angle, not the broad topic"
  ]
}}
"""


def build_writer_prompt(
    today: str,
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

This should read like one sharp article, not a template.

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
- Relevant areas include enterprise tech, consumer tech, gaming, B2B demand generation, AI PCs, and performance media.

Voice:
- Write like a smart external paid social newsletter.
- Plainspoken, analytical, specific.
- Not a corporate memo.
- Not a strategy recommendation to any specific company.
- Not a list of generic best practices.
- Make the reader feel like they found something worth thinking about.

Strict anti-generic rules:
Do NOT write lines like:
- "This can improve ROI."
- "This requires a deep understanding of the technology and its limitations."
- "AI can optimize campaigns."
- "Testing is important."
- "Measurement is critical."
- "Creative is key."
- "Operators should monitor performance."
- "Brands need to understand their audience."

Every article block must contain at least one of:
- a concrete source detail
- a specific mechanism
- a specific tension or tradeoff
- a named platform behavior
- a real campaign/case detail
- a buyer behavior detail
- a measurement caveat
- a non-obvious implication

Structure:
- Write 4 to 6 article blocks.
- Choose the headings naturally based on the story.
- Do NOT use recurring generic headings like “Operator Lessons,” “Practical Implication,” “What to Test,” or “Key Takeaways.”
- Each block must add a new idea.
- If the evidence is thin, write fewer blocks and be honest.
- Do not summarize sources one by one unless the article needs it.
- Synthesize the sources into one coherent read.

Return ONLY valid JSON.

{{
  "subject_line": "Email subject line under 70 characters",
  "eyebrow": "Short label, e.g. Creative Analysis, Measurement Note, Case Teardown, Platform Shift",
  "title": "{headline}",
  "subtitle": "{subhead}",
  "source_bar": "Strong | Medium | Thin",
  "article_blocks": [
    {{
      "heading": "Specific heading written for this article",
      "body": "Detailed paragraph with concrete detail and actual insight. No generic filler."
    }},
    {{
      "heading": "Specific heading written for this article",
      "body": "Detailed paragraph that adds a new idea, not a repeat."
    }},
    {{
      "heading": "Specific heading written for this article",
      "body": "Detailed paragraph that adds a new idea, not a repeat."
    }},
    {{
      "heading": "Specific heading written for this article",
      "body": "Detailed paragraph that adds a new idea, not a repeat."
    }}
  ],
  "sources": [
    {{
      "title": "Source title",
      "source": "Source name",
      "date_or_recency": "Date or recency",
      "url": "URL",
      "why_it_was_used": "Specific reason this source mattered to the article."
    }}
  ]
}}
"""


def build_refinement_prompt(draft_json: dict, deep_results: str) -> str:
    draft_text = json.dumps(draft_json, ensure_ascii=False, indent=2)

    return f"""
You are editing a paid social newsletter draft.

Previous reviewer feedback:
- The writing felt repetitive.
- It sounded templatey.
- The points were too basic.
- The sections repeated the same idea in different words.
- Generic lines like "requires a deep understanding" say nothing.
- The final output needs depth, specificity, and actually interesting material.

Rewrite the draft JSON below.

Draft JSON:
{draft_text}

Research evidence available:
{deep_results}

Editing rules:
1. Keep the same JSON schema.
2. Remove generic lines.
3. Every article block must add a new idea.
4. Do not repeat the main idea in different words.
5. Add concrete mechanisms, source details, examples, tensions, or caveats wherever possible.
6. If a sentence could apply to almost any marketing topic, delete or rewrite it.
7. Do not add unsupported claims.
8. Do not make it company-specific.
9. Do not use corporate phrases like "must prioritize," "leverage," "unlock," "drive ROI," or "deep understanding."
10. Keep the article readable and not too long.

Return ONLY valid JSON using the exact same schema.
"""


# ── Research functions ────────────────────────────────────────────────────────

def search_batch(
    queries: list,
    max_results: int = 5,
    label: str = "",
    include_raw_content: bool = False,
    body_limit: int = 1200
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
        "paid social case study with results creative testing B2B technology",
        "paid social advertising teardown B2B creative measurement case study",
        "site:thinkwithgoogle.com advertising effectiveness case study paid social technology",
        "site:business.linkedin.com B2B Institute paid social creative measurement research",
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
<p style="margin:0 0 14px;font-size:{size};line-height:1.75;color:{color};">
  {esc(text)}
</p>
"""


def article_blocks_html(blocks: list) -> str:
    blocks = [b for b in safe_list(blocks) if isinstance(b, dict)]

    if not blocks:
        return '<p style="margin:0;font-size:13px;color:#9CA3AF;">No article body returned.</p>'

    html = ""

    for block in blocks:
        heading = block.get("heading", "")
        body = block.get("body", "")

        html += f"""
<div style="margin-bottom:24px;">
  <h2 style="margin:0 0 9px;font-size:17px;line-height:1.35;color:#111827;">
    {esc(heading)}
  </h2>
  {paragraph(body, "#374151", "14px")}
</div>
"""

    return html


def sources_html(sources: list) -> str:
    sources = [s for s in safe_list(sources) if isinstance(s, dict)]

    if not sources:
        return '<p style="margin:0;font-size:13px;color:#9CA3AF;">No sources returned.</p>'

    html = ""

    for src in sources:
        title = src.get("title", "")
        source = src.get("source", "")
        date = src.get("date_or_recency", "")
        url = clean_url(src.get("url", "#"))
        why = src.get("why_it_was_used", "")

        html += f"""
<div style="padding:14px 0;border-bottom:1px solid #E5E7EB;">
  <p style="margin:0 0 5px;font-size:12px;color:#6B7280;">
    <strong>{esc(source)}</strong>{' · ' if source and date else ''}{esc(date)}
  </p>

  <p style="margin:0 0 7px;font-size:14px;line-height:1.55;color:#111827;font-weight:700;">
    <a href="{esc(url)}" style="color:#111827;text-decoration:none;">{esc(title)}</a>
  </p>

  <p style="margin:0 0 8px;font-size:13px;line-height:1.65;color:#4B5563;">
    {esc(why)}
  </p>

  <p style="margin:0;font-size:12.5px;">
    <a href="{esc(url)}" style="color:#2563EB;text-decoration:none;">Read source →</a>
  </p>
</div>
"""

    return html


def build_html(data: dict) -> str:
    now = datetime.now(CST)
    date_str = now.strftime("%B %d, %Y")
    week_num = now.isocalendar()[1]

    eyebrow = data.get("eyebrow", "Deep Read")
    title = data.get("title", "Paid Social Edge")
    subtitle = data.get("subtitle", "")
    source_bar = data.get("source_bar", "")
    article_blocks = data.get("article_blocks", [])
    sources = data.get("sources", [])

    source_bar_html = ""
    if source_bar:
        source_bar_html = f"""
<p style="margin:11px 0 0;font-size:11px;color:#A7F3D0;letter-spacing:.4px;text-transform:uppercase;font-weight:700;">
  Source bar: {esc(source_bar)}
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

            {source_bar_html}
          </td>
        </tr>

        <tr>
          <td style="background:#2563EB;height:4px;"></td>
        </tr>

        <tr>
          <td style="background:#FFFFFF;padding:30px 34px 10px;border-bottom:1px solid #F3F4F6;">
            {article_blocks_html(article_blocks)}
          </td>
        </tr>

        <tr>
          <td style="background:#F9FAFB;padding:24px 34px 28px;border-bottom:1px solid #F3F4F6;">
            <p style="margin:0 0 13px;font-size:10.5px;font-weight:800;color:#9CA3AF;
                      text-transform:uppercase;letter-spacing:1px;">Sources</p>
            {sources_html(sources)}
          </td>
        </tr>

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
        body_limit=900
    )

    if not landscape_raw.strip():
        raise RuntimeError("No search results returned from Tavily.")

    print("\n[Phase 3] Selecting golden thread...")
    time.sleep(5)

    selection_prompt = build_story_selection_prompt(
        today=today,
        landscape_results=landscape_raw[:12000]
    )

    selection = call_groq(selection_prompt, max_tokens=1700, temperature=0.25)

    headline = selection.get("headline", "Paid Social Edge")
    subhead = selection.get("subhead", "")
    golden_thread = selection.get("golden_thread", "")
    why_interesting = selection.get("why_this_is_interesting", "")
    editorial_warning = selection.get("editorial_warning", "")
    targeted_queries = selection.get("targeted_search_queries", [])

    if not targeted_queries:
        targeted_queries = discovery_queries[:6]

    print(f"\nHeadline: {headline}")
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
        body_limit=2600
    )

    if not deep_raw.strip():
        print("No targeted results returned. Falling back to landscape material.")
        deep_raw = landscape_raw

    print("\n[Phase 5] Writing article-led deep dive...")
    time.sleep(8)

    writer_prompt = build_writer_prompt(
        today=today,
        headline=headline,
        subhead=subhead,
        golden_thread=golden_thread,
        why_interesting=why_interesting,
        editorial_warning=editorial_warning,
        deep_results=deep_raw[:17000],
        landscape_results=landscape_raw[:5000]
    )

    draft = call_groq(writer_prompt, max_tokens=3600, temperature=0.28)

    print("\n[Phase 6] Refining article...")
    time.sleep(5)

    refinement_prompt = build_refinement_prompt(
        draft_json=draft,
        deep_results=deep_raw[:15000]
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
