"""
Paid Social Edge — Open-Ended Curator Newsletter

Core idea:
Find one genuinely interesting thing from advertising / paid social / brand stories /
creative effectiveness / buyer behavior / measurement / platform shifts / campaign history,
then write one short article about it.

Output format:
1. Title
2. Subtitle
3. Article body
4. Main source link

No fixed newsletter sections.
No forced lessons.
No forced "what to test."
No forced Dell/company-specific recommendations.
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

# Set RUN_ODD_WEEKS_ONLY=true in GitHub Actions if this deep-dive runs only on odd weeks.
# RUN_ODD_WEEKS_ONLY = os.environ.get("RUN_ODD_WEEKS_ONLY", "false").lower() == "true"


# ── Week gate ─────────────────────────────────────────────────────────────────

def check_week():
    week = datetime.now(CST).isocalendar()[1]

   # if RUN_ODD_WEEKS_ONLY and week % 2 == 0:
      #  print(f"Week {week} is even — skipping this deep-dive run.")
      #  exit(0)

    print(f"Week {week} — running Paid Social Edge curator issue.")


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


def extract_json(raw: str) -> dict:
    clean = re.sub(r"```(?:json)?|```", "", raw or "").strip()
    match = re.search(r"\{.*\}", clean, re.DOTALL)

    if not match:
        raise ValueError(f"No JSON object found in model output:\n{raw[:900]}")

    return json.loads(match.group())


def call_groq(prompt: str, max_tokens: int = 2200, temperature: float = 0.35) -> dict:
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

def build_scout_query_prompt(today: str) -> str:
    return f"""
Today is {today}.

You are creating search queries for an open-ended advertising and paid social curator newsletter.

The goal is NOT to cover a predefined topic.
The goal is to discover one genuinely interesting thing worth writing about.

The reader works in paid social at a large technology company, but the newsletter should NOT sound company-specific.
Use that context only to judge relevance.

Look broadly across:
- great advertising stories
- real company and brand stories
- detailed campaign case studies
- famous ads from history
- modern ad experiments
- paid social strategy
- creative effectiveness
- marketing science
- measurement and attribution
- platform changes
- AI and automation in advertising
- buyer behavior
- competitor messaging
- B2B and consumer tech campaigns
- unusual examples from adjacent industries
- practitioner teardowns
- research reports

A good query should help uncover something with:
- a real story
- a surprising detail
- a specific mechanism
- a useful tension
- a mistake operators can learn from
- a campaign mechanic worth studying
- a buyer behavior insight
- a measurement caveat
- a creative strategy lesson
- a source worth reading

Avoid generic searches like:
- paid social trends
- AI marketing best practices
- how to improve ROI with ads
- social media marketing tips

Prioritize credible sources when useful:
Effie, WARC, IPA, Think with Google, YouTube Works, LinkedIn B2B Institute,
Reddit for Business, Meta for Business, TikTok Business, IAB, AdExchanger,
Digiday, Marketing Brew, eMarketer, The Information, Harvard Business Review,
Stratechery, Lenny's Newsletter, Exit Five, Marketing Examples, Ads of the World,
Contagious, Campaign, The Drum, and strong practitioner teardowns.

Also consider public ad libraries, campaign pages, brand pages, landing pages, YouTube channels, and competitor examples.

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


def build_find_selection_prompt(today: str, scout_results: str) -> str:
    return f"""
Today is {today}.

You are the curator of a high-quality advertising and paid social newsletter.

Your job:
From the research results below, find ONE genuinely interesting thing worth writing about.

Do not choose a broad topic.
Do not choose something because it is trendy.
Do not choose something because it has many sources.
Choose one specific story, source, finding, campaign, case, platform shift, creative idea, measurement issue, or business detail that is actually worth reading.

The newsletter should feel like:
"I found this one interesting thing. Here's the story, why it matters, and what it quietly teaches about advertising or paid social."

Raw research results:
{scout_results}

The find can be about:
- a brand's real story
- an epic ad or campaign from history
- a modern campaign with interesting mechanics
- a case study with actual detail
- a paid social experiment
- a creative testing idea
- a platform change with second-order effects
- a measurement mistake or caveat
- a buyer behavior insight
- a competitor messaging pattern
- a practitioner teardown
- a research report with a surprising finding
- something outside paid social that still teaches paid social thinking

Avoid:
- generic best practices
- surface-level platform case studies
- "AI improves ROI" type angles
- generic trend summaries
- broad topics with no story
- anything that sounds like filler

Selection standard:
A strong find should have at least one concrete detail that makes it worth writing about.

Return ONLY valid JSON.

{{
  "should_publish": true,
  "find_title": "A short description of the chosen find",
  "article_angle": "The specific angle the article should explore",
  "why_this_is_worth_reading": "Why this is interesting and not generic",
  "main_source_title": "Best main source title",
  "main_source_url": "Best main source URL",
  "main_source_type": "Case study | Article | Research report | Campaign page | Teardown | Platform source | Other",
  "source_strength": "Strong | Medium | Thin",
  "what_to_avoid": "What would make the article boring or generic",
  "followup_queries": [
    "5 to 8 search queries to deepen this exact find, not the broad category"
  ]
}}
"""


def build_article_prompt(
    today: str,
    find_title: str,
    article_angle: str,
    why_worth_reading: str,
    main_source_title: str,
    main_source_url: str,
    source_strength: str,
    what_to_avoid: str,
    deep_results: str,
    scout_results: str
) -> str:
    return f"""
Today is {today}.

You are writing one article-style email for a high-quality advertising and paid social newsletter.

This should NOT feel like a template.
There should be no fixed sections like "operator lessons," "what to test," "practical implications," or "key takeaways."

The chosen find:
{find_title}

Article angle:
{article_angle}

Why this is worth reading:
{why_worth_reading}

Main source:
{main_source_title}
{main_source_url}

Source strength:
{source_strength}

What to avoid:
{what_to_avoid}

Deep research results:
{deep_results}

Earlier scout results:
{scout_results}

Private reader context:
- The reader works in paid social at a large technology company.
- They care about advertising, paid social, creative, measurement, buyer behavior, platform shifts, competitor messaging, and useful marketing stories.
- Do not make the article company-specific.
- Do not teach any specific company what it should do.

Write like:
"I found this interesting thing. Here's the story, why it is interesting, and what it quietly teaches about advertising or paid social."

Tone:
- smart
- plainspoken
- specific
- curious
- not corporate
- not generic
- not over-explained
- not buzzwordy

Hard rules:
- Do not write generic lines like "this improves ROI," "testing is important," "brands need to understand audiences," or "measurement is critical."
- Do not write repeated takeaways in different words.
- Do not force advice.
- Do not include bullet points unless the article genuinely needs them.
- The body should be 600 to 950 words.
- Use paragraphs.
- Include concrete details from sources.
- If the evidence is thin, be honest and write a shorter article.
- Do not invent facts.
- If the main source is promotional, say how to read it carefully.
- End naturally. Do not add a forced conclusion section.

Return ONLY valid JSON.

{{
  "subject_line": "Email subject line under 70 characters",
  "title": "Article title",
  "subtitle": "One-sentence subtitle",
  "body": "Full article body with paragraphs separated by blank lines. No markdown headings unless truly needed.",
  "main_source_title": "{main_source_title}",
  "main_source_url": "{main_source_url}",
  "source_note": "One sentence on why this source is worth reading or how to read it carefully."
}}
"""


def build_refinement_prompt(draft_json: dict, deep_results: str) -> str:
    draft_text = json.dumps(draft_json, ensure_ascii=False, indent=2)

    return f"""
You are editing a newsletter article draft.

Reviewer feedback to solve:
- The writing should not be repetitive.
- It should not feel templatey.
- It should not sound like generic paid social advice.
- It should have depth and specific details.
- It should feel like one interesting article, not a set of boxes.

Draft JSON:
{draft_text}

Evidence available:
{deep_results}

Edit the draft.

Rules:
1. Keep the exact same JSON schema.
2. Remove generic lines.
3. Make the article more specific and interesting.
4. Every paragraph should add something new.
5. Use concrete details from the evidence where possible.
6. Do not add unsupported facts.
7. Do not use corporate phrases like "leverage," "unlock," "drive ROI," "must prioritize," or "deep understanding."
8. Do not make it company-specific.
9. Keep body between 600 and 950 words unless the evidence is thin.
10. Keep the tone natural and readable.

Return ONLY valid JSON.
"""


# ── Search functions ──────────────────────────────────────────────────────────

def search_batch(
    queries: list,
    max_results: int = 5,
    label: str = "",
    include_raw_content: bool = False,
    body_limit: int = 1400
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


def fallback_scout_queries() -> list:
    return [
        "great advertising campaign case study specific strategy lesson",
        "advertising effectiveness case study surprising insight paid social",
        "brand campaign teardown creative strategy lesson",
        "paid social case study detailed mechanics creative measurement",
        "marketing science advertising effectiveness case study creative",
        "famous ad campaign history why it worked case study",
        "B2B advertising case study buyer behavior campaign mechanics",
        "technology brand advertising campaign case study AI PC laptop enterprise",
        "paid social measurement attribution mistake case study",
        "platform advertising automation second order effects paid social",
        "practitioner teardown paid social creative testing campaign",
        "competitor messaging pattern technology advertising campaign analysis"
    ]


# ── HTML rendering ────────────────────────────────────────────────────────────

def paragraphs_to_html(body: str) -> str:
    if not body:
        return '<p style="margin:0;font-size:14px;color:#9CA3AF;">No article body returned.</p>'

    parts = re.split(r"\n\s*\n", body.strip())
    html_parts = []

    for part in parts:
        clean = part.strip()
        if not clean:
            continue

        html_parts.append(
            f"""
<p style="margin:0 0 17px;font-size:14.5px;line-height:1.78;color:#374151;">
  {esc(clean)}
</p>
"""
        )

    return "\n".join(html_parts)


def build_html(data: dict) -> str:
    now = datetime.now(CST)
    date_str = now.strftime("%B %d, %Y")
    week_num = now.isocalendar()[1]

    title = data.get("title", "Paid Social Edge")
    subtitle = data.get("subtitle", "")
    body = data.get("body", "")
    main_source_title = data.get("main_source_title", "")
    main_source_url = clean_url(data.get("main_source_url", "#"))
    source_note = data.get("source_note", "")

    article_html = paragraphs_to_html(body)

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
              One Interesting Thing
            </p>

            <h1 style="margin:0 0 14px;font-size:25px;line-height:1.24;font-weight:850;color:#FFFFFF;">
              {esc(title)}
            </h1>

            <p style="margin:0;font-size:14.5px;line-height:1.65;color:#D1D5DB;">
              {esc(subtitle)}
            </p>
          </td>
        </tr>

        <tr>
          <td style="background:#2563EB;height:4px;"></td>
        </tr>

        <tr>
          <td style="background:#FFFFFF;padding:32px 36px 22px;border-bottom:1px solid #F3F4F6;">
            {article_html}
          </td>
        </tr>

        <tr>
          <td style="background:#F9FAFB;padding:24px 36px 28px;border-bottom:1px solid #F3F4F6;">
            <p style="margin:0 0 10px;font-size:10.5px;font-weight:800;color:#9CA3AF;
                      text-transform:uppercase;letter-spacing:1px;">Main source</p>

            <p style="margin:0 0 8px;font-size:14.5px;line-height:1.55;color:#111827;font-weight:700;">
              <a href="{esc(main_source_url)}" style="color:#111827;text-decoration:none;">{esc(main_source_title)}</a>
            </p>

            <p style="margin:0 0 10px;font-size:13.5px;line-height:1.65;color:#4B5563;">
              {esc(source_note)}
            </p>

            <p style="margin:0;font-size:12.5px;">
              <a href="{esc(main_source_url)}" style="color:#2563EB;text-decoration:none;">Read source →</a>
            </p>
          </td>
        </tr>

        <tr>
          <td style="background:#111827;border-radius:0 0 14px 14px;padding:18px 36px;text-align:center;" bgcolor="#111827">
            <p style="margin:0;font-size:12px;color:#9CA3AF;">
              Paid Social Edge · One useful advertising idea at a time
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

    print("\n[Phase 1] Generating scout queries...")
    scout_prompt = build_scout_query_prompt(today)

    try:
        scout_data = call_groq(scout_prompt, max_tokens=1100, temperature=0.65)
        scout_queries = scout_data.get("queries", [])

        if not scout_queries:
            raise ValueError("No queries returned by model.")

    except Exception as e:
        print(f"  Query generation failed, using fallback queries. Error: {e}")
        scout_queries = fallback_scout_queries()

    print("\nScout queries:")
    for q in scout_queries:
        print(f"  - {q}")

    print("\n[Phase 2] Broad scouting search...")
    scout_results = search_batch(
        scout_queries,
        max_results=4,
        label="Scout",
        include_raw_content=False,
        body_limit=1000
    )

    if not scout_results.strip():
        raise RuntimeError("No search results returned from Tavily.")

    print("\n[Phase 3] Selecting one interesting find...")
    time.sleep(5)

    selection_prompt = build_find_selection_prompt(
        today=today,
        scout_results=scout_results[:14000]
    )

    selection = call_groq(selection_prompt, max_tokens=1500, temperature=0.3)

    find_title = selection.get("find_title", "One Interesting Thing")
    article_angle = selection.get("article_angle", "")
    why_worth_reading = selection.get("why_this_is_worth_reading", "")
    main_source_title = selection.get("main_source_title", "")
    main_source_url = selection.get("main_source_url", "")
    source_strength = selection.get("source_strength", "")
    what_to_avoid = selection.get("what_to_avoid", "")
    followup_queries = selection.get("followup_queries", [])

    if not followup_queries:
        followup_queries = scout_queries[:6]

    print(f"\nFind: {find_title}")
    print(f"Angle: {article_angle}")
    print(f"Main source: {main_source_title} — {main_source_url}")
    print(f"Source strength: {source_strength}")
    print(f"Avoid: {what_to_avoid}")

    print("\n[Phase 4] Deepening the find with raw content...")
    time.sleep(5)

    deep_results = search_batch(
        followup_queries,
        max_results=5,
        label="Deep",
        include_raw_content=True,
        body_limit=3200
    )

    if not deep_results.strip():
        print("No deep results returned. Falling back to scout results.")
        deep_results = scout_results

    print("\n[Phase 5] Writing article...")
    time.sleep(8)

    article_prompt = build_article_prompt(
        today=today,
        find_title=find_title,
        article_angle=article_angle,
        why_worth_reading=why_worth_reading,
        main_source_title=main_source_title,
        main_source_url=main_source_url,
        source_strength=source_strength,
        what_to_avoid=what_to_avoid,
        deep_results=deep_results[:18000],
        scout_results=scout_results[:5000]
    )

    draft = call_groq(article_prompt, max_tokens=3300, temperature=0.35)

    print("\n[Phase 6] Refining article...")
    time.sleep(5)

    refinement_prompt = build_refinement_prompt(
        draft_json=draft,
        deep_results=deep_results[:16000]
    )

    data = call_groq(refinement_prompt, max_tokens=3300, temperature=0.25)

    subject = data.get("subject_line") or f"Paid Social Edge: {data.get('title', find_title)}"
    subject = compact_text(subject, 70)

    html = build_html(data)

    print(f"\nSubject: {subject}")
    print("[Phase 7] Sending email...")
    send_email(html, subject)


if __name__ == "__main__":
    main()
