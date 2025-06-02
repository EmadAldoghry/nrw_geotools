import sys
import io
import contextlib
import re

@contextlib.contextmanager
def suppress_stdout_stderr():
    original_stdout, original_stderr = sys.stdout, sys.stderr
    sys.stdout, sys.stderr = io.StringIO(), io.StringIO()
    try:
        yield
    finally:
        sys.stdout, sys.stderr = original_stdout, original_stderr

def sanitize_filename(filename_base):
    sane_filename_base = re.sub(r'[^\w\-_.]+', '_', filename_base)
    sane_filename_base = re.sub(r'_+', '_', sane_filename_base).strip('_')
    if not sane_filename_base:
        sane_filename_base = "output_features" # Default if empty after sanitize
    return sane_filename_base