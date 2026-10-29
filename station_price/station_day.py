import requests
from urllib.parse import parse_qs , parse_qsl
import pandas as pd
import io
import duckdb
import os
from dotenv import load_dotenv , find_dotenv
from datetime import datetime, timedelta
import time

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


url = "https://www.opinet.co.kr/user/opdown/opDownload.do"
payload = {
    "netfunnel_key": "",
    "opinet_key": "6qdFLpmi7zDOTaXPM8sWPCH2brugOXBbGUOD5s2BzzQ=",
}

nfl_url = ("https://nfl.opinet.co.kr/ts.wseq"
           "?opcode=5101&nfid=0&prefix=NetFunnel.gRtype=5101;"
           "&sid=service_1&aid=B7&js=yes")

# 201 대기 폴링 (8/18 검증: 2초 간격, 실측 12~20초 만에 200 전환. 표는 재발급하지 않는다)
nfl_poll_url = ("https://nfl.opinet.co.kr/ts.wseq"
                "?opcode=5002&key={key}&nfid=0&prefix=NetFunnel.gRtype=5002;"
                "&sid=service_1&aid=B7&js=yes&{ts}")
POLL_INTERVAL = 2   # 초
POLL_MAX = 60       # 최대 60회 = 2분

download_url = "https://www.opinet.co.kr/user/main/main_download_csv_big.do"


# 넷퍼널 응답 3층 벗기기: JS → '5002:200:key=...' → query string
def parse_nfl ( text ):
    _, status_code , query_string = text.split('result=')[1].split("'")[1].split(":",2)
    return status_code , parse_qs(query_string)['key'][0]


# 묶음마다 새로 부른다: 세션(방문증) → 번호표 → 201이면 200 될 때까지 대기
def get_session_and_key ():
    s = requests.Session()
    s.post(url, data=payload, timeout=15)

    r2 = s.get(nfl_url, timeout=15)
    status_code , netfunnel_key = parse_nfl(r2.text)

    poll_key = netfunnel_key
    poll_cnt = 0
    while status_code == '201':
        if poll_cnt >= POLL_MAX:
            raise RuntimeError(f"넷퍼널 대기 {POLL_MAX * POLL_INTERVAL}초 초과 (201 유지)")
        time.sleep(POLL_INTERVAL)
        r_poll = s.get(nfl_poll_url.format(key=netfunnel_key, ts=int(time.time() * 1000)), timeout=15)
        status_code , poll_key = parse_nfl(r_poll.text)  # 관찰용: 다운로드엔 처음 키를 그대로 쓴다 (8/18 검증 방식)
        poll_cnt += 1

    if status_code != '200':
        raise RuntimeError(f"넷퍼널 예상 밖 코드: {status_code}")
    if poll_cnt > 0:
        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] : 넷퍼널 201 대기 {poll_cnt * POLL_INTERVAL}초 후 입장"
              f" (폴링 응답 키: 처음 키와 {'다름' if poll_key != netfunnel_key else '같음'})", flush=True)
    return s , netfunnel_key


def download_csv ( stt_dt , end_dt):
    s , netfunnel_key = get_session_and_key()
    dl_payload = {
        "rdo1":"A", "rdo2":"A" , "rdo3":"A", "rdo4":"X",
        "LPG_CD":"A",
        "DATE_DIV_CD":"X",
        "PAGE_DIV":"PAGE_DIV_6",
        "SIDO_NM": "시/도",
        "SIGUN_NM":"시/군/구",
        "API_GBN":"A",
        "START_DT":stt_dt, #target_dt = "20260903"
        "END_DT":end_dt,
        "SIDO_CD":"",
        "SIGUN_CD":"",
        "netfunnel_key":netfunnel_key
    }


    r3 = s.post(download_url, data=dl_payload, timeout=60) # 7일치는 하루치의 7배라 넉넉히

    # CSV 대신 HTML이 오는 경우 (777B error.jsp = 번호표 없음/대기 상태, 10/7 크론 실패도 이 계열)
    # → 파싱 에러(Binder Error: no column "기간") 대신 받은 내용 앞부분을 남기고 실패
    head = r3.content[:200].decode('cp949', errors='replace')
    if head.lstrip().startswith('<'):
        raise RuntimeError(f"CSV 대신 HTML 수신 ({len(r3.content)}B): {head[:120]!r}")

    df = pd.read_csv ( io.BytesIO(r3.content), encoding = 'cp949', skiprows = [1])
    sql_df = con.sql("""
            
            select 
            CAST(strptime(CAST(t1.기간 AS VARCHAR) ,  '%Y%m%d') AS DATE) as part_dt,
            t1.번호 AS uni_cd,
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

# 빠진 날(주유소 0곳) → 연속 구간(섬)으로 묶기 → 섬마다 7일씩 쪼개기
# 반환: [('20261020', '20261026'), ('20261027', '20261030'), ...]  (chunk_start, chunk_end)
def find_missing_chunks ( stt_dt , end_dt ):
    stt_date = datetime.strptime(stt_dt, '%Y%m%d').strftime ('%Y-%m-%d')
    end_date = datetime.strptime(end_dt, '%Y%m%d').strftime ('%Y-%m-%d')

    return con.sql (f"""
    WITH series as (
    SELECT CAST(generate_series AS DATE) AS part_dt
    FROM generate_series(DATE '{stt_date}', DATE '{end_date}', INTERVAL 1 DAY)
    )
    , step1 as (
    select
    t1.part_dt
    , count(t2.uni_cd) as daily_uni_cnt
    from series t1
    left join read_parquet('s3://petroleum-project/station_price/station_day/*/*') t2
    on t1.part_dt = t2.part_dt
    group by 1
    )
    , step2 as ( -- 섬 이름표: 연속된 날은 (날짜 - 번호)가 같다
    select
    t1.part_dt
    , t1.part_dt - cast(row_number() over (order by part_dt) as INT) as group_key
    from step1 t1
    where daily_uni_cnt = 0
    )
    , step3 as ( -- 섬마다 눈금 리셋, 0부터 7칸씩
    select
    t1.group_key
    , t1.part_dt
    , t1.part_dt - cast(mod(row_number() over (partition by t1.group_key order by part_dt) - 1, 7) as INT) as group_key_2
    from step2 t1
    )
    select
    strftime(min(t1.part_dt), '%Y%m%d') as chunk_start
    , strftime(max(t1.part_dt), '%Y%m%d') as chunk_end
    from step3 t1
    group by t1.group_key, t1.group_key_2
    order by chunk_start
    """
    ).fetchall()


def upload_to_minio(df):
    #7. 결과 분기 저장.
    try:
        if not df.empty:
            
            table_name = "station_day"
            path = f"s3://petroleum-project/station_price/{table_name}/"
            # 일별 주유소 수의 최소~최대: 7일 중 하루만 비정상인 날을 로그에서 바로 보이게
            min_dt , max_dt , day_cnt , row_cnt , min_cnt , max_cnt = con.sql ("""
                SELECT min(part_dt), max(part_dt), count(*), sum(cnt), min(cnt), max(cnt)
                FROM (SELECT part_dt, count(distinct uni_cd) AS cnt FROM df GROUP BY part_dt)
            """).fetchone()
            
            con.sql(f"""
            COPY(
                SELECT * REPLACE( CAST(part_dt AS DATE) AS part_dt)
                FROM df
            )
            TO '{path}'
            (FORMAT PARQUET, PARTITION_BY (part_dt), WRITE_PARTITION_COLUMNS true,  APPEND)
            
            """)
            print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] :"
            f"[{min_dt.strftime('%Y%m%d')} ~ {max_dt.strftime('%Y%m%d')}] {day_cnt}일, {row_cnt:,}행, "
            f"일별 주유소 {min_cnt:,} ~ {max_cnt:,}곳 저장")
        else:
            print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] :"
            " 수집된 주유소 가격 정보가 없습니다. 업로드를 건너뜁니다------")
    except Exception as e:
        print(f" [에러] 업로드 중 오류 발생: {e}")
        raise  # 루프가 이 묶음을 실패로 셀 수 있게 위로 올려보낸다


if __name__ == "__main__":
    import sys 
    if len(sys.argv) >= 3 :
        stt_dt = sys.argv[1]
        end_dt = sys.argv[2]
    else:
        now= datetime.now()  #오늘날짜
        # 크론 기본값: 최근 7일(어제 포함)을 훑는다. 어제만 보면 하루 실패가 영영 남지만,
        # 7일을 보면 다음 날 크론이 빠진 날을 알아서 다시 채운다 (자가복구)
        stt_dt = (now - timedelta(days=7)).strftime('%Y%m%d')
        end_dt = (now - timedelta(days=1)).strftime('%Y%m%d')

    def log(msg):
        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] : {msg}", flush=True)

    try:
        chunk_list = find_missing_chunks(stt_dt , end_dt)
    except Exception as e:
        log(f"[에러] 빠진 날 조회 실패: {e}")
        sys.exit(1)

    log(f"[{stt_dt} ~ {end_dt}] 빠진 묶음 {len(chunk_list)}개: {chunk_list}")

    fail_list = []
    for chunk_start , chunk_end in chunk_list:
        try:
            try:
                df_station_day = download_csv(chunk_start , chunk_end)
            except RuntimeError as e:  # HTML 수신·넷퍼널 이상 → 새 번호표로 한 번만 더
                log(f"[재시도] {chunk_start} ~ {chunk_end}: {e}")
                time.sleep(10)
                df_station_day = download_csv(chunk_start , chunk_end)
            upload_to_minio(df_station_day)
        except Exception as e:  # 한 묶음이 실패해도 다음 묶음은 계속 (다음 크론이 다시 채운다)
            log(f"[에러] {chunk_start} ~ {chunk_end} 실패: {e}")
            fail_list.append((chunk_start , chunk_end))
        time.sleep(3)  # 묶음 사이 숨 고르기 (넷퍼널 대기열 자극 줄이기)

    log(f"완료: 성공 {len(chunk_list) - len(fail_list)} / 실패 {len(fail_list)} {fail_list}")
    if fail_list:
        sys.exit(1)