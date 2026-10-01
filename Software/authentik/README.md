# Lokale Authentik voor het Educatief EPD

Deze wegwerpinstantie gebruikt Authentik 2026.8.3 en een eigen PostgreSQL-volume. Gebruik
alleen fictieve accounts. De echte VIVES-omgeving wordt later via configuratie gekoppeld.

## Starten en testaccounts aanmaken

1. Kopieer `.env.example` naar `.env` in deze map. Vervang alle voorbeeldwaarden door
   afzonderlijke willekeurige geheimen. Dit bestand staat buiten Git.
2. Voer in deze map `docker compose up -d` uit en wacht tot `docker compose ps` voor server,
   worker en PostgreSQL `healthy` toont.
3. Voer uit:

   ```powershell
   docker compose exec -T server ak shell -c "exec(open('/epd-bootstrap/bootstrap.py').read())"
   ```

Het idempotente bootstrapcommando maakt twee OIDC-applicaties, de groepen `epd-studenten`,
`epd-docenten` en `epd-beheerders`, en de gebruikers `epd-student`, `epd-docent` en
`epd-beheerder`. Hun wachtwoorden en het wachtwoord van `akadmin` staan in de lokale
`authentik/.env` onder de bijbehorende `EPD_TEST_*_PASSWORD`-namen. De tweede provider
`educatief-epd-alt` heeft een eigen client, secret en issuer voor de omschakeltest.

De OIDC-clients gebruiken de authorization-code-flow met PKCE, een RS256 signing key en de
scopes `openid`, `email` en `profile`. Alleen
`http://localhost:8001/oidc/callback/` is als callback toegestaan. De lokale provider
gebruikt een invalidation flow die ook de Authentik-sessie beëindigt. Beheerders kunnen
groepen en accounts daarna in de Authentik-beheerinterface op `http://localhost:9000/`
aanpassen. De standaard profile scope bevat de groepsnamen in de `groups`-claim.

## EPD verbinden op Windows met Docker Desktop

Vul `Software/.env` aan en gebruik het client secret uit `authentik/.env`. De browser gebruikt
`localhost`, terwijl de webcontainer via `host.docker.internal` bij Authentik komt. De
optionele token-Host-header zorgt dat Authentik in het ID-token dezelfde issuer zet als in
het discoverydocument voor `localhost`. Gebruik in productie één gewone HTTPS-hostnaam en
laat `OIDC_TOKEN_HOST_HEADER` leeg.

```dotenv
DJANGO_DEBUG=1
SECURE_SSL_REDIRECT=0
OIDC_ENABLED=1
EMERGENCY_LOGIN_ENABLED=0
OIDC_ISSUER=http://localhost:9000/application/o/educatief-epd/
OIDC_RP_CLIENT_ID=educatief-epd-local
OIDC_RP_CLIENT_SECRET=<waarde van EPD_OIDC_CLIENT_SECRET>
OIDC_OP_AUTHORIZATION_ENDPOINT=http://localhost:9000/application/o/authorize/
OIDC_OP_TOKEN_ENDPOINT=http://host.docker.internal:9000/application/o/token/
OIDC_TOKEN_HOST_HEADER=localhost:9000
OIDC_OP_USER_ENDPOINT=http://host.docker.internal:9000/application/o/userinfo/
OIDC_OP_JWKS_ENDPOINT=http://host.docker.internal:9000/application/o/educatief-epd/jwks/
OIDC_END_SESSION_ENDPOINT=http://localhost:9000/application/o/educatief-epd/end-session/
OIDC_GROUP_CLAIM=groups
OIDC_STUDENT_GROUPS=epd-studenten
OIDC_TEACHER_GROUPS=epd-docenten
OIDC_ADMIN_GROUPS=epd-beheerders
```

Start daarna in `Software` met `docker compose up -d --build web` en open
`http://localhost:8001/accounts/login/`. De eerste aanmelding maakt een lokale
EPD-identiteit aan. De beheerder voegt in het EPD opleidingen en lesgroepen toe en koppelt
studenten en casussen. Een account zonder herkende globale rol krijgt een foutpagina.

De browsercontrole gebruikt een tijdelijke Edge-profielmap en leest de testwachtwoorden
uit de genegeerde `.env` in deze map:

```powershell
node check_oidc.mjs student --logout
node check_oidc.mjs docent
node check_oidc.mjs beheerder
```

Voor de tweede provider verander je in `Software/.env` de issuer naar
`http://localhost:9000/application/o/educatief-epd-alt/`, de client-ID naar
`educatief-epd-alt-local`, het secret naar `EPD_OIDC_SECOND_CLIENT_SECRET` en de JWKS- en
end-session-URL naar de slug `educatief-epd-alt`. Herstart de webcontainer. De overige
identiteits- en rolcode blijft gelijk.

## Lokale noodbeheerder en VIVES

Maak zo nodig een afzonderlijke Django-superuser met `docker compose exec web python
manage.py createsuperuser` in `Software`. `/accounts/noodlogin/` is standaard uit en
accepteert alleen die lokale superuser wanneer `EMERGENCY_LOGIN_ENABLED=1` tijdelijk is
ingeschakeld.

Vraag voor VIVES de precieze issuer, client, callback, UserInfo-claims, groepsnamen en
end-session-URL. Controleer ook dat hun provider-invalidation flow de Authentik-sessie
beëindigt; anders kan een gebruiker na afmelden direct opnieuw via SSO binnenkomen.
Gebruik HTTPS en zet `OIDC_TOKEN_HOST_HEADER` leeg. De lokale testidentiteiten worden
niet gekoppeld aan VIVES-identiteiten op e-mailadres.

Zie de officiële [Docker Compose-installatie](https://docs.goauthentik.io/install-config/install/docker-compose/)
en [logoutconfiguratie](https://docs.goauthentik.io/add-secure-apps/providers/single-logout/).
