export function Badge({ children, variant = 'gray', className = '' }) {
  const variants = {
    blue: 'bg-primary-50 text-primary-700 border border-primary-100',
    green: 'bg-emerald-50 text-emerald-700 border border-emerald-100',
    yellow: 'bg-amber-50 text-amber-700 border border-amber-100',
    red: 'bg-red-50 text-red-700 border border-red-100',
    gray: 'bg-surface-100 text-surface-600 border border-surface-200',
    purple: 'bg-violet-50 text-violet-700 border border-violet-100',
    indigo: 'bg-indigo-50 text-indigo-700 border border-indigo-100',
  }

  return (
    <span
      className={`inline-flex items-center gap-1 px-2 py-0.5 text-xs font-medium rounded-full ${variants[variant]} ${className}`}
    >
      {children}
    </span>
  )
}
