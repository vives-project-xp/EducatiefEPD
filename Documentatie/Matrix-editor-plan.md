# Ontwerpplan: flexibele spreadsheetmatrix

Datum: 15 oktober 2026. **Fasen 1–3 geïmplementeerd; fasen 4–5 blijven vervolgwerk.**

De gebruiker heeft gekozen voor een flexibele sheet met verschillende celtypes op iedere positie. Dit plan is met een subagent opgesteld en vervolgens expliciet voor implementatie goedgekeurd. Onderstaande ontwerpkeuzes blijven de richting; hoofdstuk 11 beschrijft de daadwerkelijk geleverde eerste editor en de grenzen daarvan.

## 1. Gewenste gebruikerservaring

Een docent kiest **Matrix** en krijgt direct een bewerkbaar raster, bijvoorbeeld zes rijen en vier kolommen. Rij- en kolomnamen hoeven niet meer vooraf in tekstvakken met één naam per regel te worden ingevoerd. Gewone rastercoördinaten zijn beschikbaar; inhoudelijke koppen kunnen rechtstreeks als vaste tekst in het raster worden geplaatst.

De docent kan:

- In cellen klikken en typen, of een rechthoek uit Excel plakken.
- Rijen en kolommen toevoegen, invoegen, dupliceren, verwijderen, verplaatsen en van formaat veranderen.
- Een cel of bereik selecteren en de inhoud, invoerregels en opmaak aanpassen.
- Een standaardtype op een kolom of bereik toepassen en individuele cellen daarvan laten afwijken.
- Wisselen tussen **Ontwerpen**, **Voorinvulling** en **Studentvoorbeeld**.
- Wijzigingen ongedaan maken/opnieuw uitvoeren en zien of er nog niet-opgeslagen wijzigingen zijn.

Voorbeeld: dezelfde rij kan een vast label, een datumveld, een getal met eenheid, een ja/nee-keuze en een groter tekstvak bevatten. Een volgende rij kan een andere combinatie gebruiken. Het wordt dus geen tabel waarin iedere kolom altijd één verplicht celtype heeft.

Studenten zien dezelfde indeling en kunnen alleen de aangewezen antwoordcellen invullen. De docent ziet bij beoordeling de oorspronkelijke studentindeling met leesbare waarden.

## 2. Celinhoud en opmaak

De basis moet ondersteunen:

- Korte tekst en tekst met meerdere regels.
- Getallen met exact bewaarde decimalen; instelbare weergave, zoals decimalen, eenheid, percentage of valuta, zonder formuleberekening.
- Datum, tijd en datum/tijd.
- Ja/nee, checkbox, één keuze en meerdere keuzes.
- Vaste tekst, koppen en instructies die studenten niet kunnen overschrijven.
- Per antwoordcel: verplicht, bewerkbaar, standaardwaarde, placeholder, hulptekst, toegestane keuzes en passende lengte-/waardegrenzen.
- Per cel/bereik: vet, cursief, tekst-/achtergrondkleur, uitlijning, terugloop en randen; per rij/kolom: hoogte en breedte.

Een gewone vereiste ja/nee-cel heeft drie toestanden: onbeantwoord, ja en nee. Een antwoord nee is geldig. Een checkbox met de betekenis “akkoord vereist” heeft een afzonderlijke regel nodig; een ongemarkeerde checkbox mag niet ongemerkt zowel “nee” als “niet beantwoord” betekenen.

Een latere uitbreiding kan tekstopmaak binnen één cel, veilige links, afbeeldingen en bijlagen ondersteunen. Afbeeldingen/bijlagen vereisen eerst een eigen upload-, opslag-, eigendoms- en verwijderbeleid: die infrastructuur bestaat nog niet.

Formules, macro's, externe werkmapverbindingen, draaitabellen en grafieken vallen buiten dit voorstel. Het plan levert spreadsheetbediening voor onderwijsformulieren, zonder volledige Excel-compatibiliteit te beloven.

## 3. Bediening

- Bereikselectie met muis én toetsenbord, Tab/Shift+Tab, pijltjestoetsen en Enter, met een duidelijk verschil tussen celnavigatie en inhoud bewerken.
- Kopiëren/plakken, inhoud wissen en ongedaan maken/opnieuw uitvoeren. Een plakactie is één ongedaan te maken stap.
- “Inhoud wissen” verwijdert geen celtype, opmaak of instructie. “Rij verwijderen” toont vooraf de gevolgen wanneer daarin inhoud staat.
- Eerste clipboardversie ondersteunt gewone rechthoekige waarden: Unicode, lege cellen, tabs, meerregelige tekst en voorloopnullen. Tekst blijft tekst tenzij het gekozen celtype een expliciete conversie vraagt.
- Plakken over vaste cellen, buiten de toegestane structuur of met ongeldige waarden levert een bruikbare melding/voorvertoning op. Geen stille gedeeltelijke import.
- Tekst die met een formuleteken begint wordt niet uitgevoerd. Bij latere spreadsheetexport moet ook worden voorkomen dat een externe spreadsheet die tekst alsnog als formule uitvoert.
- Latere functies: bevroren koppen, zoeken, bereik vullen, gegroepeerde secties en beperkte samengevoegde cellen.
- Alleen compatibele lege/labelcellen mogen aanvankelijk worden samengevoegd. Bestaande antwoorden nooit stilzwijgend samenvoegen of verwijderen.
- Sorteren/filteren is alleen zinvol voor expliciete tabellen met herhaalde records; willekeurig sorteren in een vrije formulierindeling kan labels en bijbehorende invoervelden uit elkaar halen.

## 4. Rollen, voorinvulling en herhaalde rijen

Docenten ontwerpen matrices in de bibliotheek. De bestaande beperking op rechtstreeks wijzigen van casusveldstructuur blijft gelden: die routes zijn voor beheerders. Dit plan verandert het gedeelde bibliotheekbeleid niet.

Er blijven drie afzonderlijke gegevenslagen:

1. **Definitie:** indeling, types, vaste teksten, validatie, opmaak en eventuele standaardantwoorden in de template.
2. **Casusvoorinvulling:** patiënt-/casusspecifieke waarden in het docentbasisdossier.
3. **Studentantwoord:** de persoonlijke kopie met eigen waarden en een eigen opgeslagen schema.

De voorinvulmodus werkt op het niveau waarop de gebruiker zich bevindt: standaardantwoorden in de bibliotheek of casusvoorinvulling in het basisdossier. De interface moet dat onderscheid benoemen.

Herhaalde rijen/secties komen in een latere fase. Een docent kan bijvoorbeeld een herhaalbare meetrij ontwerpen. Studenten mogen vervolgens instanties toevoegen binnen de ingestelde grenzen; zij veranderen niet de definities, celtypes of vaste instructies. Iedere instantie krijgt een eigen stabiele identificatie.

## 5. Technische uitgangspunten vóór de editor

- [forms.py](../Software/dossier/forms.py): FieldConfigurationForm gebruikt rows_text en columns_text, met één label per regel.
- [models.py](../Software/dossier/models.py): FieldDefinition heeft rows/columns als JSON-lijsten, zonder metadata per cel.
- [views.py](../Software/dossier/views.py) en [_dynamic_fields.html](../Software/templates/dossier/_dynamic_fields.html): huidige matrixcellen zijn tekstvelden, geadresseerd met rij-/kolomindex.
- [module_data.py](../Software/dossier/module_data.py): de workflowfix centraliseert conceptparsing en definitieve validatie. Het matrixontwerp moet daarop aansluiten.
- [services.py](../Software/dossier/services.py): bibliotheek naar casus en casus naar student zijn afzonderlijke kopieën. Ook de adoptieroute in create_case_structure moet eventuele nieuwe matrixmetadata meenemen.
- [teacher_item_form.html](../Software/templates/dossier/teacher_item_form.html): het huidige smalle generieke formulier is ongeschikt voor een uitgebreide sheet.
- [teacher_student_case.html](../Software/templates/dossier/teacher_student_case.html): beoordeling toont matrixgegevens momenteel als ruwe waarden. Ook dit scherm heeft de gedeelde rasterweergave nodig.

## 6. Datamodel en stabiele adressen

Voeg een optioneel, geversioneerd JSON-veld **matrix_definition** toe aan de abstracte FieldDefinition. Dit vereist een migratie voor LibraryField en ModuleField. Behoud tijdens de overgang ondersteuning voor bestaande rows/columns.

De definitie bevat:

- Een formaatversie, los van de bestaande LibraryTemplate.version-revisieteller.
- Geordende rijen en kolommen met stabiele IDs, labels en afmetingen.
- Alleen afwijkende instellingen per cel, geadresseerd met rij-ID en kolom-ID.
- Type, vaste inhoud, invoerrechten, keuzes, validatieregels, opmaak en standaardantwoord.
- Algemene en kolominstellingen met expliciete overrides per cel.
- In latere versies: herhaalbare secties en samenvoegingen.

Antwoorden blijven apart opgeslagen in een versieaanduiding met een geneste mapping van rij-ID naar kolom-ID naar waarde. Een rij verplaatsen verandert alleen de weergavevolgorde. Dupliceren maakt nieuwe IDs. Indexen zoals 0_0 zijn geen geschikte identiteit voor een bewerkbare sheet: verplaatsen kan anders antwoorden onder andere labels laten terechtkomen.

Bewaar getallen zonder verlies van decimale precisie. De app gebruikt nl-be; decimale komma's vereisen expliciete normalisatie en een voorspelbare weergave. Bewaar datum-/tijdwaarden in een vast formaat en bepaal het tijdzonecontract vóór implementatie. Gebruik gestructureerde waarden voor meervoudige keuzes en booleans, geen presentatiezinnen als opslagformaat.

## 7. Compatibiliteit en snapshots

- Een lege nieuwe definitie betekent **legacy versie 1**. Een adapter kan de bestaande labels en indexwaarden weergeven zonder historische snapshots te herschrijven.
- Bestaande required=true betekent minimaal één niet-lege matrixcel. Behoud dat gedrag voor oude matrices. Versie 2 kan daarnaast specifieke bewerkbare cellen verplicht maken; vaste labels en opmaak tellen niet als antwoorden.
- Zet een bronmatrix pas doelbewust om wanneer die in de nieuwe editor wordt opgeslagen. Zet bijbehorende casusvoorinvulling met een expliciete mapping in dezelfde transactie om. Onverklaarbare waarden melden en bewaren, niet verwijderen.
- Nieuwe matrixmetadata gaat mee via as_schema(), beide veldkopieerpaden en de eerste start van een studentcasus.
- Bestaande studentkopieën blijven hun eigen ModuleResponse.schema gebruiken. Latere rijtoevoegingen, typewijzigingen of templateversies veranderen die niet.
- Bewaak gelijktijdige bewerking van de gedeelde bibliotheek met revisiecontrole: een verouderde opslag mag een nieuwere wijziging niet stil overschrijven.

## 8. Validatie, opslag en toegankelijkheid

De server gebruikt de opgeslagen definitie als gezaghebbend schema. Een student stuurt antwoorden en toegestane herhaalacties, geen vervangende autoritatieve definitie. Controleer ook vaste cellen, typegrenzen, onbekende IDs, omvang en toegangsrechten op de server.

Conceptopslag controleert ingevulde waarden. Volledige indiening controleert daarnaast alle verplichte antwoordcellen. Het nieuwe raster volgt de workflowfix: bij fouten blijft alle invoer beschikbaar, gewone modulevelden en observaties worden gezamenlijk opgeslagen, en een fout voorkomt gedeeltelijke opslag.

Fouten krijgen een exacte celverwijzing, zichtbare markering en bereikbare samenvatting. Bied toegankelijke koppen, zichtbare focus, aangekondigde invoerrechten/fouten en bediening zonder muis. Test celnavigatie, tekstbewerking en keuzelijsten afzonderlijk. Een smal scherm moet een bruikbare cel-/eigenschappenweergave krijgen.

De officiële [W3C grid pattern](https://www.w3.org/WAI/ARIA/apg/patterns/grid/) beschrijft het onderscheid tussen navigatie en bewerken. ARIA-attributen alleen bewijzen geen toegankelijke werking; daadwerkelijke toetsenbord- en schermlezertests blijven nodig.

## 9. Uitvoeringsfasen

1. **Gegevenscontract en componentonderzoek.** Leg versie, IDs, types, serialisatie, fouten en kopieerregels vast. Vergelijk een beperkt aantal gridcomponenten met officiële informatie over licentie, eigen celeditors, clipboard, toegankelijkheid, opmaak en integratie in Django/static. Er is nog geen bibliotheek gekozen; een volledige frontendherschrijving is geen uitgangspunt.
2. **Directe matrixopbouw.** Bouw de brede editor met cel-/bereikbewerking, rijen/kolommen, getypeerde cellen, basisopmaak, undo/redo, waarden plakken en studentvoorbeeld. Maak een bestaand eenvoudig matrixformulier via de nieuwe editor opnieuw na.
3. **Volledige dossierintegratie.** Verbind bibliotheekkopie, casusvoorinvulling, studentopslag, definitieve validatie en leesbare beoordeling. Gebruik één gedeelde rastercomponent met verschillende rechten/modes. Verifieer oude én nieuwe matrices met twee onafhankelijke studentkopieën.
4. **Uitgebreide indelingen.** Voeg bevroren koppen, zoeken, bereik vullen, groepen, veilige samenvoegingen en docentgestuurde herhaalde rijen/secties toe.
5. **Uitwisseling en rijkere inhoud.** Voeg zo nodig waardenimport/export voor .xlsx/CSV, presets, tekstopmaak binnen cellen, links en later uploads toe. Iedere uitbreiding heeft eigen acceptatiecriteria; een volledige Excel-werkmapimport is geen impliciete belofte.

De gebruiker heeft uitvoering van de editor en dossierintegratie goedgekeurd. Latere uitbreidingsfasen blijven vervolgwerk.

## 10. Acceptatiecriteria

- Een docent maakt een matrix zonder handmatige newline-lijsten voor rijen/kolommen.
- Verschillende celtypes werken in dezelfde rij én kolom.
- Rijen/kolommen invoegen, verplaatsen en hernoemen verandert de betekenis van bestaande antwoorden niet; kopieën zijn onafhankelijk.
- Plakken bewaart realistische Excel-inhoud en heeft voorspelbaar gedrag bij lege cellen, voorloopnullen, ongeldige waarden, beschermde cellen en overflow.
- Conceptopslag, foutenherstel, observaties en indiening volgen de gecorrigeerde workflow.
- Legacywaarden, oude required-semantiek en reeds gestarte snapshots blijven behouden.
- Twee studenten blijven geïsoleerd na latere bronwijzigingen; ingediende dossiers en onbevoegde verzoeken blijven geblokkeerd.
- Beoordeling toont een leesbaar raster met de oorspronkelijke schema-/waardetypes.
- Migratie-, kopieer-, revisieconflict- en servervalidatietests tonen geen stil gegevensverlies.
- Toetsenbord, schermlezer, foutfocus en smalle schermen zijn getest; een met de gebruikers afgesproken realistische maximale sheetgrootte presteert voldoende.

## 11. Geleverde implementatie

De component is een eigen begrensde HTML/JavaScript-grid binnen Django/static, zonder
frontendbuild of nieuwe productieafhankelijkheid. Bij de vergelijking zijn de officiële
[Tabulator spreadsheet-documentatie](https://www.tabulator.info/docs/6.x/spreadsheet/)
en [AG Grid cell selection-documentatie](https://www.ag-grid.com/javascript-data-grid/cell-selection/)
geraadpleegd. De eigen component gebruikt native invoercontrols en hetzelfde contract
voor ontwerpen, invullen, voorinvullen en beoordelen. Dit is geen algemene Excel-vervanger.

- Beginraster: 6 × 4. Directe invoer, cel-/bereikselectie, rij-/kolomacties,
  afmetingen/koppen, eigenschappen, opmaak, 40 lokale undo-toestanden, TSV-kopie/plak
  en tijdelijk studentvoorbeeld zijn aanwezig.
- Alle elf genoemde celtypes zijn beschikbaar. Numerieke opslag blijft tekst met
  exacte decimalen; punt/komma worden genormaliseerd. Afronding is alleen weergave.
  Percentages worden als procentpunten ingevoerd. Datum/tijd heeft geen tijdzone:
  het is lokale kloktijd, net als de bestaande dossiercontrols.
- Een type/opmaak voor een hele kolom wordt als celinstellingen op dat geselecteerde
  bereik toegepast. Er is geen afzonderlijke cascade van kolomdefaults. Nieuwe
  rijen/kolommen beginnen met tekstcellen; dupliceren kopieert instellingen/defaults.
- Standaardantwoorden bewerk je in ontwerpmodus; casusspecifieke voorinvulling blijft
  in het bestaande basisdossierscherm. Er is geen derde tab binnen de ontwerper.
- Grenzen: 100 rijen, 40 kolommen, 2.000 cellen, 100 keuzeopties per cel, 10.000 tekens
  per cel en 512.000 JSON-tekens per definitie/antwoordset. Plak-overflow geeft een
  melding zonder gedeeltelijke wijziging; uitbreiden gebeurt bewust via de rij-/kolomacties.
- Koppen blijven bij scrollen zichtbaar. Zoeken, bereikvullen, groepen, samenvoegen,
  herhaalbare secties, XLSX/CSV-bestandsimport, inline tekstopmaak en uploads blijven
  latere uitbreidingen. Clipboard importeert waarden, geen Excel-opmaak of formules.

### Datacontract en migratie

`0007_matrix_definition` voegt een leeg optioneel JSON-veld toe aan LibraryField en
ModuleField; er is geen automatische herschrijving van bestaande gegevens. De definitie
heeft `version: 2`, `rows`, `columns` en een sparse `cells[row_id][column_id]`-mapping.
Rijen/kolommen bevatten een stabiele ID, label en hoogte/breedte. Antwoorden hebben
`version: 2` en `cells[row_id][column_id]`; booleans zijn booleans en multiselects lijsten.
Vaste tekst blijft uitsluitend in het schema. Ontbrekende antwoorden gebruiken de
gekopieerde standaardwaarde. Expliciet leeg betekent leeg, ook als er een default is.

De centrale servervalidatie staat in [matrix.py](../Software/dossier/matrix.py).
Alle opslag-/indienroutes blijven de centrale [module_data.py](../Software/dossier/module_data.py)
gebruiken. Schemawijziging en omzetting van casusvoorinvulling gebeuren in één transactie
met een modulelock. Het bronformulier heeft een schemafingerprint tegen verouderde
opslag. Expliciet kopiëren van een onderdeel en kopiëren via een dossiersjabloon dragen
matrixmetadata over; studentstart kopieert die naar de eigen snapshot. De vroegere
automatische vaste casusopbouw is verwijderd overeenkomstig de nieuwere main-workflow.
Legacy-indexwaarden worden alleen bij bewuste bronbewerking
omgezet, met behoud van hun oorspronkelijke rij-/kolomidentiteit.

### Verificatie

De regressies staan in [test_matrix.py](../Software/dossier/test_matrix.py),
[matrix-core.test.mjs](../Software/tests/matrix-core.test.mjs) en de optionele
[browsercontrole](../Software/tests/matrix-browser.mjs). Die laatste gebruikt uitsluitend
een geïsoleerde lokale testserver op poort 8017 en de afgeschermde testfixtures in
[matrix_browser_seed.py](../Software/tests/matrix_browser_seed.py).

De oorspronkelijke resultaten staan in MEMORY.md, hoofdstuk 25; de gecombineerde
verificatie met main staat in hoofdstuk 31. Migratie `0012_merge_matrix_main` verbindt
de matrixmigratie met main-migratie `0011_record_existing_rich_text_choices`.
De flexibele editor blijft onderdeel van bibliotheekvelden en dossiers. Het afzonderlijke
matrixvraagtype in Functiebeheer wordt door deze integratie niet vervangen.
De migratie is alleen op een tijdelijke testdatabase uitgevoerd; deployment van de
nieuwe code vereist de gebruikelijke migratiestap op de bedoelde applicatiedatabase.
