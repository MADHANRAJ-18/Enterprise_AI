/**
 * DocumentsPage.jsx  (Module 3 – Document Upload & Management)
 * ─────────────────────────────────────────────────────────────
 * Orchestrates the full document management experience:
 *   • Upload zone with drag-and-drop (FileUpload)
 *   • Per-file progress tracking (UploadProgress)
 *   • Searchable / sortable / filterable table (DocumentsTable)
 *   • Detail side panel (DocumentDetailModal)
 *   • Toast notifications
 *
 * Data layer: documentService.js → Supabase Storage + DB (Option A)
 * Auth:       useAuth() → user.id for all operations
 * ─────────────────────────────────────────────────────────────
 */

import { useState, useEffect, useCallback } from 'react'
import { motion } from 'framer-motion'
import {
  FileUp, Database, CheckCircle2, Clock, XCircle,
  TrendingUp, RefreshCw, LayoutGrid
} from 'lucide-react'
import { useAuth } from '../../context/AuthContext'
import { useToast } from '../../components/ui/Toast'
import { Card, CardBody } from '../../components/ui/Card'
import { Button } from '../../components/ui/Button'
import { FileUpload } from '../../components/documents/FileUpload'
import { UploadProgress } from '../../components/documents/UploadProgress'
import { DocumentsTable } from '../../components/documents/DocumentsTable'
import { DocumentDetailModal } from '../../components/documents/DocumentDetailModal'
import {
  listDocuments,
  uploadDocument,
  deleteDocument,
  downloadDocument,
  triggerProcessingAll,
  updateDocumentMetadata,
  overwriteDocument,
} from '../../services/documentService'

// ── Stats card config ────────────────────────────────────────

function buildStats(docs) {
  return [
    {
      label: 'Total Documents',
      value: docs.length,
      icon: Database,
      color: 'text-primary-600',
      bg: 'bg-primary-50 border-primary-100',
      iconBg: 'bg-primary-100',
    },
    {
      label: 'Indexed',
      value: docs.filter((d) => d.status === 'Indexed').length,
      icon: CheckCircle2,
      color: 'text-emerald-600',
      bg: 'bg-emerald-50 border-emerald-100',
      iconBg: 'bg-emerald-100',
    },
    {
      label: 'Processing',
      value: docs.filter((d) => d.status === 'Processing' || d.status === 'Uploaded').length,
      icon: Clock,
      color: 'text-amber-600',
      bg: 'bg-amber-50 border-amber-100',
      iconBg: 'bg-amber-100',
    },
    {
      label: 'Failed',
      value: docs.filter((d) => d.status === 'Failed').length,
      icon: XCircle,
      color: 'text-red-600',
      bg: 'bg-red-50 border-red-100',
      iconBg: 'bg-red-100',
    },
  ]
}

// ── Page ─────────────────────────────────────────────────────

export function DocumentsPage() {
  const { user } = useAuth()
  const { showToast, ToastComponent } = useToast()

  // ── State ──────────────────────────────────────────────────
  const [documents, setDocuments] = useState([])
  const [loadingDocs, setLoadingDocs] = useState(true)
  const [uploadQueue, setUploadQueue] = useState([]) // progress items
  const [isUploading, setIsUploading] = useState(false)
  const [isBatchProcessing, setIsBatchProcessing] = useState(false)
  const [selectedDoc, setSelectedDoc] = useState(null) // for detail modal
  const [isDeletingDetail, setIsDeletingDetail] = useState(false)
  const [isUpdatingDetail, setIsUpdatingDetail] = useState(false)
  const [isOverwritingDetail, setIsOverwritingDetail] = useState(false)

  // ── Fetch documents ────────────────────────────────────────
  const fetchDocuments = useCallback(async (showLoading = true) => {
    if (!user?.id) return
    if (showLoading) setLoadingDocs(true)
    const { data, error } = await listDocuments(user.id)
    if (error) {
      if (showLoading) showToast('Failed to load documents. Please refresh.', 'error')
    } else {
      setDocuments(data || [])
    }
    if (showLoading) setLoadingDocs(false)
  }, [user?.id])

  useEffect(() => {
    fetchDocuments(true)
  }, [fetchDocuments])

  // Auto-poll every 3s if any document is in Uploaded or Processing state
  useEffect(() => {
    const hasPending = documents.some(
      (d) => d.status === 'Uploaded' || d.status === 'Processing'
    )
    if (!hasPending) return

    const interval = setInterval(() => {
      fetchDocuments(false)
    }, 3000)

    return () => clearInterval(interval)
  }, [documents, fetchDocuments])

  // Auto-clear completed upload items after 4 s
  useEffect(() => {
    if (uploadQueue.length === 0) return
    const allDone = uploadQueue.every((q) => q.status === 'success' || q.status === 'error')
    if (!allDone) return
    const timer = setTimeout(() => setUploadQueue([]), 4000)
    return () => clearTimeout(timer)
  }, [uploadQueue])

  // ── Upload handler ─────────────────────────────────────────
  const handleUpload = async (files, category, scope = 'workspace') => {
    if (!user?.id || isUploading) return
    setIsUploading(true)

    // Initialise queue items
    const queueItems = files.map((file, i) => ({
      id: `upload-${Date.now()}-${i}`,
      file,
      status: 'uploading',
      progress: 0,
      error: null,
    }))
    setUploadQueue(queueItems)

    // Upload files sequentially
    const results = []
    for (let i = 0; i < files.length; i++) {
      const file = files[i]
      const queueId = queueItems[i].id

      const updateItem = (patch) => {
        setUploadQueue((prev) =>
          prev.map((q) => (q.id === queueId ? { ...q, ...patch } : q))
        )
      }

      const onProgress = (pct) => updateItem({ progress: pct })

      const { data, error } = await uploadDocument(file, category, user.id, onProgress, scope)

      if (error) {
        updateItem({ status: 'error', error, progress: 100 })
        showToast(error, 'error', 6000)
      } else {
        updateItem({ status: 'success', progress: 100 })
        results.push(data)
      }
    }

    // Refresh table with newly uploaded docs
    if (results.length > 0) {
      setDocuments((prev) => [...results, ...prev])
      const count = results.length
      showToast(
        `${count} document${count > 1 ? 's' : ''} uploaded to ${scope} scope successfully!`,
        'success'
      )
    }

    setIsUploading(false)
  }

  // ── Delete handler ─────────────────────────────────────────
  const handleDelete = async (doc) => {
    const { success, error } = await deleteDocument(doc)
    if (!success) {
      showToast(`Failed to delete: ${error}`, 'error')
      return
    }
    setDocuments((prev) => prev.filter((d) => d.id !== doc.id))
    showToast(`"${doc.file_name}" deleted successfully.`, 'success')
    if (selectedDoc?.id === doc.id) setSelectedDoc(null)
  }

  // Delete from detail panel
  const handleDeleteFromDetail = async (doc) => {
    setIsDeletingDetail(true)
    await handleDelete(doc)
    setIsDeletingDetail(false)
  }

  // ── Update handler ─────────────────────────────────────────
  const handleUpdate = async (doc, updates) => {
    setIsUpdatingDetail(true)
    const { data, error } = await updateDocumentMetadata(doc.id, user.id, updates)
    setIsUpdatingDetail(false)
    
    if (error) {
      showToast(`Failed to update: ${error}`, 'error')
      return
    }
    
    // Update local state
    setDocuments((prev) => prev.map((d) => (d.id === doc.id ? { ...d, ...updates } : d)))
    setSelectedDoc((prev) => ({ ...prev, ...updates }))
    showToast(`Document updated successfully.`, 'success')
  }

  // ── Overwrite handler ──────────────────────────────────────
  const handleOverwrite = async (doc, file) => {
    if (!user?.id) return
    setIsOverwritingDetail(true)
    showToast(`Replacing content for "${doc.file_name}"...`, 'info')
    const { data, error } = await overwriteDocument(doc.id, user.id, file)
    setIsOverwritingDetail(false)

    if (error) {
      showToast(error, 'error')
      return
    }

    setDocuments((prev) => prev.map((d) => (d.id === doc.id ? data : d)))
    setSelectedDoc(data)
    showToast(`File replaced successfully! Re-indexing AI knowledge...`, 'success')
  }

  // ── Download handler ───────────────────────────────────────
  const handleDownload = async (doc) => {
    const { success, error } = await downloadDocument(doc)
    if (!success) {
      showToast(`Download failed: ${error}`, 'error')
    }
  }

  // ── Stats ──────────────────────────────────────────────────
  const stats = buildStats(documents)

  return (
    <>
      <ToastComponent />
      <DocumentDetailModal
        doc={selectedDoc}
        onClose={() => setSelectedDoc(null)}
        onDownload={handleDownload}
        onDelete={handleDeleteFromDetail}
        isDeleting={isDeletingDetail}
        onUpdate={handleUpdate}
        isUpdating={isUpdatingDetail}
        onOverwrite={handleOverwrite}
        isOverwriting={isOverwritingDetail}
      />

      <motion.div
        initial={{ opacity: 0, y: 14 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.35 }}
        className="p-6 max-w-7xl mx-auto space-y-6"
      >
        {/* ── Page header ─────────────────────────────────── */}
        <div className="flex items-start justify-between gap-4">
          <div>
            <div className="flex items-center gap-2.5 mb-1">
              <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-primary-600 to-primary-800 flex items-center justify-center shadow-sm">
                <FileUp size={17} className="text-white" />
              </div>
              <div>
                <h1 className="text-xl font-bold text-surface-900">Document Library</h1>
                <p className="text-xs text-surface-400">Module 3 · Upload & Manage Knowledge Base</p>
              </div>
            </div>
          </div>
          <div className="flex items-center gap-2 flex-shrink-0">
            <Button
              variant="secondary"
              size="sm"
              onClick={async () => {
                if (!user?.id || isBatchProcessing) return
                setIsBatchProcessing(true)
                showToast('Starting AI processing for pending documents...', 'info')
                const res = await triggerProcessingAll(user.id)
                if (res.success) {
                  showToast(`Successfully processed ${res.indexed || 0} document(s)!`, 'success')
                } else {
                  showToast(res.error || 'Failed to process documents.', 'error')
                }
                setIsBatchProcessing(false)
                fetchDocuments(false)
              }}
              disabled={isBatchProcessing}
            >
              <RefreshCw size={14} className={isBatchProcessing ? 'animate-spin' : ''} />
              Process Pending
            </Button>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => fetchDocuments(true)}
              disabled={loadingDocs}
            >
              <RefreshCw size={14} className={loadingDocs ? 'animate-spin' : ''} />
              Refresh
            </Button>
          </div>
        </div>

        {/* ── Stats row ────────────────────────────────────── */}
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
          {stats.map(({ label, value, icon: Icon, color, bg, iconBg }, i) => (
            <motion.div
              key={label}
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: i * 0.06 }}
              className={`rounded-2xl border px-4 py-4 flex items-center gap-3 ${bg}`}
            >
              <div className={`w-10 h-10 rounded-xl flex items-center justify-center flex-shrink-0 ${iconBg}`}>
                <Icon size={18} className={color} />
              </div>
              <div>
                <p className={`text-2xl font-bold ${color}`}>{value}</p>
                <p className="text-xs font-medium text-surface-500 mt-0.5">{label}</p>
              </div>
            </motion.div>
          ))}
        </div>

        {/* ── Upload zone ──────────────────────────────────── */}
        <Card>
          <CardBody>
            <div className="flex items-center gap-2 mb-4">
              <TrendingUp size={15} className="text-primary-500" />
              <h2 className="text-sm font-bold text-surface-900">Upload Documents</h2>
              <span className="text-xs text-surface-400 ml-1">PDF · DOCX · TXT · up to 20 MB</span>
            </div>
            <FileUpload onUpload={handleUpload} isUploading={isUploading} />
            <UploadProgress items={uploadQueue} />
          </CardBody>
        </Card>

        {/* ── Documents table ──────────────────────────────── */}
        <Card>
          <div className="px-5 py-4 border-b border-surface-100 flex items-center gap-2">
            <LayoutGrid size={15} className="text-surface-500" />
            <h2 className="text-sm font-bold text-surface-900">All Documents</h2>
            <span className="ml-auto text-xs font-semibold text-surface-400">
              {documents.length} total
            </span>
          </div>
          <DocumentsTable
            documents={documents}
            loading={loadingDocs}
            onView={setSelectedDoc}
            onDownload={handleDownload}
            onDelete={handleDelete}
          />
        </Card>
      </motion.div>
    </>
  )
}
