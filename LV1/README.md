# Laboratorijska vježba 1

Upoznavanje platforme: razvojna pločica, memorija, pinovi i rad sa senzorom

**Kolegij:** Primjena mikroupravljačkih sustava  
**Student:** Tomislav Perković  
**Datum:** 14. 10. 2026.  
**Repozitorij:** [PerKan21/Primjena-mikroupravljackih-sustava](https://github.com/PerKan21/Primjena-mikroupravljackih-sustava)

## Shema spajanja

| Arduino Nano | SCD30 | Opis |
|---|---|---|
| 5V | VIN | Napajanje senzora s regulatora, ne s ulazno-izlaznog pina |
| GND | GND | Zajednička masa |
| A4 | SDA | Podatkovna linija |
| A5 | SCL | Taktna linija |

```text
Arduino Nano                 SCD30
     5V -------------------- VIN
    GND -------------------- GND
     A4 -------------------- SDA
     A5 -------------------- SCL
```

Senzor se javlja na I2C adresi `0x61`.

## Odabrana biblioteka

Odabrana je **SparkFun SCD30 Arduino Library, inačica 1.0.20**.

| Kriterij | Biblioteka 1 | Biblioteka 2 |
|---|---|---|
| Naziv i autor | SparkFun SCD30 Arduino Library, SparkFun Electronics | Adafruit SCD30, Adafruit Industries |
| Inačica koju ste uzeli | 1.0.20 | 1.0.11 |
| Datum zadnje izmjene | 7. 10. 2022. | 15. 11. 2023. |
| Broj otvorenih prijava problema | 0 | 2 |
| Ima li primjere i dokumentaciju | Da | Da |
| Licencija | MIT | BSD |
| Zauzeće flasha i SRAM-a | 9368 B (30 %) i 456 B (22 %) | 9696 B (31 %) i 515 B (25 %) |
| **Odabrana i zašto** | **Da**, jer je jednostavnija, zauzima manje memorije i treba samo ugrađenu biblioteku `Wire` | Ne, jer zauzima više memorije i uz `Wire` treba još Adafruit BusIO i Adafruit Unified Sensor |

Program sa SparkFun bibliotekom zauzima 328 B manje flasha i 59 B manje SRAM-a. Za usporedbu je u repozitoriju i Adafruit inačica programa, koja se od SparkFun inačice razlikuje samo u pozivima biblioteke.

## Upute za prevođenje

1. Otvoriti `LV1_SCD30_SparkFun/LV1_SCD30_SparkFun.ino` u Arduino IDE-u.
2. U upravitelju biblioteka instalirati **SparkFun SCD30 Arduino Library**, inačicu **1.0.20**.
3. Odabrati pločicu **Arduino Nano** i procesor **ATmega328P**. Ako učitavanje javi pogrešku sinkronizacije, odabrati procesor **ATmega328P (Old Bootloader)**.
4. Pokrenuti **Verify**, zatim spojiti pločicu i pokrenuti **Upload**.
5. Otvoriti serijski monitor na brzini **115200 baud**.

Za Adafruit inačicu (`LV1_SCD30_Adafruit/LV1_SCD30_Adafruit.ino`) treba instalirati biblioteke Adafruit SCD30 1.0.11, Adafruit BusIO i Adafruit Unified Sensor.

## Sadržaj repozitorija

| Datoteka | Opis |
|---|---|
| `LV1_SCD30_SparkFun/LV1_SCD30_SparkFun.ino` | Konačni program |
| `LV1_SCD30_Adafruit/LV1_SCD30_Adafruit.ino` | Program s Adafruit bibliotekom za usporedbu |
| `LV1_izvjestaj.pdf` | Izvještaj |
| `LAB1_Platforma_i_senzor.docx` | Predložak vježbe |

## Preuzeti sadržaj i korištenje AI alata

Zadatci, upute za spajanje i kostur koda preuzeti su iz predloška vježbe. Početni program napisan je na temelju profesorova kostura.

Korišteni su AI alati OpenAI ChatGPT / Codex i Anthropic Claude.

- **ChatGPT / Codex** korišten je za prepisivanje bilježaka s mjerenjima, oblikovanje izvještaja i dopune koda, odnosno I2C skeniranje, inicijalizaciju senzora, procjenu slobodnog SRAM-a, raspored LED-ice i mjerenja pomoću `millis()` te upozorenje nakon 10 s bez odgovora senzora.
- **Claude** korišten je za jezično uređivanje i usklađivanje izvještaja i README-a, izgled izvještaja, opis mjesta provjere CRC i spajanja riječi u float u izvornom kodu biblioteke te za primjer ispisa serijskog monitora u zadatku 6, koji je složen prema prosjeku izmjerenom u laboratoriju T3-28.
