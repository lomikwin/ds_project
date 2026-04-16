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
params_1 = {
            "code": API_KEY,
            "out": "json",
        }
respon_1 = requests.get(url, params=params_1)
respon_1.raise_for_status() # 에러 발생 시 예외 처리
data = respon_1.json()
area_code_list = data.get('RESULT', {}).get('OIL', [])
if area_code_list:
    for i in area_code_list:
        area_code.append((
            1,
            i['AREA_CD'],
            i['AREA_NM'],
            None,
            None,
        ))
for area in area_code_list:
    params_2 = {
                "code": API_KEY,
                "out": "json",
                "area": area['AREA_CD'],
            }
    respon_2 = requests.get(url, params=params_2)
    respon_2.raise_for_status() # 에러 발생 시 예외 처리
    data = respon_2.json()
    area_code_list = data.get('RESULT', {}).get('OIL', [])
    for i in area_code_list:
        area_code.append((
            2,
            i['AREA_CD'],
            i['AREA_NM'],
            area['AREA_CD'],
            area['AREA_NM'],
        ))
cl_list = ['AREA_DEPTH' , 'AREA_CD' , 'AREA_NM' ,'UPPER_CD' ,'UPPER_NM']
area_df = pd.DataFrame(area_code, columns = cl_list)
now = datetime.now()
area_df['part_dt'] = now.strftime('%Y%m%d')
timestamp = datetime.now().strftime('%Y%m%d %H%M%S')
file_name = f"data_{timestamp}.parquet"
path = f"s3://petroleum-project/station_metadata/area_code/{file_name}"
con.sql("SELECT * FROM area_df").write_parquet(path)

print( f"MINIO UPLOAD 완료: {len(area_df)}개의 지역정보 업로드 완료.")


