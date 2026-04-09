import math
import pandas as pd
from pyproj import Transformer

def generate_nationwide_katec_grid(radius_km=5.0, overlap_ratio=0.75):
    """
    Generates a Nationwide Hexagonal grid using KATEC (meters) coordinates.
    Covers Dokdo (East), Baengnyeongdo (West), Goseong (North), Marado (South).
    """
    # 1. KATEC Transformer 설정 (WGS84 <-> KATEC)
    proj_katec = "+proj=tmerc +lat_0=38 +lon_0=128 +k=0.9999 +x_0=400000 +y_0=600000 +ellps=bessel +units=m +no_defs"
    # WGS84 to KATEC
    to_katec = Transformer.from_crs("epsg:4326", proj_katec, always_xy=True)
    # KATEC to WGS84 (for reverse conversion)
    to_wgs84 = Transformer.from_crs(proj_katec, "epsg:4326", always_xy=True)

    # 2. 극점 좌표 정의 (WGS84: Lon, Lat)
    extreme_points = {
        "North (Goseong)": (128.601, 38.614),
        "South (Marado)": (126.269, 33.111),
        "East (Dokdo)": (131.867, 37.242),
        "West (Baengnyeongdo)": (124.613, 37.962)
    }

    # KATEC 변환 후 Bounding Box 계산
    katec_points = [to_katec.transform(lon, lat) for lon, lat in extreme_points.values()]
    min_x = min(p[0] for p in katec_points)
    max_x = max(p[0] for p in katec_points)
    min_y = min(p[1] for p in katec_points)
    max_y = max(p[1] for p in katec_points)

    print(f"[LOG] KATEC Bounds: X({min_x:.0f} ~ {max_x:.0f}), Y({min_y:.0f} ~ {max_y:.0f})")

    # 3. 격자 파라미터 계산 (단위: 미터)
    diameter_m = radius_km * 2 * 1000
    stride_x = diameter_m * overlap_ratio
    stride_y = stride_x * (math.sqrt(3) / 2)
    
    grid = []
    
    # 4. 루프 생성 (Zigzag Hexagonal)
    current_y = min_y
    row_count = 0
    
    while current_y <= max_y + stride_y:
        offset_x = (stride_x / 2) if (row_count % 2 == 1) else 0
        current_x = min_x - offset_x # 충분히 왼쪽부터 시작
        
        while current_x <= max_x + stride_x:
            # KATEC -> WGS84 역변환
            lon, lat = to_wgs84.transform(current_x, current_y)
            
            grid.append({
                "katec_x": round(current_x, 2),
                "katec_y": round(current_y, 2),
                "lat": round(lat, 7),
                "lon": round(lon, 7)
            })
            current_x += stride_x
            
        current_y += stride_y
        row_count += 1

    return pd.DataFrame(grid)

if __name__ == "__main__":
    print("=== 전국 단위 KATEC 그리드 생성 (Whitelist 준비) ===")
    
    # 0.85 overlap_ratio 적용 (수학적 빈틈 없는 효율적 격자)
    df_grid = generate_nationwide_katec_grid(radius_km=5.0, overlap_ratio=0.85)
    
    print(f"\n[SUMMARY]")
    print(f"Total Grid Points: {len(df_grid):,}")
    print(f"Estimated API Calls (x4 fuel types): {len(df_grid) * 4:,}")
    
    # 샘플 출력
    print("\n[SAMPLE DATA]")
    print(df_grid.head())
    
    # 파일 저장
    output_path = "e:/ds_project/coordinates/nationwide_master_grid_katec.parquet"
    df_grid.to_parquet(output_path)
    print(f"\n[SAVE] 그리드 파일 저장 완료: {output_path}")
