import pandas as pd 
import pyarrow
import duckdb
import os
import requests
from datetime import datetime, timedelta
from dotenv import load_dotenv , find_dotenv
import io 

#1. API 기본 호출 URL , curl을 통한 확인 완료
url = "https://www.opinet.co.kr/glopcoil_csv.do"


now= datetime.now()  #오늘날짜 
tg_dt = now  - timedelta(days=1) #이 날짜는 사실 전일자가 되어야 함. 이 코드는 매일 새벽에 돌 것이고 전일자를 수집하는 것이 목표
data_raw = {
    "TERM":"D",
    "STA_Y": tg_dt.strftime('%Y'),
    "STA_M": tg_dt.strftime('%m'),
    "STA_W": "1",
    "STA_D":tg_dt.strftime('%d'),
    "END_Y":tg_dt.strftime('%Y'), #now.strftime('%Y'),#
    "END_M":tg_dt.strftime('%m'),#now.strftime('%m'),#
    "END_W": "1",
    "END_D":tg_dt.strftime('%d'),#now.strftime('%d'),
    "OILSRTCD1":"001",
    "OILSRTCD2":"002",
    "OILSRTCD3":"003",
    "STDDATE":tg_dt.strftime('%Y%m%d'),
    "ENDDATE":tg_dt.strftime('%Y%m%d'),
    "SEL_DIV":["div_dar","div_won"] , 
    "OILSRTCD":["001","002","003"] 
}
#2. 결과 획득
response = requests.post(url, data=data_raw)
#3. 크롤링 결과 정제 및 저장
df = pd.read_csv(io.BytesIO(response.content), encoding='cp949')
print(df)
df['part_dt'] = pd.to_datetime(df['기간'],format='%y년%m월%d일')
df = df[['part_dt','Dubai' , 'Brent' , 'WTI' ]]


# 4. minio s3에 저장하기 위한 설정값 로드
load_dotenv(find_dotenv())
MINIO_ENDPOINT = os.getenv('MINIO_ENDPOINT') 
MINIO_ACCESS_KEY = os.getenv('MINIO_ACCESS_KEY')
MINIO_SECRET_KEY = os.getenv('MINIO_SECRET_KEY')


# 5. duckdb를 통한 s3 읽기 설정
duckdb.execute("INSTALL httpfs; LOAD httpfs;")
duckdb.execute(f"SET s3_endpoint='{MINIO_ENDPOINT}';")
duckdb.execute(f"SET s3_access_key_id='{MINIO_ACCESS_KEY}';")
duckdb.execute(f"SET s3_secret_access_key='{MINIO_SECRET_KEY}';")
duckdb.execute("SET s3_url_style='path'; SET s3_use_ssl='false';")



#7. 결과 분기 저장.
try:
    if not df.empty:
        partition_date = df['part_dt'].iloc[0].strftime('%Y-%m-%d')
        timestamp = datetime.now().strftime('%H%M%S')
        file_name = f"data_{timestamp}.parquet"
        table_name = "macro_indicator"
        path = f"s3://petroleum-project/{table_name}/part_dt={partition_date}/{file_name}"
        print(f"[{tg_dt.strftime('%Y-%m-%d')}] 의 원유 가격 정보를 수집하여 저장합니다.")
        duckdb.sql("SELECT * FROM df").write_parquet(path)
    else:
        print("-------수집된 원유 가격정보가 없습니다. 업로드를 건너뜁니다------")
except Exception as e:
    print(f" [에러] 작업 중 오류 발생: {e}")
duckdb.sql("SELECT * FROM df").write_parquet(path)
print(f"--- [MinIO 완료, ({datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {partition_date} 데이터가 저장되었습니다. ---")




# if __name__ == "__main__":
#     try:
#         if not df.empty:
#             print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 의 원유 가격 정보를 수집하여 저장합니다.")
#             upload_to_minio(df)
#         else:
#             print("-------수집된 원유 가격정보가 없습니다. 업로드를 건너뜁니다------")
        
        
#     except Exception as e:
#         print(f" [에러] 작업 중 오류 발생: {e}")