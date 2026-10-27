"""
LV3: alat za tablice 10.7 (mjerenja na sabirnici) i 10.8 (rucno sastavljen okvir).

Pokretanje:  python sabirnica_alat.py
Potrebno:    pip install pyserial customtkinter
Prije spajanja zatvoriti QModMaster i ostale alate, jer drze isti COM port.

Napomena o mjerenju vremena: racunalo vidi samo trenutke kad USB pretvarac preda
bajtove, pa izmjereno vrijeme sadrzi i kasnjenje USB veze (obicno 1 do 16 ms).
Trajanje bita i tocno kasnjenje odgovora mjere se osciloskopom, a ovaj alat daje
izracunate vrijednosti, broj bajtova i grubu provjeru vremena s racunala.
"""

import csv
import os
import queue
import statistics
import sys
import threading
import time
import tkinter as tk
from tkinter import messagebox, ttk

import customtkinter as ctk
import serial
import serial.tools.list_ports

BRZINA = 9600
BITOVA_PO_ZNAKU = 10          # 8N1: start, 8 podatkovnih, stop
PD03_MS = 2.0                 # kasnjenje odgovora upisano u PD-03

POZADINA, KARTICA, RUB = "#0b1220", "#131c2e", "#22304a"
TEKST, PRIGUSENO = "#e2e8f0", "#8a9ab5"
ZELENA, PLAVA, CRVENA, NARANCASTA = "#22c55e", "#38bdf8", "#ef4444", "#f59e0b"


# ============================================================ Modbus pomocno
def crc16_koraci(buf: bytes):
    """CRC-16 Modbus uz vrijednost registra nakon svakog bajta (za tablicu postupka)."""
    crc, koraci = 0xFFFF, []
    for b in buf:
        crc ^= b
        for _ in range(8):
            crc = (crc >> 1) ^ 0xA001 if crc & 1 else crc >> 1
        koraci.append((b, crc))
    return crc, koraci


def crc16(buf: bytes) -> int:
    return crc16_koraci(buf)[0]


def hexs(b: bytes) -> str:
    return " ".join(f"{x:02X}" for x in b)


def t_znak_ms() -> float:
    return BITOVA_PO_ZNAKU / BRZINA * 1000


def slozi_okvir(slave, funkcija, adresa, vrijednost):
    tijelo = bytes([slave, funkcija, adresa >> 8, adresa & 0xFF, (vrijednost >> 8) & 0xFF, vrijednost & 0xFF])
    crc, koraci = crc16_koraci(tijelo)
    return tijelo + bytes([crc & 0xFF, crc >> 8]), crc, koraci


def znacenje_zahtjeva(funkcija):
    drugi = "Broj registara" if funkcija == 0x03 else "Vrijednost koja se upisuje"
    return ["Adresa Slave uređaja",
            "Funkcijski kod, " + ("čitanje registara" if funkcija == 0x03 else "upis jednog registra"),
            "Adresa registra, viši bajt", "Adresa registra, niži bajt",
            f"{drugi}, viši bajt", f"{drugi}, niži bajt",
            "CRC-16, niži bajt", "CRC-16, viši bajt"]


def rastumaci_odgovor(odg: bytes, funkcija: int):
    """Vraca listu (bajt, znacenje) i poruku o ispravnosti odgovora."""
    if len(odg) < 5:
        return [], "Nema odgovora ili je odgovor prekratak"
    redovi = [(odg[0], "Adresa Slave uređaja")]
    crc_ok = crc16(odg[:-2]) == odg[-2] | (odg[-1] << 8)
    if odg[1] == funkcija | 0x80:
        redovi += [(odg[1], "Funkcijski kod s postavljenim bitom greške"), (odg[2], "Šifra iznimke")]
    elif funkcija == 0x03:
        n = odg[2]
        redovi += [(odg[1], "Funkcijski kod, čitanje"), (odg[2], f"Broj podatkovnih bajtova ({n})")]
        for i in range(n):
            redovi.append((odg[3 + i], f"Podatak {i // 2 + 1}, {'viši' if i % 2 == 0 else 'niži'} bajt"))
    else:
        imena = ["Funkcijski kod, upis", "Adresa registra, viši bajt", "Adresa registra, niži bajt",
                 "Vrijednost, viši bajt", "Vrijednost, niži bajt"]
        redovi += list(zip(odg[1:6], imena))
    redovi += [(odg[-2], "CRC-16, niži bajt"), (odg[-1], "CRC-16, viši bajt")]
    poruka = "CRC odgovora je ispravan" if crc_ok else "CRC odgovora NIJE ispravan"
    if funkcija == 0x03 and odg[1] == 0x03 and len(odg) >= 7:
        v = (odg[3] << 8) | odg[4]
        poruka += f"  ·  prvi podatak = {v} (0x{v:04X})"
    return redovi, poruka


# ============================================================ veza
class Veza:
    def __init__(self, port):
        self.ser = serial.Serial(port, BRZINA, bytesize=8, parity="N", stopbits=1, timeout=0)

    def zatvori(self):
        self.ser.close()

    def transakcija(self, okvir: bytes, cekanje=0.3, tisina=0.005):
        """Salje okvir i biljezi trenutke: slanje, prvi primljeni bajt, zadnji primljeni bajt."""
        self.ser.reset_input_buffer()
        t0 = time.perf_counter()
        self.ser.write(okvir)
        self.ser.flush()
        t_poslano = time.perf_counter()
        buf, t_prvi, t_zadnji = bytearray(), None, None
        while time.perf_counter() - t0 < cekanje:
            n = self.ser.in_waiting
            if n:
                t = time.perf_counter()
                buf += self.ser.read(n)
                t_prvi = t_prvi or t
                t_zadnji = t
            elif t_zadnji and time.perf_counter() - t_zadnji > tisina:
                break
            time.sleep(0.0002)
        return bytes(buf), t0, t_poslano, t_prvi, t_zadnji


class DemoVeza:
    """Simulirani pretvarac: odgovara nakon kasnjenja PD-03 i vremena prijenosa."""

    def zatvori(self):
        pass

    def transakcija(self, okvir, cekanje=0.3, tisina=0.005):
        t0 = time.perf_counter()
        t_poslano = t0 + len(okvir) * t_znak_ms() / 1000
        if okvir[1] == 0x03:
            tijelo = bytes([okvir[0], 0x03, 0x02, 0x09, 0xC4])
        else:
            tijelo = okvir[:6]
        c = crc16(tijelo)
        odg = tijelo + bytes([c & 0xFF, c >> 8])
        t_prvi = t_poslano + (PD03_MS + 0.4) / 1000 + 0.001     # 1 ms za USB
        t_zadnji = t_prvi + (len(odg) - 1) * t_znak_ms() / 1000
        time.sleep(max(0.0, t_zadnji - time.perf_counter()) + tisina)
        return odg, t0, t_poslano, t_prvi, t_zadnji


# ============================================================ aplikacija
class Alat(ctk.CTk):
    def __init__(self):
        super().__init__()
        ctk.set_appearance_mode("dark")
        self.title("LV3: sabirnica, tablice 10.7 i 10.8")
        self.geometry("1220x640")
        self.minsize(1000, 560)
        self.after(0, lambda: self.state("zoomed"))
        self.configure(fg_color=POZADINA)
        self.veza = None
        self.demo = False
        self.rezultati = queue.Queue()
        self.zadnje_107 = None

        stil = ttk.Style()
        stil.theme_use("clam")
        stil.configure("T.Treeview", background=KARTICA, fieldbackground=KARTICA, foreground=TEKST,
                       rowheight=23, font=("Segoe UI", 10))
        stil.configure("T.Treeview.Heading", background="#1b2740", foreground=PRIGUSENO,
                       font=("Segoe UI", 10, "bold"), relief="flat")
        stil.map("T.Treeview", background=[("selected", "#1d4ed8")])

        self._zaglavlje()
        self.tabovi = ctk.CTkTabview(self, fg_color=POZADINA, segmented_button_selected_color="#1d4ed8")
        self.tabovi.pack(fill="both", expand=True, padx=14, pady=(0, 14))
        self._tab_108(self.tabovi.add("10.8  Ručno sastavljen okvir"))
        self._tab_107(self.tabovi.add("10.7  Mjerenja na sabirnici"))
        self._tab_okviri(self.tabovi.add("Okviri"))
        self.osvjezi_okvir()
        self.after(50, self._obradi)

    # ------------------------------------------------------------ izgled
    def kartica(self, roditelj, naslov):
        k = ctk.CTkFrame(roditelj, fg_color=KARTICA, corner_radius=14, border_width=1, border_color=RUB)
        ctk.CTkLabel(k, text=naslov.upper(), text_color=PRIGUSENO,
                     font=ctk.CTkFont("Segoe UI", 11, "bold")).pack(anchor="w", padx=14, pady=(8, 2))
        return k

    def tablica(self, roditelj, stupci, sirine, visina):
        t = ttk.Treeview(roditelj, columns=stupci, show="headings", height=visina, style="T.Treeview")
        for s, w in zip(stupci, sirine):
            t.heading(s, text=s)
            t.column(s, width=w, anchor="center")
        return t

    def _zaglavlje(self):
        z = ctk.CTkFrame(self, fg_color=POZADINA)
        z.pack(fill="x", padx=14, pady=6)
        ctk.CTkLabel(z, text="Modbus RTU  ·  analiza sabirnice", text_color=TEKST,
                     font=ctk.CTkFont("Segoe UI", 22, "bold")).pack(side="left")
        ctk.CTkLabel(z, text=f"  {BRZINA} bit/s · 8N1", text_color=PRIGUSENO).pack(side="left")
        desno = ctk.CTkFrame(z, fg_color=POZADINA)
        desno.pack(side="right")
        portovi = [p.device for p in serial.tools.list_ports.comports()] or ["COM9"]
        self.port = ctk.CTkComboBox(desno, values=portovi, width=110)
        self.port.set("COM9" if "COM9" in portovi else portovi[0])
        self.port.pack(side="left", padx=6)
        self.demo_kv = ctk.CTkCheckBox(desno, text="Demo bez uređaja", text_color=PRIGUSENO)
        self.demo_kv.pack(side="left", padx=6)
        self.gumb = ctk.CTkButton(desno, text="Spoji", width=110, command=self.spoji, fg_color="#1d4ed8")
        self.gumb.pack(side="left", padx=6)
        self.status = ctk.CTkLabel(z, text="Nije spojeno", text_color=PRIGUSENO)
        self.status.pack(side="right", padx=16)

    def _tab_108(self, tab):
        tab.grid_columnconfigure((0, 1), weight=1)

        # Unos polja okvira
        unos = self.kartica(tab, "Polja zahtjeva")
        unos.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 8))
        red = ctk.CTkFrame(unos, fg_color=KARTICA)
        red.pack(fill="x", padx=14, pady=(0, 12))
        self.polja = {}
        for naziv, pocetno, sirina in (("Slave", "1", 60), ("Adresa registra", "4097", 100),
                                       ("Broj registara / vrijednost", "1", 100)):
            ctk.CTkLabel(red, text=naziv, text_color=PRIGUSENO).pack(side="left", padx=(8, 4))
            e = ctk.CTkEntry(red, width=sirina)
            e.insert(0, pocetno)
            e.pack(side="left")
            e.bind("<KeyRelease>", lambda _e: self.osvjezi_okvir())
            self.polja[naziv] = e
        ctk.CTkLabel(red, text="Funkcija", text_color=PRIGUSENO).pack(side="left", padx=(16, 4))
        self.funkcija = ctk.CTkSegmentedButton(red, values=["03 čitanje", "06 upis"],
                                               command=lambda _v: self.osvjezi_okvir())
        self.funkcija.set("03 čitanje")
        self.funkcija.pack(side="left")
        ctk.CTkButton(red, text="▶  Pošalji okvir", fg_color="#15803d", hover_color="#166534",
                      command=self.posalji_okvir).pack(side="right", padx=4)

        # Okvir i postupak CRC
        lijevo = self.kartica(tab, "Tablica 10.8  ·  bajtovi zahtjeva")
        lijevo.grid(row=1, column=0, sticky="nsew", padx=(0, 6))
        self.okvir_lbl = ctk.CTkLabel(lijevo, text="", text_color=ZELENA,
                                      font=ctk.CTkFont("Consolas", 18, "bold"))
        self.okvir_lbl.pack(anchor="w", padx=14, pady=(2, 6))
        self.t108 = self.tablica(lijevo, ("Bajt", "Vrijednost", "Što predstavlja"), (60, 100, 330), 8)
        self.t108.pack(fill="x", padx=14, pady=(0, 12))

        # Postupak CRC, vodoravno: bajt i vrijednost registra nakon njegove obrade
        dolje = self.kartica(tab, "Postupak CRC-16  ·  početno 0xFFFF, XOR s bajtom pa 8 posmaka s polinomom 0xA001")
        dolje.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(8, 0))
        self.tcrc = self.tablica(dolje, ("", "početno", "1.", "2.", "3.", "4.", "5.", "6."),
                                 (170, 120, 120, 120, 120, 120, 120, 120), 2)
        self.tcrc.pack(fill="x", padx=14, pady=(0, 12))

        # Odgovor
        desno = self.kartica(tab, "Odgovor pretvarača")
        desno.grid(row=1, column=1, sticky="nsew", padx=(6, 0))
        self.odg_lbl = ctk.CTkLabel(desno, text="—", text_color=PLAVA,
                                    font=ctk.CTkFont("Consolas", 18, "bold"))
        self.odg_lbl.pack(anchor="w", padx=14, pady=(2, 6))
        self.todg = self.tablica(desno, ("Bajt", "Vrijednost", "Što predstavlja"), (60, 100, 330), 8)
        self.todg.pack(fill="x", padx=14)
        self.odg_poruka = ctk.CTkLabel(desno, text="", text_color=PRIGUSENO, wraplength=520, justify="left")
        self.odg_poruka.pack(anchor="w", padx=14, pady=10)

    def _tab_107(self, tab):
        upr = self.kartica(tab, "Mjerenje")
        upr.pack(fill="x", pady=(0, 8))
        red = ctk.CTkFrame(upr, fg_color=KARTICA)
        red.pack(fill="x", padx=14, pady=(0, 12))
        ctk.CTkLabel(red, text="Broj ponavljanja", text_color=PRIGUSENO).pack(side="left", padx=4)
        self.ponavljanja = ctk.CTkEntry(red, width=70)
        self.ponavljanja.insert(0, "50")
        self.ponavljanja.pack(side="left")
        ctk.CTkLabel(red, text="Razmak između upita (ms)", text_color=PRIGUSENO).pack(side="left", padx=(16, 4))
        self.razmak = ctk.CTkEntry(red, width=70)
        self.razmak.insert(0, "50")
        self.razmak.pack(side="left")
        ctk.CTkLabel(red, text="Upit: čitanje izlazne frekvencije, 01 03 10 01 00 01 D1 0A",
                     text_color=PRIGUSENO).pack(side="left", padx=16)
        self.gumb_107 = ctk.CTkButton(red, text="▶  Pokreni mjerenje", fg_color="#15803d",
                                      hover_color="#166534", command=self.mjeri_107)
        self.gumb_107.pack(side="right", padx=4)
        self.napredak = ctk.CTkProgressBar(upr, height=10, progress_color=ZELENA)
        self.napredak.set(0)
        self.napredak.pack(fill="x", padx=14, pady=(0, 12))

        k = self.kartica(tab, "Tablica 10.7  ·  mjerenja na sabirnici")
        k.pack(fill="both", expand=True)
        self.t107 = self.tablica(k, ("Veličina", "Izračunato", "Izmjereno (računalo)", "Napomena"),
                                 (300, 130, 190, 520), 9)
        self.t107.pack(fill="x", padx=14)
        self._popuni_107(None)
        red2 = ctk.CTkFrame(k, fg_color=KARTICA)
        red2.pack(fill="x", padx=14, pady=10)
        ctk.CTkButton(red2, text="Spremi CSV", fg_color="#334155", command=self.spremi_csv).pack(side="right")
        ctk.CTkLabel(k, text="Računalo vidi samo trenutke kad USB pretvarač preda bajtove, pa izmjerena vremena "
                             "sadrže i kašnjenje USB veze. Trajanje bita i točno kašnjenje odgovora u tablici 10.7 "
                             "mjere se osciloskopom (zadatci 15 i 16), a ovdje služe kao provjera.",
                     text_color=NARANCASTA, wraplength=1150, justify="left").pack(anchor="w", padx=14, pady=(0, 12))

    def _tab_okviri(self, tab):
        k = self.kartica(tab, "Okviri  ·  → zahtjev, ← odgovor, s vremenima u ms od slanja")
        k.pack(fill="both", expand=True)
        self.dnevnik = ctk.CTkTextbox(k, font=ctk.CTkFont("Consolas", 12), fg_color="#0e1626",
                                      text_color="#a5f3fc")
        self.dnevnik.pack(fill="both", expand=True, padx=14, pady=(0, 14))

    # ------------------------------------------------------------ 10.8
    def procitaj_polja(self):
        slave = int(self.polja["Slave"].get())
        adresa = int(self.polja["Adresa registra"].get(), 0)
        vrijednost = int(self.polja["Broj registara / vrijednost"].get(), 0)
        funkcija = 0x03 if self.funkcija.get().startswith("03") else 0x06
        if not (0 <= slave <= 247 and 0 <= adresa <= 0xFFFF and 0 <= vrijednost <= 0xFFFF):
            raise ValueError
        return slave, funkcija, adresa, vrijednost

    def osvjezi_okvir(self):
        try:
            slave, funkcija, adresa, vrijednost = self.procitaj_polja()
        except ValueError:
            self.okvir_lbl.configure(text="neispravan unos", text_color=CRVENA)
            return
        okvir, crc, koraci = slozi_okvir(slave, funkcija, adresa, vrijednost)
        self.okvir_lbl.configure(text=hexs(okvir), text_color=ZELENA)
        self.t108.delete(*self.t108.get_children())
        for i, (b, z) in enumerate(zip(okvir, znacenje_zahtjeva(funkcija)), 1):
            self.t108.insert("", "end", values=(i, f"{b:02X}", z))
        self.tcrc.delete(*self.tcrc.get_children())
        self.tcrc.insert("", "end", values=("Obrađeni bajt", "", *(f"{b:02X}" for b, _ in koraci)))
        self.tcrc.insert("", "end", values=("CRC nakon bajta", "0xFFFF", *(f"0x{c:04X}" for _, c in koraci)))
        self.okvir = okvir
        self.funkcija_kod = funkcija

    def posalji_okvir(self):
        if not self._provjeri_vezu():
            return
        if self.funkcija_kod == 0x06 and not self.demo and not messagebox.askyesno(
                "Upis", "Upis u registar može pokrenuti ili zaustaviti motor. Nastaviti?"):
            return
        okvir, funkcija = self.okvir, self.funkcija_kod

        def posao():
            try:
                rez = self.veza.transakcija(okvir)
                self.rezultati.put(("108", okvir, funkcija, rez))
            except Exception as e:
                self.rezultati.put(("greska", str(e)))
        threading.Thread(target=posao, daemon=True).start()

    def _prikazi_odgovor(self, okvir, funkcija, rez):
        odg, t0, t_posl, t_prvi, t_zadnji = rez
        self._zapisi_okvir(okvir, rez)
        self.odg_lbl.configure(text=hexs(odg) or "(nema odgovora)")
        redovi, poruka = rastumaci_odgovor(odg, funkcija)
        self.todg.delete(*self.todg.get_children())
        for i, (b, z) in enumerate(redovi, 1):
            self.todg.insert("", "end", values=(i, f"{b:02X}", z))
        isti = "  ·  zahtjev je jednak gotovom okviru iz poglavlja 2" \
            if hexs(okvir) == "01 03 10 01 00 01 D1 0A" else ""
        self.odg_poruka.configure(text=poruka + isti,
                                  text_color=ZELENA if "ispravan" in poruka and "NIJE" not in poruka else CRVENA)

    # ------------------------------------------------------------ 10.7
    def mjeri_107(self):
        if not self._provjeri_vezu():
            return
        try:
            n = max(1, int(self.ponavljanja.get()))
            razmak = max(10, int(self.razmak.get())) / 1000
        except ValueError:
            messagebox.showerror("Unos", "Broj ponavljanja i razmak moraju biti cijeli brojevi.")
            return
        okvir = slozi_okvir(1, 0x03, 0x1001, 1)[0]
        self.gumb_107.configure(state="disabled")

        def posao():
            mjere = []
            for i in range(n):
                try:
                    rez = self.veza.transakcija(okvir)
                except Exception as e:
                    self.rezultati.put(("greska", str(e)))
                    break
                odg, t0, t_posl, t_prvi, t_zadnji = rez
                if odg and t_prvi:
                    mjere.append(dict(n_odg=len(odg), rtt=(t_zadnji - t0) * 1000,
                                      do_prvog=(t_prvi - t0) * 1000, odgovor=(t_zadnji - t_prvi) * 1000))
                if i < 3:
                    self.rezultati.put(("okvir", okvir, rez))
                self.rezultati.put(("napredak", (i + 1) / n))
                time.sleep(razmak)
            self.rezultati.put(("107", mjere, razmak * 1000))
        threading.Thread(target=posao, daemon=True).start()

    def _popuni_107(self, mjere, razmak_ms=None):
        tz = t_znak_ms()
        izr = {
            "bit": f"{1e6 / BRZINA:.2f}".replace(".", ","),
            "brzina": f"{BRZINA}",
            "n_zah": "8", "t_zah": f"{8 * tz:.2f}".replace(".", ","),
            "n_odg": "7", "t_odg": f"{7 * tz:.2f}".replace(".", ","),
            "kasn": f"{PD03_MS:.0f}", "tisina": f"{3.5 * tz:.2f}".replace(".", ","),
        }
        izm = {k: "—" for k in izr}
        if mjere:
            fmt = lambda x: f"{x:.2f}".replace(".", ",")
            n_odg = statistics.mode(m["n_odg"] for m in mjere)
            rtt = [m["rtt"] for m in mjere]
            kasn = [m["rtt"] - 8 * tz - n_odg * tz for m in mjere]
            izm.update(n_zah="8 (poslano)", n_odg=str(n_odg),
                       t_odg=f"{fmt(statistics.median(m['odgovor'] for m in mjere))} *",
                       kasn=f"{fmt(min(kasn))} do {fmt(statistics.median(kasn))} *",
                       tisina=f"{razmak_ms:.0f} (razmak alata)")
            izm["rtt"] = f"{fmt(min(rtt))} / {fmt(statistics.median(rtt))} / {fmt(max(rtt))}"
        napomene = {
            "bit": "1 / 9600, mjeri se osciloskopom",
            "brzina": "iz trajanja bita, mjeri se osciloskopom",
            "n_zah": "adresa, funkcija, 2 adrese, 2 broja, 2 CRC",
            "t_zah": "8 znakova po 10 bitova",
            "n_odg": "adresa, funkcija, broj bajtova, 2 podatka, 2 CRC",
            "t_odg": "* sadrži i grupiranje bajtova u USB pretvaraču",
            "kasn": "* procjena: ukupno vrijeme minus zahtjev i odgovor, s USB kašnjenjem",
            "tisina": "3,5 znakovna vremena",
        }
        nazivi = [("bit", "Trajanje bita (µs)"), ("brzina", "Brzina prijenosa (bit/s)"),
                  ("n_zah", "Broj bajtova u zahtjevu"), ("t_zah", "Trajanje zahtjeva (ms)"),
                  ("n_odg", "Broj bajtova u odgovoru"), ("t_odg", "Trajanje odgovora (ms)"),
                  ("kasn", "Kašnjenje odgovora pretvarača (ms)"),
                  ("tisina", "Najmanja tišina između okvira (ms)")]
        self.t107.delete(*self.t107.get_children())
        for k, n in nazivi:
            self.t107.insert("", "end", values=(n, izr[k], izm[k], napomene[k]))
        if mjere:
            self.t107.insert("", "end", values=("Ukupno, slanje do zadnjeg bajta (ms)", "", izm["rtt"],
                                                f"najmanje / medijan / najviše, {len(mjere)} upita"))
        self.zadnje_107 = [self.t107.item(i)["values"] for i in self.t107.get_children()]

    def spremi_csv(self):
        mapa = os.path.dirname(sys.executable if getattr(sys, "frozen", False) else os.path.abspath(__file__))
        put = os.path.join(mapa, "tablica_10_7.csv")
        with open(put, "w", newline="", encoding="utf-8-sig") as d:
            w = csv.writer(d, delimiter=";")
            w.writerow(["Veličina", "Izračunato", "Izmjereno (računalo)", "Napomena"])
            w.writerows(self.zadnje_107 or [])
        messagebox.showinfo("CSV", f"Spremljeno:\n{put}")

    # ------------------------------------------------------------ zajednicko
    def _provjeri_vezu(self):
        if not self.veza:
            messagebox.showinfo("Veza", "Najprije spoji pretvarač ili uključi demo način.")
            return False
        return True

    def spoji(self):
        if self.veza:
            self.veza.zatvori()
            self.veza = None
            self.gumb.configure(text="Spoji", fg_color="#1d4ed8")
            self.status.configure(text="Nije spojeno", text_color=PRIGUSENO)
            return
        self.demo = bool(self.demo_kv.get())
        try:
            self.veza = DemoVeza() if self.demo else Veza(self.port.get())
        except Exception as e:
            messagebox.showerror("Spajanje", f"Port se ne može otvoriti:\n{e}\n\nJe li QModMaster zatvoren?")
            return
        self.gumb.configure(text="Odspoji", fg_color="#334155")
        self.status.configure(text="Demo način" if self.demo else f"Spojeno: {self.port.get()}",
                              text_color=NARANCASTA if self.demo else ZELENA)

    def _zapisi_okvir(self, okvir, rez):
        odg, t0, t_posl, t_prvi, t_zadnji = rez
        ms = lambda t: f"{(t - t0) * 1000:7.2f} ms" if t else "      —   "
        self.dnevnik.insert("end", f"{time.strftime('%H:%M:%S')}  → {hexs(okvir)}   (predano {ms(t_posl)})\n"
                                   f"          ← {hexs(odg) or '(nema odgovora)'}   "
                                   f"(prvi bajt {ms(t_prvi)}, zadnji {ms(t_zadnji)})\n")
        self.dnevnik.see("end")

    def _obradi(self):
        while not self.rezultati.empty():
            vrsta, *ost = self.rezultati.get()
            if vrsta == "108":
                self._prikazi_odgovor(*ost)
            elif vrsta == "okvir":
                self._zapisi_okvir(*ost)
            elif vrsta == "napredak":
                self.napredak.set(ost[0])
            elif vrsta == "107":
                self._popuni_107(*ost)
                self.gumb_107.configure(state="normal")
            elif vrsta == "greska":
                self.status.configure(text=ost[0], text_color=CRVENA)
                self.gumb_107.configure(state="normal")
        self.after(50, self._obradi)


if __name__ == "__main__":
    Alat().mainloop()
