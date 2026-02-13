# 00. 기본적인 라이브러리 호출
import os
import requests
from dotenv import load_dotenv, find_dotenv

load_dotenv(find_dotenv())
def send_telegram_message(path = "by_gasoline_log.log"):
    """
    텔레그램 봇을 통해 메시지를 전송합니다.
    .env 파일에 TELEGRAM_HTTP_API TELEGRAM_ID 설정되어 있어야 합니다.
    """
    # 01. telegram chatbot을 이용하기 위한 API키, 기본 세팅등
    token = os.getenv("TELEGRAM_HTTP_API")
    chat_id = os.getenv("TELEGRAM_ID")  
    # 02. 인자로 받은 로그파일명을 갖고 경로값을 조합함
    base_path = os.path.dirname(os.path.abspath(__file__))
    path = path
    tg_file = os.path.join (base_path , path)
    # 03. 로그 파일명을 기반으로 계산한 경로값의 파일을 열음. 
    with open(tg_file , "r" ,encoding="utf-8") as f:
        log_content = f.read()
    safe_message = log_content[-3000:] 

    # 05. chatbot을 위한 패러미터값 조합 
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": f" *유가 수집 로그 리포트*\n\n```\n{safe_message}\n```",
        "parse_mode": "Markdown",
        "disable_notification": True
    }
    requests.post(url, json=payload)
    

if __name__ == "__main__" :
    import sys 
    if len(sys.argv) > 1 :
        target_file = sys.argv[1] # 내가 입력한 인자덩어리들 중 2번째 꺼를 받아와! 
    else :
        target_file = "by_gasoline_log.log"
    
    try:
        send_telegram_message(target_file)
    except Exception as e :
            print(f" [에러] 작업 중 오류 발생: {e}")

