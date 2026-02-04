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

def collect_national_avg_price_backfill(stt_dt ,end_dt ):
    dates = pd.date_range(start=f'{stt_dt}' , end=f'{end_dt}', freq = '7D')
    backfill =[]
    for i, d in enumerate(dates) :
        target_date = d.strftime('%Y%m%d')
        url = f"https://www.opinet.co.kr/api/dateAvgRecentPrice.do?out=json&code={API_KEY}&date={target_date}"

        response = requests.get(url)
        data = response.json()

        oil_list = data.get('RESULT', {}).get('OIL', [])
        df = pd.DataFrame(oil_list)
        now = datetime.now()
    #데이터 적재 시점 확인용
        df['collect_time'] = now.strftime('%Y-%m-%d %H:%M:%S') 
    
        df = df.rename(columns={'DATE':'part_dt'})
        backfill.append(df) 
        if(i+1) % 50 ==0:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] {i+1}번째 주차 데이터 수집중 --> ({target_date})")
    final_combined_df = pd.concat(backfill)
    return final_combined_df

def upload_to_minio_backfill(final_combined_df):
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
    
    con.sql("""
            SELECT 
                part_dt,
                prodcd,
                CASE 
                    WHEN prodcd = 'B027' THEN '휘발유'
                    WHEN prodcd = 'D047' THEN '자동차용경유'
                    WHEN prodcd = 'B034' THEN '고급휘발유'
                    WHEN prodcd = 'K015' THEN '자동차용부탄'
                    WHEN prodcd = 'C004' THEN '실내등유'
                END AS prodnm,
                price,
                round(price - LAG(price) over (partition by prodcd order by part_dt),2) as diff,
                collect_time
            FROM final_combined_df
            """).write_parquet("s3://petroleum-project/national_avg/", partition_by = ["part_dt"])
    print(f"--- [MinIO 완료] 전국 평균 백필 데이터가 저장되었습니다. ---")


if __name__ == "__main__":
    try:
        # 1. 데이터 수집
        df = collect_national_avg_price_backfill('20000107' , '20100109')
        #print(df.head())
        
        # 2. 업로드
        upload_to_minio_backfill(df)
        
    except Exception as e:
        print(f" [에러] 작업 중 오류 발생: {e}")