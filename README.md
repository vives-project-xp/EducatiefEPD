# PX4 - Educatief EPD vroedkunde

[![VIVES Elektronica-ICT](https://img.shields.io/badge/VIVES-Elektronica--ICT-blue)](https://www.vives.be/nl/technology/elektronica-ict)
[![Project Experience](https://img.shields.io/badge/Project-Experience-brightgreen)](https://github.com/vives-project-xp)

# Project 

Een educatief elektronisch patiëntendossier voor zorgopleidingen. Docenten moeten fictieve
patiëntcasussen en basisdossiers kunnen voorbereiden, terwijl iedere student een eigen 
bewerkbare versie van zo’n dossier krijgt.

Dit project combineert verschillende domeinen uit elektronica-ICT: full-stack webontwikkeling, databases en datamodellering, authenticatie en autorisatie containerisatie, UX, softwarearchitectuur en testing. Studenten bouwen geen losstaande demo, maar ontwerpen een platform waarin rollen, herbruikbare templates, individuele studentenversies en onderhoudbaarheid vanaf het begin doordacht moeten worden.

## Doel

Een veilig, flexibel en herbruikbaar leerplatform ontwikkelen. Het platform start bij Vroedkunde en kan later worden uitgebreid naar andere zorgopleidingen.

## Stappen

- Analyse en architectuur: workflows, gebruikersrollen en datamodel bepalen.
- Dossiers en casussen: docenten maken dossiers; studenten werken in eigen versies.
- Herbruikbare inhoud: formulieren en dossiermodules delen via een bibliotheek.
- Testen en documentatie: functionaliteit valideren en installatie en beheer beschrijven.
- Mogelijke uitbreiding: AI inzetten voor samenvattingen, tijdlijnen en didactische feedback.

## Software

- Backend: Python en Django.
- Database: MySQL.
- Webinterface: Django-templates, HTML en CSS.
- Deployment: Docker Compose.
- Authenticatie: ondersteuning voor koppeling met een centrale identity provider.

## Inhoud van software en media

Overzicht van de belangrijkste mappen en startbestanden:

```text
EducatiefEPD/
|-- Software/
|   |-- .env.example
|   |-- compose.yaml
|   |-- DEPLOYMENT.md
|   |-- Dockerfile
|   |-- manage.py
|   |-- requirements.txt
|   |-- config/
|   |-- docker/
|   |   `-- mysql/
|   |-- dossier/
|   |   |-- management/commands/
|   |   `-- migrations/
|   |-- static/
|   |-- templates/
|   `-- backups/
`-- media/
    |-- Foto_EPD.jpg
    |-- IMG_1509.HEIC
    |-- Poster P.E. Educatief EPD.png
    `-- README.md
```

## Benodigde inhoud

- `config/` bevat de Django-configuratie; `dossier/` bevat de applicatie en database-migraties.
- `templates/` en `static/` bevatten respectievelijk de webpagina's en vormgeving.
- `compose.yaml`, `Dockerfile` en `requirements.txt` beschrijven hoe de applicatie draait en welke Python-pakketten nodig zijn. `manage.py` voert Django-beheercommando's uit.
- `.env.example` toont welke lokale instellingen nodig zijn. Gebruik eigen waarden in `.env` en deel dat bestand niet.
- `media/` is voor projectafbeeldingen en documentatiemateriaal. Gebruik geen vertrouwelijke of herleidbare patiëntgegevens.

## Leden

| <img src="https://github.com/EwoudBoutje.png" width="64" alt="Ewoud Bouttelisier"> | Ewoud Bouttelier | Ontwikkelaar |

|<img src="https://github.com/Mathiss-Rambour.png" width="64" alt="Mathiss Rambour">| Mathiss Rambour | Ontwikkelaar |

|<img src="https://github.com/bhavninderpalsingh-tech.png" width="64" alt="Bhavninder Pal Singh">| Bhavninder Pal Singh | Ontwikkelaar |


