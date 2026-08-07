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
export async function checkDuplicate(fileName, fileSize, userId) {
  const { data, error } = await supabase
    .from('documents')
    .select('id')
    .eq('user_id', userId)
    .eq('file_name', fileName)
    .eq('file_size', fileSize)
    .limit(1)

  if (error) {
    console.error('[documentService] Duplicate check error:', error)
    return false // Allow upload if check fails
  }

  return data && data.length > 0
}

// ── Upload ───────────────────────────────────────────────────

/**
 * Uploads a file to Supabase Storage and saves metadata to the documents table.
 * Triggers Module 4 AI processing pipeline in FastAPI backend.
 *
 * @param {File}     file      - The File object to upload
 * @param {string}   category  - Document category (e.g. 'HR', 'Finance')
 * @param {string}   userId    - Authenticated user's UUID
 * @param {Function} onProgress - Optional progress callback (0-100)
 * @returns {Promise<{data: object|null, error: string|null}>}
 */
export async function uploadDocument(file, category, userId, onProgress) {
  // 1. Validate
  const validation = validateFile(file)
  if (!validation.valid) return { data: null, error: validation.error }

  // 2. Duplicate check
  const isDuplicate = await checkDuplicate(file.name, file.size, userId)
  if (isDuplicate) {
    return {
      data: null,
      error: `"${file.name}" has already been uploaded. Please rename the file or delete the existing copy.`,
    }
  }

  // 3. Build storage path: {userId}/{timestamp}_{sanitizedFileName}
  const sanitizedName = file.name.replace(/[^a-zA-Z0-9._-]/g, '_')
  const storagePath = `${userId}/${Date.now()}_${sanitizedName}`
  const fileType = getFileTypeLabel(file.name)

  // 4. Upload to Supabase Storage
  onProgress?.(10)
  const { error: storageError } = await supabase.storage
    .from(BUCKET_NAME)
    .upload(storagePath, file, {
      cacheControl: '3600',
      upsert: false,
      contentType: file.type || 'application/octet-stream',
    })

  if (storageError) {
    console.error('[documentService] Storage upload error:', storageError)
    return { data: null, error: `Upload failed: ${storageError.message}` }
  }
  onProgress?.(70)

  // 5. Save metadata to documents table
  const { data: docRow, error: dbError } = await supabase
    .from('documents')
    .insert([
      {
        user_id: userId,
        file_name: file.name,
        file_type: fileType,
        file_size: file.size,
        storage_path: storagePath,
        category: category || 'General',
        status: 'Uploaded',
      },
    ])
    .select()
    .single()

  if (dbError) {
    console.error('[documentService] DB insert error:', dbError)
    // Attempt to roll back storage upload
    await supabase.storage.from(BUCKET_NAME).remove([storagePath])
    return { data: null, error: `Failed to save document record: ${dbError.message}` }
  }

  onProgress?.(90)

  // 6. Trigger backend processing (Module 4)
  triggerProcessing(docRow.id, userId).catch((err) =>
    console.warn('[documentService] Backend processing trigger warning:', err)
  )

  onProgress?.(100)
  return { data: docRow, error: null }
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
  // 1. Remove from FAISS vector index (best effort)
  try {
    await fetch(`${API_BASE_URL}/processing/index/${doc.id}?user_id=${doc.user_id}`, {
      method: 'DELETE',
    })
  } catch (e) {
    console.warn('[documentService] FAISS index delete warning:', e)
  }

  // 2. Remove from Storage
  const { error: storageError } = await supabase.storage
    .from(BUCKET_NAME)
    .remove([doc.storage_path])

  if (storageError) {
    console.error('[documentService] Storage delete error:', storageError)
  }

  // 3. Delete metadata row
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

