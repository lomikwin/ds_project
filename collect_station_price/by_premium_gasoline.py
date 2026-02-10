import pandas as pd 
import pyarrow
import duckdb
import os
import requests
from datetime import datetime
from dotenv import load_dotenv , find_dotenv


# 1. 환경 변수 로드
load_dotenv(find_dotenv())
OPINET_API_KEY_GROUP = ['OPINET_API_KEY_1', 'OPINET_API_KEY_2', 'OPINET_API_KEY_3', 
                        'OPINET_API_KEY_4', 'OPINET_API_KEY_5', 'OPINET_API_KEY_6' ] # OPINET_API_KEY가 여러개로 늘어날 수도 있으니까 list로 관리
# API_KEY = os.getenv('OPINET_API_KEY_1') --> 이건 이제 동적변수가 되어야 하므로 함수 안으로 집어넣기
MINIO_ENDPOINT = os.getenv('MINIO_ENDPOINT') 
MINIO_ACCESS_KEY = os.getenv('MINIO_ACCESS_KEY')
MINIO_SECRET_KEY = os.getenv('MINIO_SECRET_KEY')


#2. duckdb를 통한 s3 읽기 설정
duckdb.execute("INSTALL httpfs; LOAD httpfs;")
duckdb.execute(f"SET s3_endpoint='{MINIO_ENDPOINT}';")
duckdb.execute(f"SET s3_access_key_id='{MINIO_ACCESS_KEY}';")
duckdb.execute(f"SET s3_secret_access_key='{MINIO_SECRET_KEY}';")
duckdb.execute("SET s3_url_style='path'; SET s3_use_ssl='false';")

#3. API 기본 호출 URL
url = "https://www.opinet.co.kr/api/aroundAll.do"

# 일배치를 통해 동적으로 변화하는 마스터 테이블의 s3 경로
target_coordinates_path = "s3://petroleum-project/target_coordinates/target_coordinates.parquet"
target_coordinates = duckdb.read_parquet(target_coordinates_path).df()



def by_premium_gasoline(target_df ):
    
    #최적화된 좌표별로 api호출을 하고 이를 통해 주유소별 고급휘발유 가격 정보를 수집합니다.
    #prodcd: 유종 코드 (B027:휘발유, D047:경유, B034:고급휘발유, K015:LPG , C004:실내등유)
    
    by_station = []
    key_index = 5 #5번 키부터 사용시작

    for i , (index, row) in enumerate(target_df[target_df['is_premium_gasoline_check']==1].iterrows()) : #target_coordinates 폴더에서 check가 1인 좌표만 탐색
        # 이 부분은 다른 로직과 상관없이 걍 step 표기용 부분.
        if i%100 == 0:
            print(f"[{datetime.now().strftime('%H:%M:%S')}]: {i}번째 Dot의 주유소를 수집중입니다.")
        # API 호출횟수가 초과하면 그 에러값을 바탕으로 API키 교체
        success_flag = False
        oil_list = []
        try:
            while not success_flag and key_index>= 0:
                    params = {
                    "code": os.getenv(OPINET_API_KEY_GROUP[key_index]),
                    "out": "json",
                    "x": row["katec_x"],
                    "y": row["katec_y"],
                    "radius": 5000,
                    "prodcd": "B034" , #"B027",  # 휘발유 기준 (경유는 D047)
                    "sort": 1          # 1: 가격순, 2: 거리순
                    }
                    response = requests.get(url, params=params)
                    response.raise_for_status() # 에러 발생 시 예외 처리
                    data = response.json()
                    message = data.get('RESULT',{}).get('MESSAGE')
                
                    if message and "한도" in message :
                        print("한도 초과 키를 교체합니다")
                        key_index -= 1
                        continue
                    else:
                        oil_list = data.get('RESULT', {}).get('OIL', [])
                        success_flag = True
            
            for station in oil_list:
                by_station.append ((
                    row["katec_x"] , 
                    row["katec_y"] , 
                    #row["lat"], 정규화차원에서 lat, lon 정보는 생략
                    #row["lon"],
                    station["UNI_ID"],
                    station["POLL_DIV_CD"],
                    station["OS_NM"],
                    station["GIS_X_COOR"],
                    station["GIS_Y_COOR"],
                    station["DISTANCE"],
                    params["prodcd"], # 나중에 함수로 만들때는 이걸 인자로 넣도록 하고, 일단 api호출값에서는 이 prodcd가 없어서 이걸 수기로 테이블에 넣는 방법을 택했다.
                    station["PRICE"]
                    ))
        except Exception as e:
            print(f"[ERROR] API 호출 중 오류 발생: {e}")
    columns =['katec_x' , 'katec_y' , #'dot_lat' , 'dot_lon' , 
              'uni_cd' , 'brand_cd',
            'station_name' , 'station_x' , 'station_y' , 'distance' , 'fuel_type' , 'price' ]
    final_result = pd.DataFrame(by_station , columns=columns)
    

    now = datetime.now()
    final_result['collect_time'] = now.strftime('%Y-%m-%d %H:%M:%S') 
    final_result['part_dt'] = now.strftime('%Y%m%d')
    final_result = final_result[['part_dt' , 'katec_x' , 'katec_y' , #'dot_lat', 'dot_lon' ,
                                'uni_cd' , 'brand_cd','station_name' , 
                                'station_x' , 'station_y' ,'distance', 'fuel_type' , 'price' ,'collect_time']]

    return final_result

def upload_to_minio(df):
    partition_date = df['part_dt'].iloc[0]
    timestamp = datetime.now().strftime('%H%M%S')
    file_name = f"data_{timestamp}.parquet"
    table_name = "by_premium_gasoline"
    path = f"s3://petroleum-project/{table_name}/part_dt={partition_date}/{file_name}"

    
    duckdb.sql("SELECT * FROM df").write_parquet(path)
    print(f"--- [MinIO 완료] {partition_date} 데이터가 저장되었습니다. ---")


if __name__ == "__main__":
    try:
        df = by_premium_gasoline(target_coordinates) 
        
        if not df.empty:
            print(f"---{len(df)}개의 주유소를 발견 업로드를 시작합니다")
            upload_to_minio(df)
        else:
            print("-------수집된 주유소가 없습니다. 업로드를 건너뜁니다------")
        
        
    except Exception as e:
        print(f" [에러] 작업 중 오류 발생: {e}")