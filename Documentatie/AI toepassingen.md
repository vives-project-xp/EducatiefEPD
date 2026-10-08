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

1. **Kies en beoordeel een AI-aanbieder.** Bepaal of gegevens de applicatie mogen verlaten, welke bewaartermijnen gelden en of een verwerkersovereenkomst nodig is. Begin voor de eerste tests met fictieve gegevens.
2. **Voeg configuratie toe.** Zet bijvoorbeeld `AI_ENABLED`, `AI_API_KEY`, `AI_MODEL` en `AI_TIMEOUT_SECONDS` in `Software/.env.example` en lees die in `Software/config/settings.py`. Geef de API-sleutel via `.env` of een secrets manager door; commit nooit echte sleutels.
3. **Maak een afgeschermde AI-client.** Voeg `Software/dossier/ai/__init__.py` en `Software/dossier/ai/client.py` toe. De client verstuurt alleen expliciet geselecteerde context, gebruikt time-outs en geeft fouten duidelijk door aan de applicatie. Log geen API-sleutels, volledige prompts of persoonsgegevens.
4. **Maak gedeelde prompt- en validatielogica.** Voeg `Software/dossier/ai/prompts.py` en `Software/dossier/ai/schemas.py` toe. Definieer per taak een vaste instructie en controleer AI-antwoorden op het verwachte formaat voordat ze worden getoond.
5. **Behoud autorisatie in Django.** De AI-client mag nooit zelf bepalen of een gebruiker een dossier mag zien. De view controleert eerst de rol en toegang met de bestaande helpers in `Software/dossier/views.py`.
6. **Toon resultaten als concept.** Schrijf AI-uitvoer niet automatisch in `AssignmentSubmission`, `ModuleResponse` of bestaande feedback. Toon de tekst eerst ter controle. Voeg pas opslag toe als daarvoor een expliciet model en bewaarbeleid zijn afgesproken.
7. **Voeg tests en audit toe.** Gebruik `unittest.mock.patch` om externe AI-calls in tests te vervangen. Test toegangscontrole, lege context, ongeldige AI-uitvoer, providerfouten en de auditgebeurtenis. Bewaar geen volledige gevoelige context in `AuditEvent.details`.

---

## 1. Een dossier automatisch samenvatten

**Doel:** een docent krijgt een beknopt overzicht van een ingediende fictieve studentcasus.

**Bestanden:** bestaand `Software/dossier/models.py`, `Software/dossier/views.py`, `Software/dossier/urls.py`, `Software/templates/dossier/teacher_student_case.html`, `Software/dossier/tests.py`; nieuw `Software/dossier/ai/summaries.py` en eventueel `Software/templates/dossier/ai_summary.html`.

1. Voeg in `summaries.py` een functie toe die voor één `StudentCase` de relevante antwoorden uit `assignment_submissions` en `module_responses` omzet naar beperkte, gelabelde tekst. Sluit lege velden en irrelevante gegevens uit.
2. Maak in `views.py` een login-beveiligde POST-view voor het aanvragen van een samenvatting. Controleer `require_teacher`, laad de studentcasus en controleer met `editable_case` of de docent toegang heeft tot de bijbehorende casus.
3. Voeg in `urls.py` bijvoorbeeld `docent/studentdossier/<int:student_case_id>/ai/samenvatting/` toe en plaats in `teacher_student_case.html` een CSRF-beveiligde knop.
4. Vraag de AI om vaste onderdelen terug te geven, zoals kern van de casus, belangrijkste observaties, acties, hiaten en vragen voor bespreking. Vraag om geen feiten toe te voegen en iedere bewering aan een dossieronderdeel te koppelen.
5. Toon het resultaat op hetzelfde docentenscherm als AI-concept. Test docenttoegang, weigering voor studenten, AI-fouten en dat de oorspronkelijke antwoorden niet wijzigen.

## 2. Een tijdlijn opbouwen

**Doel:** gebeurtenissen uit de casus in chronologische volgorde tonen, met herkomstinformatie.

**Bestanden:** bestaand `models.py`, `views.py`, `urls.py`, `teacher_student_case.html`, `tests.py`; nieuw `Software/dossier/ai/timelines.py` en eventueel `Software/templates/dossier/ai_timeline.html`.

1. Definieer in `timelines.py` welke bronnen gebeurtenissen kunnen opleveren, zoals opdrachtinzendingen en gedateerde velden in module-antwoorden.
2. Bouw eerst tijdlijnitems met expliciete bronverwijzing en datum uit gestructureerde velden. Laat AI alleen vrije tekst helpen omzetten naar neutrale korte beschrijvingen; laat het geen ontbrekende datums raden.
3. Valideer iedere datum en sorteer items in Django. Plaats onvolledige of onzekere datums in een aparte groep, bijvoorbeeld “Datum onbekend”.
4. Voeg een login-beveiligde docentroute toe in `urls.py` en een weergave in `teacher_student_case.html`. Toon bij elk item een link of verwijzing naar het oorspronkelijke dossieronderdeel.
5. Test chronologische sortering, ontbrekende datums, foutieve datums, bronverwijzingen en toegang tot andermans casussen.

## 3. Ontbrekende of tegenstrijdige registraties signaleren

**Doel:** mogelijke onvolledigheden en inconsistenties zichtbaar maken zonder gegevens automatisch te wijzigen.

**Bestanden:** bestaand `models.py`, `views.py`, `urls.py`, `teacher_student_case.html`, `tests.py`; nieuw `Software/dossier/ai/consistency.py`.

1. Begin in `consistency.py` met deterministische controles voor ontbrekende verplichte velden en datums. Gebruik daarvoor `ModuleResponse.schema` en `ModuleResponse.data` waar mogelijk.
2. Voeg optioneel AI-analyse toe voor mogelijke inhoudelijke tegenstrijdigheden. Geef alleen relevante, beperkte tekstfragmenten mee en vraag om twee concrete bronverwijzingen per mogelijke tegenspraak.
3. Valideer de output en presenteer elk resultaat als “te controleren signaal”, niet als vastgestelde fout. Bied geen automatische correctie aan.
4. Toon signalen op het bevoegde dossier- of docentenscherm. Registreer in `AuditEvent` dat de controle is uitgevoerd, maar zet geen volledige dossierinhoud in de auditdetails.
5. Test correcte registraties, ontbrekende velden, foutieve AI-output, fout-positieven en toegangscontrole.

## 4. Reflectievragen genereren

**Doel:** een student krijgt vragen die diens eigen reflectie op een oefencasus verdiepen.

**Bestanden:** bestaand `models.py`, `views.py`, `urls.py`, `case_detail.html`, `tests.py`; nieuw `Software/dossier/ai/reflection.py` en eventueel `Software/templates/dossier/ai_reflection.html`.

1. Koppel de functie aan één bestaande opdracht of casus en bepaal de context uit de gepubliceerde casus en relevante leerdoelen.
2. Voeg in `reflection.py` een generator toe die een beperkt aantal open vragen oplevert, bijvoorbeeld over onderbouwing, alternatieven, signalen en vervolgstappen.
3. Voeg een POST-route toe die alleen toegankelijk is voor een student die via `get_student_case` toegang heeft tot de casus. Vermijd generatie voor een niet-toegankelijke of ongepubliceerde casus.
4. Toon vragen als oefenhulp en sla ze niet op in het formele antwoordveld. Als de student ze later wil bewaren, laat die dat expliciet doen.
5. Test toegang tot toegewezen casussen, lege leerdoelen en providerfouten.

## 5. Feedback op een fictieve casus geven

**Doel:** formatieve feedback bieden zonder een cijfer of formeel docentenoordeel te genereren.

**Bestanden:** bestaand `models.py`, `views.py`, `urls.py`, `case_detail.html`, `teacher_student_case.html`, `tests.py`; nieuw `Software/dossier/ai/formative_feedback.py` en eventueel `Software/templates/dossier/ai_feedback.html`.

1. Definieer samen met docenten een rubric met criteria zoals analyse, onderbouwing en volledigheid. Gebruik geen rubric die automatisch een formele score bepaalt.
2. Laat de student de functie alleen op een fictieve, eigen casus of inzending toepassen. Verzamel uitsluitend het betreffende antwoord, de opdrachtinstructie en de leerdoelen.
3. Voeg een generator toe die per criterium sterke punten, vragen en verbeterkansen geeft, met verwijzingen naar concrete passages.
4. Toon de uitvoer als “AI-oefenfeedback” en houd deze apart van `AssignmentSubmission.feedback`, dat de docent gebruikt voor formele feedback.
5. Test dat AI-feedback geen bestaande docentfeedback overschrijft en dat niet-ingediende of niet-toegankelijke inzendingen volgens de afgesproken regels worden behandeld.

## 6. Ruwe aantekeningen herschrijven

**Doel:** een gebruiker kan een eigen tekstvoorstel laten ordenen of verduidelijken.

**Bestanden:** bestaand `views.py`, `urls.py`, `dossier.html`, `_dynamic_fields.html`, `tests.py`; nieuw `Software/dossier/ai/rewrites.py` en eventueel `Software/templates/dossier/ai_rewrite.html`.

1. Kies eerst welke tekstvelden geschikt zijn en voor welke rollen de actie beschikbaar wordt.
2. Voeg een POST-endpoint toe dat de tekst uit het formulier gebruikt, maar het oorspronkelijke veld niet opslaat of overschrijft.
3. Laat `rewrites.py` alleen taal, structuur of toon aanpassen. Geef expliciet mee dat feiten, datums en onzekerheden ongewijzigd moeten blijven.
4. Toon origineel en voorstel naast elkaar met knoppen om het voorstel over te nemen, verder te bewerken of te verwerpen. De gebruiker bevestigt zelf het opslaan via het bestaande formulier.
5. Test CSRF, roltoegang, lege tekst en dat de oorspronkelijke registratie gelijk blijft wanneer het voorstel wordt verworpen.

## 7. Een interactieve casussimulatie aanbieden

**Doel:** de student oefent een gesprek in een fictieve situatie met AI als gesprekspartner.

**Bestanden:** bestaand `models.py`, `views.py`, `urls.py`, `tests.py`; nieuw `Software/dossier/ai/simulations.py`, `Software/templates/dossier/simulation.html` en, als gesprekken bewaard worden, een modelwijziging in `models.py` plus een Django-migratie.

1. Definieer een simulatiescenario met rol, doel, toegestane achtergrondinformatie en stopvoorwaarden. Begin met docent-goedgekeurde fictieve casussen.
2. Bouw in `simulations.py` een gespreksturn-functie met begrensde gesprekslengte en alleen context van dat scenario.
3. Maak scherm en POST-routes voor starten, antwoorden en afronden. Controleer dat de student de gekozen casus mag gebruiken.
4. Toon na afloop reflectie of feedback als oefenmateriaal. Sla het gesprek niet op als reguliere dossierregistratie; als opslag nodig is, maak een expliciet model met bewaartermijn en verwijderoptie.
5. Test sessie-isolatie tussen studenten, maximale lengte, providerfouten en dat geen gegevens uit andere casussen in het gesprek verschijnen.

## 8. Varianten van bestaande casussen maken

**Doel:** docenten laten een fictieve casus als concept uitbreiden of aanpassen.

**Bestanden:** bestaand `models.py`, `views.py`, `urls.py`, `teacher_case.html`, `tests.py`; nieuw `Software/dossier/ai/case_variants.py` en eventueel `Software/templates/dossier/ai_case_variant.html`.

1. Voeg alleen voor docenten een actie toe op de casusbeheerpagina en laat de docent doel en moeilijkheidsgraad kiezen.
2. Genereer een voorstel op basis van casusinhoud en leerdoelen. Vraag om uitsluitend fictieve details toe te voegen en geen bestaande feiten stilzwijgend te veranderen.
3. Toon verschil tussen origineel en variant. Schrijf de variant pas na expliciete goedkeuring als nieuwe `Case` op, of als concept volgens het bestaande statusmodel.
4. Zorg dat varianten niet automatisch gepubliceerd of aan studentgroepen toegewezen worden.
5. Test dat de originele casus ongewijzigd blijft, alleen bevoegde docenten varianten maken en concepten niet zichtbaar zijn voor studenten.

## 9. Vragen stellen over goedgekeurd lesmateriaal

**Doel:** antwoorden geven op basis van controleerbare bronnen uit de casusbibliotheek.

**Bestanden:** bestaand `models.py`, `views.py`, `urls.py`, `library_list.html`, `tests.py`; nieuw `Software/dossier/ai/library_search.py`, `Software/dossier/ai/retrieval.py` en `Software/templates/dossier/library_assistant.html`.

1. Bepaal welke bibliotheekitems goedgekeurd en door de rol van de gebruiker toegankelijk zijn. Begin met tekst uit `LibraryTemplate` en bijbehorende velden.
2. Implementeer zoeken naar relevante passages. Voor een eerste versie kan eenvoudige tekstzoeking volstaan; embeddings of een vectorstore zijn een aparte latere keuze.
3. Geef alleen gevonden passages aan de AI en vraag om bronverwijzingen. Als geen bruikbare passages bestaan, laat de assistent aangeven dat er geen bron is.
4. Voeg een vraagformulier toe aan de bibliotheek en toon antwoord met links naar de gebruikte items.
5. Test dat gearchiveerde of niet-toegestane items niet in antwoorden terechtkomen en dat bronverwijzingen correct zijn.

## 10. Vervolgstappen bij een oefencasus verkennen

**Doel:** meerdere mogelijke onderzoeksvragen of acties verkennen bij een fictieve casus.

**Bestanden:** bestaand `views.py`, `urls.py`, `case_detail.html`, `tests.py`; nieuw `Software/dossier/ai/next_steps.py` en eventueel `Software/templates/dossier/ai_next_steps.html`.

1. Beperk deze functie tot fictieve oefencasussen en laat de gebruiker expliciet een casus selecteren.
2. Vraag de AI om meerdere opties, de onderliggende redenatie en welke informatie nog ontbreekt. Vraag niet om één definitieve instructie.
3. Presenteer de uitkomst als brainstorm met waarschuwing dat de student bronnen en leerstof moet raadplegen.
4. Gebruik een eigen view en templatefragment; schrijf de suggesties niet automatisch naar het dossier of een actieplan.
5. Test lege context, onverwachte AI-uitvoer, roltoegang en duidelijke markering als AI-suggesties.

## 11. Les- en beoordelingsmateriaal voorbereiden

**Doel:** docenten conceptvragen, voorbeeldantwoorden of rubricvoorstellen laten maken.

**Bestanden:** bestaand `views.py`, `urls.py`, `library_detail.html`, `tests.py`; nieuw `Software/dossier/ai/teaching_material.py` en `Software/templates/dossier/ai_teaching_material.html`.

1. Maak een docentenscherm waarin de docent leerdoel, materiaaltype, doelgroep en niveau selecteert.
2. Genereer één materiaaltype per verzoek en valideer de uitvoer op formaat, bijvoorbeeld vraag plus antwoord plus bron of rubriccriterium.
3. Toon alles als concept met bewerkfunctionaliteit. Sla pas na controle op in een passend bibliotheekitem; publiceer niet automatisch.
4. Voeg zo nodig aparte velden toe aan modellen; maak de migratie met `python manage.py makemigrations dossier` en controleer die vóór toepassing.
5. Test dat studenten geen materiaal kunnen genereren of publiceren en dat conceptmateriaal niet openbaar wordt.

## 12. Teksten begrijpelijker maken

**Doel:** uitleg of lesmateriaal laten herschrijven op een gekozen taalniveau.

**Bestanden:** bestaand `views.py`, `urls.py`, `library_detail.html`, `tests.py`; nieuw `Software/dossier/ai/plain_language.py` en `Software/templates/dossier/ai_plain_language.html`.

1. Voeg een actie toe op geselecteerde goedgekeurde instructies of casusbeschrijvingen, met een beperkt aantal taalniveaus.
2. Stuur alleen de geselecteerde tekst en het niveau; vraag om betekenis, vakinhoud en waarschuwingen niet weg te laten.
3. Toon origineel en aangepaste tekst naast elkaar. Houd de aangepaste variant tijdelijk of sla die alleen op na bevestiging door de docent.
4. Test vaktermen, lege invoer, HTML/speciale tekens en behoud van belangrijke instructies.
5. Laat docenten representatieve output beoordelen voordat studenten deze functie gebruiken.

## 13. Lesmateriaal vertalen

**Doel:** een docent laten vertalen en controleren van goedgekeurde onderwijsinhoud.

**Bestanden:** bestaand `views.py`, `urls.py`, `library_detail.html`, `tests.py`; nieuw `Software/dossier/ai/translations.py` en `Software/templates/dossier/ai_translation.html`.

1. Laat een docent brontekst en doeltaal selecteren. Definieer waar nodig een gecontroleerde lijst met vaktermen.
2. Genereer een conceptvertaling met behoud van opmaak, betekenis en onzekerheden. Laat AI geen ontbrekende inhoud aanvullen.
3. Toon vertaling en origineel naast elkaar en vermeld taal/model of generatieversie volgens het bewaarbeleid.
4. Publiceer of vervang origineel nooit automatisch; laat de docent expliciet opslaan als vertaalde versie.
5. Test termenlijst, opmaak, fouten in vertaling en dat de brontekst onveranderd blijft.

## 14. Een persoonlijke leerroute voorstellen

**Doel:** een student passende volgende oefeningen laten ontdekken op basis van leerdoelen en eigen voortgang.

**Bestanden:** bestaand `models.py`, `views.py`, `urls.py`, `home.html`, `tests.py`; nieuw `Software/dossier/ai/learning_path.py` en eventueel `Software/templates/dossier/learning_path.html`.

1. Bepaal welke voortgangsvelden relevant en toegestaan zijn; stuur geen volledige dossiers of docentnotities mee.
2. Genereer aanbevelingen uitsluitend uit beschikbare, gepubliceerde casussen en expliciete leerdoelen.
3. Toon per suggestie waarom die wordt aanbevolen en laat de student kiezen. Bied een optie om de aanbeveling te negeren.
4. Gebruik aanbevelingen niet voor cijfers, studievoortgangsbesluiten, selectie of automatische profilering.
5. Test dat aanbevelingen alleen verwijzen naar casussen waartoe de student toegang heeft en dat geen verborgen docentfeedback wordt gebruikt.

## 15. Casussen aan leerdoelen koppelen

**Doel:** docenten helpen casussen aan competenties of leerdoelen te koppelen.

**Bestanden:** bestaand `models.py`, `views.py`, `urls.py`, `teacher_case.html`, `tests.py`; nieuw `Software/dossier/ai/learning_objectives.py`.

1. Bepaal waar leerdoelen nu worden opgeslagen en welke bestaande casusvelden als context mogen worden gebruikt.
2. Laat AI mogelijke koppelingen met onderbouwing en verwijzing naar relevante casuspassages voorstellen.
3. Toon voorstellen aan de bevoegde docent en laat die bevestigen, verwijderen of wijzigen.
4. Sla alleen bevestigde koppelingen op. Als de huidige modellen geen relatie ondersteunen, voeg die toe in `models.py` en maak een gecontroleerde migratie.
5. Test dat AI-voorstellen niet automatisch als gevalideerde curriculumdata worden behandeld.

## 16. Quizvragen en flashcards maken

**Doel:** oefenmateriaal genereren uit goedgekeurde lesstof.

**Bestanden:** bestaand `models.py`, `views.py`, `urls.py`, `library_detail.html`, `tests.py`; nieuw `Software/dossier/ai/quizzes.py` en `Software/templates/dossier/ai_quiz.html`.

1. Laat de docent bronmateriaal, leerdoel, aantal vragen en vraagtype selecteren.
2. Laat AI vragen, antwoorden, uitleg en bronverwijzingen in een vast JSON-formaat opleveren; valideer dit met `ai/schemas.py`.
3. Toon vragen als preview en laat een docent dubbelzinnige of foutieve vragen aanpassen.
4. Voeg goedgekeurde quizitems toe aan een aparte oefenmodule of bestaand opdrachtmodel. Publiceer ze niet zonder expliciete docentactie.
5. Test antwoordvalidatie, bronverwijzingen, inhoudelijke fouten en dat studenten de antwoordsleutel niet vóór het beantwoorden zien.

## 17. Lesmateriaal controleren op duidelijkheid

**Doel:** docenten signalen geven over mogelijk onduidelijke instructies voordat materiaal wordt gepubliceerd.

**Bestanden:** bestaand `views.py`, `urls.py`, `library_detail.html`, `tests.py`; nieuw `Software/dossier/ai/material_review.py` en `Software/templates/dossier/ai_material_review.html`.

1. Voeg een docentactie toe om een conceptinstructie of bibliotheekitem te controleren.
2. Vraag AI om concrete passages te markeren met het mogelijke probleem en een suggestie, bijvoorbeeld ontbrekende stap, onverklaarde vakterm of dubbelzinnige formulering.
3. Toon bevindingen naast de bron en laat de docent zelf wijzigingen aanbrengen.
4. Start geen automatische herschrijving of publicatie. Bewaar eventuele controle-uitvoer apart van de gepubliceerde brontekst.
5. Test dat ieder signaal naar een bestaande passage verwijst en dat fouten van de AI de bewerkingspagina niet blokkeren.

## Aanbevolen implementatievolgorde

1. Begin met reflectievragen, quizvragen of het controleren van lesmateriaal op fictieve of goedgekeurde inhoud.
2. Implementeer eerst de gedeelde configuratie, AI-client, validatie en tests; kies daarna één toepassing als proef.
3. Laat docenten output controleren en meet feitelijke juistheid, bruikbaarheid, foutmeldingen en kosten.
4. Voeg pas daarna functies toe die studentdossiers verwerken. Controleer eerst privacy, toegangsrechten, bewaartermijnen en afspraken met de AI-aanbieder.
5. Houd AI-uitvoer steeds herkenbaar als gegenereerd concept. De gebruiker blijft verantwoordelijk voor controle, beoordeling en besluiten.

## Validatie na implementatie

Voer vanuit `Software` minimaal de relevante tests uit:

```powershell
docker compose run --rm web python manage.py test dossier
docker compose run --rm web python manage.py check
```

Test daarnaast handmatig met een docent, student zonder rechten en fictieve casusdata. Controleer dat ongeldige AI-uitvoer en providerstoringen als fout worden getoond, dat de oorspronkelijke antwoorden intact blijven en dat geen geheime sleutels of volledige persoonsgegevens in logs terechtkomen.
