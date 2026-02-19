#include <Arduino.h>
#include <WiFi.h>
#include <PubSubClient.h>
#include "pinmap.h"

#ifndef DEVICE_NAME
#define DEVICE_NAME "pinpilot_device"
#endif

// ---- WiFi / MQTT (MVP placeholders) ----
const char* WIFI_SSID = "YOUR_WIFI";
const char* WIFI_PASS = "YOUR_PASS";

const char* MQTT_HOST = "192.168.1.10";   // your Orange Pi / broker
const int   MQTT_PORT = 1883;

WiFiClient espClient;
PubSubClient mqtt(espClient);

static void connectWiFi() {
  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASS);
  while (WiFi.status() != WL_CONNECTED) {
    delay(300);
    Serial.print(".");
  }
  Serial.println("\nWiFi connected");
}

static void mqttReconnect() {
  while (!mqtt.connected()) {
    Serial.print("MQTT connecting...");
    if (mqtt.connect(DEVICE_NAME)) {
      Serial.println("connected");
      mqtt.publish("pinpilot/status", "online");
    } else {
      Serial.print("failed rc=");
      Serial.print(mqtt.state());
      Serial.println(" retry in 2s");
      delay(2000);
    }
  }
}

void setup() {
  Serial.begin(115200);
  delay(200);

  // Example usage: configure pins if they exist
#ifdef EPAPER_SPI_2P13_CS
  pinMode(EPAPER_SPI_2P13_CS, OUTPUT);
  digitalWrite(EPAPER_SPI_2P13_CS, HIGH);
#endif

#ifdef WS2812_DIN
  pinMode(WS2812_DIN, OUTPUT);
  digitalWrite(WS2812_DIN, LOW);
#endif

  connectWiFi();
  mqtt.setServer(MQTT_HOST, MQTT_PORT);
}

void loop() {
  if (!mqtt.connected()) mqttReconnect();
  mqtt.loop();

  static uint32_t last = 0;
  if (millis() - last > 5000) {
    last = millis();
    mqtt.publish("pinpilot/heartbeat", DEVICE_NAME);
  }
}
