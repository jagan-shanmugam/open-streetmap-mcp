"""
Test cases for the search_category functionality.

This module tests the fix for the search_category bug where subcategories
were causing 400 errors due to incorrect Overpass query syntax.
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch
from typing import List, Dict, Any

# Import the OSMClient class
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from osm_mcp_server.server import OSMClient


class TestSearchCategory:
    """Test cases for search_category functionality."""
    
    @pytest.fixture
    def osm_client(self):
        """Create a mock OSM client for testing."""
        client = OSMClient()
        client.session = AsyncMock()
        return client
    
    @pytest.mark.asyncio
    async def test_search_features_by_category_with_subcategories(self, osm_client):
        """Test that subcategories generate correct Overpass query syntax."""
        
        # Mock successful response
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={"elements": []})
        
        osm_client.session.post.return_value.__aenter__.return_value = mock_response
        
        # Test parameters
        bbox = (-122.4194, 37.7749, -122.4000, 37.7850)  # San Francisco area
        category = "amenity"
        subcategories = ["restaurant", "cafe", "bar"]
        
        # Call the method
        result = await osm_client.search_features_by_category(bbox, category, subcategories)
        
        # Verify the query was called
        osm_client.session.post.assert_called_once()
        
        # Get the actual query that was sent
        call_args = osm_client.session.post.call_args
        query_data = call_args[1]["data"]
        
        # Verify the query contains the correct regex pattern
        expected_pattern = '"amenity"~"^(restaurant|cafe|bar)$"'
        assert expected_pattern in query_data, f"Expected pattern not found in query: {query_data}"
        
        # Verify the query structure is correct
        assert "[out:json];" in query_data
        assert "node[" in query_data
        assert "way[" in query_data
        assert "relation[" in query_data
        assert "out body;" in query_data
        
        # Verify the bounding box coordinates are correct
        assert "37.7749,-122.4194,37.7850,-122.4" in query_data
        
        # Verify the result is a list
        assert isinstance(result, list)
    
    @pytest.mark.asyncio
    async def test_search_features_by_category_without_subcategories(self, osm_client):
        """Test that queries without subcategories work correctly."""
        
        # Mock successful response
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={"elements": []})
        
        osm_client.session.post.return_value.__aenter__.return_value = mock_response
        
        # Test parameters
        bbox = (-122.4194, 37.7749, -122.4000, 37.7850)
        category = "amenity"
        subcategories = None
        
        # Call the method
        result = await osm_client.search_features_by_category(bbox, category, subcategories)
        
        # Get the actual query that was sent
        call_args = osm_client.session.post.call_args
        query_data = call_args[1]["data"]
        
        # Verify the query uses simple category filter
        expected_filter = '"amenity"'
        assert expected_filter in query_data, f"Expected filter not found in query: {query_data}"
        
        # Verify no regex pattern is used
        assert "~" not in query_data
        
        # Verify the result is a list
        assert isinstance(result, list)
    
    @pytest.mark.asyncio
    async def test_search_features_by_category_error_handling(self, osm_client):
        """Test error handling when the API returns an error."""
        
        # Mock error response
        mock_response = AsyncMock()
        mock_response.status = 400
        
        osm_client.session.post.return_value.__aenter__.return_value = mock_response
        
        # Test parameters
        bbox = (-122.4194, 37.7749, -122.4000, 37.7850)
        category = "amenity"
        subcategories = ["restaurant"]
        
        # Verify that an exception is raised
        with pytest.raises(Exception) as exc_info:
            await osm_client.search_features_by_category(bbox, category, subcategories)
        
        assert "Failed to search features by category: 400" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_search_features_by_category_single_subcategory(self, osm_client):
        """Test with a single subcategory to ensure regex pattern is correct."""
        
        # Mock successful response
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={"elements": []})
        
        osm_client.session.post.return_value.__aenter__.return_value = mock_response
        
        # Test parameters
        bbox = (-122.4194, 37.7749, -122.4000, 37.7850)
        category = "shop"
        subcategories = ["supermarket"]
        
        # Call the method
        result = await osm_client.search_features_by_category(bbox, category, subcategories)
        
        # Get the actual query that was sent
        call_args = osm_client.session.post.call_args
        query_data = call_args[1]["data"]
        
        # Verify the query contains the correct regex pattern for single subcategory
        expected_pattern = '"shop"~"^(supermarket)$"'
        assert expected_pattern in query_data, f"Expected pattern not found in query: {query_data}"
        
        # Verify the result is a list
        assert isinstance(result, list)
    
    def test_query_syntax_examples(self):
        """Test that the query syntax examples match the expected format."""
        
        # Example 1: Multiple subcategories
        subcategories = ["restaurant", "cafe", "bar"]
        category = "amenity"
        subcategory_pattern = "|".join(subcategories)
        query_filter = f'"{category}"~"^({subcategory_pattern})$"'
        
        expected = '"amenity"~"^(restaurant|cafe|bar)$"'
        assert query_filter == expected
        
        # Example 2: Single subcategory
        subcategories = ["supermarket"]
        category = "shop"
        subcategory_pattern = "|".join(subcategories)
        query_filter = f'"{category}"~"^({subcategory_pattern})$"'
        
        expected = '"shop"~"^(supermarket)$"'
        assert query_filter == expected
        
        # Example 3: No subcategories
        subcategories = None
        category = "amenity"
        if subcategories:
            subcategory_pattern = "|".join(subcategories)
            query_filter = f'"{category}"~"^({subcategory_pattern})$"'
        else:
            query_filter = f'"{category}"'
        
        expected = '"amenity"'
        assert query_filter == expected


if __name__ == "__main__":
    # Run the tests
    pytest.main([__file__, "-v"])