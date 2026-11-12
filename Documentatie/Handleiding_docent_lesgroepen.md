# Handleiding docent: lesgroepen maken

In deze handleiding staat stap voor stap welke acties een docent uitvoert om een
lesgroep aan te maken en studenten toegang te geven tot de juiste casussen.

## Vooraf controleren

Controleer voordat je begint:

- Je bent aangemeld in het Educatief EPD als **docent**.
- De juiste **opleiding** bestaat al.
- Iedere student die je wilt toevoegen heeft zich minimaal één keer aangemeld
  via Authentik. Alleen daarna is de student bekend in het EPD.
- De casus die je aan de groep wilt koppelen hoort bij dezelfde opleiding als de
  lesgroep.

Een docent kan alleen eigen lesgroepen beheren. Een EPD-beheerder kan ook
lesgroepen van andere docenten beheren.

## Stappenplan

### 1. Open Lesgroepen

1. Open het **Docentdashboard**.
2. Klik bovenaan op **Lesgroepen**.
3. Controleer of je al een bestaande groep kunt gebruiken. Maak alleen een
   nieuwe groep als dat nodig is.
4. Klik op **Lesgroep toevoegen**.

### 2. Maak de lesgroep aan

Vul het formulier in:

1. Vul bij **Groepsnaam** een herkenbare naam in, bijvoorbeeld
   `Vroedkunde jaar 2 - groep A`.
2. Kies bij **Opleiding** de opleiding waarvoor de groep les krijgt.
3. Klik op **Bewaren**.

De docent wordt automatisch als verantwoordelijke docent opgeslagen. Na het
bewaren opent de detailpagina van de nieuwe lesgroep.

> **Let op:** een docent kan bij het aanmaken alleen een opleiding kiezen
> waarvoor die docent lesgroepen mag beheren. Een beheerder kan daarnaast de
> verantwoordelijke docent kiezen.

### 3. Voeg studenten toe

1. Open op de detailpagina de sectie **Student toevoegen**.
2. Kies bij **Student** de student.
3. Controleer de naam en het e-mailadres.
4. Klik op **Toevoegen**.
5. Herhaal deze stappen voor iedere student.

De toegevoegde studenten verschijnen bovenaan in de tabel **Studenten**. Daar
zie je ook hun e-mailadres.

Een student verschijnt alleen in de keuzelijst wanneer die student:

- de rol **student** heeft;
- zich al minstens één keer via Authentik heeft aangemeld; en
- bij dezelfde opleiding hoort of nog geen opleiding heeft.

Heeft een student nog geen opleiding, dan koppelt het EPD die student bij het
toevoegen automatisch aan de opleiding van de lesgroep.

### 4. Controleer de groepsleden

Controleer in de tabel **Studenten** of alle gewenste studenten zijn toegevoegd.
Staat een student er niet tussen, controleer dan of de student al een eerste
login heeft uitgevoerd en of de juiste rol en opleiding zijn ingesteld.

Een student verwijderen:

1. Zoek de student in de tabel.
2. Klik op **Verwijderen**.

Verwijderen uit de lesgroep trekt de toegang tot casussen die aan deze groep
zijn gekoppeld in. Bestaande studentdossiers blijven bewaard.

### 5. Wijs casussen toe aan de lesgroep

Studenten zien een casus pas wanneer de casus aan hun lesgroep is toegewezen.

1. Ga terug naar het **Docentdashboard**.
2. Open de gewenste patiëntcasus.
3. Controleer of de casus bij dezelfde opleiding hoort als de lesgroep.
4. Ga naar **Toegang voor lesgroepen**.
5. Vink de lesgroep(en) aan die toegang moeten krijgen.
6. Klik op **Toewijzing bewaren**.

Bij iedere lesgroep staat tussen haakjes hoeveel studenten eraan gekoppeld zijn.
Selecteer alleen groepen waarvoor de casus bedoeld is.

### 6. Publiceer de casus

Een casus moet gepubliceerd zijn voordat studenten ermee kunnen werken.

1. Controleer in de casus of het basisdossier en de opdrachten klaar zijn.
2. Klik op **Publiceren**.
3. Controleer of de status verandert naar **Gepubliceerd**.

Studenten in de geselecteerde lesgroep kunnen de casus nu openen. Een student
die de casus niet ziet, controleer je op drie punten:

1. De student is lid van de juiste lesgroep.
2. De lesgroep is geselecteerd bij **Toegang voor lesgroepen**.
3. De casus heeft de status **Gepubliceerd**.

## Een bestaande lesgroep wijzigen

Open **Lesgroepen**, klik op de gewenste groep en kies **Groepsgegevens
bewerken**. Je kunt de groepsnaam en opleiding aanpassen.

Wijzig de opleiding alleen wanneer:

- alle gekoppelde casussen bij de nieuwe opleiding horen; en
- alle studenten met een al ingestelde opleiding bij de nieuwe opleiding horen.

Het EPD blokkeert de wijziging wanneer hier nog niet aan is voldaan. Verplaats
eerst de betreffende casussen of studenten.

## Een lesgroep verwijderen

Verwijder een lesgroep alleen wanneer deze niet meer nodig is:

1. Open de lesgroep.
2. Klik op **Lesgroep verwijderen**.
3. Bevestig de waarschuwing.

Door verwijderen worden de lesgroep, de groepsleden en de koppelingen met
casussen losgekoppeld. Studenten verliezen daarmee direct toegang via deze
groep. Bestaande studentdossiers worden niet verwijderd.

## Korte eindcontrole

Gebruik na het inrichten deze controle:

- [ ] De lesgroep heeft een duidelijke naam.
- [ ] De juiste opleiding is gekozen.
- [ ] Alle studenten hebben eerst ingelogd en zijn toegevoegd.
- [ ] De juiste casus is aan de lesgroep toegewezen.
- [ ] De casus heeft de status **Gepubliceerd**.
- [ ] Een teststudent kan de casus terugvinden en openen.