import { useState, useEffect, useRef } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { 
  Send, CheckCircle, AlertCircle, Loader2, Brain, BarChart3, 
  Flag, Mic, Volume2, Square, Play, BrainCircuit
} from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import api from '../services/api';

// Canonical technical term mapping for live speech recognition
function normalizeLiveTerms(text) {
  if (!text) return '';
  text = text.replace(/[\u0600-\u06FF\u0750-\u077F\uFB50-\uFDFF\uFE70-\uFEFF]+/g, '');

  const rules = [
    [/\b(?:see\s*plus\s*plus|c\s*plus\s*plus)\b/gi, 'C++'],
    [/\b(?:see\s*sharp|c\s*sharp)\b/gi, 'C#'],
    [/\b(?:fast\s*api)\b/gi, 'FastAPI'],
    [/\b(?:node\s*js)\b/gi, 'Node.js'],
    [/\b(?:next\s*js)\b/gi, 'Next.js'],
    [/\b(?:pie\s*thon|python)\b/gi, 'Python'],
    [/\b(?:java)\b/gi, 'Java'],
    [/\b(?:golang)\b/gi, 'Go'],
    [/\b(?:type\s*script)\b/gi, 'TypeScript'],
    [/\b(?:java\s*script)\b/gi, 'JavaScript'],
    [/\b(?:postgres|post\s*gres|postgress)\b/gi, 'PostgreSQL'],
    [/\b(?:mongo\s*db)\b/gi, 'MongoDB'],
    [/\b(?:sequel|s\s*q\s*l)\b/gi, 'SQL'],
    [/\b(?:no\s*sql)\b/gi, 'NoSQL'],
    [/\b(?:sqlite|sequel\s*lite)\b/gi, 'SQLite'],
    [/\b(?:rest\s*apis?)\b/gi, 'REST API'],
    [/\b(?:rest\s*ful)\b/gi, 'RESTful'],
    [/\b(?:j\s*w\s*t|jay\s*son\s*web\s*tokens?|json\s*web\s*tokens?)\b/gi, 'JWT'],
    [/\b(?:o\s*auth\s*2|oauth\s*2)\b/gi, 'OAuth 2.0'],
    [/\b(?:o\s*auth)\b/gi, 'OAuth'],
    [/\b(?:k\s*8\s*s|cooper\s*neties|cubernetes)\b/gi, 'Kubernetes'],
    [/\b(?:dock\s*er)\b/gi, 'Docker'],
    [/\b(?:git\s*hub)\b/gi, 'GitHub'],
    [/\b(?:ci\s*cd|c\s*i\s*c\s*d)\b/gi, 'CI/CD'],
    [/\b(?:g\s*i\s*l)\b/gi, 'GIL'],
    [/\b(?:o\s*o\s*p)\b/gi, 'OOP'],
    [/\b(?:d\s*s\s*a)\b/gi, 'DSA'],
    [/\b(?:r\s*a\s*g)\b/gi, 'RAG'],
    [/\b(?:l\s*l\s*ms?)\b/gi, 'LLM'],
    [/\b(?:a\s*c\s*i\s*d)\b/gi, 'ACID'],
    [/\b(?:v\s*tables?)\b/gi, 'vtable'],
    [/\b(?:b\s*trees?)\b/gi, 'B-tree'],
    [/\b(?:async\s*and\s*await|async\s*await)\b/gi, 'async/await'],
  ];

  for (const [pattern, replacement] of rules) {
    text = text.replace(pattern, replacement);
  }
  return text;
}

export default function Interview() {
  const { id } = useParams();
  const navigate = useNavigate();

  // Session state
  const [session, setSession] = useState(null);
  const [currentQuestion, setCurrentQuestion] = useState(null);
  const [answer, setAnswer] = useState('');
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [finishing, setFinishing] = useState(false);
  const [error, setError] = useState('');

  // Adaptive state
  const [questionsAnswered, setQuestionsAnswered] = useState(0);
  const [isComplete, setIsComplete] = useState(false);

  // Voice layer state
  const [isSpeaking, setIsSpeaking] = useState(false);
  const [ttsLoading, setTtsLoading] = useState(false);
  const [autoplayBlocked, setAutoplayBlocked] = useState(false);
  const [isRecording, setIsRecording] = useState(false);
  const [isTranscribing, setIsTranscribing] = useState(false);
  const [micPermissionDenied, setMicPermissionDenied] = useState(false);
  const [liveInterimSnippet, setLiveInterimSnippet] = useState('');

  const audioRef = useRef(null);
  const mediaRecorderRef = useRef(null);
  const audioChunksRef = useRef([]);
  const recognitionRef = useRef(null);
  const baseAnswerRef = useRef('');

  useEffect(() => {
    loadSession();
    return () => {
      stopAudioPlayback();
      cleanupRecording();
    };
  }, [id]);

  useEffect(() => {
    if (currentQuestion) {
      const isFirst = currentQuestion.question_number === 1;
      playQuestionAudio(currentQuestion, isFirst);
    }
    return () => {
      stopAudioPlayback();
    };
  }, [currentQuestion?.id]);

  const loadSession = async () => {
    try {
      const res = await api.get(`/interviews/${id}`);
      const data = res.data;
      setSession(data);

      if (data.status === 'completed') {
        navigate(`/results/${id}`);
        return;
      }

      const questions = data.questions || [];
      const unanswered = questions.find(q => !q.answer_text);
      if (unanswered) {
        setCurrentQuestion(unanswered);
        setQuestionsAnswered(questions.filter(q => q.answer_text).length);
      } else if (questions.length > 0) {
        setCurrentQuestion(questions[questions.length - 1]);
        setQuestionsAnswered(questions.length);
      }
    } catch (err) {
      setError('Failed to load interview session');
    } finally {
      setLoading(false);
    }
  };

  const stopAudioPlayback = () => {
    if (audioRef.current) {
      audioRef.current.pause();
      audioRef.current.currentTime = 0;
      audioRef.current = null;
    }
    setIsSpeaking(false);
    setTtsLoading(false);
  };

  const playQuestionAudio = async (question, isIntro = false) => {
    if (!question || !question.question_text) return;

    stopAudioPlayback();
    setTtsLoading(true);
    setAutoplayBlocked(false);

    try {
      const res = await api.post(
        '/interviews/voice/tts',
        {
          text: question.question_text,
          question_number: question.question_number || 1,
          include_intro: isIntro,
        },
        { responseType: 'blob' }
      );

      const blobUrl = URL.createObjectURL(res.data);
      const audio = new Audio(blobUrl);
      audioRef.current = audio;

      audio.onplay = () => {
        setIsSpeaking(true);
        setTtsLoading(false);
        setAutoplayBlocked(false);
      };

      audio.onended = () => {
        setIsSpeaking(false);
        setTtsLoading(false);
      };

      audio.onerror = () => {
        setIsSpeaking(false);
        setTtsLoading(false);
      };

      const playPromise = audio.play();
      if (playPromise !== undefined) {
        playPromise.catch((err) => {
          setIsSpeaking(false);
          setTtsLoading(false);
          if (err.name === 'NotAllowedError') {
            setAutoplayBlocked(true);
          }
        });
      }
    } catch (err) {
      setIsSpeaking(false);
      setTtsLoading(false);
    }
  };

  const cleanupRecording = () => {
    if (recognitionRef.current) {
      try { recognitionRef.current.stop(); } catch (_) {}
      recognitionRef.current = null;
    }
    if (mediaRecorderRef.current && mediaRecorderRef.current.state !== 'inactive') {
      try { mediaRecorderRef.current.stop(); } catch (_) {}
    }
    if (mediaRecorderRef.current?.stream) {
      mediaRecorderRef.current.stream.getTracks().forEach((track) => track.stop());
    }
    mediaRecorderRef.current = null;
  };

  const startRecording = async () => {
    stopAudioPlayback();
    setMicPermissionDenied(false);
    setError('');
    setLiveInterimSnippet('');
    baseAnswerRef.current = answer.trim();

    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
      setMicPermissionDenied(true);
      return;
    }

    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      audioChunksRef.current = [];

      let mimeType = 'audio/webm;codecs=opus';
      if (!MediaRecorder.isTypeSupported(mimeType)) {
        mimeType = MediaRecorder.isTypeSupported('audio/webm') ? 'audio/webm' : '';
      }

      const recorder = mimeType ? new MediaRecorder(stream, { mimeType }) : new MediaRecorder(stream);
      mediaRecorderRef.current = recorder;

      recorder.ondataavailable = (event) => {
        if (event.data && event.data.size > 0) {
          audioChunksRef.current.push(event.data);
        }
      };

      recorder.onstop = async () => {
        const audioBlob = new Blob(audioChunksRef.current, { type: recorder.mimeType || 'audio/webm' });
        stream.getTracks().forEach((t) => t.stop());

        if (audioBlob.size > 500) {
          await transcribeRecordedAudio(audioBlob);
        } else {
          setIsTranscribing(false);
        }
      };

      recorder.start(250);
      setIsRecording(true);

      const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
      if (SpeechRecognition) {
        try {
          const recognition = new SpeechRecognition();
          recognition.continuous = true;
          recognition.interimResults = true;
          recognition.lang = 'en-US';
          let sessionFinal = '';

          recognition.onresult = (event) => {
            let interim = '';
            for (let i = event.resultIndex; i < event.results.length; i++) {
              const text = event.results[i][0].transcript;
              if (event.results[i].isFinal) sessionFinal += ' ' + text;
              else interim += ' ' + text;
            }
            const rawSpoken = (sessionFinal + ' ' + interim).trim();
            const normalizedSpoken = normalizeLiveTerms(rawSpoken);
            setLiveInterimSnippet(normalizedSpoken);
            const prefix = baseAnswerRef.current;
            const fullAnswer = prefix ? `${prefix} ${normalizedSpoken}` : normalizedSpoken;
            setAnswer(fullAnswer.trim());
          };

          recognition.onend = () => {
            if (mediaRecorderRef.current && mediaRecorderRef.current.state === 'recording') {
              try { recognition.start(); } catch (_) {}
            }
          };

          recognition.start();
          recognitionRef.current = recognition;
        } catch (e) {
          console.warn('Live recognition error:', e);
        }
      }
    } catch (err) {
      setIsRecording(false);
      setMicPermissionDenied(true);
    }
  };

  const stopRecording = () => {
    if (recognitionRef.current) {
      try { recognitionRef.current.stop(); } catch (_) {}
      recognitionRef.current = null;
    }
    if (mediaRecorderRef.current && mediaRecorderRef.current.state === 'recording') {
      setIsRecording(false);
      setIsTranscribing(true);
      mediaRecorderRef.current.stop();
    } else {
      setIsRecording(false);
      setIsTranscribing(false);
    }
  };

  const transcribeRecordedAudio = async (audioBlob) => {
    setIsTranscribing(true);
    setError('');
    try {
      const formData = new FormData();
      formData.append('file', audioBlob, 'candidate_answer.webm');
      const res = await api.post('/interviews/voice/transcribe', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });
      const rawTranscript = (res.data?.transcript || '').trim();
      const cleanTranscript = normalizeLiveTerms(rawTranscript);
      if (cleanTranscript) {
        const prefix = baseAnswerRef.current;
        const refined = prefix ? `${prefix} ${cleanTranscript}` : cleanTranscript;
        setAnswer(refined.trim());
      }
    } catch (err) {
      console.warn('Whisper STT error, preserving live speech text:', err);
    } finally {
      setIsTranscribing(false);
      setLiveInterimSnippet('');
    }
  };

  const handleSubmitAnswer = async () => {
    if (!currentQuestion || submitting) return;
    if (!answer.trim()) {
      setError('Please write or speak an answer before submitting.');
      return;
    }
    if (isRecording) stopRecording();
    stopAudioPlayback();
    setSubmitting(true);
    setError('');

    try {
      const res = await api.post(`/interviews/${id}/questions/${currentQuestion.id}/answer`, { answer_text: answer });
      const data = res.data;
      setQuestionsAnswered(data.questions_answered || (questionsAnswered + 1));
      
      if (data.is_complete) {
        setIsComplete(true);
        navigate(`/results/${id}`);
      } else if (data.next_question) {
        setCurrentQuestion(data.next_question);
        setAnswer('');
        baseAnswerRef.current = '';
        setLiveInterimSnippet('');
      }
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to submit answer');
    } finally {
      setSubmitting(false);
    }
  };

  const handleFinishInterview = async () => {
    if (!confirm('Are you sure you want to finish the interview now?')) return;
    stopAudioPlayback();
    if (isRecording) stopRecording();
    setFinishing(true);
    try {
      await api.post(`/interviews/${id}/complete`);
      navigate(`/results/${id}`);
    } catch (err) {
      setError('Failed to finish interview');
      setFinishing(false);
    }
  };

  const getBloomLabel = (level) => {
    const labels = { remember: 'Remember', understand: 'Understand', apply: 'Apply', analyze: 'Analyze', evaluate: 'Evaluate', create: 'Create' };
    return labels[level] || level || '';
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen bg-slate-50">
        <div className="text-center">
          <div className="animate-spin-slow rounded-full h-8 w-8 border-b-2 border-indigo-600 mx-auto mb-4"></div>
          <p className="text-slate-500 font-medium text-sm">Loading your interview...</p>
        </div>
      </div>
    );
  }

  if (error && !currentQuestion) {
    return (
      <div className="flex items-center justify-center min-h-screen bg-slate-50 p-4">
        <div className="card max-w-md w-full text-center p-8">
          <AlertCircle size={40} className="text-red-500 mx-auto mb-4" />
          <h2 className="text-xl font-bold text-slate-900 mb-2">Error</h2>
          <p className="text-slate-500 mb-6 text-sm">{error}</p>
          <button className="btn btn-primary w-full" onClick={() => navigate('/dashboard')}>Back to Dashboard</button>
        </div>
      </div>
    );
  }

  const currentQNum = currentQuestion?.question_number || 1;

  return (
    <div className="min-h-screen page-container flex flex-col fade-up">
      
      {/* Top Bar - Glassmorphism */}
      <div className="sticky top-0 z-10 bg-white/80 backdrop-blur-md border-b border-slate-200 shadow-sm">
        <div className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="h-16 flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="w-8 h-8 rounded-lg bg-indigo-500 flex items-center justify-center">
                <BrainCircuit size={18} className="text-white" />
              </div>
              <span className="font-bold text-lg text-slate-900 tracking-tight hidden sm:block">SmartInterview</span>
              <span className="badge badge-indigo ml-2 hidden sm:inline-flex shadow-sm">
                {session?.mode === 'syllabus' ? 'Syllabus Session' : 'Adaptive Session'}
              </span>
            </div>
            
            <div className="flex items-center gap-4">
              <div className="text-xs font-bold text-slate-500 bg-slate-100 px-3 py-1.5 rounded-full border border-slate-200">
                Question {currentQNum}
              </div>
              <button 
                onClick={handleFinishInterview} 
                disabled={finishing || submitting}
                className="btn bg-white text-slate-700 border border-slate-200 hover:bg-red-50 hover:text-red-600 hover:border-red-200 transition-colors py-1.5 shadow-sm"
              >
                {finishing ? <Loader2 size={16} className="animate-spin mr-1.5" /> : <Flag size={14} className="mr-1.5" />}
                Finish Interview
              </button>
            </div>
          </div>
        </div>
      </div>

      {/* Main Content */}
      <div className="flex-1 w-full max-w-4xl mx-auto px-4 py-8 sm:px-6 lg:px-8 flex flex-col">
        {currentQuestion && (
          <div className="flex flex-col flex-1 animate-[fadeIn_0.4s_ease-out]">
            
            {/* Metadata Badges */}
            <div className="flex flex-wrap gap-2 mb-4">
              <span className="badge badge-slate shadow-sm">
                {currentQuestion.skill}
              </span>
              <span className="badge badge-emerald capitalize shadow-sm">
                {currentQuestion.difficulty}
              </span>
              <span className="badge badge-amber capitalize shadow-sm">
                {(currentQuestion.question_type || '').replace(/_/g, ' ')}
              </span>
              {currentQuestion.bloom_level && (
                <span className="badge bg-purple-50 text-purple-700 border border-purple-200 flex items-center gap-1.5 shadow-sm">
                  <Brain size={12} />
                  {getBloomLabel(currentQuestion.bloom_level)}
                </span>
              )}
            </div>

            {/* Question Card */}
            <div className="card p-6 md:p-8 mb-6 border-t-4 border-t-indigo-600 shadow-sm relative overflow-hidden">
              
              <div className="flex items-center justify-between mb-4 relative z-10">
                <div className="text-xs font-extrabold text-indigo-600 tracking-wider">QUESTION {currentQNum}</div>
                
                {/* Voice Status Controls */}
                <div className="flex items-center gap-2">
                  {ttsLoading && (
                    <span className="badge badge-indigo">
                      <Loader2 size={12} className="animate-spin mr-1.5" /> Loading voice...
                    </span>
                  )}

                  {isSpeaking && (
                    <span className="badge bg-indigo-50 text-indigo-700 border border-indigo-200 shadow-sm">
                      <span className="w-1.5 h-1.5 rounded-full bg-indigo-600 mr-1.5 animate-pulse"></span>
                      Interviewer speaking
                      <button onClick={stopAudioPlayback} className="ml-2 text-[10px] text-slate-400 hover:text-indigo-600 underline cursor-pointer bg-transparent border-none">Skip</button>
                    </span>
                  )}

                  {autoplayBlocked && !isSpeaking && !ttsLoading && (
                    <button
                      onClick={() => playQuestionAudio(currentQuestion, currentQuestion.question_number === 1)}
                      className="btn btn-secondary text-xs py-1 text-indigo-600 border-indigo-200 hover:bg-indigo-50"
                    >
                      <Play size={12} className="fill-current" /> Listen
                    </button>
                  )}

                  {!isSpeaking && !ttsLoading && !autoplayBlocked && (
                    <button
                      onClick={() => playQuestionAudio(currentQuestion, false)}
                      className="btn btn-secondary text-xs py-1 shadow-sm"
                    >
                      <Volume2 size={12} /> Replay
                    </button>
                  )}
                </div>
              </div>

              <div className="text-lg md:text-xl font-bold text-slate-900 leading-relaxed relative z-10 prose prose-slate max-w-none prose-p:my-2 prose-ul:my-2 prose-ol:my-2 prose-pre:my-2 prose-pre:bg-slate-800 prose-pre:text-slate-100">
                <ReactMarkdown remarkPlugins={[remarkGfm]}>
                  {currentQuestion.question_text}
                </ReactMarkdown>
              </div>
            </div>

            {/* Answer Card */}
            <div className="card p-4 md:p-6 flex-1 flex flex-col mb-4 shadow-sm border border-slate-200">
              <div className="flex items-center justify-between mb-3">
                <label className="text-sm font-bold text-slate-800" htmlFor="answer-input">Your Answer</label>
                
                <div className="flex items-center gap-2">
                  {isRecording && (
                    <span className="badge badge-emerald shadow-sm">
                      <div className="wave-bars mr-1.5"><div className="wave-bar"></div><div className="wave-bar"></div><div className="wave-bar"></div><div className="wave-bar"></div></div>
                      Listening live...
                    </span>
                  )}
                  {isTranscribing && (
                    <span className="badge badge-indigo shadow-sm">
                      <Loader2 size={12} className="animate-spin mr-1.5" /> Refining terms...
                    </span>
                  )}
                </div>
              </div>

              <div className="relative flex-1 flex flex-col">
                <textarea
                  id="answer-input"
                  className="w-full flex-1 resize-y min-h-[200px] md:min-h-[250px] p-4 bg-slate-50 text-slate-900 border border-slate-200 rounded-xl focus:bg-white focus:outline-none focus:border-indigo-500 focus:ring-2 focus:ring-indigo-500/20 transition-all pr-16 text-base leading-relaxed placeholder-slate-400 font-medium"
                  value={answer}
                  onChange={e => { setAnswer(e.target.value); setError(''); }}
                  placeholder="Type your answer here, or click the microphone to speak live..."
                  disabled={submitting || isTranscribing}
                />

                <button
                  type="button"
                  onClick={isRecording ? stopRecording : startRecording}
                  disabled={submitting || isTranscribing}
                  className={`absolute top-3 right-3 p-3 rounded-xl transition-all shadow-sm ${
                    isRecording
                      ? "bg-emerald-500 text-white shadow-[0_0_0_4px_rgba(16,185,129,0.2)] animate-[pulse-dot_1.5s_infinite]"
                      : isTranscribing
                      ? "bg-slate-100 text-slate-400 cursor-not-allowed border border-slate-200"
                      : "bg-white text-slate-400 border border-slate-200 hover:text-indigo-600 hover:border-indigo-200 hover:bg-indigo-50"
                  }`}
                >
                  {isTranscribing ? <Loader2 size={20} className="animate-spin" /> 
                    : isRecording ? <Square size={20} className="fill-current" /> 
                    : <Mic size={20} />}
                </button>
              </div>

              {isRecording && liveInterimSnippet && (
                <div className="mt-3 text-xs text-emerald-700 bg-emerald-50 border border-emerald-200 rounded-lg px-3 py-2 flex items-center gap-2 shadow-sm">
                  <span className="font-bold uppercase tracking-wider text-[10px]">Live Voice</span>
                  <span className="italic truncate font-medium">{liveInterimSnippet}</span>
                </div>
              )}

              {micPermissionDenied && (
                <div className="mt-3 p-3 rounded-lg bg-amber-50 border border-amber-200 text-amber-700 text-xs flex items-center justify-between shadow-sm">
                  <span className="font-medium">Microphone access was denied. You can continue typing.</span>
                  <button onClick={() => setMicPermissionDenied(false)} className="text-amber-900 hover:underline font-bold ml-3 bg-transparent border-none cursor-pointer">Dismiss</button>
                </div>
              )}
              
              <div className="flex flex-col sm:flex-row justify-between items-center mt-5 gap-4">
                <span className="text-xs font-medium text-slate-500">
                  {answer.length} characters
                </span>
                <button
                  className="btn btn-primary w-full sm:w-auto px-8 py-3.5 shadow-[0_0_20px_rgba(79,70,229,0.3)] hover:shadow-[0_0_30px_rgba(79,70,229,0.5)]"
                  onClick={handleSubmitAnswer}
                  disabled={submitting || !answer.trim()}
                >
                  {submitting ? (
                    <><Loader2 size={18} className="animate-spin mr-2" /> Evaluating...</>
                  ) : (
                    <><span className="font-bold tracking-wide">Submit Answer</span> <Send size={16} className="ml-2" /></>
                  )}
                </button>
              </div>
              
              {error && (
                <div className="mt-4 p-3 rounded-lg bg-red-500/10 border border-red-500/20 text-red-400 text-sm flex items-center gap-2">
                  <AlertCircle size={16} /> {error}
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
