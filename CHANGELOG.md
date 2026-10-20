# Journal des modifications

## 5.7.0

- Securite : vitest 5 (corrige tinypool, execution de code via pollution de prototype), actions GitHub epinglees par SHA.

## 5.6.0

- Mise à jour automatique (plugin Tauri updater) : vérification au démarrage, dialogue de confirmation en français avec version et notes, progression, installation silencieuse signée (minisign) puis relance.
- Réglages : « Vérifier les mises à jour automatiquement » (actif par défaut) et bouton « Rechercher une mise à jour ».
- Publication : `scripts/make-latest-json.py` génère `latest.json` ; `scripts/build.ps1` signe l'installeur ; la CI Linux signe et publie aussi les `.sig`.
- Tests (vitest) : réglage de mise à jour et cohérence des versions.

## 5.5.1

Version précédente (voir l'historique git).
