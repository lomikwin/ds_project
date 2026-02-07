### No need to make this very simmilar py file. But for saving history. I duplicated py file for only collecting white list dots for LPG
import pandas as pd 
import pyarrow
import duckdb
import os
import requests
from datetime import datetime
from dotenv import load_dotenv , find_dotenv


# 1. 환경 변수 로드
load_dotenv(find_dotenv())
API_KEY = os.getenv('OPINET_API_KEY_4')
MINIO_ENDPOINT = os.getenv('MINIO_ENDPOINT')
MINIO_ACCESS_KEY = os.getenv('MINIO_ACCESS_KEY')
MINIO_SECRET_KEY = os.getenv('MINIO_SECRET_KEY')

# API 기본 호출 URL
url = "https://www.opinet.co.kr/api/aroundAll.do"
#os 라이브러리를 활용하여, geographic_master_table.parquet의 절대 경로를 찾음.
base_path = os.path.dirname(os.path.abspath(__file__))

# 이 절대경로에다가 ~.parquet 파일을 붙여서 경로를 만듬
master_table_path = os.path.join(base_path, "nationwide_master_grid_katec.parquet")

master_table = duckdb.read_parquet(master_table_path).df()

#이제 API키를 2개를 갖고 내가 돌려가면서 써볼것이기에 이 부분을 미리 사전에 반영해둠. 

def collect_by_gasstation(target_df , prodcd="B027"):
    """
    주유소별 가격 정보를 수집합니다.
    - prodcd: 유종 코드 (B027:휘발유, D047:경유, B034:고급휘발유, K015:LPG , C004:실내등유)

    """
    by_gasstation = []
    
    for i , (index, row) in enumerate(target_df.iterrows()) : #enumerate라는 것은 처음 배우는데 for 루프를 돌때 바퀴수를 말해주는 함수라고 한다. 
        # # 한도 초과시 강제로 break
        # if i >= limit:
        #     print (f"---- 사전 설정한 한도 {limit}회를 초과하여 강제 종료합니다.----")
        #     break
        # 진행율 표기 --> 100개마다
        if i%100 == 0:
            print(f"[{datetime.now().strftime('%H:%M:%S')}]: {i}번째 Dot의 주유소를 수집중입니다.")
        params = {
            "code": API_KEY,
            "out": "json",
            "x": row["katec_x"],
            "y": row["katec_y"],
            "radius": 5000,
            "prodcd": prodcd , #"B027",  # 휘발유 기준 (경유는 D047)
            "sort": 1          # 1: 가격순, 2: 거리순
        }
        try:
            response = requests.get(url, params=params)
            response.raise_for_status() # 에러 발생 시 예외 처리
            data = response.json()
        
            oil_list = data.get('RESULT', {}).get('OIL', [])
            #print(f"   -> 검색 결과 {len(oil_list)}개 발견!")

            for station in oil_list:
                by_gasstation.append ((
                    row["katec_x"] , 
                    row["katec_y"] , 
                    row["lat"],
                    row["lon"],
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
    columns =['katec_x' , 'katec_y' , 'dot_lat' , 'dot_lon' , 'uni_cd' , 'brand_cd',
            'station_name' , 'station_x' , 'station_y' , 'distance' , 'fuel_type' , 'price' ]
    final_result = pd.DataFrame(by_gasstation , columns=columns)
    #주유소 A에 대해서 dot_1 , dot_2가 모두 커버가 될때 dot_1의 주유소 개수가 적으면 이걸 dot_2가 커버하도록 만들어볼 예정
    #이렇게 하면 애매하게 1개만 걸리는 dot_을 모두 0으로 만들어 api콜수를 줄일수도 있다.
    #final_result = final_result.drop_duplicates(subset='uni_cd') 
    now = datetime.now()
    final_result['collect_time'] = now.strftime('%Y-%m-%d %H:%M:%S') 
    final_result['part_dt'] = now.strftime('%Y%m%d')
    final_result = final_result[['part_dt' , 'katec_x' , 'katec_y' , 'dot_lat', 'dot_lon' ,'uni_cd' , 'brand_cd','station_name' , 
                                'station_x' , 'station_y' ,'distance', 'fuel_type' , 'price' ,'collect_time']]

    return final_result

def upload_to_minio(df):
    
    con = duckdb.connect()
    con.execute("INSTALL httpfs; LOAD httpfs;")

    #2. .env에서 가져온 Minio설정값 로딩
    con.execute(f"SET s3_endpoint='{MINIO_ENDPOINT}';")
    con.execute(f"SET s3_access_key_id='{MINIO_ACCESS_KEY}';")
    con.execute(f"SET s3_secret_access_key='{MINIO_SECRET_KEY}';")
    con.execute("SET s3_url_style='path'; SET s3_use_ssl='false';")

    partition_date = df['part_dt'].iloc[0]
    timestamp = datetime.now().strftime('%H%M%S')
    file_name = f"data_{timestamp}.parquet"
    path = f"s3://petroleum-project/coord_validation_logs/part_dt={partition_date}/{file_name}"

    
    con.sql("SELECT * FROM df").write_parquet(path)
    print(f"--- [MinIO 완료] {partition_date} 데이터가 저장되었습니다. ---")


if __name__ == "__main__":
    try:
        #==============수동으로 API키를 돌리기 위해 새로 세팅한 영역============
        START_1 = 4500
        END_1 = 5900
        #START_2 = 5900
        #END_2 = 6500
        #=================================================================
        api_key1_cover = master_table.iloc[START_1:END_1]
        #api_key2_cover = master_table.iloc[START_2:END_2]
        print(f"--- [모드 변경] 자동차용부탄(K015) Nationwide 수색을 시작합니다 ({START_1}~{END_1}) ---")
        df = collect_by_gasstation(api_key1_cover , prodcd='K015') #api_key1_cover) #(api_key2_cover)
        
        if not df.empty:
            print(f"---{len(df)}개의 주유소를 발견 업로드를 시작합니다")
            upload_to_minio(df)
        else:
            print("-------집된 주유소가 없습니다. 업로드를 건너뜁니다------")
        
        
    except Exception as e:
        print(f" [에러] 작업 중 오류 발생: {e}")