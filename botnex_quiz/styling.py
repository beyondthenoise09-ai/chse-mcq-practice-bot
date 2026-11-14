"""Premium typography helpers (Unicode styled fonts) - no normal font in headings."""
from __future__ import annotations

def _map(text: str, up: int, low: int, dig: int | None = None) -> str:
    out = []
    for ch in text:
        if "A" <= ch <= "Z":
            out.append(chr(up + ord(ch) - 65))
        elif "a" <= ch <= "z":
            out.append(chr(low + ord(ch) - 97))
        elif dig is not None and "0" <= ch <= "9":
            out.append(chr(dig + ord(ch) - 48))
        else:
            out.append(ch)
    return "".join(out)

def bold(t: str) -> str:            # 𝗕𝗼𝗹𝗱 sans
    return _map(t, 0x1D5D4, 0x1D5EE, 0x1D7EC)

def bold_italic(t: str) -> str:     # 𝘽𝙤𝙡𝙙 𝙄𝙩𝙖𝙡𝙞𝙘 sans
    return _map(t, 0x1D63C, 0x1D656)

def script(t: str) -> str:          # 𝓢𝓬𝓻𝓲𝓹𝓽 bold
    return _map(t, 0x1D4D0, 0x1D4EA)

def mono(t: str) -> str:            # 𝙼𝚘𝚗𝚘
    return _map(t, 0x1D670, 0x1D68A, 0x1D7F6)

_SMALL = dict(zip("abcdefghijklmnopqrstuvwxyz", "ᴀʙᴄᴅᴇꜰɢʜɪᴊᴋʟᴍɴᴏᴘǫʀsᴛᴜᴠᴡxʏᴢ"))
_BTN = {**_SMALL, "a": "Λ", "e": "ε", "o": "σ", "n": "η"}   # same look as the music bot buttons

def btn(t: str) -> str:
    """ʙᴜᴛᴛᴏɴ ꜱᴛʏʟᴇ text: small caps with Λ ε σ η accents (like the music bot buttons)."""
    return "".join(_BTN.get(c, c) for c in t.lower())

def esc(t: object) -> str:
    """HTML escape for Telegram HTML parse mode."""
    return str(t).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

LINE = "━━━━━━━━━━━━━━━━━━"
