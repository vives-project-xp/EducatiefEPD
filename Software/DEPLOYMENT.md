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

De webcontainer wacht op MySQL, voert migraties en collectstatic uit en start Gunicorn.
Er wordt geen vaste dossierbibliotheek meer gezaaid. Nieuwe casussen starten zonder
dossiermodules; de docent kiest vervolgens een dossiersjabloon of losse onderdelen.
`SEED_DEMO=1` maakt uitsluitend expliciete demo-inhoud met een eigen dossiersjabloon aan.

Controleer de effectieve applicatieverbinding:

```sh
docker compose exec web python manage.py check_database
```

## Updates na het samenvoegen van de dossiertakken

Migratie `0009_merge_dossiers_functions` brengt de bestaande migratiepaden voor
dossiersjablonen en functiebeheer samen. Bewaar beide `0007`- en `0008`-reeksen;
deze kunnen al op afzonderlijke ontwikkelomgevingen zijn toegepast. De nieuwe migratie
werkt zowel op een lege database als na één van beide takken.

Migratie `0010_remove_librarytemplate_is_fixed` verwijdert de verouderde instelling
voor automatisch toevoegen. De bestaande bibliotheekmodules, casuskopieën en
studentgegevens blijven behouden. De automatische seed/kopieerroute en het commando
`initialize_platform` zijn verwijderd. `0011_record_existing_rich_text_choices` legt
het al aanwezige teksteditortype ook in de migratiestatus vast.

Voor de flexibele matrix blijft `0007_matrix_definition` als historische migratie
bestaan. `0012_merge_matrix_main` verbindt deze met `0011_record_existing_rich_text_choices`.
Pas de volledige migratiereeks toe, zowel bij een upgrade vanaf main als vanaf Matrix.
Lege matrixdefinities behouden de oude rij-/kolomweergave; bestaande studentsnapshots
worden niet herschreven. Nieuwe definities worden ook via dossiersjablonen gekopieerd.

Maak vóór een update een back-up. Bouw en start vervolgens de webcontainer opnieuw:

```sh
docker compose up -d --build web
docker compose exec web python manage.py check
docker compose exec web python manage.py makemigrations --check --dry-run
```

`http://localhost:8001/health/` controleert ook de databaseverbinding. De standaard
Compose-healthcheck test alleen de open webpoort. Controleer daarnaast de aanmelding
en de bibliotheek. Start geen andere branch op hetzelfde volume als die branch een
afwijkend databaseschema verwacht.

Bytecode en SQL-back-ups horen niet in Git. De eerdere gevolgde testdump is lokaal
bewaard als `backups/local/educatief_epd-test.sql`; deze genegeerde map wordt niet in
de containerimage opgenomen.

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

Controleer `/health/`, containerlogs, beschikbare opslag en MySQL-back-ups. De
MySQL-initialisatie verleent de applicatiegebruiker alleen binnen `test_educatief_epd`
extra rechten. Django-tests gebruiken een tijdelijke testdatabase. Om de
opstartmigraties op de applicatiedatabase over te slaan, gebruik je voor controles
expliciet de Python-entrypoint:

```sh
docker compose run --rm --no-deps --entrypoint python web manage.py test
docker compose run --rm --no-deps --entrypoint python -e DJANGO_DEBUG=0 web manage.py check --deploy
```
