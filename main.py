from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import asyncio
import datetime
from datetime import timedelta
import re
import logging
import sys
from typing import List, Optional
from pydantic import BaseModel
from catholic_mass_readings import USCCB, models

# Set up logging
logging.basicConfig(stream=sys.stdout, level=logging.DEBUG)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Catholic Mass Readings API",
    description="API providing daily mass readings from USCCB",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def get_liturgical_season(date_obj):
    # Simplified liturgical calendar logic
    year = date_obj.year
    
    # Calculate Easter (Astronomical method)
    a = year % 19
    b = year // 100
    c = year % 100
    d = b // 4
    e = b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i = c // 4
    k = c % 4
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    easter_month = (h + l - 7 * m + 114) // 31
    easter_day = ((h + l - 7 * m + 114) % 31) + 1
    easter = datetime.date(year, easter_month, easter_day)
    
    # Calculate other dates
    ash_wednesday = easter - timedelta(days=46)
    pentecost = easter + timedelta(days=49)
    advent_start = datetime.date(year, 11, 27) + timedelta(days=(6 - datetime.date(year, 11, 27).weekday()))
    christmas = datetime.date(year, 12, 25)
    epiphany = datetime.date(year, 1, 6)
    
    # Determine season
    if date_obj >= ash_wednesday and date_obj < easter:
        return "Lent", "#7030A0"  # Purple
    elif date_obj >= easter and date_obj <= pentecost:
        return "Easter", "#FFFFFF"  # White
    elif date_obj >= advent_start and date_obj < christmas:
        return "Advent", "#7030A0"  # Purple
    elif (date_obj >= christmas and date_obj <= datetime.date(year, 12, 31)) or \
         (date_obj >= datetime.date(year, 1, 1) and date_obj <= epiphany):
        return "Christmas", "#FFFFFF"  # White
    else:
        return "Ordinary Time", "#008000"  # Green

def get_feast_day(title):
    """Extract feast day information from mass title"""
    feast_patterns = [
        r"Feast of (.+)",
        r"Solemnity of (.+)",
        r"Memorial of (.+)",
        r"Optional Memorial of (.+)"
    ]
    
    for pattern in feast_patterns:
        match = re.search(pattern, title)
        if match:
            return match.group(1)
    return None

def parse_reading_text(text: str) -> dict:
    """Parse the mass reading text into structured data"""
    logger.debug(f"Parsing text: {text[:200]}...")  # Log first 200 chars
    
    sections = []
    lines = text.split('\n')
    current_section = None
    url = None
    title = None
    
    for i, line in enumerate(lines):
        line = line.strip()
        if not line:
            continue
            
        logger.debug(f"Processing line {i}: {line}")
            
        # Catch URL
        if line.startswith('https://'):
            url = line
            logger.debug(f"Found URL: {url}")
            continue
            
        # Check for main title
        if not title and not line.startswith('R.') and not line.startswith('The word') and not line.startswith('The Gospel'):
            title = line
            logger.debug(f"Found title: {title}")
            continue
            
        # Check for section headers
        reading_match = re.search(r'(First Reading|Second Reading|Gospel|Responsorial Psalm|Alleluia):\s*(.*?)(?:\s+(\d+:\d+(?:-\d+)?))?\s*$', line)
        if reading_match:
            if current_section:
                sections.append(current_section)
                logger.debug(f"Added section: {current_section}")
            
            reading_type = reading_match.group(1)
            source = reading_match.group(2).strip() if reading_match.group(2) else ''
            verse = reading_match.group(3) if reading_match.group(3) else ''
            
            # Look ahead for verse numbers if not found in header
            if not verse:
                for next_line in lines[i+1:i+3]:
                    verse_match = re.search(r'(\d+:\d+(?:-\d+)?)', next_line)
                    if verse_match:
                        verse = verse_match.group(1)
                        break
            
            full_source = f"{source} {verse}".strip()
            logger.debug(f"Found reading: {reading_type} - {full_source}")
            
            current_section = {
                'type': reading_type,
                'source': full_source,
                'content': []
            }
            continue
            
        # Add content to current section
        if current_section:
            current_section['content'].append(line)
            
    # Add the last section
    if current_section:
        sections.append(current_section)
        logger.debug(f"Added final section: {current_section}")
        
    result = {
        'title': title,
        'url': url,
        'sections': sections
    }
    
    logger.debug(f"Final parsed result: {result}")
    return result

@app.get("/")
async def root():
    return {
        "message": "Catholic Mass Readings API",
        "endpoints": {
            "mass_readings": "/mass/{date}",
            "documentation": "/docs"
        }
    }

@app.get("/mass/{date}")
async def get_mass(date: str, mass_type: Optional[str] = None):
    try:
        date_obj = datetime.datetime.strptime(date, "%Y-%m-%d").date()
        logger.debug(f"Processing request for date: {date_obj}")
        
        async with USCCB() as usccb:
            available_types = await usccb.get_mass_types(date_obj)
            logger.debug(f"Available mass types: {available_types}")
            
            if mass_type:
                type_to_use = getattr(models.MassType, mass_type.upper())
            elif available_types:
                type_to_use = available_types[0]
            else:
                type_to_use = models.MassType.DEFAULT

            logger.debug(f"Using mass type: {type_to_use}")
            mass = await usccb.get_mass(date_obj, type_to_use)
            
            if not mass:
                raise HTTPException(status_code=404, detail="Mass readings not found")
            
            # Log the raw mass object
            logger.debug(f"Raw mass object: {str(mass)}")
            
            # Parse the mass text into structured data
            parsed_data = parse_reading_text(str(mass))
            
            # Get liturgical information
            season, color = get_liturgical_season(date_obj)
            feast_day = get_feast_day(parsed_data['title'])
            
            response = {
                "date": str(mass.date),
                "title": parsed_data['title'],
                "url": parsed_data['url'],
                "mass_type": type_to_use.name,
                "liturgical_info": {
                    "season": season,
                    "color": color,
                    "feast_day": feast_day
                },
                "readings": parsed_data['sections']
            }
            
            logger.debug(f"Final response: {response}")
            return response
            
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")
    except Exception as e:
        logger.error(f"Error processing request: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)