# Laboratorijska vježba 3

Upravljanje frekvencijskim pretvaračem i motorom preko Modbus RTU

**Kolegij:** Primjena mikroupravljačkih sustava  
**Student:** Tomislav Perković  
**Datum:** 27. 10. 2026.  
**Repozitorij:** [PerKan21/Primjena-mikroupravljackih-sustava](https://github.com/PerKan21/Primjena-mikroupravljackih-sustava)

## Spajanje sabirnice

| Pretvarač USB u RS-485 | Pretvarač CW100 | Opis |
|---|---|---|
| A | A+ | Diferencijalni vod |
| B | B- | Diferencijalni vod |
| GND | COM | Zajednička referenca, obavezna |

Veza: vrata COM9, 9600 bit/s, format 8N1, adresa Slave uređaja 1, adresiranje s brojanjem od nule. Na pretvaraču su postavljeni P0-02 = 2 i P0-03 = 9, tako da se pogonom upravlja preko sabirnice.

## Programi

Vježba ne sadrži zadatke s kodom za mikroupravljač. Master uređaj je računalo. Uz QModMaster su za mjerenja napisana dva alata u Pythonu:

| Program | Namjena |
|---|---|
| `Kod/GUI/cw100_gui.py` | Upravljanje pogonom (zadavanje frekvencije, naprijed, natrag, stop) i očitavanje bloka 4096 do 4105 za tablicu 10.2 |
| `Kod/GUI/modbus_rtu.py` | Modbus RTU Master za `cw100_gui.py`: slaganje okvira, CRC-16, kraj okvira po tišini od 5 ms |
| `Kod/GUI/Alat za sabirnicu/sabirnica_alat.py` | Ručno sastavljen okvir i postupak CRC-a (tablica 10.8), slanje okvira i mjerenje vremena transakcije (tablica 10.7) |

Programi se pokreću iz izvornog koda, uz Python 3.11 ili noviji:

```bash
pip install pyserial customtkinter
python Kod/GUI/cw100_gui.py
python "Kod/GUI/Alat za sabirnicu/sabirnica_alat.py"
```

Oba programa imaju demo način za rad bez pretvarača. Prije spajanja treba zatvoriti QModMaster, jer koristi ista serijska vrata.

## Sadržaj

| Datoteka | Opis |
|---|---|
| `LV3_izvjestaj.pdf` | Izvještaj |
| `LAB3_VFD_Modbus_RTU.docx` | Izvorni predložak vježbe |
| `LAB3_VFD_Modbus_RTU-popunjeno.docx` | Predložak vježbe s ispunjenim tablicama iz poglavlja 10 |
| `Kod/` | Alati u Pythonu korišteni za mjerenja |

## Preuzeti sadržaj i korištenje AI alata

Zadatci, mapa registara i parametri pretvarača preuzeti su iz predloška vježbe.

Korišten je AI alat **Anthropic Claude**.
