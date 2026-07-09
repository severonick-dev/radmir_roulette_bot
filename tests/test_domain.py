"""Проверки доменной логики рулетки."""

import pytest

from src.roulette import domain as d


def test_color_counts_and_disjoint():
    assert len(d.RED_NUMBERS) == 18
    assert len(d.BLACK_NUMBERS) == 18
    assert d.RED_NUMBERS.isdisjoint(d.BLACK_NUMBERS)


def test_all_numbers_covered_exactly_once():
    assert (d.RED_NUMBERS | d.BLACK_NUMBERS | {0}) == set(range(37))


def test_wheel_order_is_full_permutation():
    assert len(d.WHEEL_ORDER) == 37
    assert set(d.WHEEL_ORDER) == set(range(37))


def test_color_of():
    assert d.color_of(0) is d.Color.GREEN
    assert d.color_of(32) is d.Color.RED
    assert d.color_of(2) is d.Color.BLACK


def test_dozen():
    assert d.dozen_of(0) == 0
    assert d.dozen_of(1) == 1
    assert d.dozen_of(12) == 1
    assert d.dozen_of(13) == 2
    assert d.dozen_of(24) == 2
    assert d.dozen_of(25) == 3
    assert d.dozen_of(36) == 3


def test_column():
    assert d.column_of(0) == 0
    assert d.column_of(1) == 1
    assert d.column_of(2) == 2
    assert d.column_of(3) == 3
    assert d.column_of(34) == 1
    assert d.column_of(36) == 3


def test_half_and_even():
    assert d.half_of(18) == 1
    assert d.half_of(19) == 2
    assert d.half_of(0) == 0
    assert d.is_even(0) is None
    assert d.is_even(2) is True
    assert d.is_even(3) is False


def test_classify():
    o = d.classify(0)
    assert o.color is d.Color.GREEN and o.even is None and o.dozen == 0
    r = d.classify(32)
    assert r.color is d.Color.RED and r.dozen == 3 and r.even is True


@pytest.mark.parametrize("bad", [-1, 37, 100, 1.5, True, "5"])
def test_validate_rejects_bad(bad):
    with pytest.raises(ValueError):
        d.validate(bad)
