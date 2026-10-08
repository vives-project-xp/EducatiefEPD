# AI-toepassingen in EducatiefEPD: implementatieplannen

Dit document beschrijft hoe de voorgestelde AI-toepassingen in de huidige Django-applicatie kunnen worden gebouwd. Het is een stappenplan, geen beschrijving van reeds aanwezige AI-functionaliteit.

## Bestaande onderdelen waarop de plannen aansluiten

- `Software/dossier/models.py` bevat onder andere `Case`, `StudentCase`, `AssignmentSubmission`, `ModuleResponse`, `LibraryTemplate` en `AuditEvent`.
- `Software/dossier/views.py` bevat de schermlogica en rolcontroles, waaronder `require_teacher`, `editable_case` en `teacher_student_case`.
- `Software/dossier/urls.py` bevat de routes voor dossiers, docentenschermen en de casusbibliotheek.
- `Software/dossier/services.py` bevat bestaande domeinservices, zoals `audit`.
- De templates staan in `Software/templates/dossier/`; relevante voorbeelden zijn `teacher_student_case.html`, `library_detail.html` en `case_detail.html`.
- `Software/config/settings.py`, `Software/.env.example` en `Software/compose.yaml` zijn de configuratiepunten voor omgevingsinstellingen.
- `Software/dossier/tests.py` bevat de bestaande Django-workflowtests.

Bestanden hieronder met **nieuw** zijn voorstellen en bestaan nog niet. Voeg niet alle functies tegelijk toe. Kies één toepassing, implementeer en test die, en hergebruik daarna de AI-basis voor volgende toepassingen.

## Gedeelde basis voor AI-functies

1. **Kies en beoordeel een AI-aanbieder.** Bepaal of gegevens de applicatie mogen verlaten, welke bewaartermijnen gelden en of een verwerkersovereenkomst nodig is. Begin voor de eerste tests met fictieve gegevens en leg het besluit vast in `Documentatie/AI toepassingen.md`.
2. **Voeg configuratie toe.** Zet bijvoorbeeld `AI_ENABLED`, `AI_API_KEY`, `AI_MODEL` en `AI_TIMEOUT_SECONDS` in `Software/.env.example`, lees die instellingen in `Software/config/settings.py` en geef ze door aan de webservice in `Software/compose.yaml`. Geef de API-sleutel via `.env` of een secrets manager door; commit nooit echte sleutels.
3. **Maak een afgeschermde AI-client.** Maak `Software/dossier/ai/__init__.py` en `Software/dossier/ai/client.py`; laat de client alleen expliciet geselecteerde context versturen, time-outs gebruiken en fouten duidelijk doorgeven. Voeg alleen indien nodig een SDK toe aan `Software/requirements.txt`. Log geen API-sleutels, volledige prompts of persoonsgegevens.
4. **Maak gedeelde prompt- en validatielogica.** Definieer vaste instructies in `Software/dossier/ai/prompts.py` en controleer het verwachte formaat met validators in `Software/dossier/ai/schemas.py` voordat resultaten worden getoond.
5. **Behoud autorisatie in Django.** Controleer rol en dossierrechten in de betreffende view in `Software/dossier/views.py` met de bestaande helpers en registreer de endpoint in `Software/dossier/urls.py`. De AI-client mag nooit zelf bepalen of een gebruiker een dossier mag zien.
6. **Toon resultaten als concept.** Render AI-uitvoer vanuit de betreffende view in een template onder `Software/templates/dossier/` en schrijf die niet automatisch naar `AssignmentSubmission`, `ModuleResponse` of bestaande feedback. Voeg pas een model en migratie toe via `Software/dossier/models.py` en `Software/dossier/migrations/` als opslag en bewaarbeleid expliciet zijn afgesproken.
7. **Voeg tests en audit toe.** Vervang externe AI-calls met `unittest.mock.patch` in `Software/dossier/tests.py` en test toegangscontrole, lege context, ongeldige AI-uitvoer, providerfouten en audit. Gebruik `Software/dossier/services.py` voor de bestaande auditservice en bewaar geen volledige gevoelige context in `AuditEvent.details`; wijzig `Software/dossier/models.py` alleen als de auditstructuur moet veranderen.

---

## 1. Een dossier automatisch samenvatten

**Doel:** een docent krijgt een beknopt overzicht van een ingediende fictieve studentcasus.

1. Maak in `Software/dossier/ai/summaries.py` een functie die voor één `StudentCase` relevante antwoorden omzet naar beperkte, gelabelde tekst; haal die antwoorden uit de modellen in `Software/dossier/models.py` en sluit lege of irrelevante velden uit.
2. Voeg in `Software/dossier/views.py` een login-beveiligde POST-view toe die `require_teacher` en `editable_case` gebruikt om docenttoegang te controleren.
3. Registreer de POST-route in `Software/dossier/urls.py` en plaats de CSRF-beveiligde knop in `Software/templates/dossier/teacher_student_case.html`.
4. Definieer de vaste samenvattingsonderdelen in `Software/dossier/ai/prompts.py` en valideer de output via `Software/dossier/ai/schemas.py`; laat `Software/dossier/ai/summaries.py` geen feiten toevoegen en iedere bewering aan een dossieronderdeel koppelen.
5. Toon het resultaat als AI-concept in `Software/templates/dossier/teacher_student_case.html`, verwerk het resultaat in `Software/dossier/views.py` en voeg tests voor docenttoegang, studentenweigering, AI-fouten en ongewijzigde brongegevens toe aan `Software/dossier/tests.py`.

## 2. Een tijdlijn opbouwen

**Doel:** gebeurtenissen uit de casus in chronologische volgorde tonen, met herkomstinformatie.

1. Definieer in `Software/dossier/ai/timelines.py` welke bronnen gebeurtenissen opleveren; gebruik daarvoor onder meer opdrachtinzendingen en gedateerde velden van de modellen in `Software/dossier/models.py`.
2. Bouw in `Software/dossier/ai/timelines.py` tijdlijnitems met expliciete bronverwijzing en datum uit gestructureerde velden. Laat de prompt in `Software/dossier/ai/prompts.py` AI alleen vrije tekst omzetten, nooit ontbrekende datums raden.
3. Valideer datums, sorteer items en groepeer onzekere datums in `Software/dossier/ai/timelines.py`; wijzig datumvelden in `Software/dossier/models.py` alleen als de bestaande velden niet volstaan.
4. Voeg de login-beveiligde view toe in `Software/dossier/views.py`, registreer de route in `Software/dossier/urls.py` en toon de tijdlijn met bronverwijzingen in `Software/templates/dossier/teacher_student_case.html`.
5. Voeg tests voor sortering, ontbrekende/foutieve datums, bronverwijzingen en toegang toe in `Software/dossier/tests.py` en test de tijdlijnlogica in `Software/dossier/ai/timelines.py`.

## 3. Ontbrekende of tegenstrijdige registraties signaleren

**Doel:** mogelijke onvolledigheden en inconsistenties zichtbaar maken zonder gegevens automatisch te wijzigen.

1. Implementeer deterministische controles in `Software/dossier/ai/consistency.py` en gebruik daarvoor `ModuleResponse.schema` en `ModuleResponse.data` zoals gedefinieerd in `Software/dossier/models.py`.
2. Voeg in `Software/dossier/ai/consistency.py` optionele AI-analyse toe voor mogelijke tegenstrijdigheden; definieer beperkte context en bronverwijzingen in `Software/dossier/ai/prompts.py` en valideer de resultaten met `Software/dossier/ai/schemas.py`.
3. Valideer output in `Software/dossier/ai/consistency.py` en presenteer resultaten als controleerbare signalen via `Software/dossier/views.py` en de relevante template onder `Software/templates/dossier/`; pas niets automatisch aan.
4. Toon signalen in de bevoegde view/template en registreer de controle via `audit` in `Software/dossier/services.py` zonder dossierinhoud in auditdetails. `AuditEvent` staat al in `Software/dossier/models.py`.
5. Voeg tests voor normale, ontbrekende en tegenstrijdige registraties, foutieve AI-output en toegangscontrole toe aan `Software/dossier/tests.py` en test de controles in `Software/dossier/ai/consistency.py`.

## 4. Reflectievragen genereren

**Doel:** een student krijgt vragen die diens eigen reflectie op een oefencasus verdiepen.

1. Bepaal in `Software/dossier/views.py` en aan de hand van de modellen in `Software/dossier/models.py` welke opdracht/casus en leerdoelen als context zijn toegestaan.
2. Maak in `Software/dossier/ai/reflection.py` een generator voor een beperkt aantal open vragen, schrijf de instructies in `Software/dossier/ai/prompts.py` en valideer de uitvoer met `Software/dossier/ai/schemas.py`.
3. Voeg de POST-view met `get_student_case`-toegangscontrole toe aan `Software/dossier/views.py` en registreer de endpoint in `Software/dossier/urls.py`.
4. Toon vragen als oefenhulp in `Software/templates/dossier/case_detail.html` of `Software/templates/dossier/dossier.html`; sla ze niet op als formele antwoorden in `Software/dossier/models.py`, tenzij expliciete opslag wordt ontworpen.
5. Voeg tests voor casustoegang, lege leerdoelen en providerfouten toe aan `Software/dossier/tests.py` en test de generator in `Software/dossier/ai/reflection.py`.

## 5. Feedback op een fictieve casus geven

**Doel:** formatieve feedback bieden zonder een cijfer of formeel docentenoordeel te genereren.

1. Definieer met docenten een rubric zonder formele score en leg criteria vast in `Documentatie/AI toepassingen.md`; valideer de rubric eventueel met een schema in `Software/dossier/ai/schemas.py`.
2. Beperk toepassing in `Software/dossier/views.py` tot een fictieve eigen casus en selecteer uit `Software/dossier/models.py` alleen het antwoord, de opdrachtinstructie en leerdoelen.
3. Maak de feedbackgenerator in `Software/dossier/ai/formative_feedback.py`, zet instructies in `Software/dossier/ai/prompts.py` en valideer output met `Software/dossier/ai/schemas.py`.
4. Toon output afzonderlijk van formele docentfeedback in `Software/templates/dossier/case_detail.html` of `Software/templates/dossier/teacher_student_case.html`, verwerkt via `Software/dossier/views.py`; schrijf niet naar `AssignmentSubmission.feedback` in `Software/dossier/models.py`.
5. Test dat formele feedback niet wordt overschreven en controleer inzendstatus en rechten met tests in `Software/dossier/tests.py` en de autorisatie in `Software/dossier/views.py`.

## 6. Ruwe aantekeningen herschrijven

**Doel:** een gebruiker kan een eigen tekstvoorstel laten ordenen of verduidelijken.

1. Kies geschikte velden en rollen aan de hand van `Software/dossier/models.py` en `Software/dossier/views.py` en leg de scope vast in `Documentatie/AI toepassingen.md`.
2. Voeg in `Software/dossier/views.py` een POST-view toe, registreer die in `Software/dossier/urls.py` en zorg dat de aangeleverde tekst niet automatisch wordt opgeslagen.
3. Maak `Software/dossier/ai/rewrites.py` en definieer in `Software/dossier/ai/prompts.py` dat alleen taal, structuur of toon aangepast mag worden; feiten, datums en onzekerheden blijven behouden.
4. Toon origineel en voorstel in `Software/templates/dossier/dossier.html` of `Software/templates/dossier/_dynamic_fields.html`, met verwerking van overnemen/bewerken/verwerpen in `Software/dossier/views.py`.
5. Test CSRF, roltoegang, lege tekst en behoud van origineel in `Software/dossier/tests.py` en `Software/dossier/ai/rewrites.py`.

## 7. Een interactieve casussimulatie aanbieden

**Doel:** de student oefent een gesprek in een fictieve situatie met AI als gesprekspartner.

1. Definieer scenario, rol, doel, context en stopvoorwaarden voor fictieve casussen op basis van bestaand materiaal in `Software/dossier/models.py`; zet scenario-instructies in `Software/dossier/ai/simulations.py`.
2. Bouw een begrensde gespreksturn-functie in `Software/dossier/ai/simulations.py` en laat die de gedeelde client in `Software/dossier/ai/client.py` gebruiken.
3. Maak de schermlogica in `Software/dossier/views.py`, registreer POST-routes in `Software/dossier/urls.py` en voeg het gespreksscherm toe als `Software/templates/dossier/simulation.html`.
4. Toon feedback als oefenmateriaal in `Software/templates/dossier/simulation.html`. Als gesprekken bewaard worden, definieer dan een model in `Software/dossier/models.py`, maak een migratie onder `Software/dossier/migrations/` en leg het bewaarbeleid vast.
5. Test isolatie, maximale lengte, providerfouten en bronafbakening in `Software/dossier/tests.py` en `Software/dossier/ai/simulations.py`.

## 8. Varianten van bestaande casussen maken

**Doel:** docenten laten een fictieve casus als concept uitbreiden of aanpassen.

1. Voeg de docentactie en doel-/niveauselectie toe aan `Software/templates/dossier/teacher_case.html` en behandel de invoer in `Software/dossier/views.py`.
2. Genereer een voorstel met fictieve details in `Software/dossier/ai/case_variants.py`; definieer de prompt in `Software/dossier/ai/prompts.py` en haal toegestane bronvelden uit `Software/dossier/models.py`.
3. Toon het verschil in `Software/templates/dossier/ai_case_variant.html` en sla pas na goedkeuring als nieuwe conceptcasus op via `Software/dossier/views.py` en de modellen in `Software/dossier/models.py`.
4. Voorkom automatische publicatie of groepskoppeling met controles in `Software/dossier/views.py`, `Software/dossier/models.py` en de routeconfiguratie in `Software/dossier/urls.py`.
5. Test behoud van originele inhoud, docentrollen en conceptzichtbaarheid in `Software/dossier/tests.py` en `Software/dossier/views.py`.

## 9. Vragen stellen over goedgekeurd lesmateriaal

**Doel:** antwoorden geven op basis van controleerbare bronnen uit de casusbibliotheek.

1. Bepaal met de modellen in `Software/dossier/models.py` en de toegangslogica in `Software/dossier/views.py` welke bibliotheekitems goedgekeurd en roltoegankelijk zijn.
2. Implementeer passagezoeking, eventueel eerst eenvoudige tekstzoeking, in `Software/dossier/ai/retrieval.py` en `Software/dossier/ai/library_search.py`.
3. Geef uitsluitend gevonden passages mee via `Software/dossier/ai/library_search.py`, definieer bronverwijzingen in `Software/dossier/ai/prompts.py` en valideer ze in `Software/dossier/ai/schemas.py`; geef geen antwoord zonder bron.
4. Voeg de vraagview toe aan `Software/dossier/views.py`, registreer de route in `Software/dossier/urls.py` en maak het vraag-/antwoordscherm in `Software/templates/dossier/library_assistant.html`, eventueel bereikbaar vanuit `Software/templates/dossier/library_list.html`.
5. Test archivering, toegangsrechten en bronverwijzingen in `Software/dossier/tests.py` en `Software/dossier/ai/retrieval.py`.

## 10. Vervolgstappen bij een oefencasus verkennen

**Doel:** meerdere mogelijke onderzoeksvragen of acties verkennen bij een fictieve casus.

1. Beperk de functie tot fictieve oefencasussen en expliciete selectie in `Software/templates/dossier/case_detail.html`; controleer de toegang in `Software/dossier/views.py` en gebruik de casusmodellen uit `Software/dossier/models.py`.
2. Vraag om meerdere opties, afwegingen en ontbrekende informatie in de prompt in `Software/dossier/ai/prompts.py`; genereer en valideer ze via `Software/dossier/ai/next_steps.py` en `Software/dossier/ai/schemas.py`.
3. Presenteer de resultaten als brainstorm in `Software/templates/dossier/ai_next_steps.html` en geef ze door vanuit `Software/dossier/views.py`.
4. Houd de functie apart met een eigen route in `Software/dossier/urls.py` en view in `Software/dossier/views.py`; schrijf niet automatisch naar `Software/dossier/models.py` of een actieplan.
5. Test lege context, fouten, roltoegang en markering als AI-suggestie in `Software/dossier/tests.py` en `Software/dossier/ai/next_steps.py`.

## 11. Les- en beoordelingsmateriaal voorbereiden

**Doel:** docenten conceptvragen, voorbeeldantwoorden of rubricvoorstellen laten maken.

1. Maak in `Software/templates/dossier/ai_teaching_material.html` een docentenscherm voor leerdoel, materiaaltype, doelgroep en niveau en koppel dit aan een view in `Software/dossier/views.py` met een route in `Software/dossier/urls.py`.
2. Genereer één materiaaltype per verzoek in `Software/dossier/ai/teaching_material.py` en valideer het formaat met `Software/dossier/ai/schemas.py`.
3. Toon de uitvoer als bewerkbaar concept in `Software/templates/dossier/ai_teaching_material.html` en sla die pas na docentcontrole op via `Software/dossier/views.py` en, indien bibliotheekopslag wordt toegevoegd, `Software/dossier/models.py`.
4. Voeg indien nodig velden toe aan `Software/dossier/models.py` en maak de bijbehorende migratie in `Software/dossier/migrations/`.
5. Test roltoegang, publicatie en conceptzichtbaarheid met tests in `Software/dossier/tests.py` en controles in `Software/dossier/views.py`.

## 12. Teksten begrijpelijker maken

**Doel:** uitleg of lesmateriaal laten herschrijven op een gekozen taalniveau.

1. Voeg de actie en niveauselectie voor goedgekeurde teksten toe aan `Software/templates/dossier/library_detail.html` en verwerk de aanvraag in `Software/dossier/views.py`.
2. Stuur alleen tekst en niveau vanuit `Software/dossier/ai/plain_language.py` en definieer in `Software/dossier/ai/prompts.py` dat inhoud en waarschuwingen behouden moeten blijven.
3. Toon origineel en voorstel in `Software/templates/dossier/ai_plain_language.html`; sla via `Software/dossier/views.py` en eventueel `Software/dossier/models.py` alleen op na bevestiging.
4. Test vaktermen, lege invoer, speciale tekens en behoud van instructies in `Software/dossier/tests.py` en `Software/dossier/ai/plain_language.py`.
5. Leg de evaluatiecriteria vast in `Documentatie/AI toepassingen.md` en laat docenten output beoordelen vóór studentgebruik; voeg regressietests toe aan `Software/dossier/tests.py`.

## 13. Lesmateriaal vertalen

**Doel:** een docent laten vertalen en controleren van goedgekeurde onderwijsinhoud.

1. Laat de docent brontekst en doeltaal selecteren in `Software/templates/dossier/library_detail.html`, verwerk die keuze in `Software/dossier/views.py` en definieer vaktermen eventueel in `Software/dossier/ai/glossary.py`.
2. Genereer een conceptvertaling met behoud van betekenis en opmaak in `Software/dossier/ai/translations.py` en schrijf de vertaalinstructies in `Software/dossier/ai/prompts.py`.
3. Toon origineel en vertaling naast elkaar in `Software/templates/dossier/ai_translation.html`, gevuld vanuit `Software/dossier/views.py`.
4. Laat de docent expliciet opslaan via `Software/dossier/views.py`; vervang bronmateriaal nooit automatisch in `Software/dossier/models.py`. Maak alleen een migratie onder `Software/dossier/migrations/` als vertalingen structureel worden opgeslagen.
5. Test terminologie, opmaak, vertaalfouten en ongewijzigde bron in `Software/dossier/tests.py` en `Software/dossier/ai/translations.py`.

## 14. Een persoonlijke leerroute voorstellen

**Doel:** een student passende volgende oefeningen laten ontdekken op basis van leerdoelen en eigen voortgang.

1. Bepaal toegestane voortgangsvelden in `Software/dossier/models.py` en selecteer die in `Software/dossier/views.py`; sluit dossiers en docentnotities uit.
2. Genereer aanbevelingen uit gepubliceerde, toegankelijke casussen in `Software/dossier/ai/learning_path.py` en definieer de prompt in `Software/dossier/ai/prompts.py`.
3. Toon aanbevelingen en reden in `Software/templates/dossier/learning_path.html` of `Software/templates/dossier/home.html`; verwerk accepteren/negeren in `Software/dossier/views.py`.
4. Leg uitsluiting van cijfers, formele voortgangsbesluiten en profilering vast in `Documentatie/AI toepassingen.md` en bewaak die in `Software/dossier/views.py`.
5. Test casustoegang en uitsluiting van verborgen feedback in `Software/dossier/tests.py` en `Software/dossier/ai/learning_path.py`.

## 15. Casussen aan leerdoelen koppelen

**Doel:** docenten helpen casussen aan competenties of leerdoelen te koppelen.

1. Bepaal de bestaande leerdoelopslag en toegestane casusvelden in `Software/dossier/models.py` en controleer de selectie in `Software/dossier/views.py`.
2. Laat AI koppelingen met onderbouwing en passageverwijzingen voorstellen via `Software/dossier/ai/learning_objectives.py`; definieer instructies in `Software/dossier/ai/prompts.py` en validatie in `Software/dossier/ai/schemas.py`.
3. Toon voorstellen aan de bevoegde docent via `Software/dossier/views.py`, registreer de actie in `Software/dossier/urls.py` en voeg de interface toe aan `Software/templates/dossier/teacher_case.html`.
4. Sla alleen bevestigde koppelingen op in `Software/dossier/models.py`; maak daarvoor zo nodig een nieuwe migratie onder `Software/dossier/migrations/`.
5. Test dat AI-voorstellen niet automatisch als gevalideerde data gelden met tests in `Software/dossier/tests.py` en controles in `Software/dossier/views.py`.

## 16. Quizvragen en flashcards maken

**Doel:** oefenmateriaal genereren uit goedgekeurde lesstof.

1. Laat de docent bron, leerdoel, aantal en vraagtype kiezen in `Software/templates/dossier/ai_quiz.html` en verwerk de invoer in `Software/dossier/views.py`.
2. Genereer vragen, antwoorden, uitleg en bronverwijzingen in `Software/dossier/ai/quizzes.py` en valideer het formaat met `Software/dossier/ai/schemas.py`.
3. Toon een preview in `Software/templates/dossier/ai_quiz.html` en laat docentaanpassingen verwerken via `Software/dossier/views.py`.
4. Sla alleen goedgekeurde quizitems op met modellen in `Software/dossier/models.py` en verwerking in `Software/dossier/views.py`; maak indien nodig een migratie onder `Software/dossier/migrations/`.
5. Test antwoordvalidatie, bronnen, inhoudsfouten en verborgen antwoordsleutels in `Software/dossier/tests.py` en `Software/dossier/ai/quizzes.py`.

## 17. Lesmateriaal controleren op duidelijkheid

**Doel:** docenten signalen geven over mogelijk onduidelijke instructies voordat materiaal wordt gepubliceerd.

1. Voeg de docentactie toe in `Software/templates/dossier/library_detail.html`, behandel die in `Software/dossier/views.py` en registreer de route in `Software/dossier/urls.py`.
2. Laat AI mogelijke onduidelijkheden aan concrete passages koppelen in `Software/dossier/ai/material_review.py`; definieer de instructies in `Software/dossier/ai/prompts.py` en de validatie in `Software/dossier/ai/schemas.py`.
3. Toon bevindingen naast de bron in `Software/templates/dossier/ai_material_review.html` en lever ze aan vanuit `Software/dossier/views.py`.
4. Voorkom automatisch herschrijven of publiceren in `Software/dossier/views.py`; bewaar controles apart van bronmateriaal en voeg alleen bij expliciete opslag een modelwijziging toe in `Software/dossier/models.py`.
5. Test passageverwijzingen en foutafhandeling in `Software/dossier/tests.py` en `Software/dossier/ai/material_review.py`.

## Aanbevolen implementatievolgorde

1. Begin met reflectievragen, quizvragen of lesmateriaalcontrole op fictieve/goedgekeurde inhoud en implementeer die in de bijbehorende AI-module onder `Software/dossier/ai/` met een scherm onder `Software/templates/dossier/`.
2. Implementeer configuratie in `Software/.env.example`, `Software/config/settings.py` en `Software/compose.yaml`, de client in `Software/dossier/ai/client.py`, prompts en validatie in `Software/dossier/ai/prompts.py` en `Software/dossier/ai/schemas.py`, en tests in `Software/dossier/tests.py`.
3. Laat docenten output controleren aan de hand van evaluatiecriteria in `Documentatie/AI toepassingen.md`; meet juistheid, bruikbaarheid, fouten en kosten met tests in `Software/dossier/tests.py` en registreer gebruik zo nodig via `Software/dossier/services.py`.
4. Voeg dossierfuncties pas toe na privacy-, autorisatie- en bewaarbeoordeling; werk toegangscontroles bij in `Software/dossier/views.py`, routes in `Software/dossier/urls.py`, configuratie in `Software/.env.example` en alleen bij opslag de modellen in `Software/dossier/models.py`.
5. Houd AI-uitvoer herkenbaar als concept in de relevante templates onder `Software/templates/dossier/`, verwerk ze via `Software/dossier/views.py` en voeg controles toe aan `Software/dossier/tests.py`.

## Validatie na implementatie

Voer vanuit de map `Software` minimaal de relevante tests uit met `docker compose run --rm web python manage.py test dossier`. Dit controleert onder meer `Software/dossier/tests.py`, `Software/config/settings.py` en de aangepaste AI-views en services. Voer daarna `docker compose run --rm web python manage.py check` uit.

```powershell
docker compose run --rm web python manage.py test dossier
docker compose run --rm web python manage.py check
```

Test daarnaast handmatig met een docent, student zonder rechten en fictieve casusdata. Controleer dat ongeldige AI-uitvoer en providerstoringen als fout worden getoond, dat de oorspronkelijke antwoorden intact blijven en dat geen geheime sleutels of volledige persoonsgegevens in logs terechtkomen.
