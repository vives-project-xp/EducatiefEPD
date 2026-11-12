# Automatische webdeployments naar de VM

Bij iedere push op `main` draait `.github/workflows/tests.yml` de bestaande tests,
deployregressies en Compose-validatie. Daarna bouwt GitHub het webimage, draait de
Django/MySQL-suite in **dat image**, controleert productie-statics, echte startup
en HTTP/databasehealth, en publiceert
het in `ghcr.io/vives-project-xp/educatiefepd`. Een SSH-job deployt de exacte digest.
PRs krijgen geen deployment. `workflow_dispatch` maakt handmatig starten mogelijk.

De SSH-job wordt pas actief wanneer de repositoryvariabele `DEPLOY_ENABLED` op
`true` staat. Zo kunnen jullie eerst de VM en secrets instellen. Images worden
al gebouwd en gepubliceerd terwijl deployment uitstaat. Er zijn geen repository
Deploy keys nodig en de VM hoeft bij een update geen broncode uit GitHub te halen.

## 1. Voorwaarden en bestaande VM controleren

Deze route gebruikt de door jullie bevestigde **publiek bereikbare SSH-toegang**.
`VM_HOST` is het publieke DNS-adres/IP, niet uitsluitend `10.20.10.36`.
De VM moet uitgaand GHCR kunnen bereiken. De image is Linux/amd64, passend bij de
standaard GitHub Ubuntu-runner; controleer `uname -m` op de VM (`x86_64`).

De Linux-gebruiker, bijvoorbeeld `student`, heeft Python 3, Docker-toegang zonder
sudo en Docker Compose v2 nodig, met ondersteuning voor `up --wait` en
`config --format json`. Gebruik een recente Compose-versie, minimaal 2.24.
Docker en SSH worden door de VM-beheerder beschikbaar gesteld.

Begin vanuit de map waarmee de bestaande EPD-containers gestart zijn:

```sh
cd /home/student/EducatiefEPD/Software  # pas aan aan jullie bestaande locatie
docker compose ps
docker compose version
python3 --version
uname -m

db_id=$(docker compose ps -q db)
web_id=$(docker compose ps -q web)
docker inspect --format '{{index .Config.Labels "com.docker.compose.project"}}' "$db_id"
docker inspect --format '{{range .Mounts}}{{if eq .Destination "/var/lib/mysql"}}{{.Name}}{{end}}{{end}}' "$db_id"
docker inspect --format '{{range .Mounts}}{{if eq .Destination "/app/uploads"}}{{.Source}}{{end}}{{end}}' "$web_id"
docker port "$web_id" 8001
```

Bewaar de gevonden **projectnaam**, **MySQL-volumenaam**, **uploadmap** en
**poortbinding** voor stap 2. Het script vergelijkt opslag met de bestaande
containers en stopt bij een afwijking. Gebruik geen nieuwe projectnaam bij het
overnemen van een draaiende installatie. Dat kan een tweede stack opleveren.

Controleer dat aanmelden, uploads en de browser-URL al werken. De CI/CD-installatie
configureert geen nieuwe Authentik-provider, proxy of certificaten. Met
`DJANGO_DEBUG=0` verwacht de huidige app HTTPS; alleen `SECURE_SSL_REDIRECT=0`
instellen maakt sessiecookies niet geschikt voor HTTP. Een eventueel bestaande
HTTP-testconfiguratie wordt overgenomen, niet automatisch gewijzigd.

## 2. Vaste deploymap op de VM

Maak op de VM een eigen map voor configuratie, deployscript en back-ups:

```sh
install -d -m 700 /home/student/epd-deploy
```

Kopieer vanuit deze repository op je **eigen computer** de drie bestanden. Vervang
`PUBLIEKE_HOST` en indien nodig poort/gebruiker:

```powershell
scp -P 22 Software/deploy/deploy.py Software/deploy/compose.yaml Software/deploy/deploy.example.json student@PUBLIEKE_HOST:/home/student/epd-deploy/
```

Daarna op de **VM**, met het pad naar jullie werkende `.env`:

```sh
umask 077
cp -n /home/student/EducatiefEPD/Software/.env /home/student/epd-deploy/app.env
cd /home/student/epd-deploy
cp -n deploy.example.json deploy.json
chmod 600 app.env deploy.json
nano deploy.json
```

Vul `deploy.json` in:

- `project`: exact de projectnaam uit stap 1, vaak `software`.
- `mysql_volume`: exact het bestaande volume uit stap 1, vaak `software_mysql_data`.
- `media_dir`: de bestaande absolute uploadmap, zonder symlink.
- `web_bind`: de bestaande hostbinding, bijvoorbeeld `0.0.0.0`, `127.0.0.1` of
  het VM-IP. Hostpoort blijft `8001`.
- `health_host`: een host uit `ALLOWED_HOSTS`, zonder protocol, bijvoorbeeld
  `epd.example.be` of `10.20.10.36`. Dit is voor de interne HTTP/DB-check.
- `health_url`: de werkende app-URL met `/health/`, bereikbaar **vanaf de VM**,
  bijvoorbeeld `https://epd.example.be/health/`. Deze moet rechtstreeks HTTP 200
  met `{"status":"ok"}` geven, zonder redirect. Geldige HTTPS-certificaten blijven vereist.
- `image_repository`: `ghcr.io/vives-project-xp/educatiefepd` in kleine letters.

`app.env` bewaart de bestaande DB-/OIDC-instellingen. Wijzig geen databasewachtwoorden
bij deze overgang. Compose neemt de instellingen expliciet over en geeft het
MySQL-rootwachtwoord niet aan de webcontainer. `RUN_MIGRATIONS=0` en `SEED_DEMO=0`
worden voor deployments afgedwongen. Migraties gebeuren in een afzonderlijke stap.

Voor een **lege VM**: richt eerst de app, uploadrechten en Authentik eenmalig in
volgens [DEPLOYMENT.md](DEPLOYMENT.md) en [authentik/README.md](authentik/README.md),
met jullie werkelijke VM-URLs/callbacks. Doorloop daarna bovenstaande overname.
Dit deployscript maakt bewust geen nieuwe database of accounts aan.

## 3. GHCR-toegang op de VM

De workflow publiceert met zijn automatische `GITHUB_TOKEN`; hiervoor voeg je
geen persoonlijk token aan de workflow toe. De organisatie moet pakketpublicatie
toestaan. Bij een bestaand package moet deze repository Actions-toegang hebben.

Een nieuw GHCR-package is standaard privé. Laat het privé en geef de VM toegang
met een **personal access token (classic)** met alleen `read:packages`, van een
account dat het package mag lezen. Autoriseer organisatie-SSO indien vereist.
Op de VM, als dezelfde gebruiker die gaat deployen:

```sh
read -r -p 'GitHub gebruikersnaam: ' gh_user
read -r -s -p 'GHCR token (read:packages): ' ghcr_token
printf '\n'
printf '%s' "$ghcr_token" | docker login ghcr.io -u "$gh_user" --password-stdin
unset ghcr_token
chmod 700 ~/.docker
chmod 600 ~/.docker/config.json
```

Het token blijft op de VM; stuur het niet in chat en zet het niet in `app.env` of
Git. Vernieuw het vóór de vervaldatum. Zonder credential helper bewaart Docker
de login omkeerbaar gecodeerd in de gebruikersconfiguratie.
Als de beheerder het package bewust publiek maakt, kan de VM anoniem pullen.
Zie [GitHub: Container registry](https://docs.github.com/en/packages/working-with-a-github-packages-registry/working-with-the-container-registry).

## 4. Aparte SSH-deploysleutel maken

Op je **eigen computer**, in PowerShell:

```powershell
ssh-keygen -t ed25519 -C "epd-github-actions" -f "$env:USERPROFILE\.ssh\epd-actions"
```

Kies een andere bestandsnaam als die al bestaat; overschrijf geen bestaande sleutel.
Laat de passphrase voor deze afzonderlijke automatiseringssleutel leeg, door bij
beide passphrasevragen Enter te drukken. De workflow gebruikt geen interactieve agent.

- `epd-actions.pub` is de **publieke** sleutel voor de VM.
- `epd-actions` is de **private** sleutel voor het GitHub Actions-secret.
- Geen van beide hoort bij GitHub **Settings → SSH and GPG keys** of **Deploy keys**
  voor deze verbinding: Actions logt ermee in op Linux, niet op GitHub.

Lees op je computer uitsluitend de publieke sleutel:

```powershell
Get-Content "$env:USERPROFILE\.ssh\epd-actions.pub"
```

Log met je bestaande toegang op de VM in en open:

```sh
install -d -m 700 ~/.ssh
touch ~/.ssh/authorized_keys
chmod 600 ~/.ssh/authorized_keys
nano ~/.ssh/authorized_keys
```

Voeg één nieuwe regel toe, zonder bestaande regels te verwijderen:

```text
restrict ssh-ed25519 PLAK_HIER_DE_PUBLIEKE_SLEUTEL epd-github-actions
```

`restrict` schakelt forwarding en interactieve PTY uit, maar laat de remote
deployopdracht toe. Deze sleutel heeft toegang als de gekozen VM-gebruiker;
bewaar de private sleutel uitsluitend lokaal en als Actions-secret. Docker-toegang
geeft ruime rechten op de VM. Een aparte deploygebruiker kan later door de beheerder
worden ingericht als die rechten verder gescheiden moeten worden.

Test vanaf je computer:

```powershell
ssh -T -p 22 -i "$env:USERPROFILE\.ssh\epd-actions" -o IdentitiesOnly=yes student@PUBLIEKE_HOST "python3 --version && docker compose version"
```

## 5. SSH-hostkey vastleggen

De pipeline vertrouwt alleen een vooraf gecontroleerde hostkey, niet een key die
tijdens deployment onbevestigd wordt opgehaald. Op de VM, via je vertrouwde sessie:

```sh
ssh-keygen -lf /etc/ssh/ssh_host_ed25519_key.pub
```

Haal op je computer de publieke key op en vergelijk de **SHA256-fingerprint**:

```powershell
ssh-keyscan -p 22 -t ed25519 PUBLIEKE_HOST 2>$null | Set-Content -Encoding ascii "$env:TEMP\epd-known-hosts"
ssh-keygen -lf "$env:TEMP\epd-known-hosts"
```

Alleen bij dezelfde fingerprint gebruik je de inhoud van `epd-known-hosts` als
`VM_KNOWN_HOSTS`. Gebruik precies dezelfde host en poort als in de workflow.
Bij een afwijkende poort bevat known_hosts `[host]:poort`. Herhaal de verificatie
na een herinstallatie van SSH/VM; schakel hostkeycontrole niet uit.

## 6. GitHub-secrets en inschakelen

Ga naar de **repository** → **Settings → Secrets and variables → Actions**.
Maak onder **Secrets** deze repositorysecrets:

- `VM_HOST`: publiek IP/DNS-adres, zonder `ssh://` of poort.
- `VM_PORT`: bijvoorbeeld `22` (zonder secret gebruikt de workflow ook 22).
- `VM_USER`: bijvoorbeeld `student`.
- `VM_DEPLOY_PATH`: `/home/student/epd-deploy`, absoluut en zonder spaties.
- `VM_SSH_KEY`: volledige inhoud van de private `epd-actions`, inclusief
  `BEGIN OPENSSH PRIVATE KEY` en `END OPENSSH PRIVATE KEY`.
- `VM_KNOWN_HOSTS`: volledige, geverifieerde known_hosts-regel uit stap 5.

Je kunt de private sleutel op je eigen Windows-computer rechtstreeks naar het
klembord kopiëren, zonder hem in chat of terminaluitvoer te zetten:

```powershell
Get-Content -Raw "$env:USERPROFILE\.ssh\epd-actions" | Set-Clipboard
```

Plak in het GitHub-secret en wis daarna het klembord. Voor `VM_KNOWN_HOSTS`:

```powershell
Get-Content -Raw "$env:TEMP\epd-known-hosts" | Set-Clipboard
```

Repositorysecrets vereisen write-toegang bij een organisatierepo of collaborator-
toegang bij een persoonlijke repo. Vraag bij ontbrekende toegang de beheerder om
de instellingen eenmalig te doen. Voor deze workflow hoeft geen GitHub Environment
of self-hosted runner te worden aangemaakt.
Zie [GitHub: Actions-secrets](https://docs.github.com/en/actions/how-tos/write-workflows/choose-what-workflows-do/use-secrets).

Laat de codewijzigingen op `main` terechtkomen. De eerste run kan al een image
publiceren terwijl deployment nog uitstaat. Zet, wanneer VM, registrylogin en
SSH-secrets gereed zijn, onder **Variables** de repositoryvariabele:

```text
DEPLOY_ENABLED = true
```

Ga naar **Actions → Tests → Run workflow → main**. Daarna triggert iedere push op
`main` vanzelf de keten. De bestaande checknamen blijven behouden voor eventuele
branch protection. Bescherm `main` met reviews en vereiste tests, want code op main
kan via deze workflow op de VM worden uitgevoerd.

## 7. Wat gebeurt er tijdens een release?

1. Alleen succesvolle tests kunnen de imagejob vrijgeven. De gepubliceerde digest
   komt van het image waarin ook de Django-tests en `collectstatic` slaagden.
2. GitHub laat één deployjob tegelijk lopen en annuleert geen lopende deploy voor
   een nieuwe push. Een inmiddels achterhaalde main-commit wordt overgeslagen;
   snelle opeenvolgende pushes kunnen zo in één nieuwste deployment samenkomen.
3. De VM neemt een bestandslock en weigert oudere workflowrunnummers. Eenzelfde
   runnummer mag uitsluitend dezelfde commit en digest opnieuw proberen.
4. Controle bestaande opslag en back-updatabasenaam, pull image, controle commitlabel, Django-/databasecheck,
   `collectstatic` en schrijfbaarheid van uploads. Tot hier blijft web draaien.
5. Web stopt tijdelijk. De VM maakt `mysql.sql`, `uploads.tar.gz` en een kopie van
   lokale configuratie in een afgeschermde `backups/<tijd>-<commit>/`.
   `BACKUP_COMPLETE` verschijnt alleen als beide back-upcommando's slaagden.
6. Een tijdelijke container voert `migrate` eenmaal uit. Daarna wordt alleen `web`
   vervangen met `--no-deps --no-build`; de startentrypoint migreert niet opnieuw.
7. De containerhealthcheck controleert HTTP én database. Daarna controleert de VM
   ook `health_url`. Pas dan krijgt `state.json` status `healthy`.

Er is **downtime tijdens back-up, migratie en webstart**. De database blijft draaien;
schrijvers buiten deze webapp moeten tijdens dit onderhoudsvenster eveneens stil
staan. Authentik en zijn gegevens blijven onaangeraakt. Test na de eerste deployment
zelf aanmelden, één casus en een upload; `/health/` bewijst geen werkende OIDC-login.

De vaste VM-bestanden `deploy.py` en `compose.yaml` worden niet via SSH overschreven.
Bij toekomstige wijzigingen aan het deploymentcontract kopieer je die bewust
opnieuw, wanneer geen deployment loopt. `app.env`, `deploy.json`, `state.json` en
back-ups nooit overschrijven met repositoryvoorbeelden.

## 8. Fouten, herstel en back-ups

- **Tests/build/pull/preflight faalt:** bestaande webcontainer blijft beschikbaar.
- **Back-up faalt vóór migratie:** het script start de bestaande webcontainer weer,
  tenzij een eerdere mislukte migratie de schema-compatibiliteit onzeker maakte.
- **Migratie faalt:** bestaande web blijft gestopt; inspecteer de fout en herstel
  met een nieuwe commit. MySQL-schemawijzigingen zijn niet volledig transactioneel.
- **Nieuwe web/health faalt:** workflow faalt, geen automatische database-restore.
  Inspecteer containerstatus/logs, `state.json` en de back-up. De kandidaat kan
  deels draaien; voer bij herstel bewust onderhoud uit.
- **SSH valt weg/job wordt handmatig geannuleerd:** controleer eerst op de VM of
  het proces nog loopt en welke status opgeslagen is. Start geen handmatige
  migratie daarnaast. Het VM-lock voorkomt twee gelijktijdige scriptdeployments.
- **Rerun:** kies na een verbindingsfout bij voorkeur *Re-run failed jobs*, zodat
  dezelfde image-output wordt gebruikt. *Re-run all jobs* bouwt opnieuw; een andere
  digest met hetzelfde runnummer wordt bewust geweigerd. Gebruik dan een nieuwe
  workflow_dispatch/main-run met een hoger runnummer.

Een vorige image terugzetten is alleen verantwoord als het huidige schema daarmee
compatibel is. `state.json` bewaart de vorige succesvolle release en iedere back-up
het oude image-ID. Normaal herstel: een corrigerende main-commit met compatibele
migraties. Verwijder `state.json` niet om een oudere release te forceren.

Voor een noodzakelijke database-restore: blokkeer writes, maak eerst een extra
back-up van de fouttoestand, herstel DB en uploads uit hetzelfde gecontroleerde
back-uppunt en kies de bijpassende applicatieversie. Nieuwe gegevens na het
back-uppunt gaan daarbij verloren; daarom doet het script dit nooit automatisch.
Oefen het herstel eerst op een aparte database volgens [DEPLOYMENT.md](DEPLOYMENT.md).

De lokale releaseback-ups zijn geen bescherming tegen verlies van de VM. Kopieer
ze versleuteld naar opslag buiten de VM, bewaak vrije schijfruimte en spreek een
bewaartermijn af. Authentik/PostgreSQL en Authentik-media vragen een **afzonderlijke**
regelmatige back-up. Het script verwijdert geen oude back-ups of images automatisch.
Gebruik nooit `docker compose down -v` voor deze omgeving.

## Lokale/CI-controles

```sh
python3 -m unittest discover -s Software/deploy/tests -v
python3 Software/deploy/tests/check_compose.py
sh -n Software/entrypoint.sh
```

De regressies simuleren Docker-fouten en controleren dat een opslagwissel,
achterhaalde release, back-upfout, migratiefout en ongezonde nieuwe versie correct
worden afgehandeld. Ze vervangen geen echte VM-/SSH-/back-uphersteltest.
