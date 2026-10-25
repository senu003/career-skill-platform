import React, { createContext, useState, useContext, useEffect } from 'react';
import { fetchWithAuth } from '../api';

const AssessmentContext = createContext();

export function AssessmentProvider({ children }) {
  const [analysisResult, setAnalysisResultState] = useState(() => {
    try {
      const saved = localStorage.getItem('career_platform_analysis');
      return saved ? JSON.parse(saved) : null;
    } catch {
      return null;
    }
  });

  const setAnalysisResult = (data) => {
    setAnalysisResultState(data);
    try {
      if (data) {
        localStorage.setItem('career_platform_analysis', JSON.stringify(data));
      } else {
        localStorage.removeItem('career_platform_analysis');
      }
    } catch (e) {
      console.warn('Failed to save analysis result to localStorage:', e);
    }
  };

  const clearAnalysis = () => {
    setAnalysisResult(null);
  };

  const [isRefreshing, setIsRefreshing] = useState(false);

  const refreshAnalysis = async (targetId = null) => {
    const idToUse = targetId || analysisResult?.analysis_id;
    setIsRefreshing(true);
    try {
      if (idToUse) {
        const detailRes = await fetchWithAuth(`/cv/sessions/${idToUse}`);
        if (detailRes) {
          setAnalysisResult(detailRes);
          return detailRes;
        }
      } else {
        const sessRes = await fetchWithAuth('/cv/sessions');
        if (sessRes?.sessions && sessRes.sessions.length > 0) {
          const latestSess = sessRes.sessions[0];
          const detailRes = await fetchWithAuth(`/cv/sessions/${latestSess.analysis_id}`);
          if (detailRes) {
            setAnalysisResult(detailRes);
            return detailRes;
          }
        }
      }
    } catch (err) {
      console.warn('Could not refresh analysis session:', err);
    } finally {
      setIsRefreshing(false);
    }
    return null;
  };

  const updateSkillResult = (skillName, resultData) => {
    if (!analysisResult || !analysisResult.skills) return Promise.resolve(null);

    const updatedSkills = analysisResult.skills.map((s) => {
      if (s.skill.toLowerCase() === skillName.toLowerCase()) {
        return {
          ...s,
          // Strictly preserve CV evidence
          matched: s.matched,
          cv_match_status: s.cv_match_status,
          cv_level: s.cv_level,
          assessed_level: resultData.assessed_level !== undefined ? resultData.assessed_level : s.assessed_level,
          level_gap: resultData.level_gap !== undefined ? resultData.level_gap : s.level_gap,
          total_score: resultData.total_score !== undefined ? resultData.total_score : s.total_score,
          is_weakness: resultData.is_weakness !== undefined ? resultData.is_weakness : s.is_weakness,
          weakness_reason: resultData.weakness_reason !== undefined ? resultData.weakness_reason : s.weakness_reason,
          priority: resultData.priority !== undefined ? resultData.priority : s.priority,
          recommendation: resultData.recommendation !== undefined ? resultData.recommendation : s.recommendation,
          recommendation_reason: resultData.recommendation_reason !== undefined ? resultData.recommendation_reason : s.recommendation_reason,
          skill_recommendation: resultData.skill_recommendation !== undefined ? resultData.skill_recommendation : s.skill_recommendation,
          recommendation_confidence: resultData.recommendation_confidence !== undefined ? resultData.recommendation_confidence : s.recommendation_confidence,
          improvement_probability: resultData.improvement_probability !== undefined ? resultData.improvement_probability : s.improvement_probability,
        };
      }
      return s;
    });

    const newResult = {
      ...analysisResult,
      skills: updatedSkills,
      matched_skills: (analysisResult.matched_skills || []).map((ms) => {
        if (ms.skill.toLowerCase() === skillName.toLowerCase()) {
          const up = updatedSkills.find((u) => u.skill.toLowerCase() === skillName.toLowerCase());
          return up || ms;
        }
        return ms;
      }),
      missing_skills: (analysisResult.missing_skills || []).map((ms) => {
        if (ms.skill.toLowerCase() === skillName.toLowerCase()) {
          const up = updatedSkills.find((u) => u.skill.toLowerCase() === skillName.toLowerCase());
          return up || ms;
        }
        return ms;
      }),
    };
    setAnalysisResult(newResult);

    // If session ID exists, trigger authoritative backend sync
    if (analysisResult?.analysis_id) {
      return refreshAnalysis(analysisResult.analysis_id);
    }
    return Promise.resolve(newResult);
  };

  // Auto-restore latest session from API if no active analysis in memory/localStorage
  useEffect(() => {
    let isCancelled = false;
    if (!analysisResult) {
      const fetchLatestSession = async () => {
        try {
          const sessRes = await fetchWithAuth('/cv/sessions');
          if (isCancelled) return;
          if (sessRes?.sessions && sessRes.sessions.length > 0) {
            const latestSess = sessRes.sessions[0];
            const detailRes = await fetchWithAuth(`/cv/sessions/${latestSess.analysis_id}`);
            if (isCancelled) return;
            if (detailRes) {
              setAnalysisResultState((prev) => {
                // Never overwrite a freshly set or active analysis
                if (prev) return prev;
                try {
                  localStorage.setItem('career_platform_analysis', JSON.stringify(detailRes));
                } catch {}
                return detailRes;
              });
            }
          }
        } catch (err) {
          console.warn('Could not auto-restore latest session:', err);
        }
      };
      fetchLatestSession();
    }
    return () => {
      isCancelled = true;
    };
  }, [analysisResult]);

  return (
    <AssessmentContext.Provider value={{ analysisResult, setAnalysisResult, updateSkillResult, clearAnalysis, refreshAnalysis, isRefreshing }}>
      {children}
    </AssessmentContext.Provider>
  );
}

export function useAssessment() {
  return useContext(AssessmentContext);
}

