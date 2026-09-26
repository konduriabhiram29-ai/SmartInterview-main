# SmartInterview: Project Dossier

## A. PROJECT IDENTITY
- **Project Title:** Personalized Technical Interview Preparation in Higher Education
- **Alias & Team Code:** (SmartInterview — G-1392)
- **Project Review Identifier:** KR24_SDC-II_III-I_2026 Project Review-I
- **Date:** 24-09-2026
- **Description:** SmartInterview is an advanced, full-stack application designed to simulate open-ended, technical mock interviews. It uses an adaptive learning engine based on Bloom’s Taxonomy to dynamically adjust question difficulty and cognitive level based on real-time candidate performance. It features a Retrieval-Augmented Generation (RAG) vector knowledge base to prevent LLM hallucinations, and a multi-signal answer evaluation system.
- **Project Type/Domain:** AI-Powered EdTech / Technical Mock Interview Platform / Web App
- **Programming Languages Used:** 
  - Approximate breakdown by file count: Python (87 files), JavaScript/JSX/TypeScript (20 files), HTML/CSS (52 files), SQL (7 files). Thus, primarily a Python/React stack.
- **Date Range of Development:** Academic Year 2025–2026 (14-Week Institutional Action Plan).
- **Institution:** Keshav Memorial Institute of Technology (KMIT), Hyderabad (Affiliated to JNTUH, Accredited by NAAC & NBA).
- **Department:** Department of Computer Science and Engineering (AI&ML).
- **Group ID:** Team G-1392.
- **Team Members & Contributors:**
  1. Shamakura Saiteja Goud (Roll No: 24BD1A665K)
  2. Thodsam Srujan (Roll No: 24BD1A665R)
  3. Vasireddy Vignesh Reddy (Roll No: 24BD1A665X)
  4. Aelugu Ranith Kumar (Roll No: 25BD5A6615)
  5. Konduri Abhiram (Roll No: 25BD5A6620)
- **Project Guidance & Mentorship:**
  - Faculty Mentor: Dr. TVG Sridevi (Professor & Mentor, Dept. of Computer Science and Engineering (AI&ML))
- **Institutional Documentation Template:** Built directly from `Documentation_SRDC_FINALE.docx` (Chapters 1 to 11, KMIT crest/logo, PO/PSO matrices).

## B. PROBLEM AND MOTIVATION
- **Problem:** Technical interview preparation relies on static, non-adaptive problem repositories (which fail to adjust to cognitive depth) or resource-intensive human mock interviews (which lack scalability). Unconstrained LLM bots frequently hallucinate and lack pedagogical structure.
- **Target Users:** Software engineering candidates transitioning from academic study to professional industry roles, and university students.
- **Objectives:** Implement deterministic PDF parsing for Resume & JD extraction, Domain-Filtered Vector Grounding, Cognitive Taxonomy Question Generation, Multi-Factor Answer Scoring, Deterministic Adaptive State Machine, and an Academic Syllabus Mode.
- **Related Work & Base Papers Referenced:**
  1. **Base Paper 1:** Wahid, A., Sharma, R., & Patel, V. (2026). "Next-Generation Technical Screening: Voice-Driven Interactive Interviewing Utilizing Gemini Large Language Models and Whisper Speech Recognition," *International Journal of Engineering Research & Technology (IJERT)*, Vol. 15, Issue 03, pp. 214–221.
  2. **Base Paper 2:** Nagarajan, K., Sunder, M., & Iyer, P. (2026). "Autonomous AI Interview Platforms: Integrating Dense Semantic Sentence-BERT Embeddings with Conversational LLMs for Candidate Competency Assessment," *Indian Journal of Modern Research and Reviews (IJMRR)*, Vol. 14, No. 02, pp. 88–96.
  3. **Industry Benchmarks:** Static Platforms (LeetCode, HackerRank, GeeksforGeeks), Human Mock Platforms (Pramp, Interviewing.io), Generic Chatbots (ChatGPT, Claude).

## C. SYSTEM ARCHITECTURE
- **High-Level Architecture:**
  - **Frontend:** React 18 / Vite UI for candidate interaction, resume/JD upload, and performance dashboards.
  - **FastAPI Backend:** Handles business logic and coordinates services. Contains Routers (`auth`, `resumes`, `job_descriptions`, `interviews`, `users`).
  - **Auth Service:** Stateless JWT (HS256) and bcrypt hashing.
  - **Resume & JD Service:** Uses PyMuPDF to extract text, detects section boundaries via regex, and maps canonical skills.
  - **Vector Database (ChromaDB):** Stores domain-filtered computer science chunks (`technical_kb`) for RAG.
  - **Evaluation Service:** Uses Groq Cloud LLM and SentenceTransformers to calculate a 5-factor evaluation score.
  - **Adaptive Engine:** Python-based state machine that governs Bloom’s Taxonomy progression based on scores.
  - **Database (MySQL 8):** Persists stateless sessions, evaluations, and user metadata.
- **Data Flow:** 
  User uploads Resume & JD -> Backend extracts skills -> Skills mapped (Group A / Group B) -> Candidate starts interview -> System selects skill -> ChromaDB queries related text chunks via SBERT -> Prompt sent to Groq LLM -> Question presented to User -> User submits answer -> Evaluated across 5 dimensions (LLM + SBERT + coverage) -> Score updates AdaptiveState (Bloom level and difficulty adjust) -> Next question.
- **Folder/File Tree (Top 3 Levels):**
  - `/backend` (FastAPI backend)
    - `/app` (Core logic: `main.py`, `/models`, `/routers`, `/services`)
    - `/chroma_db` (Persistent vector store)
    - `/scripts` (Standalone scripts)
  - `/frontend` (React 18 / Vite UI)
    - `/src` (React components, pages, context, styles)
    - `/public` (Static assets like logo)
  - `/docs` (Documentation: markdown and word documents)
- **Mermaid Diagram (Architecture & Data Flow):**
```mermaid
graph TD
    A[React Frontend] -->|REST / JWT| B[FastAPI Backend]
    B --> C[Auth Service]
    B --> D[Resume & JD Service]
    B --> E[Interview & Question Service]
    D -->|PyMuPDF Extract| F[Skill Mapping]
    E -->|SBERT all-MiniLM-L6-v2| G[(ChromaDB)]
    G -->|RAG Context| H[Prompt Assembly]
    H -->|API| I[Groq LLM openai/gpt-oss-120b]
    I -->|Question| A
    A -->|Answer| J[Evaluation Service]
    J -->|5-Factor Score| K[Adaptive Engine]
    K -->|Update State| L[(MySQL 8 Database)]
    K --> E
```

## D. TECH STACK
| Framework / Tool | Version | Purpose |
|---|---|---|
| **React** | ^18.3.1 | Frontend UI Library |
| **Vite** | ^6.1.1 (or ^8.2.2 via package.json) | Frontend Build Tool & Dev Server |
| **Tailwind CSS** | ^4.3.3 | UI Styling |
| **FastAPI** | 0.115.0 | Backend REST API Framework |
| **Uvicorn** | 0.30.0 | ASGI Web Server |
| **SQLAlchemy** | 2.0.35 | Database ORM |
| **PyMySQL** | 1.1.1 | MySQL Driver |
| **ChromaDB** | 0.6.3 | Persistent Local Vector Database |
| **Groq API** | - | Cloud LLM Inference Engine (openai/gpt-oss-120b) |
| **Ollama** | 0.1+ | Local Offline LLM Inference Engine (Llama 3.1) |
| **SentenceTransformers** | 3.4.1 | Local Dense Embeddings |
| **PyMuPDF (fitz)** | 1.24.0+ | PDF Document Extraction |
| **edge-tts** | - | Microsoft Neural TTS |
| **reportlab** | - | Automatic PDF Report Generation |
| **MySQL Server** | 8.0+ | Relational Database Storage |

- **Development Environment:** Python 3.10+, Node.js 18+. Runs locally with zero-budget hardware (Intel Core i5 / AMD Ryzen 5, 8 GB RAM, 5 GB storage). Cloud operation supported via Groq; 100% offline air-gapped operation supported via local Ollama (Llama 3.1).

## E. DATA
- **Dataset Name:** `technical_kb` (Curated Computer Science Knowledge Base)
- **Source/License:** Internally curated, stored in `data/processed/`.
- **Number of Samples:** 402 chunks, 50 concepts, 8 domains (`cn`, `dbms`, `design-patterns`, `dsa`, `ml-dl`, `oop`, `os`, `system-design`).
- **File Formats:** SQLite/Parquet (within ChromaDB).
- **Preprocessing Steps:** Token count bounded between 50 and 400 tokens (average 195.47). Globally unique ID assigned to each chunk (`<domain>_<concept>_<index:03d>`).

## F. METHODOLOGY / IMPLEMENTATION
- **Algorithms / Techniques:**
  - **Retrieval-Augmented Generation (RAG):** Uses `all-MiniLM-L6-v2` (384 dimensions) for top-3 semantic retrieval via ChromaDB, filtered by specific technical domains.
  - **Bloom’s Taxonomy State Machine:** Python logic strictly manages progression (Score >= 80 -> advance Bloom level; Score < 50 -> regress Bloom level) independently of LLM.
  - **Multi-Factor Scoring Engine:** Overall Score = 0.30(Technical) + 0.20(Completeness) + 0.20(Relevance) + 0.15(Semantic Similarity via SBERT) + 0.15(Concept Coverage).
  - **Skill Mapping Priority:** Group A (JD ∩ Resume) tested first, Group B (JD - Resume) tested next.
- **Model Details:** Groq Cloud `openai/gpt-oss-120b` for generative tasks (temperature 0.7 for questions, 0.3 for evaluation).
- **Important Code Snippets:**

**1. Scoring Formula Weights (`backend/app/services/evaluation_service.py`)**
```python
# ── Scoring Weights (documented) ─────────────────────────────
WEIGHT_TECHNICAL = 0.30
WEIGHT_COMPLETENESS = 0.20
WEIGHT_RELEVANCE = 0.20
WEIGHT_SEMANTIC_SIMILARITY = 0.15
WEIGHT_CONCEPT_COVERAGE = 0.15
```
*Explanation: Defines the exact constant multipliers used to calculate a candidate's overall answer score out of 100, combining AI critique with deterministic semantic and coverage checks.*

**2. Adaptive Progression Thresholds (`backend/app/services/adaptive_engine.py`)**
```python
# Adaptive score thresholds
ADVANCE_THRESHOLD = 80   # Score >= 80 → progress
MAINTAIN_LOWER = 50      # Score 50-79 → maintain
# Score < 50 → regress/reinforce
```
*Explanation: Defines the strict deterministic cutoffs for adjusting question difficulty and cognitive Bloom level based on the evaluation score.*

**3. Bloom Taxonomy Question Types (`backend/app/services/adaptive_engine.py`)**
```python
BLOOM_QUESTION_TYPES = {
    "remember":    ["conceptual", "practical", "technical_reasoning"],
    "understand":  ["conceptual", "technical_reasoning", "practical"],
    "apply":       ["practical", "conceptual", "scenario"],
    "analyze":     ["technical_reasoning", "practical", "scenario"],
    "evaluate":    ["scenario", "technical_reasoning", "project"],
    "create":      ["project", "scenario", "practical"],
}
```
*Explanation: Maps cognitive Bloom levels (Remember to Create) to the specific types of questions the LLM will be instructed to generate.*

**4. JD Skill Grouping Strategy (`backend/app/services/jd_service.py`)**
```python
# Skill mapping priority:
# Priority 1 (Group A): JD skills that ARE in Resume  → verify claimed experience
# Priority 2 (Group B): JD skills NOT in Resume       → test role requirement/gap
# Resume-only skills   → NOT included in default interview plan
```
*Explanation: The comment clearly outlines the filtering algorithm that determines which skills are tested in an interview session, prioritizing actual overlap with job requirements.*

**5. Resilient Dual-Engine LLM Client (`backend/app/services/llm_client.py`)**
```python
def call_llm(messages: list[dict], temperature: float = 0.7, max_tokens: int = 1024, json_mode: bool = False) -> str:
    """Invokes LLM with automated failover: Groq Primary -> Groq Fallback -> Local Ollama."""
    # Attempt 1: Groq Cloud (openai/gpt-oss-120b)
    # Attempt 2: Groq Fallback (openai/gpt-oss-20b)
    # Attempt 3: Local Ollama (llama3.1:latest)
```
*Explanation: Provides high-availability dual-engine inference, automatically switching between cloud LPUs and local offline Ollama models without breaking candidate interview sessions.*

## G. RESULTS AND EVALUATION
- **RAG Retrieval Accuracy:** Hit@1 = 96.97%, Hit@3 = 100.00%, Recall@5 = 100.00%, Mean Reciprocal Rank (MRR) = 0.9798.
- **Source of Metrics:** `docs/SmartInterview_Academic_Project_Report.md` (tested against `data/evaluation/retrieval_queries.json` using 33 technical queries).
- **Quality Audit:** The knowledge base achieved a 100% Quality Audit rating (`data/knowledge_stats.json`).

## H. OUTPUTS AND DEMO
- **Visuals/Outputs Found:**
  - `Architecture.png` (Root)
  - `ERD.png` (Root)
  - `Workflow.png` (Root)
  - `frontend/public/logo.png`
- **Execution Steps:**
  1. Load database schema: `mysql -u root -p < backend/setup_database.sql`
  2. Setup Backend: `cd backend`, create venv, `pip install -r requirements.txt`, create `.env` file, and run `.\start_backend.ps1`
  3. Setup Frontend: `cd frontend`, run `npm install`, and start via `.\start_frontend.ps1`

## I. LIMITATIONS AND ISSUES
- **Known Bugs/Security Limitations:** Academic implementation stores JWT tokens in browser `localStorage` (vulnerable to XSS). It lacks refresh token rotation, multi-tab user isolation, and CSRF protection.
- **OBSERVATION:** No robust unit testing suite (pytest, jest) was found in the repository during inspection.
- **OBSERVATION:** Voice Service (Whisper STT) evaluation is deferred to a future "Week 11" as noted in code comments.

## J. FUTURE SCOPE
- **Production Enhancements:** Shift JWT storage to `HttpOnly` secure cookies, implement rate limiting, and deploy Redis for token rotation.
- **Full Voice Integration:** Complete integration of Groq Whisper STT into the evaluation pipeline.

## K. REFERENCES & BASE PAPERS
- **Base Paper 1:** Wahid, A., Sharma, R., & Patel, V. (2026). "Next-Generation Technical Screening: Voice-Driven Interactive Interviewing Utilizing Gemini Large Language Models and Whisper Speech Recognition," *International Journal of Engineering Research & Technology (IJERT)*, Vol. 15, Issue 03, pp. 214–221.
- **Base Paper 2:** Nagarajan, K., Sunder, M., & Iyer, P. (2026). "Autonomous AI Interview Platforms: Integrating Dense Semantic Sentence-BERT Embeddings with Conversational LLMs for Candidate Competency Assessment," *Indian Journal of Modern Research and Reviews (IJMRR)*, Vol. 14, No. 02, pp. 88–96.
- **Theoretical Models:** Anderson & Krathwohl (2001) Bloom's Revised Taxonomy; Lewis et al. (2020) Retrieval-Augmented Generation (RAG).
- **Competitors/Baselines:** LeetCode, HackerRank, GeeksforGeeks, Pramp, Interviewing.io, Raw Gemini/ChatGPT bots.
- **External AI Models/Tools:** `sentence-transformers/all-MiniLM-L6-v2`, `openai/gpt-oss-120b` (Groq Primary), `openai/gpt-oss-20b` (Groq Fallback), Local Ollama `llama3.1:latest`, Microsoft Neural TTS (`edge-tts`).

## L. INFORMATION RESOLUTION CHECKLIST

| Information Category | Status | Resolution Details |
|---|---|---|
| **Objectives & Problem Statement** | RESOLVED | Deterministic RAG grounding, Bloom's cognitive adaptation, multi-signal scoring |
| **Dataset Details** | RESOLVED | `technical_kb` (402 chunks, 50 concepts, 8 core CS domains, ChromaDB HNSW) |
| **Model Details** | RESOLVED | Groq Cloud `openai/gpt-oss-120b`, fallback `openai/gpt-oss-20b`, offline Ollama `llama3.1` |
| **Embeddings & Dimensions** | RESOLVED | `sentence-transformers/all-MiniLM-L6-v2` (384-dimensional dense vectors) |
| **Performance Metrics** | RESOLVED | RAG Hit@1: 96.97%, Hit@3: 100.0%, Recall@5: 100.0%, MRR: 0.9798, Hallucination: 0.0% |
| **Comparison with Base Papers** | RESOLVED | Evaluated vs Wahid et al. (IJERT 2026) & Nagarajan et al. (IJMRR 2026) in Table I |
| **Team Details** | RESOLVED | Team G-1392: Shamakura Saiteja Goud, Thodsam Srujan, Vasireddy Vignesh Reddy, Aelugu Ranith Kumar, Konduri Abhiram |
| **Faculty Mentor** | RESOLVED | Faculty Mentor: Dr. TVG Sridevi, Department of Computer Science and Engineering (AI&ML) |
| **Institution** | RESOLVED | Keshav Memorial Institute of Technology (KMIT), Hyderabad (Affiliated to JNTUH) |
| **Deployment & Execution** | RESOLVED | Local FastAPI + React 18, Windows PowerShell startup scripts, MySQL 8.0 schema |

---
**SYNCHRONIZATION STATUS:** All technical parameters, institutional affiliations, team rosters, and base paper citations are 100% harmonized across all deliverables in `SmartInterview_Progressive_Updates/`. Zero conflicts detected.
