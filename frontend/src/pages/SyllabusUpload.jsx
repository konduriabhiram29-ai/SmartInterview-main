import { useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import api from '../services/api';
import {
  BookOpen,
  UploadCloud,
  FileText,
  X,
  CheckCircle2,
  AlertCircle,
  Play,
  ArrowRight,
  Loader2,
  Sparkles,
  Layers,
  Clock,
  RotateCcw,
} from 'lucide-react';

export default function SyllabusUpload() {
  const [uploadedFiles, setUploadedFiles] = useState([]);
  const [processing, setProcessing] = useState(false);
  const [processingStatus, setProcessingStatus] = useState('');
  const [processedData, setProcessedData] = useState(null);
  const [selectedTopics, setSelectedTopics] = useState([]);
  const [starting, setStarting] = useState(false);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);

  const fileInputRef = useRef(null);
  const navigate = useNavigate();

  useEffect(() => {
    // Check if user already has an active syllabus
    api.get('/interviews/syllabus/current')
      .then(res => {
        if (res.data?.syllabus_id) {
          setProcessedData(res.data);
          setSelectedTopics(res.data.topics || []);
        }
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  const handleFileSelect = (e) => {
    const files = Array.from(e.target?.files || e.dataTransfer?.files || []);
    if (!files.length) return;

    const allowed = ['.pdf', '.txt', '.docx'];
    const valid = files.filter(f => {
      const ext = f.name.slice(f.name.lastIndexOf('.')).toLowerCase();
      return allowed.includes(ext);
    });

    if (valid.length !== files.length) {
      setError('Only PDF, TXT, and DOCX files are supported.');
    } else {
      setError('');
    }

    setUploadedFiles(prev => {
      const names = new Set(prev.map(f => f.name));
      return [...prev, ...valid.filter(f => !names.has(f.name))];
    });

    if (e.target) e.target.value = '';
  };

  const removeFile = (name) => {
    setUploadedFiles(prev => prev.filter(f => f.name !== name));
    if (uploadedFiles.length <= 1) {
      setProcessedData(null);
      setSelectedTopics([]);
    }
  };

  const handleProcessMaterial = async () => {
    if (uploadedFiles.length === 0) {
      setError('Please upload at least one syllabus file first.');
      return;
    }
    setError('');
    setProcessing(true);
    setProcessedData(null);
    setSelectedTopics([]);

    const steps = [
      'Extracting document text...',
      'Inferring subject and key topics...',
      'Creating isolated vector knowledge base...',
      'Finalizing syllabus RAG...',
    ];
    let step = 0;
    setProcessingStatus(steps[step]);
    const interval = setInterval(() => {
      step = Math.min(step + 1, steps.length - 1);
      setProcessingStatus(steps[step]);
    }, 1500);

    try {
      const formData = new FormData();
      uploadedFiles.forEach(f => formData.append('files', f));

      const res = await api.post('/interviews/upload-syllabus', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });

      clearInterval(interval);
      setProcessingStatus('Ready');
      setProcessedData(res.data);
      setSelectedTopics(res.data.topics || []);
    } catch (err) {
      clearInterval(interval);
      setError(err.response?.data?.detail || 'Failed to process syllabus. Please try again.');
    } finally {
      setProcessing(false);
    }
  };

  const toggleTopic = (topic) => {
    setSelectedTopics(prev =>
      prev.includes(topic) ? prev.filter(t => t !== topic) : [...prev, topic]
    );
  };

  const selectAllTopics = () => {
    if (processedData?.topics) {
      if (selectedTopics.length === processedData.topics.length) {
        setSelectedTopics([]);
      } else {
        setSelectedTopics([...processedData.topics]);
      }
    }
  };

  const handleStartInterview = async () => {
    if (!processedData?.syllabus_id) {
      setError('Please upload and process syllabus material first.');
      return;
    }
    if (selectedTopics.length === 0) {
      setError('Please select at least one topic for your interview.');
      return;
    }

    setError('');
    setStarting(true);
    try {
      const payload = {
        mode: 'syllabus',
        syllabus_id: processedData.syllabus_id,
        selected_topics: selectedTopics,
        resume_id: null,
      };
      const res = await api.post('/interviews/start', payload);
      navigate(`/interview/${res.data.session_id}`);
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to start syllabus interview');
      setStarting(false);
    }
  };

  if (loading) {
    return (
      <div className="page-container flex items-center justify-center min-h-[60vh]">
        <div className="animate-spin-slow rounded-full h-8 w-8 border-b-2 border-indigo-600"></div>
      </div>
    );
  }

  return (
    <div className="page-container max-w-5xl fade-up">
      {/* Header */}
      <div className="page-header flex items-center gap-4 mb-8">
        <div className="w-14 h-14 rounded-2xl bg-indigo-50 border border-indigo-100 flex items-center justify-center text-indigo-600 shadow-sm">
          <BookOpen size={28} />
        </div>
        <div>
          <h1 className="page-title mb-1">Syllabus & Course Interview</h1>
          <p className="page-subtitle max-w-2xl">
            Upload your course syllabus, lecture slides, or exam reference material. Questions are strictly source-grounded in your documents.
          </p>
        </div>
      </div>

      {error && (
        <div className="error-banner mb-6 shadow-sm">
          {error}
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
        {/* Left Column: Upload & Files */}
        <div className="flex flex-col gap-6">
          <div className="card p-6 flex flex-col h-full shadow-sm border border-slate-100">
            <div className="flex items-center justify-between mb-5 border-b border-slate-100/60 pb-4">
              <h2 className="text-base font-bold text-slate-900 flex items-center gap-2">
                <UploadCloud size={18} className="text-indigo-600" />
                Course Material
              </h2>
              <span className="badge badge-indigo">PDF · DOCX · TXT</span>
            </div>

            {/* Dropzone */}
            <div
              onClick={() => fileInputRef.current?.click()}
              onDragOver={(e) => { e.preventDefault(); e.stopPropagation(); }}
              onDrop={(e) => { e.preventDefault(); e.stopPropagation(); handleFileSelect(e); }}
              className="flex-shrink-0 group border-2 border-dashed border-slate-300 hover:border-indigo-400 hover:bg-indigo-50/50 rounded-2xl p-8 text-center cursor-pointer transition-all duration-300 shadow-sm relative overflow-hidden"
            >
              <div className="w-16 h-16 rounded-full bg-slate-100 text-slate-400 flex items-center justify-center mx-auto mb-4 group-hover:scale-110 group-hover:bg-indigo-100 group-hover:text-indigo-600 transition-all">
                <UploadCloud size={32} />
              </div>
              <p className="text-base font-bold text-slate-900 mb-1">
                Click or drag files here
              </p>
              <p className="text-xs text-slate-500 max-w-[200px] mx-auto font-medium">
                Upload university syllabus, lecture notes, or reference docs (up to 20 MB each)
              </p>
              <input
                ref={fileInputRef}
                type="file"
                accept=".pdf,.docx,.txt"
                multiple
                className="hidden"
                onChange={handleFileSelect}
              />
            </div>

            {/* Uploaded Files List */}
            {uploadedFiles.length > 0 && (
              <div className="mt-6 flex-1 flex flex-col">
                <div className="eyebrow text-slate-500 mb-3 px-1">
                  Selected Files ({uploadedFiles.length})
                </div>
                <div className="space-y-2 flex-1 max-h-[160px] overflow-y-auto pr-1 custom-scrollbar">
                  {uploadedFiles.map((file) => (
                    <div
                      key={file.name}
                      className="flex items-center justify-between p-3.5 rounded-xl bg-slate-50/80 border border-slate-200/60 hover:border-slate-300 transition-colors shadow-sm"
                    >
                      <div className="flex items-center gap-3 min-w-0 flex-1">
                        <FileText size={18} className="text-indigo-500 shrink-0" />
                        <span className="text-sm font-semibold text-slate-900 truncate">{file.name}</span>
                      </div>
                      <div className="flex items-center gap-3 shrink-0 ml-3">
                        <span className="badge badge-slate text-[10px]">{(file.size / 1024).toFixed(0)} KB</span>
                        <button
                          type="button"
                          onClick={() => removeFile(file.name)}
                          className="text-slate-400 hover:text-red-500 p-1 rounded-md transition-colors hover:bg-red-50"
                          title="Remove file"
                        >
                          <X size={14} />
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Process Button */}
            {uploadedFiles.length > 0 && !processedData && (
              <button
                type="button"
                onClick={handleProcessMaterial}
                disabled={processing}
                className="mt-6 w-full btn btn-primary py-3.5 shadow-md flex items-center justify-center gap-2 transition-all"
              >
                {processing ? (
                  <>
                    <div className="animate-spin-slow rounded-full h-4 w-4 border-b-2 border-white"></div>
                    <span>{processingStatus}</span>
                  </>
                ) : (
                  <>
                    <Sparkles size={18} />
                    <span>Analyze & Extract Topics</span>
                  </>
                )}
              </button>
            )}

            {/* Processed Success Badge */}
            {processedData && (
              <div className="mt-6 p-5 rounded-xl bg-emerald-50/50 border border-emerald-200 shadow-sm relative overflow-hidden">
                <div className="absolute top-0 left-0 w-1 h-full bg-emerald-500"></div>
                <div className="flex items-center justify-between mb-3">
                  <div className="flex items-center gap-2 text-emerald-800 font-bold text-sm">
                    <CheckCircle2 size={18} className="text-emerald-600" />
                    <span>Material Processed</span>
                  </div>
                  <button
                    type="button"
                    onClick={() => {
                      setProcessedData(null);
                      setSelectedTopics([]);
                      setUploadedFiles([]);
                    }}
                    className="badge badge-emerald bg-white cursor-pointer hover:bg-emerald-50 transition-colors flex items-center gap-1.5"
                  >
                    <RotateCcw size={12} /> Reset
                  </button>
                </div>

                {processedData.metrics && (
                  <div className="pt-3 border-t border-emerald-200/60 flex flex-wrap items-center gap-2 text-[10px] text-emerald-700 font-extrabold uppercase tracking-widest">
                    <span className="flex items-center gap-1 bg-emerald-100/50 px-2 py-0.5 rounded">
                      <Clock size={12} /> Total: {processedData.metrics.total_elapsed_sec}s
                    </span>
                    <span className="px-1.5">• Extract: {processedData.metrics.stages?.extraction_sec}s</span>
                    <span className="px-1.5">• Topics: {processedData.metrics.stages?.topic_inference_sec}s</span>
                    <span className="px-1.5">• RAG DB: {processedData.metrics.stages?.embedding_and_chroma_sec}s</span>
                  </div>
                )}
              </div>
            )}
          </div>
        </div>

        {/* Right Column: Inferred Topics & Start Session */}
        <div className="flex flex-col gap-6">
          <div className="card p-6 flex flex-col h-full shadow-sm border border-slate-100">
            <div className="flex-1 flex flex-col">
              <div className="flex items-center justify-between mb-5 border-b border-slate-100/60 pb-4">
                <div>
                  <h2 className="text-base font-bold text-slate-900 flex items-center gap-2 mb-1">
                    <Layers size={18} className="text-indigo-600" />
                    Syllabus Topics
                  </h2>
                  <p className="text-[11px] font-bold text-slate-400 uppercase tracking-widest">
                    {processedData
                      ? `${selectedTopics.length} of ${processedData.topics?.length || 0} selected`
                      : 'Waiting for material'}
                  </p>
                </div>
                {processedData?.topics?.length > 0 && (
                  <button
                    type="button"
                    onClick={selectAllTopics}
                    className="badge badge-indigo bg-indigo-50 hover:bg-indigo-100 cursor-pointer transition-colors shadow-sm"
                  >
                    {selectedTopics.length === processedData.topics.length ? 'Deselect All' : 'Select All'}
                  </button>
                )}
              </div>

              {/* Subject Tag */}
              {processedData?.subject && (
                <div className="mb-5 px-4 py-3 rounded-xl bg-slate-50 border border-slate-200 flex items-center gap-3 shadow-sm">
                  <span className="w-8 h-8 rounded-lg bg-indigo-100 text-indigo-600 flex items-center justify-center shrink-0">
                    <BookOpen size={16} />
                  </span>
                  <div>
                    <div className="text-[10px] font-extrabold text-slate-400 uppercase tracking-widest mb-0.5">Course Subject</div>
                    <div className="text-sm font-black text-slate-900">{processedData.subject}</div>
                  </div>
                </div>
              )}

              {/* Topics Grid */}
              {processedData?.topics?.length > 0 ? (
                <div className="flex flex-wrap gap-2 pt-2 max-h-[300px] overflow-y-auto pr-2 custom-scrollbar">
                  {processedData.topics.map((topic) => {
                    const isSelected = selectedTopics.includes(topic);
                    return (
                      <button
                        key={topic}
                        type="button"
                        onClick={() => toggleTopic(topic)}
                        className={`px-4 py-2 text-xs font-bold rounded-xl cursor-pointer transition-all border shadow-sm ${
                          isSelected
                            ? 'bg-indigo-600 text-white border-indigo-600 drop-shadow-md scale-[1.02]'
                            : 'bg-white border-slate-200 text-slate-600 hover:border-indigo-300 hover:bg-indigo-50/30'
                        }`}
                      >
                        {topic}
                      </button>
                    );
                  })}
                </div>
              ) : (
                <div className="flex-1 flex flex-col items-center justify-center py-12 text-center">
                  <div className="w-20 h-20 rounded-full bg-slate-50 flex items-center justify-center mb-4 border border-slate-100">
                    <Layers size={32} className="text-slate-300" />
                  </div>
                  <h3 className="text-base font-bold text-slate-900 mb-1">No Topics Extracted</h3>
                  <p className="text-sm text-slate-500 max-w-[240px] font-medium leading-relaxed">
                    Upload your course document on the left and analyze it to view and select topics.
                  </p>
                </div>
              )}
            </div>

            {/* Start Button */}
            <div className="pt-6 border-t border-slate-100/60 mt-6 shrink-0">
              <button
                id="start-syllabus-interview-btn"
                type="button"
                onClick={handleStartInterview}
                disabled={starting || !processedData || selectedTopics.length === 0}
                className="btn btn-primary w-full py-4 text-sm font-bold shadow-md flex items-center justify-center gap-2 group transition-all"
              >
                {starting ? (
                  <>
                    <div className="animate-spin-slow rounded-full h-5 w-5 border-b-2 border-white"></div>
                    <span>Initializing Engine...</span>
                  </>
                ) : (
                  <>
                    <Play size={18} />
                    <span>Start Exam Preparation</span>
                    <ArrowRight size={18} className="group-hover:translate-x-1 transition-transform" />
                  </>
                )}
              </button>

              <div className="mt-4 flex items-center justify-center gap-2 text-xs font-semibold text-slate-500">
                <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse"></span>
                <span>Adaptive difficulty strictly grounded in your material</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
