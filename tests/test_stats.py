"""Тесты статистического ядра: χ²-p-value, детекция смещения, Марков."""

import math

from src.analysis import stats
from src.roulette.domain import Difficulty


def test_chi2_sf_known_values():
    # критические значения хи-квадрат при alpha=0.05
    assert math.isclose(stats.chi2_sf(3.8415, 1), 0.05, abs_tol=1e-3)
    assert math.isclose(stats.chi2_sf(5.9915, 2), 0.05, abs_tol=1e-3)
    assert stats.chi2_sf(0.0, 1) == 1.0
    assert stats.chi2_sf(1000.0, 1) < 1e-6


def test_empty_sample():
    r = stats.analyze([], Difficulty.EASY)
    assert r.n == 0 and r.biased is False and r.top is None
    assert "нет" in r.verdict.lower()


def test_balanced_colors_not_biased():
    # 180 red (число 1) + 180 black (число 2) + 10 green (0) = ровно ожидаемое
    numbers = [1] * 180 + [2] * 180 + [0] * 10
    r = stats.analyze(numbers, "easy")
    assert r.small_sample is False
    assert r.biased is False
    assert r.p_value > 0.05


def test_all_red_is_biased():
    r = stats.analyze([1] * 100, Difficulty.EASY)  # 1 — красное
    assert r.biased is True
    assert r.top is not None and r.top.category == "red"
    assert r.p_value < 0.05


def test_small_sample_not_biased():
    r = stats.analyze([1] * 5, Difficulty.EASY)
    assert r.small_sample is True
    assert r.biased is False


def test_markov_after_black_comes_red():
    numbers = [1, 2, 1, 2, 1, 2]  # красное/чёрное поочерёдно, последнее — чёрное
    r = stats.analyze(numbers, Difficulty.EASY)
    assert r.markov_last == "black"
    assert r.markov_pick is not None
    assert r.markov_pick[0] == "red"
    assert math.isclose(r.markov_pick[1], 1.0)


def test_numbers_mode_hot_number():
    numbers = [7] * 30 + list(range(37)) * 5  # 7 сильно перевес, остальные ~ровно
    r = stats.analyze(numbers, Difficulty.NUMBERS)
    assert r.df == 36
    assert r.biased is True
    assert r.top is not None and r.top.category == "7"


def test_dozen_mode_biased_first_dozen():
    r = stats.analyze([1] * 60, Difficulty.MEDIUM)  # всё в 1-й дюжине
    assert r.biased is True
    assert r.top is not None and r.top.category == "d1"


def test_predict_local_always_names_candidate():
    # даже на случайных малых данных должен назвать конкретное число
    r = stats.analyze([17, 5, 23, 0], Difficulty.NUMBERS)
    assert "число" in stats.predict_local(r)
    # и при пустой выборке кандидат всё равно назван
    assert "кандидат" in stats.predict_local(stats.analyze([], Difficulty.NUMBERS))


def test_top_predictions_uniform_at_zero():
    r = stats.analyze([], Difficulty.NUMBERS)
    top = stats.top_predictions(r, 3)
    assert len(top) == 3
    assert all(abs(p - 1 / 37) < 1e-9 for _, p in top)  # пусто → равновероятно


def test_top_predictions_favours_frequent():
    r = stats.analyze([17] * 10 + [8] * 3, Difficulty.NUMBERS)
    top = stats.top_predictions(r, 3)
    assert top[0][0].category == "17"  # самый частый — первый
    assert top[0][1] > top[1][1]


def test_category_labels():
    assert stats.category_label("red", Difficulty.EASY) == "красное"
    assert "1–12" in stats.category_label("d1", Difficulty.MEDIUM)
    assert stats.category_label("17", Difficulty.NUMBERS) == "число 17"
