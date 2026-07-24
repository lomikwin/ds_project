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

# 2. minio s3에 저장하기 위한 설정값 로드
load_dotenv(find_dotenv())
MINIO_ENDPOINT = os.getenv('MINIO_ENDPOINT') 
MINIO_ACCESS_KEY = os.getenv('MINIO_ACCESS_KEY')
MINIO_SECRET_KEY = os.getenv('MINIO_SECRET_KEY')

# 3. duckdb를 통한 s3 읽기 설정
duckdb.execute("INSTALL httpfs; LOAD httpfs;")
duckdb.execute(f"SET s3_endpoint='{MINIO_ENDPOINT}';")
duckdb.execute(f"SET s3_access_key_id='{MINIO_ACCESS_KEY}';")
duckdb.execute(f"SET s3_secret_access_key='{MINIO_SECRET_KEY}';")
duckdb.execute("SET s3_url_style='path'; SET s3_use_ssl='false';")




def gather_crude_oil_price(stt_dt, end_dt, currency = "USD"):
    stt_dt = datetime.strptime(stt_dt,'%Y%m%d')
    end_dt = datetime.strptime(end_dt,'%Y%m%d')
    #now= datetime.now()  #오늘날짜 
    #tg_dt = now  - timedelta(days=1) #이 날짜는 사실 전일자가 되어야 함. 이 코드는 매일 새벽에 돌 것이고 전일자를 수집하는 것이 목표
    data_raw = {
        "TERM":"D",
        "STA_Y": stt_dt.strftime('%Y'),
        "STA_M": stt_dt.strftime('%m'),
        "STA_W": "1",
        "STA_D":stt_dt.strftime('%d'),
        "END_Y":end_dt.strftime('%Y'), #now.strftime('%Y'),#
        "END_M":end_dt.strftime('%m'),#now.strftime('%m'),#
        "END_W": "1",
        "END_D":end_dt.strftime('%d'),#now.strftime('%d'),
        "OILSRTCD1":"001",
        "OILSRTCD2":"002",
        "OILSRTCD3":"003",
        "STDDATE":stt_dt.strftime('%Y%m%d'),
        "ENDDATE":end_dt.strftime('%Y%m%d'),
        "SEL_DIV": "div_won" if currency == "KRW" else "div_dar",
        "OILSRTCD":["001","002","003"] 
    }
#2. 결과 획득
    response = requests.post(url, data=data_raw)
#3. 크롤링 결과 정제 및 저장
    df = pd.read_csv(io.BytesIO(response.content), encoding='cp949')
    df['part_dt'] = pd.to_datetime(df['기간'],format='%y년%m월%d일')
    df['currency'] = currency
    df['unit'] = "liter" if currency == "KRW" else "barrel"

    df = df[['part_dt','currency','unit','Dubai' , 'Brent' , 'WTI' ]]
    return df
# 중복파티션 방지용 함수
def drop_existing (df , stt_dt , end_dt ):
    return duckdb.sql(f"""
       WITH existing_table AS (
        SELECT DISTINCT part_dt, currency
        FROM read_parquet('s3://petroleum-project/crude_oil_price/*/*.parquet')
        WHERE part_dt BETWEEN strptime('{stt_dt}','%Y%m%d') AND strptime('{end_dt}' ,'%Y%m%d')    -- ★ 파티션 프루닝용
       ) -- duckdb의 date_parse 문법 = strptime
       SELECT
       t1.*
       FROM df t1
       LEFT JOIN existing_table t2
       ON CAST(t1.part_dt AS DATE) = t2.part_dt
       AND t1.currency = t2.currency
       WHERE t2.part_dt IS NULL
    """
    ).df()


def upload_to_minio(df):
    #7. 결과 분기 저장.
    try:
        if not df.empty:
            
            table_name = "crude_oil_price"
            path = f"s3://petroleum-project/{table_name}/"
            min_dt , max_dt , cnt =  duckdb.sql ("SELECT min(part_dt), max(part_dt), count(*) from df").fetchone()
            
            duckdb.sql(f"""
            COPY(
                SELECT * REPLACE( CAST(part_dt AS DATE) AS part_dt)
                FROM df
            )
            TO '{path}'
            (FORMAT PARQUET, PARTITION_BY (part_dt), APPEND)
            
            """)
            print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] :"
            f"[{min_dt.strftime('%Y%m%d')} ~ {max_dt.strftime('%Y%m%d')}] 의 {cnt}행의 원유 가격 정보를 수집하여 저장합니다.")
        else:
            print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] :"
            " 수집된 원유 가격정보가 없습니다. 업로드를 건너뜁니다------")
    except Exception as e:
        print(f" [에러] 작업 중 오류 발생: {e}")


if __name__ == "__main__":
    import sys 
    if len(sys.argv) >= 3 :
        stt_dt = sys.argv[1]
        end_dt = sys.argv[2]
    else:
        now= datetime.now()  #오늘날짜 
        tg_dt = now  - timedelta(days=1) #이 날짜는 사실 전일자가 되어야 함. 이 코드는 매일 새벽에 돌 것이고 전일자를 수집하는 것이 목표
        stt_dt = tg_dt.strftime('%Y%m%d')
        end_dt = tg_dt.strftime('%Y%m%d')
    try:
        df_krw = gather_crude_oil_price(stt_dt , end_dt , 'KRW')
        df_krw = drop_existing(df_krw,stt_dt,end_dt)
        upload_to_minio(df_krw)
        df_usd = gather_crude_oil_price(stt_dt , end_dt )
        df_usd = drop_existing(df_usd,stt_dt,end_dt)
        upload_to_minio(df_usd)
        
        
    except Exception as e:
        print(f" [에러] 작업 중 오류 발생: {e}")