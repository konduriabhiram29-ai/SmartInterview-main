<div align="center">
  <div style="width: 80px; height: 80px; background-color: #4f46e5; border-radius: 20px; display: flex; align-items: center; justify-content: center; margin-bottom: 20px;">
    <svg xmlns="http://www.w3.org/2000/svg" width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 2v20M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6"/></svg>
  </div>
  
  # SmartInterview

  **An Adaptive, AI-Powered Technical Interview & Examination Preparation Platform**

  [![FastAPI](https://img.shields.io/badge/FastAPI-005571?style=for-the-badge&logo=fastapi)](https://fastapi.tiangolo.com/)
  [![React](https://img.shields.io/badge/React-20232A?style=for-the-badge&logo=react&logoColor=61DAFB)](https://reactjs.org/)
  [![TailwindCSS](https://img.shields.io/badge/Tailwind_CSS-38B2AC?style=for-the-badge&logo=tailwind-css&logoColor=white)](https://tailwindcss.com/)
  [![Groq](https://img.shields.io/badge/Groq-F55036?style=for-the-badge&logo=groq&logoColor=white)](https://groq.com/)

</div>

<br />

SmartInterview revolutionizes how students and professionals prepare for technical assessments. By bridging the gap between passive studying and active recall, the platform provides hyper-realistic, dynamic mock interviews tailored explicitly to your target role or curriculum. 

Whether you're uploading a job description to prep for a software engineering interview, or uploading a university syllabus to cram for finals, SmartInterview dynamically adjusts its questioning using state-of-the-art **Retrieval-Augmented Generation (RAG)** and **Adaptive State-Machine Routing**.

---

## 🌟 Core Features

- **🎯 Adaptive Resume Mode (Targeted Prep):**
  - Upload your Resume and a Target Job Description.
  - The AI parses your skills, identifies gaps against the JD, and dynamically selects difficulty curves (from Entry Level to Staff Engineer).
  - Uses state-machine routing to adjust subsequent questions based on your real-time performance.

- **📚 Course Syllabus Mode (RAG Architecture):**
  - Upload entire study guides, syllabus PDFs, or textbook chapters.
  - The backend chunks, embeds, and indexes the materials in **ChromaDB**.
  - Creates a targeted exam covering exactly the subjects you requested—perfect for university prep.

- **🎙️ Real-time Voice Interaction:**
  - Built-in live speech recognition allows you to simply click a button and speak your answers.
  - Text-to-Speech (TTS) engine voices the interviewer's questions back to you, simulating the pressure of a real technical round.

- **📊 Deep Analytics & PDFs:**
  - Complete post-interview debriefs with scoring on Technical Accuracy, Completeness, Semantic Similarity, and Relevance.
  - Generates comprehensive PDF reports of your performance.

---

## 🏗️ Architecture

SmartInterview relies on a modern, decoupled microservice architecture:

- **Frontend:** React SPA built with Vite, styled elegantly using Tailwind CSS v4 and Framer Motion. 
- **Backend:** High-performance, asynchronous REST API powered by FastAPI (Python 3.10+).
- **AI/LLM Engine:** Groq (Llama 3 / Mixtral) handles adaptive questioning, feedback generation, and semantic evaluations with lightning-fast inference.
- **Vector DB:** ChromaDB powers the RAG pipeline for Syllabus Mode.
- **Storage:** SQLite handles user states, sessions, and historic evaluation data.

---

## 🚀 Quick Start Guide

### Prerequisites
- Node.js (v20+)
- Python (3.10+)
- A [Groq API Key](https://console.groq.com/keys)

### 1. Clone & Environment Setup
```bash
git clone https://github.com/yourusername/Smart-Interview-main.git
cd Smart-Interview-main

# Set up the environment variables
cp .env.example .env
# Edit .env and insert your GROQ_API_KEY
```

### 2. Backend Initialization
```bash
# Create and activate a virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r backend/requirements.txt

# Start the FastAPI server
cd backend
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```
*The API is now running at `http://localhost:8000` (Docs at `http://localhost:8000/docs`).*

### 3. Frontend Initialization
Open a new terminal window.
```bash
cd frontend

# Install packages
npm install

# Start the Vite development server
npm run dev
```
*The app is now running at `http://localhost:5174`.*

---

## 🧪 Running Tests
The project features an automated End-to-End (E2E) testing suite using Playwright.
```bash
# Install playwright browsers
python -m playwright install

# Run the test suite
python tests/fixtures/test_e2e.py
```

---

## 📖 Academic Deliverables
All synchronized academic documentation and artifacts for this project are located in:
- `SmartInterview_Deliverables/`: Finalized frozen artifacts.
- `SmartInterview_Progressive_Updates/`: Live versioned documents (SRS, Research Paper, Master Encyclopedia).

You can verify the codebase synchronization at any time by running:
```bash
python scripts/verify_deliverables_sync.py
```

---

<div align="center">
  <i>Built with passion for the future of education and career preparation.</i>
</div>