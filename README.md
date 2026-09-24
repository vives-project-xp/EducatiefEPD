# Educatief EPD voor Vroedkunde

Een educatief prototype waarin studenten een fictieve patiëntcasus kunnen starten, dossiergegevens invullen en hun uitwerking indienen. Docenten beheren de casussen via Django admin.

## Stack

- Django 5 met server-rendered templates
- Bootstrap 5 via CDN
- MySQL 8.4
- Docker Compose en Gunicorn

## Starten met Docker

1. Kopieer `.env.example` naar `.env` en pas secrets aan voor een echte omgeving.
2. Start de applicatie:

   ```bash
   docker compose up --build
   ```

3. Maak demo-gebruikers en een voorbeeldcasus:

   ```bash
   docker compose exec web python manage.py seed_demo
   ```

4. Open http://localhost:8000/login/.

Demo-accounts:

- `docent` / `docent123`
- `student` / `student123`

## Belangrijke routes

- `/login/`: aanmelden
- `/`: dashboard, afhankelijk van de rol
- `/casus/<id>/overzicht/`: casus briefing; deze view maakt nog geen uitwerking aan
- `/casus/<id>/dossier/`: dossier openen; maakt de studentuitwerking aan en kloont de startsituatie
- `/casus/<id>/start/`: legacy-alias naar dossier openen
- `/uitwerking/<id>/`: dossierwerkruimte
- `/uitwerking/<id>/submit/`: uitwerking indienen
- `/admin/`: beheerinterface voor docenten/beheerders

## Databaseconfiguratie

De Django-configuratie leest credentials dynamisch uit de Docker-omgeving:

```python
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.mysql",
        "NAME": os.getenv("MYSQL_DATABASE", "educatief_epd"),
        "USER": os.getenv("MYSQL_USER", "epd_user"),
        "PASSWORD": os.getenv("MYSQL_PASSWORD", "epd_password"),
        "HOST": os.getenv("MYSQL_HOST", "localhost"),
        "PORT": os.getenv("MYSQL_PORT", "3306"),
    }
}
```

De webcontainer wacht op MySQL, voert migraties uit en start daarna Gunicorn. JSON-velden worden in de werkruimte gevalideerd voordat ze worden opgeslagen. Na indienen worden de gegevens read-only.

## Lokale ontwikkeling zonder Docker

Installeer de packages uit `requirements.txt`, configureer een bereikbare MySQL-database via de variabelen uit `.env.example` en voer uit:

```bash
python manage.py migrate
python manage.py seed_demo
python manage.py runserver
```