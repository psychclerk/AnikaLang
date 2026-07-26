from .errors import FMS_Error

# Document handle registry for DOCX and PPTX operations
_doc_handles = {}
_doc_next_id = 1

def _register_doc(doc_obj):
    """Register a document object and return its handle ID."""
    global _doc_next_id
    handle = _doc_next_id
    _doc_next_id += 1
    _doc_handles[handle] = doc_obj
    return handle

def _get_doc(handle):
    """Get document object by handle ID."""
    handle = int(handle)
    if handle not in _doc_handles:
        raise FMS_Error(f"Invalid document handle: {handle}. Document may have been closed.", error_type="Runtime Error")
    return _doc_handles[handle]

def _close_doc(handle):
    """Remove document from registry."""
    handle = int(handle)
    if handle in _doc_handles:
        del _doc_handles[handle]

def _path_to_file_url(path):
    """Convert a Windows/Unix path to a proper file:// URL for use in HTML/WebViews."""
    if not path:
        return ""
    # Normalize path separators
    normalized = path.replace("\\", "/")
    # Ensure it ends with / if it's a directory
    if os.path.isdir(path) and not normalized.endswith("/"):
        normalized += "/"
    # Add file:// prefix
    if not normalized.startswith("file://"):
        normalized = "file:///" + normalized.lstrip("/")
    return normalized