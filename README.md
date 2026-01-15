# SLAVI Calculator

Aplikacja webowa do obliczania indeksu **SLAVI (Specific Leaf Area Vegetation Index)** z wykorzystaniem danych rastrowych i wektorowych.

![Python](https://img.shields.io/badge/Python-3.11-blue)
![Streamlit](https://img.shields.io/badge/Streamlit-1.40-red)
![Docker](https://img.shields.io/badge/Docker-Ready-blue)
![License](https://img.shields.io/badge/License-MIT-green)

## Opis

SLAVI (Specific Leaf Area Vegetation Index) to wskaźnik roślinności wykorzystywany do estymacji powierzchni liści (LAI - Leaf Area Index). Jest szczególnie przydatny w:
- Monitorowaniu kondycji roślinności
- Analizie biomasy
- Ocenie stresu roślin
- Badaniach ekologicznych

### Wzór

```
SLAVI = NIR / (Red + SWIR)
```

Gdzie:
- **NIR** - pasmo bliskiej podczerwieni (Near Infrared), np. Sentinel-2 Band 8 (~842nm)
- **Red** - pasmo czerwone, np. Sentinel-2 Band 4 (~665nm)
- **SWIR** - pasmo krótkiej podczerwieni (Short-Wave Infrared), np. Sentinel-2 Band 11 (~1610nm)

## Uruchomienie z Docker

### Wymagania
- Docker
- Docker Compose

### Uruchomienie

```bash
git clone https://github.com/TWOJE_REPOZYTORIUM/slavi-app.git
cd slavi-app

docker-compose up --build

docker-compose up -d --build
```

Aplikacja będzie dostępna pod adresem: **http://localhost:8501**

### Zatrzymanie

```bash
docker-compose down
```

## Uruchomienie lokalne (bez Docker)

### Wymagania
- Python 3.11+
- GDAL

### Instalacja

```bash
python -m venv venv
source venv/bin/activate # Linux
venv\Scripts\activate # Windows

pip install -r requirements.txt

streamlit run app/main.py
```

## Wymagane dane wejściowe

### Dane rastrowe (GeoTIFF)

Aplikacja obsługuje dwa tryby wczytywania danych rastrowych:

#### Tryb 1: Oddzielne pliki dla każdego pasma
- **NIR.tif** - pasmo bliskiej podczerwieni
- **Red.tif** - pasmo czerwone  
- **SWIR.tif** - pasmo krótkiej podczerwieni

#### Tryb 2: Wielopasmowy raster
- Pojedynczy plik GeoTIFF zawierający wszystkie wymagane pasma
- Należy wskazać numery pasm dla NIR, Red i SWIR

### Dane wektorowe (GeoJSON)

Plik GeoJSON z poligonami reprezentującymi obszary do analizy zonalnej.

## Interpretacja wyników

| Wartość SLAVI | Interpretacja |
|---------------|---------------|
| < 0.5 | Niska gęstość roślinności / gleba |
| 0.5 - 1.0 | Umiarkowana roślinność |
| 1.0 - 2.0 | Gęsta roślinność |
| > 2.0 | Bardzo gęsta roślinność / las |

*Wartości mogą się różnić w zależności od typu roślinności i warunków atmosferycznych.*

## Przedstawienie aplikacji

### Strona główna

![main_page.png](img\main_page.png)

### Panel boczny

Wariant dla plików lokalnych:

![local_files_menu.png](img\local_files_menu.png)

Wariant dla przesyłu plików:

![manual_upload_menu.png](img\manual_upload_menu.png)

### Strona wynikowa

Obliczone wartości:

![calculated_slavi_values.png](img\calculated_slavi_values.png)

Wygenerowana mapa dla przesłanych plików:

![slavi_map.png](img\slavi_map.png)

Histogram rozkładu wartości indeksu:

![slavi_histogram.png](img\slavi_histogram.png)

Wykres obliczonych wartości średnich z podziałem na obszary:

![slavi_values_chart.png](img\slavi_values_chart.png)

Statystyki obliczone dla każdego z obszaru:

![zonal-statistics.png](img\zonal-statistics.png)

Dostepne opcje eksportu danych:

![export_options.png](img\export_options.png)

Przykładowa mapa interaktywna dostępna jest w pliku [slavi_interactive_map.html](img\slavi_interactive_map.html)