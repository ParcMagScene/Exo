#!/usr/bin/env python3
"""
EXO Documentation Maintenance — Audit-only scanner.

Scans docs/ for:
  - orphan files (not referenced by README index)
  - broken internal markdown links
  - broken anchors
  - missing standard header (breadcrumb 🧭)
  - missing standard footer (Retour à l'index)
  - duplicate content (MD5-based)
  - archive candidates (old files in active dirs)

Usage:
    python scripts/maintain_docs.py
    python scripts/maintain_docs.py --verbose
    python scripts/maintain_docs.py --json
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

# ────────────────────────────────────────────
# Config
# ────────────────────────────────────────────
DOCS_ROOT = Path(__file__).resolve().parent.parent / "docs"
INDEX_FILE = DOCS_ROOT / "README.md"

BREADCRUMB_MARKER = "🧭"
FOOTER_MARKER = "Retour à l'index"

CATEGORIES = {
    "core": "Architecture",
    "guides": "Guides",
    "ui": "Interface",
    "audits": "Audits",
    "reports": "Rapports",
    "prompts": "Prompts",
    "archives": "Archives",
}

# ────────────────────────────────────────────
# Helpers
# ────────────────────────────────────────────

def md5_file(path: Path) -> str:
    return hashlib.md5(path.read_bytes()).hexdigest()


def collect_md_files(root: Path) -> list[Path]:
    """Return all .md files under root, sorted."""
    return sorted(root.rglob("*.md"))


def extract_md_links(text: str) -> list[tuple[str, str | None]]:
    """Extract (path, anchor) from markdown links like [label](path#anchor)."""
    results = []
    for m in re.finditer(r'\[(?:[^\]]*)\]\(([^)]+)\)', text):
        target = m.group(1)
        if target.startswith(("http://", "https://", "mailto:")):
            continue
        if "#" in target:
            path_part, anchor = target.split("#", 1)
        else:
            path_part, anchor = target, None
        results.append((path_part, anchor))
    return results


def extract_anchors(text: str) -> set[str]:
    """Extract GitHub-style anchors from headings.

    GitHub's algorithm:
    1. Downcase
    2. Remove anything that is not a letter, number, space, or hyphen
       (letters include Unicode accented chars)
    3. Replace spaces with hyphens
    4. Collapse consecutive hyphens
    """
    anchors: set[str] = set()
    for m in re.finditer(r'^(#{1,6})\s+(.+)$', text, re.MULTILINE):
        heading = m.group(2).strip()
        anchor = _heading_to_anchor(heading)
        anchors.add(anchor)
    return anchors


def _heading_to_anchor(heading: str) -> str:
    """Convert a markdown heading to a GitHub-style anchor.

    GitHub's actual algorithm:
    1. Downcase
    2. Remove everything except: word chars (Unicode letters, digits, _),
       spaces, and hyphens  — removes emojis, punctuation, backticks, etc.
    3. Replace each space with a hyphen
    No stripping, no collapsing of consecutive hyphens.
    """
    a = heading.lower()
    # Remove inline code backticks
    a = a.replace('`', '')
    a = re.sub(r'[^\w\s-]', '', a, flags=re.UNICODE)
    a = a.replace(' ', '-')
    return a


def files_referenced_in_index(index_path: Path, docs_root: Path) -> set[Path]:
    """Parse the index README and return set of referenced file paths."""
    if not index_path.exists():
        return set()
    text = index_path.read_text(encoding="utf-8")
    referenced: set[Path] = set()
    for path_part, _ in extract_md_links(text):
        if not path_part:
            continue
        resolved = (index_path.parent / path_part).resolve()
        if resolved.suffix == ".md":
            referenced.add(resolved)
    return referenced


# ────────────────────────────────────────────
# Checks
# ────────────────────────────────────────────

class Report:
    def __init__(self) -> None:
        self.ok: list[str] = []
        self.orphans: list[str] = []
        self.broken_links: list[dict] = []
        self.broken_anchors: list[dict] = []
        self.missing_header: list[str] = []
        self.missing_footer: list[str] = []
        self.duplicates: list[dict] = []
        self.archive_candidates: list[str] = []
        self.stats = {"total_files": 0, "total_links": 0}


def check_orphans(all_files: list[Path], referenced: set[Path], report: Report) -> None:
    """Files not referenced in the index README."""
    for f in all_files:
        if f.resolve() == INDEX_FILE.resolve():
            continue
        if f.resolve() not in referenced:
            rel = f.relative_to(DOCS_ROOT)
            report.orphans.append(str(rel))


def check_links(all_files: list[Path], report: Report, verbose: bool) -> None:
    """Check all internal links and anchors in every file."""
    for f in all_files:
        text = f.read_text(encoding="utf-8", errors="replace")
        links = extract_md_links(text)
        report.stats["total_links"] += len(links)

        for path_part, anchor in links:
            # Resolve target file
            if path_part:
                target_path = (f.parent / path_part).resolve()
                if not target_path.exists():
                    report.broken_links.append({
                        "source": str(f.relative_to(DOCS_ROOT)),
                        "target": path_part,
                        "reason": "fichier introuvable",
                    })
                    continue
            else:
                # Same-file anchor  (#something)
                target_path = f

            # Anchor check
            if anchor:
                target_text = target_path.read_text(encoding="utf-8", errors="replace")
                available = extract_anchors(target_text)
                # Normalize the anchor for comparison
                anchor_clean = anchor.lower().strip()
                if anchor_clean not in available:
                    report.broken_anchors.append({
                        "source": str(f.relative_to(DOCS_ROOT)),
                        "anchor": f"#{anchor}",
                        "target": str(target_path.relative_to(DOCS_ROOT)) if path_part else "(même fichier)",
                    })


def check_headers_footers(all_files: list[Path], report: Report) -> None:
    """Check for standard breadcrumb header and footer."""
    for f in all_files:
        if f.resolve() == INDEX_FILE.resolve():
            continue
        text = f.read_text(encoding="utf-8", errors="replace")
        rel = str(f.relative_to(DOCS_ROOT))

        has_header = BREADCRUMB_MARKER in text[:500]
        has_footer = FOOTER_MARKER in text[-500:]

        if not has_header:
            report.missing_header.append(rel)
        if not has_footer:
            report.missing_footer.append(rel)

        if has_header and has_footer:
            report.ok.append(rel)


def check_duplicates(all_files: list[Path], report: Report) -> None:
    """MD5-based duplicate detection."""
    hashes: dict[str, list[str]] = {}
    for f in all_files:
        h = md5_file(f)
        rel = str(f.relative_to(DOCS_ROOT))
        hashes.setdefault(h, []).append(rel)

    for h, paths in hashes.items():
        if len(paths) > 1:
            report.duplicates.append({"hash": h[:12], "files": paths})


def check_archive_candidates(all_files: list[Path], report: Report) -> None:
    """Files in active dirs that look like they should be archived."""
    archive_patterns = [
        re.compile(r'v[34]\.[01]', re.IGNORECASE),
        re.compile(r'legacy|deprecated|old|obsolete', re.IGNORECASE),
        re.compile(r'backup|bak\b', re.IGNORECASE),
    ]
    for f in all_files:
        rel = f.relative_to(DOCS_ROOT)
        # Skip files already in archives/
        if str(rel).startswith("archives"):
            continue
        name = f.name.lower()
        for pat in archive_patterns:
            if pat.search(name):
                report.archive_candidates.append(str(rel))
                break


# ────────────────────────────────────────────
# Output formatters
# ────────────────────────────────────────────

RESET = "\033[0m"
GREEN = "\033[32m"
RED = "\033[31m"
YELLOW = "\033[33m"
CYAN = "\033[36m"
BOLD = "\033[1m"
DIM = "\033[2m"


def print_report(report: Report, verbose: bool) -> None:
    print()
    print(f"{BOLD}{'═' * 60}{RESET}")
    print(f"{BOLD}  📋 EXO Documentation — Rapport de maintenance{RESET}")
    print(f"{BOLD}{'═' * 60}{RESET}")
    print()

    total = report.stats["total_files"]
    ok_count = len(report.ok)
    issues = (
        len(report.orphans)
        + len(report.broken_links)
        + len(report.broken_anchors)
        + len(report.missing_header)
        + len(report.missing_footer)
        + len(report.duplicates)
    )

    print(f"  Fichiers scannés : {BOLD}{total}{RESET}")
    print(f"  Liens vérifiés   : {BOLD}{report.stats['total_links']}{RESET}")
    print(f"  Fichiers OK      : {GREEN}{ok_count}{RESET}")
    print(f"  Problèmes        : {RED if issues else GREEN}{issues}{RESET}")
    print()

    # ── Orphans ──
    _section("Fichiers orphelins (non référencés dans l'index)", report.orphans, "📂")

    # ── Broken links ──
    if report.broken_links:
        print(f"  {RED}🔗 Liens cassés ({len(report.broken_links)}){RESET}")
        for item in report.broken_links:
            print(f"     {DIM}{item['source']}{RESET} → {RED}{item['target']}{RESET}  ({item['reason']})")
        print()
    else:
        print(f"  {GREEN}🔗 Liens cassés : aucun{RESET}")
        print()

    # ── Broken anchors ──
    if report.broken_anchors:
        print(f"  {YELLOW}⚓ Ancres manquantes ({len(report.broken_anchors)}){RESET}")
        for item in report.broken_anchors:
            print(f"     {DIM}{item['source']}{RESET} → {YELLOW}{item['anchor']}{RESET} dans {item['target']}")
        print()
    else:
        print(f"  {GREEN}⚓ Ancres manquantes : aucune{RESET}")
        print()

    # ── Missing header ──
    _section("Fichiers sans header standard (🧭)", report.missing_header, "📝")

    # ── Missing footer ──
    _section("Fichiers sans footer standard", report.missing_footer, "📝")

    # ── Duplicates ──
    if report.duplicates:
        print(f"  {YELLOW}📑 Doublons détectés ({len(report.duplicates)} groupes){RESET}")
        for dup in report.duplicates:
            print(f"     MD5 {dup['hash']}… → {', '.join(dup['files'])}")
        print()
    else:
        print(f"  {GREEN}📑 Doublons : aucun{RESET}")
        print()

    # ── Archive candidates ──
    _section("Candidats à l'archivage", report.archive_candidates, "📦")

    # ── OK files ──
    if verbose and report.ok:
        print(f"  {GREEN}✅ Fichiers conformes ({len(report.ok)}){RESET}")
        for rel in report.ok:
            print(f"     {GREEN}✓{RESET} {rel}")
        print()

    # ── Summary ──
    print(f"{BOLD}{'─' * 60}{RESET}")
    if issues == 0:
        print(f"  {GREEN}{BOLD}✅ Documentation 100% conforme — aucun problème détecté.{RESET}")
    else:
        print(f"  {YELLOW}{BOLD}⚠  {issues} problème(s) à traiter.{RESET}")
    print(f"{BOLD}{'─' * 60}{RESET}")
    print()


def _section(title: str, items: list[str], icon: str) -> None:
    if items:
        print(f"  {YELLOW}{icon} {title} ({len(items)}){RESET}")
        for item in items:
            print(f"     {YELLOW}•{RESET} {item}")
        print()
    else:
        print(f"  {GREEN}{icon} {title} : aucun{RESET}")
        print()


def print_json(report: Report) -> None:
    data = {
        "stats": report.stats,
        "ok": report.ok,
        "orphans": report.orphans,
        "broken_links": report.broken_links,
        "broken_anchors": report.broken_anchors,
        "missing_header": report.missing_header,
        "missing_footer": report.missing_footer,
        "duplicates": report.duplicates,
        "archive_candidates": report.archive_candidates,
    }
    print(json.dumps(data, indent=2, ensure_ascii=False))


# ────────────────────────────────────────────
# Main
# ────────────────────────────────────────────

def main() -> int:
    parser = argparse.ArgumentParser(
        description="EXO Documentation Maintenance — Audit-only scanner"
    )
    parser.add_argument("--verbose", "-v", action="store_true", help="Affiche les fichiers conformes")
    parser.add_argument("--json", action="store_true", help="Sortie JSON (pour CI)")
    args = parser.parse_args()

    # Force UTF-8 output on Windows
    if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")

    if not DOCS_ROOT.exists():
        print(f"Erreur : répertoire docs/ introuvable ({DOCS_ROOT})", file=sys.stderr)
        return 1

    all_files = collect_md_files(DOCS_ROOT)
    referenced = files_referenced_in_index(INDEX_FILE, DOCS_ROOT)

    report = Report()
    report.stats["total_files"] = len(all_files)

    check_orphans(all_files, referenced, report)
    check_links(all_files, report, args.verbose)
    check_headers_footers(all_files, report)
    check_duplicates(all_files, report)
    check_archive_candidates(all_files, report)

    if args.json:
        print_json(report)
    else:
        print_report(report, args.verbose)

    issues = (
        len(report.broken_links)
        + len(report.missing_header)
        + len(report.missing_footer)
        + len(report.duplicates)
    )
    return 1 if issues > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
