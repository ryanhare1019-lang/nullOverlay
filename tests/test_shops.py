from nullscape_overlay.shops import (
    SHOPS,
    SHOP_LEVELS,
    is_shop_level,
    next_shop_level,
    next_shop_target,
)


def test_shop_levels_match_spec():
    assert SHOP_LEVELS == (3, 5, 8, 10, 13, 15)


def test_totals_match_spec():
    assert SHOPS[3].total == 415
    assert SHOPS[5].total == 714
    assert SHOPS[8].total == 1996
    assert SHOPS[10].total == 2642
    assert SHOPS[13].total == 1764
    assert SHOPS[15].total == 7870


def test_lap_2_is_a_curse_at_level_8():
    items_8 = [it for it in SHOPS[8].items if it.name == "Lap 2"]
    assert len(items_8) == 1
    assert items_8[0].type == "curse"
    assert items_8[0].cost is None


def test_level_10_has_choice_group():
    choice = next(it for it in SHOPS[10].items if it.type == "choice")
    names = [opt.name for opt in choice.options]
    assert names == ["Helmet + Radar", "More Alters"]


def test_level_13_has_choice_group():
    choice = next(it for it in SHOPS[13].items if it.type == "choice")
    names = [opt.name for opt in choice.options]
    assert names == ["Radar + Helmet", "More Alters"]


def test_is_shop_level():
    for lvl in (3, 5, 8, 10, 13, 15):
        assert is_shop_level(lvl)
    for lvl in (0, 1, 2, 4, 6, 7, 9, 11, 12, 14, 16):
        assert not is_shop_level(lvl)


def test_next_shop_target_between_shops():
    assert next_shop_target(0) == 415
    assert next_shop_target(1) == 415
    assert next_shop_target(2) == 415
    assert next_shop_target(4) == 714
    assert next_shop_target(6) == 1996
    assert next_shop_target(9) == 2642
    assert next_shop_target(11) == 1764
    assert next_shop_target(14) == 7870


def test_next_shop_target_on_shop_level():
    # On a shop level, "next" is the current shop.
    assert next_shop_target(3) == 415
    assert next_shop_target(15) == 7870


def test_next_shop_target_past_last_shop():
    assert next_shop_target(16) is None
    assert next_shop_level(16) is None
