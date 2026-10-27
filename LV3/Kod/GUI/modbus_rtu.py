"""Modbus RTU Master za pretvarac CW100 (LV3) i simulator za rad bez uredaja."""

import math
import threading
import time

import serial

BRZINA = 9600
SLAVE = 1
F_MAX = 50.0                  # P0-10, maksimalna frekvencija (Hz)
TIMEOUT_ODGOVORA = 0.300      # najdulje cekanje na odgovor (s)
TISINA_KRAJA = 0.005          # 5 ms tisine znaci kraj okvira

REG_ZADANA = 4096             # 0x1000, zadana frekvencija u 0,01 % od P0-10
REG_NAREDBA = 8192            # 0x2000, naredba pogonu
REG_STANJE = 12288            # 0x3000, stanje pretvaraca

NADZORNI = [  # (adresa, naziv, mjerilo, jedinica)
    (4096, "Zadana vrijednost", 0.01, "%"),
    (4097, "Izlazna frekvencija", 0.01, "Hz"),
    (4098, "Napon međukruga", 0.1, "V"),
    (4099, "Izlazni napon", 1, "V"),
    (4100, "Izlazna struja", 0.01, "A"),
    (4101, "Izlazna snaga", 0.01, "kW"),
    (4102, "Izlazni moment", 0.1, "%"),
    (4103, "Brzina vrtnje", 1, ""),
    (4104, "Digitalni ulazi", 1, ""),
    (4105, "Digitalni izlazi", 1, ""),
]
STANJA = {1: "VRTNJA NAPRIJED", 2: "VRTNJA NATRAG", 3: "ZAUSTAVLJEN"}


def crc16(buf: bytes) -> int:
    """CRC-16 Modbus, isti algoritam kao u poglavlju 2.2 predloska."""
    crc = 0xFFFF
    for b in buf:
        crc ^= b
        for _ in range(8):
            crc = (crc >> 1) ^ 0xA001 if crc & 1 else crc >> 1
    return crc


def s_crc(okvir: bytes) -> bytes:
    c = crc16(okvir)
    return okvir + bytes([c & 0xFF, c >> 8])


def hexs(b: bytes) -> str:
    return " ".join(f"{x:02X}" for x in b)


def predznak(v: int) -> int:
    return v - 0x10000 if v & 0x8000 else v


def skaliraj(sirove: list) -> dict:
    """Pretvara sirove vrijednosti bloka 4096 do 4105 u fizikalne velicine."""
    out = {}
    for (adr, _, mjerilo, _), v in zip(NADZORNI, sirove):
        if adr in (4096, 4103):
            v = predznak(v)
        out[adr] = v * mjerilo
    return out


class ModbusRTU:
    """Najjednostavniji Master: jedna transakcija u tijeku, kraj okvira po tisini."""

    def __init__(self, port):
        self.ser = serial.Serial(port, BRZINA, bytesize=8, parity="N", stopbits=1, timeout=0)
        self.lock = threading.Lock()
        self.dnevnik = None

    def zatvori(self):
        self.ser.close()

    def _primi(self) -> bytes:
        buf, pocetak, zadnji = bytearray(), time.perf_counter(), None
        while time.perf_counter() - pocetak < TIMEOUT_ODGOVORA:
            n = self.ser.in_waiting
            if n:
                buf += self.ser.read(n)
                zadnji = time.perf_counter()
            elif zadnji and time.perf_counter() - zadnji > TISINA_KRAJA:
                break
            time.sleep(0.0005)
        return bytes(buf)

    def _transakcija(self, zahtjev: bytes) -> bytes:
        okvir = s_crc(zahtjev)
        with self.lock:
            self.ser.reset_input_buffer()
            self.ser.write(okvir)
            self.ser.flush()
            odgovor = self._primi()
        if self.dnevnik:
            self.dnevnik(f"→ {hexs(okvir)}\n← {hexs(odgovor) or '(nema odgovora)'}")
        if len(odgovor) < 5:
            raise IOError("Nema odgovora ili je odgovor prekratak")
        if crc16(odgovor[:-2]) != odgovor[-2] | (odgovor[-1] << 8):
            raise IOError("Pogrešan CRC u odgovoru")
        if odgovor[0] != zahtjev[0]:
            raise IOError("Odgovor s pogrešne adrese")
        if odgovor[1] == zahtjev[1] | 0x80:
            raise IOError(f"Iznimka Modbus, šifra {odgovor[2]}")
        return odgovor

    def citaj(self, adresa: int, broj: int) -> list:
        zahtjev = bytes([SLAVE, 0x03, adresa >> 8, adresa & 0xFF, broj >> 8, broj & 0xFF])
        odg = self._transakcija(zahtjev)
        if odg[2] != 2 * broj:
            raise IOError("Neočekivan broj podatkovnih bajtova")
        return [(odg[3 + 2 * i] << 8) | odg[4 + 2 * i] for i in range(broj)]

    def pisi(self, adresa: int, vrijednost: int):
        v = vrijednost & 0xFFFF
        zahtjev = bytes([SLAVE, 0x06, adresa >> 8, adresa & 0xFF, v >> 8, v & 0xFF])
        self._transakcija(zahtjev)


class Simulator:
    """Zamjena za pretvarac, za isprobavanje sucelja bez uredaja (demo nacin)."""

    def __init__(self):
        self.zadana = 0          # 0,01 %
        self.stanje = 3
        self.f = 0.0
        self.t = time.perf_counter()
        self.dnevnik = None

    def zatvori(self):
        pass

    def _korak(self):
        sada = time.perf_counter()
        dt, self.t = sada - self.t, sada
        cilj = self.zadana / 10000 * F_MAX if self.stanje in (1, 2) else 0.0
        brzina = F_MAX / 5.0     # rampa 5 s do maksimalne frekvencije
        if self.f < cilj:
            self.f = min(cilj, self.f + brzina * dt)
        else:
            self.f = max(cilj, self.f - brzina * dt)

    def citaj(self, adresa, broj):
        self._korak()
        if adresa == REG_STANJE:
            return [self.stanje]
        f = self.f
        u = 4.6 * f
        i = 0.0 if f == 0 else 1.0 + 0.7 * f / F_MAX + 0.03 * math.sin(time.time())
        p = math.sqrt(3) * u * i * 0.3 / 1000
        smjer = -1 if self.stanje == 2 else 1
        sirove = [self.zadana & 0xFFFF, round(f * 100), 3300 + int(10 * math.sin(time.time())),
                  round(u), round(i * 100), round(p * 100), round(f * 2),
                  round(smjer * f * 27.4) & 0xFFFF, 0, 0]
        return sirove[:broj]

    def pisi(self, adresa, vrijednost):
        if adresa == REG_ZADANA:
            self.zadana = vrijednost
        elif adresa == REG_NAREDBA:
            if vrijednost in (1, 2):
                self.stanje = vrijednost
            elif vrijednost in (5, 6):
                self.stanje = 3
