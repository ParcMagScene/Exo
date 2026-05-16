# Nouvelle règle post-migration

**Tous les chemins de fichiers/dossiers référencés dans la documentation, le code et les scripts doivent pointer vers la nouvelle arborescence unifiée sous D:/EXO/.**

Exemple : D:/EXO/logs/, D:/EXO/models/, D:/EXO/config/, etc. (aucune référence à project/ n’est tolérée)
# CONTRIBUTION À LA DOCUMENTATION EXO

## Structure stricte

- **Aucun fichier documentaire ne doit être créé ailleurs que dans `docs/` et ses sous-dossiers existants.**
- **Aucun nouveau dossier ne doit être créé dans `docs/`.**
- **Aucun dossier existant ne doit être renommé.**
- **Aucun fichier documentaire ne doit être créé à la racine du projet.**

## Emplacement des documents

- **Audits** :
  - Audio : `docs/audits/audio/<nom>.md`
  - Backend : `docs/audits/backend/<nom>.md`
  - GUI : `docs/audits/gui/<nom>.md`
  - Pipeline : `docs/audits/pipeline/<nom>.md`
  - Services : `docs/audits/services/<nom>.md`
- **Documents techniques** :
  - Architecture : `docs/architecture/`
  - Implémentation : `docs/implementation/`
- **Guides de résolution** :
  - Dépannage : `docs/troubleshooting/`

## Index

- Toujours référencer tout nouveau document dans `docs/index.md`.

## Suppression et doublons

- Supprimer tout doublon documentaire.
- Ne jamais disperser, renommer ou dupliquer la documentation.

## Structure verrouillée

- Respecter strictement le fichier `docs/.structure.lock`.

---

**Tout manquement à ces règles sera considéré comme une erreur critique.**
