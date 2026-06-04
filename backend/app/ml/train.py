"""
Fine-tune the GLOF Watch U-Net on labeled Sentinel-2 glacial lake patches.
"""

from __future__ import annotations

import argparse
import logging
import random
from pathlib import Path
from typing import Optional, TypedDict

import numpy as np
import torch
import torch.nn as nn
from torch.utils.data import DataLoader, Dataset

from app.ml.unet import UNet
from app.pipeline.band_math import normalize_bands

logger = logging.getLogger(__name__)

SMOOTH = 1e-6


class TrainResult(TypedDict):
    """Summary returned by train_unet."""

    best_val_iou: float
    final_epoch: int
    checkpoint_path: str


def _discover_image_mask_pairs(image_dir: str, mask_dir: str) -> list[tuple[Path, Path]]:
    """Pair .npy image files with matching mask files by stem name."""
    image_root = Path(image_dir)
    mask_root = Path(mask_dir)
    pairs: list[tuple[Path, Path]] = []

    for image_path in sorted(image_root.glob("*.npy")):
        mask_path = mask_root / f"{image_path.stem}.npy"
        if mask_path.is_file():
            pairs.append((image_path, mask_path))

    return pairs


def _apply_augmentation(image: np.ndarray, mask: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Apply random flips and 90° rotations to image and mask."""
    if random.random() < 0.5:
        image = np.flip(image, axis=1).copy()
        mask = np.flip(mask, axis=1).copy()
    if random.random() < 0.5:
        image = np.flip(image, axis=0).copy()
        mask = np.flip(mask, axis=0).copy()
    if random.random() < 0.5:
        rotations = random.randint(1, 3)
        image = np.rot90(image, rotations, axes=(0, 1)).copy()
        mask = np.rot90(mask, rotations, axes=(0, 1)).copy()
    return image, mask


class LakeDataset(Dataset[tuple[torch.Tensor, torch.Tensor]]):
    """PyTorch dataset of Sentinel-2 image patches and lake masks."""

    def __init__(
        self,
        image_dir: str,
        mask_dir: str,
        augment: bool = False,
        pairs: Optional[list[tuple[Path, Path]]] = None,
    ) -> None:
        """
        Load paired image and mask .npy files from disk.

        Images must have shape (H, W, 4) float32; masks (H, W) uint8.
        """
        self.augment = augment
        self.pairs = pairs if pairs is not None else _discover_image_mask_pairs(
            image_dir, mask_dir
        )
        if not self.pairs:
            raise ValueError(
                f"No matching image/mask pairs found in {image_dir} and {mask_dir}"
            )

    def __len__(self) -> int:
        """Return the number of image/mask pairs."""
        return len(self.pairs)

    def __getitem__(self, index: int) -> tuple[torch.Tensor, torch.Tensor]:
        """Return normalized image (4, H, W) and mask (1, H, W) tensors."""
        image_path, mask_path = self.pairs[index]
        image = np.load(image_path).astype(np.float32)
        mask = np.load(mask_path)

        if image.ndim != 3 or image.shape[2] != 4:
            raise ValueError(
                f"Expected image shape (H, W, 4) in {image_path}, got {image.shape}"
            )
        if mask.ndim != 2:
            raise ValueError(f"Expected mask shape (H, W) in {mask_path}, got {mask.shape}")

        if self.augment:
            image, mask = _apply_augmentation(image, mask)

        image = normalize_bands(image)
        image_tensor = torch.from_numpy(image).permute(2, 0, 1).contiguous()
        mask_tensor = torch.from_numpy((mask > 0).astype(np.float32)).unsqueeze(0)
        return image_tensor, mask_tensor


class DiceLoss(nn.Module):
    """Dice loss for binary segmentation (applies sigmoid to logits)."""

    def __init__(self, smooth: float = SMOOTH) -> None:
        super().__init__()
        self.smooth = smooth

    def forward(self, logits: torch.Tensor, targets: torch.Tensor) -> torch.Tensor:
        """Compute 1 - Dice coefficient between predictions and targets."""
        probabilities = torch.sigmoid(logits)
        probabilities = probabilities.reshape(-1)
        targets = targets.reshape(-1)
        intersection = (probabilities * targets).sum()
        denominator = probabilities.sum() + targets.sum()
        dice = (2.0 * intersection + self.smooth) / (denominator + self.smooth)
        return 1.0 - dice


class CombinedLoss(nn.Module):
    """Weighted sum of BCEWithLogitsLoss and DiceLoss (0.5 each)."""

    def __init__(self) -> None:
        super().__init__()
        self.bce = nn.BCEWithLogitsLoss()
        self.dice = DiceLoss()

    def forward(self, logits: torch.Tensor, targets: torch.Tensor) -> torch.Tensor:
        """Return combined training loss."""
        return 0.5 * self.bce(logits, targets) + 0.5 * self.dice(logits, targets)


def _split_pairs(
    pairs: list[tuple[Path, Path]],
    val_split: float,
) -> tuple[list[tuple[Path, Path]], list[tuple[Path, Path]]]:
    """Split file pairs into train and validation subsets."""
    shuffled = pairs.copy()
    random.shuffle(shuffled)
    val_count = max(1, int(len(shuffled) * val_split)) if len(shuffled) > 1 else 0
    if val_count == 0:
        return shuffled, []
    val_pairs = shuffled[:val_count]
    train_pairs = shuffled[val_count:]
    if not train_pairs:
        train_pairs, val_pairs = val_pairs, train_pairs
    return train_pairs, val_pairs


def _compute_batch_metrics(
    logits: torch.Tensor,
    targets: torch.Tensor,
    threshold: float = 0.5,
) -> tuple[float, float]:
    """Compute mean pixel accuracy and IoU for a batch."""
    predictions = (torch.sigmoid(logits) >= threshold).float()
    targets_bin = (targets >= 0.5).float()

    accuracy = (predictions == targets_bin).float().mean().item()
    intersection = (predictions * targets_bin).sum().item()
    union = predictions.sum().item() + targets_bin.sum().item() - intersection
    iou = intersection / (union + SMOOTH) if union > 0 else 1.0
    return accuracy, iou


def _run_epoch(
    model: UNet,
    loader: DataLoader[tuple[torch.Tensor, torch.Tensor]],
    criterion: nn.Module,
    device: torch.device,
    optimizer: Optional[torch.optim.Optimizer] = None,
) -> tuple[float, float, float]:
    """Run one train or validation epoch and return loss, accuracy, IoU."""
    is_train = optimizer is not None
    model.train(is_train)

    total_loss = 0.0
    total_accuracy = 0.0
    total_iou = 0.0
    batch_count = 0

    for images, masks in loader:
        images = images.to(device)
        masks = masks.to(device)

        if is_train:
            assert optimizer is not None
            optimizer.zero_grad()

        logits = model(images)
        loss = criterion(logits, masks)

        if is_train:
            loss.backward()
            optimizer.step()

        accuracy, iou = _compute_batch_metrics(logits.detach(), masks)
        total_loss += loss.item()
        total_accuracy += accuracy
        total_iou += iou
        batch_count += 1

    if batch_count == 0:
        return 0.0, 0.0, 0.0

    return (
        total_loss / batch_count,
        total_accuracy / batch_count,
        total_iou / batch_count,
    )


def train_unet(
    image_dir: str,
    mask_dir: str,
    output_dir: str,
    epochs: int = 50,
    batch_size: int = 8,
    lr: float = 1e-4,
    val_split: float = 0.2,
    device: str = "cpu",
) -> TrainResult:
    """
    Fine-tune a U-Net on labeled lake patches and save checkpoints to output_dir.
    """
    try:
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        all_pairs = _discover_image_mask_pairs(image_dir, mask_dir)
        train_pairs, val_pairs = _split_pairs(all_pairs, val_split)

        train_dataset = LakeDataset(
            image_dir,
            mask_dir,
            augment=True,
            pairs=train_pairs,
        )
        val_dataset = LakeDataset(
            image_dir,
            mask_dir,
            augment=False,
            pairs=val_pairs,
        ) if val_pairs else None

        torch_device = torch.device(device)
        pin_memory = torch_device.type == "cuda"

        train_loader = DataLoader(
            train_dataset,
            batch_size=batch_size,
            shuffle=True,
            num_workers=2,
            pin_memory=pin_memory,
        )
        val_loader = (
            DataLoader(
                val_dataset,
                batch_size=batch_size,
                shuffle=False,
                num_workers=2,
                pin_memory=pin_memory,
            )
            if val_dataset is not None
            else None
        )

        model = UNet(in_channels=4, num_classes=1).to(torch_device)
        criterion = CombinedLoss()
        optimizer = torch.optim.AdamW(model.parameters(), lr=lr, weight_decay=1e-5)
        scheduler = torch.optim.lr_scheduler.ReduceLROnPlateau(
            optimizer,
            mode="min",
            patience=5,
            factor=0.5,
        )

        best_val_iou = -1.0
        best_checkpoint = output_path / "best_unet.pth"
        final_checkpoint = output_path / "final_unet.pth"

        logger.info(
            "Training U-Net on %d samples (%d train, %d val) for %d epochs",
            len(all_pairs),
            len(train_pairs),
            len(val_pairs),
            epochs,
        )

        for epoch in range(1, epochs + 1):
            train_loss, train_acc, train_iou = _run_epoch(
                model,
                train_loader,
                criterion,
                torch_device,
                optimizer=optimizer,
            )

            if val_loader is not None:
                val_loss, val_acc, val_iou = _run_epoch(
                    model,
                    val_loader,
                    criterion,
                    torch_device,
                )
            else:
                val_loss, val_acc, val_iou = train_loss, train_acc, train_iou

            scheduler.step(val_loss)

            logger.info(
                "Epoch %d/%d — train_loss=%.4f val_loss=%.4f "
                "train_iou=%.4f val_iou=%.4f val_acc=%.4f",
                epoch,
                epochs,
                train_loss,
                val_loss,
                train_iou,
                val_iou,
                val_acc,
            )

            if val_iou > best_val_iou:
                best_val_iou = val_iou
                torch.save(model.state_dict(), best_checkpoint)
                logger.info(
                    "Saved new best checkpoint (val_iou=%.4f) to %s",
                    val_iou,
                    best_checkpoint,
                )

        torch.save(model.state_dict(), final_checkpoint)
        logger.info("Saved final checkpoint to %s", final_checkpoint)

        return {
            "best_val_iou": float(best_val_iou),
            "final_epoch": epochs,
            "checkpoint_path": str(best_checkpoint if best_checkpoint.is_file() else final_checkpoint),
        }
    except Exception:
        logger.exception("U-Net training failed")
        raise


def _parse_args() -> argparse.Namespace:
    """Parse command-line arguments for training."""
    parser = argparse.ArgumentParser(
        description="Fine-tune the GLOF Watch U-Net on labeled lake patches",
    )
    parser.add_argument("--image-dir", required=True, help="Directory of (H,W,4) .npy images")
    parser.add_argument("--mask-dir", required=True, help="Directory of (H,W) .npy masks")
    parser.add_argument("--output-dir", required=True, help="Directory for saved checkpoints")
    parser.add_argument("--epochs", type=int, default=50)
    parser.add_argument("--batch-size", type=int, default=8)
    parser.add_argument("--lr", type=float, default=1e-4)
    parser.add_argument(
        "--device",
        default="cpu",
        help="Torch device, e.g. cpu or cuda",
    )
    return parser.parse_args()


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )
    args = _parse_args()
    metrics = train_unet(
        image_dir=args.image_dir,
        mask_dir=args.mask_dir,
        output_dir=args.output_dir,
        epochs=args.epochs,
        batch_size=args.batch_size,
        lr=args.lr,
        device=args.device,
    )
    print(
        f"Training complete — best_val_iou={metrics['best_val_iou']:.4f}, "
        f"epochs={metrics['final_epoch']}, checkpoint={metrics['checkpoint_path']}"
    )
