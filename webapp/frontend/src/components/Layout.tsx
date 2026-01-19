// Main layout component

import type { ReactNode } from 'react';

interface LayoutProps {
  children: ReactNode;
  className?: string;
}

// Inline SVG pattern for food ingredients
const FoodPatternSVG = () => (
  <svg
    className="absolute inset-0 w-full h-full pointer-events-none"
    style={{ opacity: 0.04 }}
    xmlns="http://www.w3.org/2000/svg"
  >
    <defs>
      <pattern id="food-pattern" x="0" y="0" width="120" height="120" patternUnits="userSpaceOnUse">
        {/* Apple */}
        <path d="M30 20c-5 0-8 3-8 8s3 10 8 10 8-5 8-10-3-8-8-8zm0-5c1-3 3-5 5-5" fill="none" stroke="currentColor" strokeWidth="1.5"/>
        {/* Carrot */}
        <path d="M80 25l-15 25m15-25c2-1 4-1 5 1m-5-1c-2-1-4-1-5 1" fill="none" stroke="currentColor" strokeWidth="1.5"/>
        {/* Leaf */}
        <path d="M20 80c0-8 6-15 15-15s15 7 15 15c-5-3-10-5-15-5s-10 2-15 5z" fill="none" stroke="currentColor" strokeWidth="1.5"/>
        {/* Egg */}
        <ellipse cx="90" cy="85" rx="8" ry="10" fill="none" stroke="currentColor" strokeWidth="1.5"/>
        {/* Berry */}
        <circle cx="60" cy="60" r="6" fill="none" stroke="currentColor" strokeWidth="1.5"/>
        <circle cx="68" cy="55" r="5" fill="none" stroke="currentColor" strokeWidth="1.5"/>
        <circle cx="65" cy="65" r="4" fill="none" stroke="currentColor" strokeWidth="1.5"/>
      </pattern>
    </defs>
    <rect width="100%" height="100%" fill="url(#food-pattern)" />
  </svg>
);

export function Layout({ children, className = '' }: LayoutProps) {
  return (
    <div className={`min-h-screen pb-safe relative ${className}`}>
      {/* Background pattern */}
      <div className="fixed inset-0 overflow-hidden" style={{ color: 'var(--text-primary)' }}>
        <FoodPatternSVG />
      </div>
      <main className="max-w-lg mx-auto px-4 py-6 relative z-10">
        {children}
      </main>
    </div>
  );
}

interface PageHeaderProps {
  title: string;
  subtitle?: string;
  action?: ReactNode;
}

export function PageHeader({ title, subtitle, action }: PageHeaderProps) {
  return (
    <div className="flex items-start justify-between mb-6">
      <div>
        <h1 className="text-2xl font-bold" style={{ color: 'var(--text-primary)' }}>
          {title}
        </h1>
        {subtitle && (
          <p className="text-sm mt-1" style={{ color: 'var(--text-secondary)' }}>
            {subtitle}
          </p>
        )}
      </div>
      {action && <div>{action}</div>}
    </div>
  );
}

interface CardProps {
  children: ReactNode;
  className?: string;
  onClick?: () => void;
}

export function Card({ children, className = '', onClick }: CardProps) {
  return (
    <div
      className={`glass-card p-4 ${onClick ? 'cursor-pointer active:scale-[0.99] transition-transform' : ''} ${className}`}
      onClick={onClick}
    >
      {children}
    </div>
  );
}

interface ButtonProps {
  children: ReactNode;
  variant?: 'primary' | 'secondary';
  size?: 'sm' | 'md' | 'lg';
  disabled?: boolean;
  loading?: boolean;
  className?: string;
  onClick?: () => void;
  type?: 'button' | 'submit';
}

export function Button({
  children,
  variant = 'primary',
  size = 'md',
  disabled = false,
  loading = false,
  className = '',
  onClick,
  type = 'button',
}: ButtonProps) {
  const sizeClasses = {
    sm: 'px-4 py-2 text-sm',
    md: 'px-6 py-3',
    lg: 'px-8 py-4 text-lg',
  };

  const baseClass = variant === 'primary' ? 'btn-primary' : 'btn-secondary';

  return (
    <button
      type={type}
      className={`${baseClass} ${sizeClasses[size]} ${disabled || loading ? 'opacity-50 cursor-not-allowed' : ''} flex items-center justify-center ${className}`}
      disabled={disabled || loading}
      onClick={onClick}
    >
      {loading ? (
        <span className="flex items-center gap-2">
          <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24">
            <circle
              className="opacity-25"
              cx="12"
              cy="12"
              r="10"
              stroke="currentColor"
              strokeWidth="4"
              fill="none"
            />
            <path
              className="opacity-75"
              fill="currentColor"
              d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
            />
          </svg>
          Загрузка...
        </span>
      ) : (
        children
      )}
    </button>
  );
}

interface LoadingSpinnerProps {
  size?: 'sm' | 'md' | 'lg';
  className?: string;
}

export function LoadingSpinner({ size = 'md', className = '' }: LoadingSpinnerProps) {
  const sizeClasses = {
    sm: 'h-4 w-4',
    md: 'h-8 w-8',
    lg: 'h-12 w-12',
  };

  return (
    <div className={`flex justify-center items-center ${className}`}>
      <svg
        className={`animate-spin ${sizeClasses[size]}`}
        style={{ color: 'var(--accent)' }}
        viewBox="0 0 24 24"
      >
        <circle
          className="opacity-25"
          cx="12"
          cy="12"
          r="10"
          stroke="currentColor"
          strokeWidth="4"
          fill="none"
        />
        <path
          className="opacity-75"
          fill="currentColor"
          d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
        />
      </svg>
    </div>
  );
}

interface EmptyStateProps {
  icon?: ReactNode;
  title: string;
  description?: string;
  action?: ReactNode;
}

export function EmptyState({ icon, title, description, action }: EmptyStateProps) {
  return (
    <div className="flex flex-col items-center justify-center py-12 text-center">
      {icon && (
        <div className="mb-4" style={{ color: 'var(--text-tertiary)' }}>
          {icon}
        </div>
      )}
      <h3 className="text-lg font-medium mb-2" style={{ color: 'var(--text-primary)' }}>
        {title}
      </h3>
      {description && (
        <p className="text-sm mb-4" style={{ color: 'var(--text-secondary)' }}>
          {description}
        </p>
      )}
      {action && <div>{action}</div>}
    </div>
  );
}

export default Layout;
