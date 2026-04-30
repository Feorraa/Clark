# Daily News Discord Agent

This is a small Google Cloud agent that sends a daily topic-based news brief to your Discord DMs.

## Architecture

Cloud Scheduler calls a private Cloud Run endpoint once per day. Cloud Run fetches Google News RSS items for your configured topics, asks Gemini on Vertex AI to turn them into a compact brief, then sends the message through the Discord bot REST API.

The service does not keep a Discord gateway connection open. That keeps Cloud Run cheap and reliable for a daily push notification.

## What You Need

- A Google Cloud project with billing enabled.
- The `gcloud` CLI installed and authenticated.
- A Discord application with a bot token.
- Your Discord user ID.

## Discord Setup

1. Open the Discord Developer Portal and create an application.
2. Add a bot to the application and copy the bot token.
3. Invite the bot to a private server you are in. For DM delivery, the bot and your user should share a server, and your privacy settings must allow the DM.
4. Enable Discord Developer Mode, right-click your profile, and copy your user ID.

Invite URL shape:

```text
https://discord.com/oauth2/authorize?client_id=YOUR_APPLICATION_ID&permissions=2048&integration_type=0&scope=bot
```

## Deploy From Windows PowerShell

From this folder, copy the deploy config template:

```powershell
Copy-Item .deploy.env.example .deploy.env
notepad .deploy.env
```

Fill in:

```text
PROJECT_ID=your-gcp-project-id
DISCORD_USER_ID=your-discord-user-id
DISCORD_BOT_TOKEN=your-discord-bot-token
```

Then deploy with:

```powershell
.\scripts\deploy.ps1
```

The script will:

- Enable the needed Google Cloud APIs.
- Create a runtime service account and a scheduler service account.
- Store your Discord bot token in Secret Manager.
- Deploy the service to Cloud Run from source.
- Create or update a daily Cloud Scheduler job.

By default, the scheduler runs every day at 6:00 AM Thailand time.

`.deploy.env` is ignored by git and by Google Cloud source uploads, so your Discord bot token stays local except when the script stores it in Secret Manager.

To send a test digest immediately:

```powershell
gcloud scheduler jobs run daily-news-agent-daily --location us-central1 --project your-gcp-project-id
```

To view logs:

```powershell
gcloud run services logs read daily-news-agent --region us-central1 --project your-gcp-project-id
```

## Local Development

```powershell
Copy-Item .env.example .env
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Edit `.env` with your values, then preview without sending:

```powershell
Invoke-RestMethod -Method Post "http://127.0.0.1:8000/run?send=false"
```

Send locally to Discord:

```powershell
Invoke-RestMethod -Method Post "http://127.0.0.1:8000/run"
```

## Configuration

| Variable | Purpose |
| --- | --- |
| `DISCORD_BOT_TOKEN` | Discord bot token. Use Secret Manager in Cloud Run. |
| `DISCORD_USER_ID` | Your Discord user ID. |
| `NEWS_TOPICS` | Comma-separated topics. |
| `NEWS_LANGUAGE` | Google News RSS language, default `en-US`. |
| `NEWS_COUNTRY` | Google News RSS country, default `US`. |
| `NEWS_CEID` | Google News RSS edition, default `US:en`. |
| `NEWS_LOOKBACK_DAYS` | RSS search lookback window, default `1`. |
| `NEWS_ITEMS_PER_TOPIC` | Items to collect per topic, default `5`. |
| `DIGEST_TIMEZONE` | Date/time zone used in the digest. |
| `GEMINI_MODEL` | Vertex AI Gemini model, default `gemini-2.5-flash`. |
| `AGENT_RUN_TOKEN` | Optional shared secret if you ever make the service public. |
| `DRY_RUN` | Set `true` to generate without sending to Discord. |

## Notes

Discord discourages opening large numbers of unsolicited DMs. This project is designed for one user: you. If you later want subscriber management, add explicit opt-in and store user preferences in Firestore.
