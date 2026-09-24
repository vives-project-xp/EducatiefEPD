# Productiedeployment

## Vereisten

- Docker Engine met Compose
- Een DNS-naam en TLS-terminatie
- Beveiligde opslag voor `.env` en back-ups

Gebruik `.env.example` als configuratiesjabloon. Demo-inhoud mag in productie nooit worden geactiveerd.

## Installatie en update

```sh
docker compose pull
docker compose build web
docker compose up -d
docker compose ps
```

De healthcheck is beschikbaar op `/health/`. Een update voert database-migraties automatisch vóór de applicatiestart uit.

## Back-up

```sh
docker compose exec -T db pg_dump -U epd educatief_epd > educatief_epd.sql
```

Bewaar back-ups versleuteld en test periodiek een herstelactie in een afzonderlijke omgeving.

## Centrale aanmelding

Zet `OIDC_ENABLED=1` en configureer de issuer-endpoints en clientgegevens uit `.env.example`. Groepsclaims worden gemapt op student, docent en beheerder. Lokale Django-aanmelding blijft als noodtoegang beschikbaar.

## Operationele aandachtspunten

- Gebruik unieke secrets per omgeving.
- Beperk directe toegang tot PostgreSQL.
- Bewaak containerlogs en `/health/`.
- Controleer de auditlog via `/admin/`.
- Schakel demo-accounts uit en koppel de echte identity provider vóór ingebruikname.
