# Passation technique — Solar Energy Manager

Document préparé le 31 octobre 2026 pour la reprise par un autre assistant. Il décrit le dépôt et le contexte accessibles à cette date. Les résultats historiques et les demandes de l'utilisateur sont distingués de l'état réel de l'installation, qui n'a pas été recontrôlé pendant la rédaction. Vérifier les fichiers et références avant toute décision : ce document ne remplace ni le code ni une observation actuelle.

## 1. Situation immédiate et accès au bon code

Le dépôt privé est [Macorou/solar-energy-manager](https://github.com/Macorou/solar-energy-manager). Au moment de cette passation :

| Élément | État vérifié |
| --- | --- |
| Branche de développement locale et distante | `feat/v1-energy-manager-impl` |
| Commit de cette branche | `219e781f0314ad5ccb1574d956179965c0611dc3` |
| Version du code | `0.1.23` |
| Branche distante `main` | `34951b85d4ebaff5882623a1d94c45c47d86dd0f`, état beaucoup plus ancien |
| PR existante | [#1, brouillon](https://github.com/Macorou/solar-energy-manager/pull/1), de la branche de développement vers `main` |
| Publication | Tag `v0.1.23`, image privée `ghcr.io/macorou/solar-energy-manager:0.1.23` |
| Contrôle GitHub Actions | [Run 41198736839](https://github.com/Macorou/solar-energy-manager/actions/runs/41198736839), terminé avec succès au commit ci-dessus |

Un clone par défaut de `main` **ne contient pas le développement courant**. Avec les droits nécessaires, récupérer la branche `feat/v1-energy-manager-impl` et revérifier son commit ; le tag `v0.1.23` est une autre référence de l'instantané publié. L'image publiée porte le digest `sha256:1804b79bc70717a87a0831b9fe54f5a9e404b46dc978b1d303070ab87bd117f2`. Une image publiée ne démontre pas qu'elle est installée sur le serveur de l'utilisateur.

Le dépôt de travail observé est un *worktree* Git lié, à `outputs/solar-energy-manager/.worktrees/v1` sous le dossier de travail Codex. Son checkout principal local n'est pas la bonne référence pour reprendre les fonctionnalités récentes. À la rédaction, le seul fichier préexistant non suivi dans ce worktree était `docs/next-patch.md` : il contient des notes locales historiques, parfois dépassées et potentiellement sensibles. Le conserver sans le publier ; il n'est pas automatiquement présent dans un clone GitHub.

Ce document décrit le commit applicatif précédant la publication de la passation. Vérifier le commit courant : des changements peuvent avoir été publiés depuis. La publication de ces documents ne constitue pas un déploiement de l'application.

## 2. Finalité et périmètre produit

Solar Energy Manager (SEM) pilote une borne de recharge de voiture électrique et un chauffe-eau en tenant compte des mesures du logement, du photovoltaïque, d'horaires et de limites électriques par phase. L'application comprend :

- un tableau de bord avec flux d'énergie, état et commandes des appareils ;
- des programmes de recharge et de chauffe, priorités et réglages solaires ;
- la configuration des équipements, sources, intégrations et contraintes réseau ;
- un historique persistant des sessions de charge avec statistiques et exports ;
- un journal de diagnostic filtrable et un historique d'événements ;
- une interface française, thèmes clair/sombre, adaptée aux téléphones et ordinateurs.

Home Assistant est principalement une source de mesures ; la borne utilise OCPP 1.6J, la voiture une intégration Peugeot et le chauffe-eau une intégration Ariston. Les fonctionnalités réelles dépendent de la configuration et des données fournies. Le code est inspiré par EVCC sur certains mécanismes, mais SEM n'embarque pas EVCC et il ne faut pas le présenter comme une reproduction complète de toutes ses fonctions.

## 3. Technologies et organisation

Versions relevées dans les dépendances et la configuration du dépôt :

- Backend : Python 3.12, FastAPI 0.162.0, Starlette 0.52.1, Uvicorn 0.54.0, HTTPX 0.28.1, websockets 17.3, bibliothèque `ocpp` 2.1.0 pour le protocole OCPP 1.6J, bibliothèque `ariston` 0.19.9, `cryptography` 50.0.2, `argon2-cffi` 25.1.0, SQLite. Les versions effectives sont verrouillées dans `backend/requirements.lock`.
- Frontend : React et React DOM 19.3.1, TypeScript 5.9.3, Vite 8.3.5, Vitest 5.0.5, Playwright 1.64.1, `openapi-typescript` 7.13.0. Node 24.11.1 est utilisé par la configuration de build/CI ; `frontend/package-lock.json` est la référence d'installation exacte.
- Validation : pytest 9.1.1, pytest-asyncio 1.4.1, tests Vitest et tests navigateur Chromium/WebKit. Docker est construit en plusieurs étapes ; l'image finale Python sert également les fichiers frontend.

Carte de lecture :

| Chemin | Rôle principal |
| --- | --- |
| `backend/app/main.py` | Fabrique FastAPI, initialisation, routes, cycle de vie, fichiers statiques |
| `backend/app/domain/` | Modèles métier, échantillons et qualité des mesures, commandes |
| `backend/app/connectors/` | Connexions Home Assistant, Peugeot, Ariston et OCPP |
| `backend/app/engine/` | Décisions énergétiques, règles de régulation et estimation SoC |
| `backend/app/runtime/` | Coordinateur, dispatch, suivi des charges et état d'exécution |
| `backend/app/scheduling/` | Récurrences, plages horaires et autorisations |
| `backend/app/storage/` | SQLite, secrets, historique des sessions et journalisation |
| `backend/app/sessions/`, `backend/app/api/` | Agrégation et endpoints, notamment sessions et journaux |
| `frontend/src/App.tsx`, `frontend/src/components/` | Navigation, tableau de bord, flux et cartes |
| `frontend/src/pages/` | Planning, réglages, sessions et journaux |
| `frontend/src/sessions/`, fichiers CSS dans `frontend/src/` | Calculs et présentation des sessions, styles par zone |
| `tests/`, `frontend/` | Tests backend, frontend et navigateur |
| `scripts/` | Export OpenAPI, serveur de tests et utilitaires |
| `compose.yaml`, `Dockerfile`, `.github/workflows/` | Image, déploiement et automatisation CI/publication |
| `docs/deployment/`, `docs/third-party/`, `docs/research/` | Notes de déploiement, provenance et recherches historiques |

Pour chaque fichier, lire son contenu courant avant modification : cette carte est volontairement fonctionnelle, pas un inventaire exhaustif de chaque module.

## 4. Flux d'exécution et décisions structurantes

### Mesures, décisions, commandes

Les connecteurs récupèrent les mesures, qui deviennent des échantillons avec valeur, qualité et dates. Le coordinateur construit une vue du site, évalue les horaires et les contraintes, suit la charge, puis interroge le moteur d'énergie. Le dispatch envoie les commandes nécessaires et réconcilie leur résultat avec des observations ultérieures. Le cycle de coordination est de l'ordre de deux secondes ; les intégrations distantes ont leurs propres rythmes.

Les qualités incluent notamment `FRESH`, `STALE`, `UNAVAILABLE` et `ESTIMATED`. Une réponse de commande acceptée n'est pas une preuve de puissance observée. Des données critiques absentes ou périmées ne doivent pas être réinterprétées comme des mesures sûres. La gestion des commandes inconnues et les réservations contribuent à éviter les doubles commandes ou le double comptage au redémarrage.

Le tableau de bord conserve la dernière puissance valide d'un appareil quand la nouvelle mesure est indisponible, et retire sa consommation lorsqu'une vraie valeur de 0 W est reçue. C'est une règle de **présentation** : elle ne doit pas remplacer les exigences de fraîcheur de la régulation. Le flux utilise une barre unique, avec solaire vert, import réseau gris et export jaune ; les appareils sont représentés par des icônes et des segments proportionnels. Voir `EnergyFlow.tsx`, `energyBalance.ts` et `powerDisplay.ts`.

### Réseau et borne

Le moteur tient compte des courants mesurés par phase, des limites configurées, de la marge et des consommations déjà réservées. Lorsqu'un dépassement le permet, il module d'abord la borne ; en dessous du minimum applicable ou si la réduction échoue et que la surcharge persiste, l'arrêt reste possible. Il existe un contrôle de surcharge persistant d'environ 60 secondes. La plage de cinq minutes introduite pour la confirmation initiale de puissance ne doit pas retarder une réaction à une surcharge mesurée ni un arrêt explicite.

La borne peut être configurée monophasée ou triphasée ; ne pas supposer une commutation automatique de phases. Les profils OCPP positifs utilisent un `TxDefaultProfile` persistant ; une suspension à 0 A cherche à préserver la transaction, avec arrêt distant de repli si nécessaire. Consulter `connectors/ocpp/profiles.py`, les tests et les notes de version avant toute modification, notamment pour les variantes de firmware Wallbox. Un profil positif persistant peut subsister pendant une indisponibilité du contrôleur : les automatismes de SEM ne s'exécutent pas lorsqu'il est arrêté. Vérifier les conséquences sur le matériel réel avant toute intervention.

Le serveur OCPP est exposé sur le même service HTTP, chemin de forme `/ocpp/<station-id>`, sous-protocole `ocpp1.6`. L'authentification Basic, lorsqu'elle est configurée, associe l'identité à la station. Le mode sans mot de passe nécessite une autorisation explicite dans la configuration (`allow_insecure_identity`) ; ne pas l'activer par défaut. `ws://` n'apporte pas de chiffrement de transport ; évaluer TLS/proxy pour un accès hors réseau de confiance. Les identifiants réels ne doivent jamais figurer dans une documentation ou un journal partagé.

### Modes et planning

La demande utilisateur la plus récente avant la passation concernait la perte du mode manuel de la voiture pendant la nuit. Le code `0.1.23` vise à rendre ce mode **persistant jusqu'à une action explicite de l'utilisateur**, y compris après redémarrage ou débranchement ; cela concerne aussi « Charger maintenant ». L'ancien paramètre `duration_minutes` reste accepté pour compatibilité, mais n'expire plus le manuel de la borne. Si une ancienne version est déjà revenue en automatique, la mise à jour ne réactive pas elle-même le manuel. Les protections électriques, l'objectif de charge et les contrôles de mesure restent actifs. Le mode manuel du chauffe-eau reste temporisé : ne pas généraliser la règle voiture sans nouvelle demande.

Le planning gère notamment objectifs, jours, début d'autorisation réseau, anticipation solaire, heures creuses, priorités et temporisations pour passages nuageux. Il faut conserver la gestion du fuseau et des passages d'heure d'été/hiver. Le passage par Pause doit pouvoir revenir au réglage automatique antérieur approprié.

### Peugeot et estimation de batterie

`backend/app/engine/evcc_soc.py` adapte le principe d'estimation EVCC, avec efficacité initiale de 85 % puis ajustement à partir d'écarts entre énergie et SoC. Une valeur API valide initialise ou recale l'estimation lorsqu'elle change ; si la valeur retournée reste identique, l'estimation peut progresser avec l'énergie mesurée. La date de mesure Peugeot n'est volontairement plus utilisée comme critère de sélection ou blocage, selon la décision de l'utilisateur. Capacité, initialisation et intégrité des mesures restent nécessaires. L'ancien champ d'efficacité véhicule est conservé pour compatibilité mais ne pilote plus cette estimation.

Le début d'une session ne doit pas recevoir artificiellement le SoC actuel comme valeur de départ. Le code limite sa fixation et sa réparation aux cas justifiables par les données ; sinon la valeur doit rester indisponible. Une valeur de fin peut être estimée : ne pas la présenter comme mesure précise sans distinction.

## 5. Historique des sessions et journaux

### Sessions de charge

L'historique est autonome dans SQLite : `runtime/charging.py`, `storage/charging_sessions.py`, `sessions/service.py`, `api/sessions.py` et `frontend/src/pages/Sessions.tsx` sont des points d'entrée utiles. Une session correspond au branchement jusqu'au débranchement ; une pause ou une nouvelle transaction pendant ce branchement ne doit pas automatiquement créer une nouvelle session. L'identifiant et la persistance cherchent à conserver la continuité après redémarrage.

L'interface comprend périodes mois/année/total, navigation, graphiques, regroupements, filtres véhicule/point de charge, tableau, détail et exports CSV/Excel. Une session est affectée pour les graphiques à sa **date locale de début**, sans découpage artificiel à minuit. Les sessions confirmées sans énergie sont masquées par défaut avec option d'inclusion ; les sessions incomplètes ou de mesure inconnue ne doivent pas être confondues avec zéro.

Les coûts et parts solaires sont des estimations construites à partir des incréments d'énergie, des mesures du logement et du tarif disponibles. Les données manquantes restent inconnues ou partielles. Le code ne dispose pas d'une provenance fiable séparant batterie domestique et solaire direct : ne pas inventer cette distinction ni des émissions CO₂. Les prix zéro ou négatifs ne sont pas nécessairement des données absentes. Les coûts partiels sont explicitement indiqués et une moyenne fiable dépend de la couverture disponible. Les mutations autorisées de sessions locales et leurs mécanismes anti-réapparition ne doivent pas effacer des données externes.

L'utilisateur a signalé sur une version antérieure des colonnes mobiles manquantes, un filtre coût indisponible et des SoC début/fin identiques. Des correctifs figurent dans l'historique ultérieur ; leur bon fonctionnement avec ses données réelles reste à confirmer, en particulier quand une session ne possède que des données partielles. Ne pas rétro-remplir des valeurs invérifiables.

### Journaux

La page `Journaux` collecte des diagnostics applicatifs dans SQLite et propose recherche, niveau, zone, navigation et export. Les catégories couvrent notamment système, HTTP, OCPP, Home Assistant, Peugeot, Ariston, site, appareils et décisions. La rétention est bornée à sept jours et 10 000 entrées ; l'API limite les pages et l'interface son nombre de lignes affichées. Les erreurs d'écriture dues à un verrouillage peuvent entraîner des pertes comptabilisées. Les anciens logs stdout Docker ne sont pas importés rétroactivement.

La rédaction/filtration cherche à masquer les secrets avant persistance, mais ne constitue pas une garantie absolue : vérifier tout export avant partage. Distinguer le journal de diagnostic des événements métier et de l'historique des sessions.

## 6. Persistance, authentification et sécurité

`SEM_DATA_DIR` désigne le répertoire de données, `/data` dans Docker. La base SQLite courante est au schéma **3** (`PRAGMA user_version`) : données de configuration/exécution, utilisateurs/sessions, événements, historique de charge et journaux. Les migrations sont additives ; lire `backend/app/storage/database.py` et les tests avant de changer le schéma. Certaines notes historiques parlent du schéma 1 ou 2 : elles ne décrivent pas l'état actuel.

Les secrets sont chiffrés via Fernet et une clé conservée sous le répertoire de données (`secrets/master.key`). Une sauvegarde/restauration doit préserver ensemble base et clé correspondante, ainsi que les autres éléments nécessaires du volume. Ne pas régénérer la clé pour une base existante. Le jeton de première configuration est stocké localement : ne jamais l'exposer ou l'inclure dans une archive destinée au code source.

L'application utilise une authentification web avec mots de passe hachés Argon2, cookie de session HTTP-only et contrôles d'origine. `SEM_SECURE_COOKIE` doit correspondre à l'utilisation effective de HTTPS. Les endpoints applicatifs sont protégés ; la sonde de vivacité est publique. Protéger également l'accès au registre GHCR privé, au serveur et aux sauvegardes.

Une seule instance de contrôle doit utiliser le même répertoire de données. `runtime/instance.py` applique ce principe ; ne jamais tester contre le volume de production. Les tests automatisés et exemples doivent employer des données fictives, sans commandes vers les appareils réels.

## 7. Installation, commandes et développement

Prévoir Python 3.12, Node 24, npm et, pour les tests d'image, Docker. Depuis la racine du checkout courant :

```bash
python3.12 -m venv .venv
. .venv/bin/activate
python -m pip install -r backend/requirements.lock
npm --prefix frontend ci

python -m pytest -q
npm --prefix frontend test
npm --prefix frontend run build

python scripts/export_openapi.py
npm --prefix frontend run types
git diff --exit-code -- backend/openapi.json frontend/src/api/schema.ts

docker compose config --quiet
```

Sur Windows, activer le venv avec la commande adaptée au shell ; `npm.cmd` peut contourner une politique PowerShell qui bloque `npm.ps1`. Le build frontend effectue la vérification TypeScript. Aucun script de lint distinct n'a été identifié dans les scripts frontend examinés.

Pour les tests navigateur :

```bash
cd frontend
npx playwright install chromium webkit
npm run e2e
```

Sur Linux CI, l'installation des dépendances système Playwright peut nécessiter `--with-deps`. `SEM_PYTHON` peut pointer vers l'interpréteur du venv ; `SEM_BROWSER`, `SEM_SCREENSHOT_DIR` et `PLAYWRIGHT_BROWSERS_PATH` sont des paramètres de test selon les scripts. `scripts/e2e_server.py` démarre un serveur isolé avec fixtures synthétiques et sans contrôle du matériel réel. Vérifier le script et les ports disponibles avant lancement.

Pour une exécution locale, définir `SEM_DATA_DIR` vers un répertoire neuf et jetable, puis :

```bash
uvicorn app.main:create_app --factory --app-dir backend --host 127.0.0.1 --port 8080
```

Le serveur Vite de développement utilise son proxy configuré pour l'API. Une exécution complète de l'application peut activer le runtime : une base jetable et l'absence de configuration d'appareils réels sont indispensables. `SEM_STATIC_DIR` permet selon le contexte de désigner les ressources frontend. `SEM_PUBLIC_URL` sert à la cohérence d'origine publique ; `TZ` règle le fuseau. Ne pas inclure de valeurs de secrets dans ces instructions.

## 8. Docker, CI et mise à jour

`Dockerfile` compile le frontend avec Node puis installe le backend dans `python:3.12.14-slim-bookworm`. Le processus s'exécute sans privilèges, sous UID/GID 10001, avec un seul worker Uvicorn ; la sonde utilise `/api/v1/health/live`. `compose.yaml` monte un volume persistant sur `/data`, limite les privilèges, monte le système de fichiers en lecture seule avec espace temporaire dédié et définit une politique de redémarrage. Les valeurs d'image, port et environnement sont paramétrables ; vérifier les paramètres effectifs du déploiement avant intervention.

`SEM_VERSION` sélectionne l'étiquette d'image ; `SEM_HTTP_PORT` règle le port hôte. L'image GHCR est privée : l'hôte qui télécharge doit avoir les droits nécessaires. Une mise à jour réelle comprend normalement sauvegarde cohérente du volume et de sa clé, vérification de la version/digest, récupération de l'image autorisée, redéploiement en conservant le volume, contrôle du démarrage et de l'état des intégrations. Le démarrage ou redémarrage peut avoir des conséquences sur le pilotage des appareils : obtenir l'accord de l'utilisateur et vérifier l'état physique au moment de l'opération. Ne pas supposer qu'un retour à une ancienne image est compatible avec un schéma SQLite migré.

La CI vérifie notamment tests backend/frontend, génération OpenAPI/types, build, navigateurs, configuration Compose et image Docker. Les tags `v*` déclenchent le workflow de vérification puis la publication GHCR. Le test d'image peut être lancé localement après build :

```bash
docker build -t sem:test .
SEM_TEST_IMAGE=sem:test python -m pytest tests/deployment/test_image_smoke.py -q
```

Syntaxe de variable à adapter à PowerShell. Ne pas prendre un ancien workflow ou un ancien digest figé comme preuve de la version actuellement déployée.

## 9. État des travaux et éléments à vérifier

### Dernier travail connu

Le correctif `0.1.23` traite le maintien du manuel voiture et la suppression de lignes techniques de demande sur le tableau de bord. La publication associée a réussi sur GitHub. Une validation historique faisait état de 398 tests Python réussis avec un smoke Docker ignoré localement, 92 tests frontend réussis, build et scénarios navigateur réussis ; la CI a également exécuté des contrôles d'image. Ces chiffres ne sont pas une nouvelle exécution et peuvent changer après reprise.

L'utilisateur avait observé une interruption nocturne et supposait un retour automatique vers 23 h 15. L'existence d'une temporisation dans l'ancienne logique étayait la correction, mais aucun journal de cette nuit ne prouve ici la cause exacte. Le fonctionnement prolongé sur son matériel et la version effectivement installée n'ont pas été vérifiés pendant cette passation.

Les fonctionnalités de sessions, journaux, réglages groupés, thèmes, barre énergétique et correctifs mobiles sont présentes dans le code. Cela ne signifie pas que chaque intégration et tous les cas limites ont été validés sur l'installation physique actuelle.

### Limites et questions ouvertes

- Vérifier avec l'utilisateur la version effectivement déployée, l'état des intégrations et ses priorités. Ne pas déduire le déploiement à partir d'une image publiée.
- Tester sur matériel réel, avec autorisation et en tenant compte des horaires : maintien manuel pendant la nuit et après redémarrage, réduction sur dépassement par phase, confirmation OCPP, reprise après déconnexion et maintien des protections. Les tests logiciels ne remplacent pas ces observations.
- Contrôler la cohérence entre SoC Peugeot mesuré et estimé, et l'exactitude des données disponibles pour les sessions réelles ; conserver les informations absentes comme telles.
- L'historique ne reconstruit pas magiquement les données non enregistrées avant son introduction. Les statistiques PV/réseau et coûts peuvent être partielles ; la provenance batterie et le CO₂ ne sont pas suffisamment documentés pour être inventés.
- Des idées plus anciennes évoquent une publication de données SEM vers Home Assistant et des évolutions tarifaires Tempo. La consommation de mesures HA existe déjà ; une publication générale vers HA ou une optimisation Tempo complète ne doit pas être considérée comme réalisée ni prioritaire sans vérification et demande.
- Plusieurs appareils et scénarios sont modélisés, mais leur comportement dans une installation particulière dépend de la configuration et des tests réels. Pas de promesse de parité intégrale avec EVCC ni de commutation automatique de phases.

### Attention aux documents historiques

Le `README.md`, certaines notes de déploiement, spécifications et plans ont été écrits à des étapes antérieures. Exemples vérifiés : une description ancienne présente tous les modes manuels comme temporaires ; une note de sauvegarde cite le schéma 1 ; d'anciennes notes OCPP décrivent d'autres hypothèses de profil. Consulter les correctifs `docs/deployment/patch-0.1.23.md`, `patch-0.1.22.md`, `patch-0.1.21.md`, `patch-0.1.20.md` et les modules/tests courants pour arbitrer. Les observations du rapport d'acceptation initial ne constituent pas un constat actuel de l'installation.

## 10. Méthode de reprise conseillée

1. Lire `CLAUDE.md`, cette passation, puis `git status --short --branch`, les derniers commits et les instructions du dépôt. Vérifier la branche distante, les fichiers non suivis et les éventuelles modifications de l'utilisateur.
2. Faire préciser la prochaine priorité si aucune nouvelle tâche n'est donnée. Examiner d'abord le code et les tests concernés ; distinguer faits, hypothèses et symptômes rapportés.
3. Pour une évolution, utiliser un environnement et des données fictifs isolés. Ajouter des tests utiles pour les changements de comportement, notamment redémarrage, états manquants, horaires et limites par phase.
4. Exécuter les contrôles adaptés au changement. Pour une modification API, vérifier le contrat OpenAPI et les types générés ; pour l'interface, contrôler les thèmes et les largeurs iPhone/Safari et ordinateur, sans débordement ni commandes tactiles trop petites.
5. Présenter ce qui a été modifié et les preuves disponibles. Demander une autorisation explicite avant tout commit, push, publication, déploiement ou commande/modification de l'installation réelle, conformément à la demande de passation. Ne jamais diffuser de données sensibles.

## 11. Provenance et licence

Des adaptations sont inspirées du code open source EVCC, notamment l'estimation SoC et le travail Peugeot. Consulter `docs/third-party/evcc-MIT.txt` et `docs/third-party/peugeot-provenance.md` pour les notices et références précises. Avant toute nouvelle copie, vérifier la licence du fichier exact ainsi que les éventuelles exceptions relatives aux fonctions sponsorisées et ressources graphiques. Les captures et discussions de conception sont des références, pas une autorisation de copier indistinctement des ressources tierces.
