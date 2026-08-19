"""Optional dependency availability for the intelligence package."""

try:
    __import__("tree_sitter")
except ImportError:
    INTELLIGENCE_AVAILABLE = False
else:
    INTELLIGENCE_AVAILABLE = True
