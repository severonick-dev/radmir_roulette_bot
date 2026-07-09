"""Хендлеры флоу: гейт доступа → сервер → казино → стол → сложность → приём чисел."""

from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import BufferedInputFile, CallbackQuery, Message

from src.access import service
from src.bot import texts
from src.bot.floorplan import render_floorplan
from src.bot.keyboards import (
    Pick,
    active_kb,
    casino_kb,
    difficulty_kb,
    servers_kb,
    table_kb,
)
from src.bot.states import Flow
from src.db import repo
from src.db.base import session_scope
from src.roulette import domain

router = Router()


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
        await send_to.answer(texts.CHOOSE_SERVER, reply_markup=servers_kb())
    else:
        await state.set_state(Flow.promo)
        await send_to.answer(texts.NEED_PROMO)


@router.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext, admin_ids: frozenset[int] = frozenset()) -> None:
    await message.answer(texts.GREETING)
    await _begin_flow(
        message,
        user_id=message.from_user.id,
        username=message.from_user.username,
        state=state,
        admin_ids=admin_ids,
    )


@router.message(Command("reset"))
async def cmd_reset(message: Message, state: FSMContext, admin_ids: frozenset[int] = frozenset()) -> None:
    await _begin_flow(
        message,
        user_id=message.from_user.id,
        username=message.from_user.username,
        state=state,
        admin_ids=admin_ids,
    )


@router.message(Flow.promo)
async def on_promo(message: Message, state: FSMContext) -> None:
    code = (message.text or "").strip()
    async with session_scope() as db:
        result = await service.redeem_promo(
            db,
            tg_user_id=message.from_user.id,
            code=code,
            username=message.from_user.username,
        )
    if result.status is service.RedeemStatus.OK:
        await message.answer(texts.promo_ok(result.access_until))
        await state.set_state(Flow.server)
        await message.answer(texts.CHOOSE_SERVER, reply_markup=servers_kb())
    else:
        await message.answer(texts.promo_error(result.status))


@router.callback_query(Flow.server, Pick.filter(F.step == "server"))
async def on_server(cb: CallbackQuery, callback_data: Pick, state: FSMContext) -> None:
    await state.update_data(server=callback_data.value)
    await state.set_state(Flow.casino)
    await cb.message.edit_text(texts.CHOOSE_CASINO, reply_markup=casino_kb())
    await cb.answer()


@router.callback_query(Flow.casino, Pick.filter(F.step == "casino"))
async def on_casino(cb: CallbackQuery, callback_data: Pick, state: FSMContext) -> None:
    await state.update_data(casino=callback_data.value)
    await state.set_state(Flow.table)
    png = render_floorplan(highlight=None)
    await cb.message.answer_photo(
        BufferedInputFile(png, "plan.png"),
        caption=texts.CHOOSE_TABLE,
        reply_markup=table_kb(),
    )
    await cb.answer()


@router.callback_query(Flow.table, Pick.filter(F.step == "table"))
async def on_table(cb: CallbackQuery, callback_data: Pick, state: FSMContext) -> None:
    await state.update_data(table=int(callback_data.value))
    await state.set_state(Flow.difficulty)
    await cb.message.answer(texts.CHOOSE_DIFFICULTY, reply_markup=difficulty_kb())
    await cb.answer()


@router.callback_query(Flow.difficulty, Pick.filter(F.step == "diff"))
async def on_difficulty(cb: CallbackQuery, callback_data: Pick, state: FSMContext) -> None:
    data = await state.get_data()
    server, casino, table = data["server"], data["casino"], data["table"]
    difficulty = callback_data.value

    async with session_scope() as db:
        sess = await repo.create_session(
            db,
            user_id=cb.from_user.id,
            server=server,
            casino=casino,
            table_no=table,
            difficulty=difficulty,
        )
        total = await repo.count_spins(db, server=server, casino=casino, table_no=table)

    await state.update_data(session_id=sess.id, difficulty=difficulty)
    await state.set_state(Flow.active)
    png = render_floorplan(highlight=table)
    await cb.message.answer_photo(
        BufferedInputFile(png, "plan.png"),
        caption=texts.session_ready(server, casino, table, difficulty, total),
        reply_markup=active_kb(),
    )
    await cb.answer()


@router.callback_query(Pick.filter(F.step == "restart"))
async def on_restart(
    cb: CallbackQuery, state: FSMContext, admin_ids: frozenset[int] = frozenset()
) -> None:
    await cb.answer()
    await _begin_flow(
        cb.message,
        user_id=cb.from_user.id,
        username=cb.from_user.username,
        state=state,
        admin_ids=admin_ids,
    )


@router.callback_query(Pick.filter())
async def on_stale_button(cb: CallbackQuery) -> None:
    # клик по устаревшей кнопке из прошлого шага
    await cb.answer("Кнопка устарела — продолжай текущий шаг.")


@router.message(Flow.active)
async def on_active_number(message: Message, state: FSMContext) -> None:
    text = (message.text or "").strip()
    if not text.isdigit():
        await message.answer(texts.SEND_NUMBER_HINT)
        return
    number = int(text)
    if not (0 <= number <= 36):
        await message.answer("Число рулетки должно быть 0–36.")
        return

    data = await state.get_data()
    async with session_scope() as db:
        await repo.add_spin(
            db,
            server=data["server"],
            casino=data["casino"],
            table_no=data["table"],
            number=number,
            user_id=message.from_user.id,
            session_id=data.get("session_id"),
        )
        total = await repo.count_spins(
            db, server=data["server"], casino=data["casino"], table_no=data["table"]
        )
    outcome = domain.classify(number)
    await message.answer(texts.spin_saved(number, outcome.color, total))


@router.message(StateFilter(None))
async def on_no_state(message: Message) -> None:
    await message.answer(texts.USE_START)
