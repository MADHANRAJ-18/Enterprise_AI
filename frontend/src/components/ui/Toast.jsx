import { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { CheckCircle, XCircle, Info, AlertTriangle, X } from 'lucide-react'

const icons = {
  success: <CheckCircle size={18} className="text-emerald-600" />,
  error: <XCircle size={18} className="text-red-600" />,
  info: <Info size={18} className="text-primary-600" />,
  warning: <AlertTriangle size={18} className="text-amber-600" />,
}

const styles = {
  success: 'bg-emerald-50 border-emerald-200 text-emerald-800',
  error: 'bg-red-50 border-red-200 text-red-800',
  info: 'bg-primary-50 border-primary-200 text-primary-800',
  warning: 'bg-amber-50 border-amber-200 text-amber-800',
}

export function Toast({ message, type = 'info', onClose }) {
  return (
    <AnimatePresence>
      {message && (
        <motion.div
          initial={{ opacity: 0, y: -20, scale: 0.95 }}
          animate={{ opacity: 1, y: 0, scale: 1 }}
          exit={{ opacity: 0, y: -20, scale: 0.95 }}
          className={`fixed top-4 right-4 z-[100] flex items-center gap-3 px-4 py-3 rounded-xl border shadow-lg ${styles[type]}`}
        >
          {icons[type]}
          <p className="text-sm font-medium">{message}</p>
          <button onClick={onClose} className="ml-1 opacity-60 hover:opacity-100 transition-opacity">
            <X size={14} />
          </button>
        </motion.div>
      )}
    </AnimatePresence>
  )
}

export function useToast() {
  const [toast, setToast] = useState(null)

  const showToast = (message, type = 'info', duration = 4000) => {
    setToast({ message, type })
    setTimeout(() => setToast(null), duration)
  }

  const ToastComponent = () => (
    <Toast
      message={toast?.message}
      type={toast?.type}
      onClose={() => setToast(null)}
    />
  )

  return { showToast, ToastComponent }
}
