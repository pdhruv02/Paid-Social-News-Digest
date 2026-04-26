from google import genai
from google.genai import types
import resend
import json
import os
import re
import time
from datetime import datetime
import pytz

# ── Config ──────────────────────────────────────────────────────────────────
GEMINI_API_KEY = os.environ["GEMINI_API_KEY"]
RESEND_API_KEY = os.environ["RESEND_API_KEY"]
FROM_EMAIL     = os.environ["FROM_EMAIL"]          # e.g. newsletter@yourdomain.com
FROM_NAME      = "Paid Social Edge"
SUBSCRIBERS_FILE = "subscribers.json"
MODEL          = "gemini-2.0-flash"                # free tier on Google AI Studio

CST = pytz.timezone("US/Central")

# ── Research ─────────────────────────────────────────────────────────────────

RESEARCH_PROMPT = """Today is {today}. You are a senior paid social strategist and intelligence analyst.

Your task: produce the weekly "Paid Social Edge" briefing for the paid social leadership team at a Fortune 100 company — Directors, VPs, and senior media buyers. These people run nine-figure media budgets, live inside Ads Manager, and are fluent in every platform. They don't need basics. They need signal.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
WHAT TO RESEARCH (search broadly)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

1. Platform mechanics & product changes
   Meta (Facebook/Instagram Ads), Google Ads, YouTube, TikTok Ads, LinkedIn Ads,
   Pinterest, Snapchat, Reddit — algorithm shifts, new ad products, auction changes,
   targeting updates, policy changes, beta launches, API/measurement changes.
   Prioritize anything that changes how you'd actually run or structure campaigns.

2. Exceptional brand campaigns & creative strategies
   Not "great ad" stories — look for campaigns where a company did something
   structurally or strategically interesting in paid social: unusual targeting,
   creative architecture, measurement approach, cross-platform plays, or results
   that reveal something about what's working now.

3. Research, data & benchmarks
   New studies, platform-released data, third-party benchmark reports, or
   privacy/signal-loss research that should change how someone thinks about
   measurement, attribution, or bidding strategy.

4. Industry & ecosystem moves
   Acquisitions, partnerships, or structural changes in the ad tech ecosystem
   that will affect how large advertisers operate — measurement vendors, DSPs,
   creative tools, data clean rooms, etc.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
QUALITY FILTER — include ONLY if ALL true:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
✅ Happened or was published in the last 7–10 days
✅ A VP of Paid Social at a Fortune 100 would want to know this
✅ Knowing this creates a strategic advantage, informs a decision, or changes
   how you'd run/structure something
✅ Substantive enough to bring up in a media strategy or leadership meeting

EXCLUDE (strictly):
❌ Tips, how-tos, or educational content
❌ Evergreen articles with a recent publication date
❌ Stories that sound impressive but have no paid social implication
❌ Pure platform PR with no real product/policy change underneath
❌ Anything a competent senior buyer already knows

SEARCH STRATEGY:
Run multiple targeted searches. Cover each major platform. Look for both
official platform announcements and independent analyst/journalist coverage.
Search for brand case studies separately. Check for data releases and reports.
Use different angles and queries to avoid missing things.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
OUTPUT
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Return ONLY a valid JSON object — no markdown fences, no preamble, no explanation.

{{
  "week_of": "{today}",
  "opening_line": "1–2 punchy sentences capturing what defined this week in paid social. Written like a briefing memo opener, not a blog intro.",
  "items": [
    {{
      "category": "Meta Ads | Google/YouTube | TikTok | LinkedIn | Other Platform | Brand Campaign | Research & Data | Industry Move",
      "headline": "Sharp, specific headline. No clickbait. No vague teasers.",
      "summary": "2–4 sentences. What happened, why it matters, what the implication is for someone managing large-scale paid social. Be specific — mention numbers, products, or mechanics where relevant.",
      "edge": "The one concrete action, test, question, or watch item this creates for a Fortune 100 paid social team. Specific. Not generic advice.",
      "source_url": "direct URL to the primary source article or announcement",
      "source_name": "Publication or source name (e.g. 'Meta Business Blog', 'Marketing Brew', 'Search Engine Land')"
    }}
  ]
}}

Target 5–8 items. Fewer high-quality items beats more mediocre ones.
If a category had no meaningful news this week, leave it out entirely.
"""


def research_newsletter() -> dict:
    client = genai.Client(api_key=GEMINI_API_KEY)
    today  = datetime.now(CST).strftime("%B %d, %Y")
    prompt = RESEARCH_PROMPT.format(today=today)

    print("  → Calling Gemini with Google Search grounding…")
    response = client.models.generate_content(
        model=MODEL,
        contents=prompt,
        config=types.GenerateContentConfig(
            tools=[types.Tool(google_search=types.GoogleSearch())],
            temperature=0.3,
        ),
    )

    full_text = response.text

    # Strip any accidental markdown fences
    clean = re.sub(r"```(?:json)?|```", "", full_text).strip()

    # Find outermost JSON object
    match = re.search(r"\{.*\}", clean, re.DOTALL)
    if not match:
        raise ValueError(f"No JSON found in response:\n{full_text[:500]}")

    return json.loads(match.group())


# ── Email builder ─────────────────────────────────────────────────────────────

CATEGORY_COLORS = {
    "Meta Ads":        "#1877F2",
    "Google/YouTube":  "#EA4335",
    "TikTok":          "#2B2B2B",
    "LinkedIn":        "#0A66C2",
    "Other Platform":  "#6366F1",
    "Brand Campaign":  "#7C3AED",
    "Research & Data": "#059669",
    "Industry Move":   "#D97706",
}
DEFAULT_COLOR = "#4B5563"


def _item_html(item: dict) -> str:
    cat   = item.get("category", "Update")
    color = CATEGORY_COLORS.get(cat, DEFAULT_COLOR)
    url   = item.get("source_url", "#")
    src   = item.get("source_name", "Source")
    return f"""
    <table width="100%" cellpadding="0" cellspacing="0" border="0"
           style="background:#ffffff;border-radius:10px;border-left:4px solid {color};
                  box-shadow:0 1px 4px rgba(0,0,0,0.07);margin-bottom:20px;">
      <tr><td style="padding:22px 26px;">
        <span style="display:inline-block;background:{color};color:#fff;font-size:10px;
                     font-weight:700;letter-spacing:0.8px;padding:3px 10px;border-radius:20px;
                     text-transform:uppercase;margin-bottom:12px;">{cat}</span>
        <h3 style="margin:0 0 10px;font-size:16px;font-weight:700;color:#111827;line-height:1.45;">
          {item.get('headline','')}
        </h3>
        <p style="margin:0 0 14px;font-size:14px;color:#374151;line-height:1.75;">
          {item.get('summary','')}
        </p>
        <table cellpadding="0" cellspacing="0" border="0" width="100%" style="margin-bottom:14px;">
          <tr><td style="background:#F0FDF4;border-radius:7px;padding:11px 16px;">
            <span style="font-size:11px;font-weight:700;color:#059669;
                         text-transform:uppercase;letter-spacing:0.6px;">⚡ Your Edge</span>
            <p style="margin:5px 0 0;font-size:13px;color:#065F46;line-height:1.65;">
              {item.get('edge','')}
            </p>
          </td></tr>
        </table>
        <a href="{url}" style="font-size:13px;color:{color};text-decoration:none;font-weight:600;">
          Read full story → {src}
        </a>
      </td></tr>
    </table>"""


def build_email_html(data: dict) -> str:
    now       = datetime.now(CST)
    date_str  = now.strftime("%B %d, %Y")
    week_num  = now.isocalendar()[1]
    opening   = data.get("opening_line", "Your weekly paid social intelligence briefing.")
    items_html = "\n".join(_item_html(i) for i in data.get("items", []))
    count      = len(data.get("items", []))

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>Paid Social Edge — Week {week_num}</title>
</head>
<body style="margin:0;padding:0;background:#ECEEF2;
             font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;">
  <table width="100%" cellpadding="0" cellspacing="0" border="0">
    <tr><td align="center" style="padding:36px 16px;">
      <table width="620" cellpadding="0" cellspacing="0" border="0" style="max-width:620px;width:100%;">

        <!-- Header -->
        <tr><td style="background:linear-gradient(135deg,#0F0C29 0%,#1a1060 50%,#24243e 100%);
                        border-radius:12px 12px 0 0;padding:36px 40px 32px;">
          <p style="margin:0 0 6px;font-size:11px;font-weight:700;letter-spacing:2.5px;
                     text-transform:uppercase;color:#818CF8;">
            WEEK {week_num} &nbsp;·&nbsp; {date_str} &nbsp;·&nbsp; {count} STORIES
          </p>
          <h1 style="margin:0 0 14px;font-size:30px;font-weight:800;color:#ffffff;letter-spacing:-0.5px;">
            Paid Social Edge
          </h1>
          <p style="margin:0;font-size:15px;color:#C7D2FE;line-height:1.7;max-width:480px;">
            {opening}
          </p>
        </td></tr>

        <!-- Divider -->
        <tr><td style="background:#4F46E5;height:3px;"></td></tr>

        <!-- Body -->
        <tr><td style="background:#ECEEF2;padding:28px 16px 8px;">
          {items_html}
        </td></tr>

        <!-- Footer -->
        <tr><td style="background:#1F2937;border-radius:0 0 12px 12px;
                        padding:24px 40px;text-align:center;">
          <p style="margin:0 0 6px;font-size:13px;color:#9CA3AF;font-weight:500;">
            Paid Social Edge
          </p>
          <p style="margin:0;font-size:12px;color:#6B7280;line-height:1.6;">
            Delivered every Tuesday at 6 AM CST &nbsp;·&nbsp;
            Research powered by Claude AI + live web search
          </p>
        </td></tr>

      </table>
    </td></tr>
  </table>
</body>
</html>"""


# ── Send ──────────────────────────────────────────────────────────────────────

def send_newsletter(html: str, subject: str) -> None:
    resend.api_key = RESEND_API_KEY

    with open(SUBSCRIBERS_FILE) as f:
        data = json.load(f)

    emails = data.get("emails", [])
    if not emails:
        print("⚠️  No subscribers found in subscribers.json — nothing sent.")
        return

    sent, failed = 0, 0
    for email in emails:
        try:
            resend.Emails.send({
                "from":    f"{FROM_NAME} <{FROM_EMAIL}>",
                "to":      email,
                "subject": subject,
                "html":    html,
            })
            print(f"  ✓ {email}")
            sent += 1
            time.sleep(0.2)   # stay well under rate limits
        except Exception as e:
            print(f"  ✗ {email} — {e}")
            failed += 1

    print(f"\n📬 Sent {sent}/{len(emails)}  |  Failed: {failed}")


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    print("🔍  Researching this week's paid social landscape…")
    data = research_newsletter()

    n = len(data.get("items", []))
    print(f"✅  Found {n} qualifying stories")

    html    = build_email_html(data)
    week_no = datetime.now(CST).isocalendar()[1]
    opening = data.get("opening_line", "")[:70].rstrip()
    subject = f"Paid Social Edge — Week {week_no} | {opening}"

    print(f"📨  Subject: {subject}")
    send_newsletter(html, subject)


if __name__ == "__main__":
    main()
