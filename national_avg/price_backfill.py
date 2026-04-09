import os
import requests
import pandas as pd
import duckdb
from datetime import datetime
from dotenv import load_dotenv , find_dotenv

# 1. 환경 변수 로드
load_dotenv(find_dotenv()) #상위폴더에서 env파일 참조
API_KEY = os.getenv('OPINET_API_KEY_4')
MINIO_ENDPOINT = os.getenv('MINIO_ENDPOINT')
MINIO_ACCESS_KEY = os.getenv('MINIO_ACCESS_KEY')
MINIO_SECRET_KEY = os.getenv('MINIO_SECRET_KEY')

def collect_national_avg_price_backfill(stt_dt ,end_dt ):
    dates = pd.date_range(start=f'{stt_dt}' , end=f'{end_dt}', freq = '7D')
    # 이 dates를 리스트로 변환. 위의 dates는 DatetimeIndex(나 처음 들어보는 타입임) 라서 append가 안된다고 한다. 그래서 리스트화를 먼저 진행.
    dates_list = dates.tolist()

    #우리는 pd.date_range 를 사용해서 7일 주기의 리스트를 만들었기 때문에  end_dt가 딱 안떨어지면 빠질 수가 있다.
    #한편 우리가 end_dt만 넣어도 api에서 그 이전 7일의 값을 뱉어내주기 때문에 end_dt만 박아주면 된다. 
    #그러면 일부 중복값이 생길텐데 그건 훗단에서 없애주자. 
    if dates_list[-1].strftime('%Y%m%d') != end_dt: 
        dates_list.append(pd.Timestamp(end_dt))    

    backfill =[]
    for i, d in enumerate(dates_list) :
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
    final_combined_df = pd.concat(backfill).drop_duplicates(subset = ['part_dt','PRODCD'])
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
    partition_date = final_combined_df['part_dt'].iloc[0]
    
    # [핵심 수정] 통째로 덮어쓰는(overwrite) 대신, "한 땀 한 땀" 파티션별로 나누어 저장합니다.
    # 이렇게 하면 기존에 있던 다른 날짜의 폴더들(20260124 등)은 건드리지 않고,
    # 우리가 수집한 날짜의 폴더만 쏙쏙 골라서 새로 만들거나 교체(overwrite)합니다.
    
    # 1. 수집된 데이터에서 유니크한 날짜 목록을 뽑습니다.
    unique_dates = final_combined_df['part_dt'].unique()
    
    print(f"--- 총 {len(unique_dates)}개의 일자별 데이터를 MinIO에 안전하게 병합합니다... ---")
    
    for date_val in unique_dates:
        # 해당 날짜의 데이터만 필터링
        daily_df = final_combined_df[final_combined_df['part_dt'] == date_val]
        
        # 쿼리는 그대로 쓰되, WHERE 절로 한 번 더 확실하게 필터링해서 씁니다.
        # 경로를 '루트'가 아니라 '해당 날짜 폴더'까지 직접 지정해 줍니다.
        # 예: s3://petroleum-project/national_avg/part_dt=20000107/data.parquet
        target_path = f"s3://petroleum-project/national_avg/price/part_dt={date_val}/data.parquet"
        
        con.sql(f"""
            SELECT 
                part_dt,
                PRODCD,
                CASE 
                    WHEN PRODCD = 'B027' THEN '휘발유'
                    WHEN PRODCD = 'D047' THEN '자동차용경유'
                    WHEN PRODCD = 'B034' THEN '고급휘발유'
                    WHEN PRODCD = 'K015' THEN '자동차용부탄'
                    WHEN PRODCD = 'C004' THEN '실내등유'
                END AS PRODNM,
                PRICE,
                round(PRICE - LAG(PRICE) over (partition by PRODCD order by part_dt),2) as DIFF,
                collect_time
            FROM daily_df
        """).write_parquet(target_path) # 여기선 overwrite 안 써도 됩니다(파일 단위라 충돌 나면 덮어씀)
        
    print(f"--- [MinIO 완료] 기존 데이터 보존 완료! 안전하게 백필이 끝났습니다. ---")


if __name__ == "__main__":
    try:
        # 1. 데이터 수집
        df = collect_national_avg_price_backfill('20000107' , '20260123')
        #print(df.head())
        
        # 2. 업로드
        upload_to_minio_backfill(df)
        
    except Exception as e:
        print(f" [에러] 작업 중 오류 발생: {e}")