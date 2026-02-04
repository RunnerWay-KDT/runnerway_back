import sys
import os
import logging

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.database import SessionLocal
from app.models.elevation import ElevationCache
from sqlalchemy import text

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def check_cache():
    db = SessionLocal()
    try:
        # User reported coordinate causing 429: approx 37.4866, 127.0364
        target_lat = 37.4866
        target_lon = 127.0364
        
        logger.info(f"Checking cache near {target_lat}, {target_lon}...")
        
        # Check within 100m (approx 0.001 degrees)
        query = text("""
            SELECT count(*) FROM elevation_cache 
            WHERE latitude BETWEEN :min_lat AND :max_lat 
            AND longitude BETWEEN :min_lon AND :max_lon
        """)
        
        cnt = db.execute(query, {
            "min_lat": target_lat - 0.001,
            "max_lat": target_lat + 0.001,
            "min_lon": target_lon - 0.001,
            "max_lon": target_lon + 0.001
        }).scalar()
        
        logger.info(f"Found {cnt} points within ~100m box.")
        
        if cnt > 0:
            # Show the points
            points = db.query(ElevationCache).filter(
                ElevationCache.latitude.between(target_lat - 0.001, target_lat + 0.001),
                ElevationCache.longitude.between(target_lon - 0.001, target_lon + 0.001)
            ).all()
            for p in points:
                logger.info(f" - Point: ({p.latitude}, {p.longitude}), Elev: {p.elevation}")
        else:
            logger.warning("No points found! Pre-caching might not have reached here yet or data is missing.")

    except Exception as e:
        logger.error(f"Error: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    check_cache()
