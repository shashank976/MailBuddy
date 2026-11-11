# MailBuddy

**Your inbox, minus the noise.**

MailBuddy is a local-first AI assistant that turns a busy Gmail inbox into a short, personalized list of conversations worth your attention. It understands email threads, highlights possible next steps, and keeps less relevant messages out of the way—without sending your messages to a hosted AI model.

Built with **React · TypeScript · FastAPI · LangGraph · Ollama · SQLite**.

> **Read and recommend, never act automatically.** MailBuddy does not send, delete, archive, or unsubscribe from emails.

## What it does

| Feature | Description |
| --- | --- |
| **Priority Inbox** | Surfaces **Needs Attention** and **Important Updates** first. |
| **Personalized priorities** | Uses your interests, responsibilities, and preferences to decide what matters. |
| **Conversation awareness** | Reads full thread histories and attempts to identify whether a request is still outstanding. |
| **Local AI** | Analyzes messages with Ollama and a locally running model. |
| **Feedback** | Lets you correct priority and category, and optionally remember a preference. |
| **Cleanup** | Keeps lower-priority messages accessible with non-destructive cleanup suggestions. |
| **Caching and progress** | Saves results in SQLite and shows scan progress batch by batch. |

## How it works

```text
Gmail API + OAuth
      |
      v
Recent conversations (last 24 hours)
      |
      v
Full thread history + message parsing
      |
      v
LangGraph analysis with local Ollama
  - Priority and action classification
  - Summarization
  - Conversation-level action resolution
  - Cleanup recommendations
      |
      v
SQLite cache + saved feedback
      |
      v
React Priority Inbox
```

MailBuddy examines Gmail threads with activity in the last **24 hours**, including older messages within those threads for context. It does **not** import the entire historical inbox. Processing runs in thread-safe batches of five conversations.

## Tech stack

| Layer | Technology |
| --- | --- |
| Frontend | React, TypeScript, Vite, Lucide |
| Backend | Python, FastAPI, Pydantic |
| AI workflow | LangGraph |
| Local inference | Ollama (`qwen3:4b-instruct` by default) |
| Email integration | Gmail API, Google OAuth 2.0 |
| Persistence | SQLite |

## Getting started

### Prerequisites

- Python 3.11+ and Node.js/npm (the project has primarily been developed on macOS)
- [Ollama](https://ollama.com/) installed locally
- A Google Cloud project with the **Gmail API enabled**
- A Google OAuth **Desktop application** client

### 1. Clone the repository

```bash
git clone https://github.com/shashank976/MailBuddy.git
cd MailBuddy
```

### 2. Configure Gmail OAuth

In the [Google Cloud Console](https://console.cloud.google.com/), enable the Gmail API, configure the OAuth consent screen, and create a **Desktop app** OAuth client. Download its JSON credentials file and save it as:

```text
backend/credentials.json
```

If the OAuth app is in testing mode, add your Google account as a test user. **Never commit credentials or tokens.**

### 3. Start the backend

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

In another terminal, start Ollama if it is not already running, and pull the model:

```bash
ollama pull qwen3:4b-instruct
```

Then run the API from the `backend/` directory:

```bash
uvicorn api:app --host 127.0.0.1 --port 8000 --reload
```

The first Gmail connection launches a browser-based OAuth authorization flow. The resulting token is stored locally at `backend/token.json`.

API documentation: <http://127.0.0.1:8000/docs>

### 4. Start the frontend

In a separate terminal, from the repository root:

```bash
cd frontend
npm ci
npm run dev
```

Open **<http://localhost:5173>**, set up **Your Profile**, then select **Analyze inbox**.

The first uncached scan may take several minutes depending on inbox size and your computer. Subsequent scans can reuse cached analyses when their inputs and version are unchanged.

## Privacy and safety

MailBuddy is designed for local AI inference and local analysis storage:

- Gmail messages are retrieved through Google's Gmail API using OAuth.
- Analysis is performed through Ollama running at `127.0.0.1` by default—not a hosted LLM API.
- Analysis results, feedback, and cached data are stored locally in SQLite; the user profile is stored in browser storage.
- Recommendations are advisory. MailBuddy never automatically changes or sends Gmail messages.
- Local tokens, OAuth credentials, environment files, and databases are excluded from Git via `.gitignore`.

**OAuth permission note:** The current implementation requests the `gmail.modify` scope even though its supported workflow is read-only. Reducing this to a read-only scope is a future improvement; changing scopes may require reauthorization.

**Important:** Always review consequential emails in Gmail. AI classifications and suggested actions can be wrong.

## Limitations

- Email importance is subjective; classification quality depends on the model and your profile.
- Local inference can be slow, especially with long threads or an uncached inbox.
- Gmail API rate limits may interrupt large or repeated scans.
- Only threads active in the last 24 hours are included, not all historical or unread mail.
- The progress indicator updates after each completed batch rather than each individual message.

## Screenshots

*Coming soon — screenshots will be added after email addresses and private content are redacted.*

## Project layout

```text
MailBuddy/
├── backend/
│   ├── agents/             # Classification, summaries, action resolution
│   ├── schemas/            # Structured agent outputs
│   ├── services/           # Caching, batching, feedback, dashboard storage
│   ├── workflows/          # LangGraph orchestration
│   ├── api.py              # FastAPI endpoints
│   ├── gmail_service.py    # OAuth and Gmail retrieval
│   └── requirements.txt
├── frontend/
│   ├── public/             # MailBuddy mascot and assets
│   └── src/                # React application
└── README.md
```

---

MailBuddy is an independent project exploring local language models, agent-based workflows, and privacy-conscious software design.
