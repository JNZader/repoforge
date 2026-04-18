"""
Tests for PageIndex module - RepoForge

TDD: Test-Driven Development for paginated repo analysis.
Enables small context models (4K-8K) to handle large repo analysis.

Run: pytest tests/test_pageindex.py -v
"""

import pytest
import tempfile
import sqlite3
from pathlib import Path


class TestPageIndex:
    """Test suite for PageIndex functionality."""

    @pytest.fixture
    def db_path(self):
        """Create temporary database for testing."""
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            path = f.name
        yield path
        # Cleanup
        Path(path).unlink(missing_ok=True)

    @pytest.fixture
    def page_index(self, db_path):
        """Create PageIndex instance with fresh database."""
        from repoforge.pageindex import PageIndex
        return PageIndex(db_path)

    def test_schema_initialization(self, page_index):
        """Test that database schema is created correctly."""
        # Verify tables exist
        conn = sqlite3.connect(page_index.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='repo_pages'
        """)
        result = cursor.fetchone()
        assert result is not None, "repo_pages table should exist"
        
        # Verify indexes exist
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='index' AND name LIKE 'idx_repo_pages_%'
        """)
        indexes = cursor.fetchall()
        assert len(indexes) >= 2, "Should have at least 2 indexes"
        
        conn.close()

    def test_paginate_repo_analysis(self, page_index):
        """Test paginating large repo analysis into chunks."""
        # Large analysis content
        analysis = """
        # Repository Analysis

        ## Project Structure
        Monorepo with apps/frontend and apps/backend.
        {'Text ' * 500}

        ## Dependencies  
        Uses React, TypeScript, and Node.js.
        {'Dependencies ' * 500}

        ## Architecture
        Clean architecture with domain layer.
        {'Architecture ' * 500}

        ## API Design
        RESTful APIs with OpenAPI spec.
        {'API ' * 500}
        """

        result = page_index.paginate_repo('test-repo', analysis)

        assert result['pages'] > 1, "Should create multiple pages"
        assert result['tokens'] > 0, "Should have total tokens"
        assert result['pages'] < 500, "Should not create excessive pages"

    def test_extract_topics(self, page_index):
        """Test topic extraction from content."""
        # Note: Headers should not have leading indentation
        content = """### Authentication Module
JWT-based authentication implementation.

### Database Schema  
PostgreSQL table definitions.
"""

        topics = page_index.extract_topics(content)

        assert len(topics) > 0, "Should extract topics"
        assert any('Authentication' in t or 'auth' in t.lower() for t in topics), \
            "Should find auth-related topic"

    def test_extract_file_refs(self, page_index):
        """Test file reference extraction."""
        content = """
        Implementation in src/auth/middleware.ts handles JWT.
        Database schema defined in src/db/schema.sql.
        Tests are in **/*.test.ts pattern.
        """

        file_refs = page_index.extract_file_refs(content)

        assert len(file_refs) > 0, "Should extract file references"
        assert any('src/auth/middleware.ts' in f for f in file_refs), \
            "Should find specific file"

    def test_get_page(self, page_index):
        """Test retrieving specific page."""
        # Setup: Create paginated content
        content = "Section 1\n" + "Text " * 300 + "\n\nSection 2\n" + "Text " * 300
        page_index.paginate_repo('get-page-repo', content)

        # Get page 1
        page1 = page_index.get_page('get-page-repo', 1)
        assert page1 is not None, "Page 1 should exist"
        assert page1['page_num'] == 1, "Should have correct page number"
        assert len(page1['content']) > 0, "Should have content"
        assert page1['topics'] is not None, "Should have topics"

    def test_get_page_nonexistent(self, page_index):
        """Test retrieving non-existent page returns None."""
        page = page_index.get_page('nonexistent-repo', 1)
        assert page is None, "Should return None for non-existent repo"

    def test_get_context_window(self, page_index):
        """Test getting page with surrounding context."""
        # Create multi-page content
        content = "\n\n".join([f"Section {i}\n{'Text ' * 400}" for i in range(1, 8)])
        page_index.paginate_repo('context-repo', content)

        # Get page 4 with window of 1
        context = page_index.get_context('context-repo', page_num=4, window_size=1)

        assert context['current_page']['page_num'] == 4, "Should return requested page"
        assert len(context['previous_pages']) == 1, "Should have 1 previous page"
        assert len(context['next_pages']) == 1, "Should have 1 next page"
        assert context['total_in_context'] == 3, "Should have 3 total pages"
        assert context['total_tokens'] > 0, "Should calculate total tokens"

    def test_get_context_boundaries_first_page(self, page_index):
        """Test context window at first page boundary."""
        content = "\n\n".join([f"Section {i}\n{'Text ' * 200}" for i in range(1, 5)])
        page_index.paginate_repo('first-boundary-repo', content)

        context = page_index.get_context('first-boundary-repo', page_num=1, window_size=1)

        assert len(context['previous_pages']) == 0, "First page has no previous"
        assert len(context['next_pages']) == 1, "Should have next page"
        assert context['total_in_context'] == 2, "Should have 2 pages"

    def test_get_context_boundaries_last_page(self, page_index):
        """Test context window at last page boundary."""
        content = "\n\n".join([f"Section {i}\n{'Text ' * 200}" for i in range(1, 5)])
        result = page_index.paginate_repo('last-boundary-repo', content)

        last_page = result['pages']
        context = page_index.get_context('last-boundary-repo', page_num=last_page, window_size=1)

        assert len(context['previous_pages']) == 1, "Should have previous page"
        assert len(context['next_pages']) == 0, "Last page has no next"

    def test_navigate_next(self, page_index):
        """Test navigating to next page."""
        content = "\n\n".join([f"Page {i}\n{'Text ' * 200}" for i in range(1, 6)])
        page_index.paginate_repo('nav-repo', content)

        next_page = page_index.navigate('nav-repo', current_page_num=2, direction='next')

        assert next_page is not None, "Should return next page"
        assert next_page['page_num'] == 3, "Should be page 3"

    def test_navigate_prev(self, page_index):
        """Test navigating to previous page."""
        content = "\n\n".join([f"Page {i}\n{'Text ' * 200}" for i in range(1, 6)])
        page_index.paginate_repo('nav-prev-repo', content)

        prev_page = page_index.navigate('nav-prev-repo', current_page_num=3, direction='prev')

        assert prev_page is not None, "Should return previous page"
        assert prev_page['page_num'] == 2, "Should be page 2"

    def test_navigate_first(self, page_index):
        """Test navigating to first page."""
        content = "\n\n".join([f"Page {i}\n{'Text ' * 200}" for i in range(1, 6)])
        page_index.paginate_repo('nav-first-repo', content)

        first = page_index.navigate('nav-first-repo', current_page_num=4, direction='first')

        assert first is not None, "Should return first page"
        assert first['page_num'] == 1, "Should be page 1"

    def test_navigate_last(self, page_index):
        """Test navigating to last page."""
        content = "\n\n".join([f"Page {i}\n{'Text ' * 200}" for i in range(1, 6)])
        result = page_index.paginate_repo('nav-last-repo', content)

        last = page_index.navigate('nav-last-repo', current_page_num=2, direction='last')

        assert last is not None, "Should return last page"
        assert last['page_num'] == result['pages'], "Should be last page"

    def test_navigate_boundaries(self, page_index):
        """Test navigation boundaries return None."""
        content = "\n\n".join([f"Page {i}\n{'Text ' * 200}" for i in range(1, 4)])
        result = page_index.paginate_repo('nav-boundary-repo', content)
        total_pages = result['pages']

        # Prev from first page
        prev = page_index.navigate('nav-boundary-repo', current_page_num=1, direction='prev')
        assert prev is None, "Prev from first should be None"

        # Next from last page
        next_page = page_index.navigate('nav-boundary-repo', current_page_num=total_pages, direction='next')
        assert next_page is None, "Next from last should be None"

    def test_find_relevant_pages_by_keywords(self, page_index):
        """Test finding pages matching keywords."""
        content = """
        ### Authentication System
        JWT tokens and session management.
        {'auth jwt security ' * 100}

        ### Database Layer  
        PostgreSQL connection pooling.
        {'database postgres sql ' * 100}

        ### API Layer
        REST endpoints and GraphQL.
        {'api rest graphql ' * 100}
        """
        page_index.paginate_repo('relevant-repo', content)

        relevant = page_index.find_relevant_pages(
            'relevant-repo',
            query='authentication jwt',
            max_pages=2
        )

        assert len(relevant) > 0, "Should find relevant pages"
        assert len(relevant) <= 2, "Should respect max_pages"
        # Check that at least one page has auth content
        assert any('auth' in p['content'].lower() or 
                   any('auth' in t.lower() for t in p['topics'])
                   for p in relevant), "Should find auth-related page"

    def test_find_relevant_pages_by_files(self, page_index):
        """Test finding pages matching file references."""
        content = """
        ### Middleware
        src/auth/middleware.ts handles JWT validation.
        {'middleware code ' * 100}

        ### Database  
        src/db/connection.ts manages pooling.
        {'database code ' * 100}
        """
        page_index.paginate_repo('files-repo', content)

        relevant = page_index.find_relevant_pages(
            'files-repo',
            query='src/auth/middleware.ts',
            max_pages=2
        )

        assert len(relevant) > 0, "Should find pages with file references"
        assert any('middleware.ts' in ' '.join(p['file_refs']) for p in relevant), \
            "Should find page with middleware.ts"

    def test_check_compaction_small_repo(self, page_index):
        """Test compaction check for small repo with small model."""
        content = "Small analysis."  # Small content
        page_index.paginate_repo('small-repo', content)

        check = page_index.check_compaction('small-repo', model_max_tokens=4096)

        assert check.should_compact is False, "Small repo should not need compaction"
        assert check.safe_to_proceed is True, "Should be safe to proceed"
        assert check.suggested_action == 'none', "Should suggest no action"

    def test_check_compaction_large_repo(self, page_index):
        """Test compaction check for large repo with small model."""
        # Create large content (~10K tokens)
        content = "Word " * 10000
        page_index.paginate_repo('large-repo', content)

        check = page_index.check_compaction('large-repo', model_max_tokens=4096)

        assert check.should_compact is True, "Large repo should need compaction"
        assert check.safe_to_proceed is False, "Should not be safe"
        assert check.suggested_action == 'paginate', "Should suggest pagination"
        assert check.current_tokens > 0, "Should have current tokens"
        assert check.max_tokens == 4096, "Should report max tokens"

    def test_get_repo_stats(self, page_index):
        """Test getting repository statistics."""
        content = "\n\n".join([f"Section {i}\n{'Text ' * 300}" for i in range(1, 6)])
        page_index.paginate_repo('stats-repo', content)

        stats = page_index.get_repo_stats('stats-repo')

        assert stats['pages'] > 0, "Should have page count"
        assert stats['tokens'] > 0, "Should have token count"
        # Large content may create many pages due to chunking algorithm

    def test_get_repo_stats_nonexistent(self, page_index):
        """Test getting stats for non-existent repo."""
        stats = page_index.get_repo_stats('nonexistent-repo')

        assert stats['pages'] == 0, "Should have 0 pages"
        assert stats['tokens'] == 0, "Should have 0 tokens"

    def test_delete_repo_pages(self, page_index):
        """Test deleting all pages for a repository."""
        content = "\n\n".join([f"Section {i}\n{'Text ' * 200}" for i in range(1, 4)])
        page_index.paginate_repo('delete-repo', content)

        # Verify pages exist
        stats_before = page_index.get_repo_stats('delete-repo')
        assert stats_before['pages'] > 0, "Should have pages before delete"

        # Delete pages
        page_index.delete_repo_pages('delete-repo')

        # Verify pages deleted
        stats_after = page_index.get_repo_stats('delete-repo')
        assert stats_after['pages'] == 0, "Should have 0 pages after delete"
        assert stats_after['tokens'] == 0, "Should have 0 tokens after delete"

    def test_integration_repo_analysis_workflow(self, page_index):
        """Integration test: Full repo analysis workflow with small model."""
        # Step 1: Large repo analysis (simulated)
        analysis = "\n\n".join([
            f"## {topic}\n{'Content ' * 600}"
            for topic in [
                'Architecture', 'Authentication', 'Database', 
                'API Design', 'Testing', 'Deployment', 'Security'
            ]
        ])

        # Step 2: Paginate
        result = page_index.paginate_repo('integration-repo', analysis)
        assert result['pages'] >= 7, "Should create multiple pages"

        # Step 3: Check compaction for 4K model
        check = page_index.check_compaction('integration-repo', model_max_tokens=4096)
        assert check.should_compact is True, "Should need compaction"

        # Step 4: Find relevant pages for auth-related query
        relevant = page_index.find_relevant_pages(
            'integration-repo',
            query='authentication security jwt',
            max_pages=3
        )
        assert len(relevant) > 0, "Should find relevant pages"

        # Step 5: Build context within token budget
        total_tokens = 0
        max_input_tokens = 4096 * 0.6  # 60% for input
        context_pages = []

        for page in relevant:
            if total_tokens + page['token_count'] > max_input_tokens:
                break
            context_pages.append(page)
            total_tokens += page['token_count']

        assert total_tokens < max_input_tokens, "Should stay within budget"
        assert len(context_pages) > 0, "Should have at least one page"

        # Step 6: Can navigate for more context if needed
        last_page = context_pages[-1]
        next_page = page_index.navigate(
            'integration-repo',
            current_page_num=last_page['page_num'],
            direction='next'
        )
        assert next_page is not None or last_page['page_num'] == result['pages'], \
            "Should be able to navigate or at last page"

    def test_multiple_model_sizes(self, page_index):
        """Test compaction checks for different model sizes."""
        # Very small content that fits in all models
        tiny_content = "Small analysis."
        page_index.paginate_repo('tiny-repo', tiny_content)

        # 4K model - should not need compaction
        small = page_index.check_compaction('tiny-repo', 4096)
        assert small.should_compact is False, "Tiny repo with 4K should not need compaction"
        assert small.safe_to_proceed is True

        # 32K model - should not need compaction
        large = page_index.check_compaction('tiny-repo', 32768)
        assert large.should_compact is False, "Tiny repo with 32K should not need compaction"
        assert large.safe_to_proceed is True
