"""
Paid Social Edge — Paid Social Case / Ad Curator Newsletter

What this version is optimized for:
- Good campaigns, ads, case studies, platform examples, and teardowns
- Paid social mechanics, not generic brand-purpose stories
- Useful reads for people who actually work on paid social ads
- Concrete details: platform, format, audience, creative, media buying, testing, measurement, funnel, offer, or distribution
- Simple output: title, subtitle, body, main source

Avoids:
- Broad emotional advertising stories with no paid social mechanics
- Generic “marketing can do good” writeups
- Surface-level awards/case studies
- Overly templatey sections
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

RUN_ODD_WEEKS_ONLY = os.environ.get("RUN_ODD_WEEKS_ONLY", "false").lower() == "true"


# ── Week gate ─────────────────────────────────────────────────────────────────

def check_week():
    week = datetime.now(CST).isocalendar()[1]

    if RUN_ODD_WEEKS_ONLY and week % 2 == 0:
        print(f"Week {week} is even — skipping this deep-dive run.")
        exit(0)

    print(f"Week {week} — running Paid Social Edge curator issue.")


# ── Basic helpers ─────────────────────────────────────────────────────────────

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
    """
    Groq JSON mode should return valid JSON, but this fallback helps if a model
    accidentally wraps JSON in markdown or includes surrounding text.
    """
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
        raise ValueError(f"No JSON object found in model output:\n{raw[:1000]}")

    return match.group()


def validate_keys(data: dict, required_keys: list, step_name: str):
    missing = [k for k in required_keys if k not in data]
    if missing:
        raise ValueError(f"{step_name} missing required keys: {missing}")


def call_groq_json(
    prompt: str,
    required_keys: list,
    step_name: str,
    max_tokens: int = 1800,
    temperature: float = 0.35,
    repair_context: str = ""
) -> dict:
    """
    Calls Groq using JSON Object Mode and validates required keys.
    If schema validation fails, retries with a stricter repair prompt.
    """
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
                    {"role": "user", "content": current_prompt}
                ],
                temperature=temperature,
                max_tokens=max_tokens,
                response_format={"type": "json_object"},
            )

            raw = resp.choices[0].message.content or ""
            json_text = get_json_text(raw)
            data = json.loads(json_text)
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
{repair_context[:4000]}
"""

    raise RuntimeError(f"{step_name} failed after 3 attempts. Last error: {last_error}")


# ── Prompts ───────────────────────────────────────────────────────────────────

def build_scout_query_prompt(today: str) -> str:
    return f"""
Today is {today}.

Create search queries for a newsletter that finds one genuinely useful paid social / advertising example worth studying.

The goal is not to find a broadly inspiring marketing story.
The goal is to find something useful for someone who works on paid social ads.

Look for campaigns, ads, case studies, teardowns, research, or platform examples where there is some real detail about how the advertising worked.

Useful details might include:
- paid social platform used
- ad format
- creative approach
- targeting or audience insight
- media buying setup
- testing method
- measurement approach
- funnel role
- offer or landing page
- influencer/creator distribution
- performance signal
- category or competitor messaging pattern

Good sources may include official platform case studies, ad libraries, brand campaign pages, Effie, WARC, IPA, Think with Google, YouTube Works, LinkedIn B2B Institute, Reddit for Business, Meta for Business, TikTok Business, IAB, AdExchanger, Digiday, Marketing Brew, eMarketer, Campaign, The Drum, Marketing Examples, Exit Five, paid social practitioner teardowns, agency writeups, and public campaign pages.

These are examples, not a required source list.

Avoid queries that will mostly return generic advice, emotional brand-purpose stories, or award pages with no media/creative mechanics.

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

You are curating one paid social / advertising example for a newsletter read by paid social operators.

Your job:
From the research results below, choose one thing worth writing about.

Do not choose a campaign only because it is emotional, awarded, socially important, or creatively famous.
Choose it only if it has a useful advertising mechanism that someone in paid social could learn from.

Raw research results:
{scout_results}

A good pick could be:
- a paid social case study with real mechanics
- a campaign with interesting social/ad distribution
- a creative testing example
- an ad format or platform example
- a creator/influencer campaign with clear media logic
- a B2B paid media example
- a brand/category campaign with a clear paid social lesson
- a measurement or attribution example
- a teardown with specific ads, audiences, hooks, landing pages, or results
- a platform change that affects how ads are bought, tested, or measured

Avoid:
- broad brand-purpose campaigns with no paid media detail
- “marketing can do good” stories
- award summaries with no mechanics
- generic “this campaign resonated with Gen Z” writing
- examples where the only lesson is “understand your audience”
- examples where the article would become emotional but not useful

Selection standard:
A strong find should have at least one concrete paid-media detail: platform, format, audience, creative mechanic, buying/targeting approach, testing approach, measurement signal, funnel role, or campaign architecture.

If the best emotional/award-winning campaign has no paid social mechanics, do not pick it.

Return JSON only with this schema:
{{
  "should_publish": true,
  "find_title": "A short description of the chosen find",
  "article_angle": "The specific paid social / advertising angle the article should explore",
  "why_this_is_worth_reading": "Why this is useful for paid social operators, not just generally interesting",
  "main_source_title": "Best main source title",
  "main_source_url": "Best main source URL",
  "main_source_type": "Case study | Article | Research report | Campaign page | Teardown | Platform source | Other",
  "source_strength": "Strong | Medium | Thin",
  "paid_media_detail": "The concrete paid social, media buying, creative, targeting, testing, or measurement detail that makes this worth studying",
  "what_to_avoid": "What would make the article boring, emotional-only, or generic",
  "followup_queries": [
    "5 to 8 search queries to deepen this exact paid social/ad mechanics angle"
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
    paid_media_detail: str,
    what_to_avoid: str,
    extracted_main_source: str,
    deep_results: str,
    scout_results: str
) -> str:
    return f"""
Today is {today}.

Write one article-style email for a paid social / advertising newsletter.

This should not feel like a template.
There should be no fixed sections like "operator lessons," "what to test," "practical implications," or "key takeaways."

Chosen find:
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

Concrete paid-media detail to anchor the article:
{paid_media_detail}

What to avoid:
{what_to_avoid}

Extracted main source content:
{extracted_main_source}

Deep research results:
{deep_results}

Earlier scout results:
{scout_results}

Private reader context:
- The reader works in paid social.
- They care about ads, campaigns, creative, platforms, buying, targeting, testing, measurement, buyer behavior, and useful advertising examples.
- Do not make the article company-specific.

Write like:
"I found this useful advertising example. Here is what happened, what makes the campaign/ad interesting, and what it quietly teaches about paid social."

Tone:
- smart
- plainspoken
- specific
- useful
- not corporate
- not emotional for the sake of being emotional
- not generic

Hard rules:
- Do not write a general brand-purpose essay.
- Do not make the core lesson “marketing can do good.”
- Do not write generic lines like “this improves ROI,” “testing is important,” “brands need to understand audiences,” or “creative is key.”
- Do not repeat the same takeaway in different words.
- Do not force advice.
- Do not include bullet points unless the article genuinely needs them.
- The body should be 500 to 850 words.
- Use paragraphs.
- Include concrete details from sources.
- If the evidence is thin, be honest and write a shorter article.
- Do not invent facts.
- If the main source is promotional, say how to read it carefully.
- End naturally. Do not add a forced conclusion section.

Return JSON only with this schema:
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


def build_refinement_prompt(draft_json: dict, evidence: str) -> str:
    draft_text = json.dumps(draft_json, ensure_ascii=False, indent=2)

    return f"""
Edit this paid social / advertising newsletter article.

Reviewer feedback to solve:
- The article should be useful for someone in paid social ads.
- It should not become an emotional brand-purpose essay.
- It should not sound like generic marketing advice.
- It should include concrete campaign, ad, platform, creative, media buying, targeting, testing, or measurement details.
- It should feel like one useful paid social / advertising read, not a broad inspiration story.

Draft JSON:
{draft_text}

Evidence available:
{evidence}

Rules:
1. Keep the exact same JSON schema.
2. Remove generic lines.
3. Make the article more specific and useful for paid social operators.
4. Every paragraph should add something new.
5. Use concrete details from the evidence where possible.
6. Do not add unsupported facts.
7. Do not use corporate phrases like "leverage," "unlock," "drive ROI," "must prioritize," or "deep understanding."
8. Do not make it company-specific.
9. Keep body between 500 and 850 words unless the evidence is thin.
10. Keep the tone natural and readable.
11. If the draft is mainly emotional or brand-purpose driven, rewrite it around the paid media / creative / platform / measurement mechanism instead.

Return JSON only with this schema:
{{
  "subject_line": "Email subject line under 70 characters",
  "title": "Article title",
  "subtitle": "One-sentence subtitle",
  "body": "Full article body with paragraphs separated by blank lines.",
  "main_source_title": "Main source title",
  "main_source_url": "Main source URL",
  "source_note": "One sentence on why this source is worth reading or how to read it carefully."
}}
"""


# ── Tavily functions ──────────────────────────────────────────────────────────

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
                query=q,
                search_depth="advanced",
                max_results=max_results,
                include_raw_content=include_raw_content,
                include_answer=False,
                chunks_per_source=3,
                timeout=45
            )

            for item in response.get("results", []):
                url = item.get("url", "").strip()

                if not url or url in seen_urls:
                    continue

                seen_urls.add(url)

                title = item.get("title", "")
                published_date = item.get("published_date", "unknown")
                score = item.get("score", "")

                raw_content = item.get("raw_content") or ""
                snippet_content = item.get("content") or ""
                content = raw_content if raw_content else snippet_content

                results.append(
                    f"QUERY: {q}\n"
                    f"TITLE: {title}\n"
                    f"URL: {url}\n"
                    f"DATE: {published_date}\n"
                    f"SCORE: {score}\n"
                    f"BODY: {compact_text(content, body_limit)}\n"
                    f"---"
                )

            time.sleep(0.4)

        except Exception as e:
            print(f"    Search error: {e}")

    return "\n\n".join(results)


def extract_url_content(url: str, query: str = "") -> str:
    if not url or url == "#":
        return ""

    tavily = TavilyClient(api_key=TAVILY_API_KEY)

    try:
        kwargs = {
            "urls": [url],
            "extract_depth": "advanced",
            "format": "markdown",
            "timeout": 30,
            "include_images": False
        }

        if query:
            kwargs["query"] = query
            kwargs["chunks_per_source"] = 5

        response = tavily.extract(**kwargs)
        results = response.get("results", [])

        if not results:
            failed = response.get("failed_results", [])
            print(f"  Tavily extract returned no result. Failed: {failed}")
            return ""

        raw = results[0].get("raw_content", "")
        return compact_text(raw, 7000)

    except Exception as e:
        print(f"  Tavily extract failed for {url}: {e}")
        return ""


def fallback_scout_queries() -> list:
    return [
        "paid social campaign case study ad format targeting creative measurement",
        "Meta ads case study creative testing audience targeting results",
        "LinkedIn ads B2B campaign case study lead quality targeting creative",
        "TikTok Spark Ads case study creator paid social campaign mechanics",
        "Reddit ads case study community targeting paid social results",
        "YouTube ads case study creative testing media strategy results",
        "paid social advertising teardown specific ads landing page audience",
        "performance creative testing paid social case study hooks formats",
        "B2B paid social campaign teardown LinkedIn Meta Reddit",
        "paid media campaign case study attribution incrementality lift study",
        "technology brand paid social campaign case study ad creative",
        "creator influencer paid social campaign case study media buying"
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
              Paid Social Case Note
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
              Paid Social Edge · Campaigns, ads, and case studies worth studying
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
        scout_data = call_groq_json(
            prompt=scout_prompt,
            required_keys=["queries"],
            step_name="Scout query generation",
            max_tokens=1200,
            temperature=0.55
        )

        scout_queries = scout_data.get("queries", [])
        if not isinstance(scout_queries, list) or not scout_queries:
            raise ValueError("Scout queries must be a non-empty list.")

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

    print("\n[Phase 3] Selecting one paid-social-relevant find...")
    time.sleep(3)

    selection_prompt = build_find_selection_prompt(
        today=today,
        scout_results=scout_results[:13000]
    )

    selection = call_groq_json(
        prompt=selection_prompt,
        required_keys=[
            "find_title",
            "article_angle",
            "why_this_is_worth_reading",
            "main_source_title",
            "main_source_url",
            "source_strength",
            "paid_media_detail",
            "what_to_avoid",
            "followup_queries"
        ],
        step_name="Find selection",
        max_tokens=1800,
        temperature=0.25,
        repair_context=scout_results[:4000]
    )

    find_title = selection.get("find_title", "One Paid Social Example")
    article_angle = selection.get("article_angle", "")
    why_worth_reading = selection.get("why_this_is_worth_reading", "")
    main_source_title = selection.get("main_source_title", "")
    main_source_url = clean_url(selection.get("main_source_url", ""))
    source_strength = selection.get("source_strength", "")
    paid_media_detail = selection.get("paid_media_detail", "")
    what_to_avoid = selection.get("what_to_avoid", "")
    followup_queries = selection.get("followup_queries", [])

    if not isinstance(followup_queries, list) or not followup_queries:
        followup_queries = scout_queries[:6]

    print(f"\nFind: {find_title}")
    print(f"Angle: {article_angle}")
    print(f"Main source: {main_source_title} — {main_source_url}")
    print(f"Source strength: {source_strength}")
    print(f"Paid media detail: {paid_media_detail}")
    print(f"Avoid: {what_to_avoid}")

    print("\n[Phase 4] Extracting main source content...")
    extracted_main_source = extract_url_content(
        url=main_source_url,
        query=article_angle or find_title
    )

    print("\n[Phase 5] Deepening the find with search...")
    time.sleep(3)

    deep_results = search_batch(
        followup_queries,
        max_results=4,
        label="Deep",
        include_raw_content=True,
        body_limit=2200
    )

    if not deep_results.strip():
        print("No deep results returned. Falling back to scout results.")
        deep_results = scout_results

    print("\n[Phase 6] Writing article...")
    time.sleep(5)

    article_prompt = build_article_prompt(
        today=today,
        find_title=find_title,
        article_angle=article_angle,
        why_worth_reading=why_worth_reading,
        main_source_title=main_source_title,
        main_source_url=main_source_url,
        source_strength=source_strength,
        paid_media_detail=paid_media_detail,
        what_to_avoid=what_to_avoid,
        extracted_main_source=extracted_main_source[:7000],
        deep_results=deep_results[:12000],
        scout_results=scout_results[:3000]
    )

    draft = call_groq_json(
        prompt=article_prompt,
        required_keys=[
            "subject_line",
            "title",
            "subtitle",
            "body",
            "main_source_title",
            "main_source_url",
            "source_note"
        ],
        step_name="Article writing",
        max_tokens=3000,
        temperature=0.30,
        repair_context=(extracted_main_source + "\n\n" + deep_results)[:5000]
    )

    print("\n[Phase 7] Refining article...")
    time.sleep(3)

    refinement_prompt = build_refinement_prompt(
        draft_json=draft,
        evidence=(extracted_main_source + "\n\n" + deep_results)[:13000]
    )

    data = call_groq_json(
        prompt=refinement_prompt,
        required_keys=[
            "subject_line",
            "title",
            "subtitle",
            "body",
            "main_source_title",
            "main_source_url",
            "source_note"
        ],
        step_name="Article refinement",
        max_tokens=3000,
        temperature=0.22,
        repair_context=(extracted_main_source + "\n\n" + deep_results)[:4000]
    )

    subject = data.get("subject_line") or f"Paid Social Edge: {data.get('title', find_title)}"
    subject = compact_text(subject, 70)

    html = build_html(data)

    print(f"\nSubject: {subject}")
    print("[Phase 8] Sending email...")
    send_email(html, subject)


if __name__ == "__main__":
    main()
