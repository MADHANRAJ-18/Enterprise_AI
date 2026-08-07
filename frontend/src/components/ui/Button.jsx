import { Spinner } from './Spinner'

export function Button({
  children,
  variant = 'primary',
  size = 'md',
  loading = false,
  disabled = false,
  className = '',
  ...props
}) {
  const base = 'inline-flex items-center justify-center gap-2 font-semibold rounded-lg transition-all duration-150 active:scale-[0.98] disabled:opacity-50 disabled:cursor-not-allowed'

  const variants = {
    primary: 'text-white bg-primary-600 hover:bg-primary-700 shadow-sm',
    secondary: 'text-surface-700 bg-surface-50 border border-surface-200 hover:bg-surface-100 hover:border-surface-300 shadow-sm',
    ghost: 'text-surface-600 hover:bg-surface-100 hover:text-surface-900',
    danger: 'text-white bg-red-600 hover:bg-red-700 shadow-sm',
    outline: 'text-primary-600 border border-primary-200 hover:bg-primary-50',
  }

  const sizes = {
    xs: 'px-2.5 py-1.5 text-xs',
    sm: 'px-3 py-2 text-sm',
    md: 'px-4 py-2.5 text-sm',
    lg: 'px-5 py-3 text-base',
  }

  return (
    <button
      className={`${base} ${variants[variant]} ${sizes[size]} ${className}`}
      disabled={disabled || loading}
      {...props}
    >
      {loading && <Spinner size="sm" />}
      {children}
    </button>
  )
}
