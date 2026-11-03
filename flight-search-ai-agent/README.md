# Flight Search AI Agent

Find flights through a conversation instead of filling out a long search form.

This project is an Agentic AI flight-search assistant built with **Python, LangGraph, and Streamlit**. You describe the trip in everyday language, and a workflow of focused agents extracts the details, plans the search, compares available options, and prepares an email with the recommendations.

**Try the app:** https://flight-search-ai-agents.onrender.com/

> **A note about flight data:** the current version uses a route-aware mock flight dataset for demonstrations. It does not fetch live schedules, availability, or ticket prices from airline or booking APIs.

---

## What it can do

- Understand requests such as: `Find the cheapest flight from Pune to Singapore under ₹30,000`.
- Extract the route, budget, result count, nonstop preference, and fastest/cheapest sorting preference.
- Search a generated set of flight options and show the full list before narrowing it down.
- Filter by budget, sort by price or duration, and select the requested number of options.
- Remember details from earlier turns, so a follow-up like `Show me only the cheapest one` can use the previous search.
- Ask for human approval before generating the email.
- Let you review and edit the email draft before sending.
- Run in Demo Mode without an OpenAI key, using rule-based parsing and simulated email delivery.
- Offer both a Streamlit interface and a terminal interface.

## A quick example

You could start with:

```text
Find me the cheapest flight from Pune to Singapore under ₹30,000
and email me the top 3 options.
```

The workflow extracts the trip details, searches the demo inventory, filters and ranks the matches, and presents the results. You can then refine the search naturally:

```text
Show me only the cheapest one.
```

The conversation memory carries forward the route and other relevant search context.

---

## How the agents work together

The project uses **LangGraph** to coordinate the workflow. Each node has a focused responsibility, and the shared state carries information from one step to the next.

```text
User request
     |
     v
Request Parser
     |
     v
Short-Term Memory
     |
     v
Planning Agent
     |
     v
Flight Search Agent  ---> Flight Search Tool
     |
     v
Flight Analysis Agent
     |
     v
Human Approval
     |
     v
Email Agent  ----------> Email Tool
     |
     v
Result
```

### Agent responsibilities

| Component | Responsibility |
| --- | --- |
| Request Parser | Extracts source, destination, budget, sorting preference, stop preference, and number of results. |
| Memory step | Reuses context from earlier messages when a request is a follow-up. |
| Planning Agent | Builds an execution plan from the parsed travel requirements. |
| Flight Search Agent | Calls the flight-search tool and collects the available demo options. |
| Flight Analysis Agent | Applies filters and ranks flights by price or duration. |
| Human Approval | Waits for the user to approve or reject the recommendations. |
| Email Agent | Prepares the email after approval and sends it when SMTP is configured. |

The Streamlit app separates searching from approval so the user can inspect the results before choosing an action. The terminal flow supports an interactive approval step.

## Features in more detail

### Conversational memory

The app keeps short-term session context such as the previous route, budget, sorting preference, and selected flights. This makes follow-up requests feel more natural. In the web app, memory is held in Streamlit session state; LangGraph receives a snapshot during each run.

### Human-in-the-loop approval

Recommendations are not emailed automatically. The user gets a chance to review the selected flights and approve or reject the action. The email draft can be edited before it is sent.

### Demo and offline mode

When `OPENAI_API_KEY` is not configured, the parser uses rule-based extraction and the app uses its local mock flight data. Email delivery is simulated unless SMTP credentials are configured.

### Web interface

The Streamlit interface includes search controls, an agent activity timeline, flight results, a price chart, memory information, and download options for selected flights and the email text.

---

## Tech stack

| Technology | Used for |
| --- | --- |
| Python | Application and agent logic |
| LangGraph | Agent workflow and state orchestration |
| OpenAI API | Optional natural-language extraction |
| Streamlit | Interactive web application |
| SMTP | Optional email delivery |
| GitHub Actions | Test workflow / CI |
| Render | Web deployment |

---

## Project structure

The application lives in the `flight-search-ai-agent/` directory.

```text
Flight-search-AI-agents/
├── .github/
│   └── workflows/
│       └── ci-cd.yml
├── flight-search-ai-agent/
│   ├── app.py             # Streamlit web application
│   ├── main.py            # Terminal application
│   ├── agents.py          # Parser, planner, search, analysis and email nodes
│   ├── workflow.py        # LangGraph StateGraph definitions
│   ├── memory.py          # Short-term conversational memory
│   ├── tools.py           # Flight-search and email tools
│   ├── data.py            # Route-aware mock flight inventory
│   ├── ui_theme.py        # Streamlit theme and styling
│   ├── ui_common.py       # Shared UI helpers
│   ├── tests/
│   │   └── test_demo.py   # Demo workflow checks
│   ├── assets/            # App visual assets
│   ├── requirements.txt
│   └── .env.example
└── render.yaml            # Render service configuration
```

---

## Run it locally

### 1. Clone the repository

```bash
git clone https://github.com/AtharvaJadhav1/Flight-search-AI-agents.git
cd Flight-search-AI-agents/flight-search-ai-agent
```

### 2. Create and activate a virtual environment

**Windows PowerShell**

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
```

**macOS / Linux**

```bash
python3.11 -m venv .venv
source .venv/bin/activate
```

### 3. Install dependencies

```bash
python -m pip install --upgrade pip
pip install -r requirements.txt
```

### 4. Configure environment variables (optional)

Copy the example file and add credentials only for the integrations you plan to use.

**Windows PowerShell**

```powershell
Copy-Item .env.example .env
```

**macOS / Linux**

```bash
cp .env.example .env
```

Available variables:

| Variable | Purpose |
| --- | --- |
| `OPENAI_API_KEY` | Optional key for LLM-based request parsing. |
| `SMTP_EMAIL` | Sender email address for real email delivery. |
| `SMTP_PASSWORD` | SMTP app password or provider credential. |
| `SMTP_HOST` | SMTP server hostname. |
| `SMTP_PORT` | SMTP server port (default example: `587`). |

Keep your real `.env` file private. Never commit API keys, email passwords, or other credentials to GitHub.

### 5. Start the web app

```bash
streamlit run app.py
```

Streamlit will print a local URL in your terminal, usually:

```text
http://localhost:8501
```

### Or run the terminal version

```bash
python main.py
```

---

## Try these prompts

```text
Find flights from Pune to Singapore under ₹30,000.
```

```text
Show me the top 5 options by price.
```

```text
Find the fastest flights from Mumbai to Dubai.
```

```text
Only show nonstop flights from Delhi to Bengaluru.
```

```text
Show me just the cheapest option from my previous search.
```

The parser supports common budget formats such as `30k`, `₹25,000`, and `1.5 lakh`.

---

## Run the tests

From the `flight-search-ai-agent/` directory:

```bash
python tests/test_demo.py
```

The demo checks cover the main workflow paths, including search, memory-based follow-ups, and approval/rejection behavior.

---

## Deployment

The repository includes a Render Blueprint in `render.yaml` and a GitHub Actions workflow in `.github/workflows/ci-cd.yml`.

The Render configuration uses:

- **Root directory:** `flight-search-ai-agent`
- **Build command:** `pip install -r requirements.txt`
- **Start command:** Streamlit bound to Render's `$PORT`
- **Runtime:** Python 3.11

To deploy your own instance, connect the repository in Render and configure the optional environment variables in the Render dashboard. Do not put secrets in `render.yaml` or commit them to the repository.

---

## Current limitations

- Flight schedules, fares, and airline options come from mock data. They are not live booking results.
- The project does not book or ticket flights.
- Email delivery requires valid SMTP configuration; without it, sending is simulated.
- Conversational memory is short-term session memory, not persistent long-term user memory.
- Parsing without an OpenAI API key is rule-based and may not understand every way of phrasing a request.

## Ideas for the next version

- Connect a live flight data provider.
- Add travel dates, passenger counts, cabin class, and return trips.
- Add persistent conversation history.
- Compare baggage, refund rules, layovers, and total travel time from a real provider.
- Add more automated tests around parsing and edge cases.

---

## Why I built this

I wanted to explore what changes when a flight search is treated as a task for a group of collaborating agents rather than a single prompt-response interaction.

The interesting part was not just finding a few flight options. It was coordinating the steps, carrying context across follow-up messages, and keeping the user involved before an external action like sending an email.

This project helped me work hands-on with LangGraph, shared agent state, tool execution, conversational memory, and human-in-the-loop workflows.

## Feedback

Found an issue or have an idea for improving the project? Feel free to open a GitHub issue.
