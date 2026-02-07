### No need to make this very simmilar py file. But for saving history. I duplicated py file for only collecting white list dots for LPG
import pandas as pd 
import pyarrow
import duckdb
import os
import requests
from datetime import datetime
from dotenv import load_dotenv , find_dotenv

# 1. MINIO 접속 정보
load_dotenv(find_dotenv())
MINIO_ENDPOINT = os.getenv('MINIO_ENDPOINT')
MINIO_ACCESS_KEY = os.getenv('MINIO_ACCESS_KEY')
MINIO_SECRET_KEY = os.getenv('MINIO_SECRET_KEY')

# 2. 주요 연산는 전부 SQL로 처리 
SQL_CALCULATION = """
    -- 한방에 3개에 대해서 최적화 좌표를 가져오는 쿼리
    with base as ( -- 주유소 입장에서 가장 가까운 좌표값을 가져오는데 고려 요소는  가장 최근 날짜, 그리고 fuel_type
    select 
        uni_cd
        , fuel_type
        , katec_x
        , katec_y
        , distance
        , max(part_dt) over (PARTITION BY uni_cd , fuel_type ) as last_part_dt
        , ROW_NUMBER() OVER (PARTITION BY uni_cd , fuel_type ORDER BY part_dt DESC , DISTANCE ASC  ) AS dist_rank -- 가장 마지막 날짜, 그리고 가장 가까운 거리 순
        
        FROM '{gasstation_path}'
        WHERE part_dt >= 20260202
    ), dot_utility as (
        SELECT 
        katec_x 
        , katec_y
        , fuel_type
        , last_part_dt
        , count( CASE WHEN dist_rank = 1 THEN 1 END) as essential_station_cnt
        , count(1) as total_detected_cnt
        from base 
        group by 1,2,3,4
    )
    , calculation_by_coordinates as (
    select 
    katec_x
    , katec_y

    , max(case when (fuel_type = 'B027') and essential_station_cnt > 0 then 1 else 0 end) as  is_gasoline_check
    , max(case when (fuel_type = 'B034') and essential_station_cnt > 0 then 1 else 0 end) as  is_premium_gasoline_check
    , max(case when (fuel_type = 'K015') and essential_station_cnt > 0 then 1 else 0 end) as  is_lpg_check

    , max(case when fuel_type = 'B027' then cast(last_part_dt as string) end ) as last_check_gasoline
    , max(case when fuel_type = 'B034' then cast(last_part_dt as string) end ) as last_check_premium_gasoline
    , max(case when fuel_type = 'K015' then cast(last_part_dt as string) end ) as last_check_lpg
    from dot_utility
    group by 1,2 
    ) -- final union step
    SELECT
    t1.katec_x
    , t1.katec_y
    , t1.lat
    , t1.lon
    , t2.is_gasoline_check
    , t2.is_premium_gasoline_check
    , t2.is_lpg_check
    , t2.last_check_gasoline
    , t2.last_check_premium_gasoline
    , t2.last_check_lpg
    FROM master_table t1
    LEFT JOIN calculation_by_coordinates t2
    ON t1.katec_x = t2.katec_x
    AND t1.katec_y = t2.katec_y
    """

#이제 API키를 2개를 갖고 내가 돌려가면서 써볼것이기에 이 부분을 미리 사전에 반영해둠. 

def target_coordinates():
    # 3.duck DB Connect 설정
    con = duckdb.connect()
    con.execute("INSTALL httpfs; LOAD httpfs;")
    con.execute(f"SET s3_endpoint='{MINIO_ENDPOINT}';")
    con.execute(f"SET s3_access_key_id='{MINIO_ACCESS_KEY}';")
    con.execute(f"SET s3_secret_access_key='{MINIO_SECRET_KEY}';")
    con.execute("SET s3_url_style='path'; SET s3_use_ssl='false';")
    
    # 4. 참조 테이블 1번 로드 -- lat,lon 포함한 x,y좌표 테이블
    base_path = os.path.dirname(os.path.abspath(__file__))
    master_table_path = os.path.join(base_path, "nationwide_master_grid_katec.parquet")
    master_table = duckdb.read_parquet(master_table_path).df()

    # 5. 참조테이블 2번 로드 -- 나중에 연산에 의해서 수집될 테이블 참조
    gasstation_path = "s3://petroleum-project/coord_validation_logs/*/*.parquet"

    # 6.최종 결과 저장할 경로 및 파일명 , 파티션 없이 최신성만 유지할 예정
    result_path = "s3://petroleum-project/target_coordinates/target_coordinates.parquet"
    
    # 7. SQL 튜닝 - from의 path 부분을 채움.
    sql_pathed = SQL_CALCULATION.format(gasstation_path = gasstation_path)
    
    con.sql(sql_pathed).write_parquet(result_path)

    now = datetime.now()
    print(f"---[{now.strftime('%Y%m%d')}-완료]target_coordinates 생성 완료")

if __name__ == "__main__":
    try:
        target_coordinates()
        
    except Exception as e:
        print(f" [에러] 작업 중 오류 발생: {e}")

#petroleum-project/coord_validation_logs