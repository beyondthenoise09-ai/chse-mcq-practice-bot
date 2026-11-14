"""Normal vs Premium theme. Premium mode = custom (animated) emoji + button icons, owner-controlled."""
from __future__ import annotations
from dataclasses import dataclass, field
from .gateway import Btn
from .styling import btn as btn_font

# slot -> normal emoji.  The owner sends custom emojis in THIS order to map premium ids.
SLOTS = [("sparkle", "✨"), ("trophy", "🏆"), ("book", "📚"), ("check", "✅"), ("cross", "❌"),
         ("target", "🎯"), ("fire", "🔥"), ("star", "⭐"), ("next", "➡️"), ("flag", "🏁"),
         ("cap", "🎓"), ("diamond", "💎")]
NORMAL = dict(SLOTS)

@dataclass
class Theme:
    premium: bool = False
    ids: dict = field(default_factory=dict)

    @classmethod
    def from_settings(cls, s: dict) -> "Theme":
        on = bool(s.get("premium_mode")) and bool(s.get("premium_emoji"))
        return cls(on, dict(s.get("premium_emoji") or {}) if on else {})

    @classmethod
    def normal(cls) -> "Theme":
        return cls(False, {})

    def e(self, slot: str) -> str:
        """Emoji for text (HTML)."""
        ch = NORMAL.get(slot, "")
        cid = self.ids.get(slot)
        if self.premium and cid:
            return f'<tg-emoji emoji-id="{cid}">{ch}</tg-emoji>'
        return ch

    def b(self, label: str, slot: str | None = None, data: str | None = None, url: str | None = None,
          style: str | None = None, fancy: bool = True) -> Btn:
        """Button: styled text + emoji (or premium icon when available)."""
        text = btn_font(label) if fancy else label
        icon = None
        if slot:
            cid = self.ids.get(slot) if self.premium else None
            if cid:
                icon = cid
            else:
                text = f"{NORMAL.get(slot, '')} {text}".strip()
        return Btn(text=text, data=data, url=url, style=style, icon_id=icon)
