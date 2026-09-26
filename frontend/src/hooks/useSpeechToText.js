import { useState, useEffect, useRef, useCallback } from 'react';
import api from '../services/api';

export default function useSpeechToText(onTranscriptComplete) {
  const [status, setStatus] = useState('inactive'); // 'inactive', 'recording', 'transcribing'
  const [interimTexts, setInterimTexts] = useState(new Map());
  const [error, setError] = useState("");
  
  const mediaRecorderRef = useRef(null);
  const audioContextRef = useRef(null);
  const analyserRef = useRef(null);
  const chunksRef = useRef([]);
  
  const silenceStartRef = useRef(null);
  const isSpeakingRef = useRef(false);
  const isSegmentFinalizingRef = useRef(false);
  
  const animationFrameRef = useRef(null);
  const streamRef = useRef(null);
  
  const sttSessionIdRef = useRef(0);
  const segmentIdRef = useRef(0);
  const finalizedSegmentsRef = useRef(new Set());
  const latestSentVersionPerSegment = useRef({});
  const latestReceivedVersionPerSegment = useRef({});
  
  const isTranscribingInterimRef = useRef(false);
  
  const statusRef = useRef('inactive');
  useEffect(() => { statusRef.current = status; }, [status]);

  const getSupportedMimeType = () => {
    const types = [
      'audio/webm;codecs=opus',
      'audio/webm',
      'audio/mp4',
      'audio/ogg;codecs=opus',
      'audio/ogg'
    ];
    for (const t of types) {
      if (typeof MediaRecorder !== 'undefined' && MediaRecorder.isTypeSupported(t)) {
        return t;
      }
    }
    return '';
  };

  const cleanup = useCallback(() => {
    if (animationFrameRef.current) cancelAnimationFrame(animationFrameRef.current);
    if (mediaRecorderRef.current && mediaRecorderRef.current.state !== 'inactive') {
      mediaRecorderRef.current.onstop = null; 
      mediaRecorderRef.current.stop();
    }
    if (audioContextRef.current) {
      audioContextRef.current.close().catch(() => {});
      audioContextRef.current = null;
    }
    if (streamRef.current) {
      streamRef.current.getTracks().forEach(track => track.stop());
      streamRef.current = null;
    }
    setStatus('inactive');
    setInterimTexts(new Map());
    chunksRef.current = [];
    isSpeakingRef.current = false;
  }, []);

  const reset = useCallback(() => {
    cleanup();
    sttSessionIdRef.current++;
    segmentIdRef.current = 0;
    finalizedSegmentsRef.current = new Set();
    latestSentVersionPerSegment.current = {};
    latestReceivedVersionPerSegment.current = {};
    setInterimTexts(new Map());
    setError("");
  }, [cleanup]);

  const sendAudioToBackend = async (blob, isFinal, segmentId, sessionId) => {
    if (blob.size === 0) {
      if (isFinal && statusRef.current === 'transcribing') {
        setStatus('inactive');
      }
      return;
    }
    
    // Versioning to ignore stale out-of-order interim responses for this segment
    const version = (latestSentVersionPerSegment.current[segmentId] || 0) + 1;
    latestSentVersionPerSegment.current[segmentId] = version;
    
    if (!isFinal) {
      isTranscribingInterimRef.current = true;
    }
    
    const formData = new FormData();
    const extension = blob.type.includes('ogg')
      ? 'ogg'
      : blob.type.includes('mp4')
        ? 'mp4'
        : 'webm';
    formData.append('file', blob, `audio.${extension}`);
    
    try {
      const response = await api.post('/speech/transcribe', formData, {
        headers: { 'Content-Type': 'multipart/form-data' }
      });
      
      // Ignore response if the user transitioned to another question
      if (sessionId !== sttSessionIdRef.current) return;
      
      const text = response.data.text || "";
      
      if (isFinal) {
        finalizedSegmentsRef.current.add(segmentId);
        onTranscriptComplete(text);
        
        // Remove this segment's interim text once finalized
        setInterimTexts(prev => {
          const next = new Map(prev);
          next.delete(segmentId);
          return next;
        });
        
        if (statusRef.current === 'transcribing') {
          setStatus('inactive');
        }
      } else {
        // Ignore if this segment was already finalized (prevents slow interim from resurrecting it)
        if (finalizedSegmentsRef.current.has(segmentId)) return;
        
        // Only apply if this response is newer than what we've already rendered
        const received = latestReceivedVersionPerSegment.current[segmentId] || 0;
        if (version > received) {
          latestReceivedVersionPerSegment.current[segmentId] = version;
          setInterimTexts(prev => {
            const next = new Map(prev);
            next.set(segmentId, text);
            return next;
          });
        }
      }
    } catch (err) {
      console.error("Transcription error:", err);
      if (sessionId !== sttSessionIdRef.current) return;
      
      if (isFinal) {
        finalizedSegmentsRef.current.add(segmentId);
        
        // Fallback: if final transcription fails, commit the last known interim text so data isn't lost
        setInterimTexts(prev => {
          const next = new Map(prev);
          const fallbackText = next.get(segmentId);
          if (fallbackText) {
            onTranscriptComplete(fallbackText);
          }
          next.delete(segmentId);
          return next;
        });
        
        const detail = err.response?.data?.detail;
        setError(detail || "Failed to transcribe audio segment.");
        if (statusRef.current === 'transcribing') {
          setStatus('inactive');
        }
      }
    } finally {
      if (!isFinal) {
        isTranscribingInterimRef.current = false;
      }
    }
  };

  const checkAudio = useCallback(() => {
    if (!analyserRef.current || statusRef.current !== 'recording') return;
    
    const bufferLength = analyserRef.current.frequencyBinCount;
    const dataArray = new Uint8Array(bufferLength);
    analyserRef.current.getByteFrequencyData(dataArray);
    
    let sum = 0;
    for(let i = 0; i < bufferLength; i++) sum += dataArray[i];
    let average = sum / bufferLength;
    
    // Voice Activity Detection (VAD)
    if (average > 10) {
        silenceStartRef.current = Date.now();
        isSpeakingRef.current = true;
    } else {
        // 1000ms silence threshold to safely segment natural pauses
        if (isSpeakingRef.current && silenceStartRef.current && Date.now() - silenceStartRef.current > 1000) {
            isSpeakingRef.current = false;
            if (mediaRecorderRef.current && mediaRecorderRef.current.state === 'recording') {
              isSegmentFinalizingRef.current = true;
              mediaRecorderRef.current.stop(); 
            }
        }
    }
    
    animationFrameRef.current = requestAnimationFrame(checkAudio);
  }, []);

  const setupMediaRecorder = useCallback((stream) => {
    chunksRef.current = [];
    const mimeType = getSupportedMimeType();
    
    // Fallback gracefully if browser does not support MediaRecorder
    if (!mimeType) {
      setError("Your browser does not support audio recording.");
      setStatus('inactive');
      return;
    }
    
    const mediaRecorder = new MediaRecorder(stream, { mimeType });
    mediaRecorderRef.current = mediaRecorder;
    
    mediaRecorder.ondataavailable = (e) => {
      if (e.data.size > 0) chunksRef.current.push(e.data);
    };
    
    mediaRecorder.onstop = () => {
      const currentSegmentId = segmentIdRef.current;
      const currentSessionId = sttSessionIdRef.current;
      
      if (chunksRef.current.length > 0) {
        const blob = new Blob(chunksRef.current, { type: mimeType });
        sendAudioToBackend(blob, true, currentSegmentId, currentSessionId);
      } else {
        if (statusRef.current === 'transcribing') setStatus('inactive');
      }
      
      chunksRef.current = [];
      
      // If we stopped due to VAD natural pause, immediately start the next segment
      if (isSegmentFinalizingRef.current && statusRef.current === 'recording') {
        isSegmentFinalizingRef.current = false;
        segmentIdRef.current++;
        silenceStartRef.current = Date.now();
        setupMediaRecorder(streamRef.current);
      }
    };
    
    // Extract chunk every 1000ms (1 request per second) for low latency progressive updates
    mediaRecorder.start(1000); 
  }, [checkAudio]);

  const startRecording = useCallback(async () => {
    try {
      setError("");
      setStatus('recording');
      segmentIdRef.current++;
      
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      streamRef.current = stream;
      
      const AudioContext = window.AudioContext || window.webkitAudioContext;
      const audioCtx = new AudioContext();
      audioContextRef.current = audioCtx;
      
      const analyser = audioCtx.createAnalyser();
      analyser.fftSize = 512;
      analyserRef.current = analyser;
      
      const source = audioCtx.createMediaStreamSource(stream);
      source.connect(analyser);
      
      silenceStartRef.current = Date.now();
      isSpeakingRef.current = false;
      isSegmentFinalizingRef.current = false;
      
      setupMediaRecorder(stream);
      checkAudio();
      
    } catch (err) {
      console.error("Microphone permission error:", err);
      setError("Microphone access denied or unavailable.");
      setStatus('inactive');
    }
  }, [checkAudio, setupMediaRecorder]);

  const stopRecording = useCallback(() => {
    if (statusRef.current !== 'recording') return;
    
    setStatus('transcribing');
    isSegmentFinalizingRef.current = false;
    
    if (animationFrameRef.current) cancelAnimationFrame(animationFrameRef.current);
    
    if (mediaRecorderRef.current && mediaRecorderRef.current.state !== 'inactive') {
      mediaRecorderRef.current.stop(); 
    } else {
      setStatus('inactive');
    }
    
    // Do NOT stop the audio tracks immediately here!
    // The final chunks are still being processed in mediaRecorder.onstop asynchronously.
    // If we kill the stream tracks here, some browsers truncate the final audio chunk.
    // The cleanup() function will run safely when status transitions to 'inactive'.
  }, []);

  useEffect(() => {
    return () => { cleanup(); };
  }, [cleanup]);

  return {
    status,
    interimTexts,
    error,
    startRecording,
    stopRecording,
    reset
  };
}
