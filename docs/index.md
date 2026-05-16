# Nouvelle arborescence unifiée (post-migration)

# Nouvelle arborescence unifiée (post-migration)

Toute l’arborescence EXO est désormais unifiée directement sous D:/EXO/ :

```
D:/EXO/
    exo/
    qml/
    python/
    services/
    scripts/
    config/
    logs/
    models/
    (tous sous D:/EXO/)
    whispercpp/
    faiss/
    cache/
    .venv/ ou venv/
    exo_launcher.ps1
    (tout le reste)
```

Tous les chemins absolus/relatifs dans le code, les scripts et la documentation doivent pointer vers D:/EXO/<nom>/.

Le script de migration migrate_project_to_root.ps1 permet d’automatiser la migration physique.
# Documentation EXO

Bienvenue dans la documentation officielle du projet EXO.

## Table des matières

- [Architecture](architecture/)
- [Implémentation](implementation/)
- [Dépannage](troubleshooting/)
- [Audits](#audits)
    - [Audio](audits/audio/)
    - [Backend](audits/backend/)
    - [GUI](audits/gui/)
    - [Pipeline](audits/pipeline/) *(vide)*
    - [Services](audits/services/) *(vide)*

---

## Règles de contribution

Voir [CONTRIBUTING_DOCS.md](CONTRIBUTING_DOCS.md)

---


## Audits

- [Audio](audits/audio/)
- [Backend](audits/backend/)
- [GUI](audits/gui/)
- [Pipeline](audits/pipeline/) *(vide)*
- [Services](audits/services/) *(vide)*

## Implémentation

- [Guides d’implémentation](implementation/)

## Dépannage

- [Guides de résolution et troubleshooting](troubleshooting/)

---

## Structure verrouillée

Voir [docs/.structure.lock](.structure.lock)
