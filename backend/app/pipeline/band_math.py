"""
Pure NumPy spectral index and mask utilities for Sentinel-2 preprocessing.
"""

from __future__ import annotations

import math

import numpy as np
from skimage.measure import label, regionprops

PI = math.pi


def compute_ndwi(green: np.ndarray, nir: np.ndarray) -> np.ndarray:
    """
    Compute the Normalized Difference Water Index (NDWI).

    NDWI = (Green - NIR) / (Green + NIR). Values above 0 typically indicate
    water. Output is clipped to [-1, 1] as float32; non-finite results from
    division by zero are set to 0.0.
    """
    green = np.asarray(green, dtype=np.float64)
    nir = np.asarray(nir, dtype=np.float64)
    denominator = green + nir
    with np.errstate(divide="ignore", invalid="ignore"):
        ndwi = (green - nir) / denominator
    ndwi = np.where(np.isfinite(ndwi), ndwi, 0.0)
    return np.clip(ndwi, -1.0, 1.0).astype(np.float32)


def compute_turbidity(swir: np.ndarray, nir: np.ndarray) -> np.ndarray:
    """
    Compute a turbidity proxy as SWIR / NIR.

    Output is clipped to [0, 10] as float32; non-finite results from division
    by zero are set to 0.0.
    """
    swir = np.asarray(swir, dtype=np.float64)
    nir = np.asarray(nir, dtype=np.float64)
    with np.errstate(divide="ignore", invalid="ignore"):
        turbidity = swir / nir
    turbidity = np.where(np.isfinite(turbidity), turbidity, 0.0)
    return np.clip(turbidity, 0.0, 10.0).astype(np.float32)


def compute_shape_irregularity(mask: np.ndarray) -> float:
    """
    Measure mask compactness as perimeter² / (4π × area).

    A perfect circle scores 1.0; more irregular shapes score higher. Returns
    0.0 when the mask has no positive area. Uses the largest connected
    component when multiple regions are present.
    """
    binary = np.asarray(mask) > 0
    if not np.any(binary):
        return 0.0

    labeled = label(binary)
    regions = regionprops(labeled)
    if not regions:
        return 0.0

    region = max(regions, key=lambda props: props.area)
    area = float(region.area)
    if area <= 0.0:
        return 0.0

    perimeter = float(region.perimeter)
    return float((perimeter**2) / (4.0 * PI * area))


def extract_water_mask(ndwi: np.ndarray, threshold: float = 0.0) -> np.ndarray:
    """
    Build a binary water mask where NDWI exceeds threshold.

    Returns a uint8 array of 0 and 1 with the same shape as ndwi.
    """
    ndwi = np.asarray(ndwi)
    return (ndwi > threshold).astype(np.uint8)


def normalize_bands(array: np.ndarray) -> np.ndarray:
    """
    Min-max normalize each channel of an (H, W, C) array to [0, 1].

    Constant channels (max == min) are set to zero. Returns float32.
    """
    data = np.asarray(array, dtype=np.float32)
    if data.ndim != 3:
        raise ValueError(f"Expected shape (H, W, C), got {data.shape}")

    normalized = np.zeros_like(data, dtype=np.float32)
    for channel in range(data.shape[2]):
        band = data[:, :, channel]
        band_min = float(band.min())
        band_max = float(band.max())
        if band_max > band_min:
            normalized[:, :, channel] = (band - band_min) / (band_max - band_min)
    return normalized


def estimate_area_km2(
    mask: np.ndarray,
    latitude: float,
    scale_m: int = 10,
) -> float:
    """
    Estimate the area of positive mask pixels in km².

    Each pixel represents scale_m × scale_m metres on the ground, scaled by
    cos(latitude) to approximate meridian convergence.
    """
    binary = np.asarray(mask) > 0
    pixel_count = int(np.count_nonzero(binary))
    if pixel_count == 0:
        return 0.0

    pixel_area_m2 = (scale_m * scale_m) * math.cos(math.radians(latitude))
    area_m2 = pixel_count * pixel_area_m2
    return float(area_m2 / 1_000_000.0)


if __name__ == "__main__":
    rng = np.random.default_rng(42)
    height, width = 64, 64

    green = rng.uniform(0.05, 0.4, (height, width)).astype(np.float32)
    nir = rng.uniform(0.02, 0.3, (height, width)).astype(np.float32)
    swir = rng.uniform(0.01, 0.5, (height, width)).astype(np.float32)

    green[20:40, 20:40] = 0.6
    nir[20:40, 20:40] = 0.1

    ndwi = compute_ndwi(green, nir)
    turbidity = compute_turbidity(swir, nir)
    water_mask = extract_water_mask(ndwi, threshold=0.0)

    y, x = np.ogrid[:height, :width]
    circle = ((x - 32) ** 2 + (y - 32) ** 2) <= 15**2
    irregular = np.zeros((height, width), dtype=np.uint8)
    irregular[10:50, 28:36] = 1

    multi_band = np.stack([green, nir, swir], axis=-1)
    normalized = normalize_bands(multi_band)
    area_km2 = estimate_area_km2(water_mask, latitude=27.8975, scale_m=10)

    print("compute_ndwi:")
    print(f"  shape={ndwi.shape}, min={ndwi.min():.4f}, max={ndwi.max():.4f}")
    print(f"  water_fraction={(ndwi > 0).mean():.4f}")

    print("compute_turbidity:")
    print(f"  shape={turbidity.shape}, min={turbidity.min():.4f}, max={turbidity.max():.4f}")

    print("extract_water_mask:")
    print(f"  shape={water_mask.shape}, dtype={water_mask.dtype}, sum={water_mask.sum()}")

    print("compute_shape_irregularity:")
    print(f"  circle={compute_shape_irregularity(circle):.4f}")
    print(f"  irregular={compute_shape_irregularity(irregular):.4f}")
    print(f"  empty={compute_shape_irregularity(np.zeros((height, width))):.4f}")

    print("normalize_bands:")
    print(f"  input range=[{multi_band.min():.4f}, {multi_band.max():.4f}]")
    print(f"  output range=[{normalized.min():.4f}, {normalized.max():.4f}]")
    constant = np.ones((4, 4, 2), dtype=np.float32) * 3.0
    print(f"  constant channel mean={normalize_bands(constant)[:, :, 0].mean():.4f}")

    print("estimate_area_km2:")
    print(f"  water_mask area={area_km2:.6f} km²")
