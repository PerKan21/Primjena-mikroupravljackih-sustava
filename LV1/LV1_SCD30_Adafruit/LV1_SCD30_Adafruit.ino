#include <Wire.h>
#include <Adafruit_SCD30.h>

Adafruit_SCD30 senzor;

const uint8_t SCD30_ADDR = 0x61;
const uint8_t LED_PIN = 13;

unsigned long tMjerenje = 0;
unsigned long tLed = 0;
bool ledStanje = false;

unsigned long tZadnjiOdgovor = 0;
bool senzorSpreman = false;
bool upozorenjeIspisano = false;

// Procjena slobodnog SRAM-a za ATmega328P (Arduino Nano).
extern int __heap_start, *__brkval;

int slobodniSRAM() {
  int lokalnaVarijabla;
  return (int)&lokalnaVarijabla -
         (__brkval == 0 ? (int)&__heap_start : (int)__brkval);
}

void skenirajI2C() {
  Serial.println(F("Skeniranje I2C sabirnice..."));
  bool pronadenUredaj = false;

  for (uint8_t a = 1; a <= 126; a++) {
    Wire.beginTransmission(a);
    if (Wire.endTransmission() == 0) {
      Serial.print(F("Pronaden uredaj: 0x"));
      if (a < 16) Serial.print('0');
      Serial.println(a, HEX);
      pronadenUredaj = true;
    }
  }

  if (!pronadenUredaj) Serial.println(F("Nema I2C uredaja!"));
}

void setup() {
  Serial.begin(115200);
  pinMode(LED_PIN, OUTPUT);
  Wire.begin();
  Wire.setClock(100000);

  // Ogranicenje cekanja na I2C kako prekid veze ne bi zaglavio program.
  // Zahtijeva AVR Wire biblioteku s podrskom za setWireTimeout.
  Wire.setWireTimeout(25000, true);

  Serial.println(F("Pokretanje programa..."));
  skenirajI2C();

  senzorSpreman = senzor.begin(SCD30_ADDR, &Wire);
  if (senzorSpreman) {
    Serial.println(F("SCD30 uspjesno pokrenut!"));
  } else {
    Serial.println(F("SCD30 nije pronaden ili inicijalizacija nije uspjela!"));
  }
  tZadnjiOdgovor = millis();

  Serial.print(F("Slobodni SRAM pri pokretanju: "));
  Serial.print(slobodniSRAM());
  Serial.println(F(" B"));
}

void loop() {
  const unsigned long sada = millis();

  // LED radi neovisno o rasporedu mjerenja.
  if (sada - tLed >= 500) {
    tLed = sada;
    ledStanje = !ledStanje;
    digitalWrite(LED_PIN, ledStanje);
  }

  if (sada - tMjerenje >= 2000) {
    tMjerenje = sada;

    if (!senzorSpreman) {
      Serial.println(F("Senzor nije dostupan."));
    } else {
      Wire.beginTransmission(SCD30_ADDR);
      if (Wire.endTransmission() != 0) {
        Serial.println(F("GRESKA: SCD30 ne odgovara!"));
      } else {
        // Ovo je vrijeme odgovora na I2C, a ne zadnjeg uspjesnog mjerenja.
        tZadnjiOdgovor = millis();
        upozorenjeIspisano = false;

        if (!senzor.dataReady()) {
          Serial.println(F("Podatak jos nije spreman."));
        } else if (!senzor.read()) {
          Serial.println(F("Greska pri citanju mjerenja!"));
        } else {
          Serial.print(F("CO2: "));
          Serial.print(senzor.CO2, 0);
          Serial.print(F(" ppm | Temperatura: "));
          Serial.print(senzor.temperature, 2);
          Serial.print(F(" C | Vlaga: "));
          Serial.print(senzor.relative_humidity, 2);
          Serial.println(F(" %"));
        }
      }
    }
  }

  // Svjeza vremenska oznaka izbjegava oduzimanje starijeg vremena
  // od tZadnjiOdgovor azuriranog tijekom I2C komunikacije.
  if (!upozorenjeIspisano && millis() - tZadnjiOdgovor >= 10000) {
    Serial.println(F("UPOZORENJE: SCD30 ne odgovara vise od 10 s!"));
    upozorenjeIspisano = true;
  }
}
