# Laboratorijska vježba 2

Serijska komunikacija na TTL i RS-485 fizičkom sloju

**Kolegij:** Primjena mikroupravljačkih sustava  
**Student:** Tomislav Perković  
**Datum:** 20. 10. 2026.  
**Repozitorij:** [PerKan21/Primjena-mikroupravljackih-sustava](https://github.com/PerKan21/Primjena-mikroupravljackih-sustava)

## Shema spajanja

| ESP32-S3 | Modul RS485 | Opis |
|---|---|---|
| 3V3 | VCC | Napajanje modula |
| GND | GND | Zajednička masa |
| GPIO17 | TXD | Podaci iz pločice u modul |
| GPIO5 | EN | Upravljanje smjerom, visoko znači odašiljanje |
| ne spaja se | RXD | Prijemni vod se u ovoj vježbi ne koristi |
| - | A i B | Terminacijski otpornik 120 Ω između vodova A i B |

```text
ESP32-S3                 Modul RS485 (MAX3485)
    3V3 ---------------- VCC
    GND ---------------- GND
 GPIO17 ---------------- TXD
  GPIO5 ---------------- EN
                         RXD   (nije spojen)
                         A ---+
                              120 Ω
                         B ---+
```

Modul se napaja s pina 3V3, jer je 5V iznad dopuštenog napona napajanja sklopa MAX3485.

## Biblioteke

| Biblioteka | Autor / izvor | Namjena |
|---|---|---|
| HardwareSerial (u jezgri) | Arduino / Espressif | Drugi serijski port na proizvoljnim pinovima |

HardwareSerial je dio jezgre Arduino za ESP32, pa u `lib_deps` nije potrebno dodavati nijednu biblioteku.

## Upute za prevođenje

1. U Visual Studio Codeu s dodatkom PlatformIO otvoriti mapu `Kod/LV2_RS485`.
2. Okruženje `esp32s3` već je postavljeno u datoteci `platformio.ini`.
3. Pokrenuti **Build**, zatim spojiti pločicu i pokrenuti **Upload**.
4. Otvoriti **Serial Monitor** na brzini **115200 baud**.

Za mjerenje osciloskopom u datoteci `src/main.cpp` postaviti `ISPITNI_UZORAK` na `true`, pa program neprekidno šalje znak U. S vrijednošću `false` program svake dvije sekunde šalje jedan okvir.

## Sadržaj repozitorija

| Datoteka | Opis |
|---|---|
| `Kod/LV2_RS485/src/main.cpp` | Program s riješenim zadatcima TODO 1 i TODO 2 |
| `Kod/LV2_RS485/platformio.ini` | Postavke PlatformIO projekta |
| `LV2_izvjestaj.pdf` | Izvještaj |
| `slike/` | Snimke zaslona osciloskopa |
| `LAB2_Fizicki_sloj_RS485.docx` | Predložak vježbe |

## Preuzeti sadržaj i korištenje AI alata

Zadatci, upute za spajanje i program s oznakama TODO preuzeti su iz predloška vježbe.

Korišten je AI alat **Anthropic Claude**.
