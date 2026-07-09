"""Оркестрация анализа: тянет последние спины из БД и считает статистику."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from src.analysis import stats
from src.analysis.stats import AnalysisResult
from src.db import repo
from src.roulette.domain import Difficulty


async def analyze_table(
    db: AsyncSession,
    *,
    server: str,
    casino: str,
    table_no: int,
    difficulty: Difficulty | str,
    window: int = 300,
) -> AnalysisResult:
    numbers = await repo.recent_numbers(
        db, server=server, casino=casino, table_no=table_no, limit=window
    )
    return stats.analyze(numbers, difficulty)
