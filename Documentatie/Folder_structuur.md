# Folderstructuur Educatief EPD

Dit document beschrijft alleen de mappenstructuur van het project
**Educatief EPD**. De volgorde van de inhoudsopgave en de uitleg volgt de
actuele structuur van de folders.

## Inhoudsopgave

- [Folderstructuur Educatief EPD](#folderstructuur-educatief-epd)
  - [Inhoudsopgave](#inhoudsopgave)
  - [Hoofdmap `EducatiefEPD`](#hoofdmap-educatiefepd)
    - [Map `Documentatie`](#map-documentatie)
    - [Map `media`](#map-media)
    - [Map `Software`](#map-software)
      - [Map `authentik`](#map-authentik)
      - [Map `backups`](#map-backups)
      - [Map `config`](#map-config)
      - [Map `docker`](#map-docker)
        - [Map `docker/mysql`](#map-dockermysql)
      - [Map `dossier`](#map-dossier)
        - [Map `dossier/management`](#map-dossiermanagement)
          - [Map `dossier/management/commands`](#map-dossiermanagementcommands)
        - [Map `dossier/migrations`](#map-dossiermigrations)
        - [Gegenereerde map `dossier/__pycache__`](#gegenereerde-map-dossier__pycache__)
      - [Map `static`](#map-static)
      - [Map `templates`](#map-templates)
        - [Map `templates/dossier`](#map-templatesdossier)
        - [Map `templates/registration`](#map-templatesregistration)
      - [Gegenereerde mappen `__pycache__`](#gegenereerde-mappen-__pycache__)
  - [Samenhang tussen de mappen](#samenhang-tussen-de-mappen)

## Hoofdmap `EducatiefEPD`

De hoofdmap is de bovenste map van het project. Vanuit deze map zijn de drie
hoofdonderdelen bereikbaar:

- `Documentatie/`: alle projectdocumentatie;
- `Software/`: de applicatie en technische configuratie;
- `media/`: afbeeldingen en ander visueel projectmateriaal.

De algemene projectbestanden in de hoofdmap vallen buiten dit folderoverzicht.

### Map `Documentatie`

Deze map bevat handleidingen, workflows en andere uitleg over het gebruik,
beheer en ontwerp van het Educatief EPD.

De documentatie is bedoeld voor verschillende doelgroepen, zoals docenten,
beheerders en ontwikkelaars. De map bevat onder andere uitleg over lesgroepen,
dossier-sjablonen, dossierworkflows, AI-toepassingen en deze
folderstructuur.

### Map `media`

Deze map bevat afbeeldingen en ander visueel projectmateriaal, zoals
projectafbeeldingen en een projectposter.

Gebruik in deze map geen vertrouwelijke of herleidbare patiëntgegevens.

### Map `Software`

Deze map bevat de volledige technische implementatie van het Educatief EPD.
De applicatie is opgebouwd met Django, gebruikt MySQL als database, Docker
voor de uitvoeromgeving en Authentik voor OpenID Connect-authenticatie.

De submappen van `Software` worden hieronder in dezelfde volgorde uitgelegd.

#### Map `authentik`

Deze map bevat de lokale configuratie voor Authentik. Authentik verzorgt de
gebruikersaanmelding en de koppeling tussen gebruikersrollen en het EPD via
OpenID Connect.

De map wordt gebruikt voor lokale installatie, configuratie, bootstrap en
controle van de authenticatieomgeving.

#### Map `backups`

Deze map bevat databaseback-ups voor herstel en testdoeleinden.

Back-ups kunnen persoonsgegevens of andere gevoelige informatie bevatten.
Bewaar deze map daarom veilig en deel de inhoud niet zonder toestemming.

#### Map `config`

Deze map bevat de centrale Django-projectconfiguratie. De map koppelt de
applicatie aan de database, authenticatie, templates, statische bestanden en
de uitvoeromgeving.

De map bevat instellingen en routering van het project, maar niet de
specifieke domeinlogica van het EPD.

#### Map `docker`

Deze map bevat aanvullende Docker-configuratie voor infrastructuuronderdelen
van het project.

##### Map `docker/mysql`

Deze submap bevat de Docker-configuratie voor MySQL. De map ondersteunt het
opbouwen van de databasecontainer en het initialiseren van een testdatabase.

#### Map `dossier`

Dit is de belangrijkste Django-applicatiemap van het EPD. Hier bevindt zich
de functionele kern van de applicatie, zoals:

- opleidingen en lesgroepen;
- gebruikersrollen en toegangscontrole;
- studenten, patiënten en casussen;
- basisdossiers en opdrachten;
- beoordelingen en studentversies;
- bibliotheekonderdelen en dossier-sjablonen.

Binnen deze map staan ook de beheercommando's, database-migraties en
automatisch aangemaakte Python-cachebestanden.

##### Map `dossier/management`

Deze map bevat Django-beheerfunctionaliteit die niet rechtstreeks via een
webpagina wordt uitgevoerd.

###### Map `dossier/management/commands`

Deze submap bevat eigen Django-beheercommando's voor onder andere:

- het controleren van de database;
- het initialiseren van het platform;
- het vullen van een lokale omgeving met demogegevens.

De commando's worden uitgevoerd via het centrale Django-beheerprogramma.

##### Map `dossier/migrations`

Deze map bevat de versiegeschiedenis van het datamodel. Iedere migratie
beschrijft een wijziging aan de database, zoals een nieuwe tabel, een veld,
een relatie of een constraint.

De migraties zorgen ervoor dat de database-opbouw overeenkomt met de
datamodellen van de applicatie.

##### Gegenereerde map `dossier/__pycache__`

Deze map wordt automatisch door Python aangemaakt wanneer modules worden
uitgevoerd. De map bevat tijdelijke gecompileerde Python-bestanden.

De inhoud is gegenereerd en hoeft niet handmatig aangepast te worden.

#### Map `static`

Deze map bevat statische bestanden voor de webinterface, zoals styling,
JavaScript en grafische elementen.

De bestanden in deze map worden door de templates gebruikt om pagina's vorm te
geven en interactieve onderdelen te laten werken.

#### Map `templates`

Deze map bevat de HTML-templates van Django. Templates bepalen de structuur
en presentatie van de webpagina's. De views uit de applicatie leveren de
gegevens aan die in deze templates worden weergegeven.

##### Map `templates/dossier`

Deze submap bevat de pagina's van de EPD-applicatie, waaronder:

- het docentdashboard;
- patiëntcasussen en studentdossiers;
- opleidingen en lesgroepen;
- de bibliotheek en dossier-sjablonen;
- modules, velden, opdrachten en beoordelingen.

Ook gedeelde templateonderdelen voor dynamische velden staan in deze map.

##### Map `templates/registration`

Deze submap bevat de templates voor aanmelden en meldingen rond een mislukte
of geweigerde aanmelding.

#### Gegenereerde mappen `__pycache__`

Python maakt automatisch `__pycache__`-mappen aan in folders waarin Python-
modules worden uitgevoerd. Deze mappen bevatten tijdelijke `.pyc`-bestanden.

Ze bevatten geen handmatig geschreven broncode en hoeven niet aangepast te
worden.

## Samenhang tussen de mappen

De folders werken in hoofdlijnen als volgt samen:

1. `config/` verbindt Django met de omgeving en de technische instellingen.
2. `dossier/` bevat de modellen, formulieren, routes en domeinlogica.
3. `templates/` toont de webpagina's van de applicatie.
4. `static/` levert de vormgeving en interactieve onderdelen.
5. `dossier/migrations/` houdt de database-opbouw gelijk aan de modellen.
6. `authentik/` verzorgt de externe aanmelding en rolgegevens.
7. `docker/` ondersteunt een reproduceerbare uitvoeromgeving.
8. `Documentatie/` beschrijft het gebruik en beheer van het systeem.
9. `media/` bevat visueel materiaal buiten de applicatielogica.
