# MySQL-deployment

Het platform gebruikt uitsluitend MySQL 8.4. De database is alleen bereikbaar op het interne Docker-netwerk en publiceert geen hostpoort.

## Aanmelden via Authentik

De lokale Authentik-testinstantie en de configuratie staan in [authentik/README.md](authentik/README.md).
Authentik beheert accounts en globale EPD-rollen. Opleidingen, lesgroepen en casustoewijzingen
worden in het EPD beheerd. Productie gebruikt HTTPS voor zowel de EPD-callback als alle OIDC-
eindpunten. `OIDC_ENABLED=1` vereist een exacte issuer, client-ID, client secret, authorization-,
token-, UserInfo-, JWKS- en end-session-URL en de groepsmapping. De webcontainer krijgt deze
waarden via Compose; zij worden niet in Git opgeslagen.

Na een overstap naar een andere Authentik-omgeving worden gebruikers op `(issuer, sub)`
herkend. Een nieuw issuer maakt nieuwe EPD-accounts; e-mailadressen koppelen geen accounts.
Maak vóór de overstap een configuratiekopie en controleer de claims met een testaccount uit
iedere rol. Houd `EMERGENCY_LOGIN_ENABLED=0`, behalve tijdens tijdelijk herstel. Maak één
lokale superuser aan met `createsuperuser` en sla diens wachtwoord buiten de applicatie op.

## Eerste installatie

1. Kopieer `.env.example` naar `.env`.
2. Vervang alle secrets en configureer de publieke hostnamen.
3. Laat `DJANGO_DEBUG=0` en `SEED_DEMO=0` staan.
4. Start het platform:

```sh
docker compose up --build -d
docker compose ps
```

5. Maak alleen voor noodtoegang een lokale superuser. De dagelijkse EPD-beheerder komt
   via de geconfigureerde Authentik-beheerdersgroep:

```sh
docker compose exec web python manage.py createsuperuser
```

De webcontainer wacht op MySQL, voert migraties uit, zaait de standaardbibliotheek indien
nodig en start Gunicorn. De vaste dossierstructuur wordt bij het aanmaken van een casus
gekopieerd.

Controleer de effectieve applicatieverbinding:

```sh
docker compose exec web python manage.py check_database
```

## Databasebeheer

Open een MySQL-console zonder poort 3306 publiek te maken:

```sh
docker compose exec db mysql -u root -p educatief_epd
```

Een gewone `docker compose down` bewaart het volume. Gebruik nooit `docker compose down -v` op een omgeving waarvan de gegevens behouden moeten blijven.

## Back-up

Maak vóór elke update een map buiten het Docker-volume en voer uit:

```sh
mkdir -p backups
docker compose exec -T db sh -c \
  'exec mysqldump -uroot -p"$MYSQL_ROOT_PASSWORD" --single-transaction --routines --triggers --default-character-set=utf8mb4 "$MYSQL_DATABASE"' \
  > backups/educatief_epd.sql
```

Op PowerShell gebruikt het bytesgewijze script geen tekstomzetting:

```powershell
node backup_database.mjs
```

Bewaar productiebestanden versleuteld buiten de applicatieserver.

## Hersteltest

Herstel een back-up eerst naar een afzonderlijke database:

```sh
printf '%s\n' 'CREATE DATABASE educatief_epd_restore CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci;' | \
  docker compose exec -T db sh -c 'exec mysql -uroot -p"$MYSQL_ROOT_PASSWORD"'
docker compose exec -T db sh -c 'exec mysql -uroot -p"$MYSQL_ROOT_PASSWORD" educatief_epd_restore' \
  < backups/educatief_epd.sql
printf '%s\n' 'SELECT COUNT(*) FROM educatief_epd_restore.dossier_case;' | \
  docker compose exec -T db sh -c 'exec mysql -N -uroot -p"$MYSQL_ROOT_PASSWORD"'
```

Verwijder de hersteldatabase pas nadat recordaantallen en steekproeven zijn gecontroleerd.
Voor een automatische lokale herstelcontrole maakt `node verify_restore.mjs` een dump,
zet die in een uniek tijdelijk schema terug, vergelijkt aantallen casussen,
studentdossiers en externe identiteiten en verwijdert daarna het tijdelijke schema.

## Updates en monitoring

```sh
docker compose build web
docker compose up -d
docker compose ps
docker compose exec web python manage.py check_database
```

Controleer `/health/`, containerlogs, beschikbare opslag en MySQL-back-ups. De MySQL-initialisatie verleent de applicatiegebruiker alleen binnen `test_educatief_epd` extra rechten. Daardoor maken Django-tests een aparte tijdelijke database en wijzigen ze de applicatiedatabase niet.

```sh
docker compose run --rm web python manage.py test
docker compose run --rm -e DJANGO_DEBUG=0 web python manage.py check --deploy
```
