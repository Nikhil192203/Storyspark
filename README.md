# StorySpark ✨

> **Kids find science and maths boring but never get tired of stories.**  
> *StorySpark transforms difficult school concepts into age-tailored, engaging stories that children love to learn—and gives parents and teachers verified comprehension feedback.*

Built for the **8-Hour AI Hackathon**.

---

## 🏗️ Architecture Chosen

For an intensive 8-hour hackathon, we chose a **minimal, robust, and lightning-fast architecture** with zero build-tooling friction:

1. **Backend Server: Python 3.11 + FastAPI + Uvicorn**
   - **Why**: Asynchronous, ultra-lightweight, built-in OpenAPI docs, and enterprise-grade request validation via Pydantic.
   - **Security**: The backend acts as a secure reverse proxy for Google Gemini. `GEMINI_API_KEY` is loaded from `.env` and remains exclusively on the server—never leaked to the client browser.
   - **Prepared for Gemini 3.8 Flash**: Clean service boundary (`app/services/gemini_service.py`) structured for server-side Google GenAI calls in Phase 2.

2. **Frontend Shell: Semantic HTML5 + Modern Accessible CSS + Vanilla JS**
   - **Why**: No heavy npm/webpack/vite build step to break or delay progress. Loads instantaneously.
   - **Accessibility (a11y)**: Built according to WCAG 2.1 AA/AAA standards:
     - Full keyboard navigation (skip links, tab order, distinct `:focus-visible` rings).
     - Semantic HTML (`header`, `main`, `section`, `form`, `fieldset`, `legend`, `label`, `output`, `footer`).
     - Screen-reader friendly ARIA live regions (`aria-live="polite"`, `role="alert"`, `aria-describedby`, `aria-invalid`).
     - High color contrast and `prefers-reduced-motion` support.
   - **Responsive**: Fluid mobile, tablet, and desktop layouts.

3. **Validation & Pedagogy**:
   - Double-layer validation (instant client-side feedback + strict server-side Pydantic validation).
   - Developmental age bands (Ages 4–14) with dynamic pedagogy insights:
     - **Ages 4–6 (Early Explorer)**: Playful metaphors, sensory descriptions, simple rhythm.
     - **Ages 7–9 (Curious Adventurer)**: Quests, relatable dialogue, tangible cause-and-effect science.
     - **Ages 10–12 (Bold Discoverer)**: Mechanism exploration, narrative stakes, mathematical reasoning.
     - **Ages 13–14 (Young Innovator)**: Systemic thinking, nuance, real-world application.

4. **Testing**:
   - `pytest` + `httpx` (`TestClient`) testing boundary conditions, age ranges, empty/whitespace inputs, security properties, and route compliance.

---

## 📁 Project Structure

```
story spark project/
├── .env.example              # Environment variables template
├── .gitignore                # Git ignore patterns
├── README.md                 # Project documentation & guide
├── requirements.txt          # Minimal Python dependencies
├── app/
│   ├── __init__.py           # Application package
│   ├── config.py             # Secure configuration & .env loader
│   ├── main.py               # FastAPI entrypoint & static mount
│   ├── schemas.py            # Pydantic schemas & age-tier pedagogy
│   ├── api/
│   │   ├── __init__.py
│   │   └── routes.py         # Health, input validation, generation stub
│   ├── services/
│   │   ├── __init__.py
│   │   └── gemini_service.py # Gemini service architecture boundary
│   └── static/
│       ├── index.html        # Semantic HTML5 accessible landing page
│       ├── css/
│       │   └── style.css     # Accessible, responsive design system
│       └── js/
│           └── app.js        # Form validation, live guidance, loading state
└── tests/
    ├── __init__.py
    └── test_validation.py    # 20 comprehensive unit & integration tests
```

---

## 🚀 How to Run the Application Locally

### 1. Environment Setup

If running with standard Python 3.11 virtual environment:
```bash
python -m venv .venv
.venv\Scripts\activate       # On Windows
# source .venv/bin/activate  # On macOS/Linux

pip install -r requirements.txt
```

*(Or using `uv`):*
```bash
uv venv
uv pip install -r requirements.txt
```

### 2. Configure Environment Variables
Copy the template file to `.env`:
```bash
copy .env.example .env
```
Add your Google Gemini API key to `.env`:
```env
GEMINI_API_KEY=your_actual_gemini_api_key_here
PORT=8000
ENVIRONMENT=development
```

### 3. Start the Server
```bash
.venv\Scripts\python -m uvicorn app.main:app --reload --port 8000
```
Open your browser and navigate to:
👉 **[http://localhost:8000](http://localhost:8000)**

API Documentation (Swagger UI):
👉 **[http://localhost:8000/docs](http://localhost:8000/docs)**

---

## 🧪 Running the Tests

To run the complete automated test suite:
```bash
.venv\Scripts\python -m pytest -v
```

All 20 test cases verify:
- ✅ Health endpoint security (verifies `GEMINI_API_KEY` is never exposed).
- ✅ Valid school concepts across all four developmental age tiers.
- ✅ Rejection of empty, whitespace-only, too short, too long, and non-alphanumeric topics.
- ✅ Rejection of invalid age values (< 4, > 14, negative, non-integer).
- ✅ Missing payload fields.
- ✅ Compliance with Phase 1 constraints (no fake AI responses).
- ✅ HTML landing page delivery.

---

## 🛣️ Remaining Work (For Upcoming Phases)

In accordance with Phase 1 hackathon guidelines, the following are deliberately deferred to subsequent phases:
1. **Gemini 3.8 Flash Story Generation**:
   - Connecting `gemini_service.py` to the live Google GenAI API.
   - Structured educational prompt engineering based on the validated age tier.
2. **Interactive Comprehension Assessment**:
   - 3-question adaptive quiz checking whether the child understood the concept.
3. **Understanding Scoring & Diagnostics**:
   - Immediate score calculation highlighting mastered and misunderstood concepts.
4. **Parent/Teacher Learning Report**:
   - Curriculum concept breakdown, child's strengths, and recommended follow-up questions.
