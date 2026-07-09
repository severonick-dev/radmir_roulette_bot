"""Хендлеры флоу: гейт доступа → сервер → казино → стол → сложность → приём чисел."""

from __future__ import annotations

import html
import logging
from typing import TYPE_CHECKING

from aiogram import F, Router
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    BufferedInputFile,
    CallbackQuery,
    Message,
    ReplyKeyboardRemove,
)

from src.access import service
from src.analysis import ai_report, engine, stats
from src.bot import keyboards, texts
from src.bot.floorplan import render_floorplan
from src.bot.keyboards import Pick
from src.bot.states import Flow
from src.db import repo
from src.db.base import session_scope
from src.roulette import domain

if TYPE_CHECKING:
    from src.ai.client import AIClient

router = Router()

_SESSION_KEYS = ("server", "casino", "table", "difficulty")


async def _begin_flow(
    send_to: Message,
    *,
    user_id: int,
    username: str | None,
    state: FSMContext,
    admin_ids: frozenset[int],
) -> None:
    """Проверяет доступ и ведёт либо к промокоду, либо к выбору сервера."""
    await state.clear()
    async with session_scope() as db:
        ok, _ = await service.check_access(
            db, tg_user_id=user_id, username=username, admin_ids=admin_ids
        )
    if ok:
        await state.set_state(Flow.server)
        await send_to.answer(texts.CHOOSE_SERVER, reply_markup=keyboards.servers_kb())
    else:
        await state.set_state(Flow.promo)
        await send_to.answer(texts.NEED_PROMO)


@router.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext, admin_ids: frozenset[int] = frozenset()) -> None:
    await message.answer(texts.GREETING)
    await _begin_flow(
        message, user_id=message.from_user.id, username=message.from_user.username,
        state=state, admin_ids=admin_ids,
    )


@router.message(Command("reset"))
async def cmd_reset(message: Message, state: FSMContext, admin_ids: frozenset[int] = frozenset()) -> None:
    await message.answer("Начинаем заново.", reply_markup=ReplyKeyboardRemove())
    await _begin_flow(
        message, user_id=message.from_user.id, username=message.from_user.username,
        state=state, admin_ids=admin_ids,
    )


@router.message(Flow.promo)
async def on_promo(message: Message, state: FSMContext) -> None:
    async with session_scope() as db:
        result = await service.redeem_promo(
            db,
            tg_user_id=message.from_user.id,
            code=(message.text or "").strip(),
            username=message.from_user.username,
        )
    if result.status is service.RedeemStatus.OK:
        await message.answer(texts.promo_ok(result.access_until))
        await state.set_state(Flow.server)
        await message.answer(texts.CHOOSE_SERVER, reply_markup=keyboards.servers_kb())
    else:
        await message.answer(texts.promo_error(result.status))


@router.callback_query(Flow.server, Pick.filter(F.step == "server"))
async def on_server(cb: CallbackQuery, callback_data: Pick, state: FSMContext) -> None:
    await state.update_data(server=callback_data.value)
    await state.set_state(Flow.casino)
    await cb.message.edit_text(texts.CHOOSE_CASINO, reply_markup=keyboards.casino_kb())
    await cb.answer()


@router.callback_query(Flow.casino, Pick.filter(F.step == "casino"))
async def on_casino(cb: CallbackQuery, callback_data: Pick, state: FSMContext) -> None:
    await state.update_data(casino=callback_data.value)
    await state.set_state(Flow.table)
    await cb.message.answer_photo(
        BufferedInputFile(render_floorplan(highlight=None), "plan.png"),
        caption=texts.CHOOSE_TABLE,
        reply_markup=keyboards.table_kb(),
    )
    await cb.answer()


@router.callback_query(Flow.table, Pick.filter(F.step == "table"))
async def on_table(cb: CallbackQuery, callback_data: Pick, state: FSMContext) -> None:
    await state.update_data(table=int(callback_data.value))
    await state.set_state(Flow.difficulty)
    await cb.message.answer(texts.CHOOSE_DIFFICULTY, reply_markup=keyboards.difficulty_kb())
    await cb.answer()


@router.callback_query(Flow.difficulty, Pick.filter(F.step == "diff"))
async def on_difficulty(cb: CallbackQuery, callback_data: Pick, state: FSMContext) -> None:
    data = await state.get_data()
    server, casino, table = data["server"], data["casino"], data["table"]
    difficulty = callback_data.value

    async with session_scope() as db:
        sess = await repo.create_session(
            db, user_id=cb.from_user.id, server=server, casino=casino,
            table_no=table, difficulty=difficulty,
        )
        total = await repo.count_spins(db, server=server, casino=casino, table_no=table)

    await state.update_data(session_id=sess.id, difficulty=difficulty)
    await state.set_state(Flow.active)
    await cb.message.answer_photo(
        BufferedInputFile(render_floorplan(highlight=table), "plan.png"),
        caption=texts.session_ready(server, casino, table, difficulty, total),
        reply_markup=keyboards.numpad_kb(),
    )
    await cb.answer()


@router.callback_query(Pick.filter())
async def on_stale_button(cb: CallbackQuery) -> None:
    # клик по устаревшей инлайн-кнопке из прошлого шага
    await cb.answer("Кнопка устарела — продолжай текущий шаг.")


# ---------------------------------------------------------------------------
# Активная сессия: цифровая клавиатура + авто-прогноз
# ---------------------------------------------------------------------------
async def _process_spin(message: Message, state: FSMContext, number: int, ai, window: int) -> None:
    data = await state.get_data()
    if not all(k in data for k in _SESSION_KEYS):
        await state.clear()
        await message.answer(texts.SESSION_LOST, reply_markup=ReplyKeyboardRemove())
        return
    try:
        async with session_scope() as db:
            await repo.add_spin(
                db, server=data["server"], casino=data["casino"], table_no=data["table"],
                number=number, user_id=message.from_user.id, session_id=data.get("session_id"),
            )
            total = await repo.count_spins(
                db, server=data["server"], casino=data["casino"], table_no=data["table"]
            )
            numbers = await repo.recent_numbers(
                db, server=data["server"], casino=data["casino"], table_no=data["table"], limit=window
            )
        result = stats.analyze(numbers, data["difficulty"])
    except Exception:
        logging.exception("spin save/analyze failed")
        await message.answer("⚠️ Не удалось сохранить число, попробуй ещё раз.")
        return

    color = domain.classify(number).color
    block = texts.format_prediction(result)
    # цифры показываем сразу; комментарий ИИ дописываем следом
    msg = await message.answer(texts.spin_full(number, color, total, block))
    if ai is None:
        return
    try:
        raw = await ai_report.comment(
            ai, result, server=data["server"], casino=data["casino"],
            table_no=data["table"], window=window,
        )
        safe = html.escape(raw.replace("**", "").strip())
        await msg.edit_text(texts.spin_full(number, color, total, block, comment=safe))
    except Exception:
        logging.exception("AI comment failed")


async def _send_stats(message: Message, state: FSMContext, window: int) -> None:
    data = await state.get_data()
    if not all(k in data for k in _SESSION_KEYS):
        await state.clear()
        await message.answer(texts.SESSION_LOST, reply_markup=ReplyKeyboardRemove())
        return
    async with session_scope() as db:
        result = await engine.analyze_table(
            db, server=data["server"], casino=data["casino"],
            table_no=data["table"], difficulty=data["difficulty"], window=window,
        )
    await message.answer(
        texts.format_stats(
            result, server=data["server"], casino=data["casino"], table_no=data["table"]
        )
    )


@router.message(Flow.active)
async def on_active(
    message: Message,
    state: FSMContext,
    ai: "AIClient | None" = None,
    window: int = 300,
    admin_ids: frozenset[int] = frozenset(),
) -> None:
    text = (message.text or "").strip()
    if text == keyboards.STATS_BTN:
        await _send_stats(message, state, window)
        return
    if text == keyboards.CHANGE_BTN:
        await message.answer("Меняем стол 👇", reply_markup=ReplyKeyboardRemove())
        await _begin_flow(
            message, user_id=message.from_user.id, username=message.from_user.username,
            state=state, admin_ids=admin_ids,
        )
        return
    if text.isdigit() and 0 <= int(text) <= 36:
        await _process_spin(message, state, int(text), ai, window)
        return
    await message.answer(texts.SEND_NUMBER_HINT)


@router.message(StateFilter(None))
async def on_no_state(message: Message) -> None:
    await message.answer(texts.USE_START)
