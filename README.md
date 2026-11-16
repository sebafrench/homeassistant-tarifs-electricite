# Tarifs Électricité HP/HC — Home Assistant

Intégration personnalisée **entièrement locale** pour gérer les tarifs d'électricité en heures pleines (HP) et heures creuses (HC), avec programmation hebdomadaire, mode forcé, interface de configuration et prix pour le tableau de bord Énergie.

> **Version :** 1.0.0 · **Domaine :** `tarifs_electricite` · **Home Assistant :** versions modernes (2025.1+ visées). La suite de tests valide le moteur horaire ; l'intégration complète doit encore être essayée dans une instance Home Assistant réelle.

## Fonctionnalités

- Tarifs HP et HC en EUR/kWh, persistants, avec **quatre décimales**.
- Jusqu'à **4 plages HC commençant par jour**, réparties sur un maximum de 28 règles hebdomadaires. Une même plage peut être assignée à plusieurs jours.
- Création, modification, suppression de plages depuis **Configurer** (assistant graphique) ; prix et fuseau éditables sans YAML.
- Plages traversant minuit, règle dimanche→lundi, fuseau IANA (par défaut celui de Home Assistant), heures été/hiver.
- Évaluation immédiate au démarrage ; programmation native d'**un seul prochain changement** (pas de polling ni boucle permanente).
- Mode `Automatique`, `HP forcé`, `HC forcé` conservé après redémarrage.
- Entités `sensor`, `number`, `select` et actions personnalisées.
- **Bonus :** tarif de revente solaire séparé, configurable via `number.tarif_revente_surplus`.
- Aucune bibliothèque externe, clé API, accès réseau ni `configuration.yaml` nécessaires à l'exécution.

## Installation manuelle (hors ligne)

1. Téléchargez l'archive **`tarifs_electricite_installation.zip`** fournie.
2. Dans Home Assistant, ouvrez le partage de fichiers, Studio Code Server, File Editor ou SSH selon votre installation. Repérez le dossier de configuration HA, habituellement `/config`.
3. Décompressez l'archive **dans `/config/custom_components/`**. Le résultat doit être :

   ```text
   /config/custom_components/tarifs_electricite/__init__.py
   /config/custom_components/tarifs_electricite/manifest.json
   /config/custom_components/tarifs_electricite/config_flow.py
   ...
   ```

   Si `custom_components` n'existe pas, créez-le.
4. **Redémarrez Home Assistant** (nécessaire au premier chargement d'une nouvelle intégration).
5. Ouvrez **Paramètres → Appareils et services → Ajouter une intégration** et cherchez **Tarifs Électricité HP/HC**.
6. Renseignez les prix et le fuseau horaire ; choisissez **Ajouter une plage HC** pour chaque règle, puis **Terminer et enregistrer**.
7. Vérifiez les entités dans **Outils de développement → États**.

### Installation depuis GitHub / Marketplace (anciennement HACS)

Depuis **Home Assistant 2026.11**, HACS est intégré à Home Assistant sous le nom **Marketplace**. La structure de publication reste `custom_components/tarifs_electricite/` + `hacs.json`.

1. Créez un dépôt GitHub contenant **les fichiers du ZIP dépôt**, au niveau racine (pas dans un sous-dossier supplémentaire).
2. Avant publication, remplacez les deux URLs `CHANGE_ME` dans `custom_components/tarifs_electricite/manifest.json` par les véritables URLs de votre dépôt GitHub et de ses issues ; renseignez éventuellement votre pseudo dans `codeowners`.
3. Publiez le dépôt, puis dans **Paramètres → Marketplace**, ajoutez-le en tant que **dépôt personnalisé**, type **Intégration** (libellés selon version).
4. Installez-le depuis Marketplace, redémarrez Home Assistant et ajoutez l'intégration dans **Paramètres → Appareils et services**.

> Le Marketplace nécessite Internet pour récupérer le dépôt ; **l'intégration elle-même n'en a jamais besoin**. Avant HA 2026.11, utilisez l'interface HACS si disponible.

## Configuration HP/HC

Lors de l'installation, l'assistant vous propose :

| Paramètre | Exemple | Notes |
| --- | --- | --- |
| Prix HP | `0.2500` | EUR/kWh, entre 0 et 10 |
| Prix HC | `0.1900` | EUR/kWh, entre 0 et 10 |
| Prix revente surplus | `0.0600` | EUR/kWh, facultatif (0 par défaut) |
| Fuseau horaire | `Europe/Paris` | Nom IANA ; indépendant d'une API |

Dans le menu **Gestion des plages horaires** :

- **Ajouter une plage HC** : choisissez un début, une fin et les jours de semaine.
- **Modifier une plage HC** : sélectionnez une plage existante, modifiez-la, puis validez.
- **Supprimer une plage HC** : sélectionnez une plage existante pour la retirer.
- **Modifier les prix et le fuseau** : revient aux prix, puis au menu.
- **Terminer et enregistrer** : enregistre les modifications et réactualise immédiatement les capteurs, sans redémarrage.

**Exemple :** ajoutez `22:30 → 06:30` et `12:30 → 14:30`, en cochant lundi à dimanche pour chaque plage. La période `22:30 → 06:30` commence le jour coché et se poursuit le lendemain matin. Une plage de dimanche soir comprend donc le lundi matin.

Les bornes sont **début inclus / fin exclue** : à `06:30` pile on repasse en HP. L'intégration refuse les chevauchements, y compris en traversant minuit ou la frontière dimanche/lundi. Si deux plages sont strictement adjacentes, elles sont acceptées et ne provoquent pas de changement inutile entre elles.

**À propos du changement d'heure :** le calcul se fait en UTC sur des minutes réellement existantes, puis l'heure civile est évaluée dans le fuseau choisi. Une heure sautée au printemps prend effet au premier instant local existant où la condition est vraie. À l'automne, les heures répétées sont évaluées selon l'heure affichée. Ce comportement est défini et couvert par des tests.

## Modifier après installation

Ouvrez **Paramètres → Appareils et services → Tarifs Électricité HP/HC → Configurer**. Modifiez puis validez avec **Terminer et enregistrer**. Le mode tarifaire forcé n'est jamais réinitialisé par l'édition des tarifs.

Pour changer rapidement seulement les prix, utilisez les entités numériques :

- `number.tarif_hp`
- `number.tarif_hc`
- `number.tarif_revente_surplus`

Pour changer le fonctionnement, utilisez `select.mode_tarifaire` :

- `Automatique` : suit les plages HC, HP en dehors.
- `HP forcé` : tarif HP, sans prochain changement programmé.
- `HC forcé` : tarif HC, sans prochain changement programmé.

Le mode reste forcé jusqu'au retour manuel à `Automatique`, même après redémarrage.

## Entités disponibles

| ID proposé | Type | Rôle |
| --- | --- | --- |
| `sensor.tarif_electricite_actuel` | Prix numérique, `EUR/kWh` | Prix réellement appliqué maintenant |
| `sensor.periode_tarifaire` | Texte | `Heures Pleines` ou `Heures Creuses` |
| `sensor.prochain_changement_tarif` | Horodatage | Prochaine modification effective ; inconnu si mode forcé ou absence de transition |
| `sensor.prix_kwh_heures_pleines` | Prix, `EUR/kWh` | Prix HP configuré |
| `sensor.prix_kwh_heures_creuses` | Prix, `EUR/kWh` | Prix HC configuré |
| `sensor.horaires_heures_creuses` | Texte + attributs | Nombre et description des plages ; fuseau horaire |
| `sensor.prix_revente_surplus` | Prix, `EUR/kWh` | Prix de revente du surplus solaire |
| `number.tarif_hp` | Boîte numérique | Modifie HP directement |
| `number.tarif_hc` | Boîte numérique | Modifie HC directement |
| `number.tarif_revente_surplus` | Boîte numérique | Modifie le prix de revente |
| `select.mode_tarifaire` | Sélecteur | Automatique / HP forcé / HC forcé |

Ces IDs sont les noms proposés lors de la première installation et peuvent recevoir un suffixe si un autre périphérique les utilise déjà. Vérifiez les IDs attribués dans **Paramètres → Appareils et services → Entités**. Une entité renommée dans Home Assistant conserve son propre ID.

## Tableau de bord Énergie : import du réseau

1. Ouvrez **Paramètres → Tableaux de bord → Énergie** (selon la version : **Paramètres → Énergie**).
2. Dans la section **Réseau électrique**, ajoutez comme **énergie importée depuis le réseau** votre compteur de soutirage **en kWh** (Linky, FoxESS, Modbus, MQTT, etc.). L'entité doit être compatible avec les statistiques à long terme de Home Assistant, généralement `device_class: energy`, `state_class: total_increasing` et une unité comme `kWh`.
3. Dans le réglage de coût de cette source, choisissez **Utiliser une entité avec le prix actuel** / **Use an entity with current price**.
4. Sélectionnez `sensor.tarif_electricite_actuel` (ou l'ID réel après installation).
5. Enregistrez. Le tableau de bord calculera un coût estimatif en fonction des nouveaux kWh importés et du prix fourni par le capteur.

**À ne pas confondre :**

- **Consommation totale de la maison** : énergie utilisée par les appareils, y compris celle fournie directement par les panneaux solaires.
- **Énergie importée du réseau** : kWh achetés au fournisseur ; **c'est cette mesure** qu'il faut associer au tarif HP/HC.
- **Énergie exportée (injection)** : kWh renvoyés vers le réseau ; configurez-la séparément, et utilisez si souhaité `sensor.prix_revente_surplus` comme tarif de compensation.

Le module **ne lit pas lui-même** les données FoxESS, Linky, MQTT ou Modbus et ne crée pas de compteur kWh : il fournit le prix à l'outil Énergie, qui exploite un capteur de comptage existant. Le calcul est une **estimation** et peut différer de la facture (abonnement, taxes, arrondis, granularité des mesures et prix contractuel). Un arrêt de Home Assistant peut affecter la précision du coût reconstitué si le tarif a changé pendant l'arrêt.

## Tableau de bord Lovelace

L'exemple prêt à copier se trouve dans `examples/lovelace_tarifs.yaml`. Pour l'ajouter, créez un tableau de bord Lovelace ou une vue en mode YAML (ou copiez ses cartes via l'éditeur de tableau de bord en mode code). **Aucune carte communautaire requise.**

## Actions Home Assistant

Les trois actions sont toujours enregistrées quand l'intégration est chargée :

**Régler les HP :**

```yaml
action: tarifs_electricite.set_prix_hp
data:
  prix: 0.2500
```

**Régler les HC :**

```yaml
action: tarifs_electricite.set_prix_hc
data:
  prix: 0.1900
```

**Forcer les HC :**

```yaml
action: tarifs_electricite.set_mode
data:
  mode: hc_force
```

Pour revenir au mode automatique, utilisez `mode: automatique`. Pour imposer les heures pleines, utilisez `mode: hp_force`. Les noms des actions sont également visibles dans **Outils de développement → Actions**. Les trois actions conservent leurs valeurs après redémarrage.

## Vérifications manuelles dans Home Assistant

1. Avec `22:30–06:30`, `12:30–14:30` et les 7 jours sélectionnés, regardez `sensor.periode_tarifaire` : il doit correspondre à l'heure courante.
2. Changez `number.tarif_hp` dans le tableau de bord : le capteur de prix actuel doit se mettre à jour immédiatement **si le mode appliqué est HP**.
3. Passez `select.mode_tarifaire` à `HC forcé` : période = `Heures Creuses`, prix actuel = HC, prochain changement = `unknown` (pas de changement automatique).
4. Redémarrez Home Assistant : le mode et les prix forcés doivent être conservés.
5. Remettez `Automatique` : la période suit de nouveau le calendrier ; le prochain changement s'affiche.
6. Modifiez une plage dans **Configurer**, enregistrez, et vérifiez les attributs de `sensor.horaires_heures_creuses`.
7. Vérifiez que les entités d'import et d'export du réseau sont bien distinctes dans Énergie.

## Tests automatisés

Le moteur `schedule.py` n'utilise que la bibliothèque standard Python. Il est testable sans installation de Home Assistant :

```bash
python -m pip install pytest
python -m pytest -q
```

Les **25 tests** couvrent prix et validations, plages adjacentes et chevauchantes, passages minuit et dimanche/lundi, quota de 4 plages par jour, calendrier hebdomadaire et changements d'heure été/hiver.

> Le passage de ces tests ne garantit pas à lui seul que chaque écran de configuration Home Assistant ou chaque opération du Marketplace fonctionne avec votre version exacte. Testez l'installation et les actions ci-dessus avant un déploiement de production.

## Architecture

```text
custom_components/tarifs_electricite/
├── __init__.py             # runtime, services, horloge native et persistence
├── manifest.json
├── const.py
├── schedule.py             # calcul pur, horaires, validation, DST
├── config_flow.py          # installation et édition de règles par l'UI
├── sensor.py
├── number.py
├── select.py
├── services.yaml
├── icons.json
├── strings.json
└── translations/
    ├── fr.json
    └── en.json

examples/lovelace_tarifs.yaml
tests/test_schedule.py
tests/conftest.py
hacs.json
README.md
```

## Dépannage

- **L'intégration est absente du menu :** vérifiez le chemin `config/custom_components/tarifs_electricite/manifest.json`, puis redémarrez complètement Home Assistant.
- **Entité de prix introuvable dans Énergie :** assurez-vous de choisir une **entité de prix** et non une entité d'énergie. Vérifiez que `sensor.tarif_electricite_actuel` a un état numérique et une unité `EUR/kWh`.
- **La mauvaise plage semble active :** vérifiez le fuseau horaire réglé, les jours **de début** des plages qui traversent minuit et le mode (qui peut être forcé).
- **Une nouvelle plage est refusée :** vérifiez les chevauchements, y compris entre dimanche et lundi et lorsqu'une plage traverse minuit.
- **Le prix ne s'applique pas à la consommation totale :** c'est normal : le tarif d'achat du réseau s'applique à l'énergie **importée**, non à l'autoconsommation.

## Limites volontaires

- Tarification **à deux niveaux HP/HC**, pas de grille Tempo ou de jours fériés spécifiques.
- Précision temporelle à la minute ; gestion du changement d'heure en temps civil local.
- Pas de calcul direct de facture, pas de frais fixes, d'abonnement ou de taxes spécifiques.
- Pas de récupération automatique des tarifs fournisseur : ceux-ci sont **saisis manuellement**.

Licence : MIT (voir `LICENSE`).
