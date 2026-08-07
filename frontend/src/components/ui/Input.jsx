import { forwardRef } from 'react'

export const Input = forwardRef(function Input(
  { label, error, prefix, suffix, className = '', ...props },
  ref
) {
  return (
    <div className="w-full">
      {label && (
        <label className="block text-sm font-medium text-surface-700 mb-1.5">
          {label}
        </label>
      )}
      <div className="relative flex items-center">
        {prefix && (
          <div className="absolute left-3 text-surface-400 pointer-events-none">
            {prefix}
          </div>
        )}
        <input
          ref={ref}
          className={`w-full px-3.5 py-2.5 text-sm bg-surface-50 border rounded-lg outline-none transition-all duration-150 placeholder:text-surface-400
            ${error ? 'border-red-400 focus:ring-2 focus:ring-red-500/20 focus:border-red-400' : 'border-surface-200 focus:ring-2 focus:ring-primary-500/20 focus:border-primary-400'}
            ${prefix ? 'pl-9' : ''}
            ${suffix ? 'pr-9' : ''}
            ${className}`}
          {...props}
        />
        {suffix && (
          <div className="absolute right-3 text-surface-400">
            {suffix}
          </div>
        )}
      </div>
      {error && (
        <p className="mt-1.5 text-xs text-red-600">{error}</p>
      )}
    </div>
  )
})
