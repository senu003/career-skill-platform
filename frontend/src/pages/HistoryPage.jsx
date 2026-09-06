import React, { useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  FileText, Briefcase, Plus, Upload, CheckCircle2, AlertCircle, ArrowRight,
  RefreshCw, Eye, RotateCcw, Sparkles, Building, Calendar, Layers, ShieldCheck,
  TrendingUp, X, Check, Award, BookOpen, AlertTriangle, Play
} from 'lucide-react';
import { fetchWithAuth } from '../api';
import { useAssessment } from '../context/AssessmentContext';
import { isSupportedSkill } from '../utils/supportedSkills';

export default function HistoryPage() {
  const navigate = useNavigate();
  const { setAnalysisResult } = useAssessment();
  const fileInputRef = useRef(null);

  // Core Data State
  const [savedCv, setSavedCv] = useState(null);
  const [pastSessions, setPastSessions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  // CV Uploading State
  const [uploadingCv, setUploadingCv] = useState(false);
  const [uploadSuccess, setUploadSuccess] = useState(false);

  // Modal States
  const [showNewAnalysisModal, setShowNewAnalysisModal] = useState(false);
  const [selectedSessionForRetake, setSelectedSessionForRetake] = useState(null);
  const [selectedSessionResult, setSelectedSessionResult] = useState(null);
  const [loadingSessionDetail, setLoadingSessionDetail] = useState(false);

  // New Analysis Intake Form State
  const [newAnalysisCvChoice, setNewAnalysisCvChoice] = useState('latest'); // 'latest' | 'new'
  const [newAnalysisFile, setNewAnalysisFile] = useState(null);
  const [newAnalysisJobTitle, setNewAnalysisJobTitle] = useState('');
  const [newAnalysisCompany, setNewAnalysisCompany] = useState('');
  const [newAnalysisJobDesc, setNewAnalysisJobDesc] = useState('');
  const [analyzingMatch, setAnalyzingMatch] = useState(false);
  const [intakeError, setIntakeError] = useState(null);

  // Load History & CV Data
  const loadData = async () => {
    setLoading(true);
    setError(null);
    try {
      // 1. Fetch Latest Saved CV
      try {
        const cvRes = await fetchWithAuth('/cv/latest');
        if (cvRes?.has_cv && cvRes.cv) {
          setSavedCv(cvRes.cv);
        } else {
          setSavedCv(null);
        }
      } catch (err) {
        console.warn('Could not fetch saved CV:', err);
      }

      // 2. Fetch Past Job Sessions
      try {
        const sessRes = await fetchWithAuth('/cv/sessions');
        if (sessRes?.sessions) {
          setPastSessions(sessRes.sessions);
        }
      } catch (err) {
        console.warn('Could not fetch past job sessions:', err);
      }
    } catch (err) {
      setError(err.message || 'Failed to load career history.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  // Format Helper: ISO date string to clean readable format
  const formatDate = (isoString) => {
    if (!isoString) return 'N/A';
    const d = new Date(isoString);
    return d.toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'long',
      day: 'numeric',
    });
  };

  // Helper for Readiness badge styling
  const getReadinessBadgeClass = (lvl) => {
    const clean = (lvl || '').toLowerCase();
    if (clean.includes('advanced') || clean.includes('expert')) return 'readiness-badge-advanced';
    if (clean.includes('intermediate')) return 'readiness-badge-intermediate';
    if (clean.includes('basic')) return 'readiness-badge-basic';
    return 'readiness-badge-foundational';
  };

  // Handle Direct Uploading of a New Default CV from Latest CV Card
  const handleUploadNewCvClick = () => {
    if (fileInputRef.current) {
      fileInputRef.current.click();
    }
  };

  const handleDirectCvUpload = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;

    if (file.type !== 'application/pdf' && !file.name.toLowerCase().endsWith('.pdf')) {
      alert('Please upload a valid PDF resume file.');
      return;
    }

    setUploadingCv(true);
    setUploadSuccess(false);
    try {
      const formData = new FormData();
      formData.append('file', file);

      const res = await fetchWithAuth('/cv/upload', {
        method: 'POST',
        body: formData,
      });

      setSavedCv({
        id: res.cv_id || res.id,
        file_name: res.filename || file.name,
        uploaded_at: new Date().toISOString(),
      });
      setUploadSuccess(true);
      setTimeout(() => setUploadSuccess(false), 4000);
    } catch (err) {
      alert(err.message || 'Failed to upload new CV.');
    } finally {
      setUploadingCv(false);
      e.target.value = '';
    }
  };

  // Action Handler: Open View Result Modal for a Session
  const handleViewResult = async (session) => {
    setLoadingSessionDetail(true);
    setSelectedSessionResult(null);
    try {
      const res = await fetchWithAuth(`/cv/sessions/${session.analysis_id}`);
      setSelectedSessionResult(res);
      setAnalysisResult(res);
    } catch (err) {
      alert(err.message || 'Failed to retrieve session analysis result.');
    } finally {
      setLoadingSessionDetail(false);
    }
  };

  // Action Handler: Open Retake Assessment Modal for a Session
  const handleOpenRetakeModal = (session) => {
    setSelectedSessionForRetake(session);
  };

  // Action Handler: Launch Technical MCQ Assessment for a Specific Skill
  const handleLaunchSkillAssessment = (skillName) => {
    setSelectedSessionForRetake(null);
    navigate(`/assessment/${encodeURIComponent(skillName)}`);
  };

  // Action Handler: Run New Analysis Intake
  const handleStartNewAnalysis = async (e) => {
    e.preventDefault();
    setIntakeError(null);

    if (newAnalysisCvChoice === 'new' && !newAnalysisFile) {
      setIntakeError('Please choose a PDF file to upload.');
      return;
    }

    if (newAnalysisCvChoice === 'latest' && !savedCv) {
      setIntakeError('No saved CV found. Please upload a new CV.');
      return;
    }

    if (!newAnalysisJobDesc.trim()) {
      setIntakeError('Please paste the job description text.');
      return;
    }

    setAnalyzingMatch(true);

    try {
      // 1. Extract requirements
      const reqRes = await fetchWithAuth('/requirements/analyze', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text: newAnalysisJobDesc.trim() }),
      });

      const extractedRequirements = reqRes.requirements || [];
      if (!Array.isArray(extractedRequirements) || extractedRequirements.length === 0) {
        throw new Error('No skill requirements could be extracted from the job description.');
      }

      // 2. Prepare multipart form data
      const formData = new FormData();
      if (newAnalysisCvChoice === 'new' && newAnalysisFile) {
        formData.append('file', newAnalysisFile);
      } else if (savedCv) {
        formData.append('cv_id', savedCv.id);
      }

      formData.append('requirements', JSON.stringify(extractedRequirements));
      if (newAnalysisJobTitle) formData.append('job_title', newAnalysisJobTitle);
      if (newAnalysisCompany) formData.append('company', newAnalysisCompany);

      // 3. Analyze CV against requirements
      const cvRes = await fetchWithAuth('/cv/analyze', {
        method: 'POST',
        body: formData,
      });

      // 4. Save result in context & close modal
      setAnalysisResult(cvRes);
      setShowNewAnalysisModal(false);

      // Reset form state
      setNewAnalysisFile(null);
      setNewAnalysisJobTitle('');
      setNewAnalysisCompany('');
      setNewAnalysisJobDesc('');

      // Reload sessions list & open result
      await loadData();
      setSelectedSessionResult(cvRes);
    } catch (err) {
      setIntakeError(err.message || 'Failed to analyze job match.');
    } finally {
      setAnalyzingMatch(false);
    }
  };

  // Loading Spinner View
  if (loading) {
    return (
      <div className="fade-in text-center" style={{ paddingTop: '5rem', paddingBottom: '5rem' }}>
        <div className="card" style={{ padding: '3.5rem 2rem', maxWidth: '540px', margin: '0 auto' }}>
          <div className="spinner spinner-dark mb-4" style={{ width: 44, height: 44, borderWidth: 3 }}></div>
          <h2 className="card-title mb-2" style={{ color: 'var(--text-main)' }}>Loading Analysis History</h2>
          <p className="text-muted text-sm">Fetching your previous job analysis records and saved CV...</p>
        </div>
      </div>
    );
  }

  // Error Alert View
  if (error) {
    return (
      <div className="fade-in" style={{ paddingTop: '3rem' }}>
        <div className="card text-center" style={{ padding: '3rem 2rem', maxWidth: '540px', margin: '0 auto' }}>
          <div className="alert-error flex items-center justify-center gap-2 mb-4">
            <AlertCircle size={20} />
            <span>{error}</span>
          </div>
          <h2 className="card-title mb-2">Unable to Load History</h2>
          <button onClick={loadData} className="btn btn-primary mt-2">
            <RefreshCw size={16} />
            <span>Try Again</span>
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="fade-in">
      {/* Hidden File Input for Direct CV Upload */}
      <input
        type="file"
        ref={fileInputRef}
        onChange={handleDirectCvUpload}
        accept=".pdf,application/pdf"
        style={{ display: 'none' }}
      />

      {/* 1. PAGE HEADER */}
      <div className="flex justify-between items-start flex-wrap gap-4 mb-6">
        <div>
          <h1 className="page-title mb-1" style={{ color: 'var(--text-main)', fontSize: '1.85rem' }}>
            History
          </h1>
          <p className="page-subtitle" style={{ color: 'var(--text-muted)' }}>
            View your previous career analyses, retake assessments, and compare your latest results.
          </p>
        </div>

        <button
          onClick={() => {
            setNewAnalysisCvChoice(savedCv ? 'latest' : 'new');
            setShowNewAnalysisModal(true);
          }}
          className="btn btn-primary"
          style={{ padding: '0.65rem 1.35rem', fontSize: '0.925rem' }}
        >
          <Plus size={18} />
          <span>+ New Analysis</span>
        </button>
      </div>

      {/* Success Banner for CV Upload */}
      {uploadSuccess && (
        <div className="alert-success flex items-center justify-between mb-4">
          <div className="flex items-center gap-2">
            <CheckCircle2 size={18} />
            <span>CV uploaded successfully! Made default resume for all future analyses.</span>
          </div>
          <button onClick={() => setUploadSuccess(false)} style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'inherit' }}>
            <X size={16} />
          </button>
        </div>
      )}

      {/* 2. LATEST CV MANAGEMENT SECTION */}
      <div className="cv-compact-card">
        <div className="flex items-center justify-between flex-wrap gap-4">
          <div className="flex items-center gap-4">
            <div className="cv-icon-box">
              <FileText size={24} />
            </div>

            <div>
              <div className="flex items-center gap-2 mb-0.5">
                <h2 className="font-bold text-base" style={{ color: 'var(--text-main)' }}>
                  Your Latest CV
                </h2>
                {savedCv && (
                  <span className="badge badge-success flex items-center gap-1">
                    <CheckCircle2 size={12} />
                    <span>Ready to use</span>
                  </span>
                )}
              </div>

              {savedCv ? (
                <div className="text-xs text-muted flex items-center gap-3">
                  <span className="font-semibold text-main" style={{ color: 'var(--text-main)' }}>{savedCv.file_name}</span>
                  <span>•</span>
                  <span>Uploaded {formatDate(savedCv.uploaded_at)}</span>
                </div>
              ) : (
                <p className="text-xs text-muted">No saved resume found. Upload your CV to reuse it for analyses.</p>
              )}
            </div>
          </div>

          {/* CV Actions */}
          <div className="flex items-center gap-2">
            <button
              onClick={handleUploadNewCvClick}
              disabled={uploadingCv}
              className="btn btn-outline text-xs"
              style={{ padding: '0.5rem 0.9rem' }}
            >
              {uploadingCv ? (
                <>
                  <span className="spinner spinner-dark" style={{ width: 14, height: 14 }}></span>
                  <span>Uploading...</span>
                </>
              ) : (
                <>
                  <Upload size={14} />
                  <span>Upload New CV</span>
                </>
              )}
            </button>

            {savedCv && (
              <button
                onClick={() => {
                  setNewAnalysisCvChoice('latest');
                  setShowNewAnalysisModal(true);
                }}
                className="btn btn-secondary text-xs"
                style={{ padding: '0.5rem 0.9rem' }}
              >
                <Play size={14} />
                <span>Use This CV</span>
              </button>
            )}
          </div>
        </div>

        {/* Small Explanation Text */}
        <p className="text-xs text-muted mt-3 pt-2" style={{ borderTop: '1px solid var(--primary-200)', lineHeight: 1.4 }}>
          You can upload your latest CV once and reuse it for future analyses. You don't need to upload it every time.
        </p>
      </div>

      {/* 3. PREVIOUS ANALYSES HISTORY LIST */}
      <div className="mb-8">
        <div className="flex items-center justify-between mb-4">
          <h2 className="card-title mb-0" style={{ fontSize: '1.2rem' }}>
            Previous Analyses
          </h2>
          <span className="text-xs text-muted font-medium">
            {pastSessions.length} {pastSessions.length === 1 ? 'Job Analysis' : 'Job Analyses'} Recorded
          </span>
        </div>

        {pastSessions.length === 0 ? (
          /* EMPTY HISTORY STATE */
          <div className="empty-history-card">
            <div
              style={{
                width: 56,
                height: 56,
                borderRadius: '50%',
                backgroundColor: 'var(--primary-100)',
                color: 'var(--primary-600)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                margin: '0 auto 1.25rem auto',
              }}
            >
              <Briefcase size={28} />
            </div>
            <h3 className="font-bold text-lg text-main mb-1">No analyses yet</h3>
            <p className="text-muted text-sm mb-6" style={{ maxWidth: '420px', margin: '0 auto 1.5rem auto' }}>
              Upload your CV and analyze your first job opportunity to see your career readiness.
            </p>
            <button
              onClick={() => {
                setNewAnalysisCvChoice(savedCv ? 'latest' : 'new');
                setShowNewAnalysisModal(true);
              }}
              className="btn btn-primary"
              style={{ padding: '0.7rem 1.5rem' }}
            >
              <Plus size={18} />
              <span>Start Your First Analysis</span>
            </button>
          </div>
        ) : (
          /* PAST SESSIONS CARDS */
          <div className="flex flex-col gap-4">
            {pastSessions.map((sess) => {
              const scoreVal = sess.overall_score !== null && sess.overall_score !== undefined ? Math.round(sess.overall_score) : 0;
              const readinessBadgeClass = getReadinessBadgeClass(sess.overall_readiness);

              return (
                <div key={sess.analysis_id} className="history-session-card">
                  <div className="flex justify-between items-start flex-wrap gap-4">
                    {/* Left Column: Job Info & Match Metrics */}
                    <div className="flex items-start gap-4" style={{ flex: '1 1 340px' }}>
                      {/* Overall Job Match Score Pill */}
                      <div className="session-score-pill">
                        <span className="text-xs text-muted font-semibold uppercase tracking-wider" style={{ fontSize: '0.65rem' }}>
                          Overall Match
                        </span>
                        <div className="session-score-value mt-1">
                          {scoreVal}%
                        </div>
                      </div>

                      {/* Job Title & Metadata */}
                      <div>
                        <div className="flex items-center gap-2.5 flex-wrap mb-1">
                          <h3 className="font-bold text-lg text-main flex items-center gap-2" style={{ margin: 0 }}>
                            <Briefcase size={18} style={{ color: 'var(--primary-600)' }} />
                            <span>{sess.job_title}</span>
                          </h3>
                          {sess.company && (
                            <span className="badge badge-purple" style={{ fontSize: '0.75rem' }}>
                              {sess.company}
                            </span>
                          )}
                        </div>

                        {/* Metadata row: CV & Date */}
                        <div className="text-xs text-muted flex items-center gap-4 flex-wrap mb-2.5">
                          <div className="flex items-center gap-1.5">
                            <FileText size={13} style={{ color: 'var(--primary-500)' }} />
                            <span>CV: <strong>{sess.cv_filename}</strong></span>
                          </div>
                          <div className="flex items-center gap-1.5">
                            <Calendar size={13} style={{ color: 'var(--primary-500)' }} />
                            <span>Analyzed: {formatDate(sess.created_at)}</span>
                          </div>
                        </div>

                        {/* Metrics Row: Assessment Status & Readiness Level */}
                        <div className="flex items-center gap-3 flex-wrap mb-2">
                          <span className="text-xs text-muted">
                            Assessment: <strong className="text-main">{sess.assessment_status || 'Completed'}</strong>
                          </span>
                          <span className="text-xs text-muted">•</span>
                          <span className="text-xs text-muted flex items-center gap-1">
                            Overall Readiness:
                            <span className={`readiness-badge ${readinessBadgeClass}`}>
                              {sess.overall_readiness || 'Intermediate'}
                            </span>
                          </span>
                        </div>

                        {/* Summary String */}
                        <p className="text-xs font-medium text-main flex items-center gap-1.5" style={{ color: 'var(--text-body)' }}>
                          <span>
                            {sess.total_skills_count || sess.parsed_skills?.length || 0} skills analyzed
                          </span>
                          <span>•</span>
                          <span style={{ color: 'var(--success-color)' }}>
                            {sess.matched_skills_count || 0} matched
                          </span>
                          <span>•</span>
                          <span style={{ color: sess.improvement_skills_count > 0 ? '#d97706' : 'var(--text-muted)' }}>
                            {sess.improvement_skills_count || 0} skills need improvement
                          </span>
                        </p>
                      </div>
                    </div>

                    {/* Right Column: Status Badge & Actions */}
                    <div className="flex flex-col items-end gap-3" style={{ minWidth: '170px' }}>
                      <span className="badge badge-success flex items-center gap-1" style={{ padding: '0.3rem 0.75rem', fontSize: '0.75rem' }}>
                        <CheckCircle2 size={13} />
                        <span>{sess.status_badge || 'Analysis Complete'}</span>
                      </span>

                      <div className="flex items-center gap-2 mt-1">
                        <button
                          onClick={() => handleViewResult(sess)}
                          disabled={loadingSessionDetail}
                          className="btn btn-outline text-xs"
                          style={{ padding: '0.5rem 0.85rem' }}
                        >
                          <Eye size={14} />
                          <span>View Result</span>
                        </button>

                        <button
                          onClick={() => handleOpenRetakeModal(sess)}
                          className="btn btn-primary text-xs"
                          style={{ padding: '0.5rem 0.85rem' }}
                        >
                          <RotateCcw size={14} />
                          <span>Retake Assessment</span>
                        </button>
                      </div>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* 4. VIEW RESULT MODAL */}
      {selectedSessionResult && (
        <div className="modal-overlay" onClick={() => setSelectedSessionResult(null)}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()} style={{ maxWidth: '840px' }}>
            <div className="flex items-center justify-between mb-4 border-b pb-3" style={{ borderColor: 'var(--border-color)' }}>
              <div>
                <span className="badge badge-purple mb-1">Historical Result Summary</span>
                <h2 className="font-bold text-xl text-main" style={{ margin: 0 }}>
                  {selectedSessionResult.job_title} {selectedSessionResult.company ? `— ${selectedSessionResult.company}` : ''}
                </h2>
              </div>
              <button
                onClick={() => setSelectedSessionResult(null)}
                className="btn btn-outline"
                style={{ padding: '0.35rem', borderRadius: '50%', width: 32, height: 32 }}
              >
                <X size={18} />
              </button>
            </div>

            {/* Overall Score & Verdict Banner */}
            <div className="match-score-card mb-4" style={{ padding: '1.25rem 1.5rem' }}>
              <div>
                <div className="text-xs uppercase font-semibold opacity-90">Overall Job Match</div>
                <div className="match-score-val mt-1" style={{ fontSize: '2.25rem' }}>
                  {selectedSessionResult.score_data?.score !== undefined ? `${Math.round(selectedSessionResult.score_data.score)}%` : 'N/A'}
                </div>
                <div className="text-xs mt-1 opacity-90">
                  {selectedSessionResult.final_verdict || 'Evaluation Complete'}
                </div>
              </div>

              <div className="flex items-center gap-3">
                <div className="match-stat-item">
                  <div className="text-xs opacity-80">Matched</div>
                  <div className="font-bold text-base">{selectedSessionResult.score_data?.matched_count || 0}</div>
                </div>
                <div className="match-stat-item">
                  <div className="text-xs opacity-80">Missing / Weak</div>
                  <div className="font-bold text-base">{selectedSessionResult.score_data?.missing_count || 0}</div>
                </div>
                <div className="match-stat-item">
                  <div className="text-xs opacity-80">Total Skills</div>
                  <div className="font-bold text-base">{selectedSessionResult.score_data?.total_skills || 0}</div>
                </div>
              </div>
            </div>

            {/* Skill Breakdown */}
            <div className="mb-4">
              <h3 className="text-sm font-bold uppercase tracking-wider text-muted mb-2">
                Skill Breakdown ({selectedSessionResult.skills?.length || 0})
              </h3>
              <div className="flex flex-col gap-2" style={{ maxHeight: '280px', overflowY: 'auto' }}>
                {(selectedSessionResult.skills || []).map((sk, idx) => (
                  <div
                    key={idx}
                    className="flex items-center justify-between p-3 rounded text-xs"
                    style={{
                      backgroundColor: 'var(--primary-50)',
                      border: '1px solid var(--primary-200)',
                    }}
                  >
                    <div className="flex items-center gap-3">
                      <span className="font-bold text-main">{sk.skill}</span>
                      <span className="badge badge-purple">{sk.required_level || sk.level || 'Basic'}</span>
                    </div>

                    <div className="flex items-center gap-4">
                      <span>Assessed: <strong>{sk.assessed_level ? (sk.assessed_level.charAt(0).toUpperCase() + sk.assessed_level.slice(1)) : 'Not Assessed'}</strong></span>
                      <span
                        className="badge"
                        style={{
                          backgroundColor: sk.matched && !sk.is_weakness ? 'var(--success-bg)' : 'var(--warning-bg)',
                          color: sk.matched && !sk.is_weakness ? 'var(--success-color)' : '#b45309',
                        }}
                      >
                        {sk.matched && !sk.is_weakness ? 'Matched' : 'Needs Improvement'}
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* Footer Actions */}
            <div className="flex justify-between items-center border-t pt-3" style={{ borderColor: 'var(--border-color)' }}>
              <button
                onClick={() => {
                  setSelectedSessionResult(null);
                  navigate('/recommendation');
                }}
                className="btn btn-secondary text-xs flex items-center gap-1.5"
              >
                <Sparkles size={14} />
                <span>Open Recommendation Page</span>
              </button>

              <button onClick={() => setSelectedSessionResult(null)} className="btn btn-primary text-xs">
                Close
              </button>
            </div>
          </div>
        </div>
      )}

      {/* 5. RETAKE ASSESSMENT MODAL */}
      {selectedSessionForRetake && (
        <div className="modal-overlay" onClick={() => setSelectedSessionForRetake(null)}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()} style={{ maxWidth: '640px' }}>
            <div className="flex items-center justify-between mb-4 border-b pb-3" style={{ borderColor: 'var(--border-color)' }}>
              <div>
                <h2 className="font-bold text-lg text-main flex items-center gap-2" style={{ margin: 0 }}>
                  <RotateCcw size={18} style={{ color: 'var(--primary-600)' }} />
                  <span>Retake Skill Assessment</span>
                </h2>
                <p className="text-xs text-muted mt-0.5">
                  Redo assessments for skills in {selectedSessionForRetake.job_title}. Original history will be preserved.
                </p>
              </div>
              <button
                onClick={() => setSelectedSessionForRetake(null)}
                className="btn btn-outline"
                style={{ padding: '0.35rem', borderRadius: '50%', width: 32, height: 32 }}
              >
                <X size={18} />
              </button>
            </div>

            {/* Skills Available to Retake */}
            <div className="mb-4">
              <h3 className="text-xs font-bold uppercase tracking-wider text-muted mb-2">
                Job Requirements & Technical Assessment Status
              </h3>

              <div className="flex flex-col gap-2">
                {(selectedSessionForRetake.parsed_skills || []).map((skItem, idx) => {
                  const skillName = typeof skItem === 'string' ? skItem : skItem.skill;
                  const supported = isSupportedSkill(skillName);
                  const reqLvl = typeof skItem === 'object' ? skItem.level : 'Intermediate';

                  return (
                    <div
                      key={idx}
                      className="flex items-center justify-between p-3 rounded"
                      style={{
                        backgroundColor: supported ? 'var(--primary-50)' : '#f8fafc',
                        border: supported ? '1px solid var(--primary-200)' : '1px solid var(--border-color)',
                      }}
                    >
                      <div>
                        <div className="font-semibold text-sm text-main flex items-center gap-2">
                          <span>{skillName}</span>
                          {!supported && (
                            <span className="text-xs text-muted font-normal" style={{ fontSize: '0.7rem' }}>
                              (Assessment Unavailable)
                            </span>
                          )}
                        </div>
                        <div className="text-xs text-muted">Required Level: {reqLvl}</div>
                      </div>

                      {supported ? (
                        <button
                          onClick={() => handleLaunchSkillAssessment(skillName)}
                          className="btn btn-primary text-xs flex items-center gap-1.5"
                          style={{ padding: '0.35rem 0.75rem' }}
                        >
                          <Play size={13} />
                          <span>Redo Test</span>
                        </button>
                      ) : (
                        <button disabled className="btn btn-outline text-xs" style={{ opacity: 0.5, cursor: 'not-allowed', padding: '0.35rem 0.75rem' }}>
                          Unavailable
                        </button>
                      )}
                    </div>
                  );
                })}
              </div>
            </div>

            <div className="flex justify-end pt-2">
              <button onClick={() => setSelectedSessionForRetake(null)} className="btn btn-outline text-xs">
                Cancel
              </button>
            </div>
          </div>
        </div>
      )}

      {/* 6. NEW ANALYSIS / CV REUSE MODAL */}
      {showNewAnalysisModal && (
        <div className="modal-overlay" onClick={() => setShowNewAnalysisModal(false)}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()} style={{ maxWidth: '680px' }}>
            <div className="flex items-center justify-between mb-4 border-b pb-3" style={{ borderColor: 'var(--border-color)' }}>
              <div>
                <h2 className="font-bold text-xl text-main" style={{ margin: 0 }}>
                  Start New Career Skill Analysis
                </h2>
                <p className="text-xs text-muted mt-0.5">
                  Select your CV option and paste the job description to calculate candidate readiness.
                </p>
              </div>
              <button
                onClick={() => setShowNewAnalysisModal(false)}
                className="btn btn-outline"
                style={{ padding: '0.35rem', borderRadius: '50%', width: 32, height: 32 }}
              >
                <X size={18} />
              </button>
            </div>

            {intakeError && (
              <div className="alert-error flex items-center gap-2 mb-3">
                <AlertCircle size={16} />
                <span>{intakeError}</span>
              </div>
            )}

            <form onSubmit={handleStartNewAnalysis} className="flex flex-col gap-4">
              {/* CV Selection Step */}
              <div>
                <label className="form-label mb-2">1. Choose CV / Resume</label>

                <div className="grid grid-cols-2 gap-3">
                  {/* Option 1: Use Saved CV */}
                  <div
                    onClick={() => savedCv && setNewAnalysisCvChoice('latest')}
                    className={`option-card ${newAnalysisCvChoice === 'latest' ? 'selected' : ''} ${!savedCv ? 'disabled' : ''}`}
                    style={{ padding: '0.85rem 1rem' }}
                  >
                    <div className="option-badge" style={{ width: 24, height: 24, fontSize: '0.75rem' }}>
                      {newAnalysisCvChoice === 'latest' ? <Check size={14} /> : '1'}
                    </div>
                    <div>
                      <div className="font-semibold text-xs text-main">Use Saved CV</div>
                      <div className="text-xs text-muted" style={{ fontSize: '0.7rem' }}>
                        {savedCv ? savedCv.file_name : 'No saved CV available'}
                      </div>
                    </div>
                  </div>

                  {/* Option 2: Upload New CV */}
                  <div
                    onClick={() => setNewAnalysisCvChoice('new')}
                    className={`option-card ${newAnalysisCvChoice === 'new' ? 'selected' : ''}`}
                    style={{ padding: '0.85rem 1rem' }}
                  >
                    <div className="option-badge" style={{ width: 24, height: 24, fontSize: '0.75rem' }}>
                      {newAnalysisCvChoice === 'new' ? <Check size={14} /> : '2'}
                    </div>
                    <div>
                      <div className="font-semibold text-xs text-main">Upload New CV</div>
                      <div className="text-xs text-muted" style={{ fontSize: '0.7rem' }}>Select PDF file</div>
                    </div>
                  </div>
                </div>

                {newAnalysisCvChoice === 'new' && (
                  <div className="mt-3">
                    <input
                      type="file"
                      accept=".pdf,application/pdf"
                      onChange={(e) => setNewAnalysisFile(e.target.files?.[0] || null)}
                      className="input text-xs"
                      style={{ padding: '0.5rem' }}
                    />
                  </div>
                )}
              </div>

              {/* Job Details Step */}
              <div className="grid grid-cols-2 gap-3">
                <div className="form-group" style={{ marginBottom: 0 }}>
                  <label className="form-label">Job Title</label>
                  <input
                    type="text"
                    className="input"
                    placeholder="e.g. Software Engineer"
                    value={newAnalysisJobTitle}
                    onChange={(e) => setNewAnalysisJobTitle(e.target.value)}
                  />
                </div>

                <div className="form-group" style={{ marginBottom: 0 }}>
                  <label className="form-label">Company Name <span className="text-muted font-normal">(Optional)</span></label>
                  <input
                    type="text"
                    className="input"
                    placeholder="e.g. ABC Technologies"
                    value={newAnalysisCompany}
                    onChange={(e) => setNewAnalysisCompany(e.target.value)}
                  />
                </div>
              </div>

              <div className="form-group" style={{ marginBottom: 0 }}>
                <label className="form-label">Job Description *</label>
                <textarea
                  className="textarea"
                  rows={5}
                  placeholder="Paste job description requirements text here..."
                  value={newAnalysisJobDesc}
                  onChange={(e) => setNewAnalysisJobDesc(e.target.value)}
                  required
                />
              </div>

              {/* Modal Actions */}
              <div className="flex justify-end gap-3 pt-2">
                <button
                  type="button"
                  onClick={() => setShowNewAnalysisModal(false)}
                  className="btn btn-outline text-xs"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={analyzingMatch}
                  className="btn btn-primary text-xs"
                  style={{ padding: '0.65rem 1.25rem' }}
                >
                  {analyzingMatch ? (
                    <>
                      <span className="spinner" style={{ width: 14, height: 14 }}></span>
                      <span>Analyzing...</span>
                    </>
                  ) : (
                    <>
                      <span>Analyze Job Match</span>
                      <ArrowRight size={14} />
                    </>
                  )}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
