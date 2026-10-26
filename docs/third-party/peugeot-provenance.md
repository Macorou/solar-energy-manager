# Provenance Peugeot

Référence étudiée : [EVCC, révision 08caa0e2755c56501c5906e1f680a6dce7ef91b6](https://github.com/evcc-io/evcc/tree/08caa0e2755c56501c5906e1f680a6dce7ef91b6/vehicle/psa), fichiers oauth2.go, api.go et provider.go. Endpoints, identité publique du client OAuth mobile et correspondance des champs adaptés en Python. Aucun module Go embarqué ; aucune commande distante véhicule reprise. Le projet psa_car_controller (GPL) n’est pas incorporé.

EVCC est sous licence MIT : Copyright (c) evcc.io (andig, naltatis, premultiply).

Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated documentation files (the "Software"), to deal in the Software without restriction, including without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to permit persons to whom the Software is furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

Source officielle consultée le 26 octobre 2026 : [Stellantis for Developers](https://developer.groupe-psa.io/). L’application utilise actuellement le flux mobile compatible EVCC, dont le fonctionnement sur le compte de l’utilisateur reste à vérifier. Elle ne prétend pas disposer d’un contrat d’API partenaire Stellantis.
