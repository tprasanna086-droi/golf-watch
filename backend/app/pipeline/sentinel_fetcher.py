"""
Fetch Sentinel-2 L2A imagery for glacial lake monitoring via Google Earth Engine.
"""

from __future__ import annotations

import datetime
import io
import logging
from pathlib import Path
from typing import TypedDict

import ee
import httpx
import numpy as np
import rasterio
from google.oauth2 import service_account

logger = logging.getLogger(__name__)

SENTINEL2_COLLECTION = "COPERNICUS/S2_SR_HARMONIZED"
SPECTRAL_BANDS = ("B3", "B4", "B8", "B11")
DERIVED_BANDS = ("ndwi", "turbidity")
ALL_BANDS = list(SPECTRAL_BANDS) + list(DERIVED_BANDS)


class Sentinel2TileResult(TypedDict):
    """Return value from fetch_sentinel2_tile."""

    image: ee.Image
    region: ee.Geometry
    band_names: list[str]
    date_start: str
    date_end: str
    cloud_filter_pct: float
    image_count: int


def initialize_gee(service_account_email: str, key_file: str) -> None:
    """
    Authenticate and initialize the Earth Engine Python API.

    When service_account_email and key_file are non-empty, use a service account
    key file. Otherwise call ee.Initialize() for local development (gcloud auth).
    """
    try:
        if service_account_email and key_file:
            key_path = Path(key_file)
            if not key_path.is_file():
                raise FileNotFoundError(f"GEE key file not found: {key_file}")
            logger.info(
                "Initializing GEE with service account %s",
                service_account_email,
            )
            credentials = service_account.Credentials.from_service_account_file(
                str(key_path),
                scopes=["https://www.googleapis.com/auth/earthengine"],
            )
            ee.Initialize(credentials=credentials)
        else:
            logger.info(
                "No service account provided; initializing GEE with default credentials"
            )
            ee.Initialize()
        logger.info("GEE initialized successfully")
    except ee.EEException as exc:
        msg = f"Google Earth Engine initialization failed: {exc}"
        logger.error(msg)
        raise RuntimeError(msg) from exc
    except Exception as exc:
        logger.exception("Unexpected error during GEE initialization")
        raise RuntimeError(
            f"Google Earth Engine initialization failed: {exc}"
        ) from exc


def fetch_sentinel2_tile(
    latitude: float,
    longitude: float,
    date_start: str,
    date_end: str,
    buffer_m: int = 5000,
    max_cloud_pct: float = 20.0,
) -> Sentinel2TileResult:
    """
    Build a median Sentinel-2 L2A composite for a buffered lake centroid.

    Filters by bounds, date range, and CLOUDY_PIXEL_PERCENTAGE, selects green,
    red, NIR, and SWIR bands, then adds NDWI and turbidity_index bands.
    """
    point = ee.Geometry.Point([longitude, latitude])
    region = point.buffer(buffer_m)

    try:
        collection = (
            ee.ImageCollection(SENTINEL2_COLLECTION)
            .filterBounds(region)
            .filterDate(date_start, date_end)
            .filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", max_cloud_pct))
        )
        image_count = int(collection.size().getInfo())

        if image_count == 0:
            raise ValueError(
                f"No Sentinel-2 scenes between {date_start} and {date_end} "
                f"with CLOUDY_PIXEL_PERCENTAGE < {max_cloud_pct}"
            )

        composite = collection.select(list(SPECTRAL_BANDS)).median()
        green = composite.select("B3")
        nir = composite.select("B8")
        swir = composite.select("B11")

        ndwi = green.subtract(nir).divide(green.add(nir)).rename("ndwi")
        turbidity = swir.divide(nir).rename("turbidity")
        image = composite.addBands([ndwi, turbidity])

        logger.info(
            "Built Sentinel-2 median composite (%d scenes) for (%.4f, %.4f)",
            image_count,
            latitude,
            longitude,
        )

        return {
            "image": image,
            "region": region,
            "band_names": ALL_BANDS.copy(),
            "date_start": date_start,
            "date_end": date_end,
            "cloud_filter_pct": max_cloud_pct,
            "image_count": image_count,
        }
    except ee.EEException as exc:
        msg = (
            f"Earth Engine error while fetching Sentinel-2 tile at "
            f"({latitude}, {longitude}) for {date_start}–{date_end}: {exc}"
        )
        logger.error(msg)
        raise RuntimeError(msg) from exc


def _structured_array_to_hwc(
    structured: np.ndarray,
    band_names: list[str],
) -> np.ndarray:
    """Stack a structured NumPy array into (height, width, channels)."""
    planes = [np.asarray(structured[band], dtype=np.float32) for band in band_names]
    return np.stack(planes, axis=-1)


def _download_via_compute_pixels(
    image: ee.Image,
    region: ee.Geometry,
    scale: int,
    band_names: list[str],
) -> np.ndarray:
    """Download pixels using ee.data.computePixels (NUMPY_NDARRAY)."""
    clipped = image.clipToBoundsAndScale(geometry=region, scale=scale)
    structured = ee.data.computePixels(
        {
            "expression": clipped,
            "fileFormat": "NUMPY_NDARRAY",
            "bandIds": band_names,
        }
    )
    return _structured_array_to_hwc(structured, band_names)


def _download_via_get_download_url(
    image: ee.Image,
    region: ee.Geometry,
    scale: int,
) -> np.ndarray:
    """Download pixels via getDownloadURL and read GeoTIFF bytes with rasterio."""
    clipped = image.clipToBoundsAndScale(geometry=region, scale=scale)
    url = clipped.getDownloadURL(
        {
            "scale": scale,
            "region": region,
            "format": "GEO_TIFF",
        }
    )
    logger.info("Downloading tile from Earth Engine export URL")
    response = httpx.get(url, timeout=300.0)
    response.raise_for_status()
    with rasterio.open(io.BytesIO(response.content)) as dataset:
        data = dataset.read().astype(np.float32)
    return np.transpose(data, (1, 2, 0))


def download_tile_as_array(
    image: ee.Image,
    region: ee.Geometry,
    scale: int = 10,
) -> np.ndarray:
    """
    Export an ee.Image over region to a float32 NumPy array of shape (H, W, C).
    """
    band_names = image.bandNames().getInfo()
    try:
        try:
            array = _download_via_compute_pixels(image, region, scale, band_names)
        except (ee.EEException, AttributeError, TypeError, KeyError) as exc:
            logger.warning(
                "computePixels download failed (%s); trying getDownloadURL",
                exc,
            )
            array = _download_via_get_download_url(image, region, scale)
        logger.info("Downloaded tile array shape: %s", array.shape)
        return array.astype(np.float32, copy=False)
    except ee.EEException as exc:
        msg = f"Earth Engine error while downloading tile pixels: {exc}"
        logger.error(msg)
        raise RuntimeError(msg) from exc


def _last_three_months_range() -> tuple[str, str]:
    """Return (date_start, date_end) ISO strings for the past 90 days."""
    today = datetime.date.today()
    start = today - datetime.timedelta(days=90)
    return start.isoformat(), today.isoformat()


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )

    imja_lat = 27.8975
    imja_lon = 86.9175
    date_start, date_end = _last_three_months_range()

    try:
        initialize_gee("", "")
        tile = fetch_sentinel2_tile(
            latitude=imja_lat,
            longitude=imja_lon,
            date_start=date_start,
            date_end=date_end,
        )
        print(f"image_count: {tile['image_count']}")
        print(f"band_names: {tile['band_names']}")
    except (RuntimeError, ValueError) as exc:
        logger.error("Sentinel fetch demo failed: %s", exc)
        raise
