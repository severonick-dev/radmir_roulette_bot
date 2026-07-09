"""ИИ-разбор и прогноз поверх посчитанной статистики (DeepSeek через RouterAI).

ИИ получает уже посчитанные цифры (не сырые данные) и превращает их в
понятный игроку текст на русском. Честность обеспечивает системный промпт
клиента: не выдумывать закономерности, если смещения нет.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from src import venues
from src.analysis.stats import DIFFICULTY_LABELS, AnalysisResult, category_label

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


def build_predict_prompt(result: AnalysisResult, **ctx) -> str:
    """Короткий прогноз следующего исхода (после каждого спина)."""
    lines = _data_block(result, **ctx)
    lines += [
        "",
        "Предположи НАИБОЛЕЕ ВЕРОЯТНЫЙ следующий исход. Для режима чисел назови "
        "одно число 0–36 (можно 2–3 кандидата). Ответь максимум 2 короткими "
        "предложениями: ставка + честная оценка уверенности. При малых данных или "
        "отсутствии смещения прямо скажи, что это по сути случайность.",
    ]
    return "\n".join(lines)


async def narrate(ai: "AIClient", result: AnalysisResult, **ctx) -> str:
    return await ai.complete(build_prompt(result, **ctx))


async def predict_next(ai: "AIClient", result: AnalysisResult, **ctx) -> str:
    return await ai.complete(build_predict_prompt(result, **ctx))
