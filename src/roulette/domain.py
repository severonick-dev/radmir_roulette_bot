"""Доменная модель европейской рулетки (один зеро, числа 0–36).

Всё, что можно вычислить из выпавшего числа, считается здесь: цвет, дюжина,
колонка, половина, чёт/нечёт и позиция на колесе. Это единственный источник
правды о раскладке — БД и аналитика опираются только на эти функции.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

# Ячеек на колесе: 0–36, один зеро (европейская рулетка).
POCKETS = 37


class Color(str, Enum):
    RED = "red"
    BLACK = "black"
    GREEN = "green"  # только зеро


class Difficulty(str, Enum):
    """Режимы игры (сложность), которые выбирает игрок в боте."""

    EASY = "easy"        # красное / чёрное
    MEDIUM = "medium"    # дюжины: 1–12 / 13–24 / 25–36
    NUMBERS = "numbers"  # конкретные числа 0–36


RED_NUMBERS: frozenset[int] = frozenset(
    {1, 3, 5, 7, 9, 12, 14, 16, 18, 19, 21, 23, 25, 27, 30, 32, 34, 36}
)
BLACK_NUMBERS: frozenset[int] = frozenset(
    {2, 4, 6, 8, 10, 11, 13, 15, 17, 20, 22, 24, 26, 28, 29, 31, 33, 35}
)

# Порядок ячеек на колесе по часовой стрелке (европейское, один зеро).
# Нужен для будущего анализа «физических секторов» (соседей по колесу).
WHEEL_ORDER: tuple[int, ...] = (
    0, 32, 15, 19, 4, 21, 2, 25, 17, 34, 6, 27, 13, 36, 11, 30, 8, 23,
    10, 5, 24, 16, 33, 1, 20, 14, 31, 9, 22, 18, 29, 7, 28, 12, 35, 3, 26,
)


def validate(number: int) -> int:
    """Проверяет, что число — корректный исход рулетки (0–36)."""
    if not isinstance(number, int) or isinstance(number, bool) or not (0 <= number <= 36):
        raise ValueError(f"Число рулетки должно быть целым 0–36, получено: {number!r}")
    return number


def color_of(number: int) -> Color:
    validate(number)
    if number == 0:
        return Color.GREEN
    return Color.RED if number in RED_NUMBERS else Color.BLACK


def dozen_of(number: int) -> int:
    """Дюжина: 1 → 1–12, 2 → 13–24, 3 → 25–36, 0 → зеро (вне дюжин)."""
    validate(number)
    if number == 0:
        return 0
    return (number - 1) // 12 + 1


def column_of(number: int) -> int:
    """Колонка 1/2/3 (ставка 2:1); 0 → вне колонок."""
    validate(number)
    if number == 0:
        return 0
    rem = number % 3
    return 3 if rem == 0 else rem


def is_even(number: int) -> bool | None:
    """Чёт/нечёт; None для зеро (не считается ни чётом, ни нечётом)."""
    validate(number)
    if number == 0:
        return None
    return number % 2 == 0


def half_of(number: int) -> int:
    """Половина: 1 → 1–18 (low), 2 → 19–36 (high), 0 → зеро."""
    validate(number)
    if number == 0:
        return 0
    return 1 if number <= 18 else 2


def wheel_index(number: int) -> int:
    """Позиция числа на колесе (индекс в WHEEL_ORDER)."""
    validate(number)
    return WHEEL_ORDER.index(number)


@dataclass(frozen=True, slots=True)
class Outcome:
    """Полное описание выпавшего числа для сохранения и аналитики."""

    number: int
    color: Color
    dozen: int
    column: int
    half: int
    even: bool | None
    wheel_index: int


def classify(number: int) -> Outcome:
    """Разбирает число рулетки на все признаки сразу."""
    validate(number)
    return Outcome(
        number=number,
        color=color_of(number),
        dozen=dozen_of(number),
        column=column_of(number),
        half=half_of(number),
        even=is_even(number),
        wheel_index=wheel_index(number),
    )
