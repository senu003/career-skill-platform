/**
 * Shared formatting and level translation utilities for UI presentation.
 */

export function formatLevel(lvl) {
  if (!lvl) return 'N/A';
  const clean = String(lvl).trim().toLowerCase();
  if (clean === 'unspecified' || clean === 'none') return 'Any Level';
  return clean.charAt(0).toUpperCase() + clean.slice(1);
}

export function translateRequiredLevel(level) {
  if (!level) return 'Any Level';
  const clean = String(level).trim().toLowerCase();
  if (clean === 'unspecified' || clean === 'none' || clean === 'null') return 'Any Level';
  if (clean === 'basic') return 'Basic';
  if (clean === 'intermediate') return 'Intermediate';
  if (clean === 'advanced') return 'Advanced';
  return formatLevel(level);
}

export function translateCvLevel(cvLevel, isMatched) {
  if (!cvLevel) {
    return isMatched ? 'Mentioned (level unclear)' : 'Not in CV';
  }
  const clean = String(cvLevel).trim().toLowerCase();
  if (clean === 'unspecified') return 'Mentioned (level unclear)';
  if (clean === 'not_found' || clean === 'null' || clean === 'none') return 'Not in CV';
  if (clean === 'basic') return 'Basic';
  if (clean === 'intermediate') return 'Intermediate';
  if (clean === 'advanced') return 'Advanced';
  return formatLevel(cvLevel);
}

export function getLevelPillClass(levelStr, isMissing = false) {
  if (isMissing) return 'level-pill-missing';
  const s = String(levelStr || '').toLowerCase();
  if (s.includes('adv')) return 'level-pill-advanced';
  if (s.includes('inter')) return 'level-pill-intermediate';
  if (s.includes('bas')) return 'level-pill-basic';
  if (s.includes('not in cv') || s.includes('missing')) return 'level-pill-missing';
  return 'level-pill-any';
}

export function formatScore(score) {
  if (score === null || score === undefined) return null;
  if (typeof score === 'number') {
    return `${Math.round(score > 1 ? score : score * 100)}%`;
  }
  return score;
}

export function formatConfidence(conf) {
  if (conf === null || conf === undefined) return null;
  const num = typeof conf === 'number' ? conf : parseFloat(conf);
  if (isNaN(num)) return null;
  const percent = Math.round(num > 1 ? num : num * 100);
  return `${percent}%`;
}

export function formatDate(isoString) {
  if (!isoString) return 'N/A';
  const d = new Date(isoString);
  return d.toLocaleDateString('en-US', {
    year: 'numeric',
    month: 'long',
    day: 'numeric',
  });
}

export function formatTime(seconds) {
  const mins = Math.floor(seconds / 60);
  const secs = seconds % 60;
  return `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
}
