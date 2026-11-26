# Werking van het dossiersysteem

De indeling volgt de foto: opleiding links, casus in het midden en bibliotheek rechts. Binnen elk deel lopen de onderdelen van boven naar beneden.

```mermaid
flowchart LR
    subgraph EDUCATION_AREA["Opleiding"]
        direction TB
        EDUCATION["Opleiding"]
        GROUP["Lesgroepen"]
        STUDENT["Studenten"]
        EDUCATION --> GROUP --> STUDENT
    end

    subgraph CASE_AREA["Casus"]
        direction TB
        CASE["Casus"]
        TASKS["Opdrachten"]
        PATIENT["Patiënt"]
        DOSSIER["Dossier"]
        SELECTED["Gekozen modules"]
        CASE --> TASKS
        CASE --> PATIENT --> DOSSIER --> SELECTED
    end

    subgraph LIBRARY_AREA["Bibliotheek"]
        direction TB
        LIBRARY["Bibliotheek"]
        TEMPLATE["Dossier sjablonen"]
        MODULES["Modules"]
        FUNCTION_NAMES["Functies<br/>Functienamen bij een module"]
        FUNCTION_MANAGEMENT["Functiebeheer<br/>Aparte editor"]
        FORMS["Formulieren"]
        QUESTIONS["Vragen"]
        LIBRARY --> TEMPLATE
        LIBRARY --> MODULES --> FUNCTION_NAMES
        FUNCTION_NAMES -. "geen automatische koppeling" .-> FUNCTION_MANAGEMENT
        FUNCTION_MANAGEMENT --> FORMS --> QUESTIONS
    end

    GROUP -. "geeft toegang tot" .-> CASE
    TEMPLATE -->|"kiest en ordent"| SELECTED
    MODULES -. "kan worden gekozen voor"| SELECTED

    classDef education fill:#e8f1ff,stroke:#3973ac,color:#102a43
    classDef case fill:#e8f7ee,stroke:#43845a,color:#173b24
    classDef library fill:#eee9ff,stroke:#7556a8,color:#2c1d47
    classDef function fill:#f1f3f5,stroke:#6c757d,color:#212529
    class EDUCATION,GROUP,STUDENT education
    class CASE,TASKS,PATIENT,DOSSIER,SELECTED case
    class LIBRARY,TEMPLATE,MODULES library
    class FUNCTION_NAMES,FUNCTION_MANAGEMENT,FORMS,QUESTIONS function
```
