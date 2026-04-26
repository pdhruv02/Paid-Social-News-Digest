# Paid Social Edge — Setup Guide

Weekly AI-researched newsletter for your paid social team.
Runs every **Tuesday at 6 AM CST**, fully automated via GitHub Actions.

---

## What You'll Need (all free)

| Tool | Purpose | Free tier |
|------|---------|-----------|
| [GitHub](https://github.com) account | Runs the automation | Free |
| [Resend](https://resend.com) account | Sends the emails | 3,000 emails/month free |
| Anthropic API key | AI research engine | Pay-per-use (~$0.50–$2 per run with Opus) |

---

## Step 1 — Create a GitHub Repository

1. Go to [github.com/new](https://github.com/new)
2. Name it `paid-social-edge` (private is fine)
3. Click **Create repository**
4. Upload all these files into the repo (drag & drop works):
   - `newsletter.py`
   - `subscribers.json`
   - `.github/workflows/newsletter.yml`

---

## Step 2 — Set Up Resend

1. Sign up at [resend.com](https://resend.com)
2. Go to **Domains** → Add your sending domain (e.g. `yourcompany.com`)
3. Add the DNS records Resend gives you (takes 5–10 min to verify)
4. Go to **API Keys** → Create a new key → Copy it

> **Don't have a domain to verify?** Resend lets you send from `onboarding@resend.dev`
> for testing. Just use that as your FROM_EMAIL until you verify a domain.

---

## Step 3 — Add Your Secrets to GitHub

In your GitHub repo: **Settings → Secrets and variables → Actions → New repository secret**

Add these three secrets:

| Secret name | Value |
|-------------|-------|
| `ANTHROPIC_API_KEY` | Your Anthropic API key (from console.anthropic.com) |
| `RESEND_API_KEY` | Your Resend API key |
| `FROM_EMAIL` | e.g. `newsletter@yourcompany.com` |

---

## Step 4 — Add Your Subscribers

Edit `subscribers.json` and replace the example emails with your team's emails:

```json
{
  "emails": [
    "vp-paid-social@yourcompany.com",
    "senior-buyer-1@yourcompany.com",
    "senior-buyer-2@yourcompany.com"
  ]
}
```

Commit and push the change. That's your subscriber list — edit it any time.

---

## Step 5 — Test It

1. In your GitHub repo, go to **Actions**
2. Click **Paid Social Edge — Weekly Newsletter** in the left sidebar
3. Click **Run workflow** → **Run workflow**
4. Watch the logs — it should complete in 2–4 minutes
5. Check your inbox ✅

---

## Schedule

Runs every **Tuesday at 11:00 UTC** (= 6:00 AM CDT, Apr–Nov).

In winter (Nov–Mar) when Central Standard Time is UTC-6, you may want to
change the cron line in `.github/workflows/newsletter.yml` from:
```
- cron: '0 11 * * 2'
```
to:
```
- cron: '0 12 * * 2'
```

---

## Adjusting the Research Prompt

The research instructions live in `newsletter.py` in the `RESEARCH_PROMPT` variable.
You can edit this at any time — adjust topics, change the quality bar, add specific
areas to watch, etc. It's plain English, no coding knowledge needed.

---

## Cost Estimate

| Component | Approx. cost per run |
|-----------|---------------------|
| Claude Opus (research) | ~$1.50–$3.00 |
| Resend (email sending) | Free up to 3,000/month |
| GitHub Actions | Free |

To reduce cost, change `MODEL = "claude-opus-4-6"` to `MODEL = "claude-sonnet-4-6"`
in `newsletter.py` — roughly 5–10× cheaper with slightly less research depth.

---

## Troubleshooting

**"No JSON found in response"** — The AI returned an unexpected format. Re-run the
workflow; it's usually a one-off. If persistent, check your Anthropic API key.

**"Authentication failed" on Resend** — Double-check your `RESEND_API_KEY` secret
and that your FROM_EMAIL domain is verified in Resend.

**Emails going to spam** — Make sure your Resend domain DNS records are fully
verified, and that your FROM_EMAIL matches the verified domain.
