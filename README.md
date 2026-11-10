# Kalibro

Studieplanner die lokaal draait. Je uploadt cursusmateriaal, Kalibro haalt de
structuur en de omvang eruit, schat per onderdeel hoeveel tijd het kost, plant
dat in je studieblokken rond je deadlines, en **kalibreert de schattingen met je
eigen gelogde tijden**.

- **Backend:** FastAPI, SQLAlchemy, SQLite, Alembic (`backend/`)
- **Frontend:** HTML, CSS en JavaScript zonder buildstap (`frontend/`), plus
  `scherm.html`: een timer voor het 4"-aanraakscherm aan de Pi
- **Planner:** verdeelt het resterende werk over je studieblokken, vroegste
  deadline eerst, en zegt per deadline of het haalbaar is
- **Kalibratie:** een correctiefactor per taaktype en per vak uit je gelogde
  tijd, met shrinkage zolang er weinig data is, een marge (80%) in plaats van
  één getal, en de afwijking (MAPE) per week
- **Structuur zonder LLM:** PDF-bladwijzers (`get_toc()`), anders koppen herkend
  aan de lettergrootte. Gescande PDF's (geen tekstlaag) worden gemarkeerd om
  handmatig te schatten, want er is geen OCR.
- **Privacy:** cursusmateriaal blijft op je eigen toestel en gaat nooit naar een
  externe API.

## Lokaal starten

Vereist [uv](https://docs.astral.sh/uv/).

```bash
cd backend
uv sync
uv run alembic upgrade head
uv run uvicorn app.main:app --reload --port 8002
```

De app staat op <http://localhost:8002>, de timer voor het kleine scherm op
`/scherm.html` en de API-documentatie op `/docs`.

Installeren op de Pi: [docs/deployment.md](docs/deployment.md).

## Testen

```bash
cd backend
uv run pytest
```

De tests gebruiken een tijdelijke database en maken hun eigen PDF's aan.

## API

| Methode | Pad | Wat |
|---|---|---|
| `GET/POST` | `/api/courses` | vakken oplijsten of aanmaken |
| `GET/PUT/DELETE` | `/api/courses/{id}` | één vak |
| `POST` | `/api/courses/{id}/sources` | PDF uploaden: structuur + taken met schatting |
| `GET` | `/api/courses/{id}/sources` | bronnen van een vak |
| `GET/DELETE` | `/api/sources/{id}` | bron met onderdelen en taken |
| `POST` | `/api/sources/{id}/reprocess` | opnieuw verwerken (geweigerd zodra er tijd gelogd is) |
| `GET` | `/api/courses/{id}/tasks` | taken van een vak met schatting |
| `POST` | `/api/courses/{id}/tasks` | eigen taak (labo, project) |
| `PATCH/DELETE` | `/api/tasks/{id}` | taak aanpassen (o.a. eigen schatting) of verwijderen |
| `GET/POST` | `/api/courses/{id}/deadlines` | deadlines van een vak |
| `POST` | `/api/courses/{id}/deadlines/sync` | deadlines ophalen uit de iCal-feed |
| `PUT/DELETE` | `/api/deadlines/{id}` | deadline aanpassen; een feed-deadline wordt genegeerd i.p.v. gewist |
| `GET/POST/DELETE` | `/api/availability/slots`, `/exceptions` | weekpatroon en uitzonderingen |
| `POST` | `/api/tasks/{id}/start`, `/api/timer/stop`, `/api/tasks/{id}/complete` | de timer |
| `GET/POST` | `/api/tasks/{id}/sessions` | sessies, ook achteraf toevoegen |
| `GET/POST` | `/api/plan` | huidig plan met haalbaarheid / (her)plannen vanaf nu |
| `GET` | `/api/calendar.ics` | plan en deadlines als agenda-feed |
| `GET` | `/api/calibration`, `/api/calibration/accuracy` | factoren en MAPE per week |
| `GET/PUT` | `/api/rates` | basistempo per taaktype |

Een taak is een studie-eenheid, meestal een hoofdstuk. Kalibro daalt af in de
inhoudstafel tot een onderdeel hoogstens 60 pagina's telt: delen worden
hoofdstukken, hoofdstukken worden niet opgesplitst in subkoppen. Een te groot
hoofdstuk wordt in blokken van ongeveer 25 pagina's verdeeld. Cover, inhoudstafel,
voorwoord, index, bibliografie en oplossingen krijgen geen taak. Een sectie
"Exercises" of "Oefeningen" wordt een aparte oefentaak, met als omvang het aantal
genummerde vragen.
Taken uit een gescande PDF hebben `needs_manual_estimate: true` tot je zelf een
schatting invult. Dezelfde PDF twee keer uploaden geeft `409`.

## Datamodel

```
Vak (courses)
 ├─ Bron (sources)          geüpload bestand; het bestand zelf staat in data/uploads/
 │   └─ Onderdeel (sections) boom via parent_id, paginabereik, woorden, oefeningen
 ├─ Deadline (deadlines)    handmatig of uit de iCal-feed (ical_uid voorkomt dubbels)
 └─ Taak (tasks)            type + omvang, optioneel gekoppeld aan onderdeel en deadline
     ├─ Sessie (study_sessions)  gelogde tijd van de timer
     └─ Planblok (plan_blocks)   per planversie (plan_versions)

Beschikbaarheid: weekpatroon (availability_slots) + uitzonderingen per datum
Tempo (task_rates): basistempo per taaktype, in seconden per eenheid
Nauwkeurigheid (weekly_accuracy): MAPE per week
```

## Afspraken in de data

- Duur in seconden. Tijdstippen in UTC. Het weekpatroon van de beschikbaarheid
  staat in lokale tijd (`"HH:MM"`).
- Woorden en oefeningen tellen per onderdeel **zonder** de kinderen: elke pagina
  hoort bij het laatste onderdeel dat erop of ervoor begint. Optellen telt dus
  nooit iets dubbel. Het paginabereik loopt wel over de kinderen.
- Schatting van een taak: `manual_estimate_s` als die ingevuld is, anders
  `amount × seconds_per_unit`, maal de correctiefactor.
- `estimate_at_start_s` wordt vastgezet bij de eerste sessie. Zo kan latere
  herkalibratie de geschiedenis niet herschrijven en blijft de MAPE eerlijk.
- Correctiefactoren worden telkens uit de sessies berekend en niet opgeslagen.
  Alleen de wekelijkse MAPE wordt bewaard, voor de trend.
- Herplannen maakt een nieuwe `plan_version`. Oude versies blijven bestaan.
- Resterend werk = gekalibreerde schatting min gelogde tijd, minstens 15 min
  zolang een taak niet af is. Herplannen is daardoor gewoon opnieuw plannen.
- De planner deelt geen blokken korter dan 25 minuten uit, tenzij een taak
  daarmee af is.
- Schemawijzigingen gaan via Alembic.
- Cursusmateriaal komt nooit in de repo (zie `.gitignore`).
