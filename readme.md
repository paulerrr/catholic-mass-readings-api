# Catholic Mass Readings API

A self-hosted API that delivers daily Catholic mass readings from the United States Conference of Catholic Bishops (USCCB).

This project utilizes the [catholic-mass-readings](https://pypi.org/project/catholic-mass-readings/) PyPI package (v0.4.3).

## Features
- Daily mass readings in structured JSON format
- Liturgical season and color information
- Feast day identification
- Designed for self-hosting

## Installation

### Docker (Recommended)
```bash
# Copy the example configuration file
cp docker-compose.example.yml docker-compose.yml

# Edit docker-compose.yml to customize if needed

# Start the container
docker-compose up -d
```

### Standard Installation
```bash
pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port 8000
```

After installation, the API will be available at `http://localhost:8000`

## Available Endpoints
- `http://localhost:8000/` - API information
- `http://localhost:8000/mass/{date}` - Readings for a specific date (format: YYYY-MM-DD)
- `http://localhost:8000/docs` - Interactive documentation

## Implementation Example

```python
import requests

# Configuration
API_URL = "http://localhost:8000"  # Your self-hosted API address
DATE = "2025-02-27"  # Date to retrieve

def get_todays_readings():
    url = f"{API_URL}/mass/{DATE}"
    
    try:
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()
        
        print(f"📖 Mass Readings for {DATE}")
        print(f"🎄 Liturgical Season: {data['liturgical_info']['season']}")
        print(f"🏷️  Title: {data['title']}\n")
        
        for reading in data['readings']:
            print(f"====== {reading['type']} ======")
            print(f"Source: {reading['source']}")
            print("\n".join(reading['content'][:5]))  # First 5 lines
            print("\n")
            
    except requests.exceptions.RequestException as e:
        print(f"⚠️ Error fetching readings: {e}")

if __name__ == "__main__":
    get_todays_readings()
```