import React from 'react';
import { getLevelPillClass } from '../utils/formatters';

/**
 * Reusable skill level badge component with standardized styling.
 */
export default function LevelBadge({ level, isMissing = false, className = '' }) {
  const pillClass = getLevelPillClass(level, isMissing);
  return (
    <span className={`level-pill ${pillClass} ${className}`.trim()}>
      {level || 'Any Level'}
    </span>
  );
}
