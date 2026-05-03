"""Normalise tous les fichiers .md dans docs/ selon les règles strictes EXO.

Règles appliquées :
1. Trailing spaces → supprimés
2. Tabulations → 2 espaces
3. Titres ALL-CAPS → Title Case (préserve emojis, numéros, backticks)
4. Titres #### → ### (aplatir au max 3 niveaux)
5. Lignes >120 chars → wrap intelligent (hors tables, code, liens)
6. Sections vides → supprimées
7. Footer standard → ajouté si manquant
8. Lignes vides multiples → max 2 consécutives

Usage : python scripts/normalize_docs.py [--dry-run] [--verbose]
"""
import re
import sys
import unicodedata
from pathlib import Path

DOCS_DIR = Path(__file__).resolve().parent.parent / "docs"

FOOTER = "\n---\nRetour à l'index : [docs/README.md](../README.md)\n"
FOOTER_ROOT = "\n---\nRetour à l'index : [docs/README.md](README.md)\n"


# ── Casse des titres ────────────────────────────────────────────

# Mots à garder en minuscule dans Title Case (français + anglais)
LOWERCASE_WORDS = {
    'de', 'du', 'des', 'le', 'la', 'les', 'un', 'une', 'et', 'ou', 'en',
    'à', 'au', 'aux', 'par', 'pour', 'sur', 'dans', 'avec', 'sans', 'vers',
    'the', 'a', 'an', 'and', 'or', 'of', 'in', 'on', 'at', 'to', 'for',
    'with', 'from', 'by', 'is', 'are', 'was',
}

# Acronymes et termes techniques à garder tels quels
PRESERVE_UPPER = {
    'EXO', 'GUI', 'QML', 'TTS', 'STT', 'VAD', 'API', 'DSP', 'UX', 'UI',
    'XTTS', 'LLM', 'NLU', 'CPU', 'GPU', 'RAM', 'DLL', 'REST', 'SSE',
    'FAISS', 'CUDA', 'HTTP', 'HTTPS', 'JSON', 'HTML', 'CSS', 'VS',
    'CMAKE', 'WEBSOCKET', 'CRITICAL', 'HIGH', 'MEDIUM', 'LOW', 'INFO',
    'Q_INVOKABLE', 'QAudioSink', 'DirectML', 'USB', 'PCM', 'WAV', 'MP3',
    'WASAPI', 'ALSA', 'TCP', 'UDP', 'IP', 'DNS', 'URL', 'URI', 'SDK',
    'STA', 'SSD', 'HA', 'GPT', 'RTX', 'CI', 'PASS', 'FAIL', 'OK',
}


def smart_title_case(text: str) -> str:
    """Convertit un texte ALL-CAPS en casse de titre intelligente.
    
    Préserve : emojis, backticks, numéros de section, marqueurs ✅/⚠️, etc.
    """
    # Ne pas toucher aux textes entre backticks
    parts = re.split(r'(`[^`]+`)', text)
    result = []
    for j, part in enumerate(parts):
        if part.startswith('`'):
            result.append(part)
            continue

        words = part.split()
        new_words = []
        for i, word in enumerate(words):
            # Garder les symboles/emojis tels quels (pas de lettres latines)
            clean = re.sub(r'[^\w]', '', word)
            if not clean or not re.search(r'[a-zA-ZÀ-ÿ]', clean):
                new_words.append(word)
                continue

            # Garder les numéros de section (1., 2.1, etc.)
            if re.match(r'^\d+(\.\d+)*\.?$', word):
                new_words.append(word)
                continue

            # Garder les acronymes connus
            upper_clean = re.sub(r'[^\w]', '', word).upper()
            if upper_clean in PRESERVE_UPPER:
                new_words.append(word)
                continue

            # Garder les mots déjà en casse mixte (camelCase, etc.)
            if not word.isupper() and not word.islower():
                new_words.append(word)
                continue

            # Convertir ALL-CAPS → Title Case
            if word.isupper() and len(clean) > 1:
                lower = word.lower()
                # Mots fonctionnels en minuscule (sauf premier mot)
                if i > 0 and lower in LOWERCASE_WORDS:
                    new_words.append(lower)
                else:
                    # Capitalize premier caractère alpha
                    new_words.append(lower.capitalize())
            else:
                new_words.append(word)

        result.append(' '.join(new_words))
    return ''.join(result)


def fix_title_caps(line: str) -> str:
    """Corrige un titre contenant des mots ALL-CAPS non-acronymes."""
    m = re.match(r'^(#{1,6})\s+(.+)', line)
    if not m:
        return line

    hashes = m.group(1)
    title = m.group(2)

    # Nettoyer pour l'analyse : retirer backticks et constantes UPPER_CASE_ID
    clean_title = re.sub(r'`[^`]+`', '', title)
    clean_title = re.sub(r'[A-Z]+(?:_[A-Z]+)+', '', clean_title)

    # Extraire les mots alphabétiques de 2+ caractères
    words = re.findall(r'[a-zA-ZÀ-ÿ]{2,}', clean_title)
    if not words:
        return line

    # Compter les mots ALL-CAPS qui ne sont PAS des acronymes préservés
    caps_non_acro = [w for w in words if w == w.upper() and w != w.lower()
                     and w.upper() not in PRESERVE_UPPER]

    if len(caps_non_acro) < 1:
        return line

    return f"{hashes} {smart_title_case(title)}"


# ── Niveaux de titres ──────────────────────────────────────────

def flatten_deep_titles(line: str) -> str:
    """Convertit ####+ en ###."""
    m = re.match(r'^(#{4,6})\s+(.+)', line)
    if m:
        return f"### {m.group(2)}"
    return line


# ── Wrap lignes longues ────────────────────────────────────────

def should_wrap(line: str) -> bool:
    """Détermine si une ligne peut être wrappée."""
    stripped = line.strip()
    # Ne pas wrapper : tables, code, liens complexes, HTML, blockquotes, listes avec liens
    if stripped.startswith('|'):
        return False
    if stripped.startswith('```'):
        return False
    if stripped.startswith('>'):
        return False
    if stripped.startswith('<!--'):
        return False
    if stripped.startswith('<'):
        return False
    # Ligne avec beaucoup de liens Markdown → ne pas couper
    if stripped.count('](') > 2:
        return False
    # Ligne de TOC (lien avec ·)
    if '·' in stripped and '](' in stripped:
        return False
    return True


def wrap_line(line: str, max_len: int = 120) -> list[str]:
    """Wrap une ligne en plusieurs lignes de max_len caractères."""
    if len(line) <= max_len or not should_wrap(line):
        return [line]

    indent = len(line) - len(line.lstrip())
    indent_str = line[:indent]
    text = line.strip()

    # Ne pas couper à l'intérieur de [...](...)
    # Stratégie simple : couper aux espaces en respectant la longueur
    words = text.split(' ')
    lines = []
    current = indent_str

    for word in words:
        test = current + (' ' if current.strip() else '') + word
        if len(test) > max_len and current.strip():
            lines.append(current)
            current = indent_str + word
        else:
            current = test

    if current.strip():
        lines.append(current)

    return lines if lines else [line]


# ── Sections vides ─────────────────────────────────────────────

def remove_empty_sections(lines: list[str]) -> list[str]:
    """Supprime les titres suivis directement par un autre titre (section vide)."""
    result = []
    i = 0
    while i < len(lines):
        m = re.match(r'^(#{1,3})\s+', lines[i])
        if m:
            # Regarder en avant : la prochaine ligne non-vide est-elle un titre de même niveau ou supérieur ?
            j = i + 1
            while j < len(lines) and lines[j].strip() == '':
                j += 1
            if j < len(lines):
                m2 = re.match(r'^(#{1,3})\s+', lines[j])
                if m2 and len(m2.group(1)) <= len(m.group(1)):
                    # Section vide → skip this heading and blank lines after it
                    i = j
                    continue
        result.append(lines[i])
        i += 1
    return result


# ── Collapse lignes vides multiples ────────────────────────────

def collapse_blank_lines(lines: list[str]) -> list[str]:
    """Limite les lignes vides consécutives à maximum 2."""
    result = []
    blank_count = 0
    for line in lines:
        if line.strip() == '':
            blank_count += 1
            if blank_count <= 2:
                result.append(line)
        else:
            blank_count = 0
            result.append(line)
    return result


# ── Footer ─────────────────────────────────────────────────────

def has_footer(lines: list[str]) -> bool:
    """Vérifie si le fichier a déjà un footer standard."""
    for line in lines[-5:]:
        if 'Retour' in line and 'README' in line:
            return True
    return False


def add_footer(lines: list[str], is_root: bool) -> list[str]:
    """Ajoute le footer standard si manquant."""
    if has_footer(lines):
        return lines
    # Supprimer les lignes vides de fin
    while lines and lines[-1].strip() == '':
        lines.pop()
    footer = FOOTER_ROOT if is_root else FOOTER
    lines.append('')
    for fl in footer.strip().split('\n'):
        lines.append(fl)
    lines.append('')
    return lines


# ── Process file ───────────────────────────────────────────────

def process_file(filepath: Path, dry_run: bool = False) -> dict:
    """Normalise un fichier. Retourne un dict de compteurs de corrections."""
    content = filepath.read_text(encoding='utf-8')
    lines = content.splitlines()
    stats = {'trailing': 0, 'tabs': 0, 'caps': 0, 'deep': 0,
             'long': 0, 'empty_sections': 0, 'footer': 0, 'blanks': 0}

    in_code_block = False
    new_lines = []

    for line in lines:
        # Track code blocks
        if line.strip().startswith('```'):
            in_code_block = not in_code_block

        # 1. Trailing spaces
        cleaned = line.rstrip()
        if cleaned != line:
            stats['trailing'] += 1
        line = cleaned

        # 2. Tabs → 2 spaces
        if '\t' in line:
            stats['tabs'] += line.count('\t')
            line = line.replace('\t', '  ')

        # Skip further processing inside code blocks
        if in_code_block:
            new_lines.append(line)
            continue

        # 3. Flatten ####+ → ###
        old = line
        line = flatten_deep_titles(line)
        if line != old:
            stats['deep'] += 1

        # 4. ALL-CAPS titles → Title Case
        old = line
        line = fix_title_caps(line)
        if line != old:
            stats['caps'] += 1

        # 5. Long lines → wrap
        if len(line) > 120:
            wrapped = wrap_line(line)
            if len(wrapped) > 1:
                stats['long'] += 1
                new_lines.extend(wrapped)
                continue

        new_lines.append(line)

    # 6. Empty sections
    before = len(new_lines)
    new_lines = remove_empty_sections(new_lines)
    stats['empty_sections'] = before - len(new_lines)

    # 7. Collapse multiple blank lines
    before = len(new_lines)
    new_lines = collapse_blank_lines(new_lines)
    stats['blanks'] = before - len(new_lines)

    # 8. Footer (skip README.md qui est l'index)
    rel = filepath.relative_to(DOCS_DIR)
    is_root = rel.parent == Path('.')
    if rel.name != 'README.md':
        if not has_footer(new_lines):
            stats['footer'] = 1
            new_lines = add_footer(new_lines, is_root)

    new_content = '\n'.join(new_lines)
    # Assurer newline final
    if not new_content.endswith('\n'):
        new_content += '\n'

    total = sum(stats.values())
    changed = new_content != content

    if changed and not dry_run:
        filepath.write_text(new_content, encoding='utf-8')

    return stats, changed


def main():
    dry_run = '--dry-run' in sys.argv
    verbose = '--verbose' in sys.argv

    files = sorted(DOCS_DIR.rglob('*.md'))
    totals = {'trailing': 0, 'tabs': 0, 'caps': 0, 'deep': 0,
              'long': 0, 'empty_sections': 0, 'footer': 0, 'blanks': 0}
    changed_count = 0

    for f in files:
        rel = f.relative_to(DOCS_DIR)
        stats, changed = process_file(f, dry_run=dry_run)
        file_total = sum(stats.values())

        for k in totals:
            totals[k] += stats[k]

        if changed:
            changed_count += 1

        if verbose:
            if changed:
                details = ', '.join(f"{k}={v}" for k, v in stats.items() if v > 0)
                print(f"  FIX  {rel}  ({details})")
            else:
                print(f"  OK   {rel}")

    mode = "DRY-RUN" if dry_run else "APPLIED"
    print(f"\n{'='*60}")
    print(f"  Normalisation [{mode}] — {len(files)} fichiers")
    print(f"{'='*60}")
    print(f"  Fichiers modifiés : {changed_count}")
    print(f"  Trailing spaces   : {totals['trailing']}")
    print(f"  Tabulations       : {totals['tabs']}")
    print(f"  Titres MAJUSCULES : {totals['caps']}")
    print(f"  Titres ####→###   : {totals['deep']}")
    print(f"  Lignes >120 chars : {totals['long']}")
    print(f"  Sections vides    : {totals['empty_sections']}")
    print(f"  Footers ajoutés   : {totals['footer']}")
    print(f"  Lignes vides trim : {totals['blanks']}")
    print(f"{'='*60}")


if __name__ == '__main__':
    main()
