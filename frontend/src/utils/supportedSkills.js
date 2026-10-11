// Supported skills for technical assessment
export const SUPPORTED_SKILLS_SET = new Set([
  'javascript',
  'js',
  'react',
  'react.js',
  'reactjs',
  'postgresql',
  'postgres',
  'sql',
  'python',
  'python3',
  'py',
  'docker'
]);

export const SUPPORTED_SKILLS_LIST = [
  'JavaScript',
  'React',
  'PostgreSQL',
  'SQL',
  'Python',
  'Docker'
];

/**
 * Normalizes a skill string by lowercasing, trimming, and stripping punctuation/whitespace.
 * @param {string} str
 * @returns {string}
 */
function normalizeKey(str) {
  if (!str) return '';
  return str.toLowerCase().replace(/[^a-z0-9]/g, '');
}

/**
 * Checks if a skill name is supported for MCQ technical assessment.
 * Handles case variations (e.g. "PYTHON", "python"), format variations (e.g. "React.js", "python 3", " SQL "),
 * and dynamic matching against server-provided supported skills from /assessment/supported-skills.
 * 
 * @param {string} skillName 
 * @param {Array<string>|null} serverSupportedList Optional list from /assessment/supported-skills
 * @returns {boolean}
 */
export function isSupportedSkill(skillName, serverSupportedList = null) {
  if (!skillName || typeof skillName !== 'string') return false;

  const clean = skillName.trim().toLowerCase();
  if (SUPPORTED_SKILLS_SET.has(clean)) return true;

  const normalized = normalizeKey(clean);
  if (!normalized) return false;

  // Check against static normalized set
  for (const s of SUPPORTED_SKILLS_SET) {
    if (normalizeKey(s) === normalized) return true;
  }

  // Canonical alias groups
  const aliasFamilies = [
    new Set(['javascript', 'js']),
    new Set(['react', 'reactjs']),
    new Set(['postgresql', 'postgres', 'sql']),
    new Set(['python', 'py', 'python3']),
    new Set(['docker'])
  ];

  for (const family of aliasFamilies) {
    if (family.has(normalized)) return true;
  }

  // Check against serverSupportedList if supplied
  if (Array.isArray(serverSupportedList) && serverSupportedList.length > 0) {
    for (const serverSkill of serverSupportedList) {
      if (typeof serverSkill === 'string') {
        const sClean = serverSkill.trim().toLowerCase();
        if (sClean === clean) return true;
        const sNorm = normalizeKey(sClean);
        if (sNorm === normalized) return true;
        for (const family of aliasFamilies) {
          if (family.has(normalized) && (family.has(sNorm) || family.has(sClean))) {
            return true;
          }
        }
      }
    }
  }

  return false;
}
