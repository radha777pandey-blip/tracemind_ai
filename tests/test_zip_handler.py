import io
import zipfile
import pytest
from pathlib import Path
from tracemind.ingestion.zip_handler import safe_extract_zip

def test_safe_extract_zip(tmp_path):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w') as zf:
        zf.writestr('myrepo/main.py', 'print("hello")\n')
        zf.writestr('myrepo/utils.py', 'def helper(): pass\n')
        zf.writestr('myrepo/.git/config', 'git data')
        zf.writestr('myrepo/node_modules/pkg/index.js', 'console.log("module")')

    extract_dest = tmp_path / 'extracted'
    root_dir = safe_extract_zip(buf.getvalue(), str(extract_dest))

    root_path = Path(root_dir)
    assert (root_path / 'main.py').exists()
    assert (root_path / 'utils.py').exists()
    assert not (root_path / '.git').exists()
    assert not (root_path / 'node_modules').exists()

def test_path_traversal_rejection(tmp_path):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w') as zf:
        zf.writestr('../evil.py', 'malicious code')

    with pytest.raises(ValueError, match="Potentially malicious ZIP entry"):
        safe_extract_zip(buf.getvalue(), str(tmp_path / 'extracted'))

def test_empty_zip_rejection(tmp_path):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w') as zf:
        pass

    with pytest.raises(ValueError, match="The uploaded ZIP archive is empty"):
        safe_extract_zip(buf.getvalue(), str(tmp_path / 'extracted'))
