import pandas as pd 
import pyarrow
import duckdb
import os
import requests
from datetime import datetime
from dotenv import load_dotenv , find_dotenv


# 1. 환경 변수 로드
load_dotenv(find_dotenv())
API_KEY = os.getenv('OPINET_API_KEY_1') #--> 이건 이제 동적변수가 되어야 하므로 함수 안으로 집어넣기
MINIO_ENDPOINT = os.getenv('MINIO_ENDPOINT') 
MINIO_ACCESS_KEY = os.getenv('MINIO_ACCESS_KEY')
MINIO_SECRET_KEY = os.getenv('MINIO_SECRET_KEY')


#2. duckdb를 통한 s3 읽기 설정
con = duckdb.connect()
con.execute("INSTALL httpfs; LOAD httpfs;")
con.execute(f"SET s3_endpoint='{MINIO_ENDPOINT}';")
con.execute(f"SET s3_access_key_id='{MINIO_ACCESS_KEY}';")
con.execute(f"SET s3_secret_access_key='{MINIO_SECRET_KEY}';")
con.execute("SET s3_url_style='path'; SET s3_use_ssl='false';")


#3. API 기본 호출 URL
url = "https://www.opinet.co.kr/api/areaCode.do"

area_code = []
params = {
            "code": API_KEY,
            "out": "json",
            
        }
try:
    response = requests.get(url, params=params)
    response.raise_for_status() # 에러 발생 시 예외 처리
    data = response.json()

    area_code_list = data.get('RESULT', {}).get('OIL', [])
    if area_code_list:
        for i in area_code_list:
            area_code.append((
                1,
                i['AREA_CD'],
                i['AREA_NM'],
            ))
    cl_list = ['AREA_LEVEL' , 'AREA_CD' , 'AREA_NM' ]
    area_df = pd.DataFrame(area_code, columns = cl_list)
    now = datetime.now()
    area_df['part_dt'] = now.strftime('%Y%m%d')
    timestamp = datetime.now().strftime('%Y%m%d %H%M%S')
    file_name = f"data_{timestamp}.parquet"
    path = f"s3://petroleum-project/station_metadata/area_code/{file_name}"
    con.sql("SELECT * FROM area_df").write_parquet(path)
    n_list = []
    for n in range(1, 19):
        n_list.append(str(n).rjust(2,"0"))
    for n_r in n_list:
        area_code = []
        params = {
                "code": API_KEY,
                "out": "json",
                "area": n_r,
            }
        try:
            response = requests.get(url, params=params)
            response.raise_for_status() # 에러 발생 시 예외 처리
            data = response.json()

            area_code_list = data.get('RESULT', {}).get('OIL', [])
            if area_code_list:
                for i in area_code_list:
                    area_code.append((
                        2,
                        i['AREA_CD'],
                        i['AREA_NM'],
                    ))
            cl_list = ['AREA_LEVEL' , 'AREA_CD' , 'AREA_NM'  ]
            area_df = pd.DataFrame(area_code, columns = cl_list)
            now = datetime.now()
            area_df['part_dt'] = now.strftime('%Y%m%d')
            timestamp = datetime.now().strftime('%Y%m%d %H%M%S')
            file_name = f"data_{n_r}_{timestamp}.parquet"
            path = f"s3://petroleum-project/station_metadata/area_code/{file_name}"
            con.sql("SELECT * FROM area_df").write_parquet(path)
        except Exception as e:
            print(f"[ERROR] API 호출 중 오류 발생: {e}")
except Exception as e:
    print(f"[ERROR] API 호출 중 오류 발생: {e}")



