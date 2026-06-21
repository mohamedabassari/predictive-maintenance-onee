#include <SPI.h>
#include <Adafruit_MAX31865.h>
#include <DHT.h>
#include <WiFi.h>
#include <PubSubClient.h>
#include <ArduinoJson.h>
const char* WIFI_SSID     = "mohamed";
const char* WIFI_PASSWORD = "12341234";
const char* MQTT_SERVER    = "192.168.137.5"; 
const int   MQTT_PORT      = 1883;
const char* MQTT_CLIENT_ID = "esp32-pompes";
const char* TOPIC_STATUS   = "station/status/esp32";

WiFiClient espClient;
PubSubClient mqtt(espClient);
#define DHTPIN 15
#define DHTTYPE DHT22
DHT dht(DHTPIN, DHTTYPE);

#define LED_GREEN 25
#define LED_YELLOW 26
#define LED_RED 27

#define BUZZER 14

#define CS1 5
#define CS2 17
#define CS3 16
#define CS4 4
#define CS5 2

#define SPI_MOSI 23
#define SPI_MISO 19
#define SPI_SCK 18

Adafruit_MAX31865 thermos[5] = {
  Adafruit_MAX31865(CS1), Adafruit_MAX31865(CS2),
  Adafruit_MAX31865(CS3), Adafruit_MAX31865(CS4),
  Adafruit_MAX31865(CS5)
};


#define RREF      430.0
#define RNOMINAL  100.0


unsigned long lastMeasure = 0;
const unsigned long MEASURE_INTERVAL = 1000;  // 1 mesure/seconde

void connectWiFi() {
  if (WiFi.status() == WL_CONNECTED) return;
  Serial.print("Connexion WiFi");
  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  unsigned long start = millis();
  while (WiFi.status() != WL_CONNECTED && millis() - start < 15000) {
    delay(500);
    Serial.print(".");
  }
  Serial.println(WiFi.status() == WL_CONNECTED ?
    "\nWiFi OK : " + WiFi.localIP().toString() : "\nWiFi ECHEC");
}

void connectMQTT() {
  if (mqtt.connected()) return;
  Serial.print("Connexion MQTT...");
  // Last Will : si l'ESP32 se deconnecte, le broker publie "offline"
  if (mqtt.connect(MQTT_CLIENT_ID, TOPIC_STATUS, 1, true, "offline")) {
    mqtt.publish(TOPIC_STATUS, "online", true);
    Serial.println(" OK");
  } else {
    Serial.print(" ECHEC, rc=");
    Serial.println(mqtt.state());
  }
}

void setup() {
  Serial.begin(115200);

  pinMode(LED_GREEN, OUTPUT);
  pinMode(LED_YELLOW, OUTPUT);
  pinMode(LED_RED, OUTPUT);
  pinMode(BUZZER, OUTPUT);

  dht.begin();
  SPI.begin(SPI_SCK, SPI_MISO, SPI_MOSI);

  for (int i = 0; i < 5; i++) {
    thermos[i].begin(MAX31865_3WIRE);
  }

  connectWiFi();
  mqtt.setServer(MQTT_SERVER, MQTT_PORT);
  mqtt.setBufferSize(512);
  connectMQTT();

  Serial.println("SYSTEME DEMARRE");
}

void loop() {
  // Maintien des connexions
  connectWiFi();
  connectMQTT();
  mqtt.loop();

  // Cadence non bloquante (1 Hz)
  if (millis() - lastMeasure < MEASURE_INTERVAL) return;
  lastMeasure = millis();

  float temps[5];
  bool faults[5];

  for (int i = 0; i < 5; i++) {
    temps[i] = thermos[i].temperature(RNOMINAL, RREF);
    uint8_t fault = thermos[i].readFault();
    faults[i] = (fault != 0);
    if (fault) {
      Serial.printf("PT100_%d FAULT 0x%02X\n", i + 1, fault);
      thermos[i].clearFault();
    }
  }

  float ambiante = dht.readTemperature();
  float humidite = dht.readHumidity();
  bool dhtOk = !isnan(ambiante) && !isnan(humidite);

  Serial.println("========== TEMPERATURES ==========");
  for (int i = 0; i < 5; i++) {
    Serial.printf("PT100_%d : %.2f C %s\n", i + 1, temps[i],
                  faults[i] ? "(DEFAUT)" : "");
  }
  Serial.printf("AMBIANTE : %s C | HUMIDITE : %s %%\n",
                dhtOk ? String(ambiante, 1).c_str() : "ERR",
                dhtOk ? String(humidite, 1).c_str() : "ERR");
  Serial.println("==================================");

  float maxTemp = -999;
  for (int i = 0; i < 5; i++) {
    if (!faults[i] && temps[i] > maxTemp) maxTemp = temps[i];
  }

  const char* etat;
  if (maxTemp < 50) {
    digitalWrite(LED_GREEN, HIGH);
    digitalWrite(LED_YELLOW, LOW);
    digitalWrite(LED_RED, LOW);
    digitalWrite(BUZZER, LOW);
    etat = "NORMAL";
  } else if (maxTemp < 70) {
    digitalWrite(LED_GREEN, LOW);
    digitalWrite(LED_YELLOW, HIGH);
    digitalWrite(LED_RED, LOW);
    tone(BUZZER, 2000, 200);
    etat = "ATTENTION";
  } else {
    digitalWrite(LED_GREEN, LOW);
    digitalWrite(LED_YELLOW, LOW);
    digitalWrite(LED_RED, HIGH);
    digitalWrite(BUZZER, HIGH);
    etat = "DANGER";
  }
  Serial.printf("ETAT : %s\n\n", etat);

  if (mqtt.connected()) {
    for (int i = 0; i < 5; i++) {
      if (faults[i]) continue;  // on ne publie pas un capteur en defaut

      StaticJsonDocument<128> doc;
      doc["temperature"] = roundf(temps[i] * 100) / 100;
      doc["pompe_id"]    = i + 1;

      char payload[128];
      serializeJson(doc, payload);

      char topic[64];
      snprintf(topic, sizeof(topic),
               "station/pompe/%d/pt100/avant/temperature", i + 1);
      mqtt.publish(topic, payload);
    }

    // Ambiance DHT11 -> station/ambiance/dht11
    if (dhtOk) {
      StaticJsonDocument<128> docA;
      docA["temperature"] = roundf(ambiante * 10) / 10;
      docA["humidite"]    = roundf(humidite * 10) / 10;

      char payloadA[128];
      serializeJson(docA, payloadA);
      mqtt.publish("station/ambiance/dht11", payloadA);
    }

    // Etat global -> station/etat
    mqtt.publish("station/etat", etat);
  }
}
