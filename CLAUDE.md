# Instructions pour Claude Code

Ce dépôt contient **Solar Energy Manager**, une application de pilotage local de recharge de véhicule et de chauffe-eau selon le réseau, la production solaire et les horaires. Avant toute intervention, lire [HANDOFF_CLAUDE.md](HANDOFF_CLAUDE.md), puis vérifier le code et l'état Git : le document décrit un instantané, pas l'état courant de l'installation.

## Référence de travail

- Au 31 octobre 2026, le développement courant est sur `feat/v1-energy-manager-impl`, au commit `219e781f0314ad5ccb1574d956179965c0611dc3`, version `0.1.23`. La branche distante `main` contient un état bien plus ancien. Vérifier les références avant de choisir une base.
- Une PR brouillon [#1](https://github.com/Macorou/solar-energy-manager/pull/1) existe vers `main`. Ne pas la fusionner, publier, pousser, créer de tag ou déployer sans demande explicite.
- Vérifier `git status --short --branch` avant de travailler. Préserver les modifications et fichiers non suivis de l'utilisateur. `docs/next-patch.md` était un document local non suivi et historique à la date de cette passation : ne pas le supprimer, le publier ou considérer son contenu comme une feuille de route actuelle sans vérification.
- Vérifier que ces documents de passation sont disponibles dans le checkout utilisé ; leurs références décrivent l'état du projet lors de leur rédaction.

## Règles de sécurité et de confidentialité

- Ne jamais exposer mots de passe, jetons, clés, cookies, contenu de `/data`, VIN ou journaux bruts susceptibles de les contenir. Ne pas committer de données personnelles, secrets ou fichiers de configuration propres à l'installation.
- Examiner d'abord en lecture seule. Toute commande sur la borne ou le chauffe-eau, modification Home Assistant, redémarrage ou déploiement sur l'installation réelle exige une autorisation explicite et un contrôle du contexte. Les tests locaux utilisent des données isolées et fictives.
- Ne pas affaiblir les limites électriques, les conditions de fraîcheur des mesures, les protections hors ligne ou la confirmation d'effet physique. Une commande acceptée ne prouve pas son exécution. Le mode manuel maintient ces protections et l'objectif de charge.
- Un seul contrôleur peut utiliser un répertoire de données donné. Ne pas lancer une instance de test sur le volume de production. Sauvegarder de manière cohérente la base et la clé de chiffrement avant toute opération de migration ou restauration autorisée.
- Documenter ce qui est réellement vérifié ; ne jamais annoncer qu'un déploiement ou comportement physique est validé à partir des seuls tests logiciels.

## Architecture et conventions

- Backend Python/FastAPI : `backend/app`; tests : `tests/`. Frontend React/TypeScript/Vite : `frontend/src`; tests frontend et navigateur dans `frontend`.
- Garder séparés mesures, décision et commande : connecteurs -> modèle de domaine -> coordinateur / moteur -> dispatch -> confirmation physique. Les valeurs conservées pour la continuité de l'affichage ne doivent jamais servir à contourner la fraîcheur exigée par le moteur.
- L'historique des sessions est local et persistant ; ne pas créer de source de vérité concurrente ni inventer de coût, de provenance solaire ou de pourcentage de batterie manquant. Conserver les marqueurs de mesures partielles.
- La logique de SoC et certains connecteurs s'inspirent d'EVCC. Conserver les notices et provenances dans `docs/third-party/`; vérifier les licences avant toute nouvelle reprise de code ou d'images.
- Interface en français, thèmes sombre et clair, mobile iPhone/Safari et ordinateur. Préserver les fonctionnalités existantes et les accès tactiles. Les spécifications anciennes peuvent être dépassées : le code courant et les demandes ultérieures priment.

## Commandes principales

Exemples depuis la racine, dans un environnement isolé ; adapter l'activation du venv au système. Sous PowerShell, `npm.cmd` peut être nécessaire.

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

Les tests navigateur se lancent depuis `frontend` avec `npx playwright install chromium webkit` puis `npm run e2e`. L'exécution locale utilise des fixtures ; consulter `scripts/e2e_server.py` et [la passation](HANDOFF_CLAUDE.md) avant de les adapter. Le build inclut la vérification TypeScript ; aucun script de lint distinct n'a été identifié.

Pour lancer le backend localement, utiliser un `SEM_DATA_DIR` **neuf et jetable**, puis `uvicorn app.main:create_app --factory --app-dir backend --host 127.0.0.1 --port 8080`. Ne pas y raccorder des équipements réels sans autorisation. Le frontend Vite local peut utiliser le proxy API prévu par sa configuration.

Pour les modifications de schéma ou d'API, vérifier migrations, export OpenAPI, génération des types TypeScript et tests correspondants. Avant toute livraison, vérifier les tests et le diff réellement obtenus, sans supposer que les résultats historiques sont encore valables.
