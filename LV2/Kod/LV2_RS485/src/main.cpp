#include <Arduino.h>

#define PIN_TX    17
#define PIN_EN     5
#define BRZINA    115200

// true: neprekidno salje znak 'U' (0x55) za rad s osciloskopom
// false: svake dvije sekunde salje jedan okvir
const bool ISPITNI_UZORAK = false;

uint32_t brojac = 0;
uint32_t zastita_us = 0;        // zastitno vrijeme prije oslobadanja smjera

void posalji(const char* tekst) {
  // TODO 1: preuzmi smjer, posalji, pricekaj prazan medjuspremnik
  digitalWrite(PIN_EN, HIGH);
  Serial1.write((const uint8_t*)tekst, strlen(tekst));
  Serial1.flush();

  // TODO 2: zadnji znak mozda jos izlazi iz posmacnog registra,
  //         pa se ceka trajanje jednog cijelog znaka
  delayMicroseconds(zastita_us);

  digitalWrite(PIN_EN, LOW);
}

void setup() {
  Serial.begin(115200);
  delay(300);

  pinMode(PIN_EN, OUTPUT);
  digitalWrite(PIN_EN, LOW);          // u mirovanju ne odasiljemo

  // RX pin je -1 jer u ovoj vjezbi samo odasiljemo
  Serial1.begin(BRZINA, SERIAL_8N1, -1, PIN_TX);

  // TODO 2: trajanje jednog znaka u us (8N1 = 10 bitova po znaku)
  zastita_us = 10UL * 1000000UL / BRZINA;   // = 86 us pri 115200

  Serial.printf("brzina %d bit/s\n", BRZINA);
  Serial.printf("trajanje bita %.2f us\n", 1000000.0 / BRZINA);
  Serial.printf("trajanje znaka %.2f us\n", 10 * 1000000.0 / BRZINA);
  Serial.printf("zastitno vrijeme %lu us\n", zastita_us);
}

void loop() {
  if (ISPITNI_UZORAK) {               // samo za mjerenje na osciloskopu
    posalji("UUUUUUUU");
    delay(5);
    return;
  }

  char okvir[32];
  snprintf(okvir, sizeof(okvir), "PMS;%04lu\n", brojac++);
  posalji(okvir);
  Serial.printf("poslano: %s", okvir);
  delay(2000);
}
