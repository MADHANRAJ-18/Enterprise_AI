/**
 * DocumentDetailModal.jsx
 * ─────────────────────────────────────────────────────────────
 * Slide-in modal displaying full document metadata.
 * Actions: Download, Delete.
 * ─────────────────────────────────────────────────────────────
 */

import { motion, AnimatePresence } from 'framer-motion'
import {
  X, FileText, File, Tag, HardDrive, Calendar,
  Activity, FolderOpen, Download, Trash2, ExternalLink
} from 'lucide-react'
import { Badge } from '../ui/Badge'
import { Button } from '../ui/Button'
import { formatFileSize } from '../../services/documentService'

const STATUS_BADGE = {
  Uploaded:   'blue',
  Processing: 'yellow',
  Indexed:    'green',
  Failed:     'red',
}

const CATEGORY_BADGE_COLOR = {
  HR: 'purple', Finance: 'green', Legal: 'yellow',
  IT: 'indigo', Policies: 'red', Research: 'blue', General: 'gray',
}

const FILE_TYPE_STYLE = {
  PDF:  { color: 'text-red-600', bg: 'bg-red-50 border-red-100' },
  DOCX: { color: 'text-blue-600', bg: 'bg-blue-50 border-blue-100' },
  TXT:  { color: 'text-emerald-600', bg: 'bg-emerald-50 border-emerald-100' },
}

function MetaRow({ icon: Icon, label, value }) {
  return (
    <div className="flex items-start gap-3 py-3 border-b border-surface-100 last:border-0">
      <div className="w-8 h-8 rounded-lg bg-surface-100 border border-surface-200 flex items-center justify-center flex-shrink-0 mt-0.5">
        <Icon size={14} className="text-surface-500" />
      </div>
      <div className="flex-1 min-w-0">
        <p className="text-xs font-semibold text-surface-400 uppercase tracking-wide">{label}</p>
        <p className="text-sm font-medium text-surface-900 mt-0.5 break-all">{value}</p>
      </div>
    </div>
  )
}

function formatDate(iso) {
  if (!iso) return '—'
  return new Date(iso).toLocaleString('en-US', {
    year: 'numeric', month: 'long', day: 'numeric',
    hour: '2-digit', minute: '2-digit',
  })
}

/**
 * @param {object|null} doc      - Document row (null = closed)
 * @param {Function}    onClose  - Close handler
 * @param {Function}    onDownload - Download handler
 * @param {Function}    onDelete   - Delete handler
 * @param {boolean}     isDeleting - Loading state for delete
 */
export function DocumentDetailModal({ doc, onClose, onDownload, onDelete, isDeleting }) {
  const isOpen = !!doc

  const fileTypeStyle = FILE_TYPE_STYLE[doc?.file_type] || { color: 'text-surface-500', bg: 'bg-surface-100 border-surface-200' }

  return (
    <AnimatePresence>
      {isOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-end">
          {/* Backdrop */}
          <motion.div
            key="backdrop"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="absolute inset-0 bg-surface-900/30 backdrop-blur-sm"
            onClick={onClose}
          />

          {/* Side Panel */}
          <motion.div
            key="panel"
            initial={{ x: '100%', opacity: 0 }}
            animate={{ x: 0, opacity: 1 }}
            exit={{ x: '100%', opacity: 0 }}
            transition={{ type: 'spring', damping: 30, stiffness: 300 }}
            className="relative z-10 w-full max-w-sm h-full bg-surface-100 shadow-2xl flex flex-col border-l border-surface-200"
          >
            {/* Header */}
            <div className="flex items-center justify-between px-5 py-4 border-b border-surface-200">
              <div className="flex items-center gap-2.5">
                <div className={`w-9 h-9 rounded-xl border flex items-center justify-center ${fileTypeStyle.bg}`}>
                  <FileText size={16} className={fileTypeStyle.color} />
                </div>
                <div>
                  <h2 className="text-sm font-bold text-surface-900">Document Details</h2>
                  <p className="text-xs text-surface-400">{doc?.file_type} File</p>
                </div>
              </div>
              <button
                onClick={onClose}
                className="p-1.5 rounded-lg text-surface-400 hover:text-surface-700 hover:bg-surface-200 transition-colors"
              >
                <X size={16} />
              </button>
            </div>

            {/* Content */}
            <div className="flex-1 overflow-y-auto px-5 py-4">
              {/* File name hero */}
              <div className="mb-5 p-4 bg-gradient-to-br from-primary-50 to-primary-100/50 border border-primary-100 rounded-2xl">
                <p className="text-xs font-semibold text-primary-500 uppercase tracking-wide mb-1">File Name</p>
                <p className="text-sm font-bold text-surface-900 break-all leading-relaxed">{doc?.file_name}</p>
              </div>

              {/* Status + Category badges */}
              <div className="flex items-center gap-2 mb-5 flex-wrap">
                <Badge variant={STATUS_BADGE[doc?.status] || 'gray'}>
                  <Activity size={10} />
                  {doc?.status}
                </Badge>
                <Badge variant={CATEGORY_BADGE_COLOR[doc?.category] || 'gray'}>
                  <Tag size={10} />
                  {doc?.category}
                </Badge>
              </div>

              {/* Metadata rows */}
              <div>
                <MetaRow icon={File} label="File Type" value={doc?.file_type || '—'} />
                <MetaRow icon={HardDrive} label="File Size" value={formatFileSize(doc?.file_size || 0)} />
                <MetaRow icon={Calendar} label="Uploaded At" value={formatDate(doc?.uploaded_at)} />
                <MetaRow icon={FolderOpen} label="Category" value={doc?.category || '—'} />
                <MetaRow icon={Activity} label="Status" value={doc?.status || '—'} />
                <MetaRow
                  icon={ExternalLink}
                  label="Storage Path"
                  value={doc?.storage_path || '—'}
                />
              </div>
            </div>

            {/* Footer actions */}
            <div className="px-5 py-4 border-t border-surface-200 space-y-2">
              <Button
                variant="primary"
                className="w-full"
                onClick={() => onDownload(doc)}
              >
                <Download size={15} />
                Download File
              </Button>
              <Button
                variant="danger"
                className="w-full"
                loading={isDeleting}
                onClick={() => onDelete(doc)}
              >
                <Trash2 size={15} />
                Delete Document
              </Button>
            </div>
          </motion.div>
        </div>
      )}
    </AnimatePresence>
  )
}
