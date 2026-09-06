// Supported skills for initial technical assessment
export const SUPPORTED_SKILLS_SET = new Set(['javascript', 'js', 'react', 'postgresql', 'postgres']);

export const SUPPORTED_SKILLS_LIST = ['JavaScript', 'React', 'PostgreSQL'];

/**
 * Checks if a skill name is supported for MCQ technical assessment.
 * @param {string} skillName 
 * @returns {boolean}
 */
export function isSupportedSkill(skillName) {
  if (!skillName) return false;
  const clean = skillName.trim().toLowerCase();
  return SUPPORTED_SKILLS_SET.has(clean);
}
