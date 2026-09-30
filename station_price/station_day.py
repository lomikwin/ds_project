import requests
from urllib.parse import parse_qs , parse_qsl
import pandas as pd
import io
import duckdb
import os
from dotenv import load_dotenv , find_dotenv
from datetime import datetime, timedelta

# 1. 환경 변수 로드
load_dotenv(find_dotenv())
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


s = requests.Session()
url = "https://www.opinet.co.kr/user/opdown/opDownload.do"
payload = {
    "netfunnel_key": "",
    "opinet_key": "6qdFLpmi7zDOTaXPM8sWPCH2brugOXBbGUOD5s2BzzQ=",
}

r = s.post(url,data=payload,timeout=15)

nfl_url = ("https://nfl.opinet.co.kr/ts.wseq"
           "?opcode=5101&nfid=0&prefix=NetFunnel.gRtype=5101;"
           "&sid=service_1&aid=B7&js=yes")

r2 = s.get(nfl_url, timeout=15)
_, status_code ,  query_string = r2_chunk = r2.text.split('result=')[1].split("'")[1].split(":",2)

netfunnel_key = parse_qs(query_string)['key'][0]

download_url = "https://www.opinet.co.kr/user/main/main_download_csv_big.do"

#target_dt = "20260903"
def download_csv ( stt_dt , end_dt):
    dl_payload = {
        "rdo1":"A", "rdo2":"A" , "rdo3":"A", "rdo4":"X",
        "LPG_CD":"A",
        "DATE_DIV_CD":"X",
        "PAGE_DIV":"PAGE_DIV_6",
        "SIDO_NM": "시/도",
        "SIGUN_NM":"시/군/구",
        "API_GBN":"A",
        "START_DT":stt_dt,
        "END_DT":end_dt,
        "SIDO_CD":"",
        "SIGUN_CD":"",
        "netfunnel_key":netfunnel_key
    }


    r3 = s.post(download_url, data=dl_payload, timeout=15)
    df = pd.read_csv ( io.BytesIO(r3.content), encoding = 'cp949', skiprows = [1])
    sql_df = con.sql("""
            
            select 
            t1.번호 AS uni_cd,
            CAST(strptime(CAST(t1.기간 AS VARCHAR) ,  '%Y%m%d') AS DATE) as part_dt,
            t1.지역 AS area_nm,
            t1.상표 AS brand_nm,
            CASE WHEN t1.셀프여부 = '셀프' THEN TRUE WHEN t1.셀프여부 = '일반' THEN FALSE END AS is_self,
            CAST(NULLIF(t1.고급휘발유 ,0) AS INT) AS premium_gasoline,
            CAST(NULLIF(t1.휘발유 ,0) AS INT ) AS gasoline,
            CAST(NULLIF(t1.경유 ,0) AS INT ) AS diesel,
            CAST(NULLIF(t1.실내등유 ,0) AS INT) AS kerosene,
            t1.상호 AS station_nm,
            t1.주소 AS addr


            from df t1
            """
            ).df()
    return sql_df
# 중복파티션 방지용 함수
def drop_existing (df , stt_dt , end_dt ):
    return con.sql(f"""
       WITH existing_table AS (
        SELECT DISTINCT part_dt, currency
        FROM read_parquet('s3://petroleum-project/station_price/station_day/*/*.parquet')
        WHERE part_dt BETWEEN strptime('{stt_dt}','%Y%m%d') AND strptime('{end_dt}' ,'%Y%m%d')    -- ★ 파티션 프루닝용
       ) -- duckdb의 date_parse 문법 = strptime
       SELECT
       t1.*
       FROM df t1
       LEFT JOIN existing_table t2
       ON t1.part_dt  = t2.part_dt
       WHERE t2.part_dt IS NULL
    """
    ).df()

def upload_to_minio(df):
    #7. 결과 분기 저장.
    try:
        if not df.empty:
            
            table_name = "station_day"
            path = f"s3://petroleum-project/station_price/{table_name}/"
            min_dt , max_dt , cnt =  con.sql ("SELECT min(part_dt), max(part_dt), count(distinct uni_cd) from df").fetchone()
            
            con.sql(f"""
            COPY(
                SELECT * REPLACE( part_dt)
                FROM df
            )
            TO '{path}'
            (FORMAT PARQUET, PARTITION_BY (part_dt), APPEND)
            
            """)
            print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] :"
            f"[{min_dt.strftime('%Y%m%d')} ~ {max_dt.strftime('%Y%m%d')}] 의 {cnt}개의 주유소의 가격 정보를 수집하여 저장합니다.")
        else:
            print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] :"
            " 수집된 주유소 가격 정보가 없습니다. 업로드를 건너뜁니다------")
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
        df_station_day = download_csv(stt_dt , end_dt )
        df_station_day = drop_existing(df_station_day,stt_dt,end_dt)
        upload_to_minio(df_station_day)
        
        
    except Exception as e:
        print(f" [에러] 작업 중 오류 발생: {e}")