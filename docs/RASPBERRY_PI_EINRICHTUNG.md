# Raspberry Pi einrichten und Bus-Abfahrtsanzeige übertragen

Schritt-für-Schritt-Anleitung: vom leeren Raspberry Pi bis zum laufenden Dienst mit E-Ink-Display.

**Zielpfad auf dem Pi:** `/home/pi/bus-abfahrtanzeige`  
**Hardware:** Raspberry Pi Zero 2 W (oder vergleichbar), Waveshare 7,5″ E-Ink V2 (800×480), microSD-Karte (min. 16 GB empfohlen), USB-C-Netzteil (ausreichend Strom für Pi + Display).

---

## Übersicht der Phasen

| Phase | Inhalt |
|-------|--------|
| A | SD-Karte vorbereiten (OS, SSH, WLAN) |
| B | Pi starten, IP finden, per SSH verbinden |
| C | System aktualisieren, Zeitzone, SPI |
| D | Projekt übertragen, Python-Umgebung |
| E | Waveshare-Treiber, Display testen |
| F | Autostart mit systemd |
| G | Fehlersuche (Kurzreferenz) |

---

## Phase A — SD-Karte vorbereiten

### Schritt A1 — Raspberry Pi OS Lite herunterladen

1. Auf deinem Mac/PC den **Raspberry Pi Imager** installieren:  
   https://www.raspberrypi.com/software/
2. Imager starten → **Choose Device** → dein Modell (z. B. *Raspberry Pi Zero 2 W*).
3. **Choose OS** → **Raspberry Pi OS (other)** → **Raspberry Pi OS Lite (64-bit)**.  
   *Lite* = ohne Desktop, spart Ressourcen und passt zum Dauerbetrieb.
4. **Choose Storage** → deine microSD-Karte (alle Daten auf der Karte werden gelöscht).

### Schritt A2 — Erweiterte Einstellungen (empfohlen: alles in einem Schritt)

Vor dem Schreiben auf die Karte auf das **Zahnrad-Symbol** (Einstellungen) klicken und mindestens setzen:

| Einstellung | Empfehlung |
|-------------|------------|
| Hostname | `raspberrypi` (oder z. B. `bus-anzeige`) |
| Benutzer und Passwort | z. B. Benutzer `pi`, sicheres Passwort |
| WLAN | SSID und Passwort deines Heimnetzes |
| WLAN-Land | `DE` |
| SSH aktivieren | **Ja**, Authentifizierung: Passwort (oder SSH-Key, wenn du einen hinterlegst) |
| Locale | Zeitzone `Europe/Berlin`, Tastaturlayout `de` |

Mit **Speichern** bestätigen, dann **Write** / **Schreiben** starten und warten, bis die Karte fertig ist.

> **Hinweis:** Wenn du im Imager einen **eigenen Benutzernamen** (nicht `pi`) wählst, musst du in allen folgenden Befehlen `pi` durch deinen Benutzernamen ersetzen und in `deploy/bus-abfahrtanzeige.service` die Zeilen `User=` und `Group=` anpassen.

### Schritt A3 — Alternative: SSH- und WLAN-Dateien manuell anlegen

Falls du **ohne** Imager-Einstellungen arbeitest (oder die Boot-Partition nach dem Schreiben bearbeiten willst):

1. SD-Karte auswerfen, erneut einstecken — auf dem Mac erscheint oft die Partition **`bootfs`** (oder `boot`).
2. **SSH aktivieren:** leere Datei namens `ssh` (ohne Endung) im Root der Boot-Partition anlegen:

   ```bash
   touch /Volumes/bootfs/ssh
   ```

3. **WLAN einrichten:** Datei `wpa_supplicant.conf` im Root der Boot-Partition anlegen:

   ```ini
   ctrl_interface=DIR=/var/run/wpa_supplicant GROUP=netdev
   update_config=1
   country=DE

   network={
       ssid="DEIN_WLAN_NAME"
       psk="DEIN_WLAN_PASSWORT"
       key_mgmt=WPA-PSK
   }
   ```

   `ssid` und `psk` durch deine echten WLAN-Daten ersetzen. Anführungszeichen beibehalten.

4. SD-Karte sicher auswerfen (`diskutil eject` auf dem Mac).

### Schritt A4 — SD-Karte einsetzen und Pi anschließen

1. microSD-Karte in den Raspberry Pi stecken.
2. **E-Ink-Display noch nicht zwingend** verkabeln — für die ersten Tests reicht Strom + WLAN.
3. USB-C-Netzteil anschließen (qualitativ ausreichend, z. B. 2,5 A für Zero 2 W).
4. **1–2 Minuten warten**, bis der Pi hochgefahren und im WLAN ist (LED-Aktivität beobachten).

---

## Phase B — IP-Adresse finden und per SSH verbinden

### Schritt B1 — IP-Adresse ermitteln

Probiere die Wege **der Reihe nach**:

**Variante 1 — Hostname (einfachste):**

```bash
ping -c 3 raspberrypi.local
```

Wenn Antwort kommt, ist der Host erreichbar. SSH dann mit:

```bash
ssh pi@raspberrypi.local
```

**Variante 2 — Router / Fritzbox:**

Im Webinterface des Routers unter *Verbundene Geräte* / *DHCP* nach `raspberrypi` oder dem gesetzten Hostnamen suchen und die **IPv4-Adresse** notieren.

**Variante 3 — vom Mac aus im Netz scannen:**

```bash
arp -a | grep -i "b8:27:eb\|dc:a6:32\|e4:5f:01"
```

(Raspberry-Pi-MAC-Adressen beginnen oft mit diesen Präfixen — nicht immer zuverlässig.)

**Variante 4 — Monitor + Tastatur (falls WLAN/SSH scheitert):**

HDMI-Adapter (Micro-HDMI) und USB-Tastatur am Pi, einloggen, dann:

```bash
hostname -I
```

### Schritt B2 — Erste SSH-Verbindung

Auf dem Mac im Terminal (Passwort ist das aus dem Imager / deine Wahl):

```bash
ssh pi@raspberrypi.local
```

oder mit IP:

```bash
ssh pi@192.168.x.x
```

Bei der ersten Verbindung `yes` eingeben (Host-Key bestätigen), dann Passwort.

**Erfolg:** Die Eingabeaufforderung zeigt z. B. `pi@raspberrypi:~ $`.

---

## Phase C — System vorbereiten

Alle folgenden Befehle **auf dem Pi per SSH** ausführen.

### Schritt C1 — Paketquellen aktualisieren und Basis-Pakete

```bash
sudo apt update
sudo apt full-upgrade -y
sudo apt install -y python3-venv python3-pip git fonts-dejavu-core \
  python3-lgpio python3-gpiozero python3-spidev
```

`fonts-dejavu-core` sorgt für lesbare Schrift im PNG. **`python3-lgpio`** und **`python3-gpiozero`** braucht die Waveshare-Library für GPIO — auf Raspberry Pi OS (Bookworm und neuer) reicht `pip install gpiozero` allein nicht; ohne `lgpio` fällt gpiozero auf eine veraltete sysfs-Schnittstelle zurück (`NativePinFactoryFallback`, Fehler an `/sys/class/gpio/gpio24/…`).

### Schritt C2 — Zeitzone und Locale

```bash
sudo timedatectl set-timezone Europe/Berlin
timedatectl
```

Die angezeigte Zeit sollte mit der lokalen Uhrzeit übereinstimmen (wichtig für Abfahrtszeiten).

Optional interaktiv:

```bash
sudo raspi-config
```

→ *Localisation Options* → *Timezone* → *Europe* → *Berlin*.

### Schritt C3 — SPI für das E-Ink-Display aktivieren

```bash
sudo raspi-config
```

→ *Interface Options* → *SPI* → **Yes** → Finish → bei Aufforderung **Reboot**:

```bash
sudo reboot
```

Nach dem Neustart erneut per SSH verbinden.

---

## Phase D — Projekt auf den Pi übertragen

### Schritt D1 — Projekt vom Mac kopieren

**Auf dem Mac** (neues Terminal-Fenster, nicht auf dem Pi), im Ordner mit dem Projekt:

```bash
scp -r "/Users/klaasewald/Documents/Cursor/Bus Abfahrtanzeige Flur" pi@raspberrypi.local:/home/pi/bus-abfahrtanzeige
```

Pfad und Benutzername ggf. anpassen. Der Kopiervorgang kann einige Minuten dauern.

**Alternative mit rsync** (kopiert nur Änderungen, überspringt `.git` optional):

```bash
rsync -av --progress --exclude '.git' \
  "/Users/klaasewald/Documents/Cursor/Bus Abfahrtanzeige Flur/" \
  pi@raspberrypi.local:/home/pi/bus-abfahrtanzeige/
```

### Schritt D2 — Struktur auf dem Pi prüfen

Wieder **per SSH auf dem Pi**:

```bash
ls -la /home/pi/bus-abfahrtanzeige
```

Es sollten u. a. vorhanden sein: `run.py`, `run_bus_display.py`, `show_eink.py`, `bus_anzeige/`, `requirements.txt`, `deploy/`.

### Schritt D3 — Virtuelle Python-Umgebung anlegen

```bash
cd /home/pi/bus-abfahrtanzeige
python3 -m venv --system-site-packages venv
./venv/bin/pip install --upgrade pip
./venv/bin/pip install -r requirements-raspberrypi.txt
```

`--system-site-packages` ist nötig, damit das venv die per **apt** installierten Pakete **`lgpio`** und **`gpiozero`** sieht (Waveshare `epdconfig.py`). Über pip kommt zusätzlich **`spidev`** (`requirements-raspberrypi.txt`).

**Bereits ein venv ohne `--system-site-packages`?** Einmal neu anlegen:

```bash
cd /home/pi/bus-abfahrtanzeige
rm -rf venv
python3 -m venv --system-site-packages venv
./venv/bin/pip install --upgrade pip
./venv/bin/pip install -r requirements-raspberrypi.txt
```

Falls du zuvor `gpiozero` per pip installiert hast: `./venv/bin/pip uninstall -y gpiozero` (damit die apt-Version mit `lgpio` genutzt wird).

### Schritt D4 — Busdaten und PNG testen (ohne Display)

```bash
cd /home/pi/bus-abfahrtanzeige
./venv/bin/python3 run.py
```

Erwartung:

- Konsolenausgabe mit Abfahrten (Innenstadt / Außerhalb / ggf. Fehlerbereich)
- Bei Änderung: `PNG gespeichert: …/output/abfahrtsplan.png`

Mit **Strg+C** beenden.

Prüfen, ob die PNG existiert:

```bash
ls -la /home/pi/bus-abfahrtanzeige/output/abfahrtsplan.png
```

---

## Phase E — Waveshare-Treiber und E-Ink

### Schritt E1 — Waveshare-Bibliothek klonen

```bash
cd ~
git clone https://github.com/waveshare/e-Paper.git
```

Pfad zur Library (für später merken):

```text
/home/pi/e-Paper/RaspberryPi_JetsonNano/python/lib
```

Test, ob das Paket da ist:

```bash
ls /home/pi/e-Paper/RaspberryPi_JetsonNano/python/lib/waveshare_epd
```

### Schritt E2 — Display verkabeln

Laut Waveshare-Anleitung für **7,5″ V2** und README (SPI):

| Raspberry Pi | E-Ink |
|--------------|-------|
| 3,3 V | VCC |
| GND | GND |
| GPIO10 (MOSI) | DIN |
| GPIO11 (SCLK) | CLK |

Weitere Pins (CS, RST, BUSY) je nach HAT/Modul — **immer die mitgelieferte Waveshare-Dokumentation** für dein konkretes Board verwenden.

Pi danach ggf. kurz vom Strom trennen, verkabeln, wieder starten.

### Schritt E3 — E-Ink einmalig testen

Umgebungsvariable setzen und Anzeige starten (in einem Terminal):

```bash
cd /home/pi/bus-abfahrtanzeige
export WSEPD_LIB=/home/pi/e-Paper/RaspberryPi_JetsonNano/python/lib
./venv/bin/python3 show_eink.py --verbose
```

Das Skript wartet auf `output/abfahrtsplan.png`. Wenn `run.py` die Datei bereits erzeugt hat, sollte das Panel aktualisieren.

**In einem zweiten SSH-Fenster** optional Bus-Polling parallel:

```bash
cd /home/pi/bus-abfahrtanzeige
./venv/bin/python3 run.py
```

Oder beides zusammen testen:

```bash
cd /home/pi/bus-abfahrtanzeige
export WSEPD_LIB=/home/pi/e-Paper/RaspberryPi_JetsonNano/python/lib
./venv/bin/python3 run_bus_display.py
```

Beenden mit **Strg+C**.

---

## Phase F — Autostart mit systemd

### Schritt F1 — Service-Datei anpassen (falls nötig)

```bash
nano /home/pi/bus-abfahrtanzeige/deploy/bus-abfahrtanzeige.service
```

Prüfen:

- `User=` und `Group=` passen zu deinem Pi-Benutzer (Standard: `pi`)
- `WorkingDirectory=/home/pi/bus-abfahrtanzeige`
- `Environment=WSEPD_LIB=/home/pi/e-Paper/RaspberryPi_JetsonNano/python/lib`
- `ExecStart=…/venv/bin/python3 …/run_bus_display.py`

**Nur Bus + PNG ohne E-Ink-Hardware:** `ExecStart` auf `run.py` ändern statt `run_bus_display.py`.

### Schritt F2 — Dienst installieren und starten

```bash
sudo cp /home/pi/bus-abfahrtanzeige/deploy/bus-abfahrtanzeige.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable bus-abfahrtanzeige.service
sudo systemctl start bus-abfahrtanzeige.service
```

### Schritt F3 — Status und Logs prüfen

```bash
sudo systemctl status bus-abfahrtanzeige.service
```

Live-Logs:

```bash
journalctl -u bus-abfahrtanzeige.service -f
```

Beenden der Log-Ansicht: **Strg+C**.

Dienst stoppen / neu starten:

```bash
sudo systemctl stop bus-abfahrtanzeige.service
sudo systemctl restart bus-abfahrtanzeige.service
```

Nach einem **Stromausfall** startet der Dienst automatisch (wegen `enable`).

---

## Phase G — Fehlersuche (Kurzreferenz)

| Problem | Was prüfen |
|---------|------------|
| SSH geht nicht | WLAN/SSID in `wpa_supplicant.conf` oder Imager; Pi 2 Min warten; IP im Router |
| `ping raspberrypi.local` schlägt fehl | Hostname im Imager; ggf. direkte IP aus dem Router |
| `run.py` — API-Fehler | Internet am Pi: `ping -c 3 8.8.8.8`; Firewall im Router |
| Kein PNG | `output/` beschreibbar; Fehlermeldung in der Konsole |
| `No module named 'spidev'` | `./venv/bin/pip install -r requirements-raspberrypi.txt` |
| `NativePinFactoryFallback` / `gpio24` / `Invalid argument` | `sudo apt install python3-lgpio python3-gpiozero`; venv mit `--system-site-packages` neu anlegen (siehe D3); ggf. `pip uninstall gpiozero` |
| `waveshare_epd nicht gefunden` | `WSEPD_LIB` gesetzt; Pfad zu `…/python/lib` korrekt |
| Display bleibt weiß | SPI in `raspi-config` aktiv; Verkabelung; richtiges Modul **7,5″ V2** |
| Schrift sehr klein/unschön | `sudo apt install fonts-dejavu-core` |
| Falsche Uhrzeit | `timedatectl`; Zeitzone `Europe/Berlin` |
| Dienst startet nicht | `journalctl -u bus-abfahrtanzeige.service -n 50` |

---

## Checkliste „fertig eingerichtet“

- [ ] Raspberry Pi OS Lite auf SD, SSH + WLAN funktionieren
- [ ] SSH-Verbindung vom Mac aus stabil
- [ ] Zeitzone `Europe/Berlin`, Uhrzeit stimmt
- [ ] SPI aktiviert
- [ ] Projekt unter `/home/pi/bus-abfahrtanzeige`, `venv` installiert
- [ ] `run.py` erzeugt `output/abfahrtsplan.png`
- [ ] Waveshare-Library unter `/home/pi/e-Paper/…`
- [ ] `run_bus_display.py` aktualisiert das E-Ink
- [ ] `bus-abfahrtanzeige.service` enabled und `active (running)`

---

## Nützliche Befehle im Alltag

```bash
# Projektordner
cd /home/pi/bus-abfahrtanzeige

# Manuell testen (ohne systemd)
./venv/bin/python3 run.py

# Mit Display
export WSEPD_LIB=/home/pi/e-Paper/RaspberryPi_JetsonNano/python/lib
./venv/bin/python3 run_bus_display.py

# Dienst-Status
sudo systemctl status bus-abfahrtanzeige.service
```

Weitere technische Details zum Programm: [README.md](../README.md).
