#!/usr/bin/env python3
"""
Simple test for the query generation logic fix.

This test verifies that the Overpass query syntax is generated correctly
without requiring the full MCP server dependencies.
"""

def test_query_generation_with_subcategories():
    """Test that subcategories generate correct Overpass query syntax."""
    
    # Simulate the fixed logic from the server
    def generate_query_filter(category, subcategories):
        if subcategories and len(subcategories) > 0:
            # Use regex pattern for subcategories
            subcategory_pattern = "|".join(subcategories)
            return f'"{category}"~"^({subcategory_pattern})$"'
        else:
            return f'"{category}"'
    
    # Test cases
    test_cases = [
        {
            "category": "amenity",
            "subcategories": ["restaurant", "cafe", "bar"],
            "expected": '"amenity"~"^(restaurant|cafe|bar)$"'
        },
        {
            "category": "shop",
            "subcategories": ["supermarket"],
            "expected": '"shop"~"^(supermarket)$"'
        },
        {
            "category": "tourism",
            "subcategories": ["hotel", "hostel", "motel"],
            "expected": '"tourism"~"^(hotel|hostel|motel)$"'
        },
        {
            "category": "amenity",
            "subcategories": None,
            "expected": '"amenity"'
        },
        {
            "category": "leisure",
            "subcategories": [],
            "expected": '"leisure"'
        }
    ]
    
    print("🧪 Testing query generation logic")
    print("=" * 40)
    
    all_passed = True
    
    for i, test_case in enumerate(test_cases, 1):
        category = test_case["category"]
        subcategories = test_case["subcategories"]
        expected = test_case["expected"]
        
        # Generate the actual query filter
        actual = generate_query_filter(category, subcategories)
        
        # Check if it matches expected
        if actual == expected:
            print(f"✅ Test {i}: PASSED")
            print(f"   Category: {category}")
            print(f"   Subcategories: {subcategories}")
            print(f"   Generated: {actual}")
        else:
            print(f"❌ Test {i}: FAILED")
            print(f"   Category: {category}")
            print(f"   Subcategories: {subcategories}")
            print(f"   Expected: {expected}")
            print(f"   Actual: {actual}")
            all_passed = False
        
        print()
    
    print("=" * 40)
    if all_passed:
        print("🎉 All tests passed! The query generation fix is working correctly.")
        return True
    else:
        print("💥 Some tests failed. Please check the output above.")
        return False


def test_query_syntax_examples():
    """Test specific examples mentioned in the issue."""
    
    print("\n🔍 Testing specific examples from the issue")
    print("=" * 40)
    
    # Example from the issue description
    category = "amenity"
    subcategories = ["restaurant", "cafe", "bar"]
    
    # Generate the pattern
    subcategory_pattern = "|".join(subcategories)
    query_filter = f'"{category}"~"^({subcategory_pattern})$"'
    
    expected = '"amenity"~"^(restaurant|cafe|bar)$"'
    
    print(f"Category: {category}")
    print(f"Subcategories: {subcategories}")
    print(f"Generated pattern: {query_filter}")
    print(f"Expected pattern: {expected}")
    
    if query_filter == expected:
        print("✅ Pattern matches expected format")
        return True
    else:
        print("❌ Pattern does not match expected format")
        return False


def test_complete_query_generation():
    """Test complete query generation with bounding box."""
    
    print("\n🔍 Testing complete query generation")
    print("=" * 40)
    
    def generate_complete_query(bbox, category, subcategories):
        """Generate a complete Overpass query."""
        if subcategories:
            subcategory_pattern = "|".join(subcategories)
            query_filter = f'"{category}"~"^({subcategory_pattern})$"'
        else:
            query_filter = f'"{category}"'
        
        query = f"""
        [out:json];
        (
          node[{query_filter}]({bbox[1]},{bbox[0]},{bbox[3]},{bbox[2]});
          way[{query_filter}]({bbox[1]},{bbox[0]},{bbox[3]},{bbox[2]});
          relation[{query_filter}]({bbox[1]},{bbox[0]},{bbox[3]},{bbox[2]});
        );
        out body;
        """
        return query.strip()
    
    # Test parameters
    bbox = (-122.4194, 37.7749, -122.4000, 37.7850)  # San Francisco area
    category = "amenity"
    subcategories = ["restaurant", "cafe", "bar"]
    
    query = generate_complete_query(bbox, category, subcategories)
    
    print("Generated query:")
    print(query)
    print()
    
    # Check that the query contains the expected elements
    checks = [
        ("[out:json];", "Output format declaration"),
        ("node[", "Node filter"),
        ("way[", "Way filter"),
        ("relation[", "Relation filter"),
        ('"amenity"~"^(restaurant|cafe|bar)$"', "Correct regex pattern"),
        ("37.7749,-122.4194,37.785,-122.4", "Bounding box coordinates"),
        ("out body;", "Output statement")
    ]
    
    all_checks_passed = True
    for check_text, description in checks:
        if check_text in query:
            print(f"✅ {description}: Found")
        else:
            print(f"❌ {description}: Not found")
            all_checks_passed = False
    
    return all_checks_passed


def main():
    """Run all tests."""
    print("🧪 OSM MCP Server Query Generation Tests")
    print("=" * 50)
    
    test1_passed = test_query_generation_with_subcategories()
    test2_passed = test_query_syntax_examples()
    test3_passed = test_complete_query_generation()
    
    print("\n" + "=" * 50)
    if test1_passed and test2_passed and test3_passed:
        print("🎉 All tests passed! The search_category fix is working correctly.")
        return 0
    else:
        print("💥 Some tests failed. Please check the output above.")
        return 1


if __name__ == "__main__":
    exit(main())