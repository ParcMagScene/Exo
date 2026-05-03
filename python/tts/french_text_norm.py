"""Pre-normalisation francaise pour CosyVoice2.

S'execute AVANT gruut. Convertit les elements que gruut ne resout pas
proprement et qui causent une lecture degradee (souvent en anglais):
- chiffres / annees / ordinaux / monnaies / pourcentages -> mots
- abreviations FR courantes -> forme developpee
- sigles (ex: SNCF) -> epellation francaise
- apostrophes typographiques -> apostrophe droite
- micro-pauses prosodiques par insertion de virgules apres conjonctions

Module pur: aucune dependance lourde au runtime hors num2words.
Sans effet sur le streaming ni le modele.
"""
from __future__ import annotations

import re
from typing import Iterable

try:
    from num2words import num2words as _n2w
except Exception:  # pragma: no cover
    _n2w = None  # degrade gracieusement


# --- 1. Apostrophes / quotes typographiques ---------------------------------
_TYPO_QUOTES = {
    "\u2019": "'", "\u2018": "'", "\u02bc": "'",
    "\u201c": '"', "\u201d": '"', "\u00ab": '"', "\u00bb": '"',
    "\u2026": "...",
    "\u2013": "-", "\u2014": "-",
    "\u00a0": " ", "\u202f": " ",
}

def _normalize_punct(text: str) -> str:
    for src, dst in _TYPO_QUOTES.items():
        text = text.replace(src, dst)
    return text


# --- 2. Abreviations FR ------------------------------------------------------
# Dictionnaire conservateur: que des formes non ambigues.
_ABBREV_FR = {
    "M.": "Monsieur",
    "MM.": "Messieurs",
    "Mme": "Madame", "Mme.": "Madame",
    "Mmes": "Mesdames",
    "Mlle": "Mademoiselle", "Mlle.": "Mademoiselle",
    "Mlles": "Mesdemoiselles",
    "Dr": "Docteur", "Dr.": "Docteur",
    "Pr": "Professeur", "Pr.": "Professeur",
    "Me": "Maitre",
    "St": "Saint", "St.": "Saint",
    "Ste": "Sainte", "Ste.": "Sainte",
    "Sts": "Saints",
    "Stes": "Saintes",
    "av.": "avenue",
    "bd.": "boulevard", "bd": "boulevard",
    "fbg": "faubourg",
    "qqch": "quelque chose", "qqch.": "quelque chose",
    "qqn": "quelqu'un", "qqn.": "quelqu'un",
    "p.ex.": "par exemple",
    "c.-a-d.": "c'est-a-dire", "c.a.d.": "c'est-a-dire",
    "etc.": "etcetera", "etc": "etcetera",
    "cf.": "confer",
    "n\u00b0": "numero", "N\u00b0": "Numero", "no.": "numero",
    "min.": "minutes",
    "h.": "heures",
    "env.": "environ",
    "ex.": "exemple",
    "av. J.-C.": "avant Jesus-Christ",
    "ap. J.-C.": "apres Jesus-Christ",
}

# Tri par longueur decroissante pour eviter les sous-substitutions.
_ABBREV_PATTERNS = [
    (re.compile(r"(?<![A-Za-z\u00c0-\u017f])" + re.escape(k) + r"(?![A-Za-z\u00c0-\u017f])"), v)
    for k, v in sorted(_ABBREV_FR.items(), key=lambda x: -len(x[0]))
]

def _expand_abbreviations(text: str) -> str:
    for pat, rep in _ABBREV_PATTERNS:
        text = pat.sub(rep, text)
    return text


# --- 3. Sigles (SNCF -> S N C F) --------------------------------------------
# 2-6 majuscules consecutives, hors mots existants. Lecture par lettres FR.
_LETTER_FR = {
    "A": "a", "B": "be", "C": "ce", "D": "de", "E": "e", "F": "effe",
    "G": "ge", "H": "ache", "I": "i", "J": "ji", "K": "ka", "L": "elle",
    "M": "emme", "N": "enne", "O": "o", "P": "pe", "Q": "ku", "R": "erre",
    "S": "esse", "T": "te", "U": "u", "V": "ve", "W": "double ve",
    "X": "iks", "Y": "i grec", "Z": "zede",
}
_SIGLE_RE = re.compile(r"\b([A-Z]{2,6})\b")
# Mots majuscules a NE PAS epeler (acronymes lus comme des mots, ou marques).
_SIGLE_KEEP = {
    "OK", "TV", "CD", "DVD", "USB", "PDF", "HTML", "CSS", "URL", "API",
    "HTTP", "HTTPS", "SMS", "MMS", "GPS", "USA", "FBI", "CIA", "NASA",
    "OTAN", "ONU", "UE", "EU",
}

def _expand_sigles(text: str) -> str:
    def _sub(m: re.Match) -> str:
        s = m.group(1)
        if s in _SIGLE_KEEP:
            return s
        # Heuristique: si la chaine contient une voyelle ET <=4 lettres,
        # probablement lue comme un mot (NASA, OTAN). Sinon epeler.
        vowels = sum(1 for c in s if c in "AEIOUY")
        if vowels >= 1 and len(s) <= 4 and vowels >= len(s) // 3:
            return s
        return " ".join(_LETTER_FR.get(c, c) for c in s)
    return _SIGLE_RE.sub(_sub, text)


# --- 4. Nombres / annees / ordinaux / monnaies / pourcentages ---------------
_ORDINAL_RE = re.compile(r"\b(\d+)(?:er|\u00e8re|\u00e8me|eme|nd|nde|ds|nds|\u00e8mes|emes)\b", re.IGNORECASE)
_PERCENT_RE = re.compile(r"(-?\d+(?:[.,]\d+)?)\s*%")
# Ordre: formes les plus longues d'abord pour eviter qu'EUR matche dans 'euros'.
_MONEY_RE = re.compile(
    r"(-?\d+(?:[.,]\d+)?)\s*(\u20ac|euros?|EUR|dollars?|USD|\$|livres?|GBP|\u00a3)\b",
    re.IGNORECASE,
)
# Annees 1900..2099 isolees.
_YEAR_RE = re.compile(r"\b(1[5-9]\d{2}|20\d{2})\b")
# Nombre quelconque (entier ou decimal francais).
_NUM_RE = re.compile(r"-?\d+(?:[.,]\d+)?")

_MONEY_WORDS = {
    "\u20ac": "euros", "eur": "euros", "euro": "euros", "euros": "euros",
    "$": "dollars", "usd": "dollars", "dollar": "dollars", "dollars": "dollars",
    "\u00a3": "livres", "gbp": "livres", "livre": "livres", "livres": "livres",
}

def _say_int(n: int) -> str:
    if _n2w is None:
        return str(n)
    try:
        return _n2w(n, lang="fr")
    except Exception:
        return str(n)

def _say_decimal(s: str) -> str:
    if _n2w is None:
        return s
    s = s.replace(",", ".")
    try:
        if "." in s:
            int_part, dec_part = s.split(".", 1)
            int_w = _n2w(int(int_part), lang="fr")
            # Lecture chiffre par chiffre apres la virgule (usage TTS).
            dec_w = " ".join(_n2w(int(d), lang="fr") for d in dec_part)
            return f"{int_w} virgule {dec_w}"
        return _n2w(int(s), lang="fr")
    except Exception:
        return s

def _say_year(y: int) -> str:
    return _say_int(y)

def _say_ordinal(n: int) -> str:
    if _n2w is None:
        return str(n)
    try:
        return _n2w(n, lang="fr", to="ordinal")
    except Exception:
        return _say_int(n)

def _expand_numbers(text: str) -> str:
    # 1) Ordinaux d'abord (1er, 2eme, ...).
    def _ord(m: re.Match) -> str:
        return _say_ordinal(int(m.group(1)))
    text = _ORDINAL_RE.sub(_ord, text)

    # 2) Pourcentages.
    def _pct(m: re.Match) -> str:
        return _say_decimal(m.group(1)) + " pour cent"
    text = _PERCENT_RE.sub(_pct, text)

    # 3) Monnaies.
    def _money(m: re.Match) -> str:
        return _say_decimal(m.group(1)) + " " + _MONEY_WORDS.get(m.group(2).lower(), m.group(2))
    text = _MONEY_RE.sub(_money, text)

    # 4) Annees isolees.
    def _year(m: re.Match) -> str:
        return _say_year(int(m.group(1)))
    text = _YEAR_RE.sub(_year, text)

    # 5) Nombres residuels (entier ou decimal).
    def _num(m: re.Match) -> str:
        return _say_decimal(m.group(0))
    text = _NUM_RE.sub(_num, text)
    return text


# --- 5. Pauses prosodiques douces (vraies virgules) -------------------------
# Insere une virgule (vraie) apres certaines conjonctions/incises pour
# obtenir une micro-pause naturelle de CosyVoice2 (sans SSML).
_CONJ_AFTER = re.compile(
    # Ne re-virguler que si pas deja precede par une virgule (eviter "..., mais, ...").
    r"(?<![,;])\s\b(mais|donc|or|car|cependant|toutefois|neanmoins|n\u00e9anmoins|"
    r"ainsi|alors|puis|ensuite|enfin|d'abord|finalement|"
    r"par exemple|par ailleurs|en effet|en revanche|en outre|"
    r"c'est-a-dire|c'est-\u00e0-dire)\b(?=\s+[A-Za-z\u00c0-\u017f])",
    re.IGNORECASE,
)

def _insert_soft_commas(text: str) -> str:
    return _CONJ_AFTER.sub(lambda m: " " + m.group(1) + ",", text)

def _insert_soft_commas(text: str) -> str:
    # N'ajoute pas de virgule s'il y en a deja une apres.
    def _sub(m: re.Match) -> str:
        word = m.group(1)
        return f"{word},"
    return _CONJ_AFTER.sub(_sub, text)


# --- 6. Espaces / ponctuation finale ----------------------------------------
_MULTI_SPACE = re.compile(r"[ \t]+")
_SPACE_BEFORE_PUNCT = re.compile(r"\s+([,;:.!?])")

def _tidy(text: str) -> str:
    text = _MULTI_SPACE.sub(" ", text)
    text = _SPACE_BEFORE_PUNCT.sub(r"\1", text)
    return text.strip()


# --- API publique -----------------------------------------------------------
def normalize_fr(text: str, *, prosody: bool = True) -> str:
    """Pre-normalise du texte francais avant gruut.

    - prosody=True ajoute des virgules apres conjonctions/incises pour des
      micro-pauses naturelles. Sans effet sur la prononciation des mots.
    """
    if not text:
        return ""
    text = _normalize_punct(text)
    text = _expand_abbreviations(text)
    text = _expand_numbers(text)
    text = _expand_sigles(text)
    if prosody:
        text = _insert_soft_commas(text)
    text = _tidy(text)
    # Trace forensique (verifiable depuis l'exterieur)
    try:
        import os, time
        _trace = os.environ.get("EXO_FR_NORM_TRACE", r"D:\EXO\logs\fr_norm_trace.txt")
        with open(_trace, "a", encoding="utf-8") as _f:
            _f.write(f"{time.strftime('%H:%M:%S')}\t{text}\n")
    except Exception:
        pass
    return text


__all__ = ["normalize_fr"]
