/**
 * PDFCitationViewerModal.jsx
 * ─────────────────────────────────────────────────────────────
 * Interactive PDF Citation Viewer with visual text highlighting,
 * automatic page navigation, zoom controls, and smooth auto-scroll.
 * ─────────────────────────────────────────────────────────────
 */

import React, { useState, useEffect, useRef } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import {
  X,
  FileText,
  ChevronLeft,
  ChevronRight,
  ZoomIn,
  ZoomOut,
  Maximize2,
  Download,
  AlertCircle,
  CheckCircle2,
  Loader2,
  Sparkles,
  RefreshCw,
} from 'lucide-react'
import * as pdfjsLib from 'pdfjs-dist'
import pdfjsWorker from 'pdfjs-dist/build/pdf.worker.min.mjs?url'
import 'pdfjs-dist/web/pdf_viewer.css'
import { highlightCitationInTextLayer } from '../../utils/pdfHighlightHelper'
import { getDocumentFileUrl } from '../../services/documentService'

// Configure PDF.js worker directly bundled via Vite
try {
  pdfjsLib.GlobalWorkerOptions.workerSrc = pdfjsWorker
} catch (e) {
  console.warn('[PDFViewer] Worker setup fallback notice:', e)
}

/**
 * @param {object|null} citation   - Selected citation object { document_id, file_name, page_number, full_text, text_preview }
 * @param {string}      userId     - Authenticated user ID for permission verification
 * @param {Function}    onClose    - Close callback
 */
export function PDFCitationViewerModal({ citation, userId, onClose }) {
  const isOpen = !!citation

  // Viewer State
  const [pdfDoc, setPdfDoc] = useState(null)
  const [totalPages, setTotalPages] = useState(0)
  const [currentPage, setCurrentPage] = useState(1)
  const [scale, setScale] = useState(1.2)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [resolvedFileUrl, setResolvedFileUrl] = useState(null)
  const [highlightStats, setHighlightStats] = useState({
    status: null, // 'success' | 'partial' | 'not_found' | null
    totalSpans: 0,
    matchedSpans: 0,
    domCount: 0,
  })

  // DOM Refs
  const canvasRef = useRef(null)
  const textLayerRef = useRef(null)
  const renderTaskRef = useRef(null)
  const containerRef = useRef(null)

  // Determine target page and excerpt from citation
  const initialPage = citation?.page_number || citation?.page || 1
  // source_text = focused grounding sentence extracted by backend
  // full_text  = raw entire chunk (used only as last resort for display, NOT for highlighting)
  const citationExcerpt = citation?.source_text || citation?.text_preview || citation?.full_text || ''
  const isPdf = citation?.file_name ? citation.file_name.toLowerCase().endsWith('.pdf') : true

  // 1. Fetch secure document URL when modal opens
  useEffect(() => {
    if (!citation || !isOpen) {
      setPdfDoc(null)
      setError(null)
      setResolvedFileUrl(null)
      return
    }

    let isMounted = true
    setLoading(true)
    setError(null)
    setHighlightStats({ status: null, totalSpans: 0, matchedSpans: 0, domCount: 0 })

    // Set initial page from citation
    setCurrentPage(Number(initialPage) > 0 ? Number(initialPage) : 1)

    async function loadPdfUrl() {
      try {
        const { url, error: fetchErr } = await getDocumentFileUrl(citation.document_id, userId)
        if (!isMounted) return

        if (fetchErr || !url) {
          setError(fetchErr || 'Failed to obtain authorized document access.')
          setLoading(false)
          return
        }

        setResolvedFileUrl(url)

        // If non-PDF, show gentle fallback message
        if (!isPdf) {
          setLoading(false)
          return
        }

        // Load PDF Document via PDF.js
        const loadingTask = pdfjsLib.getDocument({
          url,
          withCredentials: false,
          cMapUrl: `https://unpkg.com/pdfjs-dist@${pdfjsLib.version || '6.3.289'}/cmaps/`,
          cMapPacked: true,
        })

        const loadedDoc = await loadingTask.promise
        if (!isMounted) return

        setPdfDoc(loadedDoc)
        setTotalPages(loadedDoc.numPages)
        setLoading(false)
      } catch (err) {
        if (!isMounted) return
        console.error('[PDFViewer] Error loading document:', err)
        setError(`Failed to load PDF document: ${err.message || err}`)
        setLoading(false)
      }
    }

    loadPdfUrl()

    return () => {
      isMounted = false
    }
  }, [citation, userId])

  // 2. Render Page Canvas & Text Layer when page or scale changes
  useEffect(() => {
    if (!pdfDoc || !isOpen || !isPdf || currentPage < 1 || currentPage > totalPages) {
      return
    }

    let isCancelled = false

    async function renderPage() {
      try {
        if (renderTaskRef.current) {
          renderTaskRef.current.cancel()
        }

        const page = await pdfDoc.getPage(currentPage)
        if (isCancelled) return

        const canvas = canvasRef.current
        const textLayerDiv = textLayerRef.current
        if (!canvas || !textLayerDiv) return

        const viewport = page.getViewport({ scale })

        // High DPI canvas support
        const pixelRatio = window.devicePixelRatio || 1
        canvas.height = viewport.height * pixelRatio
        canvas.width = viewport.width * pixelRatio
        canvas.style.height = `${viewport.height}px`
        canvas.style.width = `${viewport.width}px`

        const ctx = canvas.getContext('2d')
        ctx.setTransform(pixelRatio, 0, 0, pixelRatio, 0, 0)

        // Render PDF Canvas
        const renderContext = {
          canvasContext: ctx,
          viewport,
        }

        renderTaskRef.current = page.render(renderContext)
        await renderTaskRef.current.promise
        if (isCancelled) return

        // Render Selectable Text Layer
        textLayerDiv.innerHTML = ''
        textLayerDiv.style.height = `${viewport.height}px`
        textLayerDiv.style.width = `${viewport.width}px`
        textLayerDiv.style.setProperty('--scale-factor', scale)

        const textContent = await page.getTextContent()
        if (isCancelled) return

        // Render text items into textLayerDiv
        if (pdfjsLib.TextLayer) {
          const textLayer = new pdfjsLib.TextLayer({
            textContentSource: textContent,
            container: textLayerDiv,
            viewport,
          })
          await textLayer.render()
        } else {
          // Compatibility for direct span placement
          for (const item of textContent.items) {
            const span = document.createElement('span')
            span.textContent = item.str
            span.style.left = `${item.transform[4] * scale}px`
            span.style.top = `${viewport.height - item.transform[5] * scale}px`
            textLayerDiv.appendChild(span)
          }
        }

        // 3. Apply Multi-Evidence Text Highlighting if this is the cited page
        const isCitedPage = currentPage === Number(initialPage)
        if (isCitedPage && (citationExcerpt || citation?.evidence_spans?.length > 0)) {
          // Give DOM a tick to layout spans
          setTimeout(() => {
            if (isCancelled) return
            const result = highlightCitationInTextLayer(textLayerDiv, citation, citation?.aiAnswer)
            if (result.matchedCount > 0) {
              const isAll = result.matchedEvidenceSpans >= result.totalEvidenceSpans
              setHighlightStats({
                status: isAll ? 'success' : 'partial',
                totalSpans: result.totalEvidenceSpans,
                matchedSpans: result.matchedEvidenceSpans,
                domCount: result.matchedCount,
              })
              // Smooth scroll to first highlight
              result.firstMatchedElement?.scrollIntoView({
                behavior: 'smooth',
                block: 'center',
              })
            } else {
              setHighlightStats({
                status: 'not_found',
                totalSpans: result.totalEvidenceSpans || 1,
                matchedSpans: 0,
                domCount: 0,
              })
            }
          }, 60)
        } else {
          setHighlightStats({ status: null, totalSpans: 0, matchedSpans: 0, domCount: 0 })
        }
      } catch (err) {
        if (err?.name === 'RenderingCancelledException') return
        console.warn('[PDFViewer] Render page notice:', err)
      }
    }

    renderPage()

    return () => {
      isCancelled = true
    }
  }, [pdfDoc, currentPage, scale, initialPage, citationExcerpt, isPdf, totalPages])

  // Key listeners (Esc to close, Left/Right for pages)
  useEffect(() => {
    function handleKeyDown(e) {
      if (e.key === 'Escape') onClose?.()
      if (e.key === 'ArrowLeft') setCurrentPage((p) => Math.max(1, p - 1))
      if (e.key === 'ArrowRight') setCurrentPage((p) => Math.min(totalPages || 1, p + 1))
    }

    if (isOpen) {
      window.addEventListener('keydown', handleKeyDown)
      return () => window.removeEventListener('keydown', handleKeyDown)
    }
  }, [isOpen, totalPages, onClose])

  if (!isOpen) return null

  return (
    <AnimatePresence>
      <div className="fixed inset-0 z-50 flex items-center justify-center p-2 sm:p-4 md:p-6 bg-surface-950/80 backdrop-blur-md">
        {/* Backdrop click to close */}
        <div className="absolute inset-0" onClick={onClose} />

        {/* Modal Container */}
        <motion.div
          initial={{ opacity: 0, scale: 0.96, y: 10 }}
          animate={{ opacity: 1, scale: 1, y: 0 }}
          exit={{ opacity: 0, scale: 0.96, y: 10 }}
          transition={{ duration: 0.2 }}
          className="relative z-10 w-full max-w-5xl h-[92vh] bg-surface-900 border border-surface-700/80 rounded-2xl shadow-2xl flex flex-col overflow-hidden text-surface-100"
        >
          {/* Header Controls */}
          <div className="flex items-center justify-between px-4 py-3 border-b border-surface-800 bg-surface-900/95 flex-wrap gap-2">
            {/* Title & Document Badge */}
            <div className="flex items-center gap-2.5 min-w-0 max-w-[40%]">
              <div className="w-8 h-8 rounded-lg bg-primary-500/10 border border-primary-500/20 flex items-center justify-center flex-shrink-0">
                <FileText size={16} className="text-primary-400" />
              </div>
              <div className="min-w-0">
                <h3 className="text-sm font-semibold text-surface-100 truncate" title={citation?.file_name}>
                  {citation?.file_name || 'Document Viewer'}
                </h3>
                <p className="text-[11px] text-surface-400 flex items-center gap-1.5">
                  <span>Cited Source</span>
                  {citation?.source_index && (
                    <span className="bg-primary-500/20 text-primary-300 font-mono px-1 rounded text-[10px]">
                      [{citation.source_index}]
                    </span>
                  )}
                  {initialPage && <span>• Page {initialPage}</span>}
                </p>
              </div>
            </div>

            {/* Pagination Controls */}
            {isPdf && totalPages > 0 && (
              <div className="flex items-center gap-1 bg-surface-800/80 border border-surface-700 rounded-lg p-0.5">
                <button
                  onClick={() => setCurrentPage((p) => Math.max(1, p - 1))}
                  disabled={currentPage <= 1}
                  className="p-1 rounded text-surface-300 hover:text-surface-100 hover:bg-surface-700 disabled:opacity-30 disabled:hover:bg-transparent transition-colors"
                  title="Previous Page (Left Arrow)"
                >
                  <ChevronLeft size={16} />
                </button>
                <div className="flex items-center gap-1 px-1.5 text-xs font-medium text-surface-300">
                  <input
                    type="number"
                    min={1}
                    max={totalPages}
                    value={currentPage}
                    onChange={(e) => {
                      const val = parseInt(e.target.value, 10)
                      if (!isNaN(val) && val >= 1 && val <= totalPages) {
                        setCurrentPage(val)
                      }
                    }}
                    className="w-9 text-center bg-surface-900 border border-surface-700 rounded text-primary-400 font-bold focus:outline-none focus:border-primary-500 py-0.5"
                    title="Jump to page"
                  />
                  <span className="text-surface-500">/</span>
                  <span className="pr-1">{totalPages}</span>
                </div>
                <button
                  onClick={() => setCurrentPage((p) => Math.min(totalPages, p + 1))}
                  disabled={currentPage >= totalPages}
                  className="p-1 rounded text-surface-300 hover:text-surface-100 hover:bg-surface-700 disabled:opacity-30 disabled:hover:bg-transparent transition-colors"
                  title="Next Page (Right Arrow)"
                >
                  <ChevronRight size={16} />
                </button>
              </div>
            )}

            {/* Zoom Controls */}
            {isPdf && (
              <div className="flex items-center gap-1 bg-surface-800/80 border border-surface-700 rounded-lg p-0.5">
                <button
                  onClick={() => setScale((s) => Math.max(0.6, s - 0.2))}
                  className="p-1 rounded text-surface-300 hover:text-surface-100 hover:bg-surface-700 transition-colors"
                  title="Zoom Out"
                >
                  <ZoomOut size={15} />
                </button>
                <span className="text-[11px] font-mono font-medium text-surface-300 px-1.5 min-w-[42px] text-center">
                  {Math.round(scale * 100)}%
                </span>
                <button
                  onClick={() => setScale((s) => Math.min(2.5, s + 0.2))}
                  className="p-1 rounded text-surface-300 hover:text-surface-100 hover:bg-surface-700 transition-colors"
                  title="Zoom In"
                >
                  <ZoomIn size={15} />
                </button>
                <button
                  onClick={() => setScale(1.2)}
                  className="p-1 rounded text-surface-400 hover:text-surface-200 hover:bg-surface-700 transition-colors text-[10px] font-medium px-1.5"
                  title="Reset Zoom"
                >
                  Reset
                </button>
              </div>
            )}

            {/* Actions: Download & Close */}
            <div className="flex items-center gap-1.5">
              {resolvedFileUrl && (
                <a
                  href={resolvedFileUrl}
                  download={citation?.file_name || 'document.pdf'}
                  target="_blank"
                  rel="noreferrer"
                  className="p-1.5 rounded-lg text-surface-400 hover:text-surface-200 hover:bg-surface-800 transition-colors"
                  title="Download File"
                >
                  <Download size={16} />
                </a>
              )}
              <button
                onClick={onClose}
                className="p-1.5 rounded-lg text-surface-400 hover:text-surface-100 hover:bg-surface-800 transition-colors"
                title="Close Viewer (Esc)"
              >
                <X size={18} />
              </button>
            </div>
          </div>

          {/* Highlight Status Notification Banner */}
          {highlightStats.status === 'success' && (
            <div className="flex items-center justify-between px-4 py-1.5 bg-amber-500/10 border-b border-amber-500/20 text-amber-300 text-xs">
              <div className="flex items-center gap-1.5">
                <Sparkles size={13} className="text-amber-400 flex-shrink-0 animate-pulse" />
                <span>
                  {highlightStats.totalSpans > 1
                    ? `All ${highlightStats.matchedSpans} evidence passages located & highlighted on Page ${currentPage}`
                    : `Exact source text located & highlighted on Page ${currentPage}`}
                </span>
              </div>
              <span className="text-[11px] text-amber-400/80 font-mono hidden sm:inline">Auto-scrolled into view</span>
            </div>
          )}

          {highlightStats.status === 'partial' && (
            <div className="flex items-center justify-between px-4 py-1.5 bg-amber-500/10 border-b border-amber-500/20 text-amber-300 text-xs">
              <div className="flex items-center gap-1.5">
                <Sparkles size={13} className="text-amber-400 flex-shrink-0" />
                <span>
                  {highlightStats.matchedSpans} of {highlightStats.totalSpans} evidence passages highlighted on Page {currentPage}
                </span>
              </div>
              <span className="text-[11px] text-amber-400/80 font-mono hidden sm:inline">Auto-scrolled to first match</span>
            </div>
          )}

          {highlightStats.status === 'not_found' && (
            <div className="flex items-center gap-1.5 px-4 py-1.5 bg-surface-800/80 border-b border-surface-700 text-surface-400 text-xs">
              <AlertCircle size={13} className="flex-shrink-0 text-amber-500" />
              <span>Opened the cited page, but the source text could not be automatically highlighted.</span>
            </div>
          )}

          {/* Main Viewer Body */}
          <div
            ref={containerRef}
            className="flex-1 overflow-auto bg-surface-950 p-4 flex items-start justify-center relative select-text"
          >
            {/* Loading State */}
            {loading && (
              <div className="flex flex-col items-center justify-center my-auto py-20 text-surface-400">
                <Loader2 size={32} className="animate-spin text-primary-400 mb-3" />
                <p className="text-sm font-medium">Loading document & verifying authorization...</p>
                <p className="text-xs text-surface-500 mt-1">Navigating to Page {initialPage}...</p>
              </div>
            )}

            {/* Error State */}
            {!loading && error && (
              <div className="max-w-md my-auto p-6 bg-red-500/10 border border-red-500/20 rounded-2xl text-center">
                <AlertCircle size={32} className="text-red-400 mx-auto mb-3" />
                <h4 className="text-sm font-bold text-red-300 mb-1">Unable to Display Document</h4>
                <p className="text-xs text-red-400/90 leading-relaxed mb-4">{error}</p>
                {resolvedFileUrl && (
                  <a
                    href={resolvedFileUrl}
                    target="_blank"
                    rel="noreferrer"
                    className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-red-500/20 hover:bg-red-500/30 text-red-200 text-xs font-semibold rounded-lg transition-colors"
                  >
                    <Download size={13} />
                    Download File Instead
                  </a>
                )}
              </div>
            )}

            {/* Non-PDF Fallback */}
            {!loading && !error && !isPdf && (
              <div className="max-w-lg my-auto p-6 bg-surface-900 border border-surface-800 rounded-2xl text-center">
                <FileText size={36} className="text-primary-400 mx-auto mb-3" />
                <h4 className="text-base font-bold text-surface-100 mb-1">{citation?.file_name}</h4>
                <p className="text-xs text-surface-400 leading-relaxed mb-4">
                  Visual page & text highlighting is designed for PDF documents. For Word documents (.docx) or text
                  files, you can inspect the grounded excerpt below or download the file.
                </p>

                {citationExcerpt && (
                  <div className="text-left bg-surface-950 border border-surface-800 rounded-xl p-3.5 mb-4 max-h-48 overflow-y-auto">
                    <p className="text-[10px] font-semibold text-primary-400 uppercase tracking-wide mb-1">
                      Cited Excerpt
                    </p>
                    <p className="text-xs text-surface-300 leading-relaxed font-sans">{citationExcerpt}</p>
                  </div>
                )}

                {resolvedFileUrl && (
                  <a
                    href={resolvedFileUrl}
                    target="_blank"
                    rel="noreferrer"
                    className="inline-flex items-center gap-1.5 px-4 py-2 bg-primary-500 hover:bg-primary-600 text-surface-950 text-xs font-bold rounded-xl transition-colors shadow-lg shadow-primary-500/20"
                  >
                    <Download size={14} />
                    Download File
                  </a>
                )}
              </div>
            )}

            {/* PDF Canvas & Text Layer Viewport */}
            {!loading && !error && isPdf && (
              <div
                className="relative bg-white shadow-2xl rounded-sm transition-all duration-150"
                style={{
                  minWidth: canvasRef.current?.style.width || '300px',
                  minHeight: canvasRef.current?.style.height || '400px',
                }}
              >
                {/* PDF Canvas Layer */}
                <canvas ref={canvasRef} className="block rounded-sm" />

                {/* PDF Selectable Text Layer (Overlaid pixel-perfectly) */}
                <div
                  ref={textLayerRef}
                  className="textLayer"
                />
              </div>
            )}
          </div>

          {/* Footer with Excerpt Preview */}
          {citationExcerpt && (
            <div className="px-4 py-2.5 border-t border-surface-800 bg-surface-900/90 flex items-start gap-2.5">
              <div className="w-1.5 h-1.5 rounded-full bg-amber-400 flex-shrink-0 mt-1.5" />
              <div className="min-w-0 flex-1">
                <span className="text-[10px] font-semibold uppercase tracking-wider text-surface-400">
                  Grounded Citation Text:
                </span>
                <p className="text-xs text-surface-300 font-sans line-clamp-1 italic mt-0.5">
                  "{citationExcerpt}"
                </p>
              </div>
            </div>
          )}
        </motion.div>
      </div>
    </AnimatePresence>
  )
}
