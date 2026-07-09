"""ИИ-разбор и прогноз поверх посчитанной статистики (DeepSeek через RouterAI).

ИИ получает уже посчитанные цифры (не сырые данные) и превращает их в
понятный игроку текст на русском. Честность обеспечивает системный промпт
клиента: не выдумывать закономерности, если смещения нет.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from src import venues
from src.analysis.stats import (
    DIFFICULTY_LABELS,
    AnalysisResult,
    category_label,
    top_predictions,
)

if TYPE_CHECKING:
    from src.ai.client import AIClient


def _data_block(
    result: AnalysisResult, *, server: str, casino: str, table_no: int, window: int
) -> list[str]:
    diff = result.difficulty
    lines = [
        f"Режим ставки: {DIFFICULTY_LABELS[diff.value]}.",
        f"Точка: сервер {venues.server_name(server)}, {venues.casino_name(casino)}, "
        f"стол №{table_no}.",
        f"Выборка: n={result.n} последних спинов (окно {window}).",
        "Распределение (наблюдаемо% / ожидаемо%):",
    ]
    shown = sorted(result.cats, key=lambda c: c.count, reverse=True)
    if diff.value == "numbers":
        shown = [c for c in shown if c.count > 0][:10]
    for c in shown:
        lines.append(
            f"  {category_label(c.category, diff)}: "
            f"{c.freq * 100:.1f}% / {c.expected * 100:.1f}% (выпало {c.count})"
        )
    verdict = "ЗНАЧИМО" if result.biased else "не значимо"
    lines.append(f"χ²={result.chi2:.2f}, p={result.p_value:.3f}, df={result.df} → смещение {verdict}.")
    if result.markov_pick:
        cat, prob, total = result.markov_pick
        lines.append(
            f"Марков: после «{category_label(result.markov_last, diff)}» чаще идёт "
            f"«{category_label(cat, diff)}» ({prob * 100:.0f}%, {total} переходов) — сигнал слабый."
        )
    return lines


def build_prompt(result: AnalysisResult, **ctx) -> str:
    """Детальный разбор (для кнопки статистики)."""
    lines = _data_block(result, **ctx)
    lines += [
        "",
        "Дай короткий разбор на русском (3–5 предложений): стоит ли ставить и на что. "
        "Если смещение не значимо — прямо скажи, что исходы равновероятны и "
        "гарантированного преимущества нет. Не выдумывай закономерности.",
    ]
    return "\n".join(lines)


def _top_line(result: AnalysisResult) -> str:
    diff = result.difficulty
    k = 3 if diff.value == "numbers" else len(result.cats)
    parts = []
    for c, p in top_predictions(result, k):
        label = c.category if diff.value == "numbers" else category_label(c.category, diff)
        parts.append(f"{label} ({p * 100:.1f}%)")
    return ", ".join(parts)


def build_comment_prompt(result: AnalysisResult, **ctx) -> str:
    """Промпт для живого комментария поверх посчитанных вероятностей."""
    lines = _data_block(result, **ctx)
    lines += [
        "",
        f"Текущие топ-кандидаты по вероятности: {_top_line(result)}.",
        "",
        "Дай ОДНО короткое живое замечание аналитика на русском об этой картине: "
        "что сейчас в лидерах и как расклад меняется по мере накопления данных. "
        "ЗАПРЕЩЕНЫ слова «наугад», «случайно», «уверенности нет», «гарантия». "
        "Опирайся только на приведённые цифры, ничего не выдумывай и не обещай выигрыш. "
        "Ровно одно предложение, живо и по делу.",
    ]
    return "\n".join(lines)


async def narrate(ai: "AIClient", result: AnalysisResult, **ctx) -> str:
    return await ai.complete(build_prompt(result, **ctx))


async def comment(ai: "AIClient", result: AnalysisResult, **ctx) -> str:
    """Короткий ИИ-комментарий поверх цифр (без «наугад/гарантий»)."""
    return await ai.complete(
        build_comment_prompt(result, **ctx), temperature=0.6, max_tokens=1200
    )
