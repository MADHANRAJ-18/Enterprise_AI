/**
 * DocumentsTable.jsx
 * ─────────────────────────────────────────────────────────────
 * Searchable, sortable, filterable document management table.
 *
 * Columns: File Name · Scope · Category · File Type · File Size · Upload Date · Status · Actions
 * Actions: View Details · Download · Delete (with confirmation)
 * ─────────────────────────────────────────────────────────────
 */

import { useState, useMemo } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import {
  Search, ArrowUpDown, ArrowUp, ArrowDown,
  FileText, File, Eye, Download, Trash2,
  FileSearch, ChevronLeft, ChevronRight, AlertTriangle,
  Building2, Lock
} from 'lucide-react'
import { Badge } from '../ui/Badge'
import { Button } from '../ui/Button'
import { formatFileSize } from '../../services/documentService'
import { CategoryFilter } from './CategoryFilter'

// ── Config ──────────────────────────────────────────────────

const STATUS_CONFIG = {
  Uploaded:   { variant: 'blue',   dot: 'bg-blue-400' },
  Processing: { variant: 'yellow', dot: 'bg-amber-400 animate-pulse' },
  Indexed:    { variant: 'green',  dot: 'bg-emerald-400' },
  Failed:     { variant: 'red',    dot: 'bg-red-400' },
}

const FILE_TYPE_STYLE = {
  PDF:  { color: 'text-red-500',     bg: 'bg-red-50 border-red-100' },
  DOCX: { color: 'text-blue-600',    bg: 'bg-blue-50 border-blue-100' },
  TXT:  { color: 'text-emerald-600', bg: 'bg-emerald-50 border-emerald-100' },
}

const STATUS_FILTERS = ['All', 'Uploaded', 'Processing', 'Indexed', 'Failed']
const SCOPE_FILTERS = [
  { id: 'All', label: 'All Scopes' },
  { id: 'company', label: '🏢 Company Knowledge', icon: Building2 },
  { id: 'workspace', label: '🔒 My Workspace', icon: Lock },
]

const PAGE_SIZE = 10

// ── Helpers ─────────────────────────────────────────────────

function formatDate(iso) {
  if (!iso) return '—'
  return new Date(iso).toLocaleDateString('en-US', {
    year: 'numeric', month: 'short', day: 'numeric',
  })
}

function SortIcon({ column, sortKey, sortDir }) {
  if (sortKey !== column) return <ArrowUpDown size={12} className="text-surface-300" />
  return sortDir === 'asc'
    ? <ArrowUp size={12} className="text-primary-500" />
    : <ArrowDown size={12} className="text-primary-500" />
}

// ── Loading skeleton ─────────────────────────────────────────

function SkeletonRows() {
  return Array.from({ length: 5 }).map((_, i) => (
    <tr key={i} className="border-b border-surface-50">
      {Array.from({ length: 8 }).map((_, j) => (
        <td key={j} className="px-4 py-3.5">
          <div className="h-4 bg-surface-200 rounded animate-pulse" style={{ width: j === 0 ? '80%' : '60%' }} />
        </td>
      ))}
    </tr>
  ))
}

// ── Delete confirmation mini-modal ───────────────────────────

function DeleteConfirmDialog({ doc, onConfirm, onCancel, isDeleting }) {
  if (!doc) return null
  return (
    <AnimatePresence>
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        className="fixed inset-0 z-50 flex items-center justify-center p-4"
      >
        <div className="absolute inset-0 bg-surface-900/40 backdrop-blur-sm" onClick={onCancel} />
        <motion.div
          initial={{ scale: 0.92, opacity: 0 }}
          animate={{ scale: 1, opacity: 1 }}
          exit={{ scale: 0.92, opacity: 0 }}
          transition={{ type: 'spring', damping: 25, stiffness: 400 }}
          className="relative bg-surface-100 rounded-2xl shadow-2xl w-full max-w-sm p-6"
        >
          <div className="w-12 h-12 rounded-2xl bg-red-50 border border-red-100 flex items-center justify-center mx-auto mb-4">
            <AlertTriangle size={22} className="text-red-500" />
          </div>
          <h3 className="text-base font-bold text-surface-900 text-center">Delete Document</h3>
          <p className="text-sm text-surface-500 text-center mt-2">
            Are you sure you want to delete{' '}
            <span className="font-semibold text-surface-700">"{doc.file_name}"</span>?
            This action cannot be undone.
          </p>
          <div className="flex gap-3 mt-5">
            <Button variant="secondary" className="flex-1" onClick={onCancel} disabled={isDeleting}>
              Cancel
            </Button>
            <Button variant="danger" className="flex-1" loading={isDeleting} onClick={onConfirm}>
              <Trash2 size={14} />
              Delete
            </Button>
          </div>
        </motion.div>
      </motion.div>
    </AnimatePresence>
  )
}

// ── Main Component ───────────────────────────────────────────

export function DocumentsTable({ documents = [], loading, onView, onDownload, onDelete }) {
  const [search, setSearch] = useState('')
  const [scopeFilter, setScopeFilter] = useState('All')
  const [statusFilter, setStatusFilter] = useState('All')
  const [categoryFilter, setCategoryFilter] = useState('All')
  const [sortKey, setSortKey] = useState('uploaded_at')
  const [sortDir, setSortDir] = useState('desc')
  const [page, setPage] = useState(1)
  const [deleteTarget, setDeleteTarget] = useState(null)
  const [isDeleting, setIsDeleting] = useState(false)

  // ── Sort handler ─────────────────────────────────────────
  const handleSort = (key) => {
    if (sortKey === key) {
      setSortDir((d) => (d === 'asc' ? 'desc' : 'asc'))
    } else {
      setSortKey(key)
      setSortDir('asc')
    }
    setPage(1)
  }

  // ── Filtered + sorted data ───────────────────────────────
  const filtered = useMemo(() => {
    return documents
      .filter((d) => {
        const matchSearch = d.file_name.toLowerCase().includes(search.toLowerCase())
        const matchScope = scopeFilter === 'All' || (d.scope || 'company') === scopeFilter
        const matchStatus = statusFilter === 'All' || d.status === statusFilter
        const matchCat = categoryFilter === 'All' || d.category === categoryFilter
        return matchSearch && matchScope && matchStatus && matchCat
      })
      .sort((a, b) => {
        let aVal = a[sortKey]
        let bVal = b[sortKey]
        if (sortKey === 'file_size') {
          aVal = Number(aVal)
          bVal = Number(bVal)
        } else if (sortKey === 'uploaded_at') {
          aVal = new Date(aVal).getTime()
          bVal = new Date(bVal).getTime()
        } else {
          aVal = String(aVal).toLowerCase()
          bVal = String(bVal).toLowerCase()
        }
        if (aVal < bVal) return sortDir === 'asc' ? -1 : 1
        if (aVal > bVal) return sortDir === 'asc' ? 1 : -1
        return 0
      })
  }, [documents, search, scopeFilter, statusFilter, categoryFilter, sortKey, sortDir])

  // ── Pagination ────────────────────────────────────────────
  const totalPages = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE))
  const paginated = filtered.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE)

  // ── Delete handler ────────────────────────────────────────
  const handleDeleteConfirm = async () => {
    if (!deleteTarget) return
    setIsDeleting(true)
    await onDelete(deleteTarget)
    setIsDeleting(false)
    setDeleteTarget(null)
  }

  // ── Sortable column header ────────────────────────────────
  const Th = ({ label, sortable, col, className = '' }) => (
    <th
      onClick={sortable ? () => handleSort(col) : undefined}
      className={`px-4 py-3 text-left text-xs font-semibold text-surface-400 uppercase tracking-wide
        ${sortable ? 'cursor-pointer select-none hover:text-surface-700 transition-colors' : ''}
        ${className}`}
    >
      <div className="flex items-center gap-1.5">
        {label}
        {sortable && <SortIcon column={col} sortKey={sortKey} sortDir={sortDir} />}
      </div>
    </th>
  )

  return (
    <div>
      {/* Toolbar */}
      <div className="px-5 py-4 border-b border-surface-100 space-y-3">

        {/* Row 1: Scope filter tabs */}
        <div className="flex items-center gap-2 pb-1 border-b border-surface-100">
          <span className="text-xs font-bold text-surface-400 uppercase tracking-wider mr-2">Scope:</span>
          {SCOPE_FILTERS.map((s) => (
            <button
              key={s.id}
              onClick={() => { setScopeFilter(s.id); setPage(1) }}
              className={`px-3 py-1.5 rounded-xl text-xs font-semibold transition-all flex items-center gap-1.5
                ${scopeFilter === s.id
                  ? 'bg-primary-600 text-white shadow-sm shadow-primary-500/30'
                  : 'bg-surface-100 text-surface-600 hover:bg-surface-200'
                }`}
            >
              {s.label}
            </button>
          ))}
        </div>

        {/* Row 2: Search + status filter */}
        <div className="flex items-center gap-3 flex-wrap">
          {/* Search */}
          <div className="relative flex-1 min-w-48">
            <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-surface-400 pointer-events-none" />
            <input
              type="search"
              value={search}
              onChange={(e) => { setSearch(e.target.value); setPage(1) }}
              placeholder="Search by file name…"
              className="w-full pl-9 pr-3 py-2 text-sm bg-surface-50 border border-surface-200 rounded-xl outline-none
                focus:border-primary-400 focus:ring-2 focus:ring-primary-500/20 transition-all placeholder:text-surface-400"
            />
          </div>
          {/* Status filter tabs */}
          <div className="flex bg-surface-100 border border-surface-200 rounded-xl p-0.5 gap-0.5">
            {STATUS_FILTERS.map((f) => (
              <button
                key={f}
                onClick={() => { setStatusFilter(f); setPage(1) }}
                className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-all capitalize
                  ${statusFilter === f
                    ? 'bg-surface-50 text-surface-900 shadow-sm border border-surface-200'
                    : 'text-surface-500 hover:text-surface-700'
                  }`}
              >
                {f}
              </button>
            ))}
          </div>
        </div>

        {/* Row 3: Category pills */}
        <CategoryFilter
          activeCategory={categoryFilter}
          onChange={(cat) => { setCategoryFilter(cat); setPage(1) }}
          documents={documents}
        />
      </div>

      {/* Table */}
      <div className="overflow-x-auto">
        <table className="w-full">
          <thead>
            <tr className="border-b border-surface-100">
              <Th label="File Name" sortable col="file_name" className="pl-5" />
              <Th label="Scope" />
              <Th label="Category" />
              <Th label="Type" />
              <Th label="Size" sortable col="file_size" className="hidden sm:table-cell" />
              <Th label="Upload Date" sortable col="uploaded_at" className="hidden md:table-cell" />
              <Th label="Status" />
              <th className="px-4 py-3 w-28" />
            </tr>
          </thead>
          <tbody className="divide-y divide-surface-50">
            {loading ? (
              <SkeletonRows />
            ) : paginated.length === 0 ? (
              <tr>
                <td colSpan={8} className="py-16 text-center">
                  <div className="flex flex-col items-center gap-3">
                    <div className="w-14 h-14 rounded-2xl bg-surface-100 border border-surface-200 flex items-center justify-center">
                      <FileSearch size={24} className="text-surface-400" />
                    </div>
                    <p className="text-sm font-semibold text-surface-600">No documents found</p>
                    <p className="text-xs text-surface-400 max-w-xs">
                      {search || scopeFilter !== 'All' || statusFilter !== 'All' || categoryFilter !== 'All'
                        ? 'Try adjusting your search or filters.'
                        : 'Upload your first document using the zone above.'}
                    </p>
                  </div>
                </td>
              </tr>
            ) : (
              <AnimatePresence initial={false}>
                {paginated.map((doc) => {
                  const fileStyle = FILE_TYPE_STYLE[doc.file_type] || { color: 'text-surface-500', bg: 'bg-surface-100 border-surface-200' }
                  const statusCfg = STATUS_CONFIG[doc.status] || { variant: 'gray', dot: 'bg-surface-300' }
                  const isCompanyScope = (doc.scope || 'company') === 'company'

                  return (
                    <motion.tr
                      key={doc.id}
                      initial={{ opacity: 0, y: 4 }}
                      animate={{ opacity: 1, y: 0 }}
                      exit={{ opacity: 0 }}
                      transition={{ duration: 0.18 }}
                      className="hover:bg-surface-50/80 transition-colors group"
                    >
                      {/* File Name */}
                      <td className="px-5 py-3.5">
                        <div className="flex items-center gap-3">
                          <div className={`w-9 h-9 rounded-xl border flex items-center justify-center flex-shrink-0 ${fileStyle.bg}`}>
                            <FileText size={15} className={fileStyle.color} />
                          </div>
                          <div className="min-w-0">
                            <p className="text-sm font-semibold text-surface-900 truncate max-w-[180px] lg:max-w-[260px]">
                              {doc.file_name}
                            </p>
                            <p className="text-xs text-surface-400">ID: {doc.id.slice(0, 8)}…</p>
                          </div>
                        </div>
                      </td>

                      {/* Scope Badge */}
                      <td className="px-4 py-3.5">
                        {isCompanyScope ? (
                          <span className="inline-flex items-center gap-1 text-xs font-bold text-indigo-700 bg-indigo-50 border border-indigo-100 px-2 py-1 rounded-lg">
                            <Building2 size={11} /> Company
                          </span>
                        ) : (
                          <span className="inline-flex items-center gap-1 text-xs font-bold text-slate-700 bg-slate-100 border border-slate-200 px-2 py-1 rounded-lg">
                            <Lock size={11} /> Workspace
                          </span>
                        )}
                      </td>

                      {/* Category */}
                      <td className="px-4 py-3.5">
                        <span className="text-xs font-medium text-surface-600 bg-surface-100 border border-surface-200 px-2 py-1 rounded-lg">
                          {doc.category}
                        </span>
                      </td>

                      {/* Type */}
                      <td className="px-4 py-3.5">
                        <span className={`text-xs font-bold px-2 py-1 rounded-lg border ${fileStyle.bg} ${fileStyle.color}`}>
                          {doc.file_type}
                        </span>
                      </td>

                      {/* Size */}
                      <td className="px-4 py-3.5 hidden sm:table-cell">
                        <span className="text-sm text-surface-500">{formatFileSize(doc.file_size)}</span>
                      </td>

                      {/* Date */}
                      <td className="px-4 py-3.5 hidden md:table-cell">
                        <span className="text-sm text-surface-400">{formatDate(doc.uploaded_at)}</span>
                      </td>

                      {/* Status */}
                      <td className="px-4 py-3.5">
                        <div className="flex items-center gap-1.5">
                          <span className={`w-1.5 h-1.5 rounded-full flex-shrink-0 ${statusCfg.dot}`} />
                          <Badge variant={statusCfg.variant}>{doc.status}</Badge>
                        </div>
                      </td>

                      {/* Actions */}
                      <td className="px-4 py-3.5">
                        <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                          {/* View details */}
                          <button
                            onClick={() => onView(doc)}
                            title="View Details"
                            className="p-1.5 rounded-lg text-surface-400 hover:text-primary-600 hover:bg-primary-50 transition-colors"
                          >
                            <Eye size={14} />
                          </button>
                          {/* Download */}
                          <button
                            onClick={() => onDownload(doc)}
                            title="Download"
                            className="p-1.5 rounded-lg text-surface-400 hover:text-emerald-600 hover:bg-emerald-50 transition-colors"
                          >
                            <Download size={14} />
                          </button>
                          {/* Delete */}
                          <button
                            onClick={() => setDeleteTarget(doc)}
                            title="Delete"
                            className="p-1.5 rounded-lg text-surface-400 hover:text-red-600 hover:bg-red-50 transition-colors"
                          >
                            <Trash2 size={14} />
                          </button>
                        </div>
                      </td>
                    </motion.tr>
                  )
                })}
              </AnimatePresence>
            )}
          </tbody>
        </table>
      </div>

      {/* Pagination */}
      {!loading && filtered.length > PAGE_SIZE && (
        <div className="px-5 py-3.5 border-t border-surface-100 flex items-center justify-between">
          <p className="text-xs text-surface-400">
            Showing{' '}
            <span className="font-semibold text-surface-700">
              {(page - 1) * PAGE_SIZE + 1}–{Math.min(page * PAGE_SIZE, filtered.length)}
            </span>{' '}
            of <span className="font-semibold text-surface-700">{filtered.length}</span> documents
          </p>
          <div className="flex items-center gap-1">
            <button
              onClick={() => setPage((p) => Math.max(1, p - 1))}
              disabled={page === 1}
              className="p-1.5 rounded-lg text-surface-500 hover:bg-surface-100 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
            >
              <ChevronLeft size={15} />
            </button>
            <span className="px-2 text-xs font-medium text-surface-600">
              {page} / {totalPages}
            </span>
            <button
              onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
              disabled={page === totalPages}
              className="p-1.5 rounded-lg text-surface-500 hover:bg-surface-100 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
            >
              <ChevronRight size={15} />
            </button>
          </div>
        </div>
      )}

      {/* Delete confirmation dialog */}
      {deleteTarget && (
        <DeleteConfirmDialog
          doc={deleteTarget}
          onConfirm={handleDeleteConfirm}
          onCancel={() => setDeleteTarget(null)}
          isDeleting={isDeleting}
        />
      )}
    </div>
  )
}
