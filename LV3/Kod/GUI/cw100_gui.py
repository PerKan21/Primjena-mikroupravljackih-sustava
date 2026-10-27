"""
LV3: moderno sucelje za upravljanje pretvaracem CW100 preko Modbus RTU.

Pokretanje:  python cw100_gui.py
Potrebno:    pip install pyserial customtkinter
Prije spajanja zatvoriti QModMaster, jer drzi isti COM port.
"""

import csv
import math
import os
import queue
import sys
import threading
import time
import tkinter as tk
from tkinter import messagebox, ttk

import customtkinter as ctk
import serial.tools.list_ports

from modbus_rtu import (F_MAX, NADZORNI, REG_NAREDBA, REG_STANJE, REG_ZADANA,
                        STANJA, ModbusRTU, Simulator, skaliraj)

# --- Paleta ---
POZADINA = "#0b1220"
KARTICA = "#131c2e"
RUB = "#22304a"
TEKST = "#e2e8f0"
PRIGUSENO = "#8a9ab5"
ZELENA = "#22c55e"
PLAVA = "#38bdf8"
CRVENA = "#ef4444"
NARANCASTA = "#f59e0b"
SIVA = "#475569"
FREKVENCIJE = [10, 20, 30, 40, 50]


def miješaj(c1, c2, t):
    """Linearno miješanje dviju boja, za sjaj bez prozirnosti."""
    a = [int(c1[i:i + 2], 16) for i in (1, 3, 5)]
    b = [int(c2[i:i + 2], 16) for i in (1, 3, 5)]
    return "#" + "".join(f"{round(x + (y - x) * t):02x}" for x, y in zip(a, b))


# ============================================================ radna nit
class Radnik(threading.Thread):
    """Sva komunikacija ide u ovoj niti, pa animacija ostaje glatka."""

    def __init__(self, izvor, rezultati):
        super().__init__(daemon=True)
        self.izvor = izvor
        self.naredbe = queue.Queue()
        self.rezultati = rezultati
        self.stani = threading.Event()
        izvor.dnevnik = lambda t: rezultati.put(("okvir", t))

    def run(self):
        while not self.stani.is_set():
            while not self.naredbe.empty():
                adr, v, opis = self.naredbe.get()
                try:
                    self.izvor.pisi(adr, v)
                    self.rezultati.put(("info", opis))
                except Exception as e:
                    self.rezultati.put(("greska", f"{opis}: {e}"))
            try:
                sirove = self.izvor.citaj(4096, 10)
                stanje = self.izvor.citaj(REG_STANJE, 1)[0]
                self.rezultati.put(("podaci", skaliraj(sirove), stanje))
            except Exception as e:
                self.rezultati.put(("greska", str(e)))
            time.sleep(0.25)
        self.izvor.zatvori()


# ============================================================ animirani motor
class Motor(tk.Canvas):
    """Motor s rotorom koji se vrti brzinom razmjernom izlaznoj frekvenciji i sjajem stanja."""

    def __init__(self, master, velicina=300):
        super().__init__(master, width=velicina, height=velicina, bg=KARTICA, highlightthickness=0)
        self.c = velicina / 2
        self.kut = 0.0
        self.f = 0.0          # izlazna frekvencija (Hz)
        self.smjer = 1
        self.boja = SIVA
        self.faza = 0.0
        c, r = self.c, velicina * 0.36
        self.sjaj = [self.create_oval(c - r - k * 5, c - r - k * 5, c + r + k * 5, c + r + k * 5,
                                      outline=KARTICA, width=5) for k in range(6, 0, -1)]
        self.stator = self.create_oval(c - r, c - r, c + r, c + r, outline=SIVA, width=4, fill="#0e1626")
        for k in range(12):   # zubi statora
            a = math.radians(k * 30)
            x1, y1 = c + (r - 10) * math.cos(a), c + (r - 10) * math.sin(a)
            x2, y2 = c + (r - 2) * math.cos(a), c + (r - 2) * math.sin(a)
            self.create_line(x1, y1, x2, y2, fill=RUB, width=3)
        self.lopatice = [self.create_polygon(0, 0, 0, 0, 0, 0, fill=SIVA, outline="") for _ in range(6)]
        rr = r * 0.2
        self.glavina = self.create_oval(c - rr, c - rr, c + rr, c + rr, fill="#1f2a40", outline=SIVA, width=3)
        self.natpis = self.create_text(c, velicina - 14, text="0,00 Hz", fill=PRIGUSENO,
                                       font=("Segoe UI", 12, "bold"))
        self.r = r
        self._crtaj()

    def postavi(self, f, stanje):
        self.f = f
        self.smjer = -1 if stanje == 2 else 1
        self.boja = ZELENA if stanje == 1 else PLAVA if stanje == 2 else SIVA

    def korak(self):
        # 1 Hz izlazne frekvencije prikazuje se kao 8 stupnjeva po slici (oko 33 slike u sekundi)
        self.kut = (self.kut + self.smjer * self.f * 8.0) % 360
        self.faza += 0.12
        self._crtaj()

    def _crtaj(self):
        c, r = self.c, self.r
        radi = self.f > 0.05
        boja = self.boja if radi else SIVA
        puls = 0.55 + 0.45 * math.sin(self.faza) if radi else 0.0
        for k, o in enumerate(self.sjaj):
            t = (k + 1) / len(self.sjaj)
            self.itemconfig(o, outline=miješaj(KARTICA, boja, t * 0.55 * puls) if radi else KARTICA)
        self.itemconfig(self.stator, outline=boja)
        self.itemconfig(self.glavina, outline=boja)
        for n, p in enumerate(self.lopatice):
            a = math.radians(self.kut + n * 60)
            tocke = []
            for dr, da in ((0.22, -16), (0.9, -6), (0.9, 8), (0.22, 16)):
                aa = a + math.radians(da)
                tocke += [c + r * dr * math.cos(aa), c + r * dr * math.sin(aa)]
            self.coords(p, *tocke)
            self.itemconfig(p, fill=miješaj("#334155", boja, 0.85 if radi else 0.2))
        self.itemconfig(self.natpis, text=f"{self.f:.2f} Hz".replace(".", ","),
                        fill=boja if radi else PRIGUSENO)


class Lampica(tk.Canvas):
    """Mala svjetleca lampica sa sjajem."""

    def __init__(self, master, natpis, boja):
        super().__init__(master, width=150, height=34, bg=KARTICA, highlightthickness=0)
        self.boja, self.ukljucena, self.faza = boja, False, 0.0
        self.krugovi = [self.create_oval(17 - k, 17 - k, 17 + k, 17 + k, outline="", fill=KARTICA)
                        for k in (14, 11, 8)]
        self.create_text(36, 17, text=natpis, anchor="w", fill=TEKST, font=("Segoe UI", 11, "bold"))

    def korak(self):
        self.faza += 0.15
        puls = 0.7 + 0.3 * math.sin(self.faza)
        for k, o in enumerate(self.krugovi):
            if self.ukljucena:
                t = (0.25, 0.5, 1.0)[k] * puls
                self.itemconfig(o, fill=miješaj(KARTICA, self.boja, t))
            else:
                self.itemconfig(o, fill=(KARTICA, KARTICA, "#2a3550")[k])


# ============================================================ aplikacija
class Aplikacija(ctk.CTk):
    def __init__(self):
        super().__init__()
        ctk.set_appearance_mode("dark")
        self.title("LV3: CW100 preko Modbus RTU")
        self.geometry("1280x800")
        self.minsize(1150, 740)
        self.configure(fg_color=POZADINA)

        self.rezultati = queue.Queue()
        self.radnik = None
        self.demo = False
        self.zadnje, self.stanje = None, 3
        self.zadnji_odgovor = 0.0
        self.retci = {f: {} for f in FREKVENCIJE}

        self._zaglavlje()
        self.tabovi = ctk.CTkTabview(self, fg_color=POZADINA, segmented_button_selected_color="#1d4ed8")
        self.tabovi.pack(fill="both", expand=True, padx=14, pady=(0, 14))
        self._tab_upravljanje(self.tabovi.add("Upravljanje"))
        self._tab_tablica(self.tabovi.add("Tablica 10.2"))
        self._tab_okviri(self.tabovi.add("Okviri na sabirnici"))

        self.after(30, self._animacija)
        self.after(50, self._obradi)

    # ------------------------------------------------------------ izgled
    def kartica(self, roditelj, naslov):
        k = ctk.CTkFrame(roditelj, fg_color=KARTICA, corner_radius=14, border_width=1, border_color=RUB)
        ctk.CTkLabel(k, text=naslov.upper(), text_color=PRIGUSENO,
                     font=ctk.CTkFont("Segoe UI", 11, "bold")).pack(anchor="w", padx=14, pady=(10, 4))
        return k

    def _zaglavlje(self):
        z = ctk.CTkFrame(self, fg_color=POZADINA)
        z.pack(fill="x", padx=14, pady=10)
        ctk.CTkLabel(z, text="CW100  ·  Modbus RTU", text_color=TEKST,
                     font=ctk.CTkFont("Segoe UI", 22, "bold")).pack(side="left")
        ctk.CTkLabel(z, text="  9600 bit/s · 8N1 · Slave 1", text_color=PRIGUSENO,
                     font=ctk.CTkFont("Segoe UI", 13)).pack(side="left")

        desno = ctk.CTkFrame(z, fg_color=POZADINA)
        desno.pack(side="right")
        portovi = [p.device for p in serial.tools.list_ports.comports()] or ["COM9"]
        self.port = ctk.CTkComboBox(desno, values=portovi, width=110)
        self.port.set("COM9" if "COM9" in portovi else portovi[0])
        self.port.pack(side="left", padx=6)
        self.demo_kv = ctk.CTkCheckBox(desno, text="Demo bez uređaja", text_color=PRIGUSENO)
        self.demo_kv.pack(side="left", padx=6)
        self.gumb_spoji = ctk.CTkButton(desno, text="Spoji", width=110, command=self.spoji,
                                        fg_color="#1d4ed8", hover_color="#1e40af")
        self.gumb_spoji.pack(side="left", padx=6)
        self.status = ctk.CTkLabel(z, text="Nije spojeno", text_color=PRIGUSENO)
        self.status.pack(side="right", padx=16)

    def _tab_upravljanje(self, tab):
        tab.grid_columnconfigure(1, weight=1)
        tab.grid_rowconfigure(0, weight=1)

        # Lijevo: motor i lampice
        lijevo = self.kartica(tab, "Motor")
        lijevo.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
        self.motor = Motor(lijevo, 320)
        self.motor.pack(padx=14, pady=4)
        self.stanje_lbl = ctk.CTkLabel(lijevo, text="ZAUSTAVLJEN", text_color=PRIGUSENO,
                                       font=ctk.CTkFont("Segoe UI", 18, "bold"))
        self.stanje_lbl.pack(pady=(0, 6))
        red = ctk.CTkFrame(lijevo, fg_color=KARTICA)
        red.pack(pady=(0, 12))
        self.lampice = {
            "veza": Lampica(red, "VEZA", ZELENA),
            "nap": Lampica(red, "NAPRIJED", ZELENA),
            "nat": Lampica(red, "NATRAG", PLAVA),
            "gr": Lampica(red, "GREŠKA", CRVENA),
        }
        for i, l in enumerate(self.lampice.values()):
            l.grid(row=i // 2, column=i % 2, padx=4, pady=2)

        # Desno: mjerenja i upravljanje
        desno = ctk.CTkFrame(tab, fg_color=POZADINA)
        desno.grid(row=0, column=1, sticky="nsew")
        desno.grid_columnconfigure((0, 1, 2), weight=1)

        self.plocice = {}
        raspored = [(4097, "Izlazna frekvencija", "Hz", 2), (4099, "Izlazni napon", "V", 0),
                    (4100, "Izlazna struja", "A", 2), (4101, "Izlazna snaga", "kW", 2),
                    (4098, "Napon međukruga", "V", 1), (4096, "Zadana vrijednost", "%", 2)]
        for n, (adr, naziv, jed, dec) in enumerate(raspored):
            k = self.kartica(desno, f"{naziv}  ·  {adr}")
            k.grid(row=n // 3, column=n % 3, sticky="nsew", padx=5, pady=5)
            v = ctk.CTkLabel(k, text="—", text_color=TEKST, font=ctk.CTkFont("Segoe UI", 30, "bold"))
            v.pack(anchor="w", padx=14)
            ctk.CTkLabel(k, text=jed, text_color=PRIGUSENO).pack(anchor="w", padx=14, pady=(0, 10))
            self.plocice[adr] = (v, dec)

        traka = self.kartica(desno, "Izlazna frekvencija prema maksimalnoj (P0-10 = 50 Hz)")
        traka.grid(row=2, column=0, columnspan=3, sticky="ew", padx=5, pady=5)
        self.traka = ctk.CTkProgressBar(traka, height=14, progress_color=ZELENA)
        self.traka.set(0)
        self.traka.pack(fill="x", padx=14, pady=(2, 14))

        upr = self.kartica(desno, "Upravljanje  ·  P0-02 = 2, P0-03 = 9")
        upr.grid(row=3, column=0, columnspan=3, sticky="ew", padx=5, pady=5)
        red = ctk.CTkFrame(upr, fg_color=KARTICA)
        red.pack(fill="x", padx=14, pady=(0, 6))
        self.f_lbl = ctk.CTkLabel(red, text="Zadana f: 25,0 Hz", text_color=TEKST,
                                  font=ctk.CTkFont("Segoe UI", 15, "bold"), width=170, anchor="w")
        self.f_lbl.pack(side="left")
        self.klizac = ctk.CTkSlider(red, from_=0, to=F_MAX, number_of_steps=100, command=self._natpis_klizaca)
        self.klizac.set(25)
        self.klizac.pack(side="left", fill="x", expand=True, padx=10)
        ctk.CTkButton(red, text="Postavi f", width=110, command=self.postavi_f_klizac).pack(side="left")

        gumbi = ctk.CTkFrame(upr, fg_color=KARTICA)
        gumbi.pack(fill="x", padx=14, pady=(6, 14))
        gumbi.grid_columnconfigure((0, 1, 2, 3), weight=1)
        for i, (t, kod, b, h) in enumerate([
                ("▶  RUN NAPRIJED", 1, "#15803d", "#166534"),
                ("◀  RUN NATRAG", 2, "#0369a1", "#075985"),
                ("■  STOP", 6, "#b91c1c", "#991b1b"),
                ("↺  Potvrdi grešku", 7, "#b45309", "#92400e")]):
            ctk.CTkButton(gumbi, text=t, height=48, fg_color=b, hover_color=h,
                          font=ctk.CTkFont("Segoe UI", 14, "bold"),
                          command=lambda k=kod: self.naredba(k)).grid(row=0, column=i, sticky="ew", padx=4)

    def _tab_tablica(self, tab):
        stil = ttk.Style()
        stil.theme_use("clam")
        stil.configure("Tamna.Treeview", background=KARTICA, fieldbackground=KARTICA, foreground=TEKST,
                       rowheight=34, bordercolor=RUB, font=("Segoe UI", 11))
        stil.configure("Tamna.Treeview.Heading", background="#1b2740", foreground=PRIGUSENO,
                       font=("Segoe UI", 10, "bold"), relief="flat")
        stil.map("Tamna.Treeview", background=[("selected", "#1d4ed8")])

        k = self.kartica(tab, "Tablica 10.2  ·  vrijednosti preko sabirnice uz mjerenja kliještima")
        k.pack(fill="both", expand=True)
        stupci = ("f", "f_reg", "u_reg", "i_reg", "p_reg", "u_klj", "i_klj", "f_klj", "odst")
        naslovi = ("Zadana f (Hz)", "0x1001 f (Hz)", "0x1003 U (V)", "0x1004 I (A)", "0x1005 P (kW)",
                   "Kliješta U (V)", "Kliješta I (A)", "Kliješta f (Hz)", "Najveće odstupanje")
        self.tablica = ttk.Treeview(k, columns=stupci, show="headings", height=5, style="Tamna.Treeview")
        for s, n in zip(stupci, naslovi):
            self.tablica.heading(s, text=n)
            self.tablica.column(s, width=120, anchor="center")
        for f in FREKVENCIJE:
            self.tablica.insert("", "end", iid=str(f), values=(f,) + ("",) * 8)
        self.tablica.pack(fill="x", padx=14, pady=6)

        red = ctk.CTkFrame(k, fg_color=KARTICA)
        red.pack(fill="x", padx=14, pady=10)
        ctk.CTkButton(red, text="1  Postavi f retka", command=self.postavi_f_retka).pack(side="left", padx=4)
        ctk.CTkButton(red, text="2  Spremi očitanje", command=self.spremi_u_redak).pack(side="left", padx=4)
        ctk.CTkLabel(red, text="Kliješta U · I · f:", text_color=PRIGUSENO).pack(side="left", padx=(18, 6))
        self.klj = [ctk.CTkEntry(red, width=80, placeholder_text=p) for p in ("U (V)", "I (A)", "f (Hz)")]
        for e in self.klj:
            e.pack(side="left", padx=2)
        ctk.CTkButton(red, text="3  Upiši kliješta", command=self.upisi_klijesta).pack(side="left", padx=8)
        ctk.CTkButton(red, text="Spremi CSV", fg_color="#334155", hover_color="#1e293b",
                      command=self.spremi_csv).pack(side="right", padx=4)
        ctk.CTkLabel(k, text="Odaberi redak, postavi frekvenciju, pričekaj da motor dođe na brzinu, "
                             "spremi očitanje i upiši vrijednosti s kliješta.",
                     text_color=PRIGUSENO).pack(anchor="w", padx=14, pady=(0, 12))

    def _tab_okviri(self, tab):
        k = self.kartica(tab, "Okviri na sabirnici  ·  → zahtjev, ← odgovor")
        k.pack(fill="both", expand=True)
        self.dnevnik = ctk.CTkTextbox(k, font=ctk.CTkFont("Consolas", 12), fg_color="#0e1626",
                                      text_color="#a5f3fc")
        self.dnevnik.pack(fill="both", expand=True, padx=14, pady=(0, 14))

    # ------------------------------------------------------------ petlje
    def _animacija(self):
        self.motor.korak()
        veza = self.radnik is not None and time.time() - self.zadnji_odgovor < 1.5
        self.lampice["veza"].ukljucena = veza
        self.lampice["nap"].ukljucena = veza and self.stanje == 1
        self.lampice["nat"].ukljucena = veza and self.stanje == 2
        for l in self.lampice.values():
            l.korak()
        self.after(30, self._animacija)

    def _obradi(self):
        while not self.rezultati.empty():
            vrsta, *ostalo = self.rezultati.get()
            if vrsta == "podaci":
                self._podaci(*ostalo)
            elif vrsta == "okvir":
                self._zapisi(ostalo[0])
            elif vrsta == "info":
                self._zapisi(ostalo[0])
                self.lampice["gr"].ukljucena = False
            elif vrsta == "greska":
                self._zapisi("!! " + ostalo[0])
                self.lampice["gr"].ukljucena = True
                self.status.configure(text=ostalo[0], text_color=CRVENA)
        self.after(50, self._obradi)

    def _podaci(self, v, stanje):
        self.zadnje, self.stanje = v, stanje
        self.zadnji_odgovor = time.time()
        for adr, (lbl, dec) in self.plocice.items():
            lbl.configure(text=f"{v[adr]:.{dec}f}".replace(".", ","))
        f = max(0.0, v[4097])
        self.motor.postavi(f, stanje)
        self.traka.set(min(1.0, f / F_MAX))
        boja = ZELENA if stanje == 1 else PLAVA if stanje == 2 else PRIGUSENO
        self.traka.configure(progress_color=boja if stanje != 3 else SIVA)
        self.stanje_lbl.configure(text=STANJA.get(stanje, f"STANJE {stanje}"), text_color=boja)
        self.status.configure(text=f"Očitano {time.strftime('%H:%M:%S')}", text_color=ZELENA)
        self.lampice["gr"].ukljucena = False

    def _zapisi(self, t):
        self.dnevnik.insert("end", time.strftime("%H:%M:%S  ") + t + "\n")
        self.dnevnik.see("end")

    # ------------------------------------------------------------ akcije
    def spoji(self):
        if self.radnik:
            self.radnik.stani.set()
            self.radnik = None
            self.gumb_spoji.configure(text="Spoji", fg_color="#1d4ed8")
            self.status.configure(text="Nije spojeno", text_color=PRIGUSENO)
            self.motor.postavi(0, 3)
            return
        try:
            self.demo = bool(self.demo_kv.get())
            izvor = Simulator() if self.demo else ModbusRTU(self.port.get())
        except Exception as e:
            messagebox.showerror("Spajanje", f"Port se ne može otvoriti:\n{e}\n\nJe li QModMaster zatvoren?")
            return
        self.radnik = Radnik(izvor, self.rezultati)
        self.radnik.start()
        self.gumb_spoji.configure(text="Odspoji", fg_color="#334155")
        self.status.configure(text="Demo način" if self.demo else f"Spojeno: {self.port.get()}",
                              text_color=NARANCASTA if self.demo else ZELENA)

    def posalji(self, adr, v, opis):
        if not self.radnik:
            messagebox.showinfo("Veza", "Najprije spoji pretvarač.")
            return
        self.radnik.naredbe.put((adr, v, opis))

    def postavi_f(self, f):
        v = round(f / F_MAX * 10000)
        self.posalji(REG_ZADANA, v, f"Zadano {f:.1f} Hz (4096 = {v})".replace(".", ","))

    def _natpis_klizaca(self, v=None):
        v = self.klizac.get() if v is None else v
        self.f_lbl.configure(text=f"Zadana f: {v:.1f} Hz".replace(".", ","))

    def postavi_f_klizac(self):
        self._natpis_klizaca()
        self.postavi_f(round(self.klizac.get(), 1))

    def naredba(self, kod):
        if kod in (1, 2) and not self.demo and not messagebox.askyesno(
                "Pokretanje", "Je li vratilo slobodno i zaštićeno i je li pokretanje glasno najavljeno?"):
            return
        self.posalji(REG_NAREDBA, kod, f"Naredba 8192 = {kod}")

    # ------------------------------------------------------------ tablica 10.2
    def odabrani(self):
        sel = self.tablica.selection()
        if not sel:
            messagebox.showinfo("Tablica", "Najprije odaberi redak.")
            return None
        return int(sel[0])

    def postavi_f_retka(self):
        f = self.odabrani()
        if f is not None:
            self.klizac.set(f)
            self._natpis_klizaca()
            self.postavi_f(f)

    def spremi_u_redak(self):
        f = self.odabrani()
        if f is None:
            return
        if not self.zadnje:
            messagebox.showinfo("Tablica", "Još nema očitanih vrijednosti.")
            return
        v = self.zadnje
        self.retci[f].update(f_reg=v[4097], u_reg=v[4099], i_reg=v[4100], p_reg=v[4101])
        self.osvjezi_redak(f)

    def upisi_klijesta(self):
        f = self.odabrani()
        if f is None:
            return
        try:
            u, i, fk = (float(e.get().replace(",", ".")) for e in self.klj)
        except ValueError:
            messagebox.showerror("Unos", "Upiši U, I i f s kliješta kao brojeve.")
            return
        self.retci[f].update(u_klj=u, i_klj=i, f_klj=fk)
        self.osvjezi_redak(f)

    def osvjezi_redak(self, f):
        r = self.retci[f]
        fmt = lambda k, d: f"{r[k]:.{d}f}".replace(".", ",") if k in r else ""
        rel = [abs(r[a] - r[b]) / r[b] * 100 for a, b in
               (("u_reg", "u_klj"), ("i_reg", "i_klj"), ("f_reg", "f_klj")) if a in r and b in r and r[b]]
        odst = f"{max(rel):.1f} %".replace(".", ",") if rel else ""
        self.tablica.item(str(f), values=(f, fmt("f_reg", 2), fmt("u_reg", 0), fmt("i_reg", 2),
                                          fmt("p_reg", 2), fmt("u_klj", 1), fmt("i_klj", 2),
                                          fmt("f_klj", 2), odst))

    def spremi_csv(self):
        mapa = os.path.dirname(sys.executable if getattr(sys, "frozen", False) else os.path.abspath(__file__))
        put = os.path.join(mapa, "tablica_10_2.csv")
        with open(put, "w", newline="", encoding="utf-8-sig") as d:
            w = csv.writer(d, delimiter=";")
            w.writerow([self.tablica.heading(s)["text"] for s in self.tablica["columns"]])
            for f in FREKVENCIJE:
                w.writerow(self.tablica.item(str(f))["values"])
        messagebox.showinfo("CSV", f"Spremljeno:\n{put}")


if __name__ == "__main__":
    Aplikacija().mainloop()
