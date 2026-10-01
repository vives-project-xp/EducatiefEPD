# Handleiding Educatief EPD

## Aanmelden en rollen

Open `/accounts/login/` en meld aan via Authentik. Een account heeft een van de
geconfigureerde globale groepen nodig: student, docent of EPD-beheerder. Bij meerdere
groepen krijgt beheerder voorrang op docent en docent op student. De EPD-rol wordt bij de
volgende login bijgewerkt. EPD-beheerders gebruiken de beheerschermen in de applicatie;
de Django-admin is uitsluitend voor een afzonderlijke lokale noodbeheerder.

Authentik beheert accounts, wachtwoorden en globale rolgroepen. Het EPD beheert
opleidingen, lesgroepen, studenten in lesgroepen en casustoewijzingen.

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
