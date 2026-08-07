/**
 * UploadProgress.jsx
 * ─────────────────────────────────────────────────────────────
 * Animated per-file upload progress list.
 * Shows file name, size, animated progress bar, success/error state.
 * ─────────────────────────────────────────────────────────────
 */

import { motion, AnimatePresence } from 'framer-motion'
import { CheckCircle2, XCircle, Loader2, File, FileText } from 'lucide-react'
import { formatFileSize } from '../../services/documentService'

// Status-derived styles
const STATUS_CONFIG = {
  uploading: {
    barColor: 'bg-primary-500',
    icon: <Loader2 size={16} className="text-primary-500 animate-spin" />,
    bg: 'bg-primary-50 border-primary-100',
    label: 'Uploading…',
    labelColor: 'text-primary-600',
  },
  success: {
    barColor: 'bg-emerald-500',
    icon: <CheckCircle2 size={16} className="text-emerald-500" />,
    bg: 'bg-emerald-50 border-emerald-100',
    label: 'Uploaded',
    labelColor: 'text-emerald-600',
  },
  error: {
    barColor: 'bg-red-500',
    icon: <XCircle size={16} className="text-red-500" />,
    bg: 'bg-red-50 border-red-100',
    label: 'Failed',
    labelColor: 'text-red-600',
  },
}

function FileIcon({ fileName }) {
  const ext = fileName?.split('.').pop().toLowerCase()
  const config = {
    pdf: 'text-red-500',
    docx: 'text-blue-500',
    txt: 'text-emerald-500',
  }
  const color = config[ext] || 'text-surface-400'
  return <FileText size={16} className={color} />
}

/**
 * @param {Array} items - Array of { id, file, status, progress, error }
 *   status: 'uploading' | 'success' | 'error'
 *   progress: 0–100
 */
export function UploadProgress({ items }) {
  if (!items || items.length === 0) return null

  return (
    <AnimatePresence>
      {items.length > 0 && (
        <motion.div
          initial={{ opacity: 0, height: 0 }}
          animate={{ opacity: 1, height: 'auto' }}
          exit={{ opacity: 0, height: 0 }}
          transition={{ duration: 0.25 }}
          className="overflow-hidden"
        >
          <div className="space-y-2 pt-1">
            <p className="text-xs font-semibold text-surface-400 uppercase tracking-wide px-1">
              Upload Queue
            </p>
            {items.map((item) => {
              const cfg = STATUS_CONFIG[item.status] || STATUS_CONFIG.uploading
              return (
                <motion.div
                  key={item.id}
                  initial={{ opacity: 0, x: -12 }}
                  animate={{ opacity: 1, x: 0 }}
                  exit={{ opacity: 0, x: 12 }}
                  transition={{ type: 'spring', stiffness: 300, damping: 30 }}
                  className={`border rounded-xl px-4 py-3 ${cfg.bg}`}
                >
                  {/* Row: icon + name + status icon */}
                  <div className="flex items-center gap-3">
                    <div className="w-8 h-8 rounded-lg bg-white/70 border border-surface-100 flex items-center justify-center flex-shrink-0">
                      <FileIcon fileName={item.file?.name} />
                    </div>
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-semibold text-surface-900 truncate">
                        {item.file?.name}
                      </p>
                      <div className="flex items-center gap-2 mt-0.5">
                        <span className={`text-xs font-medium ${cfg.labelColor}`}>
                          {item.error || cfg.label}
                        </span>
                        {item.file?.size && (
                          <span className="text-xs text-surface-400">
                            · {formatFileSize(item.file.size)}
                          </span>
                        )}
                      </div>
                    </div>
                    <div className="flex-shrink-0">{cfg.icon}</div>
                  </div>

                  {/* Progress bar */}
                  {item.status === 'uploading' && (
                    <div className="mt-2.5 bg-white/60 rounded-full h-1.5 overflow-hidden">
                      <motion.div
                        initial={{ width: '0%' }}
                        animate={{ width: `${item.progress || 0}%` }}
                        transition={{ duration: 0.3, ease: 'easeOut' }}
                        className={`h-full rounded-full ${cfg.barColor}`}
                      />
                    </div>
                  )}
                  {item.status === 'success' && (
                    <div className="mt-2.5 bg-white/60 rounded-full h-1.5 overflow-hidden">
                      <div className="h-full w-full rounded-full bg-emerald-400" />
                    </div>
                  )}
                </motion.div>
              )
            })}
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  )
}
