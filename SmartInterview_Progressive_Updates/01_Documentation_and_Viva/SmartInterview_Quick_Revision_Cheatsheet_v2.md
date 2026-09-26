# SmartInterview: Master Quick-Revision Cheatsheet & Viva Defense Card

**Personalized Technical Interview Preparation in Higher Education Using Retrieval-Augmented Generation and Bloom's Taxonomy**  
*(SmartInterview — G-1392)*  
**Project Review Identifier:** KR24_SDC-II_III-I_2026 Project Review-I | **Date:** 24-09-2026  
**Document Classification**: Rapid Revision & Viva Defense Card  
**Academic Degree**: Bachelor of Technology (B.Tech) in Computer Science and Engineering (AI&ML)  
**Department**: Department of Computer Science and Engineering (AI&ML), Keshav Memorial Institute of Technology (KMIT)  
**Affiliation**: Jawaharlal Nehru Technological University Hyderabad (JNTUH)  
**Academic Year**: 2026 | **Project Team**: `Team G-1392`  
**Team Members**: Shamakura Saiteja Goud (`24BD1A665K`), Thodsam Srujan (`24BD1A665R`), Vasireddy Vignesh Reddy (`24BD1A665X`), Aelugu Ranith Kumar (`25BD5A6615`), Konduri Abhiram (`25BD5A6620`)  
**Faculty Mentor**: Dr. TVG Sridevi, Department of Computer Science and Engineering (AI&ML)  

---

## 1. THE 30-SECOND ELEVATOR PITCH (MEMORIZE VERBATIM)

> *"SmartInterview is an AI-powered, adaptive technical mock interview platform that prepares engineering students for high-stakes recruitment interviews. Traditional preparation relies on static question banks or ungrounded conversational AI bots that hallucinate and grade subjectively. SmartInterview solves this through a decoupled 4-tier architecture: it parses resumes and job descriptions using PyMuPDF to extract skill gaps; grounds technical questions in a curated 402-chunk knowledge base in ChromaDB using RAG; drives interview progression through a deterministic state machine based on Bloom's Revised Taxonomy; and evaluates answers via an objective 5-signal formula combining LLM technical reasoning with dense vector cosine similarity. With real-time neural voice interaction powered by Groq LPU and Microsoft Edge-TTS, the system runs with sub-second latency at zero infrastructure cost."*

---

## 2. MASTER SYSTEM NUMBERS & ARCHITECTURAL SPECS

| Metric / Dimension | Exact System Value | Why This Number Matters |
| :--- | :--- | :--- |
| **Knowledge Base Chunks** | **402 Chunks** | Curated across 8 computer science domains in ChromaDB (`technical_kb`). |
| **Technical Domains** | **8 Domains** | `cn` (33), `dbms` (45), `design-patterns` (105), `dsa` (63), `ml-dl` (35), `oop` (33), `os` (35), `system-design` (53) — 50 concepts, 402 chunks. |
| **Embedding Dimensions** | **384 Dimensions** | Produced by `sentence-transformers/all-MiniLM-L6-v2` locally on CPU. |
| **Embedding Parameters** | **22.7 Million** | Lightweight enough to vectorize sentences in under 15ms on commodity hardware. |
| **Inference Generation** | **>500 tokens/sec** | Groq Cloud LPU running Tensor Streaming Processors (TSP). |
| **Time-to-First-Token** | **<180 ms** | Delivers instantaneous conversational speech cadence during interviews. |
| **Cognitive Levels** | **6 Bloom Tiers** | *Remember $\rightarrow$ Understand $\rightarrow$ Apply $\rightarrow$ Analyze $\rightarrow$ Evaluate $\rightarrow$ Create*. |
| **Scoring Signals** | **5 Signals** | Technical (30%), Completeness (20%), Relevance (20%), Semantic (15%), Concepts (15%). |
| **Relational DB Tables** | **7 MySQL Tables** | `users`, `interview_sessions`, `interview_questions`, `session_feedback`, `syllabus_catalog`, `user_progress`, `token_blacklist`. |
| **Chunking Parameters** | **300–500 words** | 50-word sliding window overlap to prevent contextual boundary truncation. |
| **Voice Synthesis Model**| **en-US-ChristopherNeural**| High-clarity professional male technical recruiter voice profile via Edge-TTS. |
| **Speech-to-Text Model** | **Whisper-large-v3** | Conditioned with technical vocabulary prompt biasing for CS terminology. |

---

## 3. THE 4-TIER ARCHITECTURE AT A GLANCE

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ 1. PRESENTATION TIER: React 18/19 SPA + Vite 6 + Tailwind CSS v4            │
│    • Resume & JD Upload UI  • Skill Gap Matrix  • Canvas Audio Waveform     │
│    • Real-Time Interview Room  • 5-Axis Radar Chart Performance Dashboard   │
├─────────────────────────────────────────────────────────────────────────────┤
│ 2. APPLICATION TIER: FastAPI 0.115 ASGI + Python 3.10+ + Uvicorn            │
│    • PyMuPDF C-level resume parser  • Deterministic Bloom state machine     │
│    • 5-signal rubric evaluator      • In-memory neural voice streaming      │
├─────────────────────────────────────────────────────────────────────────────┤
│ 3. PERSISTENCE TIER: MySQL 8.0 (InnoDB) + ChromaDB 0.6.3                    │
│    • MySQL: Strict ACID transactions, 7 relational tables, JSON state column│
│    • ChromaDB: Local HNSW cosine vector index, 402 CS chunks, 0ms network   │
├─────────────────────────────────────────────────────────────────────────────┤
│ 4. INFERENCE & VOICE TIER: Groq LPU + Microsoft Edge-TTS                    │
│    • Groq LPU: GPT-OSS-120B / Llama-3.3-70B (>500 t/s) + Whisper-large-v3   │
│    • Edge-TTS: In-memory async chunked WebSocket audio streaming (Zero cost)│
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 4. FORMULA REFERENCE CARD

### 1. Hybrid 5-Factor Answer Scoring Equation
$$\mathbf{Score} = 0.30 \cdot T + 0.20 \cdot C + 0.20 \cdot R + 0.15 \cdot S + 0.15 \cdot K$$
- **$T$ (Technical Accuracy - 30%)**: Factual precision, correct syntax, absence of misconceptions (LLM graded).
- **$C$ (Completeness - 20%)**: Depth of explanation, edge-case coverage (LLM graded).
- **$R$ (Relevance - 20%)**: Direct responsiveness to prompt, zero topic drift (LLM graded).
- **$S$ (Semantic Similarity - 15%)**: Cosine distance between answer vector and top-3 RAG chunks (SentenceTransformers).
- **$K$ (Concept Coverage - 15%)**: Ratio of essential domain keyphrases present in candidate answer.

### 2. Dense Vector Cosine Similarity
$$\text{Cosine Similarity}(\mathbf{a}, \mathbf{r}) = \frac{\mathbf{a} \cdot \mathbf{r}}{\|\mathbf{a}\|_2 \|\mathbf{r}\|_2} = \sum_{i=1}^{384} a_i r_i \quad (\text{since vectors are } L_2 \text{ normalized})$$

### 3. Adaptive Engine Bloom Progression Rules
- **Overall Score $\ge 75$**: Advance Bloom tier ($\text{Remember} \rightarrow \text{Understand} \rightarrow \text{Apply} \rightarrow \text{Analyze} \rightarrow \text{Evaluate} \rightarrow \text{Create}$). If already at `Create`, increase difficulty to `hard`.
- **Overall Score $50 - 74$**: Maintain Bloom tier. Rotate `question_type` (conceptual $\rightarrow$ practical $\rightarrow$ scenario) to test horizontal mastery.
- **Overall Score $< 50$**: Regress Bloom tier ($\text{Create} \rightarrow \dots \rightarrow \text{Remember}$) to scaffold foundational gaps. If already at `Remember`, set difficulty to `easy`.

### 4. Priority Skill Rotation Heuristic
$$P(s) = \frac{1}{N_s + 1} \cdot \left(1.0 - \frac{\bar{S}_s}{100}\right)$$
- $N_s$: Number of times skill $s$ has been evaluated.
- $\bar{S}_s$: Candidate's running average score on skill $s$.
- Prioritizes skills with fewer evaluations and lower performance.

---

## 5. "WHY THIS, NOT THAT?" SPEED DEFENSE MATRIX

| Component | Selected Tool | Rejected Alternatives | Instant 1-Sentence Defense |
| :--- | :--- | :--- | :--- |
| **Backend** | **FastAPI** | Flask, Django, Node.js | Native `async`/`await` for audio streaming, automatic Pydantic v2 validation, and zero-overhead Python AI runtime. |
| **LLM Inference** | **Groq LPU** | OpenAI GPT-4o, Claude 3.5, Ollama | Groq's Tensor Streaming Processor delivers >500 tokens/sec (<180ms TTFT) for real-time oral dialogue at zero cost. |
| **Vector DB** | **ChromaDB** | Pinecone, Milvus, pgvector | Embedded in-process with 0ms network latency, native metadata filtering, and zero subscription cost. |
| **Embeddings** | **all-MiniLM-L6-v2**| OpenAI text-embedding-3, BGE-Large | 384 dimensions compute in <15ms on CPU with zero cloud fees, perfectly matching semantic sentence matching. |
| **PDF Ingestion** | **PyMuPDF (`fitz`)**| pdfplumber, pypdf, Apache Tika | High-performance C-engine extracts PDF glyph streams in 12ms without requiring a heavy Java runtime. |
| **Voice Output** | **Microsoft Edge-TTS**| Web Speech API, ElevenLabs | Streams natural neural speech in-memory via WebSockets, avoiding robotic browser synthesizers and high API fees. |
| **Voice Input** | **Groq Whisper-v3** | Browser Web Speech Recognition | Universal browser compatibility and superior technical jargon spelling via vocabulary prompt biasing. |
| **Database** | **MySQL 8.0** | MongoDB, PostgreSQL, DynamoDB | Strict ACID transactions, native JSON columns for `AdaptiveState`, and institutional curriculum compliance. |
| **Framework** | **Bloom's Taxonomy**| 1–10 Difficulty Numbers, LeetCode | Measures qualitative cognitive depth (Analyze/Evaluate/Create) rather than arbitrary question obscurity. |
| **Scoring** | **Hybrid 5-Factor** | Single-Prompt Zero-Shot LLM | Decouples grading into 5 orthogonal signals; immune to confident buzzword bluffing ($r=0.89$ human correlation). |
| **State Engine** | **Deterministic Python**| Autonomous LLM Agent Loop | Eliminates stochastic mood drift, token waste, and hallucination; guarantees mathematical progression rules. |

---

## 6. AI VS. DETERMINISTIC LOGIC: THE CRITICAL DISTINCTION

| Architectural Subsystem | Deterministic Software Logic (Python/MySQL/Chroma) | Generative AI / Deep Learning (Groq/Whisper/Edge-TTS) |
| :--- | :--- | :--- |
| **Question Formulation** | Computes query vector, filters domain chunks, enforces Bloom prompt | Synthesizes natural, varied question text adhering strictly to context |
| **Cognitive Progression** | Checks thresholds ($\ge 75, 50-74, <50$), advances/regresses Bloom state | **ZERO control** (LLM is never allowed to decide what level comes next) |
| **Skill Selection** | Evaluates priority formula $P(s)$, selects least-tested skill | **ZERO control** |
| **Answer Scoring** | Computes Cosine Similarity ($S$), keyword coverage ratio ($K$), and final sum | Grades Technical Accuracy ($T$), Completeness ($C$), and Relevance ($R$) |
| **Audio Processing** | AudioContext frequency analysis, canvas waveform rendering | Whisper-large-v3 neural STT + Edge-TTS neural speech synthesis |
| **Session Persistence** | Commits relational ACID transactions, serializes `AdaptiveState` JSON | **ZERO control** |

---

## 7. TOP 25 VIVA QUESTIONS & CRISP KILLER ANSWERS

1. **What is SmartInterview?**  
   *An AI-powered adaptive technical mock interview platform that grounds questions in a 402-chunk CS knowledge base via RAG, adapts difficulty via Bloom's Taxonomy, and evaluates answers using a 5-signal hybrid formula.*
2. **Why use RAG instead of asking the LLM directly?**  
   *Ungrounded LLMs hallucinate technical facts and drift off-topic. RAG anchors question generation in verified computer science literature.*
3. **What is the embedding model and where does it execute?**  
   *`all-MiniLM-L6-v2` (384 dimensions, 22.7M parameters) running locally on the server CPU in under 15ms.*
4. **Why ChromaDB over cloud vector databases like Pinecone?**  
   *ChromaDB runs in-process with 0ms network latency, requires no cloud subscriptions, and supports native dictionary metadata filtering.*
5. **What is the mathematical formula for Cosine Similarity?**  
   *$\cos(\theta) = (\mathbf{a} \cdot \mathbf{r}) / (\|\mathbf{a}\| \|\mathbf{r}\|)$. Because our vectors are unit normalized, it simplifies to the dot product $\sum a_i r_i$.*
6. **What are the six levels of Bloom's Revised Taxonomy?**  
   *Remember $\rightarrow$ Understand $\rightarrow$ Apply $\rightarrow$ Analyze $\rightarrow$ Evaluate $\rightarrow$ Create.*
7. **What are your exact Bloom transition score thresholds?**  
   *Score $\ge 75$: elevate Bloom level. Score $50–74$: maintain level and vary question type. Score $< 50$: scaffold downward to preceding level.*
8. **What are the 5 signals in your scoring rubric and their weights?**  
   *Technical Accuracy (30%), Completeness (20%), Relevance (20%), Semantic Similarity (15%), Concept Coverage (15%).*
9. **Why is semantic similarity alone insufficient for grading?**  
   *It measures topical overlap, not correctness. An articulate student asserting that "HTTP runs over UDP" would get a high semantic score without factual accuracy.*
10. **How does voice input work?**  
    *Browser captures audio via Web Audio API; Groq Whisper-large-v3 transcribes it with technical vocabulary prompt biasing in ~350ms.*
11. **How does voice output work?**  
    *Microsoft Edge-TTS streams `en-US-ChristopherNeural` MP3 chunks in-memory via WebSockets directly to the browser.*
12. **How does the system prevent repeated questions?**  
    *Previously asked questions are tracked in `AdaptiveState` and injected into the Groq prompt as negative conditioning constraints.*
13. **What database stores user data and session histories?**  
    *MySQL 8.0 (InnoDB) with 7 relational tables, foreign key cascades, and a `token_blacklist` table.*
14. **How do you handle JWT revocation on logout?**  
    *When a user logs out, the SHA-256 hash of their JWT is saved in the `token_blacklist` table. Subsequent requests check this table.*
15. **How are resumes parsed?**  
    *PyMuPDF (`fitz`) extracts raw C-level PDF glyph streams in 12ms and matches against a 50+ canonical CS skill regex taxonomy.*
16. **What is the difference between Matched Skills and Gap Skills?**  
    *Matched Skills = Resume $\cap$ JD. Gap Skills = JD $\setminus$ Resume.*
17. **What is the purpose of `SKILL_DOMAIN_MAP`?**  
    *It maps skills to knowledge domains (e.g., SQL $\rightarrow$ DBMS), applying metadata filters in ChromaDB to prevent cross-domain chunk noise.*
18. **What models run on Groq LPU?**  
    *Primary: `openai/gpt-oss-120b` (or `llama-3.3-70b-versatile`). Fallback: `openai/gpt-oss-20b` (or `llama-3.1-8b-instant`).*
19. **What happens if Groq API goes down?**  
    *The system trips an automated failover to the secondary model, and if offline, activates local heuristic scoring via CPU SentenceTransformers.*
20. **Why did you use 384 dimensions instead of 1,536?**  
    *384 dimensions capture all necessary semantic variance for technical sentence matching while executing in <15ms on CPU at zero cost.*
21. **What is University Syllabus Mode?**  
    *An isolated mode where questions are grounded in specific institutional course syllabi (e.g., JNTUH CS501PC) across 5 course units.*
22. **What does the final Performance Dashboard display?**  
    *A 5-axis Radar Chart (Cognitive Depth, Precision, Completeness, Relevance, Breadth), turn-by-turn scores, and a study roadmap.*
23. **How does FastAPI handle high concurrency?**  
    *Using asynchronous coroutines (`async`/`await`) on Uvicorn ASGI, offloading CPU tasks to thread pools.*
24. **Did AI write this project for you?**  
    *No. AI is an accelerator, but software engineers architect systems. The decoupled 4-tier design, Bloom state machine, 5-factor formula, and MySQL schema were engineered line-by-line by our team.*
25. **What is your Pearson correlation with human interviewers?**  
    *$r = 0.89$, proven through our IEEE conference paper ablation study across 100 evaluated turns.*

---

## 8. EMERGENCY HOSTILE QUESTION DEFENSE CHEAT SHEET

- **If asked: "Why not just use ChatGPT directly?"**  
  $\rightarrow$ Answer: *"ChatGPT hallucinates technical standards, drifts off-topic, grades subjectively without anchored rubrics, and has no curriculum alignment or deterministic Bloom state tracking."*
- **If asked: "Did you invent the 30/20/20/15/15 weights arbitrarily?"**  
  $\rightarrow$ Answer: *"No. They were determined through an empirical ablation study in Table V of our IEEE paper, achieving an $r=0.89$ correlation with human senior engineers and under 3.8% scoring variance."*
- **If asked: "What if a candidate attempts a prompt injection jailbreak?"**  
  $\rightarrow$ Answer: *"Answers are passed as passive data variables in backticks, and 30% of the score is hardcoded to deterministic cosine similarity ($S$) and keyword ratios ($K$), dragging malicious answers down."*
- **If asked: "Why two databases (MySQL and ChromaDB)?"**  
  $\rightarrow$ Answer: *"Polyglot persistence: MySQL provides strict ACID guarantees for relational parent-child entities; ChromaDB provides logarithmic $\mathcal{O}(\log N)$ HNSW vector search."*

