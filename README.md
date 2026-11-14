# Defro Air dla Home Assistant

Integracja rekuperatorów Defro Air (DRX) ze sterownikiem ST-340 v2, przez port
BMS (Modbus RTU) i bramkę RS-485 → Modbus TCP. Konfiguracja z interfejsu, bez
wpisów w `configuration.yaml`.

## Wymagania

- Home Assistant 2026.10 lub nowszy (integracja korzysta ze współdzielonych
  połączeń Modbus).
- Bramka RS-485 → Ethernet/Wi-Fi w trybie **Modbus TCP** (nie „RTU over TCP”),
  np. USR-DR164 lub Elfin EW11A, podłączona do zacisków BMS sterownika.
- Port szeregowy bramki ustawiony jak w sterowniku, domyślnie 19200 8E1.
- Komunikacja Modbus włączona w menu instalatora sterownika.

## Instalacja

HACS → Integracje → menu → Własne repozytoria → dodaj to repozytorium jako
„Integracja”, zainstaluj „Defro Air” i zrestartuj Home Assistanta.

Ręcznie: skopiuj katalog `custom_components/defro_air` do `config/custom_components`.

## Konfiguracja

Ustawienia → Urządzenia i usługi → Dodaj integrację → **Defro Air**. Podaj adres
IP bramki, port serwera TCP bramki i adres sterownika (domyślnie 1). W opcjach
wpisu można zmienić odstęp między odczytami (domyślnie 15 s).

## Karta dashboardu

Integracja dostarcza kartę wzorowaną na ekranie głównym panelu ST-340 v2:
schemat z temperaturami, przepływami i biegami, pasek ikon stanu oraz
sterowanie.

![Karta Defro Air w Home Assistant](docs/karta.png)

Nie trzeba niczego instalować osobno. W dashboardzie dodaj kartę
„Defro Air” z listy kart albo wklej w edytorze YAML:

```yaml
type: custom:defro-air-card
```

Karta sama znajduje encje integracji. Opcje (obie nieobowiązkowe):

```yaml
type: custom:defro-air-card
device_id: 0123456789abcdef   # gdy central jest więcej niż jedna
title: Rekuperator            # napis zamiast godziny w nagłówku
```

Co pokazuje i czym steruje:

- strzałki strumieni powietrza barwione temperaturą: nawiew przechodzi
  z niebieskiego w czerwony, wywiew z czerwonego w niebieski; strumień
  zatrzymanego wentylatora jest przygaszony,
- przy otwartym bypassie strumień wywiewany jest przygaszony i pojawia się
  napis BYPASS,
- górny pasek: ikony grzania wtórnego, antyzamarzania i awarii (podświetlone,
  gdy aktywne), sprawność odzysku z odzyskiwaną mocą oraz liczba dni filtrów,
- przyciski w jednym rzędzie, dopasowane do szerokości karty:
  - **party**: wybór czasu w minutach (od 15, co 15), start i zakończenie,
    pod przyciskiem widać pozostały czas,
  - **palenisko**: sam nawiew przez 3 minuty; ponowne kliknięcie kończy tryb,
  - **bypass**: włączenie i wyłączenie zezwolenia na bypass,
  - **stop, 1, 2, 3**: wybór biegu, jeśli program sterownika udostępnia
    rejestr 157,
  - **urlop**: wybór liczby dni, start i zakończenie.

Integracja sama dodaje kartę do zasobów dashboardu (Ustawienia → Dashboardy →
Zasoby) i aktualizuje jej adres przy zmianie wersji, więc wystarczy ponownie
otworzyć dashboard. Jeśli zasoby dashboardu są trzymane w YAML-u, karta ładuje
się ze stroną startową i po instalacji lub aktualizacji trzeba odświeżyć
przeglądarkę (Ctrl+F5).

## Encje

| Typ | Encje | Rejestry |
|---|---|---|
| sensor | wydatek nawiewu i wywiewu, bieg nawiewu i wywiewu | 100–103 |
| sensor | temperatury: czerpnia, wywiew, nawiew, wyrzutnia, kontrola nagrzewnicy, GWC*, grzanie wtórne* | 104–109, 155 |
| sensor | sprawność odzysku ciepła, odzyskiwana moc (wyliczane) | — |
| sensor | stan filtrów, kod błędów, zegar sterownika* | 138, 139, 152–153 |
| binary_sensor | awaria, bypass, antyzamarzanie, urlop, GWC*, grzanie wtórne*, wejścia cyfrowe* | 132–150, 154 |
| switch | bypass, GWC* | 141, 140 |
| number | urlop (dni), party (min), palenisko (s) | 145, 147, 146 |
| button | synchronizuj zegar | 152–153 |

\* domyślnie wyłączone w rejestrze encji.

Tylko w nowszych wersjach programu sterownika (rejestry 156–174):

| Typ | Encje | Rejestry |
|---|---|---|
| fan | wentylacja: bieg zadany 0–3 | 157 |
| switch | sterowanie tygodniowe, tryb okna, nawilżacz*, flow balancing* | 156, 158, 159, 168 |
| number | moc i przepływ biegów 1–3*, temperatury bypassu* | 161–166, 173–174 |
| sensor | czas pracy filtrów, rozmiar centrali | 170, 172 |

## Wersja programu sterownika

Moduł w wersji **MBP 1.1.4** udostępnia tylko rejestry 100–155. Integracja
wykrywa to sama i nie tworzy encji z zakresu 156–174, w tym wentylatora
z ustawianiem biegu. Po aktualizacji programu sterownika wystarczy przeładować
integrację.

## Uwagi do mapy rejestrów

Mapa pochodzi z instrukcji „ST-340 v2 Medium DEFRO” (program 2.1.61)
i została sprawdzona na centrali z modułem MBP 1.1.4:

- rejestr 105 to temperatura **wywiewu**, a 107 **wyrzutni**; instrukcja
  podaje je odwrotnie, panel sterownika potwierdza tę kolejność,
- niepodłączony czujnik temperatury zwraca 1715 (lub 63066 według instrukcji),
  encja jest wtedy w stanie „nieznany”,
- rejestry 126–128 (adres, prędkość, parzystość) nie są wystawione: ich zapis
  zerwałby łączność,
- party (147) to czas w minutach: wentylatory przechodzą na bieg 3, rejestr
  odlicza w dół, wartości 1–14 sterownik podnosi do 15, zapis 0 wyłącza tryb,
- w trybie urlop biegi nawiewu i wywiewu (102, 103) pokazują wartość 4,
  czyli pracę z mocą minimalną,
- palenisko (146) to czas w sekundach, najwyżej 180: nawiew przechodzi na
  bieg 3, wywiew na bieg 0, rejestr odlicza w dół, zapis 0 wyłącza tryb,
- bramka RS-485 obsługuje poprawnie jednego klienta naraz: drugi program
  Modbus uruchomiony równolegle z Home Assistantem może dostać cudzą odpowiedź.

## Testy

Home Assistant nie działa na Windows, więc testy uruchamia się w Dockerze:

```
docker build -t defro-air-tests -f tests/Dockerfile .
docker run --rm -v "${PWD}:/src" defro-air-tests
```

Odczyt z prawdziwej centrali bez Home Assistanta (niczego nie zapisuje):

```
python tools/live_read.py 192.168.1.50 8899 1
```
