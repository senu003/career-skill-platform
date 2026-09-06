import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Upload, FileText, CheckCircle, AlertCircle, ArrowRight, RefreshCw, Briefcase, Building } from 'lucide-react';
import { fetchWithAuth } from '../api';
import { useAssessment } from '../context/AssessmentContext';
import { isSupportedSkill } from '../utils/supportedSkills';

export default function DashboardPage() {
  const navigate = useNavigate();
  const { analysisResult, setAnalysisResult, clearAnalysis } = useAssessment();

  // Intake Form State
  const [selectedFile, setSelectedFile] = useState(null);
  const [dragActive, setDragActive] = useState(false);
  const [jobTitle, setJobTitle] = useState('');
  const [companyName, setCompanyName] = useState('');
  const [jobDescription, setJobDescription] = useState('');

  // Saved CV State
  const [savedCv, setSavedCv] = useState(null);
  const [useSavedCv, setUseSavedCv] = useState(false);

  // UI Flow State
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  // Fetch last uploaded CV on mount
  React.useEffect(() => {
    const fetchSavedCv = async () => {
      try {
        const res = await fetchWithAuth('/cv/latest');
        if (res && res.has_cv && res.cv) {
          setSavedCv(res.cv);
          setUseSavedCv(true);
        }
      } catch (err) {
        console.warn('No saved CV found:', err);
      }
    };
    fetchSavedCv();
  }, []);

  // Drag and Drop Handlers
  const handleDrag = (e) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === 'dragenter' || e.type === 'dragover') {
      setDragActive(true);
    } else if (e.type === 'dragleave') {
      setDragActive(false);
    }
  };

  const handleDrop = (e) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);

    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      const file = e.dataTransfer.files[0];
      validateAndSetFile(file);
    }
  };

  const handleFileChange = (e) => {
    if (e.target.files && e.target.files[0]) {
      validateAndSetFile(e.target.files[0]);
    }
  };

  const validateAndSetFile = (file) => {
    setError(null);
    if (file.type !== 'application/pdf' && !file.name.toLowerCase().endsWith('.pdf')) {
      setError('Please select a valid PDF document.');
      return;
    }
    setSelectedFile(file);
    setUseSavedCv(false);
  };

  const removeFile = () => {
    setSelectedFile(null);
    if (savedCv) {
      setUseSavedCv(true);
    }
  };

  // Form Submission & Analysis API Integration
  const handleAnalyze = async (e) => {
    e.preventDefault();
    setError(null);

    if (!selectedFile && !useSavedCv) {
      setError('Please upload your CV PDF or choose your saved CV.');
      return;
    }

    if (!jobDescription.trim()) {
      setError('Please paste the job description text.');
      return;
    }

    setLoading(true);

    try {
      // 1. Extract requirements from job description using POST /requirements/analyze
      const reqRes = await fetchWithAuth('/requirements/analyze', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ text: jobDescription.trim() }),
      });

      const extractedRequirements = reqRes.requirements || [];

      if (!Array.isArray(extractedRequirements) || extractedRequirements.length === 0) {
        throw new Error('No skill requirements could be extracted from the job description. Please provide a more detailed description.');
      }

      // 2. Prepare multipart form data for POST /cv/analyze
      const formData = new FormData();
      if (selectedFile) {
        formData.append('file', selectedFile);
      } else if (savedCv) {
        formData.append('cv_id', savedCv.id);
      }
      formData.append('requirements', JSON.stringify(extractedRequirements));
      if (jobTitle) formData.append('job_title', jobTitle);
      if (companyName) formData.append('company', companyName);

      // 3. Analyze CV against requirements
      const cvRes = await fetchWithAuth('/cv/analyze', {
        method: 'POST',
        body: formData,
      });

      // 4. Save backend analysis response to AssessmentContext
      setAnalysisResult(cvRes);
    } catch (err) {
      setError(err.message || 'An error occurred while analyzing match. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  // Status Helper: Determines skill match status per prompt rules
  const getSkillStatus = (skillItem) => {
    if (!skillItem.matched) {
      return { label: 'Missing', className: 'status-badge-missing' };
    }
    if (skillItem.is_weakness || (skillItem.level_gap !== null && skillItem.level_gap > 0)) {
      return { label: 'Needs Improvement', className: 'status-badge-needs-improvement' };
    }
    return { label: 'Strong Match', className: 'status-badge-strong' };
  };

  // Format Helper: Capitalize text strings safely
  const formatLevel = (lvl) => {
    if (!lvl) return 'N/A';
    return lvl.charAt(0).toUpperCase() + lvl.slice(1).toLowerCase();
  };

  // Extract skills list safely from backend response
  const skillsList = analysisResult?.skills || [
    ...(analysisResult?.matched_skills || []),
    ...(analysisResult?.missing_skills || []),
  ];

  // Find first supported skill needing assessment for "Continue to Assessment"
  const supportedSkillsList = skillsList.filter(s => isSupportedSkill(s.skill));
  const firstSkillToAssess = supportedSkillsList.find(s => !s.matched || s.is_weakness || (s.level_gap && s.level_gap > 0)) || supportedSkillsList[0];

  return (
    <div className="fade-in">
      {/* 1. HEADER & WELCOME */}
      <div className="page-header">
        <h1 className="page-title">Find out how well you match this job</h1>
        <p className="page-subtitle">
          Upload your CV or use your saved resume, and provide the job description to calculate match compatibility.
        </p>
      </div>

      {/* Workflow Indicator */}
      <div className="workflow-steps">
        <div className={`workflow-step ${selectedFile || useSavedCv ? 'active' : ''}`}>
          <span className="workflow-step-num">1</span>
          <span>CV Selected</span>
        </div>
        <div className={`workflow-step-divider ${selectedFile || useSavedCv ? 'active' : ''}`} />
        <div className={`workflow-step ${jobDescription.trim() ? 'active' : ''}`}>
          <span className="workflow-step-num">2</span>
          <span>Provide Job</span>
        </div>
        <div className={`workflow-step-divider ${analysisResult ? 'active' : ''}`} />
        <div className={`workflow-step ${analysisResult ? 'active' : ''}`}>
          <span className="workflow-step-num">3</span>
          <span>Analyze Match</span>
        </div>
      </div>

      {/* ERROR ALERT */}
      {error && (
        <div className="alert-error flex items-center gap-2">
          <AlertCircle size={18} />
          <span>{error}</span>
        </div>
      )}

      {/* INTAKE FORM (CV Upload + Job Description) */}
      {!analysisResult ? (
        <form onSubmit={handleAnalyze} className="grid" style={{ gap: '1.5rem' }}>
          {/* 3. CV UPLOAD / SAVED CV CARD */}
          <div className="card">
            <h2 className="card-title flex items-center justify-between">
              <div className="flex items-center gap-2">
                <FileText size={20} style={{ color: 'var(--primary-600)' }} />
                <span>Your CV / Resume</span>
              </div>
              {savedCv && (
                <button
                  type="button"
                  onClick={() => {
                    setUseSavedCv(!useSavedCv);
                    if (!useSavedCv) setSelectedFile(null);
                  }}
                  className="btn btn-outline text-xs"
                  style={{ padding: '0.3rem 0.65rem' }}
                >
                  {useSavedCv ? 'Upload New File Instead' : 'Use Last Saved CV'}
                </button>
              )}
            </h2>

            {useSavedCv && savedCv ? (
              <div className="file-preview" style={{ backgroundColor: 'var(--primary-50)', border: '1px solid var(--primary-200)' }}>
                <div className="flex items-center gap-3">
                  <FileText size={24} style={{ color: 'var(--primary-600)' }} />
                  <div>
                    <div className="font-semibold text-sm text-main flex items-center gap-2">
                      <span>{savedCv.file_name}</span>
                      <span className="badge badge-purple">Saved Resume</span>
                    </div>
                    <div className="text-xs text-muted">
                      Uploaded on {new Date(savedCv.uploaded_at).toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' })}
                    </div>
                  </div>
                </div>
                <button
                  type="button"
                  onClick={() => setUseSavedCv(false)}
                  className="btn btn-outline"
                  style={{ padding: '0.3rem 0.6rem', fontSize: '0.8rem' }}
                >
                  Replace File
                </button>
              </div>
            ) : !selectedFile ? (
              <div
                className={`upload-zone ${dragActive ? 'dragging' : ''}`}
                onDragEnter={handleDrag}
                onDragOver={handleDrag}
                onDragLeave={handleDrag}
                onDrop={handleDrop}
                onClick={() => document.getElementById('cv-file-input').click()}
              >
                <input
                  id="cv-file-input"
                  type="file"
                  accept=".pdf,application/pdf"
                  onChange={handleFileChange}
                  style={{ display: 'none' }}
                />
                <Upload size={32} style={{ color: 'var(--primary-500)', marginBottom: '0.75rem' }} />
                <p className="font-semibold text-main mb-1">
                  Drag and drop your CV PDF here, or <span style={{ color: 'var(--primary-600)', textDecoration: 'underline' }}>Browse</span>
                </p>
                <p className="text-xs text-muted">Supports PDF format up to 10MB</p>
              </div>
            ) : (
              <div className="file-preview">
                <div className="flex items-center gap-3">
                  <FileText size={24} style={{ color: 'var(--primary-600)' }} />
                  <div>
                    <div className="font-semibold text-sm" style={{ color: 'var(--text-main)' }}>{selectedFile.name}</div>
                    <div className="text-xs text-muted">{(selectedFile.size / 1024).toFixed(1)} KB • PDF Document</div>
                  </div>
                </div>
                <button
                  type="button"
                  onClick={removeFile}
                  className="btn btn-outline"
                  style={{ padding: '0.3rem 0.6rem', fontSize: '0.8rem' }}
                >
                  Change File
                </button>
              </div>
            )}
          </div>

          {/* 4. JOB DESCRIPTION CARD */}
          <div className="card">
            <h2 className="card-title flex items-center gap-2">
              <Briefcase size={20} style={{ color: 'var(--primary-600)' }} />
              <span>Job Details & Description</span>
            </h2>

            <div className="grid grid-cols-2" style={{ gap: '1rem', marginBottom: '1.25rem' }}>
              <div className="form-group" style={{ marginBottom: 0 }}>
                <label className="form-label">Job Title</label>
                <div style={{ position: 'relative' }}>
                  <input
                    type="text"
                    className="input"
                    placeholder="e.g. Senior Frontend Engineer"
                    value={jobTitle}
                    onChange={(e) => setJobTitle(e.target.value)}
                  />
                </div>
              </div>

              <div className="form-group" style={{ marginBottom: 0 }}>
                <label className="form-label">Company Name <span className="text-muted font-normal">(Optional)</span></label>
                <input
                  type="text"
                  className="input"
                  placeholder="e.g. TechCorp"
                  value={companyName}
                  onChange={(e) => setCompanyName(e.target.value)}
                />
              </div>
            </div>

            <div className="form-group">
              <label className="form-label">Job Description Text *</label>
              <textarea
                className="textarea"
                rows={7}
                placeholder="Paste the full job description requirements here..."
                value={jobDescription}
                onChange={(e) => setJobDescription(e.target.value)}
                required
              />
            </div>

            <div className="flex justify-between items-center mt-4">
              <span className="text-xs text-muted">
                Analyzes skill match against uploaded CV using backend NLP algorithms.
              </span>
              <button
                type="submit"
                disabled={loading}
                className="btn btn-primary"
                style={{ padding: '0.75rem 1.75rem', fontSize: '0.95rem' }}
              >
                {loading ? (
                  <>
                    <span className="spinner"></span>
                    <span>Analyzing Match...</span>
                  </>
                ) : (
                  <>
                    <span>Analyze Match</span>
                    <ArrowRight size={18} />
                  </>
                )}
              </button>
            </div>
          </div>
        </form>
      ) : (
        /* 5. ANALYSIS RESULT SECTION */
        <div className="fade-in">
          {/* Top Bar for Resetting Intake */}
          <div className="flex justify-between items-center mb-4">
            <div className="text-sm font-semibold text-muted">
              {jobTitle ? `Analysis for: ${jobTitle}` : 'CV Match Analysis Result'}
              {companyName ? ` at ${companyName}` : ''}
            </div>
            <button
              onClick={() => {
                clearAnalysis();
                setSelectedFile(null);
                setJobDescription('');
              }}
              className="btn btn-outline"
              style={{ padding: '0.35rem 0.75rem', fontSize: '0.85rem' }}
            >
              <RefreshCw size={14} />
              <span>Analyze Another Job</span>
            </button>
          </div>

          {/* OVERALL MATCH SCORE BANNER */}
          <div className="match-score-card">
            <div>
              <div className="text-xs uppercase tracking-wider font-semibold" style={{ opacity: 0.85 }}>
                Overall Job Match
              </div>
              <div className="match-score-val mt-2">
                {analysisResult.score_data?.score !== undefined ? `${Math.round(analysisResult.score_data.score)}%` : 'N/A'}
              </div>
              <p className="text-xs mt-2" style={{ opacity: 0.9 }}>
                Calculated directly from backend skill requirements matching.
              </p>
            </div>

            {analysisResult.score_data && (
              <div className="match-score-details">
                <div className="match-stat-item">
                  <div className="text-xs text-muted" style={{ color: 'rgba(255,255,255,0.8)' }}>Matched</div>
                  <div className="font-bold text-lg">{analysisResult.score_data.matched_count}</div>
                </div>
                <div className="match-stat-item">
                  <div className="text-xs text-muted" style={{ color: 'rgba(255,255,255,0.8)' }}>Missing</div>
                  <div className="font-bold text-lg">{analysisResult.score_data.missing_count}</div>
                </div>
                <div className="match-stat-item">
                  <div className="text-xs text-muted" style={{ color: 'rgba(255,255,255,0.8)' }}>Total Required</div>
                  <div className="font-bold text-lg">{analysisResult.score_data.total_skills}</div>
                </div>
              </div>
            )}
          </div>

          {/* SKILLS BREAKDOWN LIST */}
          <div className="card">
            <h2 className="card-title">Skill Match Breakdown</h2>
            <p className="text-muted text-sm mb-4">
              Review required job skills against your CV evidence and assessment status.
            </p>

            <div className="skills-list">
              {skillsList.map((item, idx) => {
                const status = getSkillStatus(item);
                const reqLvl = formatLevel(item.required_level || item.level);
                const supported = isSupportedSkill(item.skill);
                
                // Determine CV Level display cleanly
                let cvLvlDisplay = 'Not assessed';
                if (item.assessed_level) {
                  cvLvlDisplay = formatLevel(item.assessed_level);
                } else if (item.cv_level) {
                  cvLvlDisplay = formatLevel(item.cv_level);
                } else if (item.matched) {
                  cvLvlDisplay = 'Detected in CV';
                }

                return (
                  <div key={idx} className="skill-card">
                    <div style={{ flex: '1 1 200px' }}>
                      <div className="font-semibold text-main text-base flex items-center gap-2">
                        <span>{item.skill}</span>
                        {!supported && (
                          <span
                            className="text-xs font-normal text-muted"
                            style={{
                              backgroundColor: 'var(--neutral-100, #f3f4f6)',
                              padding: '0.15rem 0.5rem',
                              borderRadius: '4px',
                              border: '1px solid var(--border-color)',
                            }}
                          >
                            Assessment Unavailable
                          </span>
                        )}
                      </div>
                      <div className="text-xs text-muted mt-1 flex items-center gap-3">
                        <span>Required: <strong style={{ color: 'var(--text-main)' }}>{reqLvl}</strong></span>
                        <span>•</span>
                        <span>CV Level: <strong style={{ color: 'var(--text-main)' }}>{cvLvlDisplay}</strong></span>
                      </div>
                    </div>

                    <div className="flex items-center gap-4">
                      <span className={`status-badge ${status.className}`}>
                        {status.label}
                      </span>

                      {supported ? (
                        <button
                          onClick={() => navigate(`/assessment/${encodeURIComponent(item.skill)}`)}
                          className="btn btn-secondary"
                          style={{ padding: '0.4rem 0.85rem', fontSize: '0.825rem' }}
                        >
                          Assess Skill
                        </button>
                      ) : (
                        <button
                          disabled
                          title="Technical MCQ assessment currently available for JS, React, and PostgreSQL"
                          className="btn btn-outline"
                          style={{ padding: '0.4rem 0.85rem', fontSize: '0.825rem', opacity: 0.6, cursor: 'not-allowed' }}
                        >
                          Unavailable
                        </button>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>

          {/* 6. NEXT ACTION BANNER */}
          <div
            className="card flex items-center justify-between"
            style={{ background: 'var(--primary-50)', border: '1px solid var(--primary-200)', marginTop: '1.5rem' }}
          >
            <div>
              <h3 className="font-semibold text-main text-base mb-1">Ready to complete your skill evaluation?</h3>
              <p className="text-sm text-muted">
                Take targeted assessments to verify your skills and improve candidate readiness.
              </p>
            </div>
            <button
              onClick={() => {
                if (firstSkillToAssess) {
                  navigate(`/assessment/${encodeURIComponent(firstSkillToAssess.skill)}`);
                } else {
                  navigate('/assessment');
                }
              }}
              className="btn btn-primary"
              style={{ padding: '0.7rem 1.5rem', whitespace: 'nowrap' }}
            >
              <span>Continue to Assessment</span>
              <ArrowRight size={18} />
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
