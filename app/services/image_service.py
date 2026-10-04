import os
from pathlib import Path
from typing import Optional, Tuple
from werkzeug.datastructures import FileStorage
from PIL import Image, ImageOps
from flask import current_app
from app.utils.uuid7 import generate_uuid7

# Decompression bomb defense: max 25 megapixels
Image.MAX_IMAGE_PIXELS = 25_000_000

ALLOWED_FORMATS = {"JPEG", "PNG", "WEBP"}

class ImageService:
    @classmethod
    def get_upload_dir(cls) -> Path:
        upload_folder = Path(current_app.config.get("UPLOAD_FOLDER"))
        upload_folder.mkdir(parents=True, exist_ok=True)
        return upload_folder

    @classmethod
    def process_and_save(cls, file: FileStorage) -> Tuple[Optional[str], Optional[str]]:
        """
        Validate, strip metadata, resize, and convert uploaded image to static WebP.
        Returns (relative_url, error_message).
        """
        if not file or not file.filename:
            return None, None

        # Basic filename inspection (defense in depth, though we rely on Pillow decode)
        filename = file.filename.lower()
        if not any(filename.endswith(f".{ext}") for ext in current_app.config["ALLOWED_IMAGE_EXTENSIONS"]):
            return None, "Only JPEG, PNG, and WebP images are supported."

        try:
            # Read file stream with Pillow
            img = Image.open(file.stream)
            img_format = (img.format or "").upper()

            if img_format not in ALLOWED_FORMATS:
                return None, f"Unsupported image format: {img_format}. Allowed: JPEG, PNG, WebP."

            # Reject animated images (e.g. animated WebP/GIF)
            if getattr(img, "is_animated", False) and getattr(img, "n_frames", 1) > 1:
                return None, "Animated images are not allowed. Please provide a static image."

            # Handle EXIF orientation before stripping EXIF metadata
            try:
                img = ImageOps.exif_transpose(img)
            except Exception:
                pass  # If orientation cannot be parsed, continue

            # Resize if dimensions exceed max allowed (preserving aspect ratio, no upscaling)
            max_dim = current_app.config.get("IMAGE_MAX_DIMENSION", 1600)
            orig_w, orig_h = img.size
            if orig_w > max_dim or orig_h > max_dim:
                img.thumbnail((max_dim, max_dim), Image.Resampling.LANCZOS)

            # Strip all metadata by constructing a new image with raw pixels
            # Convert palette/grayscale/CMYK images appropriately
            if img.mode in ("RGBA", "LA") or (img.mode == "P" and "transparency" in img.info):
                clean_img = Image.new("RGBA", img.size)
                clean_img.paste(img, (0, 0))
            else:
                clean_img = Image.new("RGB", img.size)
                clean_img.paste(img.convert("RGB"), (0, 0))

            # Generate unique filename using UUIDv7
            unique_name = f"{generate_uuid7()}.webp"
            destination = cls.get_upload_dir() / unique_name

            # Encode as WebP with stripped metadata
            clean_img.save(
                destination,
                format="WEBP",
                quality=current_app.config.get("IMAGE_QUALITY", 82),
                method=4
            )

            relative_url = f"/uploads/{unique_name}"
            return relative_url, None

        except Image.DecompressionBombError:
            return None, "Image exceeds maximum allowed dimensions."
        except Exception as e:
            return None, f"Image processing failed: Invalid or corrupt image file."

    @classmethod
    def delete_image_file(cls, image_path: Optional[str]) -> bool:
        """
        Permanently remove the image file from disk when a dispatch is Struck.
        """
        if not image_path:
            return True

        try:
            filename = Path(image_path).name
            target = cls.get_upload_dir() / filename
            if target.exists() and target.is_file():
                target.unlink()
                return True
        except Exception as e:
            current_app.logger.warning(f"Failed to delete image {image_path}: {e}")
        return False
