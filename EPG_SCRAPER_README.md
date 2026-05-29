## SABC Sport EPG Scraper

A Python-based automated scraper for SABC Sport TV schedules that generates Electronic Program Guide (EPG) XML files.

### Features

✅ **Automated Daily Scraping** - Scheduled via cron or GitHub Actions  
✅ **Multi-Channel Support** - Scrape SABC Sport, SABC Sport 1, SABC Sport 2  
✅ **EPG XML Generation** - Standard XMLTV format  
✅ **Flexible Scheduling** - Scrape 1 day, 7 days, or custom range  
✅ **Error Handling** - Robust fallback selectors and timeout protection  
✅ **Logging** - Track all operations with detailed logs  

### Installation

```bash
# 1. Clone the repository
git clone https://github.com/M3UCurator/IPTVList.git
cd IPTVList

# 2. Install dependencies
pip install -r requirements.txt
```

### Usage

#### Quick Start (Scrape Today)

```bash
python daily_scraper.py
```

#### Scrape Multiple Days

```bash
# Scrape next 7 days
python daily_scraper.py --days 7
```

#### Scrape Specific Channels

```bash
# Scrape only SABC Sport and SABC Sport 1
python daily_scraper.py --channels sabc_sport sabc_sport_1
```

#### Custom Output Directory

```bash
# Save EPG files to custom directory
python daily_scraper.py --output ./my_epg_data
```

#### Full Example

```bash
python daily_scraper.py \
  --days 7 \
  --channels sabc_sport sabc_sport_1 \
  --output ./epg_data
```

### Advanced: Using the Scraper Class

```python
from sabc_epg_scraper import SABCSportScraper
from datetime import datetime

scraper = SABCSportScraper()

# Scrape and save to file
xml = scraper.scrape_and_generate(
    channel="sabc_sport",
    date="2026-05-29",
    output_file="sabc_sport_epg.xml"
)

# Or just get the XML bytes
if xml:
    print(xml.decode('utf-8'))
```

### Output

The scraper generates EPG XML files in XMLTV format:

```xml
<?xml version="1.0" encoding="utf-8"?>
<tv generator-info-name="SABCSport EPG Scraper" generator-info-url="https://github.com/M3UCurator/IPTVList">
  <channel id="sabc.sport">
    <display-name>SABC Sport</display-name>
    <icon src="https://www.sabcsport.com/logo.png"/>
  </channel>
  <programme start="20260529172900 +0200" stop="20260529192900 +0200" channel="sabc.sport">
    <title>Premier League Matches 2025</title>
    <desc>Newcastle vs Everton</desc>
    <category>Sports</category>
    <icon src="..."/>
  </programme>
</tv>
```

### Schedule with Cron

Add to your crontab to run daily at midnight:

```bash
crontab -e
```

Add this line:

```cron
0 0 * * * cd /path/to/IPTVList && python daily_scraper.py --days 7 >> epg_scraper.log 2>&1
```

### GitHub Actions (Pending)

A GitHub Actions workflow file is being added to automate scraping directly in the repository. Once merged, EPG files will be automatically generated and committed daily.

### Logging

Logs are written to `epg_scraper.log` and console output:

```
2026-05-29 16:45:28,123 - INFO - Fetching schedule from https://www.sabcsport.com/tv/tv-schedule/sabc_sport/2026-05-29
2026-05-29 16:45:28,456 - INFO - Successfully fetched 45000 bytes
2026-05-29 16:45:28,789 - INFO - Found 12 programmes using selector: //div[contains(@class, 'programme')]
```

### File Structure

```
IPTVList/
├── sabc_epg_scraper.py      # Main scraper class
├── daily_scraper.py         # Standalone daily scraper script
├── requirements.txt         # Python dependencies
├── epg_data/                # Output directory (auto-created)
│   ├── sabc_sport_2026-05-29.xml
│   ├── sabc_sport_1_2026-05-29.xml
│   └── ...
└── epg_scraper.log          # Log file
```

### Troubleshooting

#### No programmes found

If the scraper finds no programmes, the website HTML structure may have changed. Check the selectors in `_parse_programme()` method and update them accordingly:

```python
# In sabc_epg_scraper.py
title_selectors = [
    ".//span[@class='title']/text()",
    ".//h2/text()",
    # Add more selectors if needed
]
```

#### Connection errors

Check your internet connection and verify the SABC Sport website is accessible:

```bash
curl -I https://www.sabcsport.com/tv/tv-schedule/sabc_sport/2026-05-29
```

#### Permission denied when saving files

Ensure the output directory is writable:

```bash
chmod 755 epg_data/
```

### Contributing

To improve the scraper:

1. Test with different dates and channels
2. Report any HTML structure changes
3. Submit improvements via pull requests

### License

MIT License - See LICENSE file for details

### Resources

- [XMLTV Format Documentation](http://www.xmltv.org/)
- [lxml Documentation](https://lxml.de/)
- [SABC Sport Website](https://www.sabcsport.com/)
