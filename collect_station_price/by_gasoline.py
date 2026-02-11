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



def by_gasoline(target_df ):
    
    #최적화된 좌표별로 api호출을 하고 이를 통해 주유소별 휘발유 가격 정보를 수집합니다.
    #prodcd: 유종 코드 (B027:휘발유, D047:경유, B034:고급휘발유, K015:LPG , C004:실내등유)
    
    by_station = []
    key_index = 5 #5번 키부터 사용시작
    null_cnt = 0
    first_failed_index = None
    target_df_filltered = target_df[target_df['is_gasoline_check']==1]
    i = 0
    while i < len(target_df_filltered):
        if i%100 == 0 :
            print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {i}번째 좌표에 대해서 호출 진행중.")
        row = target_df_filltered.iloc[i]
        success_flag = False
        oil_list = []
        try :
            while not success_flag and key_index >= 0:
                params = {
                    "code": os.getenv(OPINET_API_KEY_GROUP[key_index]),
                    "out": "json",
                    "x": row["katec_x"],
                    "y": row["katec_y"],
                    "radius": 5000,
                    "prodcd": "B027" , #"B027",  # 휘발유 기준 (경유는 D047)
                    "sort": 1          # 1: 가격순, 2: 거리순
                    }
                response = requests.get(url, params=params)
                response.raise_for_status() # 에러 발생 시 예외 처리
                data = response.json()
                api_call = data.get('RESULT',{}).get('OIL')

                if api_call != []: #성공
                    oil_list = api_call
                    success_flag = True # while 루프를 깨고 전진
                    null_cnt = 0
                    i += 1
                
                else :
                    null_cnt += 1
                    if null_cnt == 1 :
                        first_failed_index = i 
                    if null_cnt >= 10:
                        print (f"공백응답[] 10회 누적. API키를 교체합니다. {first_failed_index}번으로 돌아갑니다.")
                        key_index -= 1
                        null_cnt = 0
                        i = first_failed_index
                        break #새로운 키로 바로 찔러보도록 while loop 탈출
                    else:
                        print(f"[주의] {i}번째 좌표 공백 {null_cnt}/10")
                        success_flag = True
                        i += 1
            if key_index < 0:
                print("[주의]API키 전부 소진. 수집을 멈추고 저장합니다.")
                break
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
                    params["prodcd"], 
                    station["PRICE"]
                    ))
            
        except Exception as e:
            print(f"[ERROR] API 호출 중 오류 발생: {e}")
    columns =['katec_x' , 'katec_y' , #'dot_lat' , 'dot_lon' , 
              'uni_cd' , 'brand_cd',
            'station_name' , 'station_x' , 'station_y' , 'distance' , 'fuel_type' , 'price' ]
    final_result = pd.DataFrame(by_station , columns=columns)
    final_result = final_result.drop_duplicates(subset = 'uni_cd' , keep = 'first')
    

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
    table_name = "by_gasoline"
    path = f"s3://petroleum-project/{table_name}/part_dt={partition_date}/{file_name}"

    
    duckdb.sql("SELECT * FROM df").write_parquet(path)
    print(f"--- [MinIO 완료, ({datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {partition_date} 데이터가 저장되었습니다. ---")


if __name__ == "__main__":
    try:
        df = by_gasoline(target_coordinates) 
        
        if not df.empty:
            print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {len(df)}개의 주유소를 발견 업로드를 시작합니다")
            upload_to_minio(df)
        else:
            print("-------수집된 주유소가 없습니다. 업로드를 건너뜁니다------")
        
        
    except Exception as e:
        print(f" [에러] 작업 중 오류 발생: {e}")