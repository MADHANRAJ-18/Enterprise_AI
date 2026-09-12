/**
 * src/services/chatService.js
 * ─────────────────────────────────────────────────────────────
 * Module 5 / 6 – Chat + RAG API service layer
 *
 * Connects the React frontend to:
 *   • Module 5: POST /api/chat       (direct Groq LLM - Llama 3.3 70B)
 *   • Module 6: POST /api/rag/chat   (RAG-augmented)
 *              POST /api/rag/search  (debug chunk retrieval)
 *              GET  /api/rag/health  (combined health)
 * ─────────────────────────────────────────────────────────────
 */

const API_BASE_URL = import.meta.env.VITE_API_URL || import.meta.env.VITE_API_BASE_URL?.replace(/\/api\/?$/, '') || 'http://127.0.0.1:8000'

/**
 * Helper to fetch with clear error messages on network/connection failure.
 */
async function safeFetch(url, options = {}) {
  let res
  try {
    res = await fetch(url, options)
  } catch (err) {
    // If the server is momentarily reloading/starting, retry once after 600ms
    if (err.name === 'TypeError' || err.message?.includes('Failed to fetch')) {
      try {
        await new Promise((resolve) => setTimeout(resolve, 600))
        res = await fetch(url, options)
      } catch (_) {
        throw new Error(`Cannot connect to AI backend at ${API_BASE_URL}. Please ensure the Python FastAPI server is running on port 8000.`)
      }
    } else {
      throw err
    }
  }

  if (!res.ok) {
    let detail = `HTTP ${res.status}`
    try {
      const data = await res.json()
      detail = data.detail || data.message || detail
      if (typeof detail === 'object') detail = JSON.stringify(detail)
    } catch (_) {}
    throw new Error(detail)
  }

  return res.json()
}

// ── Module 5: Direct Groq chat ──────────────────────────────

/**
 * Send a message to Groq (Llama 3.3 70B Versatile with optional RAG).
 * When use_rag=true, the backend runs the full Module 6 pipeline.
 *
 * @param {string} message
 * @param {Array}  conversationHistory  [{role, content}]
 * @param {Object} options  { system_prompt, use_rag, document_ids, attachments }
 * @returns {Promise<ChatResponse>}
 */
export async function sendChatMessage(message, conversationHistory = [], options = {}) {
  const payload = {
    message: message.trim(),
    conversation_history: conversationHistory.map((m) => ({
      role:    m.role === 'assistant' ? 'assistant' : m.role,
      content: m.content,
    })),
    system_prompt:  options.system_prompt  || null,
    use_rag:        options.use_rag        ?? false,
    document_ids:   options.document_ids   || null,
    attachments:    options.attachments    || null,
  }

  return safeFetch(`${API_BASE_URL}/api/chat`, {
    method:  'POST',
    headers: { 'Content-Type': 'application/json' },
    body:    JSON.stringify(payload),
  })
}

// ── Module 6: RAG-specific chat (dedicated endpoint) ──────────

/**
 * RAG-augmented chat via dedicated /api/rag/chat endpoint.
 * Returns richer metadata: citations, retrieval_time, generation_time, etc.
 *
 * @param {string} message
 * @param {Object} options  { top_k, similarity_threshold, document_ids, system_prompt, conversation_history }
 * @returns {Promise<RAGChatResponse>}
 */
export async function sendRAGMessage(message, options = {}) {
  const payload = {
    message: message.trim(),
    top_k:                options.top_k                ?? 5,
    similarity_threshold: options.similarity_threshold ?? 0.3,
    document_ids:         options.document_ids         || null,
    system_prompt:        options.system_prompt        || null,
    conversation_history: options.conversation_history || null,
    attachments:          options.attachments          || null,
  }

  return safeFetch(`${API_BASE_URL}/api/rag/chat`, {
    method:  'POST',
    headers: { 'Content-Type': 'application/json' },
    body:    JSON.stringify(payload),
  })
}

/**
 * Debug: retrieve document chunks without calling LLM.
 *
 * @param {string} query
 * @param {Object} options  { top_k, similarity_threshold, document_ids }
 * @returns {Promise<SearchResponse>}
 */
export async function searchDocuments(query, options = {}) {
  const payload = {
    query: query.trim(),
    top_k:                options.top_k                ?? 10,
    similarity_threshold: options.similarity_threshold ?? 0.0,
    document_ids:         options.document_ids         || null,
  }

  return safeFetch(`${API_BASE_URL}/api/rag/search`, {
    method:  'POST',
    headers: { 'Content-Type': 'application/json' },
    body:    JSON.stringify(payload),
  })
}

// ── Health checks ─────────────────────────────────────────────

/** Verify Groq LLM connectivity (Module 5). */
export async function checkLLMHealth() {
  return safeFetch(`${API_BASE_URL}/api/chat/health`)
}

/** Verify FAISS + embedder + LLM combined health (Module 6). */
export async function checkRAGHealth() {
  return safeFetch(`${API_BASE_URL}/api/rag/health`)
}

/** Retrieve current LLM + RAG configuration. */
export async function getLLMConfig() {
  return safeFetch(`${API_BASE_URL}/api/chat/config`)
}

/** Parse a file transiently for direct attachment in chat. */
export async function parseChatFile(file) {
  const formData = new FormData()
  formData.append('file', file)

  return safeFetch(`${API_BASE_URL}/api/chat/parse-file`, {
    method: 'POST',
    body:   formData,
  })
}

// ── Conversation management (Module 9 – Chat History) ─────────

/**
 * Fetch all conversations for the authenticated user.
 * GET /api/conversations?user_id=:uid
 *
 * @param {string} userId
 * @returns {Promise<{ conversations: Array, total: number }>}
 */
export async function fetchConversations(userId) {
  return safeFetch(`${API_BASE_URL}/api/conversations?user_id=${encodeURIComponent(userId)}`)
}

/**
 * Fetch all messages for a specific conversation.
 * GET /api/conversations/:id/messages?user_id=:uid
 *
 * @param {string} convId
 * @param {string} userId
 * @returns {Promise<{ messages: Array, total: number, conversation_id: string }>}
 */
export async function fetchMessages(convId, userId) {
  return safeFetch(
    `${API_BASE_URL}/api/conversations/${encodeURIComponent(convId)}/messages?user_id=${encodeURIComponent(userId)}`
  )
}

/**
 * Create a new conversation for the authenticated user.
 * POST /api/conversations
 *
 * @param {string} userId
 * @param {string} title
 * @returns {Promise<{ success: boolean, conversation: object }>}
 */
export async function createConversation(userId, title = 'New Conversation') {
  return safeFetch(`${API_BASE_URL}/api/conversations`, {
    method:  'POST',
    headers: { 'Content-Type': 'application/json' },
    body:    JSON.stringify({ user_id: userId, title }),
  })
}

/**
 * Append a message (user or assistant) to a conversation.
 * POST /api/conversations/:id/messages
 *
 * @param {string} convId
 * @param {string} userId
 * @param {string} role 'user' | 'assistant'
 * @param {string} content
 * @param {Array|null} sources
 * @returns {Promise<{ success: boolean, message: object }>}
 */
export async function appendMessage(convId, userId, role, content, sources = null) {
  return safeFetch(`${API_BASE_URL}/api/conversations/${encodeURIComponent(convId)}/messages`, {
    method:  'POST',
    headers: { 'Content-Type': 'application/json' },
    body:    JSON.stringify({
      user_id: userId,
      role,
      content,
      sources: sources && sources.length > 0 ? sources : null,
    }),
  })
}

/**
 * Generate a dynamic 3-5 word title for a conversation using LLM.
 * POST /api/conversations/:id/generate-title
 *
 * @param {string} convId
 * @param {string} userId
 * @param {string} userMessage
 * @returns {Promise<{ success: boolean, title: string }>}
 */
export async function generateConversationTitle(convId, userId, userMessage) {
  return safeFetch(`${API_BASE_URL}/api/conversations/${encodeURIComponent(convId)}/generate-title`, {
    method:  'POST',
    headers: { 'Content-Type': 'application/json' },
    body:    JSON.stringify({
      user_id:      userId,
      user_message: userMessage,
    }),
  })
}

/**
 * Delete a conversation and all its messages.
 * DELETE /api/conversations/:id?user_id=:uid
 *
 * @param {string} convId
 * @param {string} userId
 * @returns {Promise<void>}  — 204 No Content; safeFetch handles non-JSON 204 gracefully.
 */
export async function deleteConversation(convId, userId) {
  // 204 returns no body — wrap safeFetch to handle the empty response
  let res
  try {
    res = await fetch(
      `${API_BASE_URL}/api/conversations/${encodeURIComponent(convId)}?user_id=${encodeURIComponent(userId)}`,
      { method: 'DELETE' }
    )
  } catch (err) {
    if (err.name === 'TypeError' || err.message?.includes('Failed to fetch')) {
      try {
        await new Promise((resolve) => setTimeout(resolve, 600))
        res = await fetch(
          `${API_BASE_URL}/api/conversations/${encodeURIComponent(convId)}?user_id=${encodeURIComponent(userId)}`,
          { method: 'DELETE' }
        )
      } catch (_) {
        throw new Error(`Cannot connect to AI backend at ${API_BASE_URL}. Please ensure the Python FastAPI server is running on port 8000.`)
      }
    } else {
      throw err
    }
  }
  if (!res.ok && res.status !== 204) {
    let detail = `HTTP ${res.status}`
    try {
      const data = await res.json()
      detail = data.detail || data.message || detail
    } catch (_) {}
    throw new Error(detail)
  }
  // 204 — success, no body
}

