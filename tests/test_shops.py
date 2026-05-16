from nullscape_overlay.shops import (
    SHOPS,
    SHOP_LEVELS,
    is_shop_level,
    next_shop_level,
    next_shop_target,
)


def test_shop_levels_match_spec():
    assert SHOP_LEVELS == (3, 5, 8, 10, 13, 15)


def test_totals_are_sum_of_displayed_costs():
    # total = sum of "upgrade" items + cheaper option of any "choice" group.
    # Maybes and curses are excluded (optional / no cost).
    assert SHOPS[3].total == 78 + 108                               # Paycheck + Business License
    assert SHOPS[5].total == 114 + 142 + 71 + 266 + 78              # all 5 upgrades, Defuse Kit is maybe
    assert SHOPS[8].total == 213 + 425 + 114 + 78 + 556             # 5 upgrades; Defuse Kit maybe, Lap 2 curse
    assert SHOPS[10].total == 425 + 849 + 114 + 142 + 78 + 425 + 814  # 6 upgrades + Helmet+Radar (cheaper)
    assert SHOPS[13].total == 990 + 814                             # Ninja Belt + Radar+Helmet (cheaper)
    assert SHOPS[15].total == 5960 + 1910                           # Shield + Sports Shoes


def test_business_license_cost_per_shop():
    bl_lvl3 = next(it for it in SHOPS[3].items if it.name == "Business License")
    bl_lvl5 = next(it for it in SHOPS[5].items if it.name == "Business License")
    assert bl_lvl3.cost == 108
    assert bl_lvl5.cost == 266


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
    assert next_shop_target(0) == SHOPS[3].total
    assert next_shop_target(1) == SHOPS[3].total
    assert next_shop_target(2) == SHOPS[3].total
    assert next_shop_target(4) == SHOPS[5].total
    assert next_shop_target(6) == SHOPS[8].total
    assert next_shop_target(9) == SHOPS[10].total
    assert next_shop_target(11) == SHOPS[13].total
    assert next_shop_target(14) == SHOPS[15].total


def test_next_shop_target_on_shop_level():
    # On a shop level, "next" is the current shop.
    assert next_shop_target(3) == SHOPS[3].total
    assert next_shop_target(15) == SHOPS[15].total


def test_next_shop_target_past_last_shop():
    assert next_shop_target(16) is None
    assert next_shop_level(16) is None
