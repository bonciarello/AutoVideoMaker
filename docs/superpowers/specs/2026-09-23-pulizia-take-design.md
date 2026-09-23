# Pulizia automatica dei take — design

Data: 2026-09-23 · Stato: design approvato in chat sezione per sezione, spec in revisione

## Obiettivo

Far arrivare in CapCut un montaggio quasi finito: oltre alle pause (già tolte
oggi), AutoVideoMaker toglie in automatico false partenze, autocorrezioni,
parole ripetute per inciampo, take ripetuti e i take segnati a voce con la
parola «rifaccio». Il contenuto non viene giudicato: tutto ciò che è detto una
sola volta resta.

## Contesto verificato (esplorazione su questa macchina)

- Pipeline attuale (`main.py`): estrazione audio con separazione voce →
  trascrizione con timestamp per parola (Deepgram nova-3, fallback Whisper) →
  segmenti parlati dalle parole (`--word-gap` 0.2 s, `--speech-pad` 0.05 s) o
  `silencedetect` → `process_and_export` → EDL, chunk, progetto CapCut →
  metadati Claude.
- Punto d'aggancio già presente e inutilizzato: `process_and_export(...,
  ai_cuts=[])` in `main.py:198`.
- Le parole con i tempi non vengono salvate: esiste solo `transcript.txt`.
- Deepgram con `smart_format` segna le frasi interrotte con «...» nel testo con
  punteggiatura (`punctuated_word`). Il codice oggi legge solo `w.word`, la
  forma normalizzata senza punteggiatura. Le filler word di Deepgram esistono
  solo per l'inglese: in italiano gli «ehm» non vengono trascritti e finiscono
  nelle pause.
- **Banco di prova disponibile**: il video del 16/09 (`output/2026-09-16
  09-10-23/`, 20:20, 2.399 parole) è stato rifinito a mano in CapCut 9.4.0
  partendo dal progetto generato:
  - auto: 184 segmenti, 1078,6 s tenuti (17:59);
  - manuale: 206 segmenti, 920,7 s tenuti (15:21);
  - 177 tagli manuali in più per 158,3 s (mediana ~0,35 s, una quindicina tra
    2 e 10 s; il primo è «Buongiorno a...»); solo 0,43 s di tagli automatici
    ripristinati a mano;
  - nel transcript: 22 frasi interrotte con «...» e 31 ripetizioni immediate.
- **Marcatori CapCut** (draft reali 9.4.0): `draft_info["time_marks"] =
  {"id", "mark_items": [{"id", "time_range": {"start": µs, "duration": 0},
  "color": "#00c1cd", "title": "Marcatore 01"}]}`. I marcatori per-clip stanno
  invece in `materials.time_marks` (non usati qui). L'utente usa già i
  marcatori ciano di default per le sue note.
- `generate_capcut_project` oggi **sovrascrive** un progetto con lo stesso nome
  (`src/capcut_export.py:286`): rilanciare sul video del 16/09 distruggerebbe
  il montaggio manuale.
- Ambiente: Python 3.14.3, `anthropic` 0.120.2, `numpy` 2.5.3 nel venv;
  `pytest` assente. `.gitignore` esclude `*.json`, `*.txt` e `output/`. Il
  remote è pubblico su GitHub: i dati del video non vanno nel repo.

## Decisioni prese con l'utente

- **Ambito**: solo pulizia. Niente tagli editoriali (digressioni, passaggi
  deboli) né durata target.
- **Tagli dubbi**: applicati e segnalati con un marcatore in CapCut.
- **Parola-segnale**: «rifaccio», detta da sola tra due pause.
- **Editor**: si resta su CapCut; niente export FCPXML/Resolve nella v1.
- **LLM**: `claude-opus-5` (stesso modello dei metadati), output strutturato,
  fallback server-side sui rifiuti attivato di default.

## Principio guida

Claude indica **cosa** tagliare citando i numeri delle parole; il codice
calcola **dove** tagliare. L'LLM non produce mai tempi.

## Flusso

```
trascrizione (parole con tempi) ──► output/<video>/words.json (riusato ai rilanci)
        │
        ├─► pause (come oggi) ──────────────────────────────► tagli_pause
        │
        └─► pulizia take
              1. regole deterministiche → candidati sicuri / dubbi
              2. Claude → verdetti sui dubbi + tagli nuovi
              3. unione a livello di parola → tempi (punto più silenzioso)
                                                 ──► tagli_pulizia + marcatori
        ▼
process_and_export(tagli_pause, ai_cuts=tagli_pulizia, markers=marcatori)
        ──► CapCut con marcatori · EDL · chunk · pulizia.md / pulizia.json
```

EDL e chunk ricevono i nuovi tagli senza modifiche, perché derivano dagli
stessi `keep_ranges`.

## Moduli

Nuovi (piatti in `src/`, come gli esistenti; identificatori in inglese,
commenti e messaggi in italiano):

- `cleanup_rules.py` — regole deterministiche, funzioni pure: lista di parole
  → candidati.
- `cleanup_llm.py` — passata Claude: prompt, JSON Schema, suddivisione in
  blocchi, chiamata, validazione della risposta.
- `cleanup.py` — orchestrazione: regole + Claude → unione → conversione
  parole→tempi → tagli, marcatori, report (`write_report`, chiamato da
  `main.py` dopo l'export perché servono i `keep_ranges` finali).
- `intervals.py` — aritmetica degli intervalli (unione, durata, complemento,
  intersezione, differenza) per report e banco di prova.

Modificati:

- `utils.py` — `normalize_word` (condivisa da trascrizione e regole) e la
  costante `CLAUDE_MODEL`, usata anche da `metadata_generation.py`.
- `transcription.py` — ogni parola ha `id`, `text` (con punteggiatura) e
  `confidence`; salvataggio e riuso di `words.json`.
- `main.py` — nuova fase tra trascrizione ed export, nuovi flag, marcatori per
  il progetto combinato; costruzione degli argomenti in `build_parser()`.
- `video_processing.py` — calcolo dei `keep_ranges` estratto in
  `compute_keep_ranges` (puro, usato anche dal banco di prova); parametro
  `markers` verso l'export CapCut; svuotamento della cartella `chunks` prima di
  rigenerarla.
- `capcut_export.py` — separato in costruzione pura del draft
  (`build_draft`) e scrittura su disco; marcatori; mai sovrascrivere un
  progetto esistente.

## Modello dati

Parola (in memoria e in `words.json`); le chiavi esistenti restano invariate:

```json
{"id": 0, "start": 8.08, "end": 8.61, "word": "buongiorno", "text": "Buongiorno", "confidence": 0.98}
```

- `word`: forma normalizzata (Deepgram `word`; per Whisper normalizzata da noi).
- `text`: forma con punteggiatura (Deepgram `punctuated_word`; Whisper il
  token ripulito dagli spazi).

`words.json`:

```json
{
  "version": 1,
  "video": {"name": "2026-09-16 09-10-23.mov", "size": 12278148217, "duration": 1219.63},
  "transcriber": "deepgram", "model": "nova-3", "language": "it",
  "text": "…",
  "words": ["…"]
}
```

Taglio (interno e in `pulizia.json`):

```json
{"from_id": 0, "to_id": 1, "kind": "false_start", "sure": false, "source": "rule",
 "reason": "ripartenza con saluto diverso", "text": "Buongiorno a...",
 "start": 8.05, "end": 9.90, "timeline_time": 0.0}
```

`kind`: `cue_word`, `false_start`, `self_correction`, `repetition`, `retake`.
Etichette italiane in report e marcatori: «rifaccio», «falsa partenza»,
«autocorrezione», «ripetizione», «take ripetuto».

## Regole deterministiche (`cleanup_rules.py`)

Definizioni comuni:

- `norm(w)`: minuscolo, senza punteggiatura (apostrofi interni conservati).
- **Frase**: sequenza di parole chiusa da `.` `?` `!` `...` `…` nel `text`,
  oppure da una pausa > `PHRASE_GAP` (0,6 s).
- **Parole funzione**: articoli, preposizioni semplici e articolate,
  congiunzioni (e, ed, o, ma, che, se), pronomi atoni (mi, ti, ci, vi, si, lo,
  la, li, le, ne, gli), `non`, ausiliari brevi (è, sono, ho, ha), dimostrativi
  (questo/a/i/e, quel, quello/a).
- **Ripetizioni enfatiche, mai tagliate**: no, sì, piano, via, così, quasi,
  bene, ora, subito, presto.

Le soglie sono costanti in testa al modulo, da tarare sul banco di prova.

### R1 — parola-segnale «rifaccio» (`cue_word`)

- Scatta su una parola con `norm == cue_word` e pausa ≥ `CUE_PAUSE` (0,3 s)
  prima o dopo. Le parole immediatamente precedenti «ok», «no», «scusate»,
  «aspetta» (entro 1 s) fanno parte del taglio.
- Ripartenza R = prime 5 parole dopo la parola-segnale. Si cerca all'indietro,
  fino a `RETAKE_LOOKBACK` (60 s), l'ultima posizione `s` da cui iniziano le
  stesse parole di R per il k più grande con 3 ≤ k ≤ 5.
- Prima si massimizza k, poi a parità di k si sceglie la posizione più
  recente.
- Trovata → taglio da `s` alla parola-segnale inclusa, **sicuro**.
- Non trovata → taglio dall'inizio della frase che precede la parola-segnale
  fino alla parola-segnale inclusa, **dubbio**.

### R2 — frase interrotta con «...» (`false_start`)

- Scatta su una parola k il cui `text` termina con «...» o «…», se non è
  l'ultima.
- Si cerca il j più grande (1 ≤ j ≤ 5) per cui le ultime j parole fino a k
  coincidono con le prime j parole dopo k («non è... Non è il massimo»).
  Trovato → taglio delle parole k−j+1…k, **sicuro**.
- Nessuna coincidenza (riformulazione): se il frammento, dall'inizio della sua
  frase a k, ha al massimo 3 parole → taglio del frammento, **dubbio**
  («Buongiorno a... Ciao a tutti»); altrimenti nessun candidato (lo valuta
  Claude, che vede comunque il «...»).

### R3 — parole ripetute di fila (`repetition`)

- Per n = 3, 2, 1 (prima il più lungo): se le parole i…i+n−1 coincidono con
  i+n…i+2n−1 e la pausa tra le due occorrenze è ≤ 1,0 s → taglio della prima
  occorrenza. Scansione da sinistra a destra senza sovrapposizioni («che che
  che» → togli le prime due).
- n = 1 con parola enfatica → nessun candidato.
- **Sicuro** se n ≥ 2 o se è una parola funzione; altrimenti **dubbio**
  («molto molto»).
- Nessun candidato se la prima occorrenza chiude una frase (. ? !, ma non «...»): «...di questo. Questo è il punto» resta com'è.

### R4 — take ripetuto (`retake`)

- Per frasi consecutive P e Q, con Q che inizia entro 20 s dalla fine di P e P
  non più lunga di `RETAKE_MAX_SECONDS` (30 s): se le prime c ≥ 3 parole
  normalizzate coincidono → taglio di tutta P.
- **Sicuro** se P termina con «...» oppure se P è interamente l'inizio di Q
  (c = len(P) e len(Q) ≥ len(P)); altrimenti **dubbio**. Esempio: «Non è una
  questione di soldi. Non è una questione di tempo.» ha c = 5 su 6 parole:
  è un'anafora retorica, quindi dubbio.
- Applicata a catena (P1,P2), (P2,P3)…: resta solo l'ultima versione.

Se più regole trovano lo stesso intervallo resta un solo candidato (il primo
trovato), sicuro se almeno una delle regole lo considera sicuro. I candidati
**sicuri** delle regole sono definitivi e non vanno a Claude.

## Passata Claude (`cleanup_llm.py`)

### Blocchi

- Parole divise in blocchi di circa `WINDOW_WORDS` (1.500), spezzati a fine
  frase, con `WINDOW_OVERLAP` (150) parole di contesto condivise.
- Ogni candidato dubbio va al primo blocco che lo contiene per intero (con la
  sovrapposizione un candidato vicino al confine può stare in due blocchi).
- Blocchi elaborati in parallelo (massimo 3); risultati uniti per unione.

### Input

Messaggio utente per blocco:

```
Blocco 2/5 · parole 1350–2849
1350:Buongiorno 1351:a... [pausa 1,4 s] 1352:Ciao 1353:a 1354:tutti, …

Candidati dubbi da valutare:
C1: parole 1512–1513 · ripetizione · «molto molto»
```

Le pause > 1 s sono segnate tra parentesi quadre.

Prompt di sistema (stabile, in italiano):

- ruolo: pulizia del parlato di un video YouTube in italiano registrato di
  getto;
- togliere solo: false partenze, autocorrezioni (frase iniziata e
  riformulata), take ripetuti (di più versioni tenere l'ultima completa),
  parole ripetute per inciampo;
- mai togliere contenuto detto una sola volta, anche se è una digressione;
  mai riscrivere; ripetizioni enfatiche e anafore retoriche restano;
- dopo il taglio la frase che resta deve essere completa e scorrevole;
- tagli indicati solo con numeri di parola (estremi inclusi); `sure: false`
  quando non si è certi; motivo di al massimo 8 parole.

### Output (JSON Schema, `additionalProperties: false`, tutti i campi richiesti)

```json
{
  "verdicts": [{"candidate": 1, "cut": true, "sure": true}],
  "cuts": [{"from_id": 1512, "to_id": 1515, "kind": "self_correction", "sure": false, "reason": "riformula dall'alto/dal basso"}]
}
```

`kind` per i tagli di Claude: `false_start`, `self_correction`, `retake`,
`repetition`.

### Chiamata

- `client.beta.messages.create` con `model=CLAUDE_MODEL` (`claude-opus-5`,
  costante condivisa con i metadati), `max_tokens=16000`, `output_config=
  {"format": {"type": "json_schema", "schema": …}}`,
  `betas=["server-side-fallback-2026-07-01"]`, `fallbacks="default"`.
  Thinking adattivo di default (parametro omesso).
- Risposta: primo blocco di testo → `json.loads` → validazione.
- `stop_reason` `refusal` o `max_tokens` → blocco fallito.
- Costo stimato: ~0,30 $ per un video di 20 minuti.

### Validazione (pura)

- `from_id ≤ to_id`, entrambi nel blocco.
- Durata del singolo taglio (`end` dell'ultima parola − `start` della prima)
  ≤ `MAX_CUT_SECONDS` (30 s); oltre → taglio scartato con avviso.
- Verdetti su candidati inesistenti → ignorati.
- Se i tagli di Claude nel blocco (nuovi + candidati confermati) superano il
  20% delle parole del blocco → risposta del blocco scartata, restano le
  regole, avviso.

## Esito dei tagli

| Origine | Esito | Applicato | Marcatore |
|---|---|---|---|
| regola sicura | — | sì | no |
| regola dubbia | Claude: `cut`, `sure: true` | sì | no |
| regola dubbia | Claude: `cut`, `sure: false` | sì | sì |
| regola dubbia | Claude: `keep` | no (elencato tra i tenuti) | no |
| regola dubbia | nessun verdetto / Claude non disponibile | sì | sì |
| Claude, taglio nuovo | `sure: true` / `false` | sì | solo se `false` |

- Tagli sovrapposti o adiacenti si uniscono a livello di parola; il taglio
  unito è sicuro solo se lo sono tutti i componenti.
- Senza chiave Anthropic o con `--cleanup rules`: solo regole, i dubbi
  applicati con marcatore.

## Da parole a tempi (`cleanup.py`)

Per un taglio delle parole a…b, con `prev` = a−1 e `next` = b+1:

- **Inizio**: se non c'è `prev` → 0,0. Se la pausa `prev.end`→`a.start` è
  ≥ 2·pad → punto più silenzioso in `[prev.end + pad, a.start]`; se più corta
  ma ≥ 20 ms → punto più silenzioso in `[prev.end, a.start]`; se le parole
  sono attaccate → punto più silenzioso entro ±30 ms dal punto medio.
- **Fine**: simmetrico. Se non c'è `next` → durata del video. Pausa
  `b.end`→`next.start` ≥ 2·pad → punto più silenzioso in `[b.end, next.start
  − pad]`; più corta ma ≥ 20 ms → in `[b.end, next.start]`; parole attaccate →
  entro ±30 ms dal punto medio.
- "Più silenzioso" = minimo dell'RMS su finestre da 10 ms dell'audio di
  analisi (16 kHz mono, voce separata), calcolato una volta con numpy.
- `pad` = `--speech-pad`, lo stesso margine delle pause.
- L'allineamento ai frame resta negli export, come oggi.

## Export

### CapCut

- `build_draft(clips, project_name, …)` pura; `generate_capcut_project` fa
  solo I/O.
- Ogni clip può avere `markers: [{"source_time": ce, "title": "…"}]`, dove
  `ce` è la fine del taglio in tempo sorgente.
- Posizione: `target_timerange.start` del primo segmento della clip con
  `source_start ≥ source_time − ½ frame`; se non esiste → fine dell'ultimo
  segmento della clip. Vale anche per `--capcut-single-project`.
- Scrittura: `draft_info["time_marks"] = {"id": UUID, "mark_items": [{"id":
  UUID, "time_range": {"start": µs, "duration": 0}, "color": MARKER_COLOR,
  "title": "…"}]}`; senza marcatori resta `None` come oggi.
- Titolo: `"<tipo>: «<testo tolto>»"`, al massimo 60 caratteri con «…».
- `MARKER_COLOR`: un colore della palette CapCut diverso da `#00c1cd`,
  ricavato in implementazione da un draft reale (creare un marcatore in
  CapCut, cambiarne il colore, leggere il JSON).
- **Mai sovrascrivere**: se la cartella esiste si usa `nome-2`, `nome-3`…;
  `name` e `draft_name` usano il nome finale, che viene stampato.

### Chunk ed EDL

- Nessuna modifica alla logica. Prima di rigenerare i chunk si eliminano i
  `c_*.mp4` esistenti nella cartella `chunks`.

## Report (`output/<video>/`)

- `pulizia.md` (italiano):
  - riepilogo: durata originale → finale; tempo tolto dalle pause; tempo tolto
    dalla pulizia per tipo (conteggio e secondi); numero di marcatori;
    modalità; avvisi (es. blocchi senza Claude);
  - tagli in ordine di tempo: `mm:ss` nella timeline finale · tipo · sicuro o
    dubbio · origine · contesto «…prima **[tolto]** dopo…» · motivo;
  - tenuti: candidati che Claude ha deciso di non tagliare, con contesto.
- `pulizia.json`: `{"version": 1, "mode": "full", "cuts": […], "kept": […],
  "warnings": […]}`.
- `timeline_time` calcolato dai `keep_ranges`: coincide con la posizione in
  CapCut a meno di un frame.

## CLI

- `--cleanup {full,rules,off}` (default `full`). `full` senza
  `ANTHROPIC_API_KEY` → `rules` con messaggio.
- `--cue-word` (default `rifaccio`; stringa vuota = disattivata).
- `--retranscribe`: ignora `words.json` e ritrascrive.
- `--no-metadata`: salta titolo, descrizione e miniatura AI (utile per i
  rilanci di prova, che altrimenti sovrascrivono `metadata.txt` e
  `thumbnail.png` e rifanno la chiamata a pagamento per la miniatura).
- `--no-transcription` implica `--cleanup off`.
- I nuovi parametri vengono stampati nel riepilogo iniziale.

### Riuso di `words.json`

Si riusa se nome, dimensione e durata del video corrispondono (durata entro
0,1 s), la lingua è la stessa e `transcriber` coincide con quello richiesto;
altrimenti, o con `--retranscribe`, si ritrascrive. Se Deepgram aveva fallito
(salvato `whisper`), un rilancio con il default riprova Deepgram.

## Gestione errori

La pulizia non fa mai fallire il video:

- nessuna parola disponibile → pulizia saltata con messaggio;
- Whisper al posto di Deepgram → R2 scatta raramente (manca «...»): avviso;
- errore, rifiuto o risposta non valida di Claude su un blocco → solo regole
  per quel blocco, avviso in console e nel report;
- calcolo dei marcatori fallito → progetto CapCut senza marcatori, avviso;
- `words.json` illeggibile → si ritrascrive.

## Testing

- `pytest` in `requirements-dev.txt` (eccezione `!requirements-dev.txt` nel
  `.gitignore`); `tests/conftest.py` aggiunge `src` al path.
- Dati di prova costruiti in Python (helper `make_words(testo, …)`): niente
  JSON, niente dati del video dell'utente nel repo.
- Test unitari:
  - regole R1–R4, con casi presi dal 16/09 («non è... Non è», «Buongiorno
    a... Ciao», «delle delle», «no no» intatto, «molto molto» dubbio, take
    ripetuto e anafora, «rifaccio» con e senza ripartenza, «lo rifaccio
    domani» che non scatta);
  - blocchi: divisione, sovrapposizione, unione;
  - validazione della risposta di Claude e tabella degli esiti;
  - parole→tempi con segnali RMS sintetici (pausa lunga, corta, parole
    attaccate, prima e ultima parola);
  - `build_draft`: struttura e posizione dei marcatori, anche multi-clip;
    suffisso anti-sovrascrittura su cartella temporanea;
  - report: formattazione di contesto e tempi.
- Claude sostituito da un client finto con risposte registrate: nessuna
  chiamata reale nei test.
- Verifica manuale documentata nel README: CapCut apre il draft senza avvisi;
  marcatori visibili nel punto giusto con titolo e colore; un taglio si
  ripristina trascinando il bordo della clip.

## Banco di prova e criteri di successo

0. Copia del draft CapCut del 16/09 in `output/2026-09-16
   09-10-23/banco-prova/capcut-manuale/` e dell'EDL automatico originale in
   `banco-prova/auto-originale.edl` (serve per B, perché un rilancio
   sovrascrive `premiere_pro.edl`), prima di qualsiasi rilancio.
1. Una ritrascrizione Deepgram del video per ottenere `words.json`.
2. `tools/evaluate_cleanup.py <cartella output>`:
   - estrae una volta l'audio di analisi in `banco-prova/` con
     `extract_audio` e lo riusa;
   - esegue pause + pulizia nella modalità scelta e confronta con il draft
     manuale:
     - M = tempo tolto nel montaggio manuale, B = tolto dalla versione
       automatica attuale (solo pause), E = M \ B (i 158,3 s extra),
       A = tolto dalla nuova pipeline;
     - **copertura** = |A ∩ E| / |E|;
     - **tagli in più** = |A \ M|;
     - suddivisione per durata dei tagli manuali (< 0,3 s, 0,3–1 s, > 1 s) e
       per tipo/origine dei tagli automatici;
   - scrive `banco-prova/risultati-<data-ora>.md`.
3. Taratura di soglie e parametri (anche `--word-gap`/`--speech-pad` se i
   micro-tagli manuali risultano pause da stringere), poi nuova misura.
   `--cleanup rules` è gratuito; un giro `full` costa ~0,30 $.

Criteri provvisori, da confermare dopo la prima misura:

- copertura ≥ 60% dei 158,3 s;
- tagli in più ≤ 10 s, verificati a mano nel report (alcuni potrebbero essere
  inciampi sfuggiti nel montaggio manuale);
- nessuna frase detta una sola volta danneggiata.

## Da verificare in implementazione

1. CapCut 9.4 apre un draft con `time_marks` scritti da noi (verifica
   manuale).
2. Valore di `MARKER_COLOR` dalla palette CapCut.
3. ✅ Verificato in fase di piano: `anthropic` 0.120.2 accetta `output_config`,
   `betas` e `fallbacks="default"` su `client.beta.messages.create`; la
   versione minima in `requirements.txt` sale a `anthropic>=0.120.2`.
4. ✅ Verificato in fase di piano: nell'SDK Deepgram installato (7.6.0) le
   parole espongono `punctuated_word` e `confidence` (lettura con `getattr`).
5. Precisione dei timestamp Deepgram per i micro-tagli, misurata sul banco di
   prova.

## Fuori scope (v1)

Tagli editoriali e durata target; analisi visiva; export FCPXML/Resolve;
traccia con la voce ripulita nel progetto CapCut; rilevamento degli «ehm»
oltre a ciò che già fanno le pause (da decidere dopo la prima misura);
interfaccia di revisione oltre a marcatori e report; più video nel banco di
prova (consigliato in seguito, per non tarare su un solo video).
