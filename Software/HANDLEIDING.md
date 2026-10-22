# Handleiding Educatief EPD

## Aanmelden en rollen

Open `/accounts/login/` en meld aan via Authentik. Een account heeft een van de
geconfigureerde globale groepen nodig: student, docent of EPD-beheerder. Bij meerdere
groepen krijgt beheerder voorrang op docent en docent op student. De EPD-rol wordt bij de
volgende login bijgewerkt. EPD-beheerders gebruiken de beheerschermen in de applicatie;
de Django-admin is uitsluitend voor een afzonderlijke lokale noodbeheerder.

Authentik beheert accounts, wachtwoorden en globale rolgroepen. Het EPD beheert
opleidingen, lesgroepen, studenten in lesgroepen en casustoewijzingen.

## Nieuwe gebruikers en rollen via Authentik

Het EPD bepaalt de applicatierol uit de Authentik-groepen van de gebruiker:

- `epd-studenten`: student, na aanmelden naar **Mijn casussen** op `/`.
- `epd-docenten`: docent, na aanmelden naar het **Docentdashboard** op `/docent/`.
- `epd-beheerders`: EPD-beheerder, docentdashboard met aanvullende beheermogelijkheden.

Gebruik hiervoor de **Groups**-tab van een gebruiker. Authentiks **Roles**-tab beheert
rechten binnen Authentik zelf; alleen een rol met de naam student of docent daar
aanmaken levert geen EPD-rol op. De EPD-groepen hoeven geen Authentik-superuserrechten
te krijgen. Zie [Authentik-rollen](https://docs.goauthentik.io/users-sources/roles/).

### Een nieuwe student of docent toevoegen

1. Open de lokale [Authentik-beheerinterface](http://localhost:9000/if/admin/) en
   meld aan als Authentik-beheerder.
2. Ga naar **Directory > Users**, kies **New User > Internal User** en maak de
   gebruiker aan met een unieke gebruikersnaam. Vul desgewenst naam en e-mail in.
3. Open de gebruiker. Stel via **Reset password** de aanmeldgegevens in, of gebruik
   de uitnodigings-/herstelprocedure wanneer die in deze Authentik-omgeving is ingericht.
4. Open de tab **Groups**, kies **Add to existing group** en voeg de gebruiker toe
   aan `epd-studenten` of `epd-docenten`.
5. Laat de gebruiker aanmelden via [het EPD](http://localhost:8001/accounts/login/).
   Bij de eerste geslaagde aanmelding maakt het EPD automatisch het lokale account
   en profiel aan en opent de juiste kant van de applicatie.

Deze gebruikers- en groepshandelingen staan in
[Authentiks gebruikershandleiding](https://docs.goauthentik.io/users-sources/user/user_basic_operations).
Je hoeft het nieuwe account of de globale rol niet daarnaast in Django-admin aan te maken.

### Toegang tot casussen na de eerste login

De Authentik-groep geeft de applicatierol. De inhoudstoegang regel je vervolgens in het EPD:

- Voeg een nieuwe student na de eerste login toe aan een **Lesgroep** en wijs de
  gewenste gepubliceerde casussen aan die lesgroep toe.
- Een docent beheert eigen lesgroepen en casussen. Voor een nieuwe casus moet de
  docent een lesgroep beheren binnen de gekozen opleiding.

Een student kan dus de studentkant openen terwijl **Mijn casussen** nog leeg is.
Controleer in dat geval de lesgroep en casustoewijzing.

### Een bestaande rol veranderen

Pas het groepslidmaatschap in Authentik aan en laat de gebruiker afmelden en opnieuw
aanmelden bij het EPD. De nieuwe rol wordt bij die aanmelding verwerkt; een reeds
lopende EPD-sessie wordt door deze implementatie niet meteen opnieuw op groepen gecontroleerd.

Verwijder bij een rolwissel de oude EPD-groep als die niet meer nodig is. Bij meerdere
EPD-groepen geldt **beheerder > docent > student**. Zonder herkende EPD-groep wordt
de volgende aanmelding geweigerd.

## EPD-beheerder

1. Open **Opleidingen** op het docentdashboard en voeg een opleiding toe. Vroedkunde is
   al aanwezig na de migratie.
2. Open **Lesgroepen**, maak een groep aan binnen een opleiding en kies een
   verantwoordelijke docent.
3. Voeg studenten toe nadat zij zich minstens eenmaal via Authentik hebben aangemeld.
   Het EPD toont enkel studenten van de juiste opleiding of zonder opleiding.
4. Open een casus en selecteer bij **Toegang voor lesgroepen** de groepen die deze casus
   mogen openen. Zonder toewijzing ziet een student de casus niet.

Een groepsverwijdering trekt de toegang van de student direct in. Bestaande antwoorden
blijven bewaard voor de docent. Een docent kan alleen eigen groepen beheren; een
EPD-beheerder kan alle groepen en casussen beheren.

## Docent

1. Maak een patiënt en casus aan binnen een opleiding waarvoor je een lesgroep beheert.
2. Vul het basisdossier en de opdrachten in. Gebruik de bibliotheek om herbruikbare
   onderdelen aan de casus toe te voegen.
3. Publiceer de casus en wijs haar toe aan één of meer van je lesgroepen.
4. Bekijk per student het eigen dossier en beoordeel ingediende opdrachten. De
   bibliotheek en de casusstructuur kunnen later veranderen zonder reeds gestarte
   studentdossiers te wijzigen.

## Bibliotheek beheren

Docenten en EPD-beheerders kunnen in **Bibliotheek** alle dossiermodules, vragenlijsten
en matrices bewerken, ook de vaste standaardmodules. Kies **Bewerk** om de instellingen
en de onderdelen te openen. Per veld kun je het type, de opties en de volgorde aanpassen,
een veld toevoegen of **Verwijderen** kiezen.

Met **Verwijderen** op een bibliotheekkaart of **Uit bibliotheek verwijderen** in de
editor haal je het onderdeel uit de actieve bibliotheek. Het wordt gearchiveerd en niet
meer aan nieuwe casussen toegevoegd. Bestaande casuskopieën en studentdossiers blijven
behouden. Hernoemde modules en verwijderde velden worden bij een herstart niet teruggezet.
De instelling om een template automatisch aan nieuwe casussen toe te voegen blijft bij
de EPD-beheerder.

## Student

Open **Mijn casussen**. Alleen gepubliceerde of eerder gestarte casussen die aan een
huidige lesgroep zijn toegewezen, zijn toegankelijk. Bij de eerste start ontstaat een
persoonlijke kopie. Vul de velden in, bewaar antwoorden en dien opdrachten in. Iedere
student heeft een afzonderlijk dossier.

## Problemen met aanmelden

Een pagina **Geen toegang tot het EPD** betekent dat de aanmelding mislukte of de
Authentik-account geen herkende EPD-groep heeft. Vraag de beheerder de groepsclaim en
groepsnamen te controleren. Bij IdP-uitval kan een lokale superuser tijdelijk via
`/accounts/noodlogin/` aanmelden als `EMERGENCY_LOGIN_ENABLED=1`; zet die instelling
na herstel terug op `0`.

Zie [DEPLOYMENT.md](DEPLOYMENT.md) voor installatie en back-ups en
[authentik/README.md](authentik/README.md) voor de lokale identity-provider.
