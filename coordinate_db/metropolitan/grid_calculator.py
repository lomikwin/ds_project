import math

def generate_grid_coordinates(north, south, east, west, radius_km=5.0, overlap_ratio=0.8):
    """
    Generates a grid of coordinates to cover a bounding box.
    
    Args:
        north (float): Northernmost latitude
        south (float): Southernmost latitude
        east (float): Easternmost longitude
        west (float): Westernmost longitude
        radius_km (float): Radius of coverage for each point (default 5km)
        overlap_ratio (float): Ratio of non-overlap stride to diameter. 
                               0.8 means stride is 0.8 * diameter = 0.8 * 10km = 8km.
                               Lower value means more overlap (safer coverage).
    """
    # Earth radius approximation
    R = 6371.0
    
    # Grid stride calculation
    diameter = radius_km * 2
    stride_km = diameter * overlap_ratio
    
    # Convert stride to degrees (approximation)
    # 1 deg latitude ~= 111 km
    lat_stride = stride_km / 111.0
    
    # 1 deg longitude ~= 111 * cos(lat) km
    # Use average latitude for longitude stride calculation
    avg_lat = (north + south) / 2.0
    lon_stride = stride_km / (111.0 * math.cos(math.radians(avg_lat)))
    
    coordinates = []
    
    current_lat = south
    while current_lat <= north + lat_stride: # Ensure we cover the northern edge
        current_lon = west
        while current_lon <= east + lon_stride: # Ensure we cover the eastern edge
            coordinates.append((round(current_lat, 5), round(current_lon, 5)))
            current_lon += lon_stride
        current_lat += lat_stride
        
    return coordinates

# 이 파일의 핵심 함수를 다른 곳에서 가져다 쓰기 위해,
# 실행 로드맵(테스트 코드)은 아래 if __name__ == "__main__": 블록 안에 넣습니다.
if __name__ == "__main__":
    # Bounding Box for Capital Area (Seoul + Gyeonggi + Incheon Mainland)
    # Excluded Baengnyeong-do to avoid ocean waste.
    NORTH = 38.30   # Yeoncheon
    SOUTH = 36.87   # Anseong
    EAST = 127.83   # Yangpyeong
    WEST = 126.20   # Incheon/Ganghwa (Mainland approx)

    # 1. Standard Grid (8km stride for 5km radius -> Safe Overlap)
    points_standard = generate_grid_coordinates(NORTH, SOUTH, EAST, WEST, radius_km=5.0, overlap_ratio=0.85)

    # 2. Dense Grid (7km stride for 5km radius -> Very Safe Overlap)
    points_dense = generate_grid_coordinates(NORTH, SOUTH, EAST, WEST, radius_km=5.0, overlap_ratio=0.7)

    print(f"--- Configuration ---")
    print(f"Bounding Box: N{NORTH}, S{SOUTH}, E{EAST}, W{WEST}")
    print(f"Target Radius: 5km")
    print(f"\n--- Result: Standard Grid (Stride ~8.5km) ---")
    print(f"Total Points: {len(points_standard)}")
    print(f"Daily API Calls (x4 fuel types): {len(points_standard) * 4}")

    print(f"\n--- Result: Dense Grid (Stride ~7km) ---")
    print(f"Total Points: {len(points_dense)}")
    print(f"Daily API Calls (x4 fuel types): {len(points_dense) * 4}")

    print(f"\n--- Sample Coordinates (First 5) ---")
    for p in points_standard[:5]:
        print(p)
