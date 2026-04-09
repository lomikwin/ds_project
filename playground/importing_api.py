# -*- coding: utf-8 -*-
import pandas as pd
import requests 

def importing_api(url):
    try:
        # 1. API 호출
        response = requests.get(url)
        response.raise_for_status()

        # 2. JSON 데이터 파싱
        data = response.json()
        # 3. 데이터 프레임 생성
        df = pd.DataFrame(data)

        print("---API 파싱 성공----")
        print(f"파싱된 데이터 크기 : {df.shape}")

        return df

    except requests.exceptions.RequestException as e:
        print(f"오류 발생 : {e}")
        return None

if __name__ == "__main__":
    url = "https://jsonplaceholder.typicode.com/posts"
    df = importing_api(url)
    if df is not None:
        print(df.head())