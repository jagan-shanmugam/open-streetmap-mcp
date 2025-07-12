# Tests for OSM MCP Server

This directory contains tests for the OpenStreetMap MCP Server, specifically focusing on the `search_category` functionality fix.

## Overview

The tests verify that the fix for the search_category bug works correctly. The original issue was that subcategories were causing 400 errors due to incorrect Overpass query syntax.

## What was fixed

**Before (incorrect syntax):**
```python
subcategory_filters = " or ".join([f'"{category}"="{sub}"' for sub in subcategories])
query_filter = f'({subcategory_filters})'
# Generated: ("amenity"="restaurant" or "amenity"="cafe" or "amenity"="bar")
```

**After (correct syntax):**
```python
subcategory_pattern = "|".join(subcategories)
query_filter = f'"{category}"~"^({subcategory_pattern})$"'
# Generated: "amenity"~"^(restaurant|cafe|bar)$"
```

## Test Cases

### `test_search_category.py`

This file contains comprehensive tests for the `search_features_by_category` method:

1. **`test_search_features_by_category_with_subcategories`**
   - Tests that subcategories generate correct Overpass query syntax
   - Verifies the regex pattern `"amenity"~"^(restaurant|cafe|bar)$"` is used
   - Checks that the query structure is valid

2. **`test_search_features_by_category_without_subcategories`**
   - Tests queries without subcategories work correctly
   - Verifies simple category filter `"amenity"` is used
   - Ensures no regex pattern is used

3. **`test_search_features_by_category_error_handling`**
   - Tests error handling when the API returns an error
   - Verifies appropriate exceptions are raised

4. **`test_search_features_by_category_single_subcategory`**
   - Tests with a single subcategory
   - Ensures regex pattern is correct for single items

5. **`test_query_syntax_examples`**
   - Unit tests for the query syntax logic
   - Verifies different scenarios produce correct patterns

## Running the Tests

### Simple Test (Recommended)

Run the simple query generation test that doesn't require additional dependencies:

```bash
# From the project root
python3 tests/test_query_generation.py
```

This test verifies the core fix without requiring the full MCP server setup.

### Full Test Suite (Requires Dependencies)

If you want to run the full test suite with mocking:

#### Prerequisites

Install the required dependencies:

```bash
pip install pytest pytest-asyncio
```

#### Run all tests

```bash
# From the project root
python -m pytest tests/ -v

# Or run the specific test file
python -m pytest tests/test_search_category.py -v
```

#### Run individual test

```bash
python -m pytest tests/test_search_category.py::TestSearchCategory::test_search_features_by_category_with_subcategories -v
```

## Expected Output

When the simple test passes, you should see output like:

```
🧪 OSM MCP Server Query Generation Tests
==================================================
🧪 Testing query generation logic
========================================
✅ Test 1: PASSED
   Category: amenity
   Subcategories: ['restaurant', 'cafe', 'bar']
   Generated: "amenity"~"^(restaurant|cafe|bar)$"

✅ Test 2: PASSED
   Category: shop
   Subcategories: ['supermarket']
   Generated: "shop"~"^(supermarket)$"

✅ Test 3: PASSED
   Category: tourism
   Subcategories: ['hotel', 'hostel', 'motel']
   Generated: "tourism"~"^(hotel|hostel|motel)$"

✅ Test 4: PASSED
   Category: amenity
   Subcategories: None
   Generated: "amenity"

✅ Test 5: PASSED
   Category: leisure
   Subcategories: []
   Generated: "leisure"

========================================
🎉 All tests passed! The query generation fix is working correctly.
```

When the full test suite passes, you should see output like:

```
tests/test_search_category.py::TestSearchCategory::test_search_features_by_category_with_subcategories PASSED
tests/test_search_category.py::TestSearchCategory::test_search_features_by_category_without_subcategories PASSED
tests/test_search_category.py::TestSearchCategory::test_search_features_by_category_error_handling PASSED
tests/test_search_category.py::TestSearchCategory::test_search_features_by_category_single_subcategory PASSED
tests/test_search_category.py::TestSearchCategory::test_query_syntax_examples PASSED
```

## Manual Testing

You can also test the fix manually by running the server and using the `search_category` tool:

```python
# Example usage
{
  "category": "amenity",
  "min_latitude": 37.7749,
  "min_longitude": -122.4194,
  "max_latitude": 37.7850,
  "max_longitude": -122.4000,
  "subcategories": ["restaurant", "cafe", "bar"]
}
```

This should now work without returning 400 errors.

## Overpass Query Examples

The fix ensures that queries are generated in the correct Overpass syntax:

**For multiple subcategories:**
```
[out:json];
(
  node["amenity"~"^(restaurant|cafe|bar)$"](37.7749,-122.4194,37.7850,-122.4);
  way["amenity"~"^(restaurant|cafe|bar)$"](37.7749,-122.4194,37.7850,-122.4);
  relation["amenity"~"^(restaurant|cafe|bar)$"](37.7749,-122.4194,37.7850,-122.4);
);
out body;
```

**For single subcategory:**
```
[out:json];
(
  node["shop"~"^(supermarket)$"](37.7749,-122.4194,37.7850,-122.4);
  way["shop"~"^(supermarket)$"](37.7749,-122.4194,37.7850,-122.4);
  relation["shop"~"^(supermarket)$"](37.7749,-122.4194,37.7850,-122.4);
);
out body;
```

**For no subcategories:**
```
[out:json];
(
  node["amenity"](37.7749,-122.4194,37.7850,-122.4);
  way["amenity"](37.7749,-122.4194,37.7850,-122.4);
  relation["amenity"](37.7749,-122.4194,37.7850,-122.4);
);
out body;
```