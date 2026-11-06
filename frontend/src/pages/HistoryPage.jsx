import React, { useState, useEffect, useRef, useMemo } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import {
  FileText, Briefcase, Plus, Upload, CheckCircle2, AlertCircle, ArrowRight,
  RefreshCw, Calendar, X, Layers, Check, Download, Trash2, Star
} from 'lucide-react';
import { fetchWithAuth, downloadCvFile } from '../api';
import { useAssessment } from '../context/AssessmentContext';

export default function HistoryPage() {
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const activeTab = searchParams.get('tab') || 'resumes';
  const setActiveTab = (tab) => {
    setSearchParams({ tab });
  };
  const { setAnalysisResult } = useAssessment();
  const fileInputRef = useRef(null);

  // Core Data State
  const [cvList, setCvList] = useState([]);
  const [savedCv, setSavedCv] = useState(null);
  const [selectedCvId, setSelectedCvId] = useState('');
  const [pastSessions, setPastSessions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  // Action / Feedback State
  const [uploadingCv, setUploadingCv] = useState(false);
  const [uploadSuccess, setUploadSuccess] = useState(null);
  const [actionError, setActionError] = useState(null);
  const [downloadingCvId, setDownloadingCvId] = useState(null);

  // Modal States
  const [showNewAnalysisModal, setShowNewAnalysisModal] = useState(false);

  // New Analysis Intake Form State
  const [newAnalysisCvChoice, setNewAnalysisCvChoice] = useState('saved'); // 'saved' | 'new'
  const [newAnalysisFile, setNewAnalysisFile] = useState(null);
  const [newAnalysisJobTitle, setNewAnalysisJobTitle] = useState('');
  const [newAnalysisCompany, setNewAnalysisCompany] = useState('');
  const [newAnalysisJobDesc, setNewAnalysisJobDesc] = useState('');
  const [analyzingMatch, setAnalyzingMatch] = useState(false);
  const [intakeError, setIntakeError] = useState(null);
  const [historySubmissionKey, setHistorySubmissionKey] = useState(null);

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

  // Load All History & CV Data
  const loadData = async () => {
    setLoading(true);
    setError(null);
    try {
      // 1. Fetch All Uploaded CVs
      try {
        const cvRes = await fetchWithAuth('/cv/all');
        if (cvRes?.has_cv && Array.isArray(cvRes.cvs)) {
          setCvList(cvRes.cvs);
          const defaultCv = cvRes.cvs.find((c) => c.is_default) || cvRes.cvs[0];
          setSavedCv(defaultCv);
          setSelectedCvId(defaultCv ? defaultCv.id : '');
        } else {
          setCvList([]);
          setSavedCv(null);
          setSelectedCvId('');
        }
      } catch (err) {
        console.warn('Could not fetch all CVs, attempting fallback to /cv/latest:', err);
        try {
          const fallbackRes = await fetchWithAuth('/cv/latest');
          if (fallbackRes?.has_cv && fallbackRes.cv) {
            const singleCv = { ...fallbackRes.cv, is_default: true, analyses_count: 0 };
            setCvList([singleCv]);
            setSavedCv(fallbackRes.cv);
            setSelectedCvId(fallbackRes.cv.id);
          } else {
            setCvList([]);
            setSavedCv(null);
            setSelectedCvId('');
          }
        } catch (fbErr) {
          console.warn('Could not fetch fallback latest CV:', fbErr);
        }
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

  // Trigger hidden file input
  const handleUploadNewCvClick = () => {
    if (fileInputRef.current) {
      fileInputRef.current.click();
    }
  };

  // Direct CV Upload handler
  const handleDirectCvUpload = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;

    if (file.type !== 'application/pdf' && !file.name.toLowerCase().endsWith('.pdf')) {
      setActionError('Please upload a valid PDF resume file.');
      return;
    }

    setUploadingCv(true);
    setUploadSuccess(null);
    setActionError(null);
    try {
      const formData = new FormData();
      formData.append('file', file);

      const res = await fetchWithAuth('/cv/upload', {
        method: 'POST',
        body: formData,
      });

      const uploadedName = res.filename || file.name;
      setUploadSuccess(`Resume "${uploadedName}" uploaded successfully and saved!`);
      await loadData();
      setTimeout(() => setUploadSuccess(null), 5000);
    } catch (err) {
      setActionError(err.message || 'Failed to upload new resume.');
    } finally {
      setUploadingCv(false);
      if (e.target) e.target.value = '';
    }
  };

  // Set as Default CV
  const handleSetDefaultCv = async (cv, e) => {
    if (e) e.stopPropagation();
    setActionError(null);
    try {
      await fetchWithAuth(`/cv/${cv.id}/set-default`, { method: 'POST' });
      await loadData();
    } catch (err) {
      setActionError(err.message || 'Failed to set resume as default.');
    }
  };

  // Download CV file
  const handleDownloadCv = async (cv, e) => {
    if (e) e.stopPropagation();
    setActionError(null);
    setDownloadingCvId(cv.id);
    try {
      await downloadCvFile(cv.id, cv.file_name);
    } catch (err) {
      setActionError(err.message || 'Failed to download resume file.');
    } finally {
      setDownloadingCvId(null);
    }
  };

  // Delete CV file
  const handleDeleteCv = async (cv, e) => {
    if (e) e.stopPropagation();
    if (cv.analyses_count > 0) {
      setActionError(`Cannot delete "${cv.file_name}" because it is linked to ${cv.analyses_count} job analysis session(s).`);
      return;
    }
    if (!window.confirm(`Are you sure you want to remove "${cv.file_name}"?`)) {
      return;
    }
    setActionError(null);
    try {
      await fetchWithAuth(`/cv/${cv.id}`, { method: 'DELETE' });
      await loadData();
    } catch (err) {
      setActionError(err.message || 'Failed to delete resume.');
    }
  };

  // Pre-select CV and open New Analysis modal
  const handleStartAnalysisWithCv = (cv, e) => {
    if (e) e.stopPropagation();
    setSelectedCvId(cv.id);
    setNewAnalysisCvChoice('saved');
    setShowNewAnalysisModal(true);
  };

  // Action Handler: Open full CV & JD Diagnostic Grid on Dashboard
  const handleOpenDiagnosticGrid = async (session, e) => {
    if (e) e.stopPropagation();
    try {
      const res = await fetchWithAuth(`/cv/sessions/${session.analysis_id}`);
      if (res) {
        setAnalysisResult(res);
      }
    } catch (err) {
      console.warn('Session detail fetch error:', err);
    }
    navigate(`/dashboard?analysis_id=${session.analysis_id}`);
  };

  // Action Handler: Run New Analysis Intake
  const handleStartNewAnalysis = async (e) => {
    e.preventDefault();
    setIntakeError(null);

    if (newAnalysisCvChoice === 'new' && !newAnalysisFile) {
      setIntakeError('Please choose a PDF file to upload.');
      return;
    }

    const cvToUseId = selectedCvId || savedCv?.id;
    if (newAnalysisCvChoice === 'saved' && !cvToUseId) {
      setIntakeError('No saved resume found. Please upload a new CV.');
      return;
    }

    if (!newAnalysisJobDesc.trim()) {
      setIntakeError('Please paste the job description text.');
      return;
    }

    setAnalyzingMatch(true);
    const activeKey = historySubmissionKey || (typeof crypto !== 'undefined' && crypto.randomUUID ? crypto.randomUUID() : `hist_${Date.now()}_${Math.random().toString(36).substring(2, 9)}`);
    setHistorySubmissionKey(activeKey);

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
      } else if (cvToUseId) {
        formData.append('cv_id', cvToUseId);
      }

      formData.append('requirements', JSON.stringify(extractedRequirements));
      if (newAnalysisJobTitle) formData.append('job_title', newAnalysisJobTitle);
      if (newAnalysisCompany) formData.append('company', newAnalysisCompany);
      formData.append('idempotency_key', activeKey);

      // 3. Analyze CV against requirements
      const cvRes = await fetchWithAuth('/cv/analyze', {
        method: 'POST',
        headers: {
          'Idempotency-Key': activeKey,
        },
        body: formData,
      });

      // 4. Save result in context & close modal
      setAnalysisResult(cvRes);
      setShowNewAnalysisModal(false);
      setHistorySubmissionKey(null);

      // Reset form state
      setNewAnalysisFile(null);
      setNewAnalysisJobTitle('');
      setNewAnalysisCompany('');
      setNewAnalysisJobDesc('');

      // Reload sessions list & navigate directly to Diagnostic Grid
      await loadData();
      navigate(`/dashboard?analysis_id=${cvRes.analysis_id}`);
    } catch (err) {
      setIntakeError(err.message || 'Failed to analyze job match.');
    } finally {
      setAnalyzingMatch(false);
    }
  };

  // Sort past sessions by date (most recent first)
  const sortedSessions = useMemo(() => {
    return [...pastSessions].sort((a, b) => new Date(b.created_at || 0) - new Date(a.created_at || 0));
  }, [pastSessions]);

  // Loading Spinner View
  if (loading) {
    return (
      <div className="fade-in text-center" style={{ paddingTop: '5rem', paddingBottom: '5rem' }}>
        <div className="card" style={{ padding: '3.5rem 2rem', maxWidth: '540px', margin: '0 auto' }}>
          <div className="spinner spinner-dark mb-4" style={{ width: 44, height: 44, borderWidth: 3 }}></div>
          <h2 className="card-title mb-2" style={{ color: 'var(--text-main)' }}>Loading Career History</h2>
          <p className="text-muted text-sm">Fetching your uploaded resumes and previous job analysis records...</p>
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
    <div className="fade-in" style={{ maxWidth: '1100px', margin: '0 auto', paddingBottom: '3.5rem' }}>
      {/* Hidden File Input for Direct CV Upload */}
      <input
        type="file"
        ref={fileInputRef}
        onChange={handleDirectCvUpload}
        accept=".pdf,application/pdf"
        style={{ display: 'none' }}
      />

      {/* 1. PAGE HEADER */}
      <div className="flex justify-between items-center flex-wrap gap-4 mb-8">
        <div style={{ display: 'flex', gap: '1rem', alignItems: 'center' }}>
          <div className="prep-header-icon">
            <Layers size={28} />
          </div>
          <div>
            <h1 className="page-title mb-1.5" style={{ color: 'var(--text-main)', fontSize: '1.75rem', fontWeight: 800 }}>
              History
            </h1>
            <p className="page-subtitle text-muted text-sm" style={{ margin: 0 }}>
              Manage your uploaded resumes and review previous job skill analyses.
            </p>
          </div>
        </div>

        {/* Top Action Buttons on ONE Line with the SAME Style */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', flexWrap: 'wrap' }}>
          <button
            type="button"
            onClick={handleUploadNewCvClick}
            disabled={uploadingCv}
            className="btn btn-primary flex items-center gap-2"
            style={{ padding: '0.65rem 1.25rem', fontSize: '0.875rem', fontWeight: 600, borderRadius: '8px' }}
          >
            {uploadingCv ? (
              <>
                <span className="spinner spinner-dark" style={{ width: 15, height: 15 }}></span>
                <span>Uploading...</span>
              </>
            ) : (
              <>
                <Upload size={16} />
                <span>Upload New CV</span>
              </>
            )}
          </button>

          <button
            type="button"
            onClick={() => {
              setNewAnalysisCvChoice(cvList.length > 0 ? 'saved' : 'new');
              setShowNewAnalysisModal(true);
            }}
            className="btn btn-primary flex items-center gap-2"
            style={{ padding: '0.65rem 1.25rem', fontSize: '0.875rem', fontWeight: 600, borderRadius: '8px' }}
          >
            <Plus size={16} />
            <span>New Analysis</span>
          </button>
        </div>
      </div>

      {/* Feedback Alerts */}
      {uploadSuccess && (
        <div className="alert-success flex items-center justify-between mb-6" style={{ borderRadius: '8px', padding: '0.9rem 1.25rem' }}>
          <div className="flex items-center gap-2.5">
            <CheckCircle2 size={18} style={{ color: '#16a34a', flexShrink: 0 }} />
            <span style={{ fontWeight: 500 }}>{uploadSuccess}</span>
          </div>
          <button onClick={() => setUploadSuccess(null)} style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'inherit' }}>
            <X size={16} />
          </button>
        </div>
      )}

      {actionError && (
        <div className="alert-error flex items-center justify-between mb-6" style={{ borderRadius: '8px', padding: '0.9rem 1.25rem' }}>
          <div className="flex items-center gap-2.5">
            <AlertCircle size={18} style={{ color: '#dc2626', flexShrink: 0 }} />
            <span>{actionError}</span>
          </div>
          <button onClick={() => setActionError(null)} style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'inherit' }}>
            <X size={16} />
          </button>
        </div>
      )}

      {/* 2. SUB-NAVIGATION TABS (MATCHING INTERVIEW PREP HUB) */}
      <div className="prep-tabs-nav" style={{ marginBottom: '2rem' }}>
        <button
          type="button"
          onClick={() => setActiveTab('resumes')}
          className={`prep-tab-button ${activeTab === 'resumes' ? 'active' : ''}`}
        >
          <FileText size={16} />
          <span>Uploaded Resumes</span>
          <span className="prep-tab-badge">
            {cvList.length}
          </span>
        </button>

        <button
          type="button"
          onClick={() => setActiveTab('analyses')}
          className={`prep-tab-button ${activeTab === 'analyses' ? 'active' : ''}`}
        >
          <Briefcase size={16} />
          <span>Previous Analyses</span>
          <span className="prep-tab-badge">
            {pastSessions.length}
          </span>
        </button>
      </div>

      {/* 3. TAB CONTENT: UPLOADED RESUMES */}
      {activeTab === 'resumes' && (
      <section className="fade-in" style={{ marginBottom: '2.5rem' }}>
        <div className="flex items-center justify-between mb-4 flex-wrap gap-3">
          <div className="flex items-center gap-2.5">
            <div
              style={{
                width: 32,
                height: 32,
                borderRadius: '8px',
                backgroundColor: 'var(--primary-50)',
                color: 'var(--primary-600)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
              }}
            >
              <FileText size={17} />
            </div>
            <div>
              <h2 className="card-title mb-0" style={{ fontSize: '1.25rem', fontWeight: 700 }}>
                Uploaded Resumes
              </h2>
            </div>
            <span
              style={{
                fontSize: '0.75rem',
                fontWeight: 600,
                color: 'var(--text-muted)',
                backgroundColor: 'var(--primary-50)',
                padding: '0.2rem 0.6rem',
                borderRadius: '9999px',
                marginLeft: '0.25rem',
              }}
            >
              {cvList.length} {cvList.length === 1 ? 'Resume' : 'Resumes'}
            </span>
          </div>

          <button
            onClick={handleUploadNewCvClick}
            disabled={uploadingCv}
            className="btn btn-outline text-xs flex items-center gap-2"
            style={{ padding: '0.55rem 1rem', borderRadius: '8px', fontWeight: 600 }}
          >
            {uploadingCv ? (
              <>
                <span className="spinner spinner-dark" style={{ width: 14, height: 14 }}></span>
                <span>Uploading Resume...</span>
              </>
            ) : (
              <>
                <Upload size={14} />
                <span>Upload New CV</span>
              </>
            )}
          </button>
        </div>

        {/* Resumes List or Empty State */}
        {cvList.length === 0 ? (
          <div
            className="card text-center"
            style={{
              padding: '3rem 2rem',
              borderRadius: '12px',
              border: '1.5px dashed var(--border-color)',
              backgroundColor: '#fafafa',
            }}
          >
            <div
              style={{
                width: 52,
                height: 52,
                borderRadius: '50%',
                backgroundColor: 'var(--primary-50)',
                color: 'var(--primary-600)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                margin: '0 auto 1.25rem auto',
                border: '1px solid var(--primary-100)',
              }}
            >
              <FileText size={24} />
            </div>
            <h3 className="font-bold text-base text-main mb-1.5">No Resumes Uploaded Yet</h3>
            <p className="text-muted text-xs mb-5" style={{ maxWidth: '420px', margin: '0 auto 1.25rem auto' }}>
              Upload your PDF resume to unlock automated skill extraction, JD gap analysis, and interview preparation.
            </p>
            <button
              onClick={handleUploadNewCvClick}
              disabled={uploadingCv}
              className="btn btn-primary text-xs flex items-center gap-2"
              style={{ padding: '0.65rem 1.35rem', margin: '0 auto' }}
            >
              <Upload size={14} />
              <span>Upload Your First CV</span>
            </button>
          </div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.85rem' }}>
            {cvList.map((cv) => {
              const isDefault = Boolean(cv.is_default);
              const isDownloading = downloadingCvId === cv.id;

              return (
                <div
                  key={cv.id}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    flexWrap: 'wrap',
                    gap: '1.25rem',
                    padding: '1.15rem 1.5rem',
                    backgroundColor: isDefault ? 'linear-gradient(to right, #fcfdff, #ffffff)' : '#ffffff',
                    border: isDefault ? '1.5px solid var(--primary-300)' : '1px solid var(--border-color)',
                    borderRadius: '12px',
                    boxShadow: 'var(--shadow-sm)',
                    transition: 'border-color 0.15s ease, box-shadow 0.15s ease',
                  }}
                >
                  {/* Left: CV Details */}
                  <div style={{ display: 'flex', alignItems: 'center', gap: '1rem', minWidth: '280px', flex: '1 1 auto' }}>
                    <div
                      style={{
                        width: 44,
                        height: 44,
                        borderRadius: '10px',
                        backgroundColor: isDefault ? 'var(--primary-100)' : 'var(--primary-50)',
                        color: 'var(--primary-700)',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        border: '1px solid var(--primary-200)',
                        flexShrink: 0,
                      }}
                    >
                      <FileText size={22} />
                    </div>

                    <div style={{ display: 'flex', flexDirection: 'column', gap: '0.35rem' }}>
                      <div className="flex items-center gap-2.5 flex-wrap">
                        <span style={{ fontSize: '1rem', fontWeight: 700, color: 'var(--text-main)' }}>
                          {cv.file_name}
                        </span>
                        {isDefault && (
                          <span
                            className="badge badge-purple"
                            style={{
                              fontSize: '0.72rem',
                              padding: '0.2rem 0.65rem',
                              fontWeight: 700,
                              display: 'inline-flex',
                              alignItems: 'center',
                              gap: '0.3rem',
                            }}
                          >
                            <Check size={12} />
                            <span>Active Default</span>
                          </span>
                        )}
                      </div>

                      {/* Properly spaced metadata row */}
                      <div
                        style={{
                          display: 'flex',
                          alignItems: 'center',
                          gap: '0.85rem',
                          flexWrap: 'wrap',
                          fontSize: '0.8rem',
                          color: 'var(--text-muted)',
                        }}
                      >
                        <span style={{ display: 'inline-flex', alignItems: 'center', gap: '0.4rem' }}>
                          <Calendar size={13} style={{ color: 'var(--primary-600)', flexShrink: 0 }} />
                          <span>Uploaded {formatDate(cv.uploaded_at)}</span>
                        </span>

                        <span style={{ color: 'var(--border-color)' }}>•</span>

                        <span style={{ display: 'inline-flex', alignItems: 'center', gap: '0.4rem' }}>
                          <Briefcase size={13} style={{ color: 'var(--primary-600)', flexShrink: 0 }} />
                          <span>
                            {cv.analyses_count > 0
                              ? `Used in ${cv.analyses_count} ${cv.analyses_count === 1 ? 'analysis' : 'analyses'}`
                              : 'Not analyzed yet'}
                          </span>
                        </span>
                      </div>
                    </div>
                  </div>

                  {/* Right: Actions */}
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.65rem', flexWrap: 'wrap' }}>
                    <button
                      type="button"
                      onClick={(e) => handleStartAnalysisWithCv(cv, e)}
                      className="btn btn-primary text-xs flex items-center gap-1.5"
                      style={{ padding: '0.5rem 0.95rem', borderRadius: '7px', fontWeight: 600 }}
                      title="Run a new job description analysis using this resume"
                    >
                      <Plus size={14} />
                      <span>Analyze Job</span>
                    </button>

                    <button
                      type="button"
                      onClick={(e) => handleDownloadCv(cv, e)}
                      disabled={isDownloading}
                      className="btn btn-outline text-xs flex items-center gap-1.5"
                      style={{ padding: '0.5rem 0.85rem', borderRadius: '7px' }}
                      title="Download PDF file"
                    >
                      {isDownloading ? (
                        <span className="spinner spinner-dark" style={{ width: 12, height: 12 }}></span>
                      ) : (
                        <Download size={13} />
                      )}
                      <span>Download</span>
                    </button>

                    {!isDefault && (
                      <button
                        type="button"
                        onClick={(e) => handleSetDefaultCv(cv, e)}
                        className="btn btn-outline text-xs flex items-center gap-1.5"
                        style={{ padding: '0.5rem 0.85rem', borderRadius: '7px' }}
                        title="Set as default resume for quick analyses"
                      >
                        <Star size={13} />
                        <span>Set Default</span>
                      </button>
                    )}

                    {cv.analyses_count === 0 && (
                      <button
                        type="button"
                        onClick={(e) => handleDeleteCv(cv, e)}
                        className="btn btn-outline text-xs flex items-center justify-center"
                        style={{
                          padding: '0.5rem',
                          borderRadius: '7px',
                          color: '#dc2626',
                          borderColor: '#fca5a5',
                        }}
                        title="Remove uploaded CV"
                      >
                        <Trash2 size={13} />
                      </button>
                    )}
                  </div>
                </div>
              );
            })}

            {/* Quick Upload Banner Strip */}
            <div
              onClick={handleUploadNewCvClick}
              role="button"
              tabIndex={0}
              onKeyDown={(e) => {
                if (e.key === 'Enter' || e.key === ' ') {
                  e.preventDefault();
                  handleUploadNewCvClick();
                }
              }}
              style={{
                border: '1.5px dashed var(--border-color)',
                borderRadius: '10px',
                padding: '0.85rem 1.25rem',
                backgroundColor: '#fafbfc',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                gap: '0.65rem',
                cursor: 'pointer',
                transition: 'all 0.15s ease',
                color: 'var(--text-muted)',
                fontSize: '0.825rem',
                fontWeight: 500,
                marginTop: '0.25rem',
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.borderColor = 'var(--primary-400)';
                e.currentTarget.style.backgroundColor = 'var(--primary-50)';
                e.currentTarget.style.color = 'var(--primary-700)';
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.borderColor = 'var(--border-color)';
                e.currentTarget.style.backgroundColor = '#fafbfc';
                e.currentTarget.style.color = 'var(--text-muted)';
              }}
            >
              <Upload size={14} style={{ color: 'var(--primary-600)' }} />
              <span>Have another version or role-specific resume? <strong>Click to upload new PDF</strong></span>
            </div>
          </div>
        )}
      </section>
      )}

      {/* 4. TAB CONTENT: PREVIOUS ANALYSES */}
      {activeTab === 'analyses' && (
      <section className="fade-in" style={{ marginBottom: '2.5rem' }}>
        <div className="flex items-center justify-between mb-4 flex-wrap gap-3">
          <div className="flex items-center gap-2.5">
            <div
              style={{
                width: 32,
                height: 32,
                borderRadius: '8px',
                backgroundColor: 'var(--primary-50)',
                color: 'var(--primary-600)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
              }}
            >
              <Briefcase size={17} />
            </div>
            <div>
              <h2 className="card-title mb-0" style={{ fontSize: '1.25rem', fontWeight: 700 }}>
                Previous Analyses
              </h2>
            </div>
            <span
              style={{
                fontSize: '0.75rem',
                fontWeight: 600,
                color: 'var(--text-muted)',
                backgroundColor: 'var(--primary-50)',
                padding: '0.2rem 0.6rem',
                borderRadius: '9999px',
                marginLeft: '0.25rem',
              }}
            >
              {pastSessions.length} {pastSessions.length === 1 ? 'Analysis' : 'Analyses'}
            </span>
          </div>

          <span className="text-xs text-muted font-medium">
            Click any analyzed job to explore its skill diagnostic grid
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
              Select an uploaded resume and analyze a job opportunity to see your skills match score and interview preparation roadmap.
            </p>
            <button
              onClick={() => {
                setNewAnalysisCvChoice(cvList.length > 0 ? 'saved' : 'new');
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
          <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem', width: '100%' }}>
            {sortedSessions.map((sess) => {
              const hasScore = sess.overall_score !== undefined && sess.overall_score !== null;
              const scoreVal = hasScore ? Math.round(Number(sess.overall_score)) : null;

              return (
                <div
                  key={sess.analysis_id}
                  onClick={(e) => handleOpenDiagnosticGrid(sess, e)}
                  className="history-session-card"
                  style={{
                    cursor: 'pointer',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    flexWrap: 'wrap',
                    gap: '1.5rem',
                    padding: '1.35rem 1.75rem',
                    borderRadius: '12px',
                    border: '1px solid var(--border-color)',
                    backgroundColor: '#ffffff',
                    transition: 'all 0.2s cubic-bezier(0.4, 0, 0.2, 1)',
                  }}
                  role="button"
                  tabIndex={0}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' || e.key === ' ') {
                      e.preventDefault();
                      handleOpenDiagnosticGrid(sess, e);
                    }
                  }}
                >
                  {/* Left: Job Analysis Identification */}
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '0.55rem', flex: '1 1 320px' }}>
                    <div className="flex items-center gap-2.5 flex-wrap">
                      <h3
                        className="font-bold text-lg text-main flex items-center gap-2.5"
                        style={{ margin: 0, fontSize: '1.1rem' }}
                      >
                        <Briefcase size={18} style={{ color: 'var(--primary-600)', flexShrink: 0 }} />
                        <span>{sess.job_title || 'Target Job Position'}</span>
                      </h3>

                      {sess.company && (
                        <span
                          className="badge badge-purple"
                          style={{ fontSize: '0.75rem', padding: '0.2rem 0.65rem', fontWeight: 600 }}
                        >
                          {sess.company}
                        </span>
                      )}
                    </div>

                    {/* Identifying Details: Date, Resume Used, Skills Count (Properly Spaced) */}
                    <div
                      style={{
                        display: 'flex',
                        alignItems: 'center',
                        gap: '0.9rem',
                        flexWrap: 'wrap',
                        fontSize: '0.825rem',
                        color: 'var(--text-muted)',
                      }}
                    >
                      <span style={{ display: 'inline-flex', alignItems: 'center', gap: '0.4rem' }}>
                        <Calendar size={14} style={{ color: 'var(--primary-600)', flexShrink: 0 }} />
                        <span>{formatDate(sess.created_at)}</span>
                      </span>

                      <span style={{ color: 'var(--border-color)' }}>•</span>

                      <span style={{ display: 'inline-flex', alignItems: 'center', gap: '0.4rem' }}>
                        <FileText size={14} style={{ color: 'var(--primary-600)', flexShrink: 0 }} />
                        <strong style={{ color: 'var(--text-main)', fontWeight: 600 }}>
                          {sess.cv_filename || 'Uploaded Resume'}
                        </strong>
                      </span>

                      {sess.total_skills_count > 0 && (
                        <>
                          <span style={{ color: 'var(--border-color)' }}>•</span>
                          <span style={{ display: 'inline-flex', alignItems: 'center', gap: '0.4rem' }}>
                            <CheckCircle2 size={14} style={{ color: '#16a34a', flexShrink: 0 }} />
                            <span>
                              <strong>{sess.matched_skills_count}</strong> of <strong>{sess.total_skills_count}</strong> skills matched
                            </span>
                          </span>
                        </>
                      )}
                    </div>
                  </div>

                  {/* Right: Score Pill & Open Diagnostic Grid CTA */}
                  <div
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: '1.25rem',
                      flexShrink: 0,
                    }}
                    onClick={(e) => e.stopPropagation()}
                  >
                    {scoreVal !== null && (
                      <div
                        style={{
                          display: 'flex',
                          flexDirection: 'column',
                          alignItems: 'center',
                          justifyContent: 'center',
                          padding: '0.45rem 0.9rem',
                          backgroundColor: 'var(--primary-50)',
                          border: '1px solid var(--primary-100)',
                          borderRadius: '8px',
                          minWidth: '72px',
                          textAlign: 'center',
                        }}
                      >
                        <span style={{ fontSize: '1.2rem', fontWeight: 800, color: 'var(--primary-700)', lineHeight: 1 }}>
                          {scoreVal}%
                        </span>
                        <span style={{ fontSize: '0.68rem', fontWeight: 600, color: 'var(--primary-600)', marginTop: '2px' }}>
                          Match
                        </span>
                      </div>
                    )}

                    <button
                      type="button"
                      onClick={(e) => handleOpenDiagnosticGrid(sess, e)}
                      className="btn btn-primary text-xs flex items-center gap-2"
                      style={{
                        padding: '0.65rem 1.25rem',
                        fontWeight: 600,
                        borderRadius: '8px',
                        whiteSpace: 'nowrap',
                      }}
                      title="Open the CV vs JD skill comparison grid"
                    >
                      <Layers size={14} />
                      <span>Open Diagnostic Grid</span>
                      <ArrowRight size={13} />
                    </button>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </section>
      )}

      {/* 5. NEW ANALYSIS / CV INTAKE MODAL */}
      {showNewAnalysisModal && (
        <div className="modal-overlay" onClick={() => setShowNewAnalysisModal(false)}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()} style={{ maxWidth: '680px' }}>
            <div className="flex items-center justify-between mb-4 border-b pb-3" style={{ borderColor: 'var(--border-color)' }}>
              <div>
                <h2 className="font-bold text-xl text-main" style={{ margin: 0 }}>
                  Start New Career Skill Analysis
                </h2>
                <p className="text-xs text-muted mt-0.5">
                  Select your resume and paste the job description to calculate candidate readiness.
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
                    onClick={() => cvList.length > 0 && setNewAnalysisCvChoice('saved')}
                    className={`option-card ${newAnalysisCvChoice === 'saved' ? 'selected' : ''} ${cvList.length === 0 ? 'disabled' : ''}`}
                    style={{ padding: '0.85rem 1rem' }}
                  >
                    <div className="option-badge" style={{ width: 24, height: 24, fontSize: '0.75rem' }}>
                      {newAnalysisCvChoice === 'saved' ? <Check size={14} /> : '1'}
                    </div>
                    <div>
                      <div className="font-semibold text-xs text-main">Use Saved Resume</div>
                      <div className="text-xs text-muted" style={{ fontSize: '0.7rem' }}>
                        {cvList.length > 0 ? `${cvList.length} resume(s) available` : 'No saved CV available'}
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

                {/* Sub-selector when saved CV choice is active */}
                {newAnalysisCvChoice === 'saved' && cvList.length > 0 && (
                  <div className="mt-3">
                    <label className="text-xs font-semibold text-main mb-1 block">
                      Select which saved resume to use:
                    </label>
                    <select
                      value={selectedCvId}
                      onChange={(e) => setSelectedCvId(Number(e.target.value))}
                      className="input text-xs"
                      style={{ padding: '0.55rem 0.75rem' }}
                    >
                      {cvList.map((c) => (
                        <option key={c.id} value={c.id}>
                          {c.file_name} {c.is_default ? '(Active Default)' : ''} — Uploaded {formatDate(c.uploaded_at)}
                        </option>
                      ))}
                    </select>
                  </div>
                )}

                {/* File picker when upload new CV choice is active */}
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
