# Huismeester Contactmanager

Moderne, schaalbare cloud-contactmanager voor de huismeester van een appartementencomplex, opgebouwd in twee afzonderlijke applicaties:

1. **Coöperatieve Vereniging (Port 8080):** Uitsluitend bewoners van de appartementen, inclusief 2 aparte noodcontacten en calamiteitengegevens (minder mobiel/zorg).
2. **Vereniging van Eigenaren - VvE (Port 8081):** Vastgoedeigenaren, bedrijven (commerciële ruimtes), garageboxhouders, breukdelen/stemgewicht en externe correspondentieadressen.

---

## Kernfunctionaliteiten

### 1. Wekelijkse Rebo CSV Import & Ontdubbeling
- Ondersteunt exact de 11 kolommen van Rebo voor beide verenigingen:
  `Index nummer`, `Bestemming`, `Adres appartementsrecht`, `Naam`, `Postadres`, `Telefoonnummer`, `Telefoonnummer 2`, `Telefoonnummer 3`, `Email`, `Email 2`, `Email 3`.
- **100% Veilige Ontdubbeling:** Reeds bestaande eenheden worden **met rust gelaten** (niet overschreven). Alleen nieuwe eenheden worden toegevoegd. Handmatig verrijkte gegevens (zoals breukdelen, garages of noodcontacten) blijven altijd intact.
- Ondersteunt komma (`,`), puntkomma (`;`, Nederlandse Excel) en UTF-8 / Windows-1252 encodings.

### 2. VvE Specifieke Functies (Applicatie 2)
- **Correspondentieadres Externe Eigenaren:** Automatische detectie wanneer een eigenaar elders woont (postadres wijkt af van appartementsrecht).
- **Garagebox- & Parkeerplaatsnummers:** Beheer van gekoppelde garages (bijv. G-04, P-12).
- **Breukdelen & Stemgewicht:** Duidelijk overzicht voor de ALV (bijv. 14/1000).
- **Slimme Categorisatie:** Automatische herkenning van Woningeigenaren, Bedrijven / Commercieel en Garageboxhouders.

### 3. Coöperatieve Functies (Applicatie 1)
- Twee aparte noodcontacten (Naam 1 & 2, Noodtelefoon 1 & 2, Nood-email 1 & 2).
- Vlag voor *Minder mobiel / Zorgbehoevend* (voor hulpdiensten bij ontruiming/brandalarm).
- Huisdieren, intercomnaam, etage, interne huismeesternotities.

---

## Lokale Installatie & Testen

### Coöperatieve Vereniging starten (Poort 8080):
```bash
./run_cooperatie.sh
```
Open in je browser: [http://10.13.20.161:8080](http://10.13.20.161:8080) (of localhost:8080)

### VvE Applicatie starten (Poort 8081):
```bash
./run_vve.sh
```
Open in je browser: [http://10.13.20.161:8081](http://10.13.20.161:8081) (of localhost:8081)

---

## Automatische Tests Uitvoeren
```bash
PYTHONPATH=. pytest -v
```

---

## Deployment naar Google Cloud & Firebase

De GitHub Actions pipeline ([.github/workflows/deploy.yml](.github/workflows/deploy.yml)) bouwt en publiceert beide applicaties automatisch bij elke push naar `main`:
- `cooperatie-service` op Google Cloud Run (gekoppeld aan Firestore collectie `cooperatie_contacten`)
- `vve-service` op Google Cloud Run (gekoppeld aan Firestore collectie `vve_contacten`)
