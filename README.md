# ds_project

> Personal study project — Korean petroleum price ETL pipeline,
> aiming at long-term price prediction & macroeconomic analysis.

---

## About

This Project is only for Personal study.
I don't want any contribution or discussion or any kind of feedback.

이 프로젝트는 개인 학습용으로, 외부 기여나 피드백을 전혀 받지 않습니다.

---

## Goal

데이터 수집 · 정제 · 분석 · 모델링까지 데이터 사이언스 전 영역을 직접 학습하기 위한 트랙입니다.

업무에서 활용하는 LLM 인프라(MCP)와는 별개로, 본 프로젝트는 학습 목적상 **코드 자동 생성을 지양하고 직접 작성·디버깅**합니다. 모르는 개념·방법론은 AI와 대화로 학습하되, 코드는 직접 손으로 익히는 것을 원칙으로 합니다.

---

## Current Stage

OPINET API → MinIO (Parquet) → DuckDB ETL 파이프라인 자체 구축.

- Synology NAS 기반 일배치 운영
- 전국 KATEC 격자 좌표 whitelist 최적화 · coverage 검증
- Telegram 기반 메인 잡 성공 알림 모니터링

---

## Long-term Goals

1. 국제유가 → 국내유가 반영 lag 분석
2. 환율 · 거시지표 기반 N일 후 유가 예측 모델
3. 거리 · 가격 trade-off 주유소 추천 알고리즘

---

## Stack

- **Language**: Python, SQL (DuckDB)
- **Storage**: MinIO (S3-compatible object storage), Parquet
- **Infrastructure**: Synology NAS (daily batch scheduling)
- **Notification**: Telegram bot
