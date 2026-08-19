"""Optional dependency availability for the search package."""

try:
    __import__("faiss")
except ImportError:
    SEARCH_AVAILABLE = False
else:
    SEARCH_AVAILABLE = True
