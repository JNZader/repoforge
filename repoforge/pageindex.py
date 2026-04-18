"""
PageIndex for RepoForge

Paginated repository analysis for small context models (4K-8K tokens).
Prevents compaction loops and enables granular access to large repo analysis.
"""

import sqlite3
import json
import re
from pathlib import Path
from typing import List, Dict, Optional, Any
from dataclasses import dataclass


@dataclass
class PageChunk:
    """A page chunk of repository analysis."""
    id: Optional[int]
    repo_id: str
    page_num: int
    total_pages: int
    content: str
    topics: List[str]
    file_refs: List[str]
    token_count: int
    prev_page_id: Optional[int] = None
    next_page_id: Optional[int] = None


@dataclass
class CompactionCheck:
    """Result of compaction check."""
    current_tokens: int
    max_tokens: int
    repo_id: str
    should_compact: bool
    safe_to_proceed: bool
    suggested_action: str  # 'compact', 'paginate', or 'none'


class PageIndex:
    """
    Manages paginated repository analysis.
    
    Enables small context models to handle large repo analysis
    by dividing content into navigable pages.
    """

    def __init__(self, db_path: str):
        """Initialize PageIndex with database path."""
        self.db_path = db_path
        self._init_schema()

    def _init_schema(self) -> None:
        """Initialize database schema."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Create pages table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS repo_pages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    repo_id TEXT NOT NULL,
                    page_num INTEGER NOT NULL,
                    total_pages INTEGER NOT NULL,
                    content TEXT NOT NULL,
                    topics TEXT,  -- JSON array
                    file_refs TEXT,  -- JSON array
                    token_count INTEGER NOT NULL,
                    prev_page_id INTEGER,
                    next_page_id INTEGER,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(repo_id, page_num)
                )
            """)
            
            # Create indexes
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_repo_pages_repo 
                ON repo_pages(repo_id)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_repo_pages_number 
                ON repo_pages(repo_id, page_num)
            """)
            
            conn.commit()

    def paginate_repo(self, repo_id: str, content: str, 
                     max_tokens_per_page: int = 1500,
                     overlap_tokens: int = 200) -> Dict[str, Any]:
        """
        Paginate repository analysis into chunks.
        
        Args:
            repo_id: Repository identifier
            content: Analysis content to paginate
            max_tokens_per_page: Maximum tokens per page (default: 1500)
            overlap_tokens: Tokens to overlap between pages (default: 200)
            
        Returns:
            Dict with 'pages' (count) and 'tokens' (total)
        """
        # Check if already paginated
        existing = self._get_existing_pages(repo_id)
        if existing:
            return {'pages': existing['pages'], 'tokens': existing['tokens']}

        # Chunk content
        chunks = self._chunk_content(content, max_tokens_per_page, overlap_tokens)
        total_pages = len(chunks)
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            page_ids = []
            
            for i, chunk in enumerate(chunks):
                page_num = i + 1
                topics = self.extract_topics(chunk)
                file_refs = self.extract_file_refs(chunk)
                token_count = self._estimate_tokens(chunk)
                
                cursor.execute("""
                    INSERT INTO repo_pages 
                    (repo_id, page_num, total_pages, content, topics, file_refs, token_count)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    repo_id, page_num, total_pages, chunk,
                    json.dumps(topics), json.dumps(file_refs), token_count
                ))
                
                page_ids.append(cursor.lastrowid)
            
            # Link pages
            for i, page_id in enumerate(page_ids):
                prev_id = page_ids[i - 1] if i > 0 else None
                next_id = page_ids[i + 1] if i < len(page_ids) - 1 else None
                
                cursor.execute("""
                    UPDATE repo_pages 
                    SET prev_page_id = ?, next_page_id = ?
                    WHERE id = ?
                """, (prev_id, next_id, page_id))
            
            conn.commit()

        total_tokens = sum(self._estimate_tokens(c) for c in chunks)
        return {'pages': total_pages, 'tokens': total_tokens}

    def _chunk_content(self, content: str, max_tokens: int, 
                      overlap: int) -> List[str]:
        """Split content into chunks with overlap."""
        max_chars = max_tokens * 4  # Approx 4 chars per token
        overlap_chars = overlap * 4
        
        chunks = []
        pos = 0
        
        while pos < len(content):
            end = min(pos + max_chars, len(content))
            
            if end < len(content):
                # Try to break at section boundary
                section_break = content.rfind('\n\n## ', pos, end)
                if section_break > pos + max_chars * 0.5:
                    end = section_break + 1
                else:
                    # Try paragraph break
                    para_break = content.rfind('\n\n', pos, end)
                    if para_break > pos + max_chars * 0.7:
                        end = para_break + 2
            
            chunks.append(content[pos:end].strip())
            pos = max(pos + 1, end - overlap_chars)
        
        return chunks if chunks else [content]

    def _estimate_tokens(self, text: str) -> int:
        """Estimate token count (1 token ≈ 4 chars)."""
        return max(1, len(text) // 4)

    def extract_topics(self, content: str) -> List[str]:
        """Extract topics from content (headers, bold text)."""
        topics = []
        
        # Headers (### Topic)
        headers = re.findall(r'^#{1,3}\s+(.+)$', content, re.MULTILINE)
        for h in headers[:5]:
            topics.append(h[:50])
        
        # Bold text
        if len(topics) < 10:
            bold = re.findall(r'\*\*(.+?)\*\*', content)
            for b in bold[:3]:
                topic = b[:50]
                if topic not in topics:
                    topics.append(topic)
        
        return topics[:8]

    def extract_file_refs(self, content: str) -> List[str]:
        """Extract file references from content."""
        refs = []
        
        # File paths
        paths = re.findall(r'(?:src/|apps/|packages/)[\w/\-]+\.\w+', content)
        for p in paths[:10]:
            if p not in refs:
                refs.append(p)
        
        # Glob patterns
        globs = re.findall(r'\*\*\/\*\.\w+', content)
        for g in globs[:5]:
            if g not in refs:
                refs.append(g)
        
        return refs[:15]

    def get_page(self, repo_id: str, page_num: int) -> Optional[Dict[str, Any]]:
        """Get a specific page by repository and page number."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, repo_id, page_num, total_pages, content, 
                       topics, file_refs, token_count, prev_page_id, next_page_id
                FROM repo_pages
                WHERE repo_id = ? AND page_num = ?
            """, (repo_id, page_num))
            
            row = cursor.fetchone()
            if not row:
                return None
            
            return {
                'id': row[0],
                'repo_id': row[1],
                'page_num': row[2],
                'total_pages': row[3],
                'content': row[4],
                'topics': json.loads(row[5] or '[]'),
                'file_refs': json.loads(row[6] or '[]'),
                'token_count': row[7],
                'prev_page_id': row[8],
                'next_page_id': row[9]
            }

    def get_context(self, repo_id: str, page_num: int, 
                   window_size: int = 1) -> Dict[str, Any]:
        """Get page with surrounding context."""
        start_page = max(1, page_num - window_size)
        end_page = page_num + window_size
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, repo_id, page_num, total_pages, content, 
                       topics, file_refs, token_count
                FROM repo_pages
                WHERE repo_id = ? AND page_num BETWEEN ? AND ?
                ORDER BY page_num
            """, (repo_id, start_page, end_page))
            
            pages = []
            for row in cursor.fetchall():
                pages.append({
                    'id': row[0],
                    'repo_id': row[1],
                    'page_num': row[2],
                    'total_pages': row[3],
                    'content': row[4],
                    'topics': json.loads(row[5] or '[]'),
                    'file_refs': json.loads(row[6] or '[]'),
                    'token_count': row[7]
                })
        
        current = next((p for p in pages if p['page_num'] == page_num), None)
        if not current:
            raise ValueError(f"Page {page_num} not found in repo {repo_id}")
        
        previous = [p for p in pages if p['page_num'] < page_num]
        next_pages = [p for p in pages if p['page_num'] > page_num]
        
        total_tokens = sum(p['token_count'] for p in pages)
        
        return {
            'current_page': current,
            'previous_pages': previous,
            'next_pages': next_pages,
            'total_in_context': len(pages),
            'total_tokens': total_tokens
        }

    def navigate(self, repo_id: str, current_page_num: int, 
                direction: str) -> Optional[Dict[str, Any]]:
        """Navigate to adjacent page."""
        if direction == 'next':
            return self.get_page(repo_id, current_page_num + 1)
        elif direction == 'prev':
            return self.get_page(repo_id, current_page_num - 1)
        elif direction == 'first':
            return self.get_page(repo_id, 1)
        elif direction == 'last':
            stats = self.get_repo_stats(repo_id)
            if stats['pages'] > 0:
                return self.get_page(repo_id, stats['pages'])
            return None
        else:
            return None

    def find_relevant_pages(self, repo_id: str, query: str, 
                          max_pages: int = 3) -> List[Dict[str, Any]]:
        """Find pages relevant to query."""
        keywords = [k.lower() for k in query.split() if len(k) > 2]
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, repo_id, page_num, total_pages, content, 
                       topics, file_refs, token_count
                FROM repo_pages
                WHERE repo_id = ?
                ORDER BY page_num
            """, (repo_id,))
            
            scored_pages = []
            for row in cursor.fetchall():
                page = {
                    'id': row[0],
                    'repo_id': row[1],
                    'page_num': row[2],
                    'total_pages': row[3],
                    'content': row[4],
                    'topics': json.loads(row[5] or '[]'),
                    'file_refs': json.loads(row[6] or '[]'),
                    'token_count': row[7]
                }
                
                # Score by keyword matches
                content_lower = (page['content'] + ' ' + 
                               ' '.join(page['topics'])).lower()
                score = sum(content_lower.count(kw) for kw in keywords)
                
                # Bonus for file reference matches
                file_matches = sum(1 for ref in page['file_refs'] 
                                 if any(kw in ref.lower() for kw in keywords))
                score += file_matches * 3
                
                if score > 0:
                    scored_pages.append((page, score))
        
        # Sort by score and return top N
        scored_pages.sort(key=lambda x: x[1], reverse=True)
        return [p for p, _ in scored_pages[:max_pages]]

    def check_compaction(self, repo_id: str, model_max_tokens: int,
                        safety_margin: float = 0.3) -> CompactionCheck:
        """Check if compaction is needed for model."""
        stats = self.get_repo_stats(repo_id)
        current_tokens = stats['tokens']
        threshold = model_max_tokens * (1 - safety_margin)
        
        should_compact = current_tokens > threshold
        
        return CompactionCheck(
            current_tokens=current_tokens,
            max_tokens=model_max_tokens,
            repo_id=repo_id,
            should_compact=should_compact,
            safe_to_proceed=not should_compact,
            suggested_action='paginate' if should_compact else 'none'
        )

    def get_repo_stats(self, repo_id: str) -> Dict[str, int]:
        """Get repository page statistics."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT COUNT(*), COALESCE(SUM(token_count), 0)
                FROM repo_pages
                WHERE repo_id = ?
            """, (repo_id,))
            
            row = cursor.fetchone()
            return {'pages': row[0], 'tokens': row[1]}

    def delete_repo_pages(self, repo_id: str) -> None:
        """Delete all pages for a repository."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM repo_pages WHERE repo_id = ?", (repo_id,))
            conn.commit()

    def _get_existing_pages(self, repo_id: str) -> Optional[Dict[str, int]]:
        """Check if repo already has pages."""
        stats = self.get_repo_stats(repo_id)
        if stats['pages'] > 0:
            return stats
        return None


# Convenience function
def create_page_index(db_path: str) -> PageIndex:
    """Create a PageIndex instance."""
    return PageIndex(db_path)
