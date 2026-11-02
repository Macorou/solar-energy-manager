# Chauffe manuelle après une ancienne commande en attente

L'utilisateur a demandé une chauffe, mais l'API conserve un arrêt automatique
créé pendant la reconnexion. Reproduction locale : ancienne réserve 2570 W,
état initial indisponible -> suspend ; POST manual réussi -> autre suspend,
mode enregistré manual, réserve toujours 2570 W. Aucun ordre réel envoyé.

Corriger le cycle complet dans 0.1.6 :
- Le renouvellement d'une demande manuelle ne doit pas oublier une autorisation
  en cours et provoquer une suspension ou une répétition du départ.
- Un arrêt Ariston peut être confirmé par une relecture native connectée/off
  après l'ordre, récente au seuil des mesures, complétée par une puissance <=20 W
  vérifiée après l'ordre dans HA et un réseau vérifié cohérent. La date fournisseur
  n'est pas modifiée. Une ancienne puissance seule ne suffit jamais.
- Une commande encore en cours d'envoi ne peut pas être confirmée. Tout arrêt
  du ballon requiert l'état natif off, même si la mesure électrique est nouvelle.
- Une chauffe reste confirmée par une nouvelle mesure électrique non nulle et
  l'état natif on. Conserver les confirmations strictes des bornes OCPP.
- Attendre les 60 secondes natives avant un nouveau départ, sans l'envoyer puis
  transformer son refus de temporisation en défaut inconnu.
- Présenter la chauffe demandée comme telle pendant l'arrêt préalable en attente,
  au lieu d'afficher simplement « Arrêt demandé ».
- Conserver les contrôles d'armement, objectifs, limites, erreurs, réservations et
  durée de la demande manuelle. Aucun acquittement aveugle au démarrage.

Validation : reconnexion -> arrêt accepté -> demande de chauffe -> arrêt confirmé
avec 0 W inchangé + off natif -> délai -> départ accepté -> effet mesuré.
Distribution privée amd64, sans migration, aucune action sur Portainer ou matériel.
