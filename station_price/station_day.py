import requests
from urllib.parse import parse_qs , parse_qsl
import pandas as pd
import io
import duckdb
import os
from dotenv import load_dotenv , find_dotenv

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

target_dt = "20260903"
dl_payload = {
    "rdo1":"A", "rdo2":"A" , "rdo3":"A", "rdo4":"X",
    "LPG_CD":"A",
    "DATE_DIV_CD":"X",
    "PAGE_DIV":"PAGE_DIV_6",
    "SIDO_NM": "시/도",
    "SIGUN_NM":"시/군/구",
    "API_GBN":"A",
    "START_DT":target_dt,
    "END_DT":target_dt,
    "SIDO_CD":"",
    "SIGUN_CD":"",
    "netfunnel_key":netfunnel_key
}

r3 = s.post(download_url, data=dl_payload, timeout=15)
df = pd.read_csv ( io.BytesIO(r3.content), encoding = 'cp949', skiprows = [1])
sql_df = con.sql("""
        select  
        t1.번호 as uni_cd ,
        CAST(strptime(CAST(t1.기간 AS VARCHAR) ,  '%Y%m%d') AS DATE) as part_dt,
        strptime(CAST(t1.기간 AS VARCHAR) ,  '%Y%m%d')  as part_dt_timestamp,
        t2.area_cd , 
        t1.지역 as area_nm
        from df t1 
        left join read_parquet('s3://petroleum-project/station_metadata/area_code/*.parquet') t2
        on t1.지역 = concat(t2.upper_nm , ' ' , t2.area_nm)
        and t2.area_depth = 2
        limit 5
        """
        )
print(sql_df)
# with open("/volume2/ds_project/station_price/tmp_station_day.csv", "wb") as f:      
#     f.write(r3.content)