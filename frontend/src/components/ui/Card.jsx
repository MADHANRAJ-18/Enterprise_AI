export function Card({ children, className = '', hover = false, ...props }) {
  return (
    <div
      className={`bg-surface-100 rounded-xl border border-surface-200/60 shadow-card ${hover ? 'transition-shadow duration-200 hover:shadow-card-hover cursor-pointer' : ''} ${className}`}
      {...props}
    >
      {children}
    </div>
  )
}

export function CardHeader({ children, className = '' }) {
  return (
    <div className={`px-5 py-4 border-b border-surface-100 ${className}`}>
      {children}
    </div>
  )
}

export function CardBody({ children, className = '' }) {
  return <div className={`px-5 py-4 ${className}`}>{children}</div>
}

export function CardFooter({ children, className = '' }) {
  return (
    <div className={`px-5 py-3 border-t border-surface-100 bg-surface-50/50 rounded-b-xl ${className}`}>
      {children}
    </div>
  )
}
