"""
SymbolIndex — fast in-memory index for symbol lookups.

Provides O(1) lookups by name, qualified name (file::name), and file path.
Supports cross-file resolution with import-aware disambiguation.
"""

from __future__ import annotations

from collections import defaultdict

from .extractor import Symbol


class SymbolIndex:
    """In-memory index for fast symbol lookups.

    Stores symbols indexed three ways:
    - By name: str -> list[Symbol] (all symbols with that name across files)
    - By qualified name: "file::name" -> Symbol (unique per file)
    - By file: str -> list[Symbol] (all symbols in a file)
    """

    __slots__ = ("_by_name", "_by_qualified", "_by_file")

    def __init__(
        self,
        by_name: dict[str, list[Symbol]],
        by_qualified: dict[str, Symbol],
        by_file: dict[str, list[Symbol]],
    ) -> None:
        self._by_name = by_name
        self._by_qualified = by_qualified
        self._by_file = by_file

    @classmethod
    def from_symbols(cls, symbols: list[Symbol]) -> SymbolIndex:
        """Build an index from a flat list of symbols.

        Args:
            symbols: List of Symbol instances to index.

        Returns:
            A new SymbolIndex with all three lookup maps populated.
        """
        by_name: dict[str, list[Symbol]] = defaultdict(list)
        by_qualified: dict[str, Symbol] = {}
        by_file: dict[str, list[Symbol]] = defaultdict(list)

        for sym in symbols:
            by_name[sym.name].append(sym)
            by_qualified[sym.id] = sym  # file::name
            by_file[sym.file].append(sym)

        return cls(
            by_name=dict(by_name),
            by_qualified=by_qualified,
            by_file=dict(by_file),
        )

    # ------------------------------------------------------------------
    # Lookup methods
    # ------------------------------------------------------------------

    def by_name(self, name: str) -> list[Symbol]:
        """All symbols with the given name (across all files).

        Args:
            name: Symbol name to search for.

        Returns:
            List of matching symbols. Empty list if none found.
        """
        return self._by_name.get(name, [])

    def by_qualified(self, file: str, name: str) -> Symbol | None:
        """Lookup a symbol by its qualified name (file::name).

        Args:
            file: Relative file path.
            name: Symbol name.

        Returns:
            The Symbol if found, None otherwise.
        """
        return self._by_qualified.get(f"{file}::{name}")

    def by_file(self, file: str) -> list[Symbol]:
        """All symbols defined in the given file.

        Args:
            file: Relative file path.

        Returns:
            List of symbols in that file. Empty list if none found.
        """
        return self._by_file.get(file, [])

    def resolve(
        self,
        name: str,
        from_file: str,
        imports: dict[str, str] | None = None,
    ) -> Symbol | None:
        """Resolve a symbol name with context-aware disambiguation.

        Resolution order:
        1. Same-file: symbol defined in from_file with matching name
        2. Imported: if imports maps name -> source_file, look up source_file::name
        3. Unique global: if exactly one symbol has this name across all files
        4. None: ambiguous or not found

        Args:
            name: Symbol name to resolve.
            from_file: File where the reference occurs.
            imports: Optional mapping of imported name -> source file path.

        Returns:
            The resolved Symbol, or None if not found / ambiguous.
        """
        # 1. Same-file match
        same_file = self.by_qualified(from_file, name)
        if same_file is not None:
            return same_file

        # 2. Import-based match
        if imports and name in imports:
            source_file = imports[name]
            imported = self.by_qualified(source_file, name)
            if imported is not None:
                return imported

        # 3. Unique global name
        candidates = self._by_name.get(name, [])
        if len(candidates) == 1:
            return candidates[0]

        # Ambiguous or not found
        return None

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def symbol_count(self) -> int:
        """Total number of indexed symbols."""
        return len(self._by_qualified)

    @property
    def file_count(self) -> int:
        """Number of distinct files with symbols."""
        return len(self._by_file)
