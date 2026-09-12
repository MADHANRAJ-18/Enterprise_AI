from __future__ import annotations

import logging

import os

from dataclasses import dataclass

from typing import List, Optional

logger = logging.getLogger(__name__)

CHUNK_SIZE = int(os.getenv("CHUNK_SIZE", "800"))

CHUNK_OVERLAP = int(os.getenv("CHUNK_OVERLAP", "150"))

@dataclass

class ChunkData:
    chunk_index: int

    chunk_text: str

    char_start: int

    char_end: int

    token_count: int

    page_number: Optional[int]

def chunk_text(

    text: str,

    chunk_size: int = CHUNK_SIZE,

    chunk_overlap: int = CHUNK_OVERLAP,

    page_map: Optional[List[tuple]] = None,

) -> List[ChunkData]:
    if not text or not text.strip():
        raise ValueError("Cannot chunk empty text.")

    try:
        from langchain_text_splitters import RecursiveCharacterTextSplitter

    except ImportError:
        try:
            from langchain.text_splitter import RecursiveCharacterTextSplitter

        except ImportError:
            raise ImportError(

                "langchain-text-splitters is required for chunking. "

                "Run: pip install langchain-text-splitters"

            )

    splitter = RecursiveCharacterTextSplitter(

        chunk_size=chunk_size,

        chunk_overlap=chunk_overlap,

        length_function=len,

        separators=["\n\n", "\n", ". ", "! ", "? ", "; ", ", ", " ", ""],

    )

    raw_chunks: List[str] = splitter.split_text(text)

    chunks: List[ChunkData] = []

    search_start = 0

    for idx, chunk_text_str in enumerate(raw_chunks):
        if not chunk_text_str.strip():
            continue

        char_start = text.find(chunk_text_str, search_start)

        if char_start == -1:
            char_start = max(0, search_start)

        char_end = char_start + len(chunk_text_str)

        search_start = max(search_start, char_start + max(1, len(chunk_text_str) - chunk_overlap))

        page_number = _get_page_number(char_start, page_map)

        token_count = max(1, len(chunk_text_str) // 4)

        chunks.append(ChunkData(

            chunk_index=idx,

            chunk_text=chunk_text_str.strip(),

            char_start=char_start,

            char_end=char_end,

            token_count=token_count,

            page_number=page_number,

        ))

    logger.info(

        "Chunked: %d chars → %d chunks (size=%d, overlap=%d)",

        len(text), len(chunks), chunk_size, chunk_overlap,

    )

    return chunks

def _get_page_number(

    char_offset: int,

    page_map: Optional[List[tuple]],

) -> Optional[int]:
    if not page_map:
        return None

    page_number = page_map[0][1]

    for offset, pg in page_map:
        if char_offset >= offset:
            page_number = pg

        else:
            break

    return page_number

def build_page_map(pages: list) -> List[tuple]:
    page_map: List[tuple] = []

    offset = 0

    for page_info in pages:
        page_map.append((offset, page_info.page_number))

        offset += len(page_info.text) + 2

    return page_map
