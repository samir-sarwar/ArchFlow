import type { ButtonHTMLAttributes } from 'react';

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'primary' | 'secondary' | 'ghost';
  size?: 'sm' | 'md' | 'lg';
}

const variants = {
  primary: 'bg-primary-600 text-white hover:bg-primary-500',
  secondary: 'bg-gray-100 text-gray-700 hover:bg-gray-200 border border-gray-300 dark:bg-white/5 dark:text-white/70 dark:hover:bg-white/10 dark:border-white/10',
  ghost: 'text-gray-500 hover:bg-gray-100 hover:text-gray-800 dark:text-white/50 dark:hover:bg-white/5 dark:hover:text-white/80',
};

const sizes = {
  sm: 'px-2 py-1 text-xs',
  md: 'px-4 py-2 text-sm',
  lg: 'px-6 py-3 text-base',
};

export function Button({
  variant = 'primary',
  size = 'md',
  className = '',
  ...props
}: ButtonProps) {
  return (
    <button
      className={`rounded-lg font-medium transition-colors disabled:opacity-50 ${variants[variant]} ${sizes[size]} ${className}`}
      {...props}
    />
  );
}
