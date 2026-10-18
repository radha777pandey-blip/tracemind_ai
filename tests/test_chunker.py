import pytest
from tracemind.ingestion.parser import ParsedEntity
from tracemind.ingestion.chunker import StructureAwareChunker

def test_structure_aware_chunking():
    code = '''import os
import sys

def add(a, b):
    """Add two numbers."""
    return a + b

def multiply(a, b):
    """Multiply two numbers."""
    return a * b
'''
    entities = [
        ParsedEntity(
            entity_type='function',
            name='add',
            qualified_name='math.add',
            start_line=4,
            end_line=6,
            signature='def add(a, b)',
            docstring='Add two numbers.'
        ),
        ParsedEntity(
            entity_type='function',
            name='multiply',
            qualified_name='math.multiply',
            start_line=8,
            end_line=10,
            signature='def multiply(a, b)',
            docstring='Multiply two numbers.'
        )
    ]

    chunker = StructureAwareChunker(max_chunk_lines=20)
    chunks = chunker.chunk_file('math.py', code, entities)

    assert len(chunks) == 3  # module_header, add, multiply
    
    # 1. Header chunk
    assert chunks[0].entity_name == 'module_header'
    assert 'import os' in chunks[0].content
    assert chunks[0].start_line == 1

    # 2. add chunk
    assert chunks[1].entity_name == 'add'
    assert 'def add' in chunks[1].content
    assert chunks[1].start_line == 4
    assert chunks[1].end_line == 6

    # 3. multiply chunk
    assert chunks[2].entity_name == 'multiply'
    assert 'def multiply' in chunks[2].content
    assert chunks[2].start_line == 8
    assert chunks[2].end_line == 10

def test_fallback_chunking():
    plain_text = '\n'.join([f'line {i}' for i in range(1, 101)])
    chunker = StructureAwareChunker(max_chunk_lines=30, overlap_lines=5)
    chunks = chunker.chunk_file('data.txt', plain_text, entities=[])

    assert len(chunks) > 1
    assert chunks[0].start_line == 1
    assert 'line 1' in chunks[0].content

