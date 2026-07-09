"""Тексты сообщений бота (русский)."""

from __future__ import annotations

import html
from datetime import datetime

from src import venues
from src.access.service import RedeemStatus
from src.analysis.stats import DIFFICULTY_LABELS, AnalysisResult, category_label
from src.roulette.domain import Color

# алиас для клавиатур (метки режимов живут в analysis.stats)
DIFF_LABELS = DIFFICULTY_LABELS

GREETING = (
    "👋 Это <b>Casino Radmir AI</b> — бот-аналитик рулетки.\n\n"
    "Ты сообщаешь мне выпавшие числа, а я коплю статистику по каждому столу "
    "(отдельно по серверу и казино) и показываю <b>честную аналитику</b>: "
    "частоты, тесты на смещение, разбор от ИИ.\n\n"
    "⚠️ Рулетка случайна. Если перекоса в данных нет — я прямо скажу "
    "«равновероятно», а не выдумаю «прогноз». Смысл в том, чтобы поймать "
    "смещение, если оно у стола реально есть."
)

NEED_PROMO = (
    "🔒 Доступ пока закрыт.\n\n"
    "Пришли <b>промокод</b> сообщением, чтобы открыть доступ."
)

CHOOSE_SERVER = "🖥 Выбери <b>сервер</b> Radmir:"
CHOOSE_CASINO = "🎰 Выбери <b>казино</b>:"
CHOOSE_TABLE = "На схеме — расположение столов. Выбери <b>стол</b>:"
CHOOSE_DIFFICULTY = "🎯 Выбери <b>режим</b> (сложность):"

SEND_NUMBER_HINT = "Жми <b>кнопку с выпавшим числом (0–36)</b> на клавиатуре снизу."
USE_START = "Нажми /start, чтобы начать."
SESSION_LOST = "Сессия сброшена (бот перезапускался). Нажми /start, чтобы начать заново."
SPIN_THINKING = "📝 Записал. ⏳ Прогноз ИИ…"

# Короткий дисклеймер под результатами/прогнозами.
DISCLAIMER = (
    "⚠️ <i>Это лишь аналитика и прогноз ИИ, не гарантия. За ваши средства "
    "ответственности не несём — играйте разумно и ради развлечения.</i>"
)

_COLOR_RU = {
    Color.RED: "красное 🟥",
    Color.BLACK: "чёрное ⬛",
    Color.GREEN: "зеро 🟩",
}


def color_ru(color: Color) -> str:
    return _COLOR_RU.get(color, str(color))


def promo_ok(access_until: datetime | None) -> str:
    until = access_until.strftime("%d.%m.%Y %H:%M UTC") if access_until else "—"
    return f"✅ Промокод принят! Доступ до <b>{until}</b>.\nПогнали 👇"


def promo_error(status: RedeemStatus) -> str:
    return {
        RedeemStatus.UNKNOWN: "❌ Такого промокода нет. Проверь и пришли ещё раз.",
        RedeemStatus.INACTIVE: "❌ Этот промокод отключён.",
        RedeemStatus.ALREADY_USED: "❌ Ты уже активировал этот промокод.",
        RedeemStatus.EXHAUSTED: "❌ Лимит активаций промокода исчерпан.",
    }.get(status, "❌ Не удалось активировать промокод.")


def session_ready(server: str, casino: str, table_no: int, difficulty: str, total: int) -> str:
    return (
        "✅ <b>Стол выбран</b>\n\n"
        f"🖥 Сервер: <b>{venues.server_name(server)}</b>\n"
        f"🎰 Казино: <b>{venues.casino_name(casino)}</b>\n"
        f"🃏 Стол: <b>№{table_no}</b>\n"
        f"🎯 Режим: <b>{DIFF_LABELS.get(difficulty, difficulty)}</b>\n"
        f"📊 Уже накоплено спинов на столе: <b>{total}</b>\n\n"
        "Присылай <b>выпавшие числа (0–36)</b> — я буду их записывать. "
        "Аналитику подключим следующим шагом."
    )


def spin_full(number: int, color: Color, total: int, prediction: str) -> str:
    # prediction — текст от ИИ: экранируем спецсимволы HTML и чистим markdown **,
    # иначе символы < > & сломают отправку в parse_mode=HTML
    safe = html.escape(prediction.replace("**", "")).strip()
    return (
        f"📝 <b>{number}</b> ({color_ru(color)}) записано. Всего на столе: <b>{total}</b>.\n\n"
        f"🔮 <b>Что дальше:</b> {safe}\n\n"
        f"{DISCLAIMER}"
    )


def format_stats(result: AnalysisResult, *, server: str, casino: str, table_no: int) -> str:
    head = (
        f"📊 <b>Статистика</b> — {venues.server_name(server)}, "
        f"{venues.casino_name(casino)}, стол №{table_no}\n"
        f"Режим: {DIFF_LABELS[result.difficulty.value]} · выборка n={result.n}"
    )
    if result.n == 0:
        return head + "\n\nДанных пока нет — присылай выпавшие числа."

    rows = sorted(result.cats, key=lambda c: c.count, reverse=True)
    if result.difficulty.value == "numbers":
        rows = [c for c in rows if c.count > 0][:12]
    lines = [
        f"• {category_label(c.category, result.difficulty)}: "
        f"<b>{c.freq * 100:.1f}%</b> (n={c.count}, ожид. {c.expected * 100:.1f}%)"
        for c in rows
    ]
    tail = (
        f"\nχ²={result.chi2:.2f}, p={result.p_value:.3f} → "
        + ("⚠️ есть смещение" if result.biased else "смещения нет")
    )
    return (
        head + "\n\n" + "\n".join(lines) + "\n" + tail
        + "\n\n" + result.verdict + "\n\n" + DISCLAIMER
    )
