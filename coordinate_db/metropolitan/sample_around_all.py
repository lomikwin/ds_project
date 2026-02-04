import os
import requests
from pyproj import Transformer
from dotenv import load_dotenv , find_dotenv

# .env 파일에서 API 키 로드
load_dotenv(find_dotenv())
API_KEY = os.getenv('OPINET_API_KEY_1')

def test_gas_station_collection(lat, lon, radius=10000):
    """
    특정 위경도 좌표를 기준으로 반경 내 주유소 정보를 수집하는 샘플 함수
    """
    
    # 1. 좌표 변환기 설정 (WGS84 위경도 -> KATEC 좌표계)
    # 오피넷 KATEC 정의 (Bessel 기반 TM128 방식)
    proj_katec = "+proj=tmerc +lat_0=38 +lon_0=128 +k=0.9999 +x_0=400000 +y_0=600000 +ellps=bessel +units=m +no_defs"
    
    # pyproj Transformer 생성 (always_xy=True로 설정하면 항상 경도, 위도 순서로 입력받음)
    transformer = Transformer.from_crs("epsg:4326", proj_katec, always_xy=True)
    
    # 위경도 -> KATEC 변환
    # 변환 시 lon(경도)가 X축, lat(위도)가 Y축 역할을 합니다.
    katec_x, katec_y = transformer.transform(lon, lat)
    
    print(f"[LOG] 변환 완료: WGS84({lat}, {lon}) -> KATEC({katec_x:.2f}, {katec_y:.2f})")

    # 2. 오피넷 반경 내 주유소 검색 API 호출
    url = "https://www.opinet.co.kr/api/aroundAll.do"
    params = {
        "code": API_KEY,
        "out": "json",
        "x": katec_x,
        "y": katec_y,
        "radius": radius,
        "prodcd": "" , #"B027",  # 휘발유 기준 (경유는 D047)
        "sort": 1          # 1: 가격순, 2: 거리순
    }

    try:
        response = requests.get(url, params=params)
        response.raise_for_status() # 에러 발생 시 예외 처리
        data = response.json()
        
        # 3. 결과 출력 및 검증
        oil_list = data.get('RESULT', {}).get('OIL', [])
        
        if not oil_list:
            print("[WARN] 해당 반경 내에 수집된 주유소가 없습니다.")
            return
            
        print(f"\n--- 수집 결과 (총 {len(oil_list)}개 중 전체) ---")
        for i, oil in enumerate(oil_list):
            print(f"{i+1}. [{oil['OS_NM']}]")
            print(f"   가격: {oil['PRICE']}원 / 거리: {oil['DISTANCE']}m")
            print(f"   주유소ID: {oil['UNI_ID']}")
            
    except Exception as e:
        print(f"[ERROR] API 호출 중 오류 발생: {e}")

if __name__ == "__main__":
    # 사고 실험에서 다뤘던 '송파구청' 좌표 예시
    songpa_lat, songpa_lon = 37.51447, 127.10595
    
    print("=== 오피넷 API 반경 검색 테스트 ===")
    test_gas_station_collection(songpa_lat, songpa_lon)
