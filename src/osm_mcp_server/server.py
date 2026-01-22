from fastmcp import FastMCP, Context
from dataclasses import dataclass
from typing import AsyncIterator, List, Dict, Optional, Tuple, Any, Union
import aiohttp
import json
import asyncio
from contextlib import asynccontextmanager
import math
from datetime import datetime


class OSMClient:
    def __init__(self, base_url="https://api.openstreetmap.org/api/0.6"):
        self.base_url = base_url
        self.session = None
        self.cache = {}  # Simple in-memory cache
    
    async def connect(self):
        self.session = aiohttp.ClientSession()
        
    async def disconnect(self):
        if self.session:
            await self.session.close()

    async def geocode(self, query: str) -> List[Dict]:
        """Geocode an address or place name"""
        if not self.session:
            raise RuntimeError("OSM client not connected")
        
        nominatim_url = "https://nominatim.openstreetmap.org/search"
        async with self.session.get(
            nominatim_url,
            params={
                "q": query,
                "format": "json",
                "limit": 5
            },
            headers={"User-Agent": "OSM-MCP-Server/1.0"}
        ) as response:
            if response.status == 200:
                return await response.json()
            else:
                raise Exception(f"Failed to geocode '{query}': {response.status}")
    
    async def reverse_geocode(self, lat: float, lon: float) -> Dict:
        """Reverse geocode coordinates to address"""
        if not self.session:
            raise RuntimeError("OSM client not connected")
        
        nominatim_url = "https://nominatim.openstreetmap.org/reverse"
        async with self.session.get(
            nominatim_url,
            params={
                "lat": lat,
                "lon": lon,
                "format": "json"
            },
            headers={"User-Agent": "OSM-MCP-Server/1.0"}
        ) as response:
            if response.status == 200:
                return await response.json()
            else:
                raise Exception(f"Failed to reverse geocode ({lat}, {lon}): {response.status}")

    async def get_route(self, 
                         from_lat: float, 
                         from_lon: float, 
                         to_lat: float, 
                         to_lon: float,
                         mode: str = "car",
                         steps: bool = False,
                         overview: str = "overview",
                         annotations: bool = True) -> Dict:
        """Get routing information between two points"""
        if not self.session:
            raise RuntimeError("OSM client not connected")
        
        # Use OSRM for routing
        osrm_url = f"http://router.project-osrm.org/route/v1/{mode}/{from_lon},{from_lat};{to_lon},{to_lat}"
        params = {
            "overview": overview,
            "geometries": "geojson",
            "steps": str(steps).lower(),
            "annotations": str(annotations).lower()
        }
        
        async with self.session.get(osrm_url, params=params) as response:
            if response.status == 200:
                return await response.json()
            else:
                raise Exception(f"Failed to get route: {response.status}")

    async def get_nearby_pois(self, 
                             lat: float, 
                             lon: float, 
                             radius: float = 1000,
                             categories: List[str] = None) -> List[Dict]:
        """Get points of interest near a location"""
        if not self.session:
            raise RuntimeError("OSM client not connected")
        
        # Convert radius to bounding box (approximate)
        # 1 degree latitude ~= 111km
        # 1 degree longitude ~= 111km * cos(latitude)
        lat_delta = radius / 111000
        lon_delta = radius / (111000 * math.cos(math.radians(lat)))
        
        bbox = (
            lon - lon_delta,
            lat - lat_delta,
            lon + lon_delta,
            lat + lat_delta
        )
        
        # Build Overpass query
        overpass_url = "https://overpass-api.de/api/interpreter"
        
        # Default to common POI types if none specified
        if not categories:
            categories = ["amenity", "shop", "tourism", "leisure"]
        
        # Build tag filters
        tag_filters = []
        for category in categories:
            tag_filters.append(f'node["{category}"]({{bbox}});')
        
        query = f"""
        [out:json];
        (
            {" ".join(tag_filters)}
        );
        out body;
        """
        
        query = query.replace("{bbox}", f"{bbox[1]},{bbox[0]},{bbox[3]},{bbox[2]}")
        
        async with self.session.post(overpass_url, data={"data": query}) as response:
            if response.status == 200:
                data = await response.json()
                return data.get("elements", [])
            else:
                raise Exception(f"Failed to get nearby POIs: {response.status}")

    async def search_features_by_category(self, 
                                         bbox: Tuple[float, float, float, float],
                                         category: str,
                                         subcategories: List[str] = None) -> List[Dict]:
        """Search for OSM features by category and subcategories"""
        if not self.session:
            raise RuntimeError("OSM client not connected")
        
        overpass_url = "https://overpass-api.de/api/interpreter"
        
        # Build query for specified category and subcategories
        if subcategories:
            subcategory_filters = " or ".join([f'"{category}"="{sub}"' for sub in subcategories])
            query_filter = f'({subcategory_filters})'
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
        
        async with self.session.post(overpass_url, data={"data": query}) as response:
            if response.status == 200:
                data = await response.json()
                return data.get("elements", [])
            else:
                raise Exception(f"Failed to search features by category: {response.status}")

# Create application context
@dataclass
class AppContext:
    osm_client: OSMClient

# Define lifespan manager
@asynccontextmanager
async def app_lifespan(server: FastMCP) -> AsyncIterator[AppContext]:
    """Manage OSM client lifecycle"""
    osm_client = OSMClient()
    try:
        await osm_client.connect()
        yield AppContext(osm_client=osm_client)
    finally:
        await osm_client.disconnect()

# Create the MCP server
mcp = FastMCP(
    "Location-Based App MCP Server",
    lifespan=app_lifespan
)


@mcp.tool()
async def geocode_address(address: str, ctx: Context) -> List[Dict]:
    """
    Convert an address or place name to geographic coordinates with detailed location information.
    
    This tool takes a text description of a location (such as an address, landmark name, or
    place of interest) and returns its precise geographic coordinates along with rich metadata.
    The results can be used for mapping, navigation, location-based analysis, and as input to
    other geospatial tools.
    
    Args:
        address: The address, place name, landmark, or description to geocode (e.g., "Empire State Building", 
                "123 Main St, Springfield", "Golden Gate Park, San Francisco")
        
    Returns:
        List of matching locations with:
        - Geographic coordinates (latitude/longitude)
        - Formatted address
        - Administrative boundaries (city, state, country)
        - OSM type and ID
        - Bounding box (if applicable)
        - Importance ranking
    """
    osm_client = ctx.request_context.lifespan_context.osm_client
    results = await osm_client.geocode(address)
    
    # Enhance results with additional context
    for result in results:
        if "lat" in result and "lon" in result:
            result["coordinates"] = {
                "latitude": float(result["lat"]),
                "longitude": float(result["lon"])
            }
    
    return results

@mcp.tool()
async def reverse_geocode(latitude: float, longitude: float, ctx: Context) -> Dict:
    """
    Convert geographic coordinates to a detailed address and location description.
    
    This tool takes a specific point on Earth (latitude and longitude) and returns 
    comprehensive information about that location, including its address, nearby landmarks,
    administrative boundaries, and other contextual information. Useful for translating
    GPS coordinates into human-readable locations.
    
    Args:
        latitude: The latitude coordinate (decimal degrees, WGS84)
        longitude: The longitude coordinate (decimal degrees, WGS84)
        
    Returns:
        Detailed address and location information including:
        - Formatted address
        - Building, street, city, state, country
        - Administrative hierarchy
        - OSM metadata
        - Postal code and other relevant identifiers
    """
    osm_client = ctx.request_context.lifespan_context.osm_client
    return await osm_client.reverse_geocode(latitude, longitude)

@mcp.tool()
async def find_nearby_places(
    latitude: float,
    longitude: float,
    ctx: Context,
    radius: float = 1000,  # meters
    categories: List[str] = None,
    limit: int = 20
) -> Dict[str, Any]:
    """
    Discover points of interest and amenities near a specific location.
    
    This tool performs a comprehensive search around a geographic point to identify
    nearby establishments, amenities, and points of interest. Results are organized by
    category and subcategory, making it easy to find specific types of places. Essential
    for location-based recommendations, neighborhood analysis, and proximity-based decision making.
    
    Args:
        latitude: Center point latitude (decimal degrees)
        longitude: Center point longitude (decimal degrees)
        radius: Search radius in meters (defaults to 1000m/1km)
        categories: List of OSM categories to search for (e.g., ["amenity", "shop", "tourism"]).
                   If omitted, searches common categories.
        limit: Maximum number of total results to return
        
    Returns:
        Structured dictionary containing:
        - Original query parameters
        - Total count of places found
        - Results grouped by category and subcategory
        - Each place includes name, coordinates, and associated tags
    """
    osm_client = ctx.request_context.lifespan_context.osm_client
    
    # Set default categories if not provided
    if not categories:
        categories = ["amenity", "shop", "tourism", "leisure"]
    
    ctx.info(f"Searching for places within {radius}m of ({latitude}, {longitude})")
    places = await osm_client.get_nearby_pois(latitude, longitude, radius, categories)
    
    # Group results by category
    results_by_category = {}
    
    for place in places[:limit]:
        tags = place.get("tags", {})
        
        # Find the matching category
        for category in categories:
            if category in tags:
                subcategory = tags[category]
                if category not in results_by_category:
                    results_by_category[category] = {}
                
                if subcategory not in results_by_category[category]:
                    results_by_category[category][subcategory] = []
                
                # Add place to appropriate category and subcategory
                place_info = {
                    "id": place.get("id"),
                    "name": tags.get("name", "Unnamed"),
                    "latitude": place.get("lat"),
                    "longitude": place.get("lon"),
                    "tags": tags
                }
                
                results_by_category[category][subcategory].append(place_info)
    
    # Calculate total count
    total_count = sum(
        len(places)
        for category_data in results_by_category.values()
        for places in category_data.values()
    )
    
    return {
        "query": {
            "latitude": latitude,
            "longitude": longitude,
            "radius": radius
        },
        "categories": results_by_category,
        "total_count": total_count
    }

@mcp.tool()
async def get_route_directions(
    from_latitude: float,
    from_longitude: float,
    to_latitude: float,
    to_longitude: float,
    ctx: Context,
    mode: str = "car",
    steps: bool = False,
    overview: str = "simplified",
    annotations: bool = False
) -> Dict[str, Any]:
    """
    Calculate detailed route directions between two geographic points.
    
    This tool provides comprehensive routing information between two locations using OpenStreetMap/OSRM.
    The output can be minimized using the steps, overview, and annotations parameters to reduce the response size.
    
    Args:
        from_latitude: Starting point latitude (decimal degrees)
        from_longitude: Starting point longitude (decimal degrees)
        to_latitude: Destination latitude (decimal degrees)
        to_longitude: Destination longitude (decimal degrees)
        ctx: Context (provided internally by MCP)
        mode: Transportation mode ("car", "bike", "foot")
        steps: Turn-by-turn instructions (True/False, Default: False)
        overview: Geometry output ("full", "simplified", "false"; Default: "simplified")
        annotations: Additional segment info (True/False, Default: False)
    
    Returns:
        Dictionary with routing information (summary, directions, geometry, waypoints)

    Example:
        {
          "from_latitude": 51.3334193,
          "from_longitude": 9.4540423,
          "to_latitude": 51.3295516,
          "to_longitude": 9.4576721,
          "mode": "car",
          "steps": false,
          "overview": "simplified",
          "annotations": false
        }
    """
    osm_client = ctx.request_context.lifespan_context.osm_client
    
    # Validate transportation mode
    valid_modes = ["car", "bike", "foot"]
    if mode not in valid_modes:
        ctx.warning(f"Invalid mode '{mode}'. Using 'car' instead.")
        mode = "car"
    
    ctx.info(f"Calculating {mode} route from ({from_latitude}, {from_longitude}) to ({to_latitude}, {to_longitude})")
    
    # Get route from OSRM
    route_data = await osm_client.get_route(
        from_latitude, from_longitude,
        to_latitude, to_longitude,
        mode,
        steps=steps,
        overview=overview,
        annotations=annotations
    )
    
    # Process and simplify the response
    if "routes" in route_data and len(route_data["routes"]) > 0:
        route = route_data["routes"][0]
        
        # Extract turn-by-turn directions
        steps_list = []
        if "legs" in route:
            for leg in route["legs"]:
                for step in leg.get("steps", []):
                    steps_list.append({
                        "instruction": step.get("maneuver", {}).get("instruction", ""),
                        "distance": step.get("distance"),
                        "duration": step.get("duration"),
                        "name": step.get("name", "")
                    })
        
        return {
            "summary": {
                "distance": route.get("distance"),  # meters
                "duration": route.get("duration"),  # seconds
                "mode": mode
            },
            "directions": steps_list,
            "geometry": route.get("geometry"),
            "waypoints": route_data.get("waypoints", [])
        }
    else:
        raise Exception("No route found")

@mcp.tool()
async def search_category(
    category: str,
    min_latitude: float,
    min_longitude: float,
    max_latitude: float,
    max_longitude: float,
    ctx: Context,
    subcategories: List[str] = None
) -> Dict[str, Any]:
    """
    Search for specific types of places within a defined geographic area.
    
    This tool allows targeted searches for places matching specific categories within
    a rectangular geographic region. It's particularly useful for filtering places by type
    (restaurants, schools, parks, etc.) within a neighborhood or city district. Results include
    complete location details and metadata about each matching place.
    
    Args:
        category: Main OSM category to search for (e.g., "amenity", "shop", "tourism", "building")
        min_latitude: Southern boundary of search area (decimal degrees)
        min_longitude: Western boundary of search area (decimal degrees)
        max_latitude: Northern boundary of search area (decimal degrees)
        max_longitude: Eastern boundary of search area (decimal degrees)
        subcategories: Optional list of specific subcategories to filter by (e.g., ["restaurant", "cafe"])
        
    Returns:
        Structured results including:
        - Query parameters
        - Count of matching places
        - List of matching places with coordinates, names, and metadata
    """
    osm_client = ctx.request_context.lifespan_context.osm_client
    
    bbox = (min_longitude, min_latitude, max_longitude, max_latitude)
    
    ctx.info(f"Searching for {category} in bounding box")
    features = await osm_client.search_features_by_category(bbox, category, subcategories)
    
    # Process results
    results = []
    for feature in features:
        tags = feature.get("tags", {})
        
        # Get coordinates based on feature type
        coords = {}
        if feature.get("type") == "node":
            coords = {
                "latitude": feature.get("lat"),
                "longitude": feature.get("lon")
            }
        # For ways and relations, use center coordinates if available
        elif "center" in feature:
            coords = {
                "latitude": feature.get("center", {}).get("lat"),
                "longitude": feature.get("center", {}).get("lon")
            }
        
        # Only include features with valid coordinates
        if coords:
            results.append({
                "id": feature.get("id"),
                "type": feature.get("type"),
                "name": tags.get("name", "Unnamed"),
                "coordinates": coords,
                "category": category,
                "subcategory": tags.get(category),
                "tags": tags
            })
    
    return {
        "query": {
            "category": category,
            "subcategories": subcategories,
            "bbox": {
                "min_latitude": min_latitude,
                "min_longitude": min_longitude,
                "max_latitude": max_latitude,
                "max_longitude": max_longitude
            }
        },
        "results": results,
        "count": len(results)
    }

@mcp.tool()
async def suggest_meeting_point(
    locations: List[Dict[str, float]],
    ctx: Context,
    venue_type: str = "cafe"
) -> Dict[str, Any]:
    """
    Find the optimal meeting place for multiple people coming from different locations.
    
    This tool calculates a central meeting point based on the locations of multiple individuals,
    then recommends suitable venues near that central point. Ideal for planning social gatherings,
    business meetings, or any situation where multiple people need to converge from different
    starting points.
    
    Args:
        locations: List of dictionaries, each containing the latitude and longitude of a person's location
                  Example: [{"latitude": 37.7749, "longitude": -122.4194}, {"latitude": 37.3352, "longitude": -121.8811}]
        venue_type: Type of venue to suggest as a meeting point. Options include:
                   "cafe", "restaurant", "bar", "library", "park", etc.
        
    Returns:
        Meeting point recommendations including:
        - Calculated center point coordinates
        - List of suggested venues with names and details
        - Total number of matching venues in the area
    """
    osm_client = ctx.request_context.lifespan_context.osm_client
    
    if len(locations) < 2:
        raise ValueError("Need at least two locations to suggest a meeting point")
    
    # Calculate the center point (simple average)
    avg_lat = sum(loc.get("latitude", 0) for loc in locations) / len(locations)
    avg_lon = sum(loc.get("longitude", 0) for loc in locations) / len(locations)
    
    ctx.info(f"Calculating center point for {len(locations)} locations: ({avg_lat}, {avg_lon})")
    
    # Search for venues around this center point
    venues = await osm_client.get_nearby_pois(
        avg_lat, avg_lon, 
        radius=500,  # Search within 500m of center
        categories=["amenity"]
    )
    
    # Filter venues by type
    matching_venues = []
    for venue in venues:
        tags = venue.get("tags", {})
        if tags.get("amenity") == venue_type:
            matching_venues.append({
                "id": venue.get("id"),
                "name": tags.get("name", "Unnamed Venue"),
                "latitude": venue.get("lat"),
                "longitude": venue.get("lon"),
                "tags": tags
            })
    
    # If no venues found, expand search
    if not matching_venues:
        ctx.info(f"No {venue_type} found within 500m, expanding search to 1000m")
        venues = await osm_client.get_nearby_pois(
            avg_lat, avg_lon, 
            radius=1000,
            categories=["amenity"]
        )
        
        for venue in venues:
            tags = venue.get("tags", {})
            if tags.get("amenity") == venue_type:
                matching_venues.append({
                    "id": venue.get("id"),
                    "name": tags.get("name", "Unnamed Venue"),
                    "latitude": venue.get("lat"),
                    "longitude": venue.get("lon"),
                    "tags": tags
                })
    
    # Return the result
    return {
        "center_point": {
            "latitude": avg_lat,
            "longitude": avg_lon
        },
        "suggested_venues": matching_venues[:5],  # Top 5 venues
        "venue_type": venue_type,
        "total_options": len(matching_venues)
    }

@mcp.tool()
async def explore_area(
    latitude: float,
    longitude: float,
    ctx: Context,
    radius: float = 500
) -> Dict[str, Any]:
    """
    Generate a comprehensive profile of an area including all amenities and features.
    
    This powerful analysis tool creates a detailed overview of a neighborhood or area by
    identifying and categorizing all geographic features, amenities, and points of interest.
    Results are organized by category for easy analysis. Excellent for neighborhood research,
    area comparisons, and location-based decision making.
    
    Args:
        latitude: Center point latitude (decimal degrees)
        longitude: Center point longitude (decimal degrees)
        radius: Search radius in meters (defaults to 500m)
        
    Returns:
        In-depth area profile including:
        - Address and location context
        - Total feature count
        - Features organized by category and subcategory
        - Each feature includes name, coordinates, and detailed metadata
    """
    osm_client = ctx.request_context.lifespan_context.osm_client
    
    # Categories to search for
    categories = [
        "amenity", "shop", "tourism", "leisure", 
        "natural", "historic", "public_transport"
    ]
    
    results = {}
    for i, category in enumerate(categories):
        await ctx.report_progress(i, len(categories))
        ctx.info(f"Exploring {category} features...")
        
        try:
            # Convert radius to bounding box
            lat_delta = radius / 111000
            lon_delta = radius / (111000 * math.cos(math.radians(latitude)))
            
            bbox = (
                longitude - lon_delta,
                latitude - lat_delta,
                longitude + lon_delta,
                latitude + lat_delta
            )
            
            features = await osm_client.search_features_by_category(bbox, category)
            
            # Group by subcategory
            subcategories = {}
            for feature in features:
                tags = feature.get("tags", {})
                subcategory = tags.get(category)
                
                if subcategory:
                    if subcategory not in subcategories:
                        subcategories[subcategory] = []
                    
                    # Get coordinates based on feature type
                    coords = {}
                    if feature.get("type") == "node":
                        coords = {
                            "latitude": feature.get("lat"),
                            "longitude": feature.get("lon")
                        }
                    elif "center" in feature:
                        coords = {
                            "latitude": feature.get("center", {}).get("lat"),
                            "longitude": feature.get("center", {}).get("lon")
                        }
                    
                    subcategories[subcategory].append({
                        "id": feature.get("id"),
                        "name": tags.get("name", "Unnamed"),
                        "coordinates": coords,
                        "type": feature.get("type"),
                        "tags": tags
                    })
            
            results[category] = subcategories
            
        except Exception as e:
            ctx.warning(f"Error fetching {category} features: {str(e)}")
            results[category] = {}
    
    # Get address information for the center point
    try:
        address_info = await osm_client.reverse_geocode(latitude, longitude)
    except Exception:
        address_info = {"error": "Could not retrieve address information"}
    
    # Report completion
    await ctx.report_progress(len(categories), len(categories))
    
    # Count total features
    total_features = sum(
        len(places)
        for category_data in results.values()
        for places in category_data.values()
    )
    
    return {
        "query": {
            "latitude": latitude,
            "longitude": longitude,
            "radius": radius
        },
        "address": address_info,
        "categories": results,
        "total_features": total_features,
        "timestamp": datetime.now().isoformat()
    }

# Add resource endpoints for common location-based app needs
@mcp.resource("location://place/{query}")
async def get_place_resource(query: str) -> str:
    """
    Get information about a place by name.
    
    Args:
        query: Place name or address to look up
        
    Returns:
        JSON string with place information
    """
    async with aiohttp.ClientSession() as session:
        nominatim_url = "https://nominatim.openstreetmap.org/search"
        async with session.get(
            nominatim_url,
            params={
                "q": query,
                "format": "json",
                "limit": 1
            },
            headers={"User-Agent": "LocationApp-MCP-Server/1.0"}
        ) as response:
            if response.status == 200:
                data = await response.json()
                return json.dumps(data)
            else:
                raise Exception(f"Failed to get place info for {query}: {response.status}")

@mcp.resource("location://map/{style}/{z}/{x}/{y}")
async def get_map_style(style: str, z: int, x: int, y: int) -> Tuple[bytes, str]:
    """
    Get a styled map tile at the specified coordinates.
    
    Args:
        style: Map style (standard, cycle, transport, etc.)
        z: Zoom level
        x: X coordinate
        y: Y coordinate
        
    Returns:
        Tuple of (tile image bytes, mime type)
    """
    # Map styles to their respective tile servers
    tile_servers = {
        "standard": "https://tile.openstreetmap.org/{z}/{x}/{y}.png",
        "cycle": "https://tile.thunderforest.com/cycle/{z}/{x}/{y}.png",
        "transport": "https://tile.thunderforest.com/transport/{z}/{x}/{y}.png",
        "landscape": "https://tile.thunderforest.com/landscape/{z}/{x}/{y}.png",
        "outdoor": "https://tile.thunderforest.com/outdoors/{z}/{x}/{y}.png"
    }
    
    
    if style not in tile_servers:
        style = "standard"
    
    tile_url = tile_servers[style].replace("{z}", str(z)).replace("{x}", str(x)).replace("{y}", str(y))
    
    async with aiohttp.ClientSession() as session:
        async with session.get(tile_url) as response:
            if response.status == 200:
                tile_data = await response.read()
                return tile_data, "image/png"
            else:
                raise Exception(f"Failed to get {style} tile at {z}/{x}/{y}: {response.status}")


@mcp.tool()
async def find_schools_nearby(
    latitude: float,
    longitude: float,
    ctx: Context,
    radius: float = 2000,
    education_levels: List[str] = None
) -> Dict[str, Any]:
    """
    Locate educational institutions near a specific location, filtered by education level.
    
    This specialized search tool identifies schools, colleges, and other educational institutions
    within a specified distance from a location. Results can be filtered by education level
    (elementary, middle, high school, university, etc.). Essential for families evaluating
    neighborhoods or real estate purchases with education considerations.
    
    Args:
        latitude: Center point latitude (decimal degrees)
        longitude: Center point longitude (decimal degrees)
        radius: Search radius in meters (defaults to 2000m/2km)
        education_levels: Optional list of specific education levels to filter by
                         (e.g., ["elementary", "secondary", "university"])
        
    Returns:
        List of educational institutions with:
        - Name and type
        - Distance from search point
        - Education levels offered
        - Contact information if available
        - Other relevant metadata
    """
    osm_client = ctx.request_context.lifespan_context.osm_client
    
    # Convert radius to bounding box (approximate)
    lat_delta = radius / 111000
    lon_delta = radius / (111000 * math.cos(math.radians(latitude)))
    
    bbox = (
        longitude - lon_delta,
        latitude - lat_delta,
        longitude + lon_delta,
        latitude + lat_delta
    )
    
    # Build Overpass query for educational institutions
    overpass_url = "https://overpass-api.de/api/interpreter"
    
    # Create query for amenity=school and other education-related tags
    education_filters = [
        'node["amenity"="school"]({{bbox}});',
        'way["amenity"="school"]({{bbox}});',
        'node["amenity"="university"]({{bbox}});',
        'way["amenity"="university"]({{bbox}});',
        'node["amenity"="kindergarten"]({{bbox}});',
        'way["amenity"="kindergarten"]({{bbox}});',
        'node["amenity"="college"]({{bbox}});',
        'way["amenity"="college"]({{bbox}});'
    ]
    
    query = f"""
    [out:json];
    (
        {" ".join(education_filters)}
    );
    out body;
    """
    
    query = query.replace("{bbox}", f"{bbox[1]},{bbox[0]},{bbox[3]},{bbox[2]}")
    
    async with aiohttp.ClientSession() as session:
        async with session.post(overpass_url, data={"data": query}) as response:
            if response.status == 200:
                data = await response.json()
                schools = data.get("elements", [])
            else:
                raise Exception(f"Failed to find schools: {response.status}")
    
    # Process and filter results
    results = []
    for school in schools:
        tags = school.get("tags", {})
        school_type = tags.get("school", "")
        
        # Filter by education level if specified
        if education_levels and school_type and school_type not in education_levels:
            continue
        
        # Get coordinates based on feature type
        coords = {}
        if school.get("type") == "node":
            coords = {
                "latitude": school.get("lat"),
                "longitude": school.get("lon")
            }
        elif "center" in school:
            coords = {
                "latitude": school.get("center", {}).get("lat"),
                "longitude": school.get("center", {}).get("lon")
            }
        
        # Skip if no valid coordinates
        if not coords:
            continue
        
        # Calculate distance from search point
        # Using Haversine formula for quick distance calculation
        from math import radians, sin, cos, sqrt, asin
        
        def haversine(lat1, lon1, lat2, lon2):
            R = 6371000  # Earth radius in meters
            dLat = radians(lat2 - lat1)
            dLon = radians(lon2 - lon1)
            a = sin(dLat/2)**2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dLon/2)**2
            c = 2 * asin(sqrt(a))
            return R * c
        
        distance = haversine(latitude, longitude, coords["latitude"], coords["longitude"])
        
        results.append({
            "id": school.get("id"),
            "name": tags.get("name", "Unnamed School"),
            "amenity_type": tags.get("amenity", ""),
            "school_type": school_type,
            "education_level": tags.get("isced", ""),
            "coordinates": coords,
            "distance": round(distance, 1),
            "address": {
                "street": tags.get("addr:street", ""),
                "housenumber": tags.get("addr:housenumber", ""),
                "city": tags.get("addr:city", ""),
                "postcode": tags.get("addr:postcode", "")
            },
            "tags": tags
        })
    
    # Sort by distance
    results.sort(key=lambda x: x["distance"])
    
    return {
        "query": {
            "latitude": latitude,
            "longitude": longitude,
            "radius": radius,
            "education_levels": education_levels
        },
        "schools": results,
        "count": len(results)
    }

@mcp.tool()
async def analyze_commute(
    home_latitude: float,
    home_longitude: float,
    work_latitude: float,
    work_longitude: float,
    ctx: Context,
    modes: List[str] = ["car", "foot", "bike"],
    depart_at: str = None  # Time in HH:MM format, e.g. "08:30"
) -> Dict[str, Any]:
    """
    Perform a detailed commute analysis between home and work locations.
    
    This advanced tool analyzes commute options between two locations (typically home and work),
    comparing multiple transportation modes and providing detailed metrics for each option.
    Includes estimated travel times, distances, turn-by-turn directions, and other commute-relevant
    data. Essential for real estate decisions, lifestyle planning, and workplace relocation analysis.
    
    Args:
        home_latitude: Home location latitude (decimal degrees)
        home_longitude: Home location longitude (decimal degrees)
        work_latitude: Workplace location latitude (decimal degrees)
        work_longitude: Workplace location longitude (decimal degrees)
        modes: List of transportation modes to analyze (options: "car", "foot", "bike")
        depart_at: Optional departure time (format: "HH:MM") for time-sensitive routing
        
    Returns:
        Comprehensive commute analysis with:
        - Summary comparing all transportation modes
        - Detailed route information for each mode
        - Total distance and duration for each option
        - Turn-by-turn directions
    """
    osm_client = ctx.request_context.lifespan_context.osm_client
    
    # Get address information for both locations
    home_info = await osm_client.reverse_geocode(home_latitude, home_longitude)
    work_info = await osm_client.reverse_geocode(work_latitude, work_longitude)
    
    # Get commute information for each mode
    commute_options = []
    
    for mode in modes:
        ctx.info(f"Calculating {mode} route for commute analysis")
        
        # Get route from OSRM
        try:
            route_data = await osm_client.get_route(
                home_latitude, home_longitude,
                work_latitude, work_longitude,
                mode
            )
            
            if "routes" in route_data and len(route_data["routes"]) > 0:
                route = route_data["routes"][0]
                
                # Extract directions
                steps = []
                if "legs" in route:
                    for leg in route["legs"]:
                        for step in leg.get("steps", []):
                            steps.append({
                                "instruction": step.get("maneuver", {}).get("instruction", ""),
                                "distance": step.get("distance"),
                                "duration": step.get("duration"),
                                "name": step.get("name", "")
                            })
                
                commute_options.append({
                    "mode": mode,
                    "distance_km": round(route.get("distance", 0) / 1000, 2),
                    "duration_minutes": round(route.get("duration", 0) / 60, 1),
                    "directions": steps
                })
        except Exception as e:
            ctx.warning(f"Error getting {mode} route: {str(e)}")
            commute_options.append({
                "mode": mode,
                "error": str(e)
            })
    
    # Sort by duration (fastest first)
    commute_options.sort(key=lambda x: x.get("duration_minutes", float("inf")))
    
    return {
        "home": {
            "coordinates": {
                "latitude": home_latitude,
                "longitude": home_longitude
            },
            "address": home_info.get("display_name", "Unknown location")
        },
        "work": {
            "coordinates": {
                "latitude": work_latitude,
                "longitude": work_longitude
            },
            "address": work_info.get("display_name", "Unknown location")
        },
        "commute_options": commute_options,
        "fastest_option": commute_options[0]["mode"] if commute_options else None,
        "depart_at": depart_at
    }

@mcp.tool()
async def find_ev_charging_stations(
    latitude: float,
    longitude: float,
    ctx: Context,
    radius: float = 5000,
    connector_types: List[str] = None,
    min_power: float = None
) -> Dict[str, Any]:
    """
    Locate electric vehicle charging stations near a specific location.
    
    This specialized search tool identifies EV charging infrastructure within a specified
    distance from a location. Results can be filtered by connector type (Tesla, CCS, CHAdeMO, etc.)
    and minimum power delivery. Essential for EV owners planning trips or evaluating potential
    charging stops.
    
    Args:
        latitude: Center point latitude (decimal degrees)
        longitude: Center point longitude (decimal degrees)
        radius: Search radius in meters (defaults to 5000m/5km)
        connector_types: Optional list of specific connector types to filter by
                        (e.g., ["type2", "ccs", "tesla"])
        min_power: Minimum charging power in kW
        
    Returns:
        List of charging stations with:
        - Location name and operator
        - Available connector types
        - Charging speeds
        - Number of charging points
        - Access restrictions
        - Other relevant metadata
    """
    osm_client = ctx.request_context.lifespan_context.osm_client
    
    # Convert radius to bounding box
    lat_delta = radius / 111000
    lon_delta = radius / (111000 * math.cos(math.radians(latitude)))
    
    bbox = (
        longitude - lon_delta,
        latitude - lat_delta,
        longitude + lon_delta,
        latitude + lat_delta
    )
    
    # Build Overpass query for EV charging stations
    overpass_url = "https://overpass-api.de/api/interpreter"
    
    query = f"""
    [out:json];
    (
        node["amenity"="charging_station"]({{bbox}});
        way["amenity"="charging_station"]({{bbox}});
    );
    out body;
    """
    
    query = query.replace("{bbox}", f"{bbox[1]},{bbox[0]},{bbox[3]},{bbox[2]}")
    
    async with aiohttp.ClientSession() as session:
        async with session.post(overpass_url, data={"data": query}) as response:
            if response.status == 200:
                data = await response.json()
                stations = data.get("elements", [])
            else:
                raise Exception(f"Failed to find charging stations: {response.status}")
    
    # Process and filter results
    results = []
    for station in stations:
        tags = station.get("tags", {})
        
        # Get coordinates based on feature type
        coords = {}
        if station.get("type") == "node":
            coords = {
                "latitude": station.get("lat"),
                "longitude": station.get("lon")
            }
        elif "center" in station:
            coords = {
                "latitude": station.get("center", {}).get("lat"),
                "longitude": station.get("center", {}).get("lon")
            }
        
        # Skip if no valid coordinates
        if not coords:
            continue
        
        # Extract connector information
        connectors = []
        for key, value in tags.items():
            if key.startswith("socket:"):
                connector_type = key.split(":", 1)[1]
                connectors.append({
                    "type": connector_type,
                    "count": value if value.isdigit() else 1
                })
        
        # Filter by connector type if specified
        if connector_types:
            has_matching_connector = False
            for connector in connectors:
                if connector["type"] in connector_types:
                    has_matching_connector = True
                    break
            if not has_matching_connector:
                continue
        
        # Extract power information
        power = None
        if "maxpower" in tags:
            try:
                power = float(tags["maxpower"])
            except ValueError:
                pass
        
        # Filter by minimum power if specified
        if min_power is not None and (power is None or power < min_power):
            continue
        
        # Calculate distance from search point
        from math import radians, sin, cos, sqrt, asin
        
        def haversine(lat1, lon1, lat2, lon2):
            R = 6371000  # Earth radius in meters
            dLat = radians(lat2 - lat1)
            dLon = radians(lon2 - lon1)
            a = sin(dLat/2)**2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dLon/2)**2
            c = 2 * asin(sqrt(a))
            return R * c
        
        distance = haversine(latitude, longitude, coords["latitude"], coords["longitude"])
        
        results.append({
            "id": station.get("id"),
            "name": tags.get("name", "Unnamed Charging Station"),
            "operator": tags.get("operator", "Unknown"),
            "coordinates": coords,
            "distance": round(distance, 1),
            "connectors": connectors,
            "capacity": tags.get("capacity", "Unknown"),
            "power": power,
            "fee": tags.get("fee", "Unknown"),
            "access": tags.get("access", "public"),
            "opening_hours": tags.get("opening_hours", "Unknown"),
            "address": {
                "street": tags.get("addr:street", ""),
                "housenumber": tags.get("addr:housenumber", ""),
                "city": tags.get("addr:city", ""),
                "postcode": tags.get("addr:postcode", "")
            },
            "tags": tags
        })
    
    # Sort by distance
    results.sort(key=lambda x: x["distance"])
    
    return {
        "query": {
            "latitude": latitude,
            "longitude": longitude,
            "radius": radius,
            "connector_types": connector_types,
            "min_power": min_power
        },
        "stations": results,
        "count": len(results)
    }

@mcp.tool()
async def analyze_neighborhood(
    latitude: float,
    longitude: float,
    ctx: Context,
    radius: float = 1000
) -> Dict[str, Any]:
    """
    Generate a comprehensive neighborhood analysis focused on livability factors.
    
    This advanced analysis tool evaluates a neighborhood based on multiple livability factors,
    including amenities, transportation options, green spaces, and services. Results include
    counts and proximity scores for various categories, helping to assess the overall quality
    and convenience of a residential area. Invaluable for real estate decisions, relocation
    planning, and neighborhood comparisons.
    
    Args:
        latitude: Center point latitude (decimal degrees)
        longitude: Center point longitude (decimal degrees)
        radius: Analysis radius in meters (defaults to 1000m/1km)
        
    Returns:
        Comprehensive neighborhood profile including:
        - Overall neighborhood score
        - Walkability assessment
        - Public transportation access
        - Nearby amenities (shops, restaurants, services)
        - Green spaces and recreation
        - Education and healthcare facilities
        - Detailed counts and distance metrics for each category
    """
    osm_client = ctx.request_context.lifespan_context.osm_client
    
    # Get address information for the center point
    address_info = await osm_client.reverse_geocode(latitude, longitude)
    
    # Categories to analyze for neighborhood quality
    categories = [
        # Essential services
        {"name": "groceries", "tags": ["shop=supermarket", "shop=convenience", "shop=grocery"]},
        {"name": "restaurants", "tags": ["amenity=restaurant", "amenity=cafe", "amenity=fast_food"]},
        {"name": "healthcare", "tags": ["amenity=hospital", "amenity=doctors", "amenity=pharmacy"]},
        {"name": "education", "tags": ["amenity=school", "amenity=kindergarten", "amenity=university"]},
        
        # Transportation
        {"name": "public_transport", "tags": ["public_transport=stop_position", "railway=station", "amenity=bus_station"]},
        
        # Recreation
        {"name": "parks", "tags": ["leisure=park", "leisure=garden", "leisure=playground"]},
        {"name": "sports", "tags": ["leisure=sports_centre", "leisure=fitness_centre", "leisure=swimming_pool"]},
        
        # Culture and entertainment
        {"name": "entertainment", "tags": ["amenity=theatre", "amenity=cinema", "amenity=arts_centre"]},
        
        # Other amenities
        {"name": "shopping", "tags": ["shop=mall", "shop=department_store", "shop=clothes"]},
        {"name": "services", "tags": ["amenity=bank", "amenity=post_office", "amenity=atm"]}
    ]
    
    # Build overpass queries and collect results
    results = {}
    scores = {}
    
    for i, category in enumerate(categories):
        await ctx.report_progress(i, len(categories))
        ctx.info(f"Analyzing {category['name']} in neighborhood...")
        
        # Convert radius to bounding box
        lat_delta = radius / 111000
        lon_delta = radius / (111000 * math.cos(math.radians(latitude)))
        
        bbox = (
            longitude - lon_delta,
            latitude - lat_delta,
            longitude + lon_delta,
            latitude + lat_delta
        )
        
        # Build Overpass query
        overpass_url = "https://overpass-api.de/api/interpreter"
        
        # Create query for category tags
        tag_filters = []
        for tag in category["tags"]:
            key, value = tag.split("=")
            tag_filters.append(f'node["{key}"="{value}"]({{bbox}});')
            tag_filters.append(f'way["{key}"="{value}"]({{bbox}});')
        
        query = f"""
        [out:json];
        (
            {" ".join(tag_filters)}
        );
        out body;
        """
        
        query = query.replace("{bbox}", f"{bbox[1]},{bbox[0]},{bbox[3]},{bbox[2]}")
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(overpass_url, data={"data": query}) as response:
                    if response.status == 200:
                        data = await response.json()
                        features = data.get("elements", [])
                    else:
                        ctx.warning(f"Failed to analyze {category['name']}: {response.status}")
                        features = []
                        
            # Process and calculate metrics
            feature_list = []
            distances = []
            
            for feature in features:
                tags = feature.get("tags", {})
                
                # Get coordinates based on feature type
                coords = {}
                if feature.get("type") == "node":
                    coords = {
                        "latitude": feature.get("lat"),
                        "longitude": feature.get("lon")
                    }
                elif "center" in feature:
                    coords = {
                        "latitude": feature.get("center", {}).get("lat"),
                        "longitude": feature.get("center", {}).get("lon")
                    }
                
                # Skip if no valid coordinates
                if not coords:
                    continue
                
                # Calculate distance from center point
                from math import radians, sin, cos, sqrt, asin
                
                def haversine(lat1, lon1, lat2, lon2):
                    R = 6371000  # Earth radius in meters
                    dLat = radians(lat2 - lat1)
                    dLon = radians(lon2 - lon1)
                    a = sin(dLat/2)**2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dLon/2)**2
                    c = 2 * asin(sqrt(a))
                    return R * c
                
                distance = haversine(latitude, longitude, coords["latitude"], coords["longitude"])
                distances.append(distance)
                
                feature_list.append({
                    "id": feature.get("id"),
                    "name": tags.get("name", "Unnamed"),
                    "type": feature.get("type"),
                    "coordinates": coords,
                    "distance": round(distance, 1),
                    "tags": tags
                })
            
            # Sort by distance
            feature_list.sort(key=lambda x: x["distance"])
            
            # Calculate metrics
            count = len(feature_list)
            avg_distance = sum(distances) / count if count > 0 else None
            min_distance = min(distances) if count > 0 else None
            
            # Score this category (0-10)
            # Higher score for more amenities and closer proximity
            if count == 0:
                category_score = 0
            else:
                # Base score on count and proximity
                count_score = min(count / 5, 1) * 5  # Up to 5 points for count
                proximity_score = 5 - min(min_distance / radius, 1) * 5  # Up to 5 points for proximity
                category_score = count_score + proximity_score
            
            # Store results
            results[category["name"]] = {
                "count": count,
                "features": feature_list[:10],  # Limit to top 10
                "metrics": {
                    "total_count": count,
                    "avg_distance": round(avg_distance, 1) if avg_distance else None,
                    "min_distance": round(min_distance, 1) if min_distance else None
                }
            }
            
            scores[category["name"]] = category_score
            
        except Exception as e:
            ctx.warning(f"Error analyzing {category['name']}: {str(e)}")
            results[category["name"]] = {"error": str(e)}
            scores[category["name"]] = 0
    
    # Calculate overall neighborhood score
    if scores:
        overall_score = sum(scores.values()) / len(scores)
    else:
        overall_score = 0
    
    # Calculate walkability score based on amenities within walking distance (500m)
    walkable_amenities = 0
    walkable_categories = 0
    
    for category_name, category_data in results.items():
        if "metrics" in category_data:
            # Count amenities within walking distance
            walking_count = sum(1 for feature in category_data.get("features", []) 
                               if feature.get("distance", float("inf")) <= 500)
            
            if walking_count > 0:
                walkable_amenities += walking_count
                walkable_categories += 1
    
    walkability_score = min(walkable_amenities + walkable_categories, 10)
    
    # Report completion
    await ctx.report_progress(len(categories), len(categories))
    
    return {
        "location": {
            "coordinates": {
                "latitude": latitude,
                "longitude": longitude
            },
            "address": address_info.get("display_name", "Unknown location")
        },
        "scores": {
            "overall": round(overall_score, 1),
            "walkability": walkability_score,
            "categories": {k: round(v, 1) for k, v in scores.items()}
        },
        "categories": results,
        "analysis_radius": radius,
        "timestamp": datetime.now().isoformat()
    }

@mcp.tool()
async def find_parking_facilities(
    latitude: float,
    longitude: float,
    ctx: Context,
    radius: float = 1000,
    parking_type: str = None  # e.g., "surface", "underground", "multi-storey"
) -> Dict[str, Any]:
    """
    Locate parking facilities near a specific location.
    
    This tool finds parking options (lots, garages, street parking) near a specified location.
    Results can be filtered by parking type and include capacity information where available.
    Useful for trip planning, city navigation, and evaluating parking availability in urban areas.
    
    Args:
        latitude: Center point latitude (decimal degrees)
        longitude: Center point longitude (decimal degrees)
        radius: Search radius in meters (defaults to 1000m/1km)
        parking_type: Optional filter for specific types of parking facilities
                     ("surface", "underground", "multi-storey", etc.)
        
    Returns:
        List of parking facilities with:
        - Name and type
        - Capacity information if available
        - Fee structure if available
        - Access restrictions
        - Distance from search point
    """
    osm_client = ctx.request_context.lifespan_context.osm_client
    
    # Convert radius to bounding box
    lat_delta = radius / 111000
    lon_delta = radius / (111000 * math.cos(math.radians(latitude)))
    
    bbox = (
        longitude - lon_delta,
        latitude - lat_delta,
        longitude + lon_delta,
        latitude + lat_delta
    )
    
    # Build Overpass query for parking facilities
    overpass_url = "https://overpass-api.de/api/interpreter"
    
    query = f"""
    [out:json];
    (
        node["amenity"="parking"]({{bbox}});
        way["amenity"="parking"]({{bbox}});
        relation["amenity"="parking"]({{bbox}});
    );
    out body;
    """
    
    query = query.replace("{bbox}", f"{bbox[1]},{bbox[0]},{bbox[3]},{bbox[2]}")
    
    async with aiohttp.ClientSession() as session:
        async with session.post(overpass_url, data={"data": query}) as response:
            if response.status == 200:
                data = await response.json()
                parking_facilities = data.get("elements", [])
            else:
                raise Exception(f"Failed to find parking facilities: {response.status}")
    
    # Process and filter results
    results = []
    for facility in parking_facilities:
        tags = facility.get("tags", {})
        
        # Filter by parking type if specified
        if parking_type and tags.get("parking", "") != parking_type:
            continue
        
        # Get coordinates based on feature type
        coords = {}
        if facility.get("type") == "node":
            coords = {
                "latitude": facility.get("lat"),
                "longitude": facility.get("lon")
            }
        elif "center" in facility:
            coords = {
                "latitude": facility.get("center", {}).get("lat"),
                "longitude": facility.get("center", {}).get("lon")
            }
        
        # Skip if no valid coordinates
        if not coords:
            continue
        
        # Calculate distance from search point
        from math import radians, sin, cos, sqrt, asin
        
        def haversine(lat1, lon1, lat2, lon2):
            R = 6371000  # Earth radius in meters
            dLat = radians(lat2 - lat1)
            dLon = radians(lon2 - lon1)
            a = sin(dLat/2)**2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dLon/2)**2
            c = 2 * asin(sqrt(a))
            return R * c
        
        distance = haversine(latitude, longitude, coords["latitude"], coords["longitude"])
        
        results.append({
            "id": facility.get("id"),
            "name": tags.get("name", "Unnamed Parking"),
            "type": tags.get("parking", "surface"),
            "coordinates": coords,
            "distance": round(distance, 1),
            "capacity": tags.get("capacity", "Unknown"),
            "fee": tags.get("fee", "Unknown"),
            "access": tags.get("access", "public"),
            "opening_hours": tags.get("opening_hours", "Unknown"),
            "levels": tags.get("levels", "1"),
            "address": {
                "street": tags.get("addr:street", ""),
                "housenumber": tags.get("addr:housenumber", ""),
                "city": tags.get("addr:city", ""),
                "postcode": tags.get("addr:postcode", "")
            },
            "tags": tags
        })
    
    # Sort by distance
    results.sort(key=lambda x: x["distance"])
    
    return {
        "query": {
            "latitude": latitude,
            "longitude": longitude,
            "radius": radius,
            "parking_type": parking_type
        },
        "parking_facilities": results,
        "count": len(results)
    }

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="OpenStreetMap MCP Server")
    parser.add_argument("--transport", default="stdio", choices=["stdio", "sse", "http"], help="Transport type (default: stdio)")
    parser.add_argument("--host", default="0.0.0.0", help="Host for HTTP transport (default: 0.0.0.0)")
    parser.add_argument("--port", type=int, default=8000, help="Port for HTTP transport (default: 8000)")
    
    args = parser.parse_args()
    
    if args.transport == "stdio":
        mcp.run(transport="stdio")
    else:
        mcp.run(transport=args.transport, host=args.host, port=args.port)