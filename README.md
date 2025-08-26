![L'Attia Dialogue banner](assets/lattia_banner.jpg)

# L'Attia Dialogue

L'Attia Dialogue is an AI-powered health intake interview system inspired by Peter Attia’s structured style.
It conducts adaptive intake conversations across domains like sleep, nutrition, lifestyle, medical history, and more.
The system can run both as a **web-based chat UI** and as a **CLI tool** for quick terminal-based interaction.

---

## Quick Start

### 1. Setup

1. **Download curated questions**
   Download the `questions.json` file containing curated intake questions and place it at:

   ```
   data/health_questions.fr.json
   ```

2. **Environment variables**
   Create a `.env` file with either:

   * **OpenAI**

     ```
     OPENAI_API_KEY=your-openai-api-key
     ```

   * **Azure OpenAI**

     ```
     AZURE_OPENAI_API_KEY=your-azure-api-key
     AZURE_OPENAI_ENDPOINT=your-azure-endpoint
     ```

---

### 2. Run the app (Chat UI)

Build and start the app with Docker Compose:

```bash
docker-compose up --build
```

Then access the app at [http://localhost:8000](http://localhost:8000)

---

### 3. Run the CLI

To run the chat interface directly in your terminal:

1. Make sure the backend services are running:

   ```bash
   docker-compose up
   ```

2. Install [uv](https://github.com/astral-sh/uv) (a fast Python package manager).

3. Sync dependencies:

   ```bash
   uv sync
   ```

4. Launch the CLI chat:

   ```bash
   lattia
   ```

This will start the interactive intake interview directly in your terminal.

## Project Layout

The project is organized as follows:

```
src/lattia/
│
├── core/
│   ├── agent/         # Agent code: prompts, agent loop, schemas, interview logic
│   ├── parsers/       # Parsers for curated question files (knowledge base JSON)
│   ├── pii/           # PII redaction module
│   ├── utils/         # General utilities
│   └── vector_db/     # Vector DB client code (Qdrant): embeddings, ingestion, retriever
│
├── chat.py            # CLI entry point for running the chat interface
│
├── static/            # Frontend assets (HTML, CSS, JavaScript)
│   ├── app.py         # FastAPI application entry point
│   ├── db.py          # Database setup: engine, session, declarative base
│   ├── models.py      # SQLAlchemy models (database tables)
│   ├── schemas.py     # Pydantic models (FastAPI input/output schemas)
│   └── warmup.py      # Warm-up tasks when starting the server (models, caches, etc.)
```

This structure separates the **agent logic**, **data access**, **frontend**, and **infrastructure code**, making the project modular and easier to extend.


# TODO
- [x] Build the Home page, Chat UI, and Dashboard overlay
- [x] Implement the FastAPI backend and DB
- [x] Add PII redaction
- [x] Add rate bucket limiting
- [x] Create a CLI chat client for development
- [x] Implement the main agent loop with the data models
- [x] Ensure the Attia-style of the conversation
- [x] Decide when you have enough data on every category, and when to stop the interview
- [ ] Find a good first question strategy
- [x] Add RAG over provided questions to suggest next questions
- [ ] Implement the post-interview flow
- [x] Check FHIR standards, understand what a FHIR-lite JSON format should look like
- [ ] Consider GDPR compliance
- [ ] Add proper README documentation with design decisions
- [ ] Ensure people can run it smoothly
- [ ] Film Loom video walkthrough


## Credits
- [GLiNER PII](https://huggingface.co/urchade/gliner_multi_pii-v1) - for the PII redaction model
- [GPT-6 Preview](https://www.youtube.com/watch?v=xvFZjo5PgG0) - for helping me vibe code the Frontend
