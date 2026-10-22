# Flight Search AI Agent

An **Agentic AI** mini-project that finds flights from a natural-language request, filters by budget, selects the cheapest options, and generates an email — with optional human approval before sending.

Designed for a college **Agentic AI Jury Examination**. It runs in the **terminal** and in a **Streamlit web UI**, with **Demo Mode** when no API keys are configured.

## Problem Statement

A user types a request such as:

> Find me the cheapest flight from Pune to Singapore under ₹30,000 and email me the top 3 options.

The system understands the request, plans the work, searches flights, decides which options fit the budget, asks a human to approve the recommendations, and then generates (or simulates) an email.

## Features

- Natural language flight request
- Multi-agent workflow (parser, planner, search, analysis, email)
- LangGraph orchestration
- Flight Search Tool (mock data in Demo Mode)
- Flight analysis (budget filter, sort, top N)
- **Short-Term Conversational Memory — Unit III**
- **Human-in-the-Loop Approval — Unit IV**
- Email generation (optional real SMTP)
- Demo / Offline mode (no OpenAI key required)
- Terminal interface (`main.py`)
- Streamlit web interface (`app.py`)

## Agent Architecture

```text
START
  ↓
Request Parser
  ↓
Short-Term Memory (Unit III)
  ↓
Planning Agent
  ↓
Flight Search Agent
  ↓
Flight Analysis Agent
  ↓
Human Approval (Unit IV)
  ↓
Email Agent
  ↓
END
```

## Project Structure

| File | Purpose |
| --- | --- |
| `app.py` | Streamlit web UI with workflow progress, approval, and memory panel |
| `main.py` | Terminal app with multi-turn memory and interactive approval |
| `agents.py` | Agent nodes: parse, memory, plan, search, analyze, approval, email |
| `memory.py` | Session short-term memory (Unit III) |
| `workflow.py` | LangGraph `StateGraph` and compiled graphs |
| `tools.py` | Flight Search Tool and Email Tool |
| `data.py` | Mock flight inventory |
| `tests/test_demo.py` | Runnable demo test script |
| `requirements.txt` | Python dependencies |
| `.env.example` | Optional OpenAI / SMTP settings |

## Installation

```bash
cd flight-search-ai-agent
pip install -r requirements.txt
```

Optional: copy `.env.example` to `.env` for LLM parsing or real email.

```bash
copy .env.example .env
```

On Windows, if `pip install streamlit` fails with a long-path error, enable [Windows long paths](https://pip.pypa.io/warnings/enable-long-paths) or install in a shorter directory path.

## Running Terminal Version

```bash
python main.py
```

After the first search, try a follow-up without repeating cities:

```text
Show me only the cheapest one.
```

## Running Web Version

```bash
streamlit run app.py
```

## Example Request

```text
Find me the cheapest flight from Pune to Singapore under ₹30,000 and email me the top 3 options.
```

## Demo Mode

If `OPENAI_API_KEY` is missing:

- Rule-based (regex) request parsing — **not** an LLM
- Mock flights from `data.py`
- Simulated email (no SMTP required)

The UI shows **Mode: Demo / Offline** in this case.

## Unit III — Short-Term Memory

Session memory stores source, destination, budget, top N, and last results. The **Conversation Memory** section in the web UI shows the current snapshot. Follow-up messages like “Show me only the cheapest one” reuse the previous route and budget.

## Unit IV — Human-in-the-Loop

After analysis, the agent shows its top picks and waits for **Approve & Generate Email** or **Reject**. Email is generated only after approval. Rejecting leaves the app running so you can search again.

## Tests

```bash
python tests/test_demo.py
```

Covers normal search, memory follow-up, rejection (no email), and demo parsing without an API key.

## Future Improvements

- Real flight API integration
- Persistent long-term memory (if required by a later unit)
- Richer Streamlit styling
