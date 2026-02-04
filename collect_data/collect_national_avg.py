import os
import requests
import pandas as pd
import duckdb
from datetime import datetime
from dotenv import load_dotenv , find_dotenv

# 1. 환경 변수 로드
load_dotenv(find_dotenv()) #상위폴더에서 env파일 참조
API_KEY = os.getenv('OPINET_API_KEY_1')
MINIO_ENDPOINT = os.getenv('MINIO_ENDPOINT')
MINIO_ACCESS_KEY = os.getenv('MINIO_ACCESS_KEY')
MINIO_SECRET_KEY = os.getenv('MINIO_SECRET_KEY')

def collect_national_avg_price():
    #2. API 호출 - JSON 형식
    url = f"https://www.opinet.co.kr/api/avgAllPrice.do?out=json&code={API_KEY}"

    response = requests.get(url)
    data = response.json()

    oil_list = data.get('RESULT', {}).get('OIL', [])
    df = pd.DataFrame(oil_list)
    now = datetime.now()
    #데이터 적재 시점 확인용
    df['collect_time'] = now.strftime('%Y-%m-%d %H:%M:%S') 
    #api에서 자동으로 호출하는 값이지만 이를 rename하고 이를 파티션키로 활용할 예정
    df = df.rename(columns={'TRADE_DT':'part_dt'}) 
    return df

def upload_to_minio(df):
    #1. Duckdb 연결 (파일없이 메모리에서 가볍게)
    con = duckdb.connect()
    con.execute("INSTALL httpfs; LOAD httpfs;")

    #2. .env에서 가져온 Minio설정값 로딩
    con.execute(f"SET s3_endpoint='{MINIO_ENDPOINT}';")
    con.execute(f"SET s3_access_key_id='{MINIO_ACCESS_KEY}';")
    con.execute(f"SET s3_secret_access_key='{MINIO_SECRET_KEY}';")
    con.execute("SET s3_url_style='path'; SET s3_use_ssl='false';")

    # 3. 데이터에 포함된 part_dt를 읽어 저장 경로 설정 (단층 구조)
    # iloc[0]은 데이터프레임의 첫 번째 행 값을 가져오라는 의미입니다.
    partition_date = df['part_dt'].iloc[0]
    path = f"s3://petroleum-project/national_avg/part_dt={partition_date}/data.parquet"

    # [누락된 핵심 코드]
    con.sql("SELECT * FROM df").write_parquet(path)
    print(f"--- [MinIO 완료] {partition_date} 데이터가 저장되었습니다. ---")


if __name__ == "__main__":
    try:
        # 1. 데이터 수집
        df = collect_national_avg_price()
        #print(df.head())
        
        # 2. 업로드
        upload_to_minio(df)
        
    except Exception as e:
        print(f" [에러] 작업 중 오류 발생: {e}")