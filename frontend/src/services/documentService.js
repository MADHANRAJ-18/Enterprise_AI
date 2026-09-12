/**
 * documentService.js
 * ─────────────────────────────────────────────────────────────
 * Central service layer for all document operations.
 * Uses Supabase Storage + Supabase DB directly (Option A).
 *
 * Storage bucket : enterprise-documents
 * DB table       : documents
 *
 * Storage path convention:
 *   {userId}/{timestamp}_{fileName}
 *
 * Future hook points for Module 4 (AI Processing Pipeline):
 *   - After insert: trigger background job for text extraction
 *   - Status updates: 'Uploaded' → 'Processing' → 'Indexed' | 'Failed'
 * ─────────────────────────────────────────────────────────────
 */

import { supabase } from '../lib/supabaseClient'

// ── Constants ────────────────────────────────────────────────
const BUCKET_NAME = 'enterprise-documents'
const MAX_FILE_SIZE_MB = 20
const MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024
const ALLOWED_TYPES = {
  'application/pdf': 'pdf',
  'application/vnd.openxmlformats-officedocument.wordprocessingml.document': 'docx',
  'text/plain': 'txt',
}
const ALLOWED_EXTENSIONS = ['.pdf', '.docx', '.txt']

export const CATEGORIES = [
  'General',
  'HR',
  'Finance',
  'Legal',
  'IT',
  'Policies',
  'Research',
]

export const DOCUMENT_STATUSES = ['Uploaded', 'Processing', 'Indexed', 'Failed']

// ── Validation ───────────────────────────────────────────────

/**
 * Validates a file before upload.
 * Returns { valid: true } or { valid: false, error: string }.
 */
export function validateFile(file) {
  if (!file) return { valid: false, error: 'No file provided.' }

  const ext = '.' + file.name.split('.').pop().toLowerCase()
  const isAllowedExt = ALLOWED_EXTENSIONS.includes(ext)
  const isAllowedMime = Object.keys(ALLOWED_TYPES).includes(file.type)

  // Accept if either MIME or extension matches (some browsers give wrong MIME for .docx)
  if (!isAllowedExt && !isAllowedMime) {
    return {
      valid: false,
      error: `"${file.name}" is not supported. Please upload PDF, DOCX, or TXT files only.`,
    }
  }

  if (file.size > MAX_FILE_SIZE_BYTES) {
    const sizeMB = (file.size / 1024 / 1024).toFixed(1)
    return {
      valid: false,
      error: `"${file.name}" is ${sizeMB} MB. Maximum allowed size is ${MAX_FILE_SIZE_MB} MB.`,
    }
  }

  if (file.size === 0) {
    return { valid: false, error: `"${file.name}" appears to be empty.` }
  }

  return { valid: true }
}

/**
 * Returns human-readable file type label.
 */
export function getFileTypeLabel(fileName) {
  const ext = fileName.split('.').pop().toLowerCase()
  const labels = { pdf: 'PDF', docx: 'DOCX', txt: 'TXT' }
  return labels[ext] || ext.toUpperCase()
}

/**
 * Formats bytes to human-readable size string.
 */
export function formatFileSize(bytes) {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / 1024 / 1024).toFixed(2)} MB`
}

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000/api'

// ── Duplicate Check ──────────────────────────────────────────

/**
 * Checks if a user has already uploaded a file with the same name and size.
 * Returns true if a duplicate exists.
 */
export async function checkDuplicate(fileName, fileSize, userId, scope = 'workspace') {
  const { data, error } = await supabase
    .from('documents')
    .select('id')
    .eq('user_id', userId)
    .eq('file_name', fileName)
    .eq('file_size', fileSize)
    .eq('scope', scope)
    .limit(1)

  if (error) {
    console.error('[documentService] Duplicate check error:', error)
    return false // Allow upload if check fails
  }

  return data && data.length > 0
}

// ── Upload ───────────────────────────────────────────────────

/**
 * Uploads a file via the FastAPI backend (which handles processing).
 * Supports scope: 'workspace' (private, default) | 'company' (shared, requires Knowledge Admin role).
 *
 * @param {File}     file       - The File object to upload
 * @param {string}   category   - Document category (e.g. 'HR', 'Finance')
 * @param {string}   userId     - Authenticated user's UUID
 * @param {Function} onProgress - Optional progress callback (0-100)
 * @param {string}   scope      - 'workspace' | 'company' (default: 'workspace')
 * @returns {Promise<{data: object|null, error: string|null}>}
 */
export async function uploadDocument(file, category, userId, onProgress, scope = 'workspace') {
  // 1. Validate
  const validation = validateFile(file)
  if (!validation.valid) return { data: null, error: validation.error }

  // 2. Duplicate check (scope-aware)
  const isDuplicate = await checkDuplicate(file.name, file.size, userId, scope)
  if (isDuplicate) {
    return {
      data: null,
      error: `"${file.name}" has already been uploaded in ${scope} scope. Please rename or delete the existing copy.`,
    }
  }

  // 3–5: Delegate to FastAPI backend (handles storage, DB insert, FAISS indexing)
  onProgress?.(10)
  try {
    const formData = new FormData()
    formData.append('file', file)
    formData.append('user_id', userId)
    formData.append('category', category || 'General')
    formData.append('scope', scope)

    const res = await fetch(`${API_BASE_URL}/documents/upload`, {
      method: 'POST',
      body: formData,
    })

    onProgress?.(90)
    const json = await res.json()

    if (!res.ok) {
      return { data: null, error: json.detail || `Upload failed (${res.status})` }
    }

    onProgress?.(100)
    return { data: json.document, error: null }
  } catch (err) {
    console.error('[documentService] Upload error:', err)
    return { data: null, error: err.message }
  }
}

// ── Processing Triggers (Module 4 Backend) ───────────────────

/**
 * Triggers backend processing for a single document.
 */
export async function triggerProcessing(docId, userId) {
  try {
    const res = await fetch(`${API_BASE_URL}/processing/process/${docId}?user_id=${userId}`, {
      method: 'POST',
    })
    return await res.json()
  } catch (err) {
    console.error('[documentService] Trigger processing error:', err)
    return { success: false, error: err.message }
  }
}

/**
 * Triggers backend batch processing for all pending documents for a user.
 */
export async function triggerProcessingAll(userId) {
  try {
    const res = await fetch(`${API_BASE_URL}/processing/process-all`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ user_id: userId, force_reindex: false }),
    })
    return await res.json()
  } catch (err) {
    console.error('[documentService] Trigger process-all error:', err)
    return { success: false, error: err.message }
  }
}

// ── List ─────────────────────────────────────────────────────

/**
 * Fetches all documents for the authenticated user, ordered by upload date desc.
 * @param {string} userId
 * @returns {Promise<{data: Array|null, error: string|null}>}
 */
export async function listDocuments(userId) {
  const { data, error } = await supabase
    .from('documents')
    .select('*')
    .eq('user_id', userId)
    .order('uploaded_at', { ascending: false })

  if (error) {
    console.error('[documentService] List documents error:', error)
    return { data: null, error: error.message }
  }

  return { data, error: null }
}

// ── Get Single ───────────────────────────────────────────────

/**
 * Fetches a single document by ID.
 * @param {string} docId
 * @returns {Promise<{data: object|null, error: string|null}>}
 */
export async function getDocument(docId) {
  const { data, error } = await supabase
    .from('documents')
    .select('*')
    .eq('id', docId)
    .single()

  if (error) {
    return { data: null, error: error.message }
  }
  return { data, error: null }
}

// ── Delete ───────────────────────────────────────────────────

/**
 * Deletes a document from storage, FAISS vector index, and metadata table.
 * @param {object} doc - Document row from the DB
 * @returns {Promise<{success: boolean, error: string|null}>}
 */
export async function deleteDocument(doc) {
  // 1. Try Backend API endpoint first (handles FAISS, chunks, storage, DB, and email notifications)
  try {
    const res = await fetch(`${API_BASE_URL}/documents/${doc.id}?user_id=${doc.user_id}`, {
      method: 'DELETE',
    })
    if (res.ok) {
      return { success: true, error: null }
    }
  } catch (e) {
    console.warn('[documentService] Backend delete failed, falling back to direct DB delete:', e)
  }

  // 2. Fallback: Remove from FAISS vector index
  try {
    await fetch(`${API_BASE_URL}/processing/index/${doc.id}?user_id=${doc.user_id}`, {
      method: 'DELETE',
    })
  } catch (e) {
    console.warn('[documentService] FAISS index delete warning:', e)
  }

  // 3. Fallback: Remove from Storage
  const { error: storageError } = await supabase.storage
    .from(BUCKET_NAME)
    .remove([doc.storage_path])

  if (storageError) {
    console.error('[documentService] Storage delete error:', storageError)
  }

  // 4. Fallback: Delete metadata row
  const { error: dbError } = await supabase
    .from('documents')
    .delete()
    .eq('id', doc.id)

  if (dbError) {
    console.error('[documentService] DB delete error:', dbError)
    return { success: false, error: dbError.message }
  }

  return { success: true, error: null }
}

// ── Download ─────────────────────────────────────────────────

/**
 * Generates a signed URL for a document and triggers a browser download.
 * @param {object} doc - Document row from the DB
 * @returns {Promise<{success: boolean, error: string|null}>}
 */
export async function downloadDocument(doc) {
  const { data, error } = await supabase.storage
    .from(BUCKET_NAME)
    .createSignedUrl(doc.storage_path, 60) // 60 second expiry

  if (error) {
    console.error('[documentService] Signed URL error:', error)
    return { success: false, error: error.message }
  }

  // Trigger browser download
  const anchor = document.createElement('a')
  anchor.href = data.signedUrl
  anchor.download = doc.file_name
  anchor.click()

  return { success: true, error: null }
}

/**
 * Obtains a secure temporary URL for rendering or viewing a document in the PDF viewer.
 * @param {string} docId  - Document UUID
 * @param {string} userId - Authenticated user UUID
 * @returns {Promise<{url: string|null, fileName: string|null, fileType: string|null, error: string|null}>}
 */
export async function getDocumentFileUrl(docId, userId) {
  if (!docId) return { url: null, error: 'Document ID is required.' }

  // 1. Try Backend signed URL endpoint (verifies workspace privacy and company permissions)
  try {
    const res = await fetch(`${API_BASE_URL}/documents/${docId}/signed-url?user_id=${userId}`)
    if (res.ok) {
      const json = await res.json()
      if (json.signed_url) {
        return {
          url: json.signed_url,
          fileName: json.file_name || 'Document.pdf',
          fileType: json.file_type || 'PDF',
          error: null,
        }
      }
    } else if (res.status === 403) {
      return { url: null, error: 'Access denied: You do not have permission to view this document.' }
    } else if (res.status === 404) {
      return { url: null, error: 'Document not found or has been deleted.' }
    }
  } catch (err) {
    console.warn('[documentService] Backend signed URL request failed, attempting fallback:', err)
  }

  // 2. Direct Supabase Signed URL check
  try {
    const { data: doc, error: docErr } = await supabase
      .from('documents')
      .select('id, file_name, file_type, storage_path, scope, user_id')
      .eq('id', docId)
      .single()

    if (!docErr && doc?.storage_path) {
      const { data: signedData, error: signedErr } = await supabase.storage
        .from(BUCKET_NAME)
        .createSignedUrl(doc.storage_path, 900)

      if (!signedErr && signedData?.signedUrl) {
        return {
          url: signedData.signedUrl,
          fileName: doc.file_name || 'Document.pdf',
          fileType: doc.file_type || 'PDF',
          error: null,
        }
      }
    }
  } catch (e) {
    console.warn('[documentService] Direct Supabase signed URL error:', e)
  }

  // 3. Fallback to direct backend streaming endpoint
  return {
    url: `${API_BASE_URL}/documents/${docId}/file?user_id=${userId}`,
    fileName: 'Document.pdf',
    fileType: 'PDF',
    error: null,
  }
}

function formatErrorMessage(json, res) {
  if (!json) return `Request failed (${res?.status || 'Unknown'})`
  if (typeof json.detail === 'string') return json.detail
  if (Array.isArray(json.detail)) return json.detail.map((e) => e.msg || JSON.stringify(e)).join(', ')
  if (json.detail) return JSON.stringify(json.detail)
  if (json.message) return json.message
  return `Request failed (${res?.status || 'Unknown'})`
}

// ── Update Metadata ────────────────────────────────────────────

/**
 * Updates metadata for a document (e.g., category, file_name).
 * Uses direct Supabase DB update with backend API fallback.
 * @param {string} docId
 * @param {string} userId
 * @param {object} updates - { category?: string, file_name?: string }
 * @returns {Promise<{data: object|null, error: string|null}>}
 */
export async function updateDocumentMetadata(docId, userId, updates) {
  // 1. Direct Supabase DB update
  const { data: sbData, error: sbError } = await supabase
    .from('documents')
    .update(updates)
    .eq('id', docId)
    .select()

  if (!sbError && sbData && sbData.length > 0) {
    // Notify backend asynchronously
    fetch(`${API_BASE_URL}/documents/${docId}?user_id=${userId}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(updates),
    }).catch(() => {})

    return { data: sbData[0], error: null }
  }

  // 2. Try FastAPI backend API
  const urlsToTry = [
    `${API_BASE_URL}/documents/${docId}?user_id=${userId}`,
    `http://localhost:8000/api/documents/${docId}?user_id=${userId}`,
    `http://127.0.0.1:8000/api/documents/${docId}?user_id=${userId}`,
  ]

  for (const url of urlsToTry) {
    try {
      const res = await fetch(url, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(updates),
      })
      const json = await res.json().catch(() => ({}))
      if (!res.ok) {
        return { data: null, error: formatErrorMessage(json, res) }
      }
      return { data: json, error: null }
    } catch (e) {
      // try next url
    }
  }

  return { data: null, error: sbError ? sbError.message : 'Failed to reach server' }
}

// ── Overwrite File Content ────────────────────────────────────

/**
 * Overwrites / replaces document file content and re-queues AI processing.
 * @param {string} docId
 * @param {string} userId
 * @param {File}   file
 * @returns {Promise<{data: object|null, error: string|null}>}
 */
export async function overwriteDocument(docId, userId, file) {
  const validation = validateFile(file)
  if (!validation.valid) return { data: null, error: validation.error }

  const urlsToTry = [
    `${API_BASE_URL}/documents/${docId}/overwrite`,
    `http://localhost:8000/api/documents/${docId}/overwrite`,
    `http://127.0.0.1:8000/api/documents/${docId}/overwrite`,
  ]

  let lastError = 'Failed to fetch'
  for (const url of urlsToTry) {
    try {
      const formData = new FormData()
      formData.append('file', file)
      formData.append('user_id', userId)

      const res = await fetch(url, {
        method: 'POST',
        body: formData,
      })

      const json = await res.json().catch(() => ({}))

      if (!res.ok) {
        return { data: null, error: formatErrorMessage(json, res) }
      }

      return { data: json.document, error: null }
    } catch (err) {
      lastError = err.message
    }
  }

  return { data: null, error: lastError }
}

// ── Update Status (hook for Module 4) ────────────────────────

/**
 * Updates the processing status of a document.
 * @param {string} docId
 * @param {'Uploaded'|'Processing'|'Indexed'|'Failed'} status
 * @returns {Promise<{success: boolean, error: string|null}>}
 */
export async function updateDocumentStatus(docId, status) {
  const { error } = await supabase
    .from('documents')
    .update({ status })
    .eq('id', docId)

  if (error) {
    return { success: false, error: error.message }
  }
  return { success: true, error: null }
}

