# SmartInterview: Comprehensive Cross-Deliverables Verification Matrix

This matrix documents the baseline ground truth across active code, database schemas, and all four progressive academic deliverables (**SRS, Presentation PPT, Research Paper, Master Encyclopedia & Viva Defense Guide**). Every progressive update must maintain 100% coherence across these parameters.

---

## 1. Technical Parameters & Implementation Ground Truth

| Parameter / Component | Codebase Ground Truth | SRS Specification | Presentation PPT | IEEE Research Paper | Master Encyclopedia & Viva | Status |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Primary LLM Model** | `openai/gpt-oss-120b` (`backend/app/config.py`) | Section 2.4 | Slide 4 & 7 | Section III-B | Part 11.2 | Verified |
| **Fallback LLM Model** | `openai/gpt-oss-20b` (`backend/app/config.py`) | Section 2.4 | Slide 7 | Section III-B | Part 11.3 | Verified |
| **Dense Embeddings** | `sentence-transformers/all-MiniLM-L6-v2` (384-dim) | Section 2.5 | Slide 5 | Section III-A | Part 10.1 | Verified |
| **Vector Database** | ChromaDB with HNSW index (`cosine` space) | Section 3.2 | Slide 5 | Section III-A | Part 9.2, 10.3 | Verified |
| **Pedagogical Engine** | Bloom's Revised Taxonomy (6 Tiers) | Section 3.3 | Slide 6 | Section IV-A | Part 12.1-12.6 | Verified |
| **Cognitive Tiers** | `Remember`, `Understand`, `Apply`, `Analyze`, `Evaluate`, `Create` | Section 3.3 | Slide 6 | Section IV-A | Part 12.2 | Verified |
| **Adaptive Decision Thresholds** | $\ge 75$ (Advance), $50-74$ (Maintain), $< 50$ (Remediate) | Section 3.3.2 | Slide 6 | Section IV-B | Part 13.3 | Verified |
| **Answer Scoring Dimensions** | 5 factors: Accuracy, Depth, Clarity, Coverage, SBERT Sim | Section 3.4 | Slide 7 | Section V-A | Part 14.1 | Verified |
| **Auth & Security** | JWT (HS256), bcrypt password hashing, 1440m expiration | Section 2.3 | Slide 4 | Section III-D | Part 6.1-6.4 | Verified |
| **Relational Database** | MySQL 8.0 (with SQLite local compatibility) | Section 2.2 | Slide 4 | Section III-C | Part 5.1-5.6 | Verified |
| **Voice Subsystem** | Edge-TTS (Audio synthesis) & Whisper API (STT) | Section 3.5 | Slide 8 | Section VI-A | Part 15.1-15.4 | Verified |
| **Frontend Architecture** | React 18, Vite, React Router v6, Tailwind/CSS | Section 2.1 | Slide 4 | Section III-D | Part 18.1-18.4 | Verified |
| **Backend Framework** | FastAPI, Uvicorn (Port 8000), Pydantic v2, SQLAlchemy | Section 2.2 | Slide 4 | Section III-D | Part 19.1-19.5 | Verified |
| **Base Paper 1** | Wahid et al. (IJERT 2026) - Gemini & Whisper Voice Mock | Section 1.5 | Slide 3 | Section II-A | Chapter 1 & 2 | Verified |
| **Base Paper 2** | Nagarajan et al. (IJMRR 2026) - S-BERT & LLMs Platform | Section 1.5 | Slide 3 | Section II-B | Chapter 1 & 2 | Verified |
| **Team Roster (5 Members)** | Shamakura Saiteja Goud (24BD1A665K), Thodsam Srujan (24BD1A665R), Vasireddy Vignesh Reddy (24BD1A665X), Aelugu Ranith Kumar (25BD5A6615), Konduri Abhiram (25BD5A6620) | Page 1 & 2 | Slide 1 | Title / Authors | Certificate & Dec | Verified |
| **Faculty Mentor** | Dr. TVG Sridevi, Dept of CSE (AI&ML) | Title Page | Slide 1 | Authors / Affiliation | Certificate | Verified |

---

## 2. Diagram & Asset Verification

| Diagram Name | Asset File | Deliverables Reference | Code / Architecture Source | Status |
| :--- | :--- | :--- | :--- | :--- |
| **System Architecture** | `Architecture.png` (32.1 KB) | SRS Fig 2.1, PPT Slide 4, Paper Fig 1 | React + FastAPI + ChromaDB + Groq pipeline | Verified |
| **Entity Relationship (ERD)** | `ERD.png` (44.2 KB) | SRS Fig 2.2, Encyclopedia Part 5 | `users`, `resumes`, `job_descriptions`, `interviews`, `questions` | Verified |
| **Interview Execution Workflow** | `Workflow.png` (60.1 KB) | SRS Fig 2.3, PPT Slide 5, Paper Fig 2 | End-to-end question formulation, answering & feedback loop | Verified |

---

## 3. Protocol for Progressive Updates

1. **Frozen Baseline**: Never modify files in `SmartInterview_Deliverables/`.
2. **Versioned Edits**: Apply changes directly to `SmartInterview_Progressive_Updates/` with `_v2` (or subsequent versioned) naming.
3. **Automated Verification**: Run `python scripts/verify_deliverables_sync.py` after every update to confirm zero regressions and zero conflicts.
4. **User Notification**: Remind the user about the changes made, the updated files, and confirmation of cross-document coherence.
