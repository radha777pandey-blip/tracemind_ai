import logging
from dataclasses import dataclass
from typing import List, Optional
from tracemind.ingestion.parser import ParsedEntity

logger = logging.getLogger(__name__)

@dataclass
class CodeChunk:
    chunk_index: int
    content: str
    start_line: int
    end_line: int
    entity_name: Optional[str] = None
    entity_type: Optional[str] = None

class StructureAwareChunker:
    def __init__(self, max_chunk_lines: int = 60, overlap_lines: int = 10):
        self.max_chunk_lines = max_chunk_lines
        self.overlap_lines = overlap_lines

    def chunk_file(
        self,
        file_path: str,
        content: str,
        entities: Optional[List[ParsedEntity]] = None
    ) -> List[CodeChunk]:
        lines = content.splitlines()
        total_lines = len(lines)
        if total_lines == 0:
            return []

        chunks: List[CodeChunk] = []
        chunk_idx = 0

        # If we have structured entities (functions, classes, methods)
        if entities and len(entities) > 0:
            # Sort entities by start_line
            sorted_entities = sorted(entities, key=lambda e: e.start_line)

            # 1. Header / Module imports chunk if before the first entity
            first_entity_start = sorted_entities[0].start_line
            if first_entity_start > 1:
                header_lines = lines[:first_entity_start - 1]
                header_text = "\n".join(header_lines).strip()
                if header_text:
                    chunks.append(CodeChunk(
                        chunk_index=chunk_idx,
                        content=header_text,
                        start_line=1,
                        end_line=first_entity_start - 1,
                        entity_name="module_header",
                        entity_type="module"
                    ))
                    chunk_idx += 1

            # 2. Extract chunk for each top-level entity or standalone method
            # Filter to avoid duplicate chunks if methods are already inside class
            # Prefer function and method chunks as the most queryable units
            covered_ranges = set()

            for entity in sorted_entities:
                s_line = max(1, entity.start_line)
                e_line = min(total_lines, entity.end_line)
                
                # Check if this range is already covered or too short
                entity_lines = lines[s_line - 1:e_line]
                entity_text = "\n".join(entity_lines).strip()
                if not entity_text:
                    continue

                # If entity is too long, split it with overlap
                if len(entity_lines) > self.max_chunk_lines:
                    step = self.max_chunk_lines - self.overlap_lines
                    for sub_start in range(0, len(entity_lines), step):
                        sub_end = min(sub_start + self.max_chunk_lines, len(entity_lines))
                        sub_text = "\n".join(entity_lines[sub_start:sub_end]).strip()
                        if sub_text:
                            chunks.append(CodeChunk(
                                chunk_index=chunk_idx,
                                content=sub_text,
                                start_line=s_line + sub_start,
                                end_line=s_line + sub_end - 1,
                                entity_name=entity.name,
                                entity_type=entity.entity_type
                            ))
                            chunk_idx += 1
                        if sub_end == len(entity_lines):
                            break
                else:
                    chunks.append(CodeChunk(
                        chunk_index=chunk_idx,
                        content=entity_text,
                        start_line=s_line,
                        end_line=e_line,
                        entity_name=entity.name,
                        entity_type=entity.entity_type
                    ))
                    chunk_idx += 1

            if chunks:
                return chunks

        # Fallback: sliding window chunking by lines with overlap
        step = max(1, self.max_chunk_lines - self.overlap_lines)
        for start_idx in range(0, total_lines, step):
            end_idx = min(start_idx + self.max_chunk_lines, total_lines)
            chunk_text = "\n".join(lines[start_idx:end_idx]).strip()
            if chunk_text:
                chunks.append(CodeChunk(
                    chunk_index=chunk_idx,
                    content=chunk_text,
                    start_line=start_idx + 1,
                    end_line=end_idx,
                    entity_name=None,
                    entity_type="text_block"
                ))
                chunk_idx += 1
            if end_idx == total_lines:
                break

        return chunks
