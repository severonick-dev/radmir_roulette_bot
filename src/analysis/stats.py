"""Статистическое ядро аналитики рулетки (чистый Python, без scipy/numpy).

Считает по последовательности выпавших чисел:
  • наблюдаемое распределение против ожидаемого (равновероятного);
  • χ²-тест согласия → есть ли статистически значимое смещение RNG;
  • простую цепь Маркова (что чаще следует за последним исходом).

Философия честная: если χ² не значим — говорим «равновероятно», а не
выдумываем закономерность. Прогноз имеет смысл только при значимом смещении.
"""

from __future__ import annotations

import math
from collections import Counter
from dataclasses import dataclass

from src.roulette import domain
from src.roulette.domain import Difficulty

# порог значимости и правило «ожидаемая частота в ячейке >= 5»
ALPHA = 0.05
MIN_CELL = 5

DIFFICULTY_LABELS = {
    "easy": "Красное / Чёрное",
    "medium": "Дюжины (1–12 / 13–24 / 25–36)",
    "numbers": "Числа 0–36",
}


# --------------------------------------------------------------------------
# χ²: p-value через регуляризованную верхнюю неполную гамма-функцию Q(a, x)
# (алгоритм Numerical Recipes: ряд при x < a+1, цепная дробь при x >= a+1)
# --------------------------------------------------------------------------
def _gammp_series(a: float, x: float) -> float:
    gln = math.lgamma(a)
    ap = a
    total = 1.0 / a
    delta = total
    for _ in range(1000):
        ap += 1.0
        delta *= x / ap
        total += delta
        if abs(delta) < abs(total) * 1e-14:
            break
    return total * math.exp(-x + a * math.log(x) - gln)


def _gammq_cf(a: float, x: float) -> float:
    gln = math.lgamma(a)
    tiny = 1e-300
    b = x + 1.0 - a
    c = 1.0 / tiny
    d = 1.0 / b
    h = d
    for i in range(1, 1000):
        an = -i * (i - a)
        b += 2.0
        d = an * d + b
        if abs(d) < tiny:
            d = tiny
        c = b + an / c
        if abs(c) < tiny:
            c = tiny
        d = 1.0 / d
        delta = d * c
        h *= delta
        if abs(delta - 1.0) < 1e-14:
            break
    return math.exp(-x + a * math.log(x) - gln) * h


def gammq(a: float, x: float) -> float:
    """Q(a, x) = 1 - P(a, x), регуляризованная верхняя неполная гамма."""
    if x <= 0.0:
        return 1.0
    if x < a + 1.0:
        return 1.0 - _gammp_series(a, x)
    return _gammq_cf(a, x)


def chi2_sf(x: float, df: int) -> float:
    """P(χ²_df > x) — правый хвост распределения хи-квадрат."""
    if x <= 0.0 or df <= 0:
        return 1.0
    return gammq(df / 2.0, x / 2.0)


# --------------------------------------------------------------------------
# Раскладка исходов по режимам
# --------------------------------------------------------------------------
def _expected(difficulty: Difficulty) -> dict[str, float]:
    if difficulty is Difficulty.EASY:
        return {"red": 18 / 37, "black": 18 / 37, "green": 1 / 37}
    if difficulty is Difficulty.MEDIUM:
        return {"d1": 12 / 37, "d2": 12 / 37, "d3": 12 / 37, "zero": 1 / 37}
    return {str(n): 1 / 37 for n in range(37)}


def _category(number: int, difficulty: Difficulty) -> str:
    o = domain.classify(number)
    if difficulty is Difficulty.EASY:
        return o.color.value
    if difficulty is Difficulty.MEDIUM:
        return "zero" if o.dozen == 0 else f"d{o.dozen}"
    return str(o.number)


def category_label(cat: str, difficulty: Difficulty) -> str:
    if difficulty is Difficulty.EASY:
        return {"red": "красное", "black": "чёрное", "green": "зеро"}.get(cat, cat)
    if difficulty is Difficulty.MEDIUM:
        return {
            "d1": "1-я дюжина (1–12)",
            "d2": "2-я дюжина (13–24)",
            "d3": "3-я дюжина (25–36)",
            "zero": "зеро",
        }.get(cat, cat)
    return f"число {cat}"


# --------------------------------------------------------------------------
# Результат
# --------------------------------------------------------------------------
@dataclass(frozen=True, slots=True)
class CatStat:
    category: str
    count: int
    freq: float       # наблюдаемая доля
    expected: float   # ожидаемая доля
    lift: float       # freq / expected (>1 — сверх нормы)


@dataclass(frozen=True, slots=True)
class AnalysisResult:
    difficulty: Difficulty
    n: int
    df: int
    small_sample: bool
    cats: tuple[CatStat, ...]
    chi2: float
    p_value: float
    biased: bool
    top: CatStat | None                         # самый «перевес» кандидат
    markov_last: str | None
    markov_pick: tuple[str, float, int] | None  # (категория, доля, число переходов)
    verdict: str


def _markov(seq: list[str]) -> tuple[str | None, tuple[str, float, int] | None]:
    if not seq:
        return None, None
    last = seq[-1]
    following = Counter(b for a, b in zip(seq, seq[1:]) if a == last)
    total = sum(following.values())
    if total == 0:
        return last, None
    cat, cnt = following.most_common(1)[0]
    return last, (cat, cnt / total, total)


def _verdict(difficulty, n, small, biased, p, top) -> str:
    if n == 0:
        return "Данных пока нет — присылай выпавшие числа."
    min_n = MIN_CELL * len(_expected(difficulty))
    if small:
        return (
            f"Мало данных (n={n}, для теста нужно ≥{min_n}). "
            "Пока считаю исходы равновероятными — копим статистику."
        )
    if biased and top is not None:
        return (
            f"⚠️ Обнаружено смещение (p={p:.3f}) в сторону "
            f"«{category_label(top.category, difficulty)}»: наблюдаемо "
            f"{top.freq * 100:.1f}% против ожидаемых {top.expected * 100:.1f}%. "
            "Есть смысл присмотреться к этому исходу."
        )
    return (
        f"Значимого смещения нет (p={p:.2f}). Исходы равновероятны — "
        "математического преимущества по этим данным не видно."
    )


def predict_local(result: "AnalysisResult") -> str:
    """Короткий прогноз без ИИ (фолбэк, если ИИ выключен/недоступен)."""
    diff = result.difficulty
    if result.n == 0:
        return "данных нет — первый спин это чистая случайность."
    if result.biased and result.top is not None:
        return (
            f"вероятнее «{category_label(result.top.category, diff)}» — "
            f"в данных есть перекос (p={result.p_value:.3f})."
        )
    if result.markov_pick is not None:
        cat, prob, total = result.markov_pick
        return (
            f"слабый сигнал: после «{category_label(result.markov_last, diff)}» чаще "
            f"«{category_label(cat, diff)}» ({prob * 100:.0f}%, {total} набл.) — не гарантия."
        )
    return "значимого перекоса нет — следующий исход по сути случайный."


def analyze(numbers: list[int], difficulty: Difficulty | str) -> AnalysisResult:
    """Полный разбор последовательности чисел под выбранный режим."""
    diff = difficulty if isinstance(difficulty, Difficulty) else Difficulty(difficulty)
    expected = _expected(diff)
    n = len(numbers)

    counts = Counter(_category(num, diff) for num in numbers)
    cats: list[CatStat] = []
    chi2 = 0.0
    for cat, p in expected.items():
        obs = counts.get(cat, 0)
        exp = n * p
        if exp > 0:
            chi2 += (obs - exp) ** 2 / exp
        freq = obs / n if n else 0.0
        lift = (freq / p) if (n and p) else 0.0
        cats.append(CatStat(cat, obs, freq, p, lift))

    df = len(expected) - 1
    p_value = chi2_sf(chi2, df) if n else 1.0
    small = n < MIN_CELL * len(expected)
    biased = bool(n) and not small and p_value < ALPHA
    top = max(cats, key=lambda c: c.lift) if n else None

    seq = [_category(num, diff) for num in numbers]
    markov_last, markov_pick = _markov(seq)

    return AnalysisResult(
        difficulty=diff,
        n=n,
        df=df,
        small_sample=small,
        cats=tuple(cats),
        chi2=chi2,
        p_value=p_value,
        biased=biased,
        top=top if biased else None,
        markov_last=markov_last,
        markov_pick=markov_pick,
        verdict=_verdict(diff, n, small, biased, p_value, top),
    )
