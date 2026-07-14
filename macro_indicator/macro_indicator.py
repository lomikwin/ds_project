import pandas as pd 
import pyarrow
import duckdb
import os
import requests
from datetime import datetime, timedelta
from dotenv import load_dotenv , find_dotenv

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
    "END_Y":tg_dt.strftime('%Y'),
    "END_M":tg_dt.strftime('%m'),
    "END_W": "1",
    "END_D":tg_dt.strftime('%d'),
    "OILSRTCD1":"001",
    "OILSRTCD2":"002",
    "OILSRTCD3":"003",
    "STDDATE":tg_dt.strftime('%Y%m%d'),
    "ENDDATE":tg_dt.strftime('%Y%m%d'),
    "SEL_DIV":"div_dar",
    "OILSRTCD":["001","002","003"] 
}

response = requests.post(url, data=data_raw)

print(response.status_code)
print(len(response.content))
print(response.content[:200])