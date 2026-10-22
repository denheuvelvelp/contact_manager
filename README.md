# Huismeester Contactmanager

Moderne, schaalbare cloud-contactmanager voor de huismeester van een appartementencomplex, opgebouwd in twee afzonderlijke applicaties:
1. **Coöperatieve Vereniging:** Uitsluitend bewoners van de appartementen, inclusief 2 noodcontacten en calamiteitengegevens (minder mobiel/zorg).
2. **Vereniging van Eigenaren (VvE):** Eigenaren, commerciële bedrijven en garagehouders (gepland in Fase 3).

---

## Kernfunctionaliteiten (Fase 1: Coöperatieve Vereniging)

- **Wekelijkse Rebo CSV Import:**
  - Ondersteunt exact de 11 kolommen van Rebo:
    `Index nummer`, `Bestemming`, `Adres appartementsrecht`, `Naam`, `Postadres`, `Telefoonnummer`, `Telefoonnummer 2`, `Telefoonnummer 3`, `Email`, `Email 2`, `Email 3`.
  - **100% Veilige Ontdubbeling:** Reeds bestaande bewoners worden **met rust gelaten** (niet overschreven). Alleen nieuwe bewoners worden toegevoegd.
  - Ondersteunt zowel komma (`,`) als puntkomma (`;`, Nederlandse Excel) en UTF-8 / Windows-1252 encodings.
- **Twee Noodcontacten per Bewoner:**
  - Noodcontactpersoon 1 (Naam 1, Noodtelefoon 1, Nood-email 1)
  - Noodcontactpersoon 2 (Naam 2, Noodtelefoon 2, Nood-email 2)
- **Calamiteiten & Huismeesterfuncties:**
  - Vlag voor *Minder mobiel / Zorgbehoevend* (voor hulpdiensten bij ontruiming/brandalarm).
  - Intercom-naam, huisdieren, interne huismeesternotities.
- **Cloud & Beveiliging:**
  - **Google Cloud Run:** Volledig containerized via Docker.
  - **Firebase Hosting:** Snelle en veilige webtoegang met SSL.
  - **Google Cloud Firestore:** Schaalbare serverless NoSQL-database (met automatische SQLite-terugval voor direct lokaal testen).
  - **GitHub Actions & Dependabot:** Automatische codecontroles en wekelijkse dependency-scans op beveiligingslekken.

---

## Lokale Installatie & Testen

### Optie A: Met Docker (Aanbevolen)
```bash
docker compose up --build
```
Open vervolgens in je browser: [http://localhost:8080](http://localhost:8080)

### Optie B: Met Python Virtual Environment
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r apps/cooperatie/requirements.txt

# Start de applicatie
python3 -m uvicorn apps.cooperatie.main:app --port 8080 --reload
```
Open vervolgens in je browser: [http://localhost:8080](http://localhost:8080)

---

## Automatische Tests Uitvoeren
```bash
pytest -v
```

---

## Structuur Monorepo

```
.
├── .github/
│   ├── dependabot.yml       # Automatische Dependabot security updates
│   └── workflows/
│       └── ci.yml           # GitHub Actions CI (linting, syntax en tests)
├── apps/
│   ├── cooperatie/          # Applicatie 1: Coöperatieve Vereniging
│   │   ├── Dockerfile
│   │   ├── main.py          # FastAPI webapplicatie & API endpoints
│   │   ├── importer.py      # Slimme Rebo CSV-importeur met ontdubbeling
│   │   ├── models.py        # Datamodellen (Rebo kolommen + 2x noodcontacten)
│   │   ├── database.py      # Cloud Firestore + SQLite fallback
│   │   ├── templates/       # HTML5 Jinja2 interfaces (Tailwind CSS)
│   │   └── sample_rebo_cooperatie.csv # Testbestand met jouw Rebo kolommen
│   └── vve/                 # Applicatie 2: VvE (Fase 3)
├── shared/                  # Gedeelde logica
├── docker-compose.yml
└── README.md
```

