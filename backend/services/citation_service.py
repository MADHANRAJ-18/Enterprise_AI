from __future__ import annotations

import re
import string
import logging
from typing import List, Set, Dict, Any, Optional

from models.rag import DocumentChunk, EvidenceSpan

logger = logging.getLogger(__name__)

# Common stop words to exclude during overlap calculation
STOP_WORDS = {
    "a", "about", "above", "after", "again", "against", "all", "am", "an", "and",
    "any", "are", "aren't", "as", "at", "be", "because", "been", "before", "being",
    "below", "between", "both", "but", "by", "can", "can't", "cannot", "could",
    "couldn't", "did", "didn't", "do", "does", "doesn't", "doing", "don't", "down",
    "during", "each", "few", "for", "from", "further", "had", "hadn't", "has",
    "hasn't", "have", "haven't", "having", "he", "he'd", "he'll", "he's", "her",
    "here", "here's", "hers", "herself", "him", "himself", "his", "how", "how's",
    "i", "i'd", "i'll", "i'm", "i've", "if", "in", "into", "is", "isn't", "it",
    "it's", "its", "itself", "let's", "me", "more", "most", "mustn't", "my",
    "myself", "no", "nor", "not", "of", "off", "on", "once", "only", "or", "other",
    "ought", "our", "ours", "ourselves", "out", "over", "own", "same", "shan't",
    "she", "she'd", "she'll", "she's", "should", "shouldn't", "so", "some", "such",
    "than", "that", "that's", "the", "their", "theirs", "them", "themselves", "then",
    "there", "there's", "these", "they", "they'd", "they'll", "they're", "they've",
    "this", "those", "through", "to", "too", "under", "until", "up", "very", "was",
    "wasn't", "we", "we'd", "we'll", "we're", "we've", "were", "weren't", "what",
    "what's", "when", "when's", "where", "where's", "which", "while", "who", "who's",
    "whom", "why", "why's", "with", "won't", "would", "wouldn't", "you", "you'd",
    "you'll", "you're", "you've", "your", "yours", "yourself", "yourselves",
    "document", "documents", "source", "sources", "excerpt", "excerpts", "context",
    "information", "provided", "uploaded", "according", "based", "found"
}

# Negation and fallback phrases indicating no document knowledge was used
NEGATIVE_PHRASES = [
    "could not find",
    "couldn't find",
    "cannot find",
    "can't find",
    "no relevant information",
    "no relevant answer",
    "no information was found",
    "no matching information",
    "not found in the uploaded",
    "not found in the provided",
    "not mentioned in the uploaded",
    "not mentioned in the provided",
    "not provided in the documents",
    "not provided in the context",
    "do not contain information",
    "does not contain information",
    "does not mention",
    "do not mention",
    "don't have access to",
    "do not have access to",
    "no documents were found",
    "no matching documents",
    "no documents contain",
    "neither of the provided documents",
    "none of the provided documents",
    "the context does not provide",
    "the context does not contain",
    "i do not have information",
    "i don't have information",
]

GREETING_STARTS = [
    "hello!", "hello,", "hello ", "hi!", "hi,", "hi ", "hey!", "hey,", "hey ",
    "good morning", "good afternoon", "good evening", "how can i help", "how can i assist",
    "you're welcome", "you are welcome", "glad i could help", "i am your enterprise ai"
]


def is_negative_or_conversational(answer_text: str) -> bool:
    """
    Check if the answer is a fallback message, negation, or general greeting.
    When True, citation lists should be empty rather than attaching irrelevant chunks.
    """
    if not answer_text or not answer_text.strip():
        return True

    text_lower = answer_text.strip().lower()

    # Short greetings or conversational dismissals
    for g in GREETING_STARTS:
        if text_lower.startswith(g) or (g in text_lower and len(text_lower) < 200):
            return True

    # Check for negative fallback indicators
    for phrase in NEGATIVE_PHRASES:
        if phrase in text_lower:
            # If the entire answer is short or primarily about not finding info, treat as fallback
            if len(text_lower) < 400 or text_lower.count("\n") <= 3:
                return True

    return False


def extract_referenced_source_indices(answer_text: str, max_sources: int) -> Set[int]:
    """
    Extract all 1-based source indices explicitly cited in the answer text.
    Handles:
      - [Source 1], [Source 2], [source 3]
      - [Source 1, 2, 3] or [Source 1, Source 2]
      - [Source 1-3] or [Source 1 - 3]
      - [Doc 1], [Document 1], [Ref 1]
      - (Source 1), (Source 2)
      - [1], [2], [1, 2]
    """
    if not answer_text or max_sources <= 0:
        return set()

    found_indices: Set[int] = set()

    # 1. Matches: [Source 1-3] or [Source 1 - 3]
    range_matches = re.finditer(r"\[(?:Source|Doc|Document|Ref)\s*(\d+)\s*[-–—]\s*(\d+)\]", answer_text, re.IGNORECASE)
    for m in range_matches:
        try:
            start, end = int(m.group(1)), int(m.group(2))
            if start <= end and start >= 1:
                for idx in range(start, min(end, max_sources) + 1):
                    found_indices.add(idx)
        except ValueError:
            pass

    # 2. Matches: [Source 1, 2, 3], [Source 1], [Doc 2], (Source 1)
    tag_matches = re.finditer(r"[\[\(](?:Source|Doc|Document|Ref)\s*([\d\s,]+)[\]\)]", answer_text, re.IGNORECASE)
    for m in tag_matches:
        raw_nums = m.group(1)
        for num_str in re.findall(r"\d+", raw_nums):
            try:
                idx = int(num_str)
                if 1 <= idx <= max_sources:
                    found_indices.add(idx)
            except ValueError:
                pass

    # 3. Matches: [1], [2], [1, 2] if preceded by a word or end of sentence
    bracket_matches = re.finditer(r"\[(\d+(?:\s*,\s*\d+)*)\]", answer_text)
    for m in bracket_matches:
        raw_nums = m.group(1)
        for num_str in re.findall(r"\d+", raw_nums):
            try:
                idx = int(num_str)
                if 1 <= idx <= max_sources:
                    found_indices.add(idx)
            except ValueError:
                pass

    return found_indices


def _tokenize(text: str) -> Set[str]:
    """Tokenize text into lowercase alphanumeric words excluding punctuation and stop words."""
    words = re.findall(r"\b[a-zA-Z0-9_-]{3,}\b", text.lower())
    return {w for w in words if w not in STOP_WORDS and not w.isdigit()}


def calculate_text_overlap(chunk_text: str, answer_text: str) -> float:
    """Calculate semantic keyword overlap between a document chunk and the generated answer."""
    if not chunk_text or not answer_text:
        return 0.0

    chunk_words = _tokenize(chunk_text)
    answer_words = _tokenize(answer_text)

    if not chunk_words or not answer_words:
        return 0.0

    intersection = chunk_words.intersection(answer_words)
    if not intersection:
        return 0.0

    # Overlap relative to the answer vocabulary
    overlap_score = len(intersection) / min(len(answer_words), 30)
    return min(1.0, overlap_score)


def extract_grounded_evidence_spans(chunk_text: str, answer_text: str) -> List[Dict[str, Any]]:
    """
    Identifies and extracts ALL exact source sentences/spans from chunk_text that
    support the AI answer, preserving document order.
    
    Returns a list of dicts: [{"text": str, "score": float}, ...]
    """
    if not chunk_text:
        return []
    
    clean_chunk = chunk_text.strip()
    if not clean_chunk:
        return []
        
    if not answer_text:
        return [{"text": clean_chunk[:300].strip(), "score": 1.0}]

    # 1. Candidate line / sentence extraction
    raw_lines = [l.strip() for l in clean_chunk.splitlines() if l.strip()]
    
    candidate_spans: List[str] = []
    for line in raw_lines:
        # If line is long or contains multiple sentences, split by sentences
        if len(line) > 130 and re.search(r"[.!?]\s+[A-Z0-9]", line):
            sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", line) if s.strip()]
            candidate_spans.extend(sentences)
        else:
            candidate_spans.append(line)

    # Filter out empty or trivially short items
    candidate_spans = [c for c in candidate_spans if len(c) >= 6]
    if not candidate_spans:
        return [{"text": clean_chunk[:300].strip(), "score": 1.0}]

    # 2. Extract answer tokens (alphanumeric words length >= 2)
    answer_tokens = set(re.findall(r"\b[a-zA-Z0-9]{2,}\b", answer_text.lower()))
    
    # 3. Score each candidate span against the answer
    scored_candidates = []
    for span in candidate_spans:
        span_words = span.split()
        # Filter out standalone short section headers (e.g. "Leave Policy", "Working Hours")
        # unless they contain terminal punctuation or numbers or are >= 22 chars with >= 4 words
        has_punctuation = any(span.endswith(p) for p in [".", "!", "?", ";"])
        has_digits = any(char.isdigit() for char in span)
        if len(span) < 22 and len(span_words) <= 3 and not has_punctuation and not has_digits:
            continue

        # Filter title banner headers like "Employee Handbook - Company Name"
        if re.search(r"\b(handbook|policy|manual|overview|guidelines|document)\s*[-–:]\s*", span, re.IGNORECASE) and not has_digits and len(span_words) <= 7:
            continue

        span_tokens = set(re.findall(r"\b[a-zA-Z0-9]{2,}\b", span.lower()))
        if not span_tokens:
            continue
            
        common = answer_tokens.intersection(span_tokens)
        if not common:
            continue
            
        # Ignore matches that only match generic stop words
        non_stop_common = common - STOP_WORDS
        if not non_stop_common:
            continue

        overlap_count = len(non_stop_common)
        density = overlap_count / (len(span_tokens) ** 0.5)
        
        # Numbers / digits bonus
        num_digits = sum(1 for tok in non_stop_common if any(char.isdigit() for char in tok))
        final_score = density + (num_digits * 0.4)
        
        # Criteria to accept as an evidence span:
        # - at least 2 non-stop words match and density >= 0.35, OR
        # - 1 non-stop word with a number/digit, OR
        # - overlap >= 3
        if (overlap_count >= 2 and density >= 0.35) or (num_digits >= 1 and overlap_count >= 1) or (overlap_count >= 3):
            scored_candidates.append({
                "text": span,
                "score": round(final_score, 4),
                "overlap": overlap_count,
            })

    # If no candidate passed the threshold, fall back to the highest scoring single candidate
    if not scored_candidates:
        best_candidate = None
        best_score = -1.0
        for span in candidate_spans:
            span_tokens = set(re.findall(r"\b[a-zA-Z0-9]{2,}\b", span.lower()))
            if not span_tokens:
                continue
            common = (answer_tokens.intersection(span_tokens)) - STOP_WORDS
            score = len(common) / (len(span_tokens) ** 0.5) if common else 0.0
            if score > best_score:
                best_score = score
                best_candidate = span
        if best_candidate and best_score > 0:
            return [{"text": best_candidate, "score": round(best_score, 4)}]
        return [{"text": candidate_spans[0], "score": 0.0}]

    # Deduplicate redundant or subset spans
    unique_spans: List[Dict[str, Any]] = []
    seen_texts: Set[str] = set()
    
    for item in scored_candidates:
        t = item["text"]
        norm_t = t.lower()
        if norm_t in seen_texts:
            continue
            
        # Avoid adding a sub-phrase if full phrase is already added or vice-versa
        is_sub = any(norm_t in existing.lower() for existing in seen_texts)
        if is_sub:
            continue
            
        seen_texts.add(norm_t)
        unique_spans.append({"text": t, "score": item["score"]})

    # Sort according to position in clean_chunk to preserve document reading order
    def get_pos(item):
        pos = clean_chunk.find(item["text"])
        return pos if pos != -1 else 999999
        
    unique_spans.sort(key=get_pos)
    return unique_spans


def extract_grounded_excerpt(chunk_text: str, answer_text: str) -> str:
    """
    Backward-compatible wrapper returning the first / primary grounded excerpt text.
    """
    spans = extract_grounded_evidence_spans(chunk_text, answer_text)
    if not spans:
        return chunk_text[:250].strip() if chunk_text else ""
    return spans[0]["text"]


def optimize_citations(
    answer_text: str,
    chunks: List[Any],
    min_similarity: float = 0.25,
    max_citations: int = 4,
) -> List[DocumentChunk]:
    """
    Filter, clean, and deduplicate citation chunks to return ONLY necessary documents.
    
    Rules & Edge Cases:
    1. If the answer is a fallback or conversational reply -> returns []
    2. If explicit [Source N] tags were cited -> includes ONLY cited chunks in referenced order.
    3. If no explicit tags -> filters by lexical overlap and similarity, capping at max_citations.
    4. Deduplicates chunks by document_id + page_number so duplicate snippets are merged.
    5. Extracts ALL grounded evidence_spans matching the AI answer on the cited page.
    6. Re-indexes source_index starting from 1 with clean previews and safe defaults.
    """
    if not chunks:
        return []

    # 1. Negative / fallback response edge case
    if is_negative_or_conversational(answer_text):
        logger.info("Citation Optimizer: answer is negative or conversational fallback — returning 0 citations")
        return []

    # 2. Extract explicitly cited [Source N] tags from answer
    explicit_indices = extract_referenced_source_indices(answer_text, max_sources=len(chunks))
    
    selected_raw_chunks = []
    if explicit_indices:
        logger.info("Citation Optimizer: found explicit cited source indices: %s", sorted(list(explicit_indices)))
        for idx in sorted(list(explicit_indices)):
            if 0 <= idx - 1 < len(chunks):
                selected_raw_chunks.append((idx, chunks[idx - 1]))
    else:
        # 3. Fallback to smart relevance + overlap filtering
        logger.info("Citation Optimizer: no explicit tags — filtering by overlap and similarity")
        scored_chunks = []
        for i, chunk in enumerate(chunks, 1):
            chunk_text = getattr(chunk, "chunk_text", "") or getattr(chunk, "full_text", "") or ""
            score = getattr(chunk, "score", 0.0) or getattr(chunk, "similarity", 0.0) or 0.0
            overlap = calculate_text_overlap(chunk_text, answer_text)

            # Keep chunk if it has meaningful overlap or high vector similarity
            if overlap >= 0.12 or score >= min_similarity:
                combined_rank = (overlap * 0.6) + (score * 0.4)
                scored_chunks.append((combined_rank, i, chunk))

        # Sort by combined relevance descending and take top N
        scored_chunks.sort(key=lambda x: x[0], reverse=True)
        selected_raw_chunks = [(i, chunk) for (_, i, chunk) in scored_chunks[:max_citations]]

        # If nothing matched overlap criteria (e.g. general summary), keep top 1 highest score if score > threshold
        if not selected_raw_chunks and chunks:
            top_chunk = chunks[0]
            top_score = getattr(top_chunk, "score", 0.0) or getattr(top_chunk, "similarity", 0.0) or 0.0
            if top_score >= min_similarity:
                selected_raw_chunks = [(1, top_chunk)]

    if not selected_raw_chunks:
        return []

    # 4. Deduplication by document_id and page_number
    deduped_chunks = []
    seen_keys: Set[str] = set()

    for _, raw in selected_raw_chunks:
        doc_id = str(getattr(raw, "document_id", "") or "")
        page = getattr(raw, "page_number", None)
        if page is None:
            page = getattr(raw, "page", None)
        chunk_idx = getattr(raw, "chunk_index", 0)

        # Unique key: doc_id + page (or chunk_idx if no page)
        key = f"{doc_id}::p{page}" if page is not None else f"{doc_id}::c{chunk_idx}"

        if key in seen_keys:
            continue
        seen_keys.add(key)
        deduped_chunks.append(raw)

    # 5. Build clean, safe DocumentChunk models with exact evidence spans
    final_citations: List[DocumentChunk] = []
    for new_idx, c in enumerate(deduped_chunks, 1):
        doc_id = str(getattr(c, "document_id", "") or "")
        chunk_id = str(getattr(c, "chunk_id", "") or f"{doc_id}::chunk_{getattr(c, 'chunk_index', new_idx)}")
        file_name = str(getattr(c, "file_name", "") or "Document")
        category = str(getattr(c, "category", "") or "")
        chunk_idx = int(getattr(c, "chunk_index", 0) or 0)
        
        page_num = getattr(c, "page_number", None)
        if page_num is None:
            page_num = getattr(c, "page", None)
        if isinstance(page_num, str) and page_num.isdigit():
            page_num = int(page_num)
        elif not isinstance(page_num, int):
            page_num = None

        score = float(getattr(c, "score", 0.0) or getattr(c, "similarity", 0.0) or 0.0)
        full_text = str(getattr(c, "chunk_text", "") or getattr(c, "full_text", "") or "").strip()
        
        # Extract ALL grounded evidence spans supporting the answer
        grounded_spans = extract_grounded_evidence_spans(full_text, answer_text)
        evidence_span_models = [EvidenceSpan(**s) for s in grounded_spans]
        
        # Construct source_text and preview
        source_text = "\n".join(s["text"] for s in grounded_spans) if grounded_spans else full_text[:300].strip()
        preview = grounded_spans[0]["text"] if grounded_spans else full_text[:300].strip()
        
        scope = str(getattr(c, "scope", "company") or "company")
        user_id = getattr(c, "user_id", None)
        if user_id:
            user_id = str(user_id)

        final_citations.append(
            DocumentChunk(
                source_index=new_idx,
                document_id=doc_id,
                chunk_id=chunk_id,
                file_name=file_name,
                category=category,
                chunk_index=chunk_idx,
                page_number=page_num,
                similarity=round(score, 4),
                text_preview=preview,
                full_text=full_text,
                source_text=source_text,
                evidence_spans=evidence_span_models,
                scope=scope,
                user_id=user_id,
            )
        )

    logger.info(
        "Citation Optimizer: reduced %d candidate chunks down to %d necessary citations (with multi-evidence spans)",
        len(chunks), len(final_citations)
    )
    return final_citations
