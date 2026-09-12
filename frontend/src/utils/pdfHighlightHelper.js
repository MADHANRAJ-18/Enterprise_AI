/**
 * pdfHighlightHelper.js
 * ─────────────────────────────────────────────────────────────
 * Robust multi-evidence text matching and highlight applicator for PDF.js textLayer.
 *
 * Key behaviors:
 * - Supports MULTIPLE evidence spans per citation (e.g. 7 separate policy sections).
 * - Matches and highlights ALL supporting passages across the PDF page simultaneously.
 * - Exact index mapping (normToOrigMap) eliminates punctuation/dash drift and DOM misalignment.
 * - Handles text split across arbitrary textLayer <span> elements and line wraps.
 * - Word-boundary continuation prevents split glyphs (e.g. "NovaTe" + "ch").
 * - Returns detailed metrics: totalEvidenceSpans, matchedEvidenceSpans, firstMatchedElement.
 * ─────────────────────────────────────────────────────────────
 */

/**
 * Normalizes text for reliable substring comparison.
 * @param {string} str
 * @returns {string}
 */
export function normalizeText(str) {
  if (!str) return ''
  return str
    .replace(/[\u2018\u2019]/g, "'")
    .replace(/[\u201C\u201D]/g, '"')
    .replace(/[\u2013\u2014]/g, '-')
    .replace(/\r\n|\r|\n/g, ' ')
    .replace(/[\u00A0\u202F]/g, ' ')
    .replace(/\s+/g, ' ')
    .trim()
    .toLowerCase()
}

/**
 * Extracts and prepares an array of clean evidence span objects from any input format
 * (array of spans, citation object with evidence_spans, source_text, text_preview, etc.).
 *
 * @param {any} citationOrSpans
 * @param {string} [aiAnswer]
 * @returns {Array<{ text: string, score?: number }>}
 */
export function extractEvidenceSpans(citationOrSpans, aiAnswer = '') {
  if (!citationOrSpans) return []

  // 1. Direct array of evidence spans
  if (Array.isArray(citationOrSpans)) {
    return citationOrSpans
      .map((s) => (typeof s === 'string' ? { text: s } : s))
      .filter((s) => s && typeof s.text === 'string' && s.text.trim().length >= 4)
  }

  // 2. Citation object with evidence_spans list
  if (Array.isArray(citationOrSpans.evidence_spans) && citationOrSpans.evidence_spans.length > 0) {
    return citationOrSpans.evidence_spans
      .map((s) => (typeof s === 'string' ? { text: s } : s))
      .filter((s) => s && typeof s.text === 'string' && s.text.trim().length >= 4)
  }

  // 3. Fallback to raw string / source_text / excerpt
  const rawText =
    typeof citationOrSpans === 'string'
      ? citationOrSpans
      : citationOrSpans.source_text ||
        citationOrSpans.text_preview ||
        citationOrSpans.full_text ||
        ''

  const cleanText = rawText.trim()
  if (!cleanText) return []

  // Split multiple lines if present
  const lines = cleanText
    .split(/\n+/)
    .map((l) => l.trim())
    .filter((l) => l.length >= 8)

  if (lines.length > 1) {
    // If aiAnswer is provided, score lines and filter out unrelated lines
    if (aiAnswer) {
      const ansTokens = new Set(
        normalizeText(aiAnswer)
          .split(/\s+/)
          .filter((w) => w.length >= 3)
      )
      const matching = lines.filter((line) => {
        const lineTokens = normalizeText(line)
          .split(/\s+/)
          .filter((w) => w.length >= 3)
        return lineTokens.some((tok) => ansTokens.has(tok))
      })
      if (matching.length > 0) {
        return matching.map((t) => ({ text: t }))
      }
    }
    return lines.map((t) => ({ text: t }))
  }

  // Single sentence / paragraph
  return [{ text: cleanText }]
}

/**
 * Searches for an evidence span inside the normalized text layer using
 * progressive matching strategies (exact -> sentence -> multi-word phrase).
 *
 * @param {string} normUnified - Full normalized text of the page
 * @param {string} normSpan    - Normalized text of the evidence span
 * @returns {{ matchStart: number, matchLen: number } | null}
 */
function findMatchInText(normUnified, normSpan) {
  if (!normUnified || !normSpan || normSpan.length < 3) return null

  // Strategy 1: Exact substring match
  let idx = normUnified.indexOf(normSpan)
  if (idx !== -1) {
    return { matchStart: idx, matchLen: normSpan.length }
  }

  // Strategy 2: Sentence / punctuation boundary fallback (for multi-sentence spans)
  if (normSpan.length > 28) {
    const sentences = normSpan
      .split(/[.!?]+/)
      .map((s) => normalizeText(s))
      .filter((s) => s.length >= 16)

    for (const sent of sentences) {
      idx = normUnified.indexOf(sent)
      if (idx !== -1) {
        return { matchStart: idx, matchLen: sent.length }
      }
    }
  }

  // Strategy 3: Anchor 4-6 word phrase match
  if (normSpan.length > 18) {
    const words = normSpan.split(' ').filter((w) => w.length >= 2)
    if (words.length >= 4) {
      // Try beginning phrase
      const startPhrase = words.slice(0, Math.min(6, words.length)).join(' ')
      idx = normUnified.indexOf(startPhrase)
      if (idx !== -1) {
        return { matchStart: idx, matchLen: startPhrase.length }
      }

      // Try middle phrase if span is long
      if (words.length >= 8) {
        const midPhrase = words.slice(2, 7).join(' ')
        idx = normUnified.indexOf(midPhrase)
        if (idx !== -1) {
          return { matchStart: idx, matchLen: midPhrase.length }
        }
      }
    }
  }

  return null
}

/**
 * Highlights ALL exact source evidence spans inside the PDF textLayer container.
 *
 * @param {HTMLElement} textLayerContainer - Container DOM element with rendered <span>s
 * @param {any} citationOrSpans            - Citation object or list of evidence spans
 * @param {string} [aiAnswer]              - The AI's full answer text for filtering
 * @returns {{ matchedCount: number, totalEvidenceSpans: number, matchedEvidenceSpans: number, firstMatchedElement: HTMLElement|null }}
 */
export function highlightCitationInTextLayer(textLayerContainer, citationOrSpans, aiAnswer = '') {
  if (!textLayerContainer || !citationOrSpans) {
    return {
      matchedCount: 0,
      totalEvidenceSpans: 0,
      matchedEvidenceSpans: 0,
      firstMatchedElement: null,
    }
  }

  // 1. Clear any previous highlights
  const existing = textLayerContainer.querySelectorAll('.pdf-citation-highlight')
  existing.forEach((el) => el.classList.remove('pdf-citation-highlight'))

  const spans = Array.from(textLayerContainer.querySelectorAll('span'))
  if (spans.length === 0) {
    return {
      matchedCount: 0,
      totalEvidenceSpans: 0,
      matchedEvidenceSpans: 0,
      firstMatchedElement: null,
    }
  }

  // 2. Build unified text and character-to-span mapping
  let unifiedText = ''
  const charMap = [] // origCharIndex -> span element

  for (const span of spans) {
    const text = span.textContent || ''
    for (let i = 0; i < text.length; i++) {
      charMap.push(span)
    }
    unifiedText += text
    // Separator between adjacent spans to prevent word merging collisions
    if (!text.endsWith(' ') && !text.endsWith('\n')) {
      unifiedText += ' '
      charMap.push(span)
    }
  }

  // 3. Build a normalized string with a 1-to-1 index map back to original characters
  let normUnified = ''
  const normToOrigMap = [] // normCharIndex -> origCharIndex

  for (let i = 0; i < unifiedText.length; i++) {
    let c = unifiedText[i].toLowerCase()

    // Normalize quotes and dashes
    if (c === '\u2018' || c === '\u2019') c = "'"
    else if (c === '\u201C' || c === '\u201D') c = '"'
    else if (c === '\u2013' || c === '\u2014') c = '-'

    // Collapse whitespace
    if (/[\s\u00A0\u202F]/.test(c)) {
      if (normUnified.length > 0 && normUnified[normUnified.length - 1] === ' ') {
        continue // skip multiple consecutive spaces
      }
      c = ' '
    }

    normUnified += c
    normToOrigMap.push(i)
  }

  // 4. Extract all evidence spans to highlight
  const evidenceSpans = extractEvidenceSpans(citationOrSpans, aiAnswer)
  if (evidenceSpans.length === 0) {
    return {
      matchedCount: 0,
      totalEvidenceSpans: 0,
      matchedEvidenceSpans: 0,
      firstMatchedElement: null,
    }
  }

  // 5. Match and collect all evidence spans
  const matchedSpansSet = new Set()
  let matchedEvidenceCount = 0

  for (const spanObj of evidenceSpans) {
    const normSpan = normalizeText(spanObj.text)
    const match = findMatchInText(normUnified, normSpan)
    if (!match) continue

    const { matchStart, matchLen } = match
    const origStart = normToOrigMap[matchStart] !== undefined ? normToOrigMap[matchStart] : 0
    const origEnd =
      normToOrigMap[matchStart + matchLen - 1] !== undefined
        ? normToOrigMap[matchStart + matchLen - 1]
        : unifiedText.length - 1

    let lastSpan = null
    for (let i = origStart; i <= origEnd && i < charMap.length; i++) {
      if (charMap[i]) {
        matchedSpansSet.add(charMap[i])
        lastSpan = charMap[i]
      }
    }

    // Word-boundary continuation check (e.g. split glyphs "NovaTe" + "ch")
    if (lastSpan) {
      const lastSpanIdx = spans.indexOf(lastSpan)
      if (lastSpanIdx !== -1 && lastSpanIdx + 1 < spans.length) {
        const nextSpan = spans[lastSpanIdx + 1]
        const nextText = (nextSpan.textContent || '').trim()
        if (nextText.length <= 4 && !/^\s/.test(nextSpan.textContent || '')) {
          matchedSpansSet.add(nextSpan)
        }
      }
    }

    matchedEvidenceCount++
  }

  // 6. Identify the FIRST matched element in document reading order
  let firstMatchedElement = null
  for (const span of spans) {
    if (matchedSpansSet.has(span)) {
      firstMatchedElement = span
      break
    }
  }

  // 7. Apply highlight class to all matched spans
  matchedSpansSet.forEach((span) => {
    span.classList.add('pdf-citation-highlight')
  })

  return {
    matchedCount: matchedSpansSet.size,
    totalEvidenceSpans: evidenceSpans.length,
    matchedEvidenceSpans: matchedEvidenceCount,
    firstMatchedElement,
  }
}
