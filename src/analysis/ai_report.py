"""ИИ-разбор поверх посчитанной статистики (DeepSeek через RouterAI).

ИИ получает уже посчитанные цифры (не сырые данные) и превращает их в
понятный игроку разбор на русском. Честность обеспечивает системный промпт
клиента: не выдумывать закономерности, если смещения нет.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from src import venues
from src.analysis.stats import DIFFICULTY_LABELS, AnalysisResult, category_label

if TYPE_CHECKING:
    from src.ai.client import AIClient


def build_prompt(
    result: AnalysisResult, *, server: str, casino: str, table_no: int, window: int
) -> str:
    diff = result.difficulty
    lines = [
        f"Режим ставки: {DIFFICULTY_LABELS[diff.value]}.",
        f"Точка: сервер {venues.server_name(server)}, {venues.casino_name(casino)}, "
        f"стол №{table_no}.",
        f"Выборка: n={result.n} последних спинов (окно {window}).",
        "",
        "Наблюдаемое распределение (наблюдаемо% / ожидаемо%):",
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
    lines.append("")
    lines.append(f"χ²={result.chi2:.2f}, p={result.p_value:.3f}, df={result.df} → смещение {verdict}.")
    if result.markov_pick:
        cat, prob, total = result.markov_pick
        lines.append(
            f"Марков: после «{category_label(result.markov_last, diff)}» чаще идёт "
            f"«{category_label(cat, diff)}» ({prob * 100:.0f}%, {total} переходов) — сигнал слабый."
        )
    lines += [
        "",
        "Дай короткий разбор на русском (3–5 предложений): стоит ли ставить и на что. "
        "Если смещение не значимо — прямо скажи, что исходы равновероятны и "
        "гарантированного преимущества нет. Не выдумывай закономерности.",
    ]
    return "\n".join(lines)


async def narrate(
    ai: AIClient,
    result: AnalysisResult,
    *,
    server: str,
    casino: str,
    table_no: int,
    window: int,
) -> str:
    prompt = build_prompt(
        result, server=server, casino=casino, table_no=table_no, window=window
    )
    return await ai.complete(prompt)
