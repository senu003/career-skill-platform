import React, { createContext, useState, useContext } from 'react';
import { fetchWithAuth } from '../api';

const AssessmentContext = createContext();

export function AssessmentProvider({ children }) {
  const [analysisResult, setAnalysisResultState] = useState(() => {
    try {
      const saved = sessionStorage.getItem('career_platform_analysis');
      return saved ? JSON.parse(saved) : null;
    } catch {
      return null;
    }
  });

  const setAnalysisResult = (data) => {
    setAnalysisResultState(data);
    try {
      if (data) {
        sessionStorage.setItem('career_platform_analysis', JSON.stringify(data));
      } else {
        sessionStorage.removeItem('career_platform_analysis');
        localStorage.removeItem('career_platform_analysis');
      }
    } catch (e) {
      console.warn('Failed to save analysis result to sessionStorage:', e);
    }
  };

  const clearAnalysis = () => {
    setAnalysisResult(null);
  };

  const [isRefreshing, setIsRefreshing] = useState(false);

  const refreshAnalysis = async (targetId = null) => {
    const idToUse = targetId || analysisResult?.analysis_id;
    if (!idToUse) return null;

    setIsRefreshing(true);
    try {
      const detailRes = await fetchWithAuth(`/cv/sessions/${idToUse}`);
      if (detailRes) {
        setAnalysisResult(detailRes);
        return detailRes;
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
          attempt_id: resultData.attempt_id !== undefined ? resultData.attempt_id : s.attempt_id,
          completed_at: resultData.completed_at !== undefined ? resultData.completed_at : s.completed_at,
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


  return (
    <AssessmentContext.Provider value={{ analysisResult, setAnalysisResult, updateSkillResult, clearAnalysis, refreshAnalysis, isRefreshing }}>
      {children}
    </AssessmentContext.Provider>
  );
}

export function useAssessment() {
  return useContext(AssessmentContext);
}

