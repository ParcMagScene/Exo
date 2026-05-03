# GUI DEAD CODE AUDIT — EXO QML

Date: 2026-05-01  
Périmètre: tout le dossier qml + assets/icônes associés

## 1) Méthode

Audit statique effectué sur l’ensemble des fichiers QML:
- inventaire complet des types QML exportés
- recherche des instanciations réelles par type
- recherche des références par nom de fichier
- détection heuristique des imports inutilisés
- détection heuristique des ids/propriétés/signaux non utilisés
- scan des assets (qml/icons + assets/icons/app)

Note importante: ids/propriétés/signaux sont détectés par analyse statique textuelle. Les faux positifs restent possibles sur des usages dynamiques.

## 2) Résumé exécutif

- Fichiers QML analysés (avant nettoyage): 58
- Fichiers QML analysés (après nettoyage): 47
- Composants jamais instanciés détectés: 10
- Composants supprimés: 10
- Singleton QML mort supprimé: 1
- Imports inutilisés supprimés: 2
- Assets/icônes non utilisés supprimés: 7
- Composants dupliqués: aucun doublon actif détecté

## 3) Fichiers inutilisés détectés et supprimés

Composants QML jamais instanciés et jamais référencés (hors déclaration dans leur propre fichier/qmldir):

- qml/components/CameraCone.qml
- qml/components/ExoBadge.qml
- qml/components/ExoConfirmDialog.qml
- qml/components/ExoDialog.qml
- qml/components/ExoMicButton.qml
- qml/components/ExoNotification.qml
- qml/components/ExoServiceStatus.qml
- qml/components/ExoStatusPill.qml
- qml/components/ExoWaveform.qml
- qml/components/SpatialNetworkIntegration.qml

Singleton non référencé:
- qml/core/PageRouter.qml

Mises à jour associées:
- qml/components/qmldir: exports supprimés
- qml/core/qmldir: suppression de l’export PageRouter

## 4) Composants jamais instanciés

État après nettoyage:
- aucun composant non-singleton restant sans instanciation

## 5) Imports inutilisés

Imports inutilisés détectés puis supprimés:
- qml/pages/MaisonPage.qml: import ../components
- qml/panels/SafeBootPanel.qml: import ../components

Autres imports inutilisés restants:
- aucun candidat détecté (scan heuristique post-nettoyage)

## 6) Ids jamais utilisés

Résultat post-nettoyage:
- 39 ids candidats non relus dans leur fichier

Exemples représentatifs:
- qml/components/AudioWaveformView.qml: animTimer
- qml/components/CognitiveTimeline.qml: snapTimer
- qml/pages/PipelinePage.qml: refreshTimer
- qml/pages/PipelinePage.qml: inspectorLogRefresh
- qml/pages/SettingsPage.qml: pitchValueText
- qml/pages/SettingsPage.qml: rateValueText

Action recommandée:
- supprimer au fil de l’eau uniquement les ids purement décoratifs non ciblés par animation/anchors/debug
- ne pas supprimer en masse sans revue visuelle

## 7) Propriétés jamais lues

Résultat post-nettoyage:
- 93 propriétés candidates non relues localement

Observations:
- une grande partie concerne des tokens du singleton Theme (réserve de design system)
- certaines propriétés sont exposées pour liaison externe ou évolution future

Action recommandée:
- traiter en lot dédié Theme: conserver les tokens voulus, retirer les tokens réellement morts
- prioriser les propriétés isolées hors Theme pour gains rapides

## 8) Signaux jamais émis / jamais connectés

Résultat post-nettoyage:
- 1 signal restant sans handler détecté

Détail:
- qml/pages/ReseauPage.qml: signal nodeClicked
  - emits_in_file: 2
  - handlers_anywhere: 0

Action recommandée:
- soit connecter ce signal dans le parent attendu
- soit le supprimer si non utilisé

## 9) Handlers jamais déclenchés

Aucun handler custom orphelin critique détecté après suppression des composants morts.

## 10) Assets/icônes non utilisés

Icônes supprimées:
- qml/icons/microphone.svg
- qml/icons/outils.svg
- qml/icons/stt.svg
- qml/icons/tts.svg
- qml/icons/vad.svg
- qml/icons/wakeword.svg
- assets/icons/app/exo@2x.png

État après nettoyage:
- pas d’asset orphelin détecté dans les emplacements audités

## 11) Doublons de composants

Aucun doublon actif détecté dans l’arborescence QML actuelle.

## 12) Correctifs appliqués dans cette passe

Suppressions de fichiers:
- 11 fichiers QML supprimés (10 composants + 1 singleton)
- 7 assets/icônes supprimés

Nettoyage code:
- qml/components/qmldir nettoyé
- qml/core/qmldir nettoyé
- imports inutilisés supprimés (2 fichiers)
- propriété legacy retirée: qml/pages/PipelinePage.qml (recentEvents)
- commentaires obsolètes mis à jour dans FloorPlanPage/FloorPlanProperties

## 13) Suppressions encore recommandées

Candidats à valider avant suppression:
- qml/pages/ReseauPage.qml: signal nodeClicked
- lot ids candidats non relus (39)
- lot propriétés candidates non lues (93), en commençant hors Theme

## 14) Conclusion

Objectif atteint:
- la base QML a été auditée et nettoyée
- les composants, imports et assets morts à forte confiance ont été supprimés
- le résiduel est désormais concentré sur des candidats de niveau "refactor" (ids/propriétés/signal isolé), à traiter de manière incrémentale avec revue fonctionnelle.
