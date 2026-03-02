"""Celery 앱 설정.

브로커 및 결과 백엔드: Redis (REDIS_URL 환경변수)
워커 실행: celery -A bot_engine.celery_app worker --loglevel=info
"""
import os

from celery import Celery

celery_app = Celery(
    "bot_engine",
    broker=os.environ.get("REDIS_URL", "redis://localhost:6379/0"),
    backend=os.environ.get("REDIS_URL", "redis://localhost:6379/0"),
    include=[
        "bot_engine.workers.spot_grid",
        "bot_engine.workers.snowball",
        "bot_engine.workers.rebalancing",
        "bot_engine.workers.spot_dca",
        "bot_engine.workers.algo_orders",
    ],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    task_acks_late=True,            # Worker 비정상 종료 시 재큐잉 보장
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,   # 봇 Task는 장시간 실행 → 1개씩 가져옴
    task_time_limit=86400,          # 최대 24시간 (봇은 장시간 실행)
    task_soft_time_limit=82800,     # soft limit: 23시간 (정상 종료 유도)
)
