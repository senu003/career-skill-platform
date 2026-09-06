import React, { createContext, useState, useContext, useEffect } from 'react';
import { fetchWithAuth } from '../api';

const AssessmentContext = createContext();

export function AssessmentProvider({ children }) {
  const [analysisResult, setAnalysisResultState] = useState(() => {
    try {
      const saved = localStorage.getItem('career_platform_analysis');
      return saved ? JSON.parse(saved) : null;
    } catch (e) {
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

  const updateSkillResult = (skillName, resultData) => {
    if (!analysisResult || !analysisResult.skills) return;
    const updatedSkills = analysisResult.skills.map((s) => {
      if (s.skill.toLowerCase() === skillName.toLowerCase()) {
        return {
          ...s,
          assessed_level: resultData.assessed_level !== undefined ? resultData.assessed_level : s.assessed_level,
          level_gap: resultData.level_gap !== undefined ? resultData.level_gap : s.level_gap,
          total_score: resultData.total_score !== undefined ? resultData.total_score : s.total_score,
          is_weakness: resultData.is_weakness !== undefined ? resultData.is_weakness : s.is_weakness,
          weakness_reason: resultData.weakness_reason !== undefined ? resultData.weakness_reason : s.weakness_reason,
          priority: resultData.priority !== undefined ? resultData.priority : s.priority,
          recommendation: resultData.recommendation !== undefined ? resultData.recommendation : s.recommendation,
          recommendation_reason: resultData.recommendation_reason !== undefined ? resultData.recommendation_reason : s.recommendation_reason,
        };
      }
      return s;
    });

    const newResult = {
      ...analysisResult,
      skills: updatedSkills,
    };
    setAnalysisResult(newResult);
  };

  // Auto-restore latest session from API if no active analysis in memory/localStorage
  useEffect(() => {
    if (!analysisResult) {
      const fetchLatestSession = async () => {
        try {
          const sessRes = await fetchWithAuth('/cv/sessions');
          if (sessRes?.sessions && sessRes.sessions.length > 0) {
            const latestSess = sessRes.sessions[0];
            const detailRes = await fetchWithAuth(`/cv/sessions/${latestSess.analysis_id}`);
            if (detailRes) {
              setAnalysisResult(detailRes);
            }
          }
        } catch (err) {
          console.warn('Could not auto-restore latest session:', err);
        }
      };
      fetchLatestSession();
    }
  }, []);

  return (
    <AssessmentContext.Provider value={{ analysisResult, setAnalysisResult, updateSkillResult, clearAnalysis }}>
      {children}
    </AssessmentContext.Provider>
  );
}

export function useAssessment() {
  return useContext(AssessmentContext);
}

