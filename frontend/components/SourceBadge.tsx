import React from 'react';
import { getSourceConfig } from '../utils/sourceMapping';

interface SourceBadgeProps {
  source: string | undefined | null;
  size?: 'sm' | 'md' | 'lg';
  showLabel?: boolean;
  className?: string;
}

export const SourceBadge: React.FC<SourceBadgeProps> = ({
  source,
  size = 'sm',
  showLabel = true,
  className = '',
}) => {
  const config = getSourceConfig(source);

  const sizeClasses = {
    sm: 'text-[8px] px-1.5 py-0.5',
    md: 'text-[9px] px-2 py-0.5',
    lg: 'text-[10px] px-2.5 py-1',
  };

  return (
    <span
      className={`
        ${sizeClasses[size]}
        ${config.color}
        ${config.bgColor}
        ${config.borderColor}
        border
        rounded
        font-black
        uppercase
        tracking-tighter
        ${className}
      `}
    >
      {showLabel ? config.label : source || 'Unknown'}
    </span>
  );
};

export default SourceBadge;