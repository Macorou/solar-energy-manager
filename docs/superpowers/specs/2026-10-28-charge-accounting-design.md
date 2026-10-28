# Recharge dynamique, suivi et SOC estimé
Autorisation : demandes utilisateur regroupées puis « ok tu peux codé ce patch ».
Base : 0.1.8 ; aucune commande matérielle, modification HA ou installation Portainer.

## Choix et contraintes
Conserver le dashboard, dessins, identifiants et secrets. Puissances W sous1000,
kW dès1000 (signe conservé). Maison reste le total voiture/ballon inclus.
Le plafond voiture3700W n'est pas relevé. Aucun capteur réel, phase ou limite20A
n'est imposé. Réglages HA facultatifs avec contrôle par phase explicitement activable.
Le solaire vaut0€/kWh par défaut, réglable ; choix de l'auteur, modifiable.
La phase physique, la capacité utile et le rendement sont des paramètres utilisateur.

## Régulation
Porter le principe EVCC ValidateCurrent : courant nouveau limité au courant
effectivement mesuré de la charge + marge du circuit. Arrondir vers le bas ;
sous le minimum, suspendre. Appliquer après budgets solaire/global dans tous modes.
Courants HA A/mA ; tensions V ; puissances W/kW. Ne pas confondre VA et W.
Échantillons vérifiés, cohérents, finis. Contrôle activé + phase non configurée
ou mesure requise absente : aucune hausse et suspension.
Pour une voiture mono, utiliser sa phase réseau configurée ; tri, les trois.
Lire Current.Import OCPP (courant mono sans phase accepté, sinon par phase).
Si la charge est à l'arrêt confirmé, courant propre0 ; si elle charge sans
courant mesuré valide, ne pas créditer le courant commandé.
Réserver les incréments pour plusieurs bornes et les commandes en attente ;
ne pas libérer un budget avant observation. Baisse immédiate sans délai nuage.
Source EVCC MIT au commit9404d825d6a659d8ce7f47d3b0d2e14ac04506e0 :
core/circuit/circuit.go ValidateCurrent, core/loadpoint.go setLimit.
Reprise adaptée par phase, attribution MIT incluse dans Docker.

## Énergie et coût
Session de branchement persistée, pauses/transactions ne la réinitialisent pas.
Index OCPP Wh/kWh indépendant des trames puissance ; meter_start/stop inclus.
Deltas non négatifs, trames chronologiques dédupliquées ; compteur réinitialisé :
rebaser et signaler résultat partiel, sans inventer de kWh.
Conserver dernière session après débranchement. Tarifs HA €/kWh ou EUR/kWh ;
coût solaire configurable, aucun tarif secret nouveau.
Mix estimé proportionnel logement : solaire autoconsommé=max(0,PV-export),
import=max(0,réseau), poids réseau=import/(import+solaire autoconsommé).
Pas de comptage de l'énergie exportée. Coût par intervalles, historique
des contextes tarif/mix, interpolation temporelle des deltas compteur.
Tarif/mix absent ou intervalle trop long : coût/part solaire partiels/inconnus,
pas0 inventé. Prix effectif instantané distinct du coût moyen de session.
Comptabilité d'affichage sans bloquer les commandes en cas de tarif absent.

## SOC
Capacité utile et rendement configurables ; SOC référence +100*delta_kWh*rendement/capacité.
Référence constructeur conservée ; estimation affichée et utilisée pour cible
en solaire, planifié et manuel avec véhicule associé. Même ancienne mesure relue
ne remet pas l'estimation à zéro. Mesure plus récente : recaler à sa date avec
énergie chargée depuis cette date ; incohérence/historique absent signalés.
Persistance, véhicule associé, débranchement et réinitialisation compteur pris
en compte ; ne pas inventer une consommation de trajet non observée.
Pas de capacité/énergie fiable : SOC ancien insuffisant pour poursuivre à
l'aveugle ; une mesure constructeur fraîche reste utilisable. Arrêt cible
latched dans la session pour éviter reprises sur arrondis ; objectif augmenté
explicitement permet une reprise. Estimation sensible aux pertes/capacité.
La jauge brute garde sa date ; source du SOC effectif et cible dans l'état public.

## États voiture
Distinguer branchée, recharge observée, attente avec motif, terminée encore
branchée, débranchée ; hors connexion/inconnu/défaut distincts. Source Wallbox,
jamais seul charging_state Peugeot ancien. Garder Observation séparément.

## Validation
Tests domaine/HA/OCPP, coordinateur réel et frontend ; schema/build/CI Docker
et navigateur. Révision indépendante finale. Publication privée0.1.9 sur branche
existante, jamais déplacer un ancien tag ni déployer le serveur.

