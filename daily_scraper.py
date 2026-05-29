#!/usr/bin/env python3
"""
Daily EPG Scraper Script
Scheduled scraper for SABC Sport TV schedules
Can be run manually or via cron/scheduler
"""

import argparse
import logging
from datetime import datetime, timedelta
from pathlib import Path
from sabc_epg_scraper import SABCSportScraper

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('epg_scraper.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Default channels to scrape
DEFAULT_CHANNELS = ["sabc_sport", "sabc_sport_1", "sabc_sport_2"]

# Default output directory
DEFAULT_OUTPUT_DIR = "epg_data"


def create_output_directory(output_dir: str) -> Path:
    """Create output directory if it doesn't exist"""
    path = Path(output_dir)
    path.mkdir(parents=True, exist_ok=True)
    return path


def scrape_daily_schedule(
    output_dir: str = DEFAULT_OUTPUT_DIR,
    channels: list = None,
    days: int = 1
) -> dict:
    """
    Scrape EPG data for specified channels and days
    
    Args:
        output_dir: Directory to save EPG files
        channels: List of channels to scrape (defaults to DEFAULT_CHANNELS)
        days: Number of days to scrape (starting from today)
        
    Returns:
        Dictionary with scraping results
    """
    
    if channels is None:
        channels = DEFAULT_CHANNELS
    
    output_path = create_output_directory(output_dir)
    scraper = SABCSportScraper()
    
    results = {
        "timestamp": datetime.now().isoformat(),
        "successful": [],
        "failed": [],
        "total": 0
    }
    
    logger.info(f"Starting EPG scrape for {days} day(s) across {len(channels)} channel(s)")
    
    # Scrape for specified number of days
    for i in range(days):
        date = (datetime.now() + timedelta(days=i)).strftime("%Y-%m-%d")
        
        for channel in channels:
            results["total"] += 1
            filename = output_path / f"sabc_{channel}_{date}.xml"
            
            try:
                xml = scraper.scrape_and_generate(
                    channel=channel,
                    date=date,
                    output_file=str(filename)
                )
                
                if xml:
                    file_size = filename.stat().st_size if filename.exists() else 0
                    results["successful"].append({
                        "channel": channel,
                        "date": date,
                        "file": str(filename),
                        "size": file_size
                    })
                    logger.info(f"✓ Generated {filename} ({file_size} bytes)")
                else:
                    results["failed"].append({
                        "channel": channel,
                        "date": date,
                        "reason": "No data returned"
                    })
                    logger.warning(f"✗ No data for {channel} on {date}")
                    
            except Exception as e:
                results["failed"].append({
                    "channel": channel,
                    "date": date,
                    "reason": str(e)
                })
                logger.error(f"✗ Error processing {channel} on {date}: {e}")
    
    return results


def print_summary(results: dict):
    """Print scraping summary"""
    print("\n" + "="*60)
    print("EPG SCRAPING SUMMARY")
    print("="*60)
    print(f"Timestamp: {results['timestamp']}")
    print(f"Total jobs: {results['total']}")
    print(f"Successful: {len(results['successful'])}")
    print(f"Failed: {len(results['failed'])}")
    
    if results["successful"]:
        print("\n✓ Successful Files:")
        for item in results["successful"]:
            print(f"  - {item['file']} ({item['size']} bytes)")
    
    if results["failed"]:
        print("\n✗ Failed Jobs:")
        for item in results["failed"]:
            print(f"  - {item['channel']} ({item['date']}): {item['reason']}")
    
    print("="*60 + "\n")


def main():
    parser = argparse.ArgumentParser(
        description="SABC Sport EPG Scraper",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Scrape today for all channels
  python daily_scraper.py
  
  # Scrape next 7 days
  python daily_scraper.py --days 7
  
  # Scrape specific channels only
  python daily_scraper.py --channels sabc_sport sabc_sport_1
  
  # Custom output directory
  python daily_scraper.py --output ./my_epg_data
        """
    )
    
    parser.add_argument(
        "--output",
        default=DEFAULT_OUTPUT_DIR,
        help=f"Output directory for EPG files (default: {DEFAULT_OUTPUT_DIR})"
    )
    
    parser.add_argument(
        "--channels",
        nargs="+",
        default=DEFAULT_CHANNELS,
        help=f"Channels to scrape (default: {' '.join(DEFAULT_CHANNELS)})"
    )
    
    parser.add_argument(
        "--days",
        type=int,
        default=1,
        help="Number of days to scrape starting from today (default: 1)"
    )
    
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress console output (logging still goes to file)"
    )
    
    args = parser.parse_args()
    
    # Run scraper
    results = scrape_daily_schedule(
        output_dir=args.output,
        channels=args.channels,
        days=args.days
    )
    
    # Print summary if not quiet
    if not args.quiet:
        print_summary(results)
    
    logger.info(f"Scraping completed: {len(results['successful'])} successful, {len(results['failed'])} failed")
    
    # Exit with error code if any failed
    return 1 if results["failed"] else 0


if __name__ == "__main__":
    exit(main())
