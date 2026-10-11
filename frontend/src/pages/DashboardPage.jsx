import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Upload, FileText, CheckCircle2, AlertCircle, AlertTriangle,
  ArrowRight, RefreshCw, Briefcase, ChevronDown, ChevronUp,
  Target, TrendingUp, Sparkles, HelpCircle
} from 'lucide-react';
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
  const [expandedEvidence, setExpandedEvidence] = useState({});
  const [activeFilter, setActiveFilter] = useState('All');
  const [supportedSkillsList, setSupportedSkillsList] = useState([]);

  const toggleEvidence = (skillKey) => {
    setExpandedEvidence((prev) => ({
      ...prev,
      [skillKey]: !prev[skillKey],
    }));
  };

  // Fetch supported assessment skills from /assessment/supported-skills
  useEffect(() => {
    let isMounted = true;
    const fetchSupportedSkills = async () => {
      try {
        const res = await fetchWithAuth('/assessment/supported-skills');
        if (isMounted && res && Array.isArray(res.supported_skills)) {
          setSupportedSkillsList(res.supported_skills);
        }
      } catch {
        // Fallback silently to predefined list
      }
    };
    fetchSupportedSkills();
    return () => {
      isMounted = false;
    };
  }, []);

  // Fetch last uploaded CV on mount
  useEffect(() => {
    let isMounted = true;
    const fetchSavedCv = async () => {
      try {
        const res = await fetchWithAuth('/cv/latest');
        if (isMounted && res && res.has_cv && res.cv) {
          setSavedCv(res.cv);
          setUseSavedCv(true);
        }
      } catch {
        // No saved CV found
      }
    };
    fetchSavedCv();
    return () => {
      isMounted = false;
    };
  }, []);

  const isSkillAvailable = (skillName) => {
    return isSupportedSkill(skillName, supportedSkillsList);
  };

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
      validateAndSetFile(e.dataTransfer.files[0]);
    }
  };

  const handleFileChange = (e) => {
    if (e.target.files && e.target.files[0]) {
      validateAndSetFile(e.target.files[0]);
    }
  };

  const validateAndSetFile = (file) => {
    setError(null);
    if (!file) return;

    if (file.type !== 'application/pdf' && !file.name.toLowerCase().endsWith('.pdf')) {
      setError('Please select a valid PDF document (.pdf).');
      return;
    }
    if (file.size > 10 * 1024 * 1024) {
      setError('File size exceeds 10MB limit. Please upload a smaller PDF.');
      return;
    }
    if (file.size === 0) {
      setError('The uploaded PDF appears empty or unreadable. Please ensure it contains readable text.');
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
    if (e && e.preventDefault) e.preventDefault();
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
      if (jobTitle.trim()) formData.append('job_title', jobTitle.trim());
      if (companyName.trim()) formData.append('company', companyName.trim());

      // 3. Analyze CV against requirements
      const cvRes = await fetchWithAuth('/cv/analyze', {
        method: 'POST',
        body: formData,
      });

      // 4. Save backend analysis response to AssessmentContext
      setAnalysisResult(cvRes);
    } catch (err) {
      if (err.status === 401 || (err.message && err.message.includes('401'))) {
        setError('Your session has expired. Redirecting to login page...');
        setTimeout(() => {
          navigate('/login');
        }, 1500);
      } else if (err.status === 502 || (err.message && err.message.includes('502'))) {
        setError('The AI analysis service is temporarily unavailable (502 Bad Gateway). Please try again shortly.');
      } else {
        setError(err.message || 'An error occurred while analyzing match. Please try again.');
      }
    } finally {
      setLoading(false);
    }
  };

  const handleAnalyzeAnother = () => {
    clearAnalysis();
    setSelectedFile(null);
    setJobDescription('');
    setExpandedEvidence({});
    setActiveFilter('All');
    setError(null);
  };

  // Format Helper: Capitalize text strings safely
  const formatLevel = (lvl) => {
    if (!lvl) return 'N/A';
    const s = String(lvl).trim();
    return s.charAt(0).toUpperCase() + s.slice(1).toLowerCase();
  };

  // Translate CV Level strictly per requirements:
  // "unspecified" -> "Mentioned, level unclear"
  // "not_found" -> "Not found in CV"
  const translateCvLevel = (cvLevel, isMatched) => {
    if (!cvLevel) {
      return isMatched ? 'Mentioned, level unclear' : 'Not found in CV';
    }
    const clean = String(cvLevel).trim().toLowerCase();
    if (clean === 'unspecified') {
      return 'Mentioned, level unclear';
    }
    if (clean === 'not_found' || clean === 'null' || clean === 'none') {
      return 'Not found in CV';
    }
    if (clean === 'basic') return 'Basic';
    if (clean === 'intermediate') return 'Intermediate';
    if (clean === 'advanced') return 'Advanced';
    return formatLevel(cvLevel);
  };

  // Extract skills list safely from backend response
  const skillsList = analysisResult?.skills || [
    ...(analysisResult?.matched_skills || []),
    ...(analysisResult?.missing_skills || []),
  ];

  const LEVEL_MAP = { basic: 1, intermediate: 2, advanced: 3 };

  // Helper to determine if a skill is a GAP
  // Missing, Needs Improvement, or assessed-below-required
  const isSkillGap = (item) => {
    const cvStatus = item.cv_match_status || (item.matched ? 'Match' : 'Missing');
    if (cvStatus === 'Missing' || !item.matched) return true;
    if (cvStatus === 'Needs Improvement') return true;

    // Assessed below required
    if (item.level_gap !== null && item.level_gap !== undefined) {
      const g = Number(item.level_gap);
      if (!isNaN(g) && g > 0) return true;
    }

    if (item.assessed_level && (item.required_level || item.level)) {
      const reqVal = LEVEL_MAP[String(item.required_level || item.level).toLowerCase().trim()] || 0;
      const assVal = LEVEL_MAP[String(item.assessed_level).toLowerCase().trim()] || 0;
      if (assVal > 0 && reqVal > 0 && assVal < reqVal) return true;
    }

    if (['Upgrade Needed', 'Re-learn Basics'].includes(item.skill_recommendation)) {
      return true;
    }

    return false;
  };

  // Calculate numeric gap size for ordering
  const getGapSize = (item) => {
    if (item.level_gap !== null && item.level_gap !== undefined) {
      const val = Number(item.level_gap);
      if (!isNaN(val)) return val;
    }
    const reqStr = String(item.required_level || item.level || 'basic').toLowerCase().trim();
    const reqVal = LEVEL_MAP[reqStr] || 1;
    const cvStatus = item.cv_match_status || (item.matched ? 'Match' : 'Missing');
    if (cvStatus === 'Missing' || !item.matched) return reqVal;
    if (cvStatus === 'Needs Improvement') {
      const cvStr = String(item.cv_level || '').toLowerCase().trim();
      const cvVal = LEVEL_MAP[cvStr] || 0;
      return Math.max(1, reqVal - cvVal);
    }
    return 0;
  };

  // Status Helper: Determines CV Match badge and style
  const getSkillStatus = (skillItem) => {
    const status = skillItem.cv_match_status || (skillItem.matched ? 'Match' : 'Missing');
    if (status === 'Match') {
      return { label: 'Match', className: 'status-badge-strong' };
    }
    if (status === 'Needs Improvement') {
      return { label: 'Needs Improvement', className: 'status-badge-needs-improvement' };
    }
    return { label: 'Missing', className: 'status-badge-missing' };
  };

  // One-line explanation under each gap
  const getGapExplanation = (item) => {
    const reqStr = formatLevel(item.required_level || item.level || 'Intermediate');
    const importancePrefix = (item.importance || 'required').toLowerCase() === 'preferred' ? 'Preferred' : 'Required';
    const cvStatus = item.cv_match_status || (item.matched ? 'Match' : 'Missing');

    if (cvStatus === 'Missing' || !item.matched) {
      return `${importancePrefix} ${reqStr}; not found in your CV`;
    }
    if (item.assessed_level && item.level_gap && Number(item.level_gap) > 0) {
      return `${importancePrefix} ${reqStr}; assessed as ${formatLevel(item.assessed_level)} (gap: ${item.level_gap})`;
    }
    if (cvStatus === 'Needs Improvement') {
      const cvLvl = item.cv_level && item.cv_level !== 'unspecified' && item.cv_level !== 'not_found'
        ? formatLevel(item.cv_level)
        : null;
      if (cvLvl) {
        return `${importancePrefix} ${reqStr}; CV evidence evaluated at ${cvLvl} level`;
      }
      return `${importancePrefix} ${reqStr}; mentioned in CV but evidence below required level`;
    }
    return `${importancePrefix} ${reqStr}; gap identified`;
  };

  // Required vs Preferred partitioning
  const requiredSkills = skillsList.filter(s => (s.importance || 'required').toLowerCase() !== 'preferred');
  const preferredSkills = skillsList.filter(s => (s.importance || '').toLowerCase() === 'preferred');

  const isMatchedSkill = (s) => (s.cv_match_status === 'Match' || (s.matched && s.cv_match_status !== 'Missing' && s.cv_match_status !== 'Needs Improvement'));

  const requiredFoundCount = requiredSkills.filter(isMatchedSkill).length;
  const totalRequiredCount = requiredSkills.length;

  const preferredFoundCount = preferredSkills.filter(isMatchedSkill).length;
  const totalPreferredCount = preferredSkills.length;

  // Match percentage: Count Required skills only (Do not mix Preferred into the percentage)
  const matchPercentage = totalRequiredCount > 0
    ? Math.round((requiredFoundCount / totalRequiredCount) * 100)
    : (skillsList.length > 0 ? Math.round((skillsList.filter(isMatchedSkill).length / skillsList.length) * 100) : 0);

  // Verdict Theme Helper
  const getVerdictTheme = (verdict) => {
    const v = (verdict || '').toLowerCase();
    if (v.includes('interview') || v.includes('ready')) {
      return {
        bg: '#ecfdf5',
        color: '#059669',
        border: '1px solid #a7f3d0',
        badgeClass: 'badge-success',
        icon: <CheckCircle2 size={24} style={{ color: '#059669' }} />
      };
    }
    if (v.includes('major') || v.includes('upskill')) {
      return {
        bg: '#fef2f2',
        color: '#dc2626',
        border: '1px solid #fecaca',
        badgeClass: 'status-badge-missing',
        icon: <AlertTriangle size={24} style={{ color: '#dc2626' }} />
      };
    }
    return {
      bg: '#fffbeb',
      color: '#b45309',
      border: '1px solid #fde68a',
      badgeClass: 'badge-warning',
      icon: <TrendingUp size={24} style={{ color: '#d97706' }} />
    };
  };

  const readinessVerdict = analysisResult?.readiness_verdict || analysisResult?.final_verdict || 'Evaluation Complete';
  const readinessReasons = analysisResult?.readiness_reasons || [];
  const verdictTheme = getVerdictTheme(readinessVerdict);

  // Check if candidate has completed any assessment
  const hasAnyAssessments = skillsList.some(s => s.assessed_level !== null && s.assessed_level !== undefined);

  // Focus First list (Gaps ONLY, max 5, ordered Required before Preferred, then largest gap first)
  const focusFirstList = (() => {
    // If backend provided priority_skills, ensure all items are strictly gaps
    if (analysisResult?.priority_skills && Array.isArray(analysisResult.priority_skills) && analysisResult.priority_skills.length > 0) {
      const gapPriority = analysisResult.priority_skills.filter(p => isSkillGap(p));
      if (gapPriority.length > 0) {
        return gapPriority.slice(0, 5);
      }
    }

    // Fallback: extract gaps from skillsList
    const gaps = skillsList.filter(s => isSkillGap(s));
    gaps.sort((a, b) => {
      // 1. Required before Preferred
      const aReq = (a.importance || 'required').toLowerCase() !== 'preferred' ? 0 : 1;
      const bReq = (b.importance || 'required').toLowerCase() !== 'preferred' ? 0 : 1;
      if (aReq !== bReq) return aReq - bReq;

      // 2. Largest gap first
      const aGap = getGapSize(a);
      const bGap = getGapSize(b);
      if (bGap !== aGap) return bGap - aGap;

      return (a.skill || '').localeCompare(b.skill || '');
    });

    return gaps.slice(0, 5).map(s => ({
      skill: s.skill,
      reason: s.cv_match_status === 'Missing' || !s.matched
        ? ((s.importance || 'required').toLowerCase() === 'preferred' ? 'Preferred skill missing from CV' : 'Required skill missing from CV')
        : (s.cv_match_status === 'Needs Improvement' ? 'Skill needs improvement based on CV evidence' : 'Skill gap identified below requirement'),
      required_level: s.required_level || s.level,
      importance: s.importance || 'required',
      level_gap: s.level_gap
    }));
  })();

  // Sort Skill Breakdown: gaps first (Missing, Needs Improvement), then Matched
  const sortedBreakdownSkills = [...skillsList].sort((a, b) => {
    const aIsGap = isSkillGap(a);
    const bIsGap = isSkillGap(b);
    if (aIsGap && !bIsGap) return -1;
    if (!aIsGap && bIsGap) return 1;

    // Within same category: Required before Preferred
    const aReq = (a.importance || 'required').toLowerCase() !== 'preferred' ? 0 : 1;
    const bReq = (b.importance || 'required').toLowerCase() !== 'preferred' ? 0 : 1;
    if (aReq !== bReq) return aReq - bReq;

    if (aIsGap && bIsGap) {
      const aGap = getGapSize(a);
      const bGap = getGapSize(b);
      if (bGap !== aGap) return bGap - aGap;
    }

    return (a.skill || '').localeCompare(b.skill || '');
  });

  // Filter chips: All / Gaps / Matched / Required / Preferred
  const filteredBreakdownSkills = sortedBreakdownSkills.filter(item => {
    if (activeFilter === 'All') return true;
    if (activeFilter === 'Gaps') return isSkillGap(item);
    if (activeFilter === 'Matched') return !isSkillGap(item);
    if (activeFilter === 'Required') return (item.importance || 'required').toLowerCase() !== 'preferred';
    if (activeFilter === 'Preferred') return (item.importance || '').toLowerCase() === 'preferred';
    return true;
  });

  // Footer CTA: Show "Continue to Assessment" only if at least one gap has an available assessment
  const allGapSkills = skillsList.filter(isSkillGap);
  const firstGapWithAssessment = allGapSkills.find(s => isSkillAvailable(s.skill));
  const showFooterCta = Boolean(firstGapWithAssessment);

  // Header display: never show placeholder like "dfgh at ghj"
  const displayJobTitle = jobTitle && jobTitle.trim() ? jobTitle.trim() : 'Your target job';
  const displayCompany = companyName && companyName.trim() ? ` at ${companyName.trim()}` : '';

  return (
    <div className="fade-in">
      {/* ERROR ALERT */}
      {error && (
        <div
          className="alert-error flex items-start gap-3 mb-4"
          role="alert"
          style={{
            padding: '1.1rem 1.25rem',
            borderRadius: 'var(--radius-sm)',
          }}
        >
          <AlertCircle size={20} style={{ flexShrink: 0, marginTop: '2px' }} />
          <div style={{ flex: 1 }}>
            <div className="font-bold text-sm mb-0.5">
              {error.includes('502') || error.toLowerCase().includes('bad gateway')
                ? 'AI Service Temporarily Unavailable'
                : 'Unable to Analyze Match'}
            </div>
            <div className="text-xs" style={{ lineHeight: 1.5, opacity: 0.95 }}>
              {error}
            </div>
            {(error.includes('502') || error.toLowerCase().includes('bad gateway')) && (
              <button
                type="button"
                onClick={handleAnalyze}
                className="btn btn-outline text-xs mt-2.5 flex items-center gap-1.5"
                style={{
                  padding: '0.35rem 0.75rem',
                  backgroundColor: '#ffffff',
                  borderColor: 'var(--danger-color)',
                  color: 'var(--danger-color)',
                }}
              >
                <RefreshCw size={13} />
                <span>Retry</span>
              </button>
            )}
          </div>
        </div>
      )}

      {/* LOADING STATE DURING ANALYSIS */}
      {loading ? (
        <div className="card text-center fade-in" style={{ padding: '3.5rem 2rem', margin: '1.5rem 0' }} role="status">
          <div
            className="spinner spinner-dark mb-4"
            style={{ width: 44, height: 44, borderWidth: 3, margin: '0 auto 1.5rem' }}
          ></div>
          <h2 className="card-title text-xl mb-2">Analyzing Job Match & CV Evidence</h2>
          <p className="text-muted text-sm mb-4" style={{ maxWidth: '520px', margin: '0 auto 1.5rem', lineHeight: 1.5 }}>
            Extracting skills from job description, comparing with your CV evidence, and synthesizing candidate readiness verdict...
          </p>
          <div className="flex justify-center items-center gap-2 text-xs text-muted flex-wrap">
            <span className="badge badge-purple">1. NLP Skill Extraction</span>
            <span>→</span>
            <span className="badge badge-purple">2. CV Evidence Matching</span>
            <span>→</span>
            <span className="badge badge-purple">3. Readiness & Priority Analysis</span>
          </div>
        </div>
      ) : !analysisResult ? (
        /* INTAKE FORM VIEW */
        <div>
          <div className="page-header">
            <h1 className="page-title">Find out how well you match this job</h1>
            <p className="page-subtitle">
              Upload your CV or choose your saved resume, and provide job requirements to calculate match compatibility.
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

          <form onSubmit={handleAnalyze} className="grid" style={{ gap: '1.5rem' }}>
            {/* CV UPLOAD / SAVED CV CARD */}
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
                <div>
                  {!savedCv && (
                    <p className="text-xs text-muted mb-2 font-medium" style={{ color: 'var(--primary-700)' }}>
                      Upload your CV to begin
                    </p>
                  )}
                  <div
                    className={`upload-zone ${dragActive ? 'dragging' : ''}`}
                    onDragEnter={handleDrag}
                    onDragOver={handleDrag}
                    onDragLeave={handleDrag}
                    onDrop={handleDrop}
                    onClick={() => document.getElementById('cv-file-input').click()}
                    tabIndex={0}
                    role="button"
                    aria-label="Upload your CV PDF document"
                    onKeyDown={(e) => {
                      if (e.key === 'Enter' || e.key === ' ') {
                        document.getElementById('cv-file-input').click();
                      }
                    }}
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

            {/* JOB DETAILS CARD */}
            <div className="card">
              <h2 className="card-title flex items-center gap-2">
                <Briefcase size={20} style={{ color: 'var(--primary-600)' }} />
                <span>Job Details & Description</span>
              </h2>

              <div className="grid grid-cols-2" style={{ gap: '1rem', marginBottom: '1.25rem' }}>
                <div className="form-group" style={{ marginBottom: 0 }}>
                  <label htmlFor="job-title-input" className="form-label">Job Title <span className="text-muted font-normal">(Optional)</span></label>
                  <input
                    id="job-title-input"
                    type="text"
                    className="input"
                    placeholder="e.g. Senior Frontend Engineer"
                    value={jobTitle}
                    onChange={(e) => setJobTitle(e.target.value)}
                  />
                </div>

                <div className="form-group" style={{ marginBottom: 0 }}>
                  <label htmlFor="company-name-input" className="form-label">Company Name <span className="text-muted font-normal">(Optional)</span></label>
                  <input
                    id="company-name-input"
                    type="text"
                    className="input"
                    placeholder="e.g. TechCorp"
                    value={companyName}
                    onChange={(e) => setCompanyName(e.target.value)}
                  />
                </div>
              </div>

              <div className="form-group">
                <label htmlFor="job-description-input" className="form-label">Job Description Text *</label>
                <textarea
                  id="job-description-input"
                  className="textarea"
                  rows={7}
                  placeholder="Paste the full job description requirements here..."
                  value={jobDescription}
                  onChange={(e) => setJobDescription(e.target.value)}
                  required
                />
              </div>

              <div className="flex justify-between items-center mt-4 flex-wrap gap-2">
                <span className="text-xs text-muted">
                  Extracts skills and compares CV qualifications against job requirements.
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
        </div>
      ) : (
        /* ========================================================
           B. PAGE STRUCTURE (TOP TO BOTTOM) - RESULTS VIEW
           1. Header
           2. Summary card
           3. Focus First (gaps only, max 5)
           4. Skill breakdown
           5. Footer CTA "Continue to Assessment"
           ======================================================== */
        <div className="fade-in">
          {/* 1. HEADER */}
          <div className="flex justify-between items-center mb-6 flex-wrap gap-4 pb-4" style={{ borderBottom: '1px solid var(--border-color)' }}>
            <div>
              <div className="text-xs uppercase tracking-wider font-semibold text-muted mb-1">
                CV Match Results
              </div>
              <h1 className="page-title text-2xl font-bold text-main" style={{ margin: 0 }}>
                {displayJobTitle}{displayCompany}
              </h1>
            </div>
            <button
              type="button"
              onClick={handleAnalyzeAnother}
              className="btn btn-outline flex items-center gap-1.5"
              id="btn-analyze-another"
              aria-label="Analyze another job"
              style={{ padding: '0.5rem 1rem', fontSize: '0.875rem' }}
            >
              <RefreshCw size={14} />
              <span>Analyze another job</span>
            </button>
          </div>

          {/* 2. SUMMARY CARD */}
          <div
            className="card mb-6"
            style={{
              padding: '1.75rem',
              backgroundColor: '#ffffff',
              border: '1px solid var(--border-color)',
            }}
          >
            <div className="flex items-start justify-between gap-6 flex-wrap mb-4 pb-4" style={{ borderBottom: '1px solid var(--border-color)' }}>
              {/* Readiness Verdict Badge & Icon */}
              <div className="flex items-center gap-3">
                <div style={{ padding: '0.5rem', borderRadius: 'var(--radius-sm)', backgroundColor: verdictTheme.bg, border: verdictTheme.border }}>
                  {verdictTheme.icon}
                </div>
                <div>
                  <div className="text-xs uppercase tracking-wider font-semibold text-muted">
                    Readiness Verdict
                  </div>
                  <div className="flex items-center gap-2 mt-0.5">
                    <span className="font-bold text-xl text-main">
                      {readinessVerdict}
                    </span>
                    <span
                      className="badge"
                      style={{
                        backgroundColor: verdictTheme.bg,
                        color: verdictTheme.color,
                        border: verdictTheme.border,
                        fontWeight: 700,
                        fontSize: '0.75rem',
                      }}
                    >
                      {readinessVerdict}
                    </span>
                  </div>
                </div>
              </div>

              {/* Match Percentage & Captions (COUNT REQUIRED SKILLS ONLY) */}
              <div style={{ textAlign: 'right' }}>
                <div className="text-xs uppercase tracking-wider font-semibold text-muted">
                  Required Skills Match
                </div>
                <div className="font-extrabold text-3xl text-main mt-0.5" style={{ color: 'var(--primary-700)', lineHeight: 1.1 }}>
                  {matchPercentage}%
                </div>
                <div className="text-xs font-semibold text-main mt-1.5" id="score-caption-required">
                  {requiredFoundCount} of {totalRequiredCount} required skills found
                </div>
                {totalPreferredCount > 0 && (
                  <div className="text-xs text-muted mt-0.5" id="score-caption-preferred">
                    {preferredFoundCount} of {totalPreferredCount} preferred skills found
                  </div>
                )}
              </div>
            </div>

            {/* Plain-language reasons from API */}
            {readinessReasons.length > 0 && (
              <div className="mb-3">
                <div className="text-xs font-semibold uppercase tracking-wider text-muted mb-2">
                  Key Reasons & Observations:
                </div>
                <ul className="flex flex-col gap-1.5" style={{ margin: 0, paddingLeft: '1.25rem' }}>
                  {readinessReasons.slice(0, 3).map((reason, rIdx) => (
                    <li key={rIdx} className="text-sm font-medium text-main" style={{ lineHeight: 1.5 }}>
                      {reason}
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {/* One line notice when no assessments exist */}
            {!hasAnyAssessments && (
              <div
                className="text-xs mt-3 pt-3 flex items-center gap-1.5 text-muted"
                style={{ borderTop: '1px solid var(--border-color)', color: '#6b7280' }}
              >
                <HelpCircle size={14} style={{ color: 'var(--primary-600)', flexShrink: 0 }} />
                <span>Based on your CV only. Take assessments to verify your skills</span>
              </div>
            )}
          </div>

          {/* 3. FOCUS FIRST (GAPS ONLY, MAX 5) */}
          <div className="card mb-6" style={{ backgroundColor: '#ffffff', border: '1.5px solid var(--primary-200)' }}>
            <div className="flex items-center justify-between mb-3 flex-wrap gap-2">
              <div>
                <h2 className="card-title mb-0.5 flex items-center gap-2" style={{ fontSize: '1.15rem' }}>
                  <Target size={18} style={{ color: 'var(--primary-600)' }} />
                  <span>Focus First: Top Priority Skills</span>
                </h2>
                <p className="text-muted text-xs">
                  Prioritized skill gaps to target first. Ordered by required importance and largest gap size.
                </p>
              </div>
              <span className="badge badge-purple" style={{ fontSize: '0.75rem' }}>
                Priority Gaps
              </span>
            </div>

            {focusFirstList.length === 0 ? (
              <div
                className="text-center py-6"
                style={{
                  backgroundColor: 'var(--primary-50)',
                  borderRadius: 'var(--radius-sm)',
                  border: '1px dashed var(--primary-200)',
                }}
              >
                <CheckCircle2 size={28} style={{ color: 'var(--success-color)', margin: '0 auto 0.5rem' }} />
                <div className="font-semibold text-main text-sm">No critical gaps found</div>
                <p className="text-xs text-muted mt-0.5">
                  Your CV demonstrates coverage for all identified job requirements.
                </p>
              </div>
            ) : (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                {focusFirstList.map((pItem, pIdx) => {
                  const pSkillName = pItem.skill;
                  const pReqLevel = formatLevel(pItem.required_level || pItem.level);
                  const pReason = pItem.reason || 'Priority skill gap identified';
                  const pImportance = (pItem.importance || 'required').toLowerCase() === 'preferred' ? 'Preferred' : 'Required';
                  const isAvailable = isSkillAvailable(pSkillName);

                  return (
                    <div
                      key={pIdx}
                      style={{
                        padding: '1rem',
                        backgroundColor: 'var(--primary-50)',
                        border: '1px solid var(--primary-200)',
                        borderRadius: 'var(--radius-sm)',
                        display: 'flex',
                        flexDirection: 'column',
                        justifyContent: 'space-between',
                        gap: '0.75rem',
                      }}
                    >
                      <div>
                        <div className="flex items-center justify-between gap-2 mb-1">
                          <span className="font-bold text-main text-sm flex items-center gap-1.5">
                            <span style={{ color: 'var(--primary-700)' }}>#{pIdx + 1}</span>
                            <span>{pSkillName}</span>
                          </span>
                          <span
                            className="badge"
                            style={{
                              fontSize: '0.7rem',
                              backgroundColor: pImportance === 'Required' ? 'rgba(99, 102, 241, 0.15)' : 'var(--neutral-100)',
                              color: pImportance === 'Required' ? 'var(--primary-700)' : 'var(--text-muted)',
                              border: '1px solid var(--primary-200)',
                            }}
                          >
                            {pImportance}
                          </span>
                        </div>
                        <div className="text-xs text-muted mb-1">
                          Required Level: <strong style={{ color: 'var(--text-main)' }}>{pReqLevel}</strong>
                        </div>
                        <p className="text-xs text-muted" style={{ margin: 0, lineHeight: 1.4, color: '#4b5563' }}>
                          {pReason}
                        </p>
                      </div>

                      <div className="flex justify-end items-center pt-1">
                        {isAvailable ? (
                          <button
                            type="button"
                            onClick={() => navigate(`/assessment/${encodeURIComponent(pSkillName)}`)}
                            className="btn btn-primary text-xs flex items-center gap-1"
                            style={{ padding: '0.35rem 0.75rem', fontSize: '0.75rem' }}
                            aria-label={`Take assessment for ${pSkillName}`}
                          >
                            <span>Take assessment</span>
                            <ArrowRight size={13} />
                          </button>
                        ) : (
                          <span className="text-xs text-muted" style={{ fontStyle: 'italic', fontSize: '0.75rem' }}>
                            No assessment available: based on CV evidence only
                          </span>
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>

          {/* 4. SKILL BREAKDOWN */}
          <div className="card mb-6">
            <div className="flex items-center justify-between mb-2 flex-wrap gap-2">
              <h2 className="card-title mb-0">Skill Match Breakdown</h2>
              <span className="text-xs text-muted">
                Showing {filteredBreakdownSkills.length} of {skillsList.length} skills
              </span>
            </div>
            <p className="text-muted text-sm mb-4">
              Review required job skills against your CV evidence, importance, and assessment status.
            </p>

            {/* Filter chips: All / Gaps / Matched / Required / Preferred */}
            <div className="filter-chips" role="group" aria-label="Filter skills by status or importance">
              {[
                { id: 'All', label: 'All', count: skillsList.length },
                { id: 'Gaps', label: 'Gaps', count: skillsList.filter(isSkillGap).length },
                { id: 'Matched', label: 'Matched', count: skillsList.filter(s => !isSkillGap(s)).length },
                { id: 'Required', label: 'Required', count: requiredSkills.length },
                { id: 'Preferred', label: 'Preferred', count: preferredSkills.length },
              ].map((chip) => (
                <button
                  key={chip.id}
                  type="button"
                  className={`filter-chip ${activeFilter === chip.id ? 'active' : ''}`}
                  onClick={() => setActiveFilter(chip.id)}
                  aria-pressed={activeFilter === chip.id}
                >
                  <span>{chip.label}</span>
                  <span className="filter-chip-count">{chip.count}</span>
                </button>
              ))}
            </div>

            {/* Skills List */}
            <div className="skills-list">
              {filteredBreakdownSkills.length === 0 ? (
                <div className="text-center py-8 text-muted text-sm">
                  No skills found matching filter "{activeFilter}".
                </div>
              ) : (
                filteredBreakdownSkills.map((item, idx) => {
                  const status = getSkillStatus(item);
                  const isGap = isSkillGap(item);
                  const reqLvl = formatLevel(item.required_level || item.level);
                  const skillImportance = (item.importance || 'required').toLowerCase() === 'preferred' ? 'Preferred' : 'Required';
                  const isAssessed = item.assessed_level !== null && item.assessed_level !== undefined;
                  const skillKey = item.skill || idx;
                  const isAvailable = isSkillAvailable(item.skill);

                  // CV Level display translation
                  const cvLvlDisplay = translateCvLevel(item.cv_level, item.matched);
                  const gapExplanation = isGap ? getGapExplanation(item) : null;

                  return (
                    <div
                      key={idx}
                      className="skill-card"
                      style={{
                        flexDirection: 'column',
                        alignItems: 'stretch',
                        borderLeft: isGap ? '4px solid #ef4444' : '4px solid #10b981',
                      }}
                    >
                      <div className="flex items-start justify-between gap-4 flex-wrap">
                        <div style={{ flex: '1 1 240px' }}>
                          <div className="font-semibold text-main text-base flex items-center gap-2 flex-wrap">
                            <span>{item.skill}</span>

                            {/* Importance Tag (Required / Preferred) */}
                            <span
                              className="badge"
                              style={{
                                fontSize: '0.7rem',
                                fontWeight: 600,
                                backgroundColor: skillImportance === 'Preferred' ? 'var(--neutral-100, #f3f4f6)' : 'rgba(99, 102, 241, 0.12)',
                                color: skillImportance === 'Preferred' ? 'var(--text-muted, #4b5563)' : 'var(--primary-700, #4338ca)',
                                border: skillImportance === 'Preferred' ? '1px solid var(--border-color, #e5e7eb)' : '1px solid var(--primary-300, #c7d2fe)',
                              }}
                            >
                              {skillImportance}
                            </span>

                            {/* Assessment status */}
                            {!isAssessed ? (
                              <span
                                className="text-xs font-normal text-muted"
                                style={{
                                  backgroundColor: 'var(--neutral-100, #f3f4f6)',
                                  padding: '0.15rem 0.5rem',
                                  borderRadius: '4px',
                                  border: '1px solid var(--border-color)',
                                }}
                              >
                                Not assessed yet
                              </span>
                            ) : (
                              <span
                                className="text-xs font-semibold"
                                style={{
                                  backgroundColor: 'var(--success-bg, #ecfdf5)',
                                  color: 'var(--success-color, #059669)',
                                  padding: '0.15rem 0.5rem',
                                  borderRadius: '4px',
                                  border: '1px solid #a7f3d0',
                                }}
                              >
                                Assessed: {formatLevel(item.assessed_level)}
                              </span>
                            )}
                          </div>

                          {/* Levels & AI Tooltip */}
                          <div className="text-xs text-muted mt-1.5 flex items-center gap-3 flex-wrap">
                            <span>
                              Required level: <strong style={{ color: 'var(--text-main)' }}>{reqLvl}</strong>
                            </span>
                            <span>•</span>
                            <span className="flex items-center gap-1.5">
                              <span>CV level:</span>
                              <strong style={{ color: 'var(--text-main)' }}>{cvLvlDisplay}</strong>
                              <span
                                className="ai-tooltip-trigger"
                                title="AI-estimated from your CV"
                                aria-label="AI-estimated from your CV"
                                tabIndex={0}
                              >
                                <Sparkles size={12} className="ai-tooltip-icon" aria-hidden="true" />
                                <span className="ai-tooltip-bubble" role="tooltip">AI-estimated from your CV</span>
                              </span>
                            </span>
                          </div>

                          {/* Short one-line explanation under each gap */}
                          {gapExplanation && (
                            <div className="text-xs font-medium mt-1.5" style={{ color: '#b91c1c' }}>
                              {gapExplanation}
                            </div>
                          )}
                        </div>

                        {/* Right side: Status badge & Take assessment button / text link */}
                        <div className="flex items-center gap-3 flex-wrap justify-end">
                          <span className={`status-badge ${status.className}`}>
                            {status.label}
                          </span>

                          {isAvailable ? (
                            isGap ? (
                              /* Primary button on gaps */
                              <button
                                type="button"
                                onClick={() => navigate(`/assessment/${encodeURIComponent(item.skill)}`)}
                                className="btn btn-primary"
                                style={{ padding: '0.4rem 0.85rem', fontSize: '0.825rem', whiteSpace: 'nowrap' }}
                                aria-label={`Take assessment for ${item.skill}`}
                              >
                                Take assessment
                              </button>
                            ) : (
                              /* Small text link on matched skills */
                              <button
                                type="button"
                                onClick={() => navigate(`/assessment/${encodeURIComponent(item.skill)}`)}
                                className="btn-link"
                                aria-label={`Verify ${item.skill} with assessment`}
                              >
                                Verify with assessment
                              </button>
                            )
                          ) : (
                            /* No assessment available */
                            <span
                              className="text-xs text-muted"
                              style={{ fontStyle: 'italic', maxWidth: '170px', textAlign: 'right', lineHeight: 1.3 }}
                            >
                              No assessment available: based on CV evidence only
                            </span>
                          )}
                        </div>
                      </div>

                      {/* Evidence toggle: Label "Why we think so" */}
                      <div style={{ marginTop: '0.75rem', paddingTop: '0.65rem', borderTop: '1px solid var(--border-color)' }}>
                        <button
                          type="button"
                          onClick={() => toggleEvidence(skillKey)}
                          className="btn btn-outline text-xs flex items-center gap-1.5"
                          aria-expanded={Boolean(expandedEvidence[skillKey])}
                          aria-controls={`evidence-panel-${idx}`}
                          style={{
                            padding: '0.25rem 0.65rem',
                            color: 'var(--text-muted)',
                            borderColor: 'var(--border-color)',
                            backgroundColor: expandedEvidence[skillKey] ? '#f1f5f9' : 'transparent',
                          }}
                        >
                          <FileText size={13} style={{ color: 'var(--primary-600)' }} />
                          <span>Why we think so</span>
                          {expandedEvidence[skillKey] ? <ChevronUp size={13} /> : <ChevronDown size={13} />}
                        </button>

                        {expandedEvidence[skillKey] && (
                          <div
                            id={`evidence-panel-${idx}`}
                            className="fade-in"
                            style={{
                              marginTop: '0.5rem',
                              padding: '0.75rem 1rem',
                              backgroundColor: '#f8fafc',
                              border: '1px solid var(--border-color)',
                              borderRadius: 'var(--radius-sm)',
                            }}
                          >
                            <div className="text-xs font-semibold text-muted uppercase tracking-wider mb-1 flex items-center gap-1.5">
                              <FileText size={12} style={{ color: 'var(--primary-600)' }} />
                              <span>CV Evidence:</span>
                            </div>
                            {item.evidence && item.evidence.trim() ? (
                              <blockquote
                                style={{
                                  margin: 0,
                                  paddingLeft: '0.75rem',
                                  borderLeft: '3px solid var(--primary-500)',
                                  color: 'var(--text-main)',
                                  fontSize: '0.825rem',
                                  fontStyle: 'italic',
                                  lineHeight: 1.5,
                                }}
                              >
                                "{item.evidence}"
                              </blockquote>
                            ) : (
                              <p className="text-muted text-xs italic" style={{ margin: 0 }}>
                                No matching text found in your CV
                              </p>
                            )}
                          </div>
                        )}
                      </div>
                    </div>
                  );
                })
              )}
            </div>
          </div>

          {/* 5. FOOTER CALL TO ACTION (ONLY IF AT LEAST ONE GAP HAS AN AVAILABLE ASSESSMENT) */}
          {showFooterCta && (
            <div
              className="card flex items-center justify-between flex-wrap gap-4"
              style={{ background: 'var(--primary-50)', border: '1px solid var(--primary-200)', marginTop: '1.5rem' }}
            >
              <div>
                <h3 className="font-semibold text-main text-base mb-1">Ready to complete your skill evaluation?</h3>
                <p className="text-sm text-muted">
                  Take targeted assessments on your priority gaps to verify your skills and improve candidate readiness.
                </p>
              </div>
              <button
                type="button"
                onClick={() => {
                  navigate(`/assessment/${encodeURIComponent(firstGapWithAssessment.skill)}`);
                }}
                className="btn btn-primary"
                style={{ padding: '0.7rem 1.5rem', whiteSpace: 'nowrap' }}
                aria-label={`Continue to assessment for ${firstGapWithAssessment.skill}`}
              >
                <span>Continue to Assessment</span>
                <ArrowRight size={18} />
              </button>
            </div>
          )}

          {/* Small footer note */}
          <div className="text-center text-xs text-muted mt-6 mb-8 py-2">
            Results are an estimate to guide upskilling, not a hiring decision.
          </div>
        </div>
      )}
    </div>
  );
}
