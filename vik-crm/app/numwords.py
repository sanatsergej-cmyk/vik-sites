import re
from typing import List, Optional, Tuple

UNITS = {"ноль": 0, "один": 1, "одна": 1, "одно": 1, "два": 2, "две": 2, "три": 3, "четыре": 4, "пять": 5,
         "шесть": 6, "семь": 7, "восемь": 8, "девять": 9}
TEENS = {"десять": 10, "одиннадцать": 11, "двенадцать": 12, "тринадцать": 13, "четырнадцать": 14, "пятнадцать": 15,
         "шестнадцать": 16, "семнадцать": 17, "восемнадцать": 18, "девятнадцать": 19}
TENS = {"двадцать": 20, "тридцать": 30, "сорок": 40, "пятьдесят": 50, "шестьдесят": 60, "семьдесят": 70,
        "восемьдесят": 80, "девяносто": 90}
WHOLE = {"целых", "целая", "целое", "целый", "целую"}
DENOM = {"десятых": 10, "десятая": 10, "десятые": 10, "сотых": 100, "сотая": 100, "сотые": 100}


def _int(tokens: List[str], i: int) -> Optional[Tuple[int, int]]:
    total, j, last_kind = 0, i, 4
    while j < len(tokens):
        w = tokens[j]
        if w == "сто":
            val, kind = 100, 3
        elif w in TENS:
            val, kind = TENS[w], 2
        elif w in TEENS:
            val, kind = TEENS[w], 1
        elif w in UNITS:
            val, kind = UNITS[w], 1
        else:
            break
        if kind >= last_kind and not (kind == 1 and last_kind == 2):
            break
        if kind == 1 and last_kind == 1:
            break
        total += val
        last_kind = kind if kind != 1 or w in TEENS else 0
        j += 1
        if w in TEENS:
            break
    return (total, j) if j > i else None


def _fmt(v: float) -> str:
    return str(int(v)) if float(v).is_integer() else f"{v:g}"


def normalize(text: str) -> str:
    """Русские числительные и слова «плюс/процентов» -> цифры и знаки, чтобы разобрать команду по правилам."""
    t = text.lower().replace("ё", "е").strip().rstrip(".!,;?")
    t = re.sub(r"\bплюс\b", "+", t)
    t = re.sub(r"\bпроцент(?:а|ов)?\b", "%", t)
    tokens = t.split()
    out: List[str] = []
    i = 0
    while i < len(tokens):
        parsed = _int(tokens, i)
        if not parsed:
            out.append(tokens[i])
            i += 1
            continue
        value, j = parsed
        if j < len(tokens) and tokens[j] in WHOLE:
            frac = _int(tokens, j + 1)
            if frac and frac[1] < len(tokens) and tokens[frac[1]] in DENOM:
                out.append(_fmt(value + frac[0] / DENOM[tokens[frac[1]]]))
                i = frac[1] + 1
                continue
        out.append(str(value))
        i = j
    return " ".join(out)
