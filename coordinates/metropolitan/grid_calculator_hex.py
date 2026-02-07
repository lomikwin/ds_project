import math

def generate_grid_coordinates(north, south, east, west, radius_km=5.0, overlap_ratio=0.866):
    """
    Generates a Hexagonal (Zigzag) grid of coordinates to cover a bounding box.
    
    Args:
        north, south, east, west: Bounding box coordinates
        radius_km: Search radius (e.g., 5km)
        overlap_ratio: Ratio of stride to diameter (0.85 is standard)
    """
    # 1. 기본 스트라이드(직선 거리) 계산
    diameter = radius_km * 2
    stride_km = diameter * overlap_ratio
    
    # 2. 육각 격자의 핵심: 수직 간격(v_stride)은 수평 간격보다 짧습니다.
    # 정육각형 배치에서 높이는 한쪽 변의 sqrt(3)/2 배이기 때문입니다 (~0.866)
    v_stride_km = stride_km * (math.sqrt(3) / 2)
    
    # 3. 위도/경도 각도 변환
    lat_stride = v_stride_km / 111.0
    avg_lat = (north + south) / 2.0
    lon_stride = stride_km / (111.0 * math.cos(math.radians(avg_lat)))
    
    coordinates = []
    current_lat = south
    row_count = 0
    
    while current_lat <= north + (lat_stride * 0.5): # 약간의 여유를 둠
        # 4. 육각 격자의 핵심: 홀수 번째 줄은 옆으로 반 칸(0.5) 밀어서 "지그재그"를 만듭니다.
        # 이렇게 해야 동그라미들이 서로 빈틈없이 맞물립니다.
        offset = (lon_stride / 2.0) if (row_count % 2 == 1) else 0.0
        
        current_lon = west - (lon_stride if offset > 0 else 0) # 왼쪽 끝 보정
        while current_lon <= east + (lon_stride * 0.5):
            # 영역 안에 들어오면 추가 (지그재그로 밀려나가는 것 방지)
            if current_lon >= west - (lon_stride * 0.5):
                coordinates.append((round(current_lat, 10), round(current_lon, 10)))
            current_lon += lon_stride
            
        current_lat += lat_stride
        row_count += 1
        
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

    # 1. Standard Grid (8.66km stride for 5km radius -> Hexagonal Limit)
    points_standard = generate_grid_coordinates(NORTH, SOUTH, EAST, WEST, radius_km=5.0, overlap_ratio=0.866)

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
