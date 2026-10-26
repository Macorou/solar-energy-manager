# Connexion Peugeot

Le connecteur lit uniquement la batterie et l’autonomie. La borne OCPP reste seule responsable de la recharge.

Dans Connexions, lancer la connexion Peugeot. Se connecter sur le domaine Peugeot, puis copier l’adresse de redirection `mymap://oauth2redirect/fr?...` dans le champ dédié de l’application. L’état OAuth est à usage unique et expire après dix minutes. Si le navigateur ne permet pas de récupérer cette adresse, l’import d’un jeton de renouvellement obtenu avec un outil compatible est disponible dans les paramètres avancés. Ne jamais transmettre ces valeurs dans une issue ou dans un chat.

Le VIN est à saisir dans Véhicules. Les accès sont chiffrés en base. Une identité client différente peut être configurée si Peugeot modifie son service. Les appels sont espacés de quinze minutes par défaut ; une limitation impose un délai de quinze minutes. Un refus permanent affiche « reconnexion nécessaire ».

L’heure affichée vient du constructeur. Un véhicule endormi peut fournir une ancienne mesure malgré une réponse HTTP réussie. Une batterie trop ancienne interdit le démarrage ou demande la suspension au prochain calcul. Aucune commande de réveil concurrente n’est envoyée.

**État de validation :** tests HTTP simulés réussis ; connexion au compte réel et comparaison avec l’e-208 2020 non effectuées. L’API mobile ne constitue pas un contrat de disponibilité de Peugeot. L’accès officiel développeur Stellantis reste soumis aux modalités du fournisseur.
