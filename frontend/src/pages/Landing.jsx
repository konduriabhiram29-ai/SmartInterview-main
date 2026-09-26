import React from 'react';
import { Link } from 'react-router-dom';
import { BrainCircuit, FileText, Brain, Zap, ArrowRight, Sparkles, CheckCircle } from 'lucide-react';
import { useAuth } from '../context/AuthContext';

const features = [
  {
    icon: FileText,
    title: 'Resume-Driven Questions',
    desc: 'Upload your resume — the AI extracts your skills, projects, and experience to build a tailored candidate profile.',
    color: 'text-blue-600',
    bg: 'bg-blue-50',
  },
  {
    icon: Brain,
    title: 'Adaptive Progression',
    desc: "Questions scale from foundational recall up to system design using Bloom's Taxonomy, calibrated to your real answers.",
    color: 'text-violet-600',
    bg: 'bg-violet-50',
  },
  {
    icon: Zap,
    title: 'Instant AI Feedback',
    desc: 'Every answer is scored across 5 dimensions — technical accuracy, completeness, relevance, semantic similarity, and concept coverage.',
    color: 'text-emerald-600',
    bg: 'bg-emerald-50',
  },
];

const techStack = ['RAG Architecture', 'ChromaDB', 'SentenceTransformers', 'Groq Llama 3', 'FastAPI', 'React', 'Tailwind v4'];

const trustItems = [
  'Voice & Text Answers',
  'Adaptive Difficulty',
  'PDF Report Export',
  'Bloom\'s Taxonomy Scoring',
];

export default function Landing() {
  const { isAuthenticated } = useAuth();

  return (
    <div className="min-h-screen bg-white flex flex-col font-sans">

      {/* ── Header ───────────────────────────────── */}
      <header className="sticky top-0 z-50 glass-header border-b border-slate-200/70">
        <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
          <div className="flex items-center gap-2.5 text-slate-900 font-bold text-lg tracking-tight">
            <div className="w-8 h-8 rounded-lg bg-indigo-600 flex items-center justify-center">
              <BrainCircuit size={18} className="text-white" />
            </div>
            Smart<span className="text-indigo-600">Interview</span>
          </div>
          <div className="flex items-center gap-3">
            {isAuthenticated ? (
              <Link to="/dashboard" className="btn btn-primary text-sm px-5 py-2 no-underline">
                Dashboard <ArrowRight size={15} />
              </Link>
            ) : (
              <>
                <Link to="/login" className="text-sm font-semibold text-slate-600 hover:text-slate-900 transition-colors no-underline">
                  Log in
                </Link>
                <Link to="/register" className="btn btn-primary text-sm px-5 py-2 no-underline">
                  Get Started
                </Link>
              </>
            )}
          </div>
        </div>
      </header>

      {/* ── Hero ─────────────────────────────────── */}
      <section className="relative overflow-hidden bg-white pt-20 pb-28 sm:pt-28 sm:pb-36">
        {/* Background gradient blob */}
        <div
          aria-hidden="true"
          className="absolute -top-40 left-1/2 -translate-x-1/2 w-[800px] h-[500px] rounded-full opacity-[0.07] blur-3xl pointer-events-none"
          style={{ background: 'radial-gradient(ellipse at center, #6366f1 0%, #9333ea 50%, transparent 100%)' }}
        />

        <div className="relative max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 text-center">

          {/* Eyebrow */}
          <div className="inline-flex items-center gap-2 px-3.5 py-1.5 rounded-full bg-indigo-50 border border-indigo-100 text-indigo-700 text-xs font-semibold mb-8 fade-up">
            <Sparkles size={13} className="text-indigo-500" />
            AI-Powered Open-Ended Adaptive Interview Engine
          </div>

          {/* Headline */}
          <h1 className="text-4xl sm:text-5xl lg:text-6xl font-extrabold text-slate-900 tracking-tight leading-[1.1] mb-6 fade-up-delay-1">
            Prepare smarter.<br />
            <span className="gradient-text">Interview better.</span>
          </h1>

          {/* Subheadline */}
          <p className="text-lg text-slate-500 max-w-2xl mx-auto mb-10 leading-relaxed fade-up-delay-2">
            Practice realistic mock interviews using tailored AI questions, adaptive Bloom's Taxonomy difficulty, resume & job description alignment, and instant rubric scoring.
          </p>

          {/* CTA Buttons */}
          <div className="flex flex-col sm:flex-row items-center justify-center gap-3 mb-12 fade-up-delay-3">
            <Link
              to={isAuthenticated ? '/setup' : '/register'}
              className="btn btn-primary text-base px-7 py-3 no-underline group"
            >
              Start Practice Session
              <ArrowRight size={18} className="transition-transform group-hover:translate-x-0.5" />
            </Link>
            <Link
              to={isAuthenticated ? '/dashboard' : '/login'}
              className="btn btn-secondary text-base px-7 py-3 no-underline"
            >
              {isAuthenticated ? 'Go to Dashboard' : 'Log in to Account'}
            </Link>
          </div>

          {/* Trust pills */}
          <div className="flex flex-wrap items-center justify-center gap-4 text-sm text-slate-500">
            {trustItems.map(t => (
              <span key={t} className="flex items-center gap-1.5">
                <CheckCircle size={14} className="text-emerald-500" />
                {t}
              </span>
            ))}
          </div>
        </div>
      </section>

      {/* ── Features ─────────────────────────────── */}
      <section className="py-24 bg-slate-50 border-y border-slate-200">
        <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="text-center mb-14">
            <p className="eyebrow mb-3">How It Works</p>
            <h2 className="text-3xl font-extrabold text-slate-900 tracking-tight">The Adaptive Interview Flow</h2>
            <p className="mt-3 text-slate-500 max-w-xl mx-auto text-base">
              No timers, no fixed question banks. Just you and an AI that adapts to your answers in real time.
            </p>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
            {features.map(({ icon: Icon, title, desc, color, bg }) => (
              <div key={title} className="card p-8 text-center">
                <div className={`w-14 h-14 rounded-xl ${bg} ${color} flex items-center justify-center mx-auto mb-5`}>
                  <Icon size={28} />
                </div>
                <h3 className="text-lg font-bold text-slate-900 mb-2">{title}</h3>
                <p className="text-slate-500 text-sm leading-relaxed">{desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── Tech Stack ───────────────────────────── */}
      <section className="py-20 bg-slate-900">
        <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 text-center">
          <h2 className="text-2xl font-extrabold text-white tracking-tight mb-2">Built With Production AI</h2>
          <p className="text-slate-400 text-sm mb-10">
            A fully engineered RAG application — not a simple LLM wrapper.
          </p>
          <div className="flex flex-wrap justify-center gap-3">
            {techStack.map(t => (
              <span
                key={t}
                className="px-4 py-2 rounded-full bg-slate-800 border border-slate-700 text-slate-300 text-sm font-medium hover:bg-slate-700 hover:text-white transition-colors"
              >
                {t}
              </span>
            ))}
          </div>
        </div>
      </section>

      {/* ── Footer ───────────────────────────────── */}
      <footer className="bg-white border-t border-slate-200 mt-auto">
        <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-8 flex flex-col sm:flex-row items-center justify-between gap-4">
          <div className="flex items-center gap-2 font-bold text-slate-900 text-sm">
            <div className="w-6 h-6 rounded-md bg-indigo-600 flex items-center justify-center">
              <BrainCircuit size={14} className="text-white" />
            </div>
            Smart<span className="text-indigo-600">Interview</span>
          </div>
          <p className="text-xs text-slate-400">© 2026 SmartInterview Platform. All rights reserved.</p>
        </div>
      </footer>
    </div>
  );
}
