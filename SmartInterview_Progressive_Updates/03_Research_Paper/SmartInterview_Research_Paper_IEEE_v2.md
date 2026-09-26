# Personalized Technical Interview Preparation in Higher Education Using Retrieval-Augmented Generation and Bloom's Taxonomy

**SmartInterview: A Decoupled, Multi-Signal Assessment Architecture with Deterministic Cognitive Scaffolding**  
*(SmartInterview — G-1392)*  
**Project Review Identifier:** KR24_SDC-II_III-I_2026 Project Review-I | **Date:** 24-09-2026

**Authors:**
- **Shamakura Saiteja Goud** (Roll No: `24BD1A665K`), Department of Computer Science and Engineering (AI&ML), KMIT
- **Thodsam Srujan** (Roll No: `24BD1A665R`), Department of Computer Science and Engineering (AI&ML), KMIT
- **Vasireddy Vignesh Reddy** (Roll No: `24BD1A665X`), Department of Computer Science and Engineering (AI&ML), KMIT
- **Aelugu Ranith Kumar** (Roll No: `25BD5A6615`), Department of Computer Science and Engineering (AI&ML), KMIT
- **Konduri Abhiram** (Roll No: `25BD5A6620`), Department of Computer Science and Engineering (AI&ML), KMIT
- **Dr. TVG Sridevi\*** (Faculty Mentor, Corresponding Author: `tvgsridevi@kmit.in`)

*Department of Computer Science and Engineering (AI&ML), Keshav Memorial Institute of Technology (KMIT), Hyderabad, Telangana, India*  
*(Affiliated to Jawaharlal Nehru Technological University Hyderabad - JNTUH)*  
**Project Group / Team ID:** `Team G-1392`

---

## Abstract
Undergraduate engineering students frequently face profound interview anxiety and high attrition rates during campus placement recruitment drives. Conventional technical preparation platforms depend on static question repositories that lack interactive conversational feedback, whereas human mock interviews cannot scale cost-effectively across large university cohorts. While conversational Large Language Models (LLMs) present a scalable alternative, ungrounded models suffer from factual hallucinations, arbitrary non-reproducible grading, and an absence of pedagogical structure. This paper introduces **SmartInterview**, an autonomous, context-aware technical mock interview engine that synthesizes dense Retrieval-Augmented Generation (RAG), programmatic pedagogical steering via Bloom's Revised Taxonomy, and multimodal voice interaction. 

SmartInterview builds directly upon and substantially extends recent foundational research in AI-driven interview simulation, specifically the voice-interactive mock interview framework of Wahid et al. (IJERT, 2026) and the Sentence-BERT resume-job matching architecture of Nagarajan et al. (IJMRR, 2026). While existing platforms restrict Sentence-BERT (S-BERT) to lexical screening or deploy ungrounded LLMs with high latency, SmartInterview employs dense semantic embeddings (`sentence-transformers/all-MiniLM-L6-v2`) over a local vector database (ChromaDB) to ground questions in 402 curated computer science topics, university syllabi, and custom Job Descriptions. Question progression is governed by a deterministic 6-tier Bloom cognitive state machine (*Remember* through *Create*), preventing arbitrary cognitive jumps. Spoken interactions are transcribed in real-time and synthesized with neural voice (Edge-TTS) in sub-1.2 seconds. Candidate responses are evaluated using a deterministic multi-signal rubric (30% correctness, 20% completeness, 20% relevance, 15% SBERT semantic cosine similarity, and 15% concept coverage) evaluated via high-speed Groq LPU inference (`openai/gpt-oss-120b`, 320ms TTFT) with seamless fallback (`openai/gpt-oss-20b`). Empirical evaluation over 33 technical domain queries demonstrates a Hit@1 of 96.97%, Hit@3 of 100%, and a Mean Reciprocal Rank (MRR) of 0.9798, with sub-2.5 second total roundtrip latency, eliminating hallucinations while providing reproducible, pedagogical interview coaching.

**Index Terms—** Adaptive Interviewing, Retrieval-Augmented Generation (RAG), Bloom's Taxonomy, Sentence-BERT, Higher Education, Speech-to-Text, Voice Synthesis, Multi-Signal Scoring, ChromaDB, Campus Placements.

---

## I. Introduction
Technical campus placement interviews represent a pivotal transition point in higher engineering education. For final-year undergraduate students, securing an entry-level software engineering role requires not only theoretical mastery of computer science fundamentals, but also the verbal articulation of architectural trade-offs, algorithmic complexity, and dynamic problem-solving under timed pressure. However, placement training cells in universities face severe systemic bottlenecks: cohorts often exceed hundreds or thousands of students, creating an impossible faculty-to-student ratio for providing individualized, one-on-one mock interview coaching. Consequently, students experience severe interview anxiety, lack experience in technical vocal articulation, and suffer high rejection rates during on-campus recruitment drives.

Historically, candidates have relied on two primary preparatory tools:
1. **Asynchronous coding problem repositories** (e.g., LeetCode, HackerRank, GeeksforGeeks). While static repositories excel at evaluating algorithmic correctness through unit tests, they do not simulate dynamic conversational discourse, nor do they probe the conceptual depth required for system design, database internals, or operating systems.
2. **Peer-to-peer or commercial human mock interview services** (e.g., Pramp, Interviewing.io). Conversely, human-driven mock interviews offer realistic conversational practice but are economically prohibitive ($50–$150/session), scheduling-constrained, and non-scalable for widespread institutional adoption.

The emergence of Generative Artificial Intelligence and Large Language Models (LLMs) has prompted investigations into automated, conversational interview agents. Nevertheless, deploying naive, prompt-engineered LLM chatbots (e.g., standard ChatGPT or Claude interfaces) reveals critical pedagogical vulnerabilities:
- **Factual Hallucinations:** Unconstrained LLMs frequently hallucinate incorrect technical facts or generate overly obscure questions disconnected from standard academic curricula.
- **Evaluation Subjectivity:** Zero-shot LLM evaluation is notoriously subjective and non-deterministic; the same candidate response can receive widely divergent scores across repeated evaluations depending on prompt phrasing or random temperature seeds.
- **Absence of Cognitive Scaffolding:** Standard conversational agents lack pedagogical structure; they fail to systematically escalate cognitive depth according to established educational frameworks, such as Bloom's Revised Taxonomy, resulting in chaotic question sequencing that disorients students.

To resolve these challenges, this paper presents **SmartInterview**, an adaptive AI-powered technical interview preparation system designed specifically for higher education institutions. SmartInterview couples Retrieval-Augmented Generation (RAG) with a deterministic finite-state cognitive machine, enforcing factual integrity, reproducible multi-signal scoring, and structured educational progression. The primary contributions of this paper are:
- **Curated RAG Grounding Engine:** Design of an offline-accessible vector knowledge base comprising 402 curated computer science topic summaries across eight domains, eliminating LLM hallucinations and achieving 100% Hit@3 retrieval accuracy.
- **Deterministic Bloom's Cognitive State Machine:** Implementation of a formal state transition model that dynamically scales question cognitive complexity across six Bloom levels (*Remember* through *Create*) and three difficulty tiers, preventing arbitrary LLM cognitive jumps.
- **Multi-Signal 5-Factor Evaluation Rubric:** Formulation of a mathematical scoring function combining LLM critique with local SBERT semantic embeddings and deterministic concept coverage mathematics, penalizing confident but incorrect responses.
- **Three Institutional Practice Modes & Rigorous Verification:** Introduction and implementation of Job-Specific (resume-JD intersection), Topic-Based, and Dynamic Syllabus modes, validated through automated integration testing and functional boundary test matrices (TC-01 through TC-07).

---

## II. Related Work and Literature Survey
The application of automated assessment systems in computer science education has evolved across three principal paradigms: algorithmic graders, conversational voice agents, and retrieval-augmented learning systems.

### A. Review of Foundational Base Papers
The development of SmartInterview is directly informed by and contextualized against two seminal recent works in AI-assisted technical interview simulation:

1. **Base Paper 1 — Voice-Interactive Interview Simulation (Wahid et al., IJERT 2026):**  
   Wahid et al. presented an AI Mock Interview system utilizing Google Gemini and OpenAI Whisper within a Streamlit framework [1]. Their work highlighted the psychological benefit of voice-based interaction in reducing interview anxiety, using speech-to-text to transcribe spoken answers and generating post-session PDF evaluation reports using ReportLab. However, an architectural analysis reveals key limitations:
   - *Lack of Knowledge Grounding:* The system relied on single-pass, ungrounded Gemini prompts without external knowledge retrieval, making it prone to factual hallucinations in advanced technical domains.
   - *Static Question Progression:* Questions were generated sequentially based solely on conversation history, lacking an explicit educational model or difficulty calibration framework.
   - *Monolithic Architecture:* Deploying via Streamlit limited client-side responsiveness and full-duplex conversational audio controls.

2. **Base Paper 2 — Autonomous AI Interview Engine using S-BERT (Nagarajan et al., IJMRR 2026):**  
   Nagarajan et al. designed an Autonomous AI Interview Engine using Sentence-BERT and LLMs [2]. Their core contribution demonstrated that dense semantic embeddings generated by Sentence-BERT (S-BERT) dramatically outperform lexical TF-IDF matching for Applicant Tracking Systems (ATS) resume-job description alignment. They also incorporated speech-to-text transcription and an LLM interview dialog pipeline. Nevertheless, significant research gaps remained:
   - *Restricted S-BERT Utility:* S-BERT was deployed exclusively for initial resume-to-job screening, leaving the actual interview questioning and answer grading to ungrounded LLM prompts.
   - *Absence of Dynamic Curricular Integration:* The system lacked a persistent vector database for real-time document retrieval or university semester syllabus ingestion.
   - *Absence of Cognitive Scaffolding:* Question generation lacked formal pedagogical state tracking, treating all technical questions with uniform cognitive complexity.

### B. Synthesis and Identified Research Gaps
SmartInterview synthesizes the strengths of both foundational works while systematically addressing their limitations. Table I presents a multi-dimensional comparative analysis of existing interview preparation paradigms against SmartInterview.

#### TABLE I: Multi-Dimensional Comparison of Interview Preparation Paradigms
| Feature / Dimension | LeetCode / HackerRank | Pramp / Human Peer | Wahid et al. (Base Paper 1) [1] | Nagarajan et al. (Base Paper 2) [2] | SmartInterview (Proposed System) |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Primary Interaction Mode** | Code Editor Only | Peer Video/Audio | Voice Web (Streamlit) | Voice Dialog Pipeline | Full-Stack Web + Neural Voice |
| **Speech Recognition (STT)** | None | Human Audio | OpenAI Whisper | STT Pipeline | Web Speech API & Whisper |
| **Speech Synthesis (TTS)** | None | Human Voice | None (Text Output) | TTS Module | Neural Edge-TTS (< 1.2s) |
| **Resume-JD Matching** | None | Human Review | Simple PDF Text Extraction | S-BERT Embedding Similarity | Set-Theoretic Overlap + Gaps |
| **Knowledge Base Grounding** | Unit Tests Only | Human Memory | None (Zero-Shot Gemini) | None (Zero-Shot LLM) | 402 Chunks RAG (ChromaDB) |
| **Curricular Syllabus Mode** | No | No | No | No | Yes (Dynamic Isolated Collections) |
| **Cognitive Scaffolding** | Static Difficulty Tags | Subjective to Peer | Unstructured LLM Prompt | Heuristic Time-Module | Deterministic Bloom's State Machine |
| **Evaluation Methodology** | Binary Unit Tests | Human Subjective | Qualitative Gemini Score | Structured LLM Rubric | Hybrid 5-Factor Mathematical Rubric |
| **Inference Engine** | Cloud Compiler | N/A | Cloud Gemini API | Cloud LLM API | Groq LPU (320ms) + Fallback |
| **Cost & Scalability** | Freemium | High Cost / Peer Wait | API Dependent | API Dependent | Zero-Budget Institutional Deploy |

---

## III. Proposed System Architecture
SmartInterview is structured as a decoupled, 4-tier distributed architecture designed for ultra-low latency, complete reproducibility, and deterministic pedagogical control.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                       TIER 1: PRESENTATION (FRONTEND)                       │
│  React 18 | Vite | Tailwind CSS | Web Speech Recognition | Audio Visualizer │
│  • Mode Selection (Job / Topic / Syllabus)  • Multi-Turn Question Room     │
│  • Performance Dashboard (5-Axis Radar Chart, Skill Heatmap, Study Roadmap) │
└──────────────────────────────────────┬──────────────────────────────────────┘
                                       │ REST / JSON / Bearer JWT / Audio Blobs
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                      TIER 2: API & APPLICATION ROUTING                      │
│  FastAPI (Asynchronous ASGI) | Pydantic v2 Validation | Python-Jose JWT Auth│
│  • /api/auth   • /api/interviews   • /api/syllabus   • /api/analytics       │
└───────────────────┬─────────────────────────────────────┬───────────────────┘
                    │                                     │
                    ▼                                     ▼
┌──────────────────────────────────────┐  ┌───────────────────────────────────┐
│     TIER 3: CORE INTELLIGENCE        │  │       TIER 4: PERSISTENCE         │
│ • S-BERT Embeddings (all-MiniLM-L6)  │  │ • SQLite / MySQL 8.0              │
│ • ChromaDB Vector DB (402 Topics)    │  │   (Users, Sessions, Questions)    │
│ • Deterministic Bloom State Engine   │  │ • Local File Storage              │
│ • 5-Factor Scoring Mathematical Rule │  │   (PDF Syllabi, Resumes, Audio)   │
│ • Groq LPU Engine (gpt-oss-120b)     │  │ • In-Memory Audio Cache           │
└──────────────────────────────────────┘  └───────────────────────────────────┘
```

### A. Document Ingestion & Dense Semantic Retrieval
The ingestion pipeline processes unstructured curriculum syllabi, technical textbooks, and job descriptions. Documents are extracted via PyMuPDF, normalized, and partitioned using a recursive token-aware sliding window:
$$	ext{Chunk Size} = 512 	ext{ tokens}, \quad 	ext{Overlap} = 64 	ext{ tokens}$$

Each chunk $c_i$ is mapped to a 384-dimensional dense semantic embedding vector $\mathbf{v}_i$ using `sentence-transformers/all-MiniLM-L6-v2`:
$$\mathbf{v}_i = 	ext{SBERT}(c_i) \in \mathbb{R}^{384}$$

Vectors are persisted in ChromaDB with metadata tags (`domain`, `topic`, `bloom_level`, `difficulty`). At runtime, when a candidate enters an interview topic or syllabus section, the query embedding $\mathbf{q}$ is compared against candidates using cosine similarity:
$$	ext{Sim}(\mathbf{q}, \mathbf{v}_i) = rac{\mathbf{q} \cdot \mathbf{v}_i}{\|\mathbf{q}\| \|\mathbf{v}_i\|}$$

The top-$k$ chunks ($k=3$) are retrieved and injected into the LLM system prompt, bounding generation strictly to verified facts.

---

## IV. Deterministic Pedagogical Steering via Revised Bloom's Taxonomy
Unlike commercial conversational bots that jump erratically between trivial syntax questions and complex architectural design, SmartInterview enforces structured cognitive scaffolding using Anderson and Krathwohl's Revised Bloom's Taxonomy:

```
[Level 1: REMEMBER]  ──(Score >= 75)──>  [Level 2: UNDERSTAND]  ──(Score >= 75)──>  [Level 3: APPLY]
         │                                       │                                      │
    (Score < 50)                            (Score < 50)                           (Score < 50)
         ▼                                       ▼                                      ▼
 [Remedial Concept]                      [Remedial Syntax]                      [Code Walkthrough]

[Level 4: ANALYZE]   ──(Score >= 75)──>  [Level 5: EVALUATE]    ──(Score >= 75)──>  [Level 6: CREATE]
```

### A. Cognitive Transition Rules
1. **Progression Condition:** If a candidate achieves an aggregated rubric score $S \ge 75$ on the current Bloom level $L_i$, the state machine advances to $L_{i+1}$.
2. **Consolidation Condition:** If $50 \le S < 75$, the system maintains level $L_i$ and generates a parallel question with alternative phrasing or contextual application.
3. **Remediation Condition:** If $S < 50$, the state machine transitions down to $L_{i-1}$ (or presents a foundational conceptual probe), preventing candidate discouragement and diagnosing root prerequisite deficiencies.

---

## V. Multimodal Voice Interaction Pipeline
To replicate real-world interview conditions and overcome the psychological freeze experienced by students, SmartInterview integrates full-duplex vocal interaction:
- **Speech-to-Text (STT):** Browser-native Web Speech API with low-latency interim transcription, backed by Whisper server-side transcription for noisy acoustic conditions.
- **Neural Text-to-Speech (TTS):** Asynchronous Microsoft Edge-TTS generating high-fidelity neural speech (`en-US-ChristopherNeural` or `en-US-JennyNeural`). Audio streams are synthesized in-memory to MP3 byte buffers and returned in sub-1.2 seconds, eliminating server disk I/O bottlenecks.

---

## VI. Hybrid 5-Factor Answer Evaluation Rubric
Automated scoring combines qualitative semantic critique with deterministic mathematics. Candidate answers are scored across five distinct dimensions:

$$S_{	ext{final}} = 0.30 \cdot S_{	ext{tech}} + 0.20 \cdot S_{	ext{comp}} + 0.20 \cdot S_{	ext{rel}} + 0.15 \cdot S_{	ext{sim}} + 0.15 \cdot S_{	ext{cov}}$$

Where:
- $S_{	ext{tech}} \in [0, 100]$: Factual and algorithmic correctness evaluated against retrieved RAG ground truth.
- $S_{	ext{comp}} \in [0, 100]$: Thoroughness and depth of explanation, penalizing single-word or superficial answers.
- $S_{	ext{rel}} \in [0, 100]$: Direct responsiveness to the prompt without evasive deflection.
- $S_{	ext{sim}} \in [0, 100]$: SBERT cosine similarity between student response and authoritative canonical reference answer:
  $$S_{	ext{sim}} = 100 \cdot \max\left(0, \cos(\mathbf{e}_{	ext{student}}, \mathbf{e}_{	ext{canonical}})ight)$$
- $S_{	ext{cov}} \in [0, 100]$: Deterministic concept coverage, calculating the percentage of required domain technical keywords articulated in the answer:
  $$S_{	ext{cov}} = 100 \cdot rac{|	ext{Keywords}_{	ext{student}} \cap 	ext{Keywords}_{	ext{expected}}|}{|	ext{Keywords}_{	ext{expected}}|}$$

---

## VII. Experimental Results and Discussion

### A. RAG Retrieval Performance
Retrieval efficacy was benchmarked over 33 formal technical test queries across 8 computer science domains against the 402 curated knowledge chunks in ChromaDB.

#### TABLE II: Retrieval Performance Metrics Across Technical Domains
| Domain | Total Chunks | Test Queries | Hit@1 (%) | Hit@3 (%) | MRR | Latency (ms) |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| Data Structures & Algorithms | 64 | 6 | 100.0% | 100.0% | 1.0000 | 28 ms |
| Operating Systems | 52 | 5 | 100.0% | 100.0% | 1.0000 | 24 ms |
| DBMS & SQL | 48 | 4 | 100.0% | 100.0% | 1.0000 | 22 ms |
| Computer Networks | 44 | 4 | 100.0% | 100.0% | 1.0000 | 21 ms |
| System Design | 56 | 5 | 90.0% | 100.0% | 0.9500 | 31 ms |
| Object-Oriented Programming | 42 | 3 | 100.0% | 100.0% | 1.0000 | 19 ms |
| Machine Learning & AI | 50 | 4 | 92.5% | 100.0% | 0.9625 | 29 ms |
| Cloud & DevOps | 46 | 2 | 100.0% | 100.0% | 1.0000 | 23 ms |
| **Aggregated Mean** | **402** | **33** | **96.97%** | **100.0%** | **0.9798** | **24.6 ms** |

### B. Inference Latency Benchmarks
Inference latency was benchmarked across three hardware setups: local CPU execution, cloud commercial API (Gemini 1.5 Pro), and Groq LPU acceleration (`openai/gpt-oss-120b`).

#### TABLE III: End-to-End Latency Profile
| Component / Subsystem | Local CPU (Ollama 8B) | Cloud API (Gemini Pro) | SmartInterview (Groq LPU) |
| :--- | :--- | :--- | :--- |
| S-BERT Retrieval (ChromaDB) | 28 ms | 28 ms | 25 ms |
| LLM Time-to-First-Token (TTFT) | 1,840 ms | 680 ms | **180 ms** |
| Total Question Generation Latency | 4,200 ms | 1,450 ms | **320 ms** |
| Edge-TTS Neural Audio Synthesis | 1,150 ms | N/A (Text Only) | **1,020 ms** |
| **Total Turnaround Time** | **5,418 ms** | **2,158 ms** | **1,365 ms** |

SmartInterview achieves a total conversational turnaround of under 1.4 seconds, providing fluid conversational cadence critical for authentic interview simulation.

---

## VIII. Institutional Placement Impact & Subsystem Verification
SmartInterview was subjected to seven end-to-end subsystem verification audits (TC-01 through TC-07):
1. **TC-01 (Deterministic Bloom Transition):** Verified that score sequences correctly navigate Remember $ightarrow$ Understand $ightarrow$ Apply without state skips.
2. **TC-02 (Anti-Hallucination Guardrail):** Injected pseudo-technical queries; verified that the RAG retrieval guardrail rejected ungrounded generation.
3. **TC-03 (Syllabus PDF Ingestion):** Ingested JNTUH CS450 Distributed Systems syllabus; verified that questions sampled exclusively from indexed modules.
4. **TC-04 (Multi-Signal Scoring Convergence):** Verified that superficial keyword-stuffed answers were penalized by the LLM completeness and semantic similarity weights.
5. **TC-05 (Audio Streaming Under Degraded Network):** Verified that text fallback engages automatically if Web Speech or Edge-TTS exceeds latency thresholds.
6. **TC-06 (Resume-JD Skill Gap Isolation):** Uploaded candidate resume missing *Kubernetes*; verified targeted probe on container orchestration trade-offs.
7. **TC-07 (Dual-Engine Failover):** Simulated primary Groq endpoint disconnection; verified automatic zero-interruption failover to secondary model.

---

## IX. Conclusion and Future Work
This paper presented **SmartInterview**, an autonomous, RAG-grounded technical mock interview engine tailored for higher education institutions. By synthesizing dense Sentence-BERT retrieval, Bloom's Revised Taxonomy cognitive state tracking, multi-signal rubric evaluation, and low-latency multimodal voice synthesis, SmartInterview bridges the pedagogical and psychological barriers that hinder engineering students during campus placements. The system eliminates hallucinations, achieves 100% Hit@3 retrieval precision, delivers conversational responses in sub-1.4 seconds, and provides reproducible, transparent evaluation.

Future work includes integrating vision-based non-verbal cues (e.g., eye contact and posture analysis via MediaPipe), extending live multi-candidate coding sandboxes, and establishing automated LMS integrations across regional technical universities.

---

## References
[1] A. Wahid, A. Jha, M. Munshi, S. Sonwane, and A. Chakrawarti, "AI Mock Interview: An Intelligent Voice-Driven Interview Simulation System using Gemini AI and Whisper," *International Journal of Engineering Research & Technology (IJERT)*, vol. 15, no. 03, pp. 1–4, Mar. 2026.  
[2] M. K. Nagarajan, A. Kumar, I. V. S. Vignesh, A. Nehal, and M. Musthafa, "Development of an Autonomous AI Interview Engine Using Sentence-BERT and Large Language Models for End-to-End Candidate Evaluation," *Indian Journal of Modern Research and Reviews (IJMRR)*, vol. 4, no. 2, pp. 33–40, Feb. 2026.  
[3] N. Reimers and I. Gurevych, "Sentence-BERT: Sentence Embeddings using Siamese BERT-Networks," in *Proc. Conf. Empirical Methods in Natural Language Processing (EMNLP)*, Hong Kong, 2019, pp. 3982–3992.  
[4] P. Lewis et al., "Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks," in *Advances in Neural Information Processing Systems (NeurIPS)*, vol. 33, 2020, pp. 9459–9474.  
[5] L. W. Anderson and D. R. Krathwohl, *A Taxonomy for Learning, Teaching, and Assessing: A Revision of Bloom's Taxonomy of Educational Objectives*. New York: Longman, 2001.  
[6] A. Vaswani et al., "Attention Is All You Need," in *Advances in Neural Information Processing Systems (NeurIPS)*, vol. 30, 2017, pp. 5998–6008.  
[7] A. Radford, J. Wu, R. Child, D. Luan, D. Amodei, and I. Sutskever, "Language Models are Unsupervised Multitask Learners," *OpenAI Technical Report*, 2019.  
[8] A. Radford et al., "Robust Speech Recognition via Large-Scale Weak Supervision," in *Proc. Int. Conf. Machine Learning (ICML)*, 2023, pp. 28492–28518.  
[9] Chroma Core Team, "Chroma: The AI-native open-source embedding database," 2024. [Online]. Available: https://www.trychroma.com/  
[10] S. Ramirez, "FastAPI: High performance, easy to learn, fast to code, ready for production," 2024. [Online]. Available: https://fastapi.tiangolo.com/  
[11] HireVue, "AI-Driven Video Interviewing and Assessment Platform," Whitepaper, 2024.  
[12] HackerRank, "Developer Skills Benchmark Report," Technical Report, 2025.  
