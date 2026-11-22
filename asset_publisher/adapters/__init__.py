from .base import Adapter, Context, Result
from .cgtrader import CGTrader
from .etsy import Etsy
from .itch import Itch
from .kit import Booth, Cults, Fab
from .roblox import Roblox
from .sketchfab import Sketchfab

# 新しい販売先はここに足す。並び順が実行順・表示順になる
ADAPTERS: dict[str, Adapter] = {
    a.name: a
    for a in [Sketchfab(), CGTrader(), Etsy(), Itch(), Roblox(), Fab(), Booth(), Cults()]
}

__all__ = ["ADAPTERS", "Adapter", "Context", "Result"]
