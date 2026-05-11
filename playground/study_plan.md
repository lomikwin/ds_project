# 공부 계획 (Study Plan)

> 진행 중 + 앞으로 공부해보고 싶은 주제 모음.
> 떠오를 때마다 아래 큐에 자유롭게 추가.

---

## 🟢 진행 중

### Cosine Similarity
5단계 학습 플랜:
1. sklearn `cosine_similarity` → N×N 매트릭스 ✅
2. N×N → long format 변환 (pandas) ✅
3. **`sklearn.neighbors.NearestNeighbors` 로 top-K 정공법** ← 여기
4. DuckDB 내장 `list_cosine_similarity` 활용
5. Cross-join 으로 순수 SQL 구현 (Spark/Hive 호환)

작업 일지: `Cosine Similarity/20260507.md`

---

## 🔵 다음 큐 (순서대로)

### 1. 상관계수 패밀리 — 수치형 변수 간 관계
- **Spearman 상관계수** — 값 대신 **순위(rank)** 로 계산. 비선형 단조관계까지 잡아냄. (5/3 세션에서 잠깐 만남)
- **Pearson 상관계수** — 가장 익숙한 그 r. 핵심 통찰: **중심화(평균 뺀) 두 벡터의 cosine similarity 와 동일**. → cosine 의 자연스러운 다음 챕터.

### 2. Chi-square (χ²) 검정 — 범주형 변수 간 독립성
- 워낙 자주 쓰임. A/B 테스트, 분할표 분석, feature 선택까지 광범위. 한 번 정리하고 가기.

### 3. Jaccard 유사도 — 집합 기반
- 교집합 / 합집합. 카테고리·태그·단어 비교용. cosine 과 달리 **"있다/없다"** 의 세계.

### 4. 생존 분석 — Cox Proportional Hazards
- 시간 + 이벤트 데이터의 정석 모델
- 석사 논문(IML 고객 잔존 분석) 과 직접 연결점 있음 → 다시 보면 깊어질 영역

### 5. 정규화 회귀 (Regularization)
- **Lasso (L1)** — 계수를 0 으로 죽임 → 자연스러운 feature selection
- **Ridge (L2)** — 계수를 줄이되 0 은 안 됨 → 다중공선성 완화
- **Elastic Net** — L1 + L2 혼합. 둘의 절충안

---

## 🟡 아이디어 큐 (자유 추가 영역)

> 떠오르는 대로. 우선순위는 나중에 정리.

-

---

## 📌 스스로에게 거는 학습 원칙

- 손계산 → 작은 데이터 → 라이브러리 → SQL 의 4단 사다리 밟기
- 세션 끝마다 `.claude/YYYYMMDD.md` 작업 일지 남기기
- 수식은 LaTeX 금지, 코드블록 / 유니코드 (‖·‖, Σ, √, θ) 사용
- 막힐 때 "에러 메시지는 정직하다" 떠올리기
