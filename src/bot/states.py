"""FSM-состояния флоу бота."""

from __future__ import annotations

from aiogram.fsm.state import State, StatesGroup


class Flow(StatesGroup):
    promo = State()       # ждём промокод (нет доступа)
    server = State()      # выбор сервера (1–21)
    casino = State()      # выбор казино
    table = State()       # выбор стола (1–6)
    difficulty = State()  # выбор сложности
    active = State()      # сессия активна — принимаем выпавшие числа
