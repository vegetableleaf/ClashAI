# Übergabe: Vision-KI-Training — Stand 2026-08-12

Für eine andere KI, die diese Arbeit fortsetzt. Geschrieben, damit sie ohne Rückfragen weiterarbeiten kann.

## Das Projekt, kurz

ClashAI ist ein Clash-Royale-Bot. **Aktiver Code liegt in `icebow/`.** Der alte, regelbasierte Bot in `trol/` ist tabu — nicht anfassen, nicht referenzieren.

**Verbindliche Regeln, die für die gesamte weitere Arbeit gelten:**
- Vor dem Ausliefern testen; wenn etwas nicht getestet werden konnte, das explizit sagen.
- Keine Verbesserungsbehauptung ohne Messung (vorher/nachher, gleicher Prüfsatz).
- `trol/` und bestehende CLI-Unterbefehle nicht ohne Begründung ändern.
- **Nie irgendetwas unter `icebow/data/` löschen.**
- Keine neuen schweren Abhängigkeiten ohne zu fragen.
- Supercell-ToS-Warnungen in README und UI sichtbar halten.
- Keine Netzwerkaufrufe außer den bereits bestehenden (offizielle CR-API in `deck_import.py`, Fandom-Wiki in `card_import.py`, optionaler Discord-Webhook in `monitor.py` — der GitHub/Kaggle-Zugriff für diesen Import wurde mit dem Nutzer abgesprochen, ist also in Ordnung, aber neue Netzwerkziele wieder fragen).
- Keine Telemetrie.
- **Antworten auf Deutsch, Code-Kommentare auf Englisch.**
- **Der Nutzer arbeitet ausschließlich über das ClashAI-Panel (`ClashAI.bat`/`ClashAI.exe`), nie über die Kommandozeile.** Jede Anweisung an ihn muss als Panel-Schritte formuliert werden (Reiter → Kachel → Feld → Knopf), nicht als Befehlszeile. Ausnahme: die Kaggle/GPU-Arbeit unten ist zwangsläufig technischer, weil sie außerhalb des Panels stattfindet — das ist begründet, nicht die Regel gebrochen.

## Wo die Vision-KI herkam (Kurzfassung der Chronologie)

1. Ausgangspunkt vor diesem Arbeitsblock: `presence recall 0.042`, `whitelist 0.015` — praktisch nutzlos.
2. vegetableleaf (Mitentwickler, baut den Simulator) stellte einen Datensatz mit ~1000+ handgelabelten Bildern bereit (`detect.zip`). Import brachte `presence 0.750`, `whitelist 0.706` (Prüftor bestanden), **9.057 Boxen, 2.509 Trainingsbilder**.
3. Trotzdem Stillstand: 83 von 133 gemessenen Klassen hatten ≤5 Beispiele im Prüfsatz. Kein Training behebt einen Mangel an echten Bildern.
4. Fund: **KataCR / Clash-Royale-Detection-Dataset** (github.com/wty-yy/Clash-Royale-Detection-Dataset, MIT-Lizenz) — 6.939 von Hand gelabelte Frames. Import über das neu gebaute `icebow/src/clashrl/katacr_boxes.py` (CLI: `katacr-boxes --src <Pfad>`).
   - Vier Entscheidungen dabei absichtlich so und nicht anders: alles geht in **train**, nie in val (ihr eigener val-Split teilt alle Episoden mit ihrem train-Split, wäre also eine Verunreinigung); **kein Umskalieren** (gemessenes Größenverhältnis 0,929 über 60 gemeinsame Klassen — praktisch identisch); Frames mit einer Einheit, die unsere Liste nicht kennt, werden **komplett verworfen**, nicht nur die Box (sonst lernt das Modell, sichtbare Einheiten zu unterdrücken); die Freund/Feind-Spalte ihrer Labels landet in `katacr_team.json`, nicht in den Labeldateien (Ultralytics läse eine 6. Spalte als Polygon und stürzt ab).
   - Ergebnis: **38.265 Boxen, 8.731 Trainingsbilder**, 14 Klassen von 0 auf echte Beispiele gehoben (u. a. `mega_minion`, `graveyard`, `mortar`, `zap`, `poison`, `lightning`, `freeze`).
   - Vor dem Import geprüft und bestätigt: keine Überschneidung mit unserem 401-Bilder-Prüfsatz (per Bildhash verglichen, die ähnlichsten Paare von Hand angeschaut — verschiedene Matches, nur dasselbe Arena-Layout).
5. Lokales Training (`yolo11s`, Bildgröße 960, RTX 3070 8 GB, Stapelgröße 3 automatisch) auf den 38.265 Boxen, 60 Epochen, ~4,8 Stunden:
   ```
   mAP50      0.775   (vorher 0.710)
   mAP50-95   0.534   (vorher 0.477)
   precision  0.736
   recall     0.685
   ```
   **Das ist besser als vegetableleafs eigenes bestes Modell** (sein `board-23`: mAP50 0.758, mAP50-95 0.522 — gemessen auf seinem eigenen Prüfsatz, der zu 97 % mit unserem identisch ist, also ein fairer Vergleich).

## Aktueller Stand — dieses Modell ist installiert und sicher

```
icebow/runs/detect/vision/weights/best.pt   <- DAS aktuell installierte, funktionierende Modell
icebow/runs/detect/vision/model_card.json   <- beschreibt genau dieses best.pt
```

```json
{
  "model": "yolo11s.pt", "imgsz": 960,
  "epochs_run": 60.0, "epochs": 58.0,
  "mAP50": 0.77545, "mAP50_95": 0.53353,
  "precision": 0.73573, "recall": 0.68489,
  "trained_on_boxes": 37768
}
```

**Wichtig: dieses Modell ist bereits ein Erfolg, unabhängig davon, was mit Kaggle passiert.** Alles, was unten beschrieben ist, ist der Versuch, mit einem größeren Netz noch mehr herauszuholen — kein notwendiger nächster Schritt.

Sicherungskopien liegen daneben (`best_pre_katacr.pt`, `best_previous.pt`) — Reste aus dem Trainingsverlauf, für den Notfall, aber nicht mehr nötig, da `best.pt` beide übertrifft.

## Der Kaggle-Versuch: warum, was gebaut wurde, was schiefging

### Warum

Lokal (RTX 3070, 8 GB) erzwingt Bildgröße 960 eine Stapelgröße von nur 3 und begrenzt das Netz auf `yolo11s` (9,5 Mio. Parameter). Ein größeres Netz (`yolo11m`, 20,2 Mio. Parameter) könnte noch besser werden — aber nicht mit 8 GB.

### Was das GPU-Ziel erfüllen muss (gemessen, nicht geschätzt)

- **Mindestens ~15 GB Grafikspeicher.** Gemessen: `yolo11m` bei Bildgröße 960 und 225 Klassen läuft auf der lokalen 8-GB-Karte in einen Speicherüberlauf bei Stapelgröße 8 und fällt auf Stapelgröße 1 zurück — de facto unbrauchbar. Auf einer Kaggle-T4 (14,56 GB nutzbar) fand die eigene Speicherprüfung von Ultralytics eine sichere Stapelgröße von 2 pro Karte.
- **CUDA-fähiges PyTorch, nicht CPU.** Kaggle liefert das vorinstalliert — aber `pip install ultralytics` ohne Vorsicht ersetzt es durch eine reine CPU-Version von PyPI (siehe Fallstricke unten).
- **Internetzugang** (einmalig, für `pip install ultralytics` und den Download des `yolo11m.pt`-Grundmodells, ~38,8 MB).
- **Mehrere Grafikkarten sind ein PLUS, aber eine zusätzliche Fehlerquelle.** Zwei T4-Karten verdoppeln den Durchsatz, brauchen aber Mehrkarten-Training (DDP), was mehr schiefgehen lassen kann als eine einzelne Karte.
- Bei zwei T4-Karten und Stapelgröße 4 gesamt: **~8 Minuten pro Epoche**, 60 Epochen ≈ 8 Stunden — passt in Kaggles 12-Stunden-Grenze pro Sitzung, aber knapp.

### Was gebaut wurde (alles im Repo, committet)

| Datei | Zweck |
|---|---|
| `icebow/src/clashrl/detect_pack.py` (CLI: `detect-pack`) | Packt den Datensatz für den Export. Schreibt standardmäßig **einen einzigen** `detect.tar` **innerhalb** eines Zips — Kaggles Uploader stürzt beim Auflisten von ~19.000 losen Dateien ab, ein Tar umgeht das. `--own-only` lässt die KataCR-Bilder weg (Ziel muss sie schon haben). `--many-files` erzwingt lose Dateien. |
| `icebow/data/exports/clashai-detect.zip` | Der fertige Datensatz, **1,16 GB**, bereits zu Kaggle hochgeladen (Datensatz-Slug beim Nutzer: `craftingbrick/1training`, taucht unter `/kaggle/input/datasets/craftingbrick/1training/` auf — Kaggle verschachtelt Datensätze unterschiedlich tief je nach Konto, deshalb sucht das Notebook rekursiv). |
| `icebow/tools/detect/kaggle_train.py` | Die eigentliche Trainingslogik, **versionierte Quelle der Wahrheit**. Wird von `detect-pack` automatisch neben das Zip kopiert (als `.py` und als `.ipynb`). |
| `icebow/data/exports/clashai-kaggle.ipynb` | Dasselbe Skript als Jupyter-Notebook — **zum Importieren, nicht zum Einfügen** (Copy-Paste in eine Zelle riskiert stille Einrückungsfehler in Python). |

**Wichtige Lektionen, die in `kaggle_train.py` bereits eingebaut sind** (nicht erneut lösen, falls sie wieder auftauchen — sie sind schon behoben):
1. Datensatz-Suche ist **rekursiv** (`rglob`), weil Kaggle Datensätze unterschiedlich tief verschachtelt (ein Level bei manchen Konten, drei bei diesem: `/kaggle/input/datasets/<user>/<name>/`).
2. `data.yaml` wird **im Notebook aus `classes.txt` neu gebaut**, nie mitgeliefert — die lokale `data.yaml` enthält einen absoluten Windows-Pfad, der unter Linux bedeutungslos ist.
3. `pip install ultralytics` **pinnt PyTorch über eine Constraints-Datei** an die bereits installierte Version, statt frei aufzulösen — sonst zieht pip eine reine CPU-Version von PyPI und ersetzt Kaggles CUDA-Build lautlos. Ein Vorab-Check bricht sofort ab, falls PyTorch in der aktuellen Sitzung schon kaputt ist (`+cpu` im Versionsstring), mit der Anweisung, die Sitzung neu zu starten — ein erneutes Ausführen der Zelle kann das nicht reparieren.
4. **AutoBatch (automatische Stapelgrößen-Suche) funktioniert nicht bei mehreren Grafikkarten** — Ultralytics wirft dann einen Fehler. Das Notebook misst den sicheren Wert selbst auf einer Karte (über `DetectionModel` mit der **echten** Klassenzahl neu aufgebaut, **nicht** die geladene Modell-Datei — die hätte noch 80 COCO-Klassen und keine Verlustberechnung, was den Messwert um das 6-Fache verfälscht hatte) und multipliziert mit der Kartenzahl.

### Was schiefging (und warum es kein Code-Fehler war)

Drei Abstürze in Folge, alle durch dieselbe Ursache: **eine interaktive Kaggle-„Draft Session" erlaubt nur eine lebende Verbindung.** Jedes Mal, wenn sich der Nutzer von einem neuen Gerät/Tab neu verbunden hat (Handy, neuer Browser-Tab), hat Kaggle ein **KeyboardInterrupt (SIGINT)** an den laufenden Trainingsprozess geschickt, um die alte Verbindung für die neue freizumachen. Das killt das Training, egal wie stabil der Code ist.

**Bestätigt durch die Absturzprotokolle:** `torch/distributed/elastic/agent/server/api.py] Received 2 death signal` gefolgt von `KeyboardInterrupt` in beiden Rängen (Mehrkarten-Prozessen) — ein gezieltes Signal, kein Speicherüberlauf, kein Datenfehler.

**Ein Lauf hat trotzdem 7 Epochen geschafft** bevor er unterbrochen wurde: `mAP50 0.634, mAP50-95 0.435, recall 0.551` nach ~55 Minuten — auf einem guten Weg, die lokalen 0,775 zu übertreffen, aber noch nicht so weit. Diese Gewichte lagen zuletzt unter `/kaggle/working/runs/vision/weights/best.pt` in der Kaggle-Sitzung — **Stand offen, ob sie gesichert/heruntergeladen wurden.** Falls die Sitzung inzwischen abgelaufen oder neu gestartet ist, sind sie wahrscheinlich weg (Kaggle-Sitzungsspeicher ist flüchtig, nichts wird automatisch gesichert).

## Handlungsoptionen für den nächsten Anlauf

Sortiert nach Aufwand:

1. **„Save Version" → „Save & Run All" statt einer Draft Session verwenden.** Läuft als eigenständiger Hintergrundauftrag ohne lebende Verbindung — nichts, womit man ihn durch Neuverbinden aus Versehen unterbrechen kann. Gleicher Datensatz, gleiches Notebook, nur ein anderer Startknopf. **Das ist die naheliegende erste Wahl**, weil sie die tatsächliche Ursache behebt, ohne Geld zu kosten.
2. **Hier aufhören.** Das installierte `yolo11s`-Modell (0,775 mAP50) ist bereits besser als vegetableleafs bestes. Der ganze Kaggle-Versuch ist ein Bonus, keine Notwendigkeit.
3. **Eine gemietete Grafikkarte** (vast.ai, RunPod — wenige Cent bis ~1 € für den ganzen Lauf). Voll zuverlässig, da eine eigene Maschine ohne Sitzungs-Konkurrenz. Braucht ein Konto mit Zahlungsmethode — **das trägt ausschließlich der Nutzer selbst ein**, niemals die KI (Zahlungsdaten sind tabu).
4. **Nur eine Grafikkarte statt zwei** auf Kaggle — nimmt die Mehrkarten-Fehleranfälligkeit raus, aber eine Karte statt zwei bedeutet ungefähr die doppelte Zeit pro Epoche; 60 Epochen würden dann über Kaggles 12-Stunden-Grenze laufen. Nur mit weniger Epochen sinnvoll, also eine Notlösung.

## Falls die Kaggle-Sitzung mit dem Epoche-7-Modell noch lebt

Vor allem anderen prüfen und sichern:
```python
import subprocess
print(subprocess.run(["ls", "-la", "/kaggle/working/runs/vision/weights/"],
                     capture_output=True, text=True).stdout)
print(subprocess.run(["tail", "-6", "/kaggle/working/runs/vision/results.csv"],
                     capture_output=True, text=True).stdout)
```
Wenn `best.pt` dort noch existiert: über den Dateibereich im Notebook herunterladen, **bevor** irgendetwas anderes versucht wird. Diese Gewichte sind noch nicht so gut wie das installierte Modell (mAP50 0,634 gegen 0,775 bei Epoche 7), aber ein Beleg dafür, dass die Kurve stieg — verlustfrei mitzunehmen, falls greifbar.

## Prüfsatz-Disziplin — nicht brechen

`icebow/data/detect/images/val/` (401 Bilder) ist der **feste Vergleichsmaßstab** für alle Modellgenerationen. Nie neu mischen, nie verkleinern. Jede neue Kaggle-Version muss auf **genau diesem** Prüfsatz gemessen werden, sonst ist „besser" nicht mehr belegbar. Der lokale Befehl dafür: `run.py detect-eval` (misst gegen `images/val`, gibt `presence`, `whitelist ident`, pro-Klasse-Recall aus).
