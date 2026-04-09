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
con = duckdb.connect()
con.execute("INSTALL httpfs; LOAD httpfs;")
con.execute(f"SET s3_endpoint='{MINIO_ENDPOINT}';")
con.execute(f"SET s3_access_key_id='{MINIO_ACCESS_KEY}';")
con.execute(f"SET s3_secret_access_key='{MINIO_SECRET_KEY}';")
con.execute("SET s3_url_style='path'; SET s3_use_ssl='false';")

SQL_QUERY = """
with unq_station  as (
select 
t1.uni_cd , t1.station_name , t1.brand_cd , t1.station_x , t1.station_y 
from  read_parquet('s3://petroleum-project/station_price/diesel/part_dt={part_key}/*.parquet') t1
union
select
t1.uni_cd , t1.station_name , t1.brand_cd , t1.station_x , t1.station_y
from  read_parquet('s3://petroleum-project/station_price/gasoline/part_dt={part_key}/*.parquet') t1
union
select
t1.uni_cd , t1.station_name , t1.brand_cd , t1.station_x , t1.station_y
from  read_parquet('s3://petroleum-project/station_price/premium_gasoline/part_dt={part_key}/*.parquet') t1
)
select
{part_key} as part_dt
, t1.uni_cd
, t1.station_name
, t1.brand_cd
, t1.station_x
, t1.station_y
, t2.price as gasoline
, t3.price as diesel
, t4.price as premium_gasoline
from unq_station t1
left join read_parquet('s3://petroleum-project/station_price/gasoline/part_dt={part_key}/*.parquet') t2
on t1.uni_cd = t2.uni_cd
left join read_parquet('s3://petroleum-project/station_price/diesel/part_dt={part_key}/*.parquet') t3
on t1.uni_cd = t3.uni_cd
left join read_parquet('s3://petroleum-project/station_price/premium_gasoline/part_dt={part_key}/*.parquet') t4
on t1.uni_cd = t4.uni_cd
"""

def by_station_agg(part_key):
    sql_filled = SQL_QUERY.format(part_key = part_key)
    
    
    result_path = f"s3://petroleum-project/station_price/agg/part_dt={part_key}/data.parquet"
    con.sql(sql_filled).write_parquet(result_path , overwrite = True)
    print(f"---[{part_key}]by_station_agg 생성 완료")



if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        part_key = sys.argv[1]
    else:
        part_key = datetime.now().strftime('%Y%m%d')
    try:
        by_station_agg(part_key)
    except Exception as e:
        print(f"[에러] 작업 중 오류 발생 : {e}")