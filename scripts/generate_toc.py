#!/usr/bin/env python3
"""Génère automatiquement une Table des Matières (TOC) pour tous les fichiers .md dans docs/.

Règles :
- TOC générée à partir des titres #, ##, ###
- Placée juste après le header (breadcrumb + titre + sous-titre/date)
- Mise à jour si une TOC existante est détectée
- Ignorée pour les fichiers avec moins de 2 sections (titres ## ou ###)
- Gère les titres avec emojis, caractères spéciaux, backticks
"""

import re
import sys
from pathlib import Path

DOCS_DIR = Path(__file__).resolve().parent.parent / "docs"

# Marqueurs pour délimiter la TOC générée
TOC_START = "<!-- TOC -->"
TOC_END = "<!-- /TOC -->"


def slugify(title: str) -> str:
    """Convertit un titre Markdown en ancre compatible GitHub/VS Code."""
    # Supprimer le formatage markdown (**, `, ~~)
    slug = re.sub(r'[*`~]', '', title)
    # Supprimer tous les emojis et symboles Unicode
    slug = re.sub(
        r'[\U0001F000-\U0001FFFF'   # Emoticons, symbols, etc.
        r'\U00002600-\U000027BF'     # Misc symbols, Dingbats
        r'\U0000FE00-\U0000FE0F'     # Variation selectors
        r'\U0000200D'                # Zero width joiner
        r'\U00002700-\U000027BF'     # Dingbats
        r'\U0000231A-\U000023FF'     # Misc technical
        r'\U00002B50-\U00002B55'     # Stars
        r'\U000025A0-\U000025FF'     # Geometric shapes
        r'\U00002190-\U000021FF'     # Arrows
        r'\U00003000-\U0000303F'     # CJK symbols
        r']+', '', slug)
    # Supprimer les balises HTML
    slug = re.sub(r'<[^>]+>', '', slug)
    slug = slug.strip().lower()
    # Remplacer espaces par des tirets
    slug = re.sub(r'\s+', '-', slug)
    # Ne garder que alphanum, tirets, underscores
    slug = re.sub(r'[^\w-]', '', slug)
    # Nettoyer les tirets multiples
    slug = re.sub(r'-+', '-', slug).strip('-')
    return slug


def extract_headers(lines: list[str]) -> list[tuple[int, str, str]]:
    """Extrait les titres #/##/### hors blocs de code.

    Retourne une liste de (level, raw_title, slug).
    """
    headers = []
    in_code_block = False
    for line in lines:
        stripped = line.rstrip()
        if stripped.startswith("```"):
            in_code_block = not in_code_block
            continue
        if in_code_block:
            continue
        m = re.match(r'^(#{1,3})\s+(.+)$', stripped)
        if m:
            level = len(m.group(1))
            raw = m.group(2).strip()
            headers.append((level, raw, slugify(raw)))
    return headers


def generate_toc(headers: list[tuple[int, str, str]], skip_title: bool = True) -> list[str]:
    """Génère les lignes de la TOC Markdown.

    skip_title: ignore le premier h1 (titre principal du document).
    """
    toc_headers = headers[:]
    if skip_title and toc_headers and toc_headers[0][0] == 1:
        toc_headers = toc_headers[1:]

    # Filtrer le titre "Table des matières" lui-même s'il existe déjà en dur
    toc_headers = [h for h in toc_headers if 'table-des-mati' not in h[2]]

    if len(toc_headers) < 2:
        return []

    # Déterminer le niveau minimum pour l'indentation
    min_level = min(h[0] for h in toc_headers)

    lines = [TOC_START, "## Table des matières", ""]
    for level, raw, slug in toc_headers:
        indent = "  " * (level - min_level)
        # Nettoyer le titre pour l'affichage (retirer les emojis de début)
        display = re.sub(
            r'^[\U0001F000-\U0001FFFF'
            r'\U00002600-\U000027BF'
            r'\U0000FE00-\U0000FE0F'
            r'\U0000200D'
            r'\U00002700-\U000027BF'
            r'\U0000231A-\U000023FF'
            r'\U00002B50-\U00002B55'
            r'\U000025A0-\U000025FF'
            r'\U00002190-\U000021FF'
            r'\U00003000-\U0000303F'
            r'\s]+', '', raw).strip()
        if not display:
            display = raw
        lines.append(f"{indent}- [{display}](#{slug})")
    lines.append("")
    lines.append(TOC_END)
    return lines


def find_header_end(lines: list[str]) -> int:
    """Trouve la position après le header (breadcrumb, titre, sous-titre, séparateur).

    Retourne l'index de la ligne après laquelle insérer la TOC.
    """
    found_title = False
    last_header_line = 0

    for i, line in enumerate(lines):
        stripped = line.strip()
        # Breadcrumb
        if stripped.startswith('>') and not found_title:
            last_header_line = i
            continue
        # Premier titre h1
        if not found_title and stripped.startswith('# '):
            found_title = True
            last_header_line = i
            continue
        if found_title:
            # Sous-titres, blockquotes, métadonnées dans le bloc header
            if stripped.startswith('>') or stripped.startswith('### ') or stripped == '':
                last_header_line = i
                continue
            # Séparateur --- marque la fin nette du header
            if stripped == '---':
                return i + 1
            # Tout autre contenu → fin du header
            break

    return last_header_line + 1


def remove_existing_toc(lines: list[str]) -> list[str]:
    """Supprime une TOC existante (entre marqueurs ET/OU section ## Table des matières)."""
    result = []
    # Pass 1 : supprimer les marqueurs <!-- TOC --> ... <!-- /TOC -->
    i = 0
    while i < len(lines):
        if lines[i].strip() == TOC_START:
            while i < len(lines) and lines[i].strip() != TOC_END:
                i += 1
            if i < len(lines):
                i += 1  # skip TOC_END
            while i < len(lines) and lines[i].strip() == '':
                i += 1
            continue
        result.append(lines[i])
        i += 1

    # Pass 2 : supprimer aussi toute section "## Table des matières" manuelle (avec ou sans emoji, toute casse)
    cleaned = []
    i = 0
    while i < len(result):
        stripped = result[i].strip()
        if re.match(r'^##\s+[\U0001F300-\U0001FAFF\s]*Table des matières', stripped, re.IGNORECASE):
            i += 1
            while i < len(result):
                s = result[i].strip()
                if (s.startswith('## ') and not re.match(r'^\d+\.', s)) or s == '---':
                    break
                i += 1
            while i < len(result) and result[i].strip() == '':
                i += 1
            continue
        cleaned.append(result[i])
        i += 1

    return cleaned


def remove_inline_sommaire(lines: list[str]) -> list[str]:
    """Supprime les lignes '**Sommaire :** [...]' obsolètes (remplacées par la TOC)."""
    result = []
    for line in lines:
        if re.match(r'^\s*\*\*Sommaire\s*:\*\*', line):
            continue
        result.append(line)
    return result


def process_file(filepath: Path, dry_run: bool = False) -> str:
    """Traite un fichier .md : ajoute/met à jour la TOC.

    Retourne: 'added', 'updated', 'skipped', ou 'unchanged'.
    """
    content = filepath.read_text(encoding='utf-8')
    original_lines = content.splitlines()

    # Extraire les headers
    headers = extract_headers(original_lines)

    # Compter les sections (hors h1 titre principal et "Table des matières")
    sections = [h for h in headers
                if not (h[0] == 1) and 'table-des-mati' not in h[2]]
    if len(sections) < 2:
        return 'skipped'

    # Vérifier si une TOC existe déjà
    has_toc = TOC_START in content or any(
        re.match(r'^##\s+Table des matières', l.strip()) for l in original_lines
    )

    # Supprimer l'ancienne TOC
    clean_lines = remove_existing_toc(original_lines)

    # Supprimer les anciens sommaires inline
    clean_lines = remove_inline_sommaire(clean_lines)

    # Recalculer les headers après suppression de l'ancienne TOC
    # N'extraire que les headers APRÈS le bloc header (ignorer les ### sous-titres du header)
    insert_pos = find_header_end(clean_lines)
    headers = extract_headers(clean_lines[insert_pos:])
    toc_lines = generate_toc(headers, skip_title=False)

    if not toc_lines:
        return 'skipped'

    # Construire le nouveau contenu
    new_lines = clean_lines[:insert_pos]
    # S'assurer d'une ligne vide avant la TOC
    if new_lines and new_lines[-1].strip() != '':
        new_lines.append('')
    new_lines.extend(toc_lines)
    new_lines.append('')
    # Ajouter le reste du contenu
    remaining = clean_lines[insert_pos:]
    # Éviter les lignes vides en double
    while remaining and remaining[0].strip() == '':
        remaining = remaining[1:]
    new_lines.extend(remaining)

    new_content = '\n'.join(new_lines) + '\n'

    if new_content == content:
        return 'unchanged'

    if not dry_run:
        filepath.write_text(new_content, encoding='utf-8')

    return 'updated' if has_toc else 'added'


def main():
    dry_run = '--dry-run' in sys.argv
    verbose = '--verbose' in sys.argv or '-v' in sys.argv

    if not DOCS_DIR.exists():
        print(f"Erreur: {DOCS_DIR} introuvable")
        sys.exit(1)

    md_files = sorted(DOCS_DIR.rglob('*.md'))
    stats = {'added': 0, 'updated': 0, 'skipped': 0, 'unchanged': 0}

    for f in md_files:
        rel = f.relative_to(DOCS_DIR)
        result = process_file(f, dry_run=dry_run)
        stats[result] += 1
        if verbose or result in ('added', 'updated'):
            symbol = {'added': '✅', 'updated': '🔄', 'skipped': '⏭️', 'unchanged': '⚪'}
            print(f"  {symbol[result]} {rel} — {result}")

    print(f"\n{'[DRY RUN] ' if dry_run else ''}Résultat:")
    print(f"  ✅ Ajoutées: {stats['added']}")
    print(f"  🔄 Mises à jour: {stats['updated']}")
    print(f"  ⏭️ Ignorées (<2 sections): {stats['skipped']}")
    print(f"  ⚪ Inchangées: {stats['unchanged']}")
    print(f"  📊 Total: {sum(stats.values())} fichiers")


if __name__ == '__main__':
    main()
