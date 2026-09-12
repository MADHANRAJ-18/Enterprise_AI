/**
 * FileUpload.jsx
 * ─────────────────────────────────────────────────────────────
 * Drag-and-drop upload zone with browse button.
 * Validates file type (PDF, DOCX, TXT) and size (≤ 20 MB) client-side.
 * Accepts category and scope selectors for the upload.
 * ─────────────────────────────────────────────────────────────
 */

import { useState, useCallback, useRef } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { Upload, FileText, File, CloudUpload, AlertCircle, FolderOpen, Shield, Lock, Building2 } from 'lucide-react'
import { validateFile, CATEGORIES } from '../../services/documentService'
import { useAuth } from '../../context/AuthContext'
import { Button } from '../ui/Button'

const FILE_TYPE_ICONS = {
  pdf: { color: 'text-red-500', bg: 'bg-red-50 border-red-100' },
  docx: { color: 'text-blue-600', bg: 'bg-blue-50 border-blue-100' },
  txt: { color: 'text-emerald-600', bg: 'bg-emerald-50 border-emerald-100' },
}

function getFileExt(name) {
  return name.split('.').pop().toLowerCase()
}

export function FileUpload({ onUpload, isUploading }) {
  const { isKnowledgeAdmin } = useAuth()
  const isAdmin = isKnowledgeAdmin()

  const [isDragging, setIsDragging] = useState(false)
  const [category, setCategory] = useState('General')
  const [scope, setScope] = useState('workspace') // 'workspace' | 'company'
  const [stagedFiles, setStagedFiles] = useState([]) // files ready to upload
  const [validationErrors, setValidationErrors] = useState([])
  const inputRef = useRef(null)

  // ── Drag handlers ──────────────────────────────────────────
  const handleDragOver = useCallback((e) => {
    e.preventDefault()
    e.stopPropagation()
    setIsDragging(true)
  }, [])

  const handleDragLeave = useCallback((e) => {
    e.preventDefault()
    if (!e.currentTarget.contains(e.relatedTarget)) {
      setIsDragging(false)
    }
  }, [])

  const handleDrop = useCallback((e) => {
    e.preventDefault()
    e.stopPropagation()
    setIsDragging(false)
    const files = Array.from(e.dataTransfer.files)
    processFiles(files)
  }, [])

  // ── File processing ────────────────────────────────────────
  const processFiles = (files) => {
    const errors = []
    const valid = []

    for (const file of files) {
      const result = validateFile(file)
      if (result.valid) {
        valid.push(file)
      } else {
        errors.push(result.error)
      }
    }

    setValidationErrors(errors)
    setStagedFiles(valid)
  }

  const handleBrowse = (e) => {
    const files = Array.from(e.target.files)
    processFiles(files)
    e.target.value = ''
  }

  const handleUpload = () => {
    if (stagedFiles.length === 0 || isUploading) return
    onUpload(stagedFiles, category, scope)
    setStagedFiles([])
    setValidationErrors([])
  }

  const removeStagedFile = (index) => {
    setStagedFiles((prev) => prev.filter((_, i) => i !== index))
  }

  return (
    <div className="space-y-4">
      {/* Drop Zone */}
      <div
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
        onClick={() => !isUploading && inputRef.current?.click()}
        className={`relative border-2 border-dashed rounded-2xl p-8 text-center transition-all duration-200 cursor-pointer
          ${isUploading ? 'pointer-events-none opacity-60' : ''}
          ${isDragging
            ? 'border-primary-400 bg-primary-50 scale-[1.01]'
            : 'border-surface-200 bg-surface-50/40 hover:border-primary-300 hover:bg-primary-50/30'
          }`}
      >
        <input
          ref={inputRef}
          type="file"
          multiple
          className="hidden"
          accept=".pdf,.docx,.txt"
          onChange={handleBrowse}
        />

        {/* Icon */}
        <motion.div
          animate={{ scale: isDragging ? 1.15 : 1, rotate: isDragging ? 5 : 0 }}
          transition={{ type: 'spring', stiffness: 400, damping: 20 }}
          className={`w-16 h-16 rounded-2xl flex items-center justify-center mx-auto mb-4 border transition-colors
            ${isDragging
              ? 'bg-primary-100 border-primary-200'
              : 'bg-surface-100 border-surface-200'
            }`}
        >
          <CloudUpload
            size={28}
            className={isDragging ? 'text-primary-600' : 'text-surface-500'}
          />
        </motion.div>

        <h3 className="text-base font-semibold text-surface-900">
          {isDragging ? 'Drop your files here' : 'Drag & drop documents'}
        </h3>
        <p className="text-sm text-surface-500 mt-1">
          or{' '}
          <span className="text-primary-600 font-semibold hover:text-primary-700">
            browse files
          </span>{' '}
          from your computer
        </p>
        <div className="flex items-center justify-center gap-3 mt-4">
          {['PDF', 'DOCX', 'TXT'].map((type) => (
            <span
              key={type}
              className="inline-flex items-center gap-1 px-2.5 py-1 bg-surface-100 border border-surface-200 rounded-lg text-xs font-medium text-surface-600"
            >
              <FileText size={11} />
              {type}
            </span>
          ))}
          <span className="text-xs text-surface-400">· max 20 MB each</span>
        </div>
      </div>

      {/* Validation errors */}
      <AnimatePresence>
        {validationErrors.length > 0 && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: 'auto' }}
            exit={{ opacity: 0, height: 0 }}
            className="space-y-1.5 overflow-hidden"
          >
            {validationErrors.map((err, i) => (
              <div
                key={i}
                className="flex items-start gap-2 px-3 py-2.5 bg-red-50 border border-red-100 rounded-xl text-sm text-red-700"
              >
                <AlertCircle size={15} className="mt-0.5 flex-shrink-0" />
                <span>{err}</span>
              </div>
            ))}
          </motion.div>
        )}
      </AnimatePresence>

      {/* Staged files + scope + category selector */}
      <AnimatePresence>
        {stagedFiles.length > 0 && (
          <motion.div
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -8 }}
            className="bg-surface-50 border border-surface-200 rounded-2xl overflow-hidden"
          >
            {/* Staged file list */}
            <div className="px-4 py-3 border-b border-surface-100">
              <p className="text-xs font-semibold text-surface-400 uppercase tracking-wide mb-2">
                Ready to upload · {stagedFiles.length} file{stagedFiles.length > 1 ? 's' : ''}
              </p>
              <div className="space-y-2">
                {stagedFiles.map((file, i) => {
                  const ext = getFileExt(file.name)
                  const iconStyle = FILE_TYPE_ICONS[ext] || { color: 'text-surface-500', bg: 'bg-surface-100 border-surface-200' }
                  return (
                    <div key={i} className="flex items-center gap-3">
                      <div className={`w-8 h-8 rounded-lg border flex items-center justify-center flex-shrink-0 ${iconStyle.bg}`}>
                        <File size={14} className={iconStyle.color} />
                      </div>
                      <div className="min-w-0 flex-1">
                        <p className="text-sm font-medium text-surface-900 truncate">{file.name}</p>
                        <p className="text-xs text-surface-400">
                          {(file.size / 1024 / 1024).toFixed(2)} MB · {ext.toUpperCase()}
                        </p>
                      </div>
                      <button
                        onClick={(e) => { e.stopPropagation(); removeStagedFile(i) }}
                        className="text-surface-400 hover:text-red-500 transition-colors p-1 rounded"
                      >
                        ×
                      </button>
                    </div>
                  )
                })}
              </div>
            </div>

            {/* Scope selector + Category selector + upload button */}
            <div className="px-4 py-3 flex items-center gap-3 flex-wrap">

              {/* Scope selector */}
              <div className="flex items-center gap-2 flex-1 min-w-[200px]">
                <Shield size={15} className="text-primary-500 flex-shrink-0" />
                <label className="text-sm font-medium text-surface-600 whitespace-nowrap">Scope</label>
                <select
                  value={scope}
                  onChange={(e) => setScope(e.target.value)}
                  className="flex-1 min-w-0 px-3 py-1.5 text-sm bg-surface-100 border border-surface-200 rounded-lg outline-none focus:border-primary-400 focus:ring-2 focus:ring-primary-500/20 transition-all text-surface-900"
                >
                  <option value="workspace">🔒 My Workspace (Private)</option>
                  <option value="company" disabled={!isAdmin}>
                    🏢 Company Knowledge (Shared) {!isAdmin ? '🔒 Admin Only' : ''}
                  </option>
                </select>
              </div>

              {/* Category selector */}
              <div className="flex items-center gap-2 flex-1 min-w-[180px]">
                <FolderOpen size={15} className="text-surface-400 flex-shrink-0" />
                <label className="text-sm font-medium text-surface-600 whitespace-nowrap">Category</label>
                <select
                  value={category}
                  onChange={(e) => setCategory(e.target.value)}
                  className="flex-1 min-w-0 px-3 py-1.5 text-sm bg-surface-100 border border-surface-200 rounded-lg outline-none focus:border-primary-400 focus:ring-2 focus:ring-primary-500/20 transition-all text-surface-900"
                >
                  {CATEGORIES.map((cat) => (
                    <option key={cat} value={cat}>{cat}</option>
                  ))}
                </select>
              </div>

              <Button
                onClick={handleUpload}
                loading={isUploading}
                disabled={isUploading}
                size="sm"
                className="flex-shrink-0"
              >
                <Upload size={14} />
                Upload {stagedFiles.length > 1 ? `${stagedFiles.length} Files` : 'File'}
              </Button>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}
