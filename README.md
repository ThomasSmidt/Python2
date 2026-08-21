# Python II — ETL-datapipeline med kryptografi (Iris flora-data)

Løsning på de to case-opgaver *"Python rettet mod databehandling"* og *"Kryptografi"*.

Naturcentret ønsker et system til analyse af blomsterdata. Pipelinen henter Iris-datasættet
fra en international datakilde, filtrerer det ned til arten **Iris-setosa**, gemmer resultatet
som CSV og i en MySQL-database, og præsenterer det som tre diagrammer.

Repositoriet indeholder **to versioner** af løsningen, som krævet ved afleveringen:

| Mappe | Indhold |
|---|---|
| [`etl_uden_kryptering/`](etl_uden_kryptering/) | Iteration 1 — ETL-løsning **uden** kryptering af data |
| [`etl_med_kryptering/`](etl_med_kryptering/) | Iteration 2 — samme pipeline, men data krypteres **inden** de gemmes i CSV-filen og i databasen |

Version 2 er en kopi af version 1 med et ekstra `security.py`-modul samt tilpasninger i
`load.py` og `main.py`. Alt andet er identisk, så forskellen mellem de to iterationer er let
at se med en diff:

```powershell
git diff --no-index etl_uden_kryptering etl_med_kryptering
```

---

## Arkitektur

Begge versioner er bygget som ét main-script, der importerer selvstændige, genbrugelige moduler:

```
main.py                 Orkestrerer Extract -> Transform -> Load -> Visualisering
├── config.py           Central konfiguration (URL, mapper, kolonnenavne, MySQL)
├── extract.py          Extract: 3 metoder til download (requests / wget / subprocess+curl)
├── transform.py        Transform: PySpark, filtrerer species == "Iris-setosa"
├── load.py             Load: gemmer som CSV i Output_dir + som tabel i MySQL
├── visualisering.py    Visualisering: scatter-plot, histogram, boxplots
└── security.py         (kun version 2) AES-GCM / AES-CBC / Fernet kryptering
```

Dataflow:

```
Datakilde (HTTPS)
   -> Input_dir/iris.csv                 (rå data, med kolonnenavne)
   -> PySpark-filter (Iris-setosa)
   -> Output_dir/transform_iris.csv      (version 2: krypteret)
   -> MySQL: iris_pipeline.iris_setosa   (version 2: krypteret)
   -> læses tilbage -> (version 2: dekrypteres) -> 3 diagrammer
```

---

## Forudsætninger

* **Python 3.10+**
* **Java 17 eller 21** (JDK) — kræves af PySpark. Tjek med `java -version`.
* **MySQL-server** kørende på `localhost:3306`
* **curl** (kun nødvendigt for `extract_with_curl`; følger med Windows 10/11 som `curl.exe`)

Løsningen er udviklet og testet på Windows 11 med PowerShell.

---

## Installation

```powershell
git clone <repo-url>
cd <repo>

# vælg den version du vil køre
cd etl_uden_kryptering        # eller: cd etl_med_kryptering

py -m venv venv
.\venv\Scripts\Activate.ps1

pip install -r requirements.txt
```

Uden venv kan du køre direkte med `py`, som bruger den installerede Python 3.10.
Bemærk at `python` på Windows ofte rammer Microsoft Stores stub i stedet for den
rigtige Python — brug `py`, hvis du får beskeden *"Python was not found"*.

### MySQL-opsætning

Databasen `iris_pipeline` **oprettes automatisk**, hvis den ikke findes — der skal derfor kun
være en bruger med rettigheder til at oprette databaser. Tilret loginoplysningerne i
`config.py`, så de passer til din server:

```python
MYSQL_CONFIG = {
    "host": "localhost",
    "port": 3306,
    "user": "root",
    "password": "Passw0rd",
}
```

---

## Kørsel

```powershell
py main.py
```

Scriptet kører hele pipelinen og åbner til sidst de tre diagrammer i et vindue. Hver kørsel
overskriver både CSV-filen i `Output_dir/` og tabellen i databasen, så gammelt data aldrig
hænger ved.

Eksempel på output fra version 2:

```
Encryption: AES-GCM
Extracted: Input_dir/iris.csv
Transformed: 50 Iris-setosa rows
Saved encrypted CSV: Output_dir/transform_iris.csv
Loaded encrypted data into MySQL: iris_pipeline.iris_setosa

As stored in the database (ciphertext):
                    sepal_length                  sepal_width  ...
0   yO3D_flKtK_II5OIUPeIyOKUDb2K...  CjEMVtgr08iH-muiejUMOT4qaW4...
1   ZaO35Dy5Fjji6LzgkALwKPeL2yed...  1oE8IICvOe3OB0GGjjs57ANEJyM...

After decryption, ready for the charts:
   sepal_length  sepal_width  petal_length  petal_width      species
0           5.1          3.5           1.4          0.2  Iris-setosa
1           4.9          3.0           1.4          0.2  Iris-setosa
```

---

## Extract — tre metoder og sikkerhedsvurdering

`extract.py` indeholder alle tre krævede metoder, og alle tre virker:

| Metode | Teknologi |
|---|---|
| `extract_with_requests()` | `requests`, streamet i 8 KiB blokke |
| `extract_with_wget()` | `wget`-modulet (ren Python, ikke wget-binæren) |
| `extract_with_curl()` | `subprocess` med den eksterne `curl` |

Fælles for alle tre:

* **HTTPS håndhæves** — ikke-HTTPS-URL'er afvises, og certifikatvalidering er slået til.
* **Beskyttelse mod command-line injection** — `subprocess.run()` kaldes med en argumentliste
  og `shell=False`, så URL'en aldrig fortolkes af en shell. De to øvrige metoder rører
  slet ikke en shell.
* **Robusthed** — data hentes i små blokke i stedet for på én gang, der er timeouts og retry,
  og en afbrudt download slettes, så næste trin aldrig arbejder videre på en korrupt fil.
* **Intet hardcodet filnavn** — filnavnet udledes af URL'ens sti og saniteres, hvilket samtidig
  forhindrer path traversal.

### Valgt metode: `requests`

Bemærk først, at `curl` ikke er en selvstændig fjerde mulighed: fra Python kan man kun nå
curl-binæren ved at starte den som en proces, så "curl" og "subprocess (curl/wget)" er den
samme mulighed beskrevet to gange. Der er altså tre reelt forskellige teknologier.

| | `requests` | `wget`-modulet | `curl` via `subprocess` |
|---|---|---|---|
| Injection-flade | Ingen | Ingen | Kun lukket via disciplin (arg-liste + `shell=False`) |
| Ekstern binær / PATH-hijacking | Nej | Nej | **Ja** |
| Kontrol over TLS fra Python | Fuld | Næsten ingen | Afhænger af binærens build |
| Vedligeholdt | Aktivt | **Sidste release 2015** | Aktivt |
| Timeout | connect + read | **Ingen** | `--connect-timeout` |
| Retry med backoff | urllib3 `Retry` | Nej | `--retry` |
| Resume af afbrudt download | Nej | Nej | `--continue-at` |
| Fejlsignalering | Typet exception-hierarki | Generiske exceptions | Numerisk exit-kode |
| Cross-platform | Ja | Ja | Nej (afhænger af installeret binær) |

**Sikkerhed:** `requests` og `wget`-modulet konstruerer aldrig en kommandolinje, så
injection-fladen er ikke bare lukket — den findes ikke. `extract_with_curl()` er sikker som
den er skrevet, men sikkerheden er en egenskab ved udviklerens disciplin frem for ved
teknologien: én senere refaktorering til en f-string med `shell=True` genåbner hullet. Dertil
kommer at det at starte et eksternt program betyder, at Python slår `curl` op via PATH — på en
maskine hvor PATH indeholder en mappe med svage skriverettigheder kan det opslag kapres.
Det stærkeste argument mod `wget`-modulet er supply chain: PyPI-pakken `wget` 3.2 er sidst
udgivet i **2015** og ville ikke få en rettelse, hvis der blev fundet en sårbarhed i den.

**Reliability:** `wget`-modulet er diskvalificeret her — det har slet ingen timeout-parameter,
så en stallet TCP-forbindelse (det normale symptom på et ustabilt net) får det til at hænge i
det uendelige. `curl` er stærkest på papiret med retry, resume og stall-detektion, men dens
største fordel — resume — er værdiløs her, hvor kildefilen er ~4,5 KB og kommer i ét svar.
`requests` dækker alt vi reelt har brug for, inde i processen: streaming holder
hukommelsen flad, `timeout=(connect, read)` dræber en stallet socket, og en urllib3
`Retry`-policy monteret på sessionen giver samme robusthed som `curl --retry`.

**Konklusion:** `requests` vinder sikkerhedsmæssigt, matcher `curl` på alle de
robusthedsegenskaber denne datakilde faktisk kan udnytte, og er den eneste af de tre der er
ægte cross-platform. Hele argumentet står udførligt som kodekommentar i `run_extract()` i
`main.py`.

**Bemærk om kolonnenavne:** kildefilen leveres *uden* header-række (første linje er allerede en
observation). `_ensure_header_row()` i `extract.py` tilføjer derfor header-rækken, så CSV-filen
i `Input_dir` viser fornuftige kolonnenavne, når den åbnes manuelt — som krævet.

---

## Kryptografi (version 2)

`security.py` implementerer de tre krævede krypteringsmetoder, alle med samme kontrakt
(`str` ind, Base64-token ud), så de kan udskiftes 1:1:

| # | Metode | Funktioner | Tokenlængde for `"5.1"` |
|---|---|---|---|
| 1 | **AES-GCM** | `encrypt_aes_gcm()` / `decrypt_aes_gcm()` | 44 tegn |
| 2 | **AES-CBC** (rå, PKCS7) | `encrypt_aes_cbc()` / `decrypt_aes_cbc()` | 44 tegn |
| 3 | **AES-CBC via Fernet** | `encrypt_fernet()` / `decrypt_fernet()` | 100 tegn |

### Valgt metode: AES-GCM

Begrundelsen står udførligt som kodekommentar i `security.py` (afsnittet
*"CHOICE OF METHOD FOR THIS PIPELINE"*). Kort fortalt, netop for denne datatype:

* **Integritet er lige så vigtigt som fortrolighed.** Det er forskningsdata til overvågning og
  dokumentation — et lydløst ændret måletal ville forplante sig direkte ud i naturcentrets
  grafer. AES-GCM er authenticated encryption og opdager enhver manipulation via sit
  authentication tag. Rå AES-CBC (metode 2) giver kun fortrolighed og ville dekryptere
  manipuleret data til et forkert tal uden at sige fra — derfor fravalgt.
* **Værdierne er meget små.** Hver celle er 3–4 tegn, og der krypteres celle for celle, så
  overhead pr. værdi betyder alt. GCM koster 28 bytes; Fernet koster 57 bytes, og rå CBC
  spilder en hel ekstra 16-byte blok på padding.
* **Fernet (metode 3)** løser CBC's integritetsproblem med HMAC, men er bygget til
  tidsbegrænsede tokens: den låser os til AES-128 og har et indbygget timestamp/ttl, der er
  irrelevant for måledata, som skal kunne læses om mange år.

### Hvad krypteres — og hvad sker der ved genindlæsning

Alle celleværdier krypteres individuelt, før de forlader processen i `load.py`. Kolonnenavnene
bevares i klartekst — de er skemaoplysninger, ikke måledata, og skal kunne bruges i
SQL-queries. Fordi værdierne gemmes som Base64-tokens, er de numeriske kolonner i databasen
deklareret `VARCHAR(255)` i stedet for `DOUBLE`.

Når data læses tilbage til de tre diagrammer, kalder `main.py` `decrypt_dataframe()`, som
dekrypterer hver celle og caster de fire målekolonner tilbage til `float`, inden
DataFramen sendes videre til `visualisering.py`.

### Nøglehåndtering

Nøglen er **aldrig hardcodet**. Ved første kørsel genereres en 32-byte AES-256-nøgle med
`os.urandom()` og gemmes i `secret.key`. Filen er med i `.gitignore` og må aldrig
committes. Nøglen kan i stedet leveres via en miljøvariabel, som har forrang — så ligger
den ikke i samme mappe som de data den beskytter:

```powershell
$env:IRIS_AES_KEY = "<base64-kodet 32-byte nøgle>"
```

Mister du `secret.key`, kan eksisterende krypteret data ikke længere læses — slet i så fald
`Output_dir/` og databasetabellen, og kør pipelinen igen.

---

## Kendte begrænsninger

* Kryptering på celleniveau betyder, at databasen ikke længere kan lave aritmetik eller
  range-queries på måleværdierne. SQL kan hente rækkerne, men selve analysen sker i Python
  efter dekryptering. Det er den bevidste pris for at beskytte data i hvile.
* PySpark kræver en JDK. Uden Java på PATH fejler `transform.py`.
