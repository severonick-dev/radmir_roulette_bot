"""Тесты «чистых» частей бота: схема зала, клавиатуры, тексты."""

from src.bot import keyboards, texts
from src.bot.floorplan import TABLE_POS, render_floorplan
from src.roulette.domain import Color

PNG_SIG = b"\x89PNG\r\n\x1a\n"


def test_floorplan_is_png():
    data = render_floorplan()
    assert data[:8] == PNG_SIG
    assert len(data) > 1000


def test_floorplan_highlight_changes_image():
    assert render_floorplan(None) != render_floorplan(3)


def test_all_six_tables_have_positions():
    assert set(TABLE_POS) == {1, 2, 3, 4, 5, 6}


def _button_count(kb) -> int:
    return sum(len(row) for row in kb.inline_keyboard)


def test_servers_kb_has_21_buttons():
    assert _button_count(keyboards.servers_kb()) == 21


def test_casino_kb_has_two():
    assert _button_count(keyboards.casino_kb()) == 2


def test_table_kb_has_six():
    assert _button_count(keyboards.table_kb()) == 6


def test_difficulty_kb_matches_labels():
    kb = keyboards.difficulty_kb()
    assert _button_count(kb) == len(texts.DIFF_LABELS) == 3


def test_color_ru_covers_all():
    assert "красное" in texts.color_ru(Color.RED)
    assert "чёрное" in texts.color_ru(Color.BLACK)
    assert "зеро" in texts.color_ru(Color.GREEN)


def test_numpad_has_39_buttons():
    kb = keyboards.numpad_kb()
    assert sum(len(r) for r in kb.keyboard) == 39  # 0..36 + 2 действия


def test_spin_full_escapes_ai_text():
    # опасный текст от ИИ (< и **) не должен попасть сырым в HTML
    out = texts.spin_full(7, Color.RED, 10, "ставь <3% и **точно**")
    assert "<3%" not in out
    assert "&lt;3%" in out
    assert "**" not in out
