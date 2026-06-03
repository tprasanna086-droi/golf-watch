"""
Sentinel-2 image preprocessing utilities for the GLOF pipeline.

Handles band extraction, spectral index computation, tiling, and
input tensor construction for the 5-channel U-Net.
"""

import numpy as np
import rasterio


def load_sentinel2_bands(tif_path: str) -> dict:
    """
    Opens a Sentinel-2 GeoTIFF using rasterio.
    Returns a dict with keys: 'green', 'nir', 'swir', 'meta'
    Assumes band order: B3 (green)=1, B8 (nir)=2, B11 (swir)=3
    Normalizes each band to float32 in range [0, 1] by dividing by 10000.0
    (Sentinel-2 L2A surface reflectance scale factor)
    """
    with rasterio.open(tif_path) as src:
        green = src.read(1).astype(np.float32) / 10000.0
        nir = src.read(2).astype(np.float32) / 10000.0
        swir = src.read(3).astype(np.float32) / 10000.0
        meta = src.meta.copy()
        meta["transform"] = src.transform

    # Clamp to [0, 1] in case of outliers
    green = np.clip(green, 0.0, 1.0)
    nir = np.clip(nir, 0.0, 1.0)
    swir = np.clip(swir, 0.0, 1.0)

    return {"green": green, "nir": nir, "swir": swir, "meta": meta}


def compute_ndwi(green: np.ndarray, nir: np.ndarray) -> np.ndarray:
    """
    NDWI = (green - nir) / (green + nir + 1e-8)
    Returns float32 array, same shape as input bands.
    """
    ndwi = (green - nir) / (green + nir + 1e-8)
    return ndwi.astype(np.float32)


def compute_turbidity(nir: np.ndarray, swir: np.ndarray) -> np.ndarray:
    """
    Turbidity proxy = swir / (nir + 1e-8)
    Returns float32 array.
    """
    turb = swir / (nir + 1e-8)
    return turb.astype(np.float32)


def tile_image(image: np.ndarray, tile_size: int = 256, overlap: int = 32) -> list:
    """
    Splits a (C, H, W) image array into overlapping tiles of shape
    (C, tile_size, tile_size).
    Returns list of (tile_array, row_offset, col_offset) tuples.
    Pads image with zeros if dimensions are not divisible.
    """
    c, h, w = image.shape
    step = tile_size - overlap

    # Pad image so dimensions are divisible by step
    pad_h = (step - (h % step)) % step + overlap
    pad_w = (step - (w % step)) % step + overlap
    padded = np.pad(
        image,
        ((0, 0), (0, pad_h), (0, pad_w)),
        mode="constant",
        constant_values=0,
    )

    _, ph, pw = padded.shape
    tiles = []

    for row in range(0, ph - tile_size + 1, step):
        for col in range(0, pw - tile_size + 1, step):
            tile = padded[:, row : row + tile_size, col : col + tile_size]
            tiles.append((tile, row, col))

    return tiles


def build_input_tensor(bands: dict) -> np.ndarray:
    """
    Stacks green, nir, swir, ndwi, turbidity into a (5, H, W) float32 array.
    This is the 5-channel input to U-Net.
    """
    green = bands["green"]
    nir = bands["nir"]
    swir = bands["swir"]

    ndwi = compute_ndwi(green, nir)
    turbidity = compute_turbidity(nir, swir)

    tensor = np.stack([green, nir, swir, ndwi, turbidity], axis=0)
    return tensor.astype(np.float32)
