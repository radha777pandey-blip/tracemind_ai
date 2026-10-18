import pytest
from pathlib import Path
from tracemind.ingestion.scanner import CodebaseScanner

def test_scanner_directory(tmp_path):
    # Setup test files
    (tmp_path / 'main.py').write_text('print("hello world")\n', encoding='utf-8')
    (tmp_path / 'utils.js').write_text('export function add(a, b) { return a + b; }\n', encoding='utf-8')
    (tmp_path / 'README.md').write_text('# Test Repo\n', encoding='utf-8')
    
    # Ignored directory and files
    git_dir = tmp_path / '.git'
    git_dir.mkdir()
    (git_dir / 'config').write_text('git config', encoding='utf-8')
    
    node_dir = tmp_path / 'node_modules'
    node_dir.mkdir()
    (node_dir / 'package.json').write_text('{}', encoding='utf-8')
    
    cache_dir = tmp_path / '__pycache__'
    cache_dir.mkdir()
    (cache_dir / 'main.cpython-314.pyc').write_bytes(b'binary bytecode')
    
    # Binary file in root
    (tmp_path / 'image.png').write_bytes(b'\x89PNG\r\n\x1a\n\x00\x00')

    scanner = CodebaseScanner()
    scanned = scanner.scan_directory(str(tmp_path))

    paths = {f.relative_path for f in scanned}
    assert 'main.py' in paths
    assert 'utils.js' in paths
    assert 'README.md' in paths
    assert not any(p.startswith('.git') for p in paths)
    assert not any(p.startswith('node_modules') for p in paths)
    assert not any('__pycache__' in p for p in paths)
    assert not any(p.endswith('.png') for p in paths)

    main_f = next(f for f in scanned if f.relative_path == 'main.py')
    assert main_f.language == 'python'
    assert main_f.line_count == 1
    assert len(main_f.file_hash) == 64
