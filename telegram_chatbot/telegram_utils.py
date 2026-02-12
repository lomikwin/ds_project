import os
import requests
from dotenv import load_dotenv, find_dotenv

# 환경 변수 로드
load_dotenv("e:/ds_project/.env")

def send_telegram_message(message):
    """
    텔레그램 봇을 통해 메시지를 전송합니다.
    .env 파일에 TELEGRAM_HTTP_API TELEGRAM_ID 설정되어 있어야 합니다.
    """
    token = os.getenv("TELEGRAM_HTTP_API")
    chat_id = os.getenv("TELEGRAM_ID")
    
    if not token or not chat_id:
        print("[주의] 텔레그램 토큰 또는 채팅 ID가 설정되지 않았습니다. 메시지를 보내지 않습니다.")
        return

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": message,
        "parse_mode": "Markdown" # 마크다운 형식을 지원하여 볼드체 등을 쓸 수 있습니다.
    }
    
    try:
        response = requests.post(url, json=payload)
        response.raise_for_status()
        # print("[성공] 텔레그램 메시지가 전송되었습니다.")
    except Exception as e:
        print(f"[에러] 텔레그램 메시지 전송 실패: {e}")
