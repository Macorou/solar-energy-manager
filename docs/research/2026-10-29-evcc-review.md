# Revue finale du port EVCC pour 0.1.15

Une revue indépendante, en lecture seule, a porté sur le diff
`ab42834748a8cdfd65ed2ddea84c06eff5925985..295f2ac2cc2c0a261ddfbbfe4cc53d32916d8b32`,
le plan approuvé et les sources EVCC figées. Elle a été interrompue par une
limite d’utilisation puis reprise dans le même contexte. Aucun deuxième
reviewer n’a été lancé. La revue a conclu à trois problèmes importants,
reproduits en mémoire, sans problème classé critique. Ces problèmes sont
traités dans une passe de corrections et de tests de régression.

| Problème confirmé | Correction et vérification |
| --- | --- |
| Une panne de GetConfiguration empêchait l’arrêt et laissait l’autorisation active. Une exception du profil zéro ou du nettoyage empêchait aussi le repli. | Retrait de l’autorisation et annulation du départ avant tout réseau, même hors connexion ; capacités négociées persistées et réutilisées sans lecture bloquante ; repli RemoteStop sur refus ou exception. Budgets 5 s pour le profil, 5 s pour le nettoyage et 10 s pour le repli, sous le délai de transport de 25 s. Régression initiale : 2 échecs puis réussite ; tests supplémentaires après reboot et hors connexion. |
| Current.Offered pouvait confirmer une consigne alors que le courant réel surchargeait toujours le circuit indéfiniment. | Surveillance indépendante du courant physique et de la surcharge pendant 60 s. Suspension et défaut persistant, acquitté par désactivation explicite après arrêt mesuré. Tests du moteur et de la chaîne coordinator/dispatcher : consigne annoncée 16,9 A, courant réel 20,3 A et réseau 22,376 A ; cas complémentaire de réduction effectivement appliquée, reprise d’application et acquittement. |
| Sans capacité de batterie, une panne Peugeot laissait le pourcentage mémorisé autoriser une recharge ciblée indéfinie. | Le pourcentage reste affiché ; il devient inutilisable pour ce pilotage sans API valide et sans estimateur. Un message demande la capacité utile. Avec capacité et estimateur amorcé, la progression EVCC continue. Régression reproduite puis corrigée, sans critère de date Peugeot. |

Les points que le reviewer a refusé de certifier ont été examinés explicitement :

- Acceptation réelle des profils et application physique de la consigne par la
  Wallbox installée : validation matérielle maintenue après déploiement autorisé.
  Les tests simulés ne remplacent pas cette validation.
- Commutation automatique des phases, circuits parents arbitraires et autres
  protocoles de borne : restent hors du périmètre approuvé et sont exclus des
  fonctionnalités annoncées dans la note de version.

La revue a également confirmé la proximité du port de l’estimateur avec EVCC,
la stabilité du cas de surcharge sans cascade, la conservation des transactions
en pause et l’absence de fuite de secret dans la nouvelle API OCPP.
