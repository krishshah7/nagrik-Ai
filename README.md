# Nagrik AI 2.0 — AI-Powered Civic Complaint Assistant

Nagrik AI lets citizens report civic problems (potholes, drainage, garbage, streetlights, etc.),
automatically triages every complaint with Gemini, answers questions about municipal rules using
RAG over real documents, and routes chat questions to the right AI agent — all in one small,
easy-to-read Flask app.

Built in 4 phases, each adding one new skill on top of the last:

| Phase | What it adds | Concepts |
|---|---|---|
| 1. Software Engineering | Login, register, submit/search/filter complaints, admin panel | CRUD, REST routes, DB design |
| 2. Generative AI | Gemini classifies, summarizes, rewrites, translates, and answers "how do I..." | Prompting, structured output |
| 3. RAG | Answers "who is responsible for..." using real municipal documents | Embeddings, FAISS, retrieval |
| 4. Agentic AI | A Router Agent sends chat messages to a Complaint / Knowledge / Analytics agent | Multi-agent orchestration (LangGraph) |

## Features

- Citizen registration and login
- Submit a complaint — Gemini automatically fills in category, severity, summary, and a
  suggested action
- "Rewrite with AI" button to clean up a complaint before submitting
- Dashboard with search and filters (by category, status, keyword)
- Admin panel to review complaints and update their status
- AI Assistant chat page: describe a new problem, ask about rules/schemes, or ask about
  complaint statistics — a Router Agent decides who should answer

## Tech Stack

- **Backend:** Flask, Flask-SQLAlchemy, Flask-Login, SQLite
- **AI:** Google Gemini (`google-generativeai`)
- **RAG:** LangChain + FAISS
- **Agents:** LangGraph
- **Frontend:** plain HTML / CSS / JS (Jinja2 templates, no framework)

## Project Structure

```
nagrik-ai/
├── app.py                  # Flask routes (Phase 1)
├── models.py                # User & Complaint database models
├── ai_agents.py              # All AI logic: Phases 2, 3, and 4 in one file
├── requirements.txt
├── .env.example
├── static/
│   ├── style.css
│   └── script.js
├── templates/
│   ├── base.html
│   ├── login.html
│   ├── register.html
│   ├── submit.html
│   ├── dashboard.html
│   ├── admin.html
│   └── assistant.html
└── data/
    └── municipal_docs/       # Sample rules/schemes used for RAG (Phase 3)
        ├── amc_complaint_rules.txt
        ├── government_schemes.txt
        └── municipal_guidelines.txt
```

> The files in `data/municipal_docs/` are **sample/placeholder documents** written for this
> project. Replace them with your city's real complaint rules, scheme PDFs (converted to `.txt`),
> and municipal guidelines to make the RAG answers accurate for a real deployment.

## How the AI pieces fit together

- **`classify_complaint()`** — Phase 2. Turns a raw complaint into `category`, `severity`,
  `summary`, `suggested_action` using a single Gemini prompt with a strict JSON output format.
- **`knowledge_agent_answer()`** — Phase 3. Splits the `.txt` files in `data/municipal_docs/`
  into chunks, embeds them with Gemini embeddings, indexes them in FAISS, retrieves the top
  matches for a question, and asks Gemini to answer using only that context.
- **`run_agent()`** — Phase 4. A small LangGraph graph with 4 nodes: `router`,
  `complaint_agent`, `knowledge_agent`, `analytics_agent`. The router asks Gemini to label the
  incoming message, then the graph sends it to the matching agent. The analytics agent is only
  ever shown pre-computed statistics from safe SQLAlchemy queries — the LLM never writes or
  runs raw SQL, which keeps it simple and safe.

**No API key? No problem.** Every AI function has a rule-based or keyword-based fallback, so the
whole app still runs and is demoable without a `GEMINI_API_KEY` — you'll just get simpler
answers instead of Gemini's.

## Setup

1. **Clone and enter the project**
   ```bash
   git clone https://github.com/<your-username>/nagrik-ai.git
   cd nagrik-ai
   ```

2. **Create a virtual environment**
   ```bash
   python -m venv venv
   source venv/bin/activate        # Windows: venv\Scripts\activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Set up your environment variables**
   ```bash
   cp .env.example .env
   ```
   Then open `.env` and add your Gemini API key (free at
   [aistudio.google.com/apikey](https://aistudio.google.com/apikey)).

5. **Run the app**
   ```bash
   python app.py
   ```
   Visit `http://127.0.0.1:5000`. The database (`nagrik.db`) and a default admin account are
   created automatically on first run.

   **Default admin login:** `admin@nagrik.ai` / `admin123` (change this before using the app for
   anything real).

## Pushing this to your own GitHub

```bash
git init
git add .
git commit -m "Nagrik AI 2.0 - civic complaint assistant"
git branch -M main
git remote add origin https://github.com/<your-username>/nagrik-ai.git
git push -u origin main
```

`.env` and `nagrik.db` are already excluded via `.gitignore` so you won't accidentally commit
your API key or local data.

## Possible next steps

- Swap the sample `data/municipal_docs/` files for your city's real rulebook
- Add file/photo upload for complaints
- Add email/SMS notifications when a complaint's status changes
- Deploy with a production server (e.g. Gunicorn) and a persistent Postgres database
