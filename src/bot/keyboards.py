"""Инлайн-клавиатуры и callback-данные флоу."""

from __future__ import annotations

from aiogram.filters.callback_data import CallbackData
from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from src import venues
from src.bot.texts import DIFF_LABELS


class Pick(CallbackData, prefix="pick"):
    """Универсальный колбэк выбора: step = server|casino|table|diff|restart."""

    step: str
    value: str


def servers_kb() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for slug in venues.SERVERS:  # "1".."21"
        b.button(text=slug, callback_data=Pick(step="server", value=slug))
    b.adjust(5)
    return b.as_markup()


def casino_kb() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for slug, name in venues.CASINOS.items():
        b.button(text=name, callback_data=Pick(step="casino", value=slug))
    b.adjust(2)
    return b.as_markup()


def table_kb() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for n in venues.TABLES:
        b.button(text=f"Стол {n}", callback_data=Pick(step="table", value=str(n)))
    b.adjust(3)
    return b.as_markup()


def difficulty_kb() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for key, label in DIFF_LABELS.items():
        b.button(text=label, callback_data=Pick(step="diff", value=key))
    b.adjust(1)
    return b.as_markup()


def active_kb() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="🔄 Сменить стол/казино", callback_data=Pick(step="restart", value="-"))
    return b.as_markup()
