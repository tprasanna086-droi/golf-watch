"""
U-Net model definition and inference utilities.

Uses segmentation-models-pytorch (smp) with a ResNet-34 encoder.
The model takes 5-channel input (green, nir, swir, ndwi, turbidity)
and outputs a single-class water mask.
"""

import numpy as np
import torch
import segmentation_models_pytorch as smp
import rasterio.features
from shapely.geometry import Polygon, shape


def get_unet_model(pretrained: bool = True):
    """
    Returns an smp U-Net with ResNet-34 encoder configured for
    5-channel input and single-class binary segmentation.
    """
    model = smp.Unet(
        encoder_name="resnet34",
        encoder_weights="imagenet" if pretrained else None,
        in_channels=5,
        classes=1,
        activation=None,
    )
    return model


def run_inference(model, tile: np.ndarray, device: str = "cpu") -> np.ndarray:
    """
    Runs a single tile through the model.

    Args:
        model: The U-Net model (in eval mode).
        tile: numpy array of shape (5, H, W), float32.
        device: 'cpu' or 'cuda'.

    Returns:
        A (H, W) numpy float32 probability mask (sigmoid-activated).
    """
    model.eval()
    model.to(device)

    # Convert to tensor: (1, 5, H, W)
    tensor = torch.from_numpy(tile).unsqueeze(0).float().to(device)

    with torch.no_grad():
        logits = model(tensor)  # (1, 1, H, W)

    probs = torch.sigmoid(logits).squeeze().cpu().numpy()  # (H, W)
    return probs.astype(np.float32)


def mask_to_polygon(
    mask: np.ndarray,
    transform,
    threshold: float = 0.5,
) -> list[Polygon]:
    """
    Converts a probability mask to a list of shapely Polygons.

    Args:
        mask: (H, W) float32 probability mask.
        transform: Affine transform from rasterio (maps pixel → CRS coords).
        threshold: Probability cutoff for binarisation.

    Returns:
        List of shapely Polygon objects (filtered: area > 100 pixels).
    """
    binary = (mask >= threshold).astype(np.uint8)

    polygons = []
    pixel_area_threshold = 100  # minimum polygon size in pixels

    for geom, value in rasterio.features.shapes(
        binary, mask=binary == 1, transform=transform
    ):
        if value == 1:
            poly = shape(geom)
            # Filter small polygons (area is in CRS units via transform,
            # but we approximate pixel count from the binary mask)
            if poly.area > 0 and _pixel_count(poly, transform) >= pixel_area_threshold:
                polygons.append(poly)

    return polygons


def _pixel_count(polygon: Polygon, transform) -> float:
    """Estimate pixel count from polygon area and pixel size."""
    pixel_width = abs(transform.a)
    pixel_height = abs(transform.e)
    pixel_area = pixel_width * pixel_height
    if pixel_area == 0:
        return 0
    return polygon.area / pixel_area
