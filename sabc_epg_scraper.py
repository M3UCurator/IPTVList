#!/usr/bin/env python3
"""
SABC Sport EPG Scraper
Extracts TV schedule from SABC Sport website and generates EPG XML
"""

import requests
from lxml import etree
from datetime import datetime, timedelta
import logging
from typing import List, Dict, Optional
import json
import gzip

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class SABCSportScraper:
    """Scrapes SABC Sport TV schedule and generates EPG data"""
    
    BASE_URL = "https://www.sabcsport.com/tv/tv-schedule"
    
    HEADERS = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
        "Accept-Encoding": "gzip, deflate",
        "Connection": "keep-alive",
    }
    
    # Channel mappings
    CHANNELS = {
        "sabc_sport": {
            "id": "sabc.sport",
            "name": "SABC Sport",
            "icon": "https://www.sabcsport.com/logo.png"
        },
        "sabc_sport_1": {
            "id": "sabc.sport.1",
            "name": "SABC Sport 1",
            "icon": "https://www.sabcsport.com/logo.png"
        },
        "sabc_sport_2": {
            "id": "sabc.sport.2",
            "name": "SABC Sport 2",
            "icon": "https://www.sabcsport.com/logo.png"
        }
    }
    
    def __init__(self, timeout: int = 15):
        """Initialize scraper with timeout"""
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update(self.HEADERS)
    
    def fetch_schedule(self, channel: str, date: str) -> Optional[str]:
        """
        Fetch TV schedule HTML from SABC Sport
        
        Args:
            channel: Channel name (e.g., 'sabc_sport')
            date: Date in YYYY-MM-DD format
            
        Returns:
            HTML content as string, or None if request fails
        """
        url = f"{self.BASE_URL}/{channel}/{date}"
        
        try:
            logger.info(f"Fetching schedule from {url}")
            response = self.session.get(url, timeout=self.timeout)
            response.raise_for_status()
            
            logger.info(f"Successfully fetched {len(response.text)} bytes")
            return response.text
            
        except requests.exceptions.Timeout:
            logger.error(f"Timeout fetching {url}")
            return None
        except requests.exceptions.ConnectionError:
            logger.error(f"Connection error fetching {url}")
            return None
        except requests.exceptions.HTTPError as e:
            logger.error(f"HTTP error {e.response.status_code} fetching {url}")
            return None
        except Exception as e:
            logger.error(f"Error fetching {url}: {e}")
            return None
    
    def parse_html(self, html: str) -> Optional[etree._Element]:
        """Parse HTML content into lxml tree"""
        try:
            parser = etree.HTMLParser()
            tree = etree.fromstring(html, parser)
            return tree
        except Exception as e:
            logger.error(f"Error parsing HTML: {e}")
            return None
    
    def extract_programmes(self, tree: etree._Element) -> List[Dict]:
        """
        Extract programme data from HTML tree
        
        Args:
            tree: lxml element tree
            
        Returns:
            List of programme dictionaries
        """
        programmes = []
        
        try:
            # Try multiple selectors to find programme containers
            selectors = [
                "//div[contains(@class, 'programme')]",
                "//div[contains(@class, 'schedule-item')]",
                "//article[contains(@class, 'programme')]",
                "//*[@data-programme-id]",
            ]
            
            programme_elements = []
            for selector in selectors:
                programme_elements = tree.xpath(selector)
                if programme_elements:
                    logger.info(f"Found {len(programme_elements)} programmes using selector: {selector}")
                    break
            
            if not programme_elements:
                logger.warning("No programme elements found")
                return programmes
            
            for elem in programme_elements:
                try:
                    programme = self._parse_programme(elem)
                    if programme:
                        programmes.append(programme)
                except Exception as e:
                    logger.debug(f"Error parsing individual programme: {e}")
                    continue
            
            logger.info(f"Extracted {len(programmes)} programmes")
            return programmes
            
        except Exception as e:
            logger.error(f"Error extracting programmes: {e}")
            return programmes
    
    def _parse_programme(self, elem: etree._Element) -> Optional[Dict]:
        """Parse individual programme element"""
        
        # Try various XPath selectors
        title_selectors = [
            ".//span[@class='title']/text()",
            ".//h2/text()",
            ".//h3/text()",
            ".//div[@class='programme-title']/text()",
            ".//span[contains(@class, 'title')]/text()",
        ]
        
        description_selectors = [
            ".//span[@class='description']/text()",
            ".//p[@class='description']/text()",
            ".//div[@class='programme-desc']/text()",
            ".//span[contains(@class, 'description')]/text()",
        ]
        
        category_selectors = [
            ".//span[@class='category']/text()",
            ".//span[@class='genre']/text()",
            ".//div[@class='category']/text()",
        ]
        
        time_selectors = [
            ".//span[@class='start-time']/@data-time",
            ".//span[@class='start-time']/text()",
            ".//time/@datetime",
            ".//@data-start",
        ]
        
        def extract_text(selectors, elem):
            for sel in selectors:
                result = elem.xpath(sel)
                if result:
                    return result[0].strip() if isinstance(result[0], str) else str(result[0])
            return None
        
        title = extract_text(title_selectors, elem)
        if not title:
            return None
        
        programme = {
            'title': title,
            'description': extract_text(description_selectors, elem),
            'category': extract_text(category_selectors, elem),
            'start_time': extract_text(time_selectors, elem),
            'stop_time': None,
        }
        
        # Try to extract icon
        icon_results = elem.xpath(".//img[@class='icon']/@src | .//img[contains(@class, 'icon')]/@src")
        if icon_results:
            programme['icon'] = icon_results[0]
        
        return programme
    
    def create_epg_xml(self, channel_key: str, programmes: List[Dict]) -> bytes:
        """
        Create EPG XML structure
        
        Args:
            channel_key: Channel identifier key
            programmes: List of programme dictionaries
            
        Returns:
            XML as bytes
        """
        channel_info = self.CHANNELS.get(channel_key, self.CHANNELS['sabc_sport'])
        
        tv = etree.Element("tv")
        tv.set("generator-info-name", "SABCSport EPG Scraper")
        tv.set("generator-info-url", "https://github.com/M3UCurator/IPTVList")
        
        # Add channel
        channel = etree.SubElement(tv, "channel")
        channel.set("id", channel_info['id'])
        
        display_name = etree.SubElement(channel, "display-name")
        display_name.text = channel_info['name']
        
        icon = etree.SubElement(channel, "icon")
        icon.set("src", channel_info.get('icon', ''))
        
        # Add programmes
        for prog in programmes:
            if not prog.get('title'):
                continue
            
            programme = etree.SubElement(tv, "programme")
            
            # Set start and stop times
            if prog.get('start_time'):
                programme.set("start", prog['start_time'])
            if prog.get('stop_time'):
                programme.set("stop", prog['stop_time'])
            
            programme.set("channel", channel_info['id'])
            
            # Add title
            title = etree.SubElement(programme, "title")
            title.text = prog['title']
            
            # Add description
            if prog.get('description'):
                desc = etree.SubElement(programme, "desc")
                desc.text = prog['description']
            
            # Add category
            if prog.get('category'):
                category = etree.SubElement(programme, "category")
                category.text = prog['category']
            
            # Add icon
            if prog.get('icon'):
                icon_elem = etree.SubElement(programme, "icon")
                icon_elem.set("src", prog['icon'])
        
        xml = etree.tostring(
            tv,
            pretty_print=True,
            encoding="utf-8",
            xml_declaration=True
        )
        
        return xml
    
    def scrape_and_generate(self, channel: str, date: str, 
                           output_file: str = None, compress: bool = False) -> Optional[bytes]:
        """
        Complete workflow: fetch, parse, and generate EPG
        
        Args:
            channel: Channel name
            date: Date in YYYY-MM-DD format
            output_file: Optional output file path
            compress: Whether to compress output with gzip
            
        Returns:
            XML bytes (or gzipped bytes if compress=True), or None if failed
        """
        logger.info(f"Starting scrape for {channel} on {date}")
        
        # Fetch HTML
        html = self.fetch_schedule(channel, date)
        if not html:
            return None
        
        # Parse HTML
        tree = self.parse_html(html)
        if tree is None:
            return None
        
        # Extract programmes
        programmes = self.extract_programmes(tree)
        if not programmes:
            logger.warning("No programmes extracted")
        
        # Generate EPG XML
        xml = self.create_epg_xml(channel, programmes)
        
        # Compress if requested
        output_data = xml
        if compress:
            output_data = gzip.compress(xml)
            logger.info("Output compressed with gzip")
        
        # Save to file if specified
        if output_file:
            try:
                with open(output_file, 'wb') as f:
                    f.write(output_data)
                logger.info(f"EPG saved to {output_file}")
            except Exception as e:
                logger.error(f"Error saving to {output_file}: {e}")
        
        return output_data


def main():
    """Example usage"""
    scraper = SABCSportScraper()
    
    # Scrape for today
    today = datetime.now().strftime("%Y-%m-%d")
    
    xml = scraper.scrape_and_generate(
        channel="sabc_sport",
        date=today,
        output_file="sabc_sport_epg.xml.gz",
        compress=True
    )
    
    if xml:
        print("EPG generated successfully!")
        print(f"Output file: sabc_sport_epg.xml.gz")
        print(f"Compressed size: {len(xml)} bytes")
    else:
        print("Failed to generate EPG")


if __name__ == "__main__":
    main()
