"""
U-Net segmentation model for glacial lake boundary detection from Sentinel-2 imagery.
"""

from __future__ import annotations

import logging
from typing import Tuple

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F

logger = logging.getLogger(__name__)

PADDING_MULTIPLE = 16


class DoubleConv(nn.Module):
    """Two consecutive Conv2d → BatchNorm → ReLU blocks."""

    def __init__(self, in_channels: int, out_channels: int) -> None:
        super().__init__()
        self.block = nn.Sequential(
            nn.Conv2d(in_channels, out_channels, kernel_size=3, padding=1, bias=False),
            nn.BatchNorm2d(out_channels),
            nn.ReLU(inplace=True),
            nn.Conv2d(out_channels, out_channels, kernel_size=3, padding=1, bias=False),
            nn.BatchNorm2d(out_channels),
            nn.ReLU(inplace=True),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """Apply the double convolution block."""
        return self.block(x)


class Down(nn.Module):
    """Encoder block: DoubleConv followed by MaxPool2d."""

    def __init__(self, in_channels: int, out_channels: int) -> None:
        super().__init__()
        self.conv = DoubleConv(in_channels, out_channels)
        self.pool = nn.MaxPool2d(kernel_size=2)

    def forward(self, x: torch.Tensor) -> Tuple[torch.Tensor, torch.Tensor]:
        """Return pooled features and the pre-pool tensor for skip connection."""
        skip = self.conv(x)
        return self.pool(skip), skip


class Up(nn.Module):
    """Decoder block: ConvTranspose2d upsample, concat skip, then DoubleConv."""

    def __init__(self, in_channels: int, out_channels: int) -> None:
        super().__init__()
        self.up = nn.ConvTranspose2d(
            in_channels,
            out_channels,
            kernel_size=2,
            stride=2,
        )
        self.conv = DoubleConv(out_channels * 2, out_channels)

    def forward(self, x: torch.Tensor, skip: torch.Tensor) -> torch.Tensor:
        """Upsample, align spatial size with skip, concatenate, and refine."""
        x = self.up(x)
        x = _crop_or_pad_to_match(x, skip)
        x = torch.cat([skip, x], dim=1)
        return self.conv(x)


def _crop_or_pad_to_match(x: torch.Tensor, target: torch.Tensor) -> torch.Tensor:
    """Align x spatial dimensions to match target for skip concatenation."""
    diff_y = target.size(2) - x.size(2)
    diff_x = target.size(3) - x.size(3)

    if diff_y == 0 and diff_x == 0:
        return x

    pad_left = diff_x // 2
    pad_right = diff_x - pad_left
    pad_top = diff_y // 2
    pad_bottom = diff_y - pad_top

    if diff_x >= 0 and diff_y >= 0:
        return F.pad(x, [pad_left, pad_right, pad_top, pad_bottom])

    # Crop when upsampled tensor is larger than skip
    y_start = max(-pad_top, 0)
    x_start = max(-pad_left, 0)
    return x[
        :,
        :,
        y_start : y_start + target.size(2),
        x_start : x_start + target.size(3),
    ]


class UNet(nn.Module):
    """
    U-Net for binary glacial lake segmentation.

    Encoder channels: in_channels → 64 → 128 → 256 → 512, bottleneck 1024.
    Decoder mirrors encoder with skip connections.
    """

    def __init__(self, in_channels: int = 4, num_classes: int = 1) -> None:
        super().__init__()
        self.down1 = Down(in_channels, 64)
        self.down2 = Down(64, 128)
        self.down3 = Down(128, 256)
        self.down4 = Down(256, 512)
        self.bottleneck = DoubleConv(512, 1024)
        self.up1 = Up(1024, 512)
        self.up2 = Up(512, 256)
        self.up3 = Up(256, 128)
        self.up4 = Up(128, 64)
        self.out_conv = nn.Conv2d(64, num_classes, kernel_size=1)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """Return raw logits of shape (N, num_classes, H, W)."""
        x, skip1 = self.down1(x)
        x, skip2 = self.down2(x)
        x, skip3 = self.down3(x)
        x, skip4 = self.down4(x)
        x = self.bottleneck(x)
        x = self.up1(x, skip4)
        x = self.up2(x, skip3)
        x = self.up3(x, skip2)
        x = self.up4(x, skip1)
        return self.out_conv(x)

    def count_parameters(self) -> int:
        """Return the number of trainable parameters."""
        return sum(param.numel() for param in self.parameters() if param.requires_grad)


def load_unet(checkpoint_path: str, device: str = "cpu") -> UNet:
    """
    Load a trained U-Net checkpoint and return the model in eval mode.
    """
    model = UNet(in_channels=4, num_classes=1)
    try:
        state_dict = torch.load(checkpoint_path, map_location=device, weights_only=True)
    except TypeError:
        # Older PyTorch versions do not support weights_only
        state_dict = torch.load(checkpoint_path, map_location=device)

    if isinstance(state_dict, dict) and "state_dict" in state_dict:
        state_dict = state_dict["state_dict"]

    model.load_state_dict(state_dict)
    model.to(device)
    model.eval()
    param_count = model.count_parameters()
    logger.info(
        "Loaded U-Net from %s on %s (%d trainable parameters)",
        checkpoint_path,
        device,
        param_count,
    )
    return model


def _pad_hwc_to_multiple(
    array: np.ndarray,
    multiple: int = PADDING_MULTIPLE,
) -> Tuple[np.ndarray, int, int]:
    """Pad (H, W, C) array so height and width are multiples of `multiple`."""
    height, width = array.shape[:2]
    pad_h = (multiple - (height % multiple)) % multiple
    pad_w = (multiple - (width % multiple)) % multiple
    if pad_h == 0 and pad_w == 0:
        return array, height, width
    padded = np.pad(
        array,
        ((0, pad_h), (0, pad_w), (0, 0)),
        mode="constant",
        constant_values=0.0,
    )
    return padded, height, width


def predict_mask(
    model: UNet,
    array: np.ndarray,
    device: str = "cpu",
    threshold: float = 0.5,
) -> np.ndarray:
    """
    Run inference on a normalized (H, W, C) array and return a binary mask.

    Pads inputs to a multiple of 16 before inference and crops the output
    back to the original spatial size.
    """
    if array.ndim != 3:
        raise ValueError(f"Expected input shape (H, W, C), got {array.shape}")

    model.eval()
    model.to(device)

    padded, orig_h, orig_w = _pad_hwc_to_multiple(array.astype(np.float32, copy=False))
    tensor = (
        torch.from_numpy(padded)
        .permute(2, 0, 1)
        .unsqueeze(0)
        .to(device)
    )

    with torch.no_grad():
        logits = model(tensor)
        probabilities = torch.sigmoid(logits)

    mask = (probabilities.squeeze().cpu().numpy() >= threshold).astype(np.uint8)
    return mask[:orig_h, :orig_w]


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    model = UNet(in_channels=4, num_classes=1)
    print(f"Trainable parameters: {model.count_parameters():,}")

    sample = torch.randn(1, 4, 256, 256)
    output = model(sample)
    assert output.shape == (1, 1, 256, 256), f"Unexpected shape: {output.shape}"
    print("U-Net self-test passed")
