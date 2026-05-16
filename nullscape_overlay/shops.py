"""Static shop data for Nullscape Duo Standard mode.

Shops appear at fixed levels. Each shop lists recommended buys.
Type drives the row color in the overlay:
  - "upgrade" -> green
  - "maybe"   -> yellow
  - "curse"   -> red (price shown as "(curse)")
  - "choice"  -> "Choose one:" header with two indented sub-options
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

ItemType = Literal["upgrade", "maybe", "curse", "choice"]


@dataclass(frozen=True)
class Item:
    name: str
    cost: int | None
    type: ItemType
    # Only used when type == "choice"
    options: tuple["Item", ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class Shop:
    level: int
    total: int
    items: tuple[Item, ...]


SHOPS: dict[int, Shop] = {
    3: Shop(level=3, total=415, items=(
        Item("Paycheck", 78, "upgrade"),
        Item("Business License", 266, "upgrade"),
        Item("Adrenaline", 71, "maybe"),
    )),
    5: Shop(level=5, total=714, items=(
        Item("Swiftness Rings", 114, "upgrade"),
        Item("Medal", 142, "upgrade"),
        Item("Adrenaline", 71, "upgrade"),
        Item("Business License", 266, "upgrade"),
        Item("Paycheck", 78, "upgrade"),
        Item("Defuse Kit", 43, "maybe"),
    )),
    8: Shop(level=8, total=1996, items=(
        Item("Double Jump", 213, "upgrade"),
        Item("Grace Wings", 425, "upgrade"),
        Item("Swiftness Rings", 114, "upgrade"),
        Item("Paycheck", 78, "upgrade"),
        Item("Ice Skates", 556, "upgrade"),
        Item("Defuse Kit", 43, "maybe"),
        Item("Lap 2", None, "curse"),
    )),
    10: Shop(level=10, total=2642, items=(
        Item("Pocket Bell", 425, "upgrade"),
        Item("Advanced Gravity Coil", 849, "upgrade"),
        Item("Swiftness Rings", 114, "upgrade"),
        Item("Tria Orbs", 142, "upgrade"),
        Item("Paycheck", 78, "upgrade"),
        Item("Fanny Pack", 425, "upgrade"),
        Item("__choice__", None, "choice", options=(
            Item("Helmet + Radar", 814, "upgrade"),
            Item("More Alters", 849, "upgrade"),
        )),
    )),
    13: Shop(level=13, total=1764, items=(
        Item("Ninja Belt", 990, "upgrade"),
        Item("Bigger Grapple Points", 708, "maybe"),
        Item("__choice__", None, "choice", options=(
            Item("Radar + Helmet", 814, "upgrade"),
            Item("More Alters", 849, "upgrade"),
        )),
    )),
    15: Shop(level=15, total=7870, items=(
        Item("Shield", 5960, "upgrade"),
        Item("Sports Shoes", 1910, "upgrade"),
    )),
}

SHOP_LEVELS: tuple[int, ...] = tuple(sorted(SHOPS.keys()))


def is_shop_level(level: int) -> bool:
    return level in SHOPS


def next_shop_target(current_level: int) -> int | None:
    """Total gift cost of the next shop at or after current_level. None past the last shop."""
    for lvl in SHOP_LEVELS:
        if lvl >= current_level:
            return SHOPS[lvl].total
    return None


def next_shop_level(current_level: int) -> int | None:
    for lvl in SHOP_LEVELS:
        if lvl >= current_level:
            return lvl
    return None
