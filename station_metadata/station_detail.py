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
                        'OPINET_API_KEY_4', 'OPINET_API_KEY_5', 'OPINET_API_KEY_6' ] 
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
url = "https://www.opinet.co.kr/api/detailById.do"


# 일배치를 통해 만들어지는 agg 테이블에서 직접 가져오기
path = "s3://petroleum-project/station_price/agg/*/*.parquet"
tg_station = con.sql(
    f"""
    
    WITH base_step as (
    SELECT DISTINCT t1.uni_cd , max(t1.part_dt) as max_part_dt , 1 as SEQ
    FROM  read_parquet('s3://petroleum-project/station_price/agg/*/*.parquet') t1
    LEFT join read_parquet('s3://petroleum-project/station_metadata/station_detail/*/*.parquet') t2
    ON t1.uni_cd = t2.uni_cd
    WHERE t2.part_dt is null
    GROUP by 1
    HAVING cast(max(t1.part_dt) as varchar) >= strftime( today()  - interval 60 DAYS , '%Y%m%d')

    UNION ALL 
    SELECT 
    DISTINCT t1.uni_cd, max ( t1.part_dt) as max_part_dt  , 2 AS SEQ
    from read_parquet('s3://petroleum-project/station_metadata/station_detail/*/*.parquet') t1
    group by 1
    HAVING cast(max(t1.part_dt) as varchar) >= strftime( today()  - interval 60 DAYS , '%Y%m%d')
    )
    SELECT * 
    FROM base_step
    ORDER BY SEQ , 2
    LIMIT 1000
    """
    ).df() # 나중에 저 LIMIT 부분을 갖고 테스트 양을 조절.

def meta_detail(tg_station ):
    
    #최적화된 좌표별로 api호출을 하고 이를 통해 주유소별 휘발유 가격 정보를 수집합니다.
    #prodcd: 유종 코드 (B027:휘발유, D047:경유, B034:고급휘발유, K015:LPG , C004:실내등유)
    
    meta_detail_list = []
    columns = ['uni_cd' , 'POLL_DIV_CO' , 'GPOLL_DIV_CO' , 'OS_NM',
            'VAN_ADR' , 'NEW_ADR' , 'TEL' , 'SIGUNCD' , 'LPG_YN' ,
            'MAINT_YN' , 'CAR_WASH_YN', 'KPETRO_YN' , 'CVS_YN',
            'GIS_X_COOR' , 'GIS_Y_COOR' , 'PROD_CD' , 'PRICE',
            'TRADE_DT' , 'TRADE_TM'
            ]
    key_index = 5 #5번 키부터 사용시작
    null_cnt = 0
    first_failed_index = None
    
    i = 0
    while i < len(tg_station):
        if i%100 == 0 :
            print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {i}번째 좌표에 대해서 호출 진행중.")
        row = tg_station.iloc[i]
        success_flag = False
        result_list = []
        try :
            while not success_flag and key_index >= 0:
                params = {
                    "code": os.getenv(OPINET_API_KEY_GROUP[key_index]),
                    "out": "json",
                    "id": row["uni_cd"],
                    }
                response = requests.get(url, params=params)
                response.raise_for_status() # 에러 발생 시 예외 처리
                data = response.json()
                api_call = data.get('RESULT',{}).get('OIL')

                if api_call != []:
                    result_list = api_call
                    success_flag = True
                    null_cnt = 0
                    i += 1
                else :
                    null_cnt += 1
                    if null_cnt == 1:
                        first_failed_index = i
                    if null_cnt >= 50:
                        print (f"공백응답[] 50회 누적. API키를 교체합니다. {first_failed_index}번으로 돌아갑니다.")
                        key_index -= 1
                        null_cnt = 0
                        i = first_failed_index
                        break #새로운 키로 바로 찔러보도록 while loop 탈출
                    else:
                        print(f"[주의] {i}번째 주유소 공백 {null_cnt}/50")
                        success_flag = True
                        i += 1
            if key_index < 0:
                print("[주의]API키 전부 소진. 수집을 멈추고 저장합니다.")
                break
            for station in result_list:
                common = (
                    station["UNI_ID"],
                    station["POLL_DIV_CO"],
                    station["GPOLL_DIV_CO"],
                    station["OS_NM"],
                    station["VAN_ADR"],
                    station["NEW_ADR"],
                    station["TEL"],
                    station["SIGUNCD"],
                    station["LPG_YN"],
                    station["MAINT_YN"],
                    station["CAR_WASH_YN"],
                    station["KPETRO_YN"],
                    station["CVS_YN"],
                    station["GIS_X_COOR"],
                    station["GIS_Y_COOR"],
                )
                oil_prices = station["OIL_PRICE"]
                if isinstance(oil_prices,dict):
                    oil_prices = [oil_prices]
                for oil in oil_prices:
                    meta_detail_list.append(
                        common + (
                        oil["PRODCD"],
                        oil["PRICE"],
                        oil["TRADE_DT"],
                        oil["TRADE_TM"],

                        ))
        except Exception as e:
                print(f"[ERROR]API 호출 중 오류 발생: {e}")
 
    long_df = pd.DataFrame(meta_detail_list, columns = columns)
    idx_col =  ['uni_cd' , 'POLL_DIV_CO' , 'GPOLL_DIV_CO' , 'OS_NM',
                    'VAN_ADR' , 'NEW_ADR' , 'TEL' , 'SIGUNCD' , 'LPG_YN' ,
                    'MAINT_YN' , 'CAR_WASH_YN', 'KPETRO_YN' , 'CVS_YN',
                    'GIS_X_COOR' , 'GIS_Y_COOR' ]
    final_result = long_df.pivot_table(
        index = idx_col,
        columns = 'PROD_CD',
        values = 'PRICE',
        aggfunc = 'first',
    ).reset_index()
    final_result = final_result.rename(columns={
        'B027' : 'gasoline_price',
        'B034' : 'premium_gasoline_price',
        'D047' : 'diesel_price' , 
        'K015' : 'lpg_price',
        'C004' : 'kerosene_price',
        })
    trade_time_value = (
        long_df.groupby('uni_cd')[['TRADE_DT','TRADE_TM']]
                .max()
                .reset_index()
               )
    final_result = final_result.merge(trade_time_value, on='uni_cd', how='left')
    now = datetime.now()
    final_result['collect_time'] = now.strftime('%Y-%m-%d %H:%M:%S') 
    final_result['part_dt'] = now.strftime('%Y%m%d')
    # final_result = final_result[
    #     ['part_dt', 'uni_cd' , 'POLL_DIV_CD' , 'GPOLL_DIV_CD' , 'OS_NM',
    #                 'VAN_ADR' , 'NEW_ADR' , 'TEL' , 'SIGUNCD' , 'LPG_YN' ,
    #                 'MAINT_YN' , 'CAR_WASH_YN', 'KPETRO_YN' , 'CVS_YN',
    #                 'GIS_X_COOR' , 'GIS_Y_COOR' , 'gasoline_price' , 'premium_gasoline_price',
    #                 'diesel_price' , 'lpg_price' , 'kerosene_price'
    #                 ]]
    return final_result


def upload_to_minio(df):
    partition_date = df['part_dt'].iloc[0]
    timestamp = datetime.now().strftime('%H%M%S')
    file_name = f"data_{timestamp}.parquet"
    path = f"s3://petroleum-project/station_metadata/station_detail/part_dt={partition_date}/{file_name}"
    con.sql("SELECT * FROM df").write_parquet(path)
    print(f"--- [MinIO 완료, ({datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {partition_date} 데이터가 저장되었습니다. ---")



if __name__ == "__main__":
    try:
        df = meta_detail(tg_station) # 1day : 0:3500 ,  2day : 3500:7000 , 3day : 7000:
        
        if not df.empty:
            print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {len(df)}개의 주유소의 메타정보를 발견 업로드를 시작합니다")
            upload_to_minio(df)
        else:
            print("-------수집된 주유소가 없습니다. 업로드를 건너뜁니다------")
        
        
    except Exception as e:
        print(f" [에러] 작업 중 오류 발생: {e}")