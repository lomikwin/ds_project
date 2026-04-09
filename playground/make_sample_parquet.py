import pandas as pd
import numpy as np
import pyarrow

# 1. 100행 5열의 샘플 데이터 생성
data = {
    'id': range(1, 101),
    'date': pd.date_range(start='2026-01-01', periods=100),
    'category': np.random.choice(['A', 'B', 'C'], size=100),
    'value': np.random.uniform(10.5, 500.5, size=100).round(2),
    'status': np.random.choice([True, False], size=100)
}

df = pd.DataFrame(data)


# 2. Parquet 파일로 저장
file_name = 'sample_data.parquet'
df.to_parquet(file_name, engine='pyarrow', index=False)

print(f"✅ {file_name} 파일이 생성되었습니다!")
print(df.head()) # 상위 5줄 미리보기