# Automatische webupdates: de VM haalt releases op

De VM is bereikbaar als `student@10.20.10.36`. Dat is een privéadres; een publieke
SSH-ingang is niet vastgesteld. Daarom haalt de VM zelf releases op bij GHCR.
Deze handleiding vervangt de eerdere SSH-deploymentprocedure.

Bij een push op `main` doet `.github/workflows/tests.yml` het volgende:

1. Bestaande Django/MySQL-tests, JavaScript-controles en deployregressies uitvoeren.
2. Een Linux/amd64-webimage bouwen met commit-, main- en workflowrunnummetadata.
3. De Django/MySQL-suite in datzelfde image draaien, productie-statics verzamelen
   en echte startup plus HTTP/databasehealth controleren.
4. Het geteste image publiceren onder een unieke SHA/run/attempt-tag in GHCR.
5. In een geserialiseerde releasejob de exacte digest promoveren naar het kanaal
   `ghcr.io/vives-project-xp/educatiefepd:main`. Een achterhaalde commit of lager
   runnummer mag een nieuwere release niet overschrijven.

De VM controleert ongeveer iedere minuut het kanaal en deployt alleen een nieuwe
geldige release. Een ongewijzigde gezonde release doet niets. Mislukte tests
publiceren geen nieuwe release naar het kanaal. Snelle pushes kunnen worden
samengenomen: de nieuwste geslaagde, gepromoveerde main-release wordt uitgerold.
Een release die al wordt uitgevoerd, wordt niet afgebroken voor een volgende push.

## Wat is er nog nodig?

- De aangepaste broncode moet op `main` staan en de Actions-workflow moet toegestaan zijn.
- Actions gebruikt automatisch `GITHUB_TOKEN` om images te publiceren. De organisatie
  moet pakketpublicatie toestaan; een bestaand package moet deze repository toegang geven.
- De VM heeft Python >= 3.10, Docker-toegang als `student`, Compose >= 2.24,
  Linux/amd64 en uitgaande toegang tot GHCR nodig.
- Voor een privé-package heeft `student` op de VM een werkende `docker login ghcr.io` nodig.
- Een user-timer voert de poller uit; controleer lingering voor werking na uitloggen/reboot.
  Bij ontbrekende rechten kan een bestaande actieve cronservice de user-crontab uitvoeren.

De SSH-secrets `VM_HOST`, `VM_PORT`, `VM_USER`, `VM_DEPLOY_PATH`, `VM_SSH_KEY`,
`VM_KNOWN_HOSTS` en de repositoryvariabele `DEPLOY_ENABLED` worden niet meer gebruikt.
Je kunt ze verwijderen als ze uitsluitend voor deze oude deploymentroute bedoeld
waren. Verwijder geen persoonlijke SSH-toegang. Het activeren gebeurt op de VM
met `pull.enabled`, niet via een GitHub-secret of repositoryvariabele.

## 1. Bestaande VM-configuratie behouden

De eerder voorbereide map `/home/student/epd-deploy` blijft bruikbaar:

- `app.env`: bestaande werkende DB-/OIDC-/Django-configuratie, rechten 0600.
- `deploy.json`: echte projectnaam, volumenaam, canonieke absolute uploadmap,
  poortbinding, health-host/URL en image-repository, rechten 0600.
- `state.json` en `backups/`: behouden als deze al bestaan.

Volgens het VM-rapport is de projectnaam `software`, het volume
`software_mysql_data`, en de health-URL `http://10.20.10.36:8001/health/`.
De bestaande HTTP-testconfiguratie gebruikt `DJANGO_DEBUG=1` en
`SECURE_SSL_REDIRECT=0`. Dit is een testopstelling; de pullroute wijzigt die
instellingen niet. Voor normaal productiegebruik blijft een correcte HTTPS-
inrichting nodig. Zet DEBUG niet aan om fouten te verbergen.

Controleer werkelijke mountnamen en paden wanneer je configuratie afwijkt.
`media_dir` moet absoluut en canoniek zijn; alleen `uploads` is ongeldig.
Het script weigert een andere databasevolume-/uploadmount of databasenaam dan
de bestaande installatie. Maak voor deze overgang geen nieuwe opslag aan.

Uploadrechten moeten de containergebruiker toegang geven. Het eerdere VM-rapport
noemt `o+w` op twee directories; vervang dat waar mogelijk door gerichte eigenaar-,
groep- of ACL-rechten. Voer geen brede recursieve chmod/chown uit.

Voor een nog lege VM: installeer eerst de app en Authentik volgens
[DEPLOYMENT.md](DEPLOYMENT.md) en [authentik/README.md](authentik/README.md).
De pullroute vereist een bestaande draaiende database en maakt geen accounts aan.

## 2. Nieuwe scripts naar de VM kopiëren

Gebruik bestanden uit de aangepaste checkout. Stop eerst een eventuele bestaande
pulltimer en laat een lopende release afronden voordat je scripts vervangt.
Dit betreft geen webcontainerherstart.

Vanuit PowerShell op je eigen computer, in de repositoryroot:

```powershell
scp Software/deploy/deploy.py Software/deploy/poll.py Software/deploy/compose.yaml Software/deploy/epd-pull.service Software/deploy/epd-pull.timer Software/deploy/epd-pull.cron student@10.20.10.36:/home/student/epd-deploy/
```

Dit gebruikt jouw gewone SSH-toegang op het schoolnetwerk/VPN. GitHub heeft deze
verbinding niet nodig. Bestaande `app.env`, `deploy.json`, `state.json`,
`pull-state.json` en back-ups nooit overschrijven met voorbeelden.

Op de VM als `student`:

```sh
chmod 700 /home/student/epd-deploy
chmod 600 /home/student/epd-deploy/app.env /home/student/epd-deploy/deploy.json
python3 -m py_compile /home/student/epd-deploy/deploy.py /home/student/epd-deploy/poll.py
```

Voor de VM-AI staat een volledige installatieopdracht in
[VM-PULL-PROMPT.md](VM-PULL-PROMPT.md).

## 3. GHCR-login controleren

Gebruik de bestaande login als die al is uitgevoerd. Anders maak je in je
persoonlijke GitHub-account een personal access token **classic** met
`read:packages`, van een account dat het package mag lezen. Autoriseer organisatie-
SSO indien vereist. Daarna op de VM als `student`:

```sh
read -r -p 'GitHub gebruikersnaam: ' gh_user
read -r -s -p 'GHCR token: ' ghcr_token
printf '\n'
printf '%s' "$ghcr_token" | docker login ghcr.io -u "$gh_user" --password-stdin
unset ghcr_token
chmod 700 ~/.docker
chmod 600 ~/.docker/config.json
```

Voer iedere `read`-regel uit en vul het antwoord in wanneer de terminal erom vraagt.
De tokeninvoer is onzichtbaar. Het token hoort niet in chat, Git of `app.env`.
Een credential helper moet ook zonder interactieve desktopontgrendeling werken
voor de user-service. Zonder helper is de Docker-configuratie omkeerbaar gecodeerd;
beperk de bestandsrechten. Een publiek package kan anoniem worden opgehaald.
Zie [Docker pull](https://docs.docker.com/reference/cli/docker/image/pull/) en
[GitHub GHCR](https://docs.github.com/en/packages/working-with-a-github-packages-registry/working-with-the-container-registry).

## 4. Eerst een geteste release publiceren en controleren

Laat de aangepaste code via jullie normale proces op `main` terechtkomen.
Open **GitHub → EducatiefEPD → Actions → Tests → Run workflow → main**.
Laat alle jobs slagen, inclusief **Publish main release channel for VM**.
Hiervoor stel je geen VM-secrets of `DEPLOY_ENABLED` in.

Voer vervolgens op de VM uit:

```sh
cd /home/student/epd-deploy
python3 poll.py --check
```

Dit haalt het image op en controleert digest, platform, bronrepository, main-label,
commit en runnummer. Het verandert geen containers, database of deploymentstatus.
`deploy` in de uitvoer betekent dat een nieuwe release klaarstaat; het is in deze
checkmodus nog geen daadwerkelijke deployment. `current` betekent dat die release
al gezond is uitgerold; `needs_retry` vraagt onderzoek van een eerdere poging.
De lockfile en Docker-imagecache mogen wel ontstaan of bijgewerkt worden.

`manifest unknown` of `:main: not found` kan betekenen dat het kanaal nog niet gepubliceerd is. `unauthorized`
of `denied` wijst op login-/pakketrechten. Geen credentials of netwerkinstellingen
wijzigen om deze fouten te verbergen; onderzoek eerst de betreffende GitHub-job/login.

## 5. Timer installeren en werking na uitloggen vaststellen

De meegeleverde units gebruiken `%h/epd-deploy` en `/usr/bin/python3`. Controleer
dat die overeenkomen met de werkelijke gebruiker en Python-locatie; pas alleen
die paden aan indien nodig. Installeer als `student`:

```sh
install -d -m 700 ~/.config/systemd/user
install -m 600 /home/student/epd-deploy/epd-pull.service ~/.config/systemd/user/epd-pull.service
install -m 600 /home/student/epd-deploy/epd-pull.timer ~/.config/systemd/user/epd-pull.timer
systemctl --user daemon-reload
systemd-analyze --user verify ~/.config/systemd/user/epd-pull.service ~/.config/systemd/user/epd-pull.timer
loginctl show-user student --property=Linger --value
```

De laatste opdracht moet voor een blijvende inrichting `yes` geven. Bij `no`
moet de school-/VM-beheerder eenmalig onderstaande opdracht uitvoeren:

```sh
loginctl enable-linger student
```

Daarmee kan de user-manager bij boot starten en na uitloggen blijven draaien.
Ga niet uit van sudo-rechten voor `student`. Zonder lingering kun je testen zolang
de gebruikerssessie actief is, maar noem de installatie dan nog niet permanent.
Bij `Failed to connect to bus` ontbreekt een bruikbare systemd-gebruikerssessie;
laat de beheerder die herstellen in plaats van de timer als root te installeren.
Zie [systemd timers](https://www.freedesktop.org/software/systemd/man/latest/systemd.timer.html)
en [loginctl lingering](https://www.freedesktop.org/software/systemd/man/latest/loginctl.html).

### Alternatief zonder lingering: bestaande cronservice

Als lingering niet beschikbaar is en `student` geen beheerrechten heeft, kun je
dezelfde poller vanuit een **user-crontab** draaien, mits cron al actief is en
user-crontabs toegestaan zijn. Controleer `command -v crontab` en
`systemctl is-active cron` (op sommige distributies heet de service `crond`).
Ontbreekt of draait cron niet, laat de beheerder één van beide schedulers mogelijk
maken. Installeer niet stilzwijgend een extra systeemdienst.

Gebruik óf cron óf de systemd-timer. Pauzeer nieuwe starts en laat een eventuele
lopende deploy afronden voordat je wisselt. Maak een afgeschermde back-up van de
bestaande `crontab -l`; bewaar alle bestaande taken. Open daarna `crontab -e` en
voeg de ene taakregel uit `epd-pull.cron` toe. De template veronderstelt
`/home/student/epd-deploy` en `/usr/bin/python3`; controleer die paden.
Gebruik niet `crontab epd-pull.cron`, want dat zou andere bestaande taken vervangen.

De taak draait iedere minuut, ook na uitloggen en na boot zodra cron actief is.
Dezelfde lokale vlag, VM-lock en statuscontrole beschermen de uitvoering.
Controleer dat de cronservice voor boot ingeschakeld is; een echte herstart is
zonder aparte test geen bewezen rebootcontrole. Logging staat bij deze variant in
`/home/student/epd-deploy/pull.log`; bewaak de bestandsgrootte en bewaartermijn.
Zie de [Debian crontab-handleiding](https://manpages.debian.org/trixie/cron/crontab.5.en.html).

## 6. Automatische updates activeren

Deze stap kan de eerste echte deployment en downtime starten. Voer hem uit wanneer
de check in stap 4 slaagt, de bestaande opslag klopt en het onderhoudsvenster past.

Voor de systemd-variant:

```sh
cd /home/student/epd-deploy
touch pull.enabled
chmod 600 pull.enabled
systemctl --user enable --now epd-pull.timer
systemctl --user start epd-pull.service
systemctl --user status epd-pull.timer --no-pager
journalctl --user -u epd-pull.service -n 100 --no-pager
```

De eerste controle is na ongeveer 30 seconden, daarna ongeveer 60 seconden na het
eindigen van de vorige controle/deployment. Handmatig `start epd-pull.service`
start direct een controle; systemd start geen tweede instantie als die al loopt.
De poller en handmatige deployer gebruiken bovendien dezelfde VM-lock.

Voor de cronvariant: installeer de ene user-crontaak, maak `pull.enabled` met 0600
en controleer na de volgende minuut `tail -n 100 ~/epd-deploy/pull.log`. Je kunt
ook meteen `python3 ~/epd-deploy/poll.py` uitvoeren; de lock voorkomt overlap.

Controleer na de eerste release: `state.json` heeft status `healthy`, de health-URL
geeft HTTP 200, en aanmelden, een casus openen en een upload werken. De tests op
`/health/` bewijzen op zichzelf geen werkende OIDC-login of volledige casusflow.

## 7. Onderhoud, pauzeren en herstel

Pauzeren zonder een lopende migratie af te breken:

```sh
rm -f /home/student/epd-deploy/pull.enabled
systemctl --user disable --now epd-pull.timer
```

Stop hierbij niet de `.service` als die aan het deployen is. Laat de lopende
release afronden; een volgende poll slaat over zolang het vlagbestand ontbreekt.
Activeer opnieuw met de opdrachten uit stap 6.
Bij cron is het verwijderen van `pull.enabled` voldoende om volgende deploys te
pauzeren; verwijder desgewenst alleen de EPD-regel uit de crontab, niet andere taken.

De releaseprocedure blijft: bestaande opslag/databasekeuze controleren, image pull
en commitlabelcontrole, Django/databasecheck, collectstatic en uploadrechten;
daarna webstop, consistente DB-/uploadsback-up, migratie eenmaal, alleen web
vervangen en interne plus externe HTTP/databasehealth controleren. Er is downtime
tijdens back-up/migratie/start. Andere schrijvers moeten ook stil staan. Authentik
wordt niet opnieuw ingericht of herstart.

`state.json` bewaart de daadwerkelijke deploystatus, vorige image en back-uplocatie.
`pull-state.json` onthoudt de laatste poging. Een mislukte of afgebroken release
wordt **niet iedere minuut opnieuw gemigreerd**. Na diagnose kun je, met
`pull.enabled` aanwezig, expliciet opnieuw proberen:

```sh
python3 /home/student/epd-deploy/poll.py --retry
```

Een nieuwe release met een hoger runnummer mag normaal verder. Een lager runnummer
wordt genegeerd; gewijzigde inhoud onder hetzelfde runnummer wordt geweigerd.
Publiceer bij zo'n conflict een nieuwe workflow_dispatch/main-run, geen herbouw
onder hetzelfde reeds gebruikte runnummer. Verwijder de statusbestanden niet om
deze bescherming te omzeilen.

Bij register-/netwerkfouten blijft de app zoals hij was en probeert de volgende
timer opnieuw contact. Bij een back-upfout vóór migratie start de oude container
weer, behalve na een eerdere onzekere schemawijziging. Na migratiefouten of een
ongezonde nieuwe versie gebeurt geen blinde rollback of automatische DB-restore.
Onderzoek logs/status en publiceer een passende reparatie.

Releaseback-ups bevatten MySQL, uploads en lokale configuratie; bewaar ze ook
versleuteld buiten de VM, bewaak schijfruimte en oefen herstel op een aparte DB.
Authentik/PostgreSQL/media vragen afzonderlijke back-ups. Oude images en back-ups
worden niet automatisch verwijderd. Gebruik nooit `docker compose down -v`.
Zie [DEPLOYMENT.md](DEPLOYMENT.md) voor herstelcontroles.

De vaste deployscripts/Compose worden niet door applicatie-updates overschreven.
Bij een nieuw deploymentcontract installeer je die bewust opnieuw nadat een
eventuele lopende release is afgerond, met behoud van lokale config/status/back-ups.

## Controles voor deze code

```sh
python3 -m unittest discover -s Software/deploy/tests -v
python3 Software/deploy/tests/check_compose.py
sh -n Software/entrypoint.sh
```

Regressies controleren opslagbehoud, migratie-/healthfouten, kanaalpromotievolgorde,
digestselectie, metadata, pauzeren, herhaalde pogingen en expliciete retry. Dat is
geen bewijs van een echte GHCR-publicatie, permanente VM-timer of back-uprestore;
die controles moeten bij installatie daadwerkelijk uitgevoerd worden.
