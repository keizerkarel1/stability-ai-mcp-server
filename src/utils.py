"""
Utility functions for image handling and file storage.
"""

import base64
import json
import os
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional, Tuple
from PIL import Image as PILImage
import io


# Configure logging to stderr only (MCP requirement)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)


class StorageError(Exception):
    """Custom exception for storage-related errors."""
    pass


def get_storage_path() -> Path:
    """
    Get the configured image storage path from environment variable.
    
    Returns:
        Path: The storage directory path
        
    Raises:
        StorageError: If path is invalid or cannot be created
    """
    # Get path from environment variable
    storage_path_env = os.getenv("IMAGE_STORAGE_PATH")
    
    if storage_path_env:
        # Expand user path (~) and environment variables
        storage_path = Path(storage_path_env).expanduser().resolve()
        logger.info(f"Using configured storage path: {storage_path}")
    else:
        # Default to ./images relative to the current working directory
        storage_path = Path.cwd() / "images"
        logger.info(f"Using default storage path: {storage_path}")
    
    # Validate and create directory
    try:
        # Create directory if it doesn't exist
        storage_path.mkdir(parents=True, exist_ok=True)
        
        # Test write permissions
        test_file = storage_path / ".write_test"
        try:
            test_file.touch()
            test_file.unlink()  # Remove test file
        except PermissionError:
            raise StorageError(
                f"No write permission for storage directory: {storage_path}. "
                f"Please check directory permissions or choose a different path."
            )
    
    except OSError as e:
        raise StorageError(
            f"Cannot create or access storage directory: {storage_path}. "
            f"Error: {e}. Please check the IMAGE_STORAGE_PATH configuration."
        )
    
    return storage_path


def generate_filename(seed: int, output_format: str, prefix: str = "stability") -> str:
    """
    Generate a unique filename for the image.
    
    Args:
        seed: The seed used for generation
        output_format: File format (png, jpeg)
        prefix: Filename prefix
        
    Returns:
        str: Generated filename
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"{prefix}_{timestamp}_{seed}.{output_format}"


def save_image_with_metadata(
    image_data: bytes, 
    metadata: Dict, 
    filename: Optional[str] = None
) -> Tuple[str, str]:
    """
    Save image and its metadata to the configured storage directory.
    
    Args:
        image_data: Raw image bytes
        metadata: Generation metadata (seed, model, prompt, etc.)
        filename: Optional custom filename
        
    Returns:
        Tuple[str, str]: (image_file_path, metadata_file_path)
        
    Raises:
        StorageError: If saving fails
    """
    try:
        storage_path = get_storage_path()
        
        # Generate filename if not provided
        if not filename:
            seed = metadata.get('seed', 0)
            output_format = metadata.get('output_format', 'png')
            filename = generate_filename(seed, output_format)
        
        # Save image
        image_path = storage_path / filename
        with open(image_path, 'wb') as f:
            f.write(image_data)
        
        # Save metadata
        metadata_filename = f"{image_path.stem}_metadata.json"
        metadata_path = storage_path / metadata_filename
        
        # Add file info to metadata
        enhanced_metadata = {
            **metadata,
            "file_path": str(image_path),
            "file_size": len(image_data),
            "generated_at": datetime.now().isoformat(),
            "storage_directory": str(storage_path)
        }
        
        with open(metadata_path, 'w', encoding='utf-8') as f:
            json.dump(enhanced_metadata, f, indent=2, ensure_ascii=False)
        
        logger.info(f"Saved image: {image_path}")
        logger.info(f"Saved metadata: {metadata_path}")
        
        return str(image_path), str(metadata_path)
    
    except Exception as e:
        raise StorageError(f"Failed to save image and metadata: {e}")


def encode_image_to_base64(image_path: str) -> str:
    """
    Encode image file to base64 string.
    
    Args:
        image_path: Path to the image file
        
    Returns:
        str: Base64 encoded image
        
    Raises:
        StorageError: If encoding fails
    """
    try:
        with open(image_path, 'rb') as f:
            image_data = f.read()
        return base64.b64encode(image_data).decode('utf-8')
    except Exception as e:
        raise StorageError(f"Failed to encode image to base64: {e}")


def decode_base64_to_image(base64_data: str, output_path: str) -> None:
    """
    Decode base64 string to image file.
    
    Args:
        base64_data: Base64 encoded image data
        output_path: Output file path
        
    Raises:
        StorageError: If decoding fails
    """
    try:
        image_data = base64.b64decode(base64_data)
        with open(output_path, 'wb') as f:
            f.write(image_data)
    except Exception as e:
        raise StorageError(f"Failed to decode base64 to image: {e}")


def validate_image_file(image_path: str) -> bool:
    """
    Validate that the file is a valid image.
    
    Args:
        image_path: Path to the image file
        
    Returns:
        bool: True if valid image, False otherwise
    """
    try:
        path = Path(image_path)
        if not path.exists():
            return False
        
        # Try to open with PIL to validate
        with PILImage.open(path) as img:
            img.verify()
        return True
    except Exception:
        return False


def get_image_info(image_path: str) -> Optional[Dict]:
    """
    Get basic information about an image file.
    
    Args:
        image_path: Path to the image file
        
    Returns:
        Dict: Image information or None if invalid
    """
    try:
        if not validate_image_file(image_path):
            return None
        
        with PILImage.open(image_path) as img:
            return {
                "format": img.format,
                "mode": img.mode,
                "size": img.size,
                "width": img.width,
                "height": img.height
            }
    except Exception:
        return None


def cleanup_storage_directory(max_files: int = 1000) -> int:
    """
    Clean up old files in storage directory if it gets too large.
    
    Args:
        max_files: Maximum number of files to keep
        
    Returns:
        int: Number of files removed
    """
    try:
        storage_path = get_storage_path()
        
        # Get all image files sorted by modification time (oldest first)
        image_files = []
        for file_path in storage_path.iterdir():
            if file_path.is_file() and file_path.suffix.lower() in ['.png', '.jpg', '.jpeg']:
                image_files.append(file_path)
        
        image_files.sort(key=lambda f: f.stat().st_mtime)
        
        # Remove oldest files if over limit
        files_to_remove = len(image_files) - max_files
        if files_to_remove > 0:
            removed_count = 0
            for file_path in image_files[:files_to_remove]:
                try:
                    # Remove image file
                    file_path.unlink()
                    
                    # Remove associated metadata file if exists
                    metadata_path = storage_path / f"{file_path.stem}_metadata.json"
                    if metadata_path.exists():
                        metadata_path.unlink()
                    
                    removed_count += 1
                    logger.info(f"Removed old file: {file_path}")
                    
                except Exception as e:
                    logger.error(f"Failed to remove file {file_path}: {e}")
            
            return removed_count
        
        return 0
        
    except Exception as e:
        logger.error(f"Failed to cleanup storage directory: {e}")
        return 0


def get_storage_stats() -> Dict:
    """
    Get statistics about the storage directory.
    
    Returns:
        Dict: Storage statistics
    """
    try:
        storage_path = get_storage_path()
        
        total_files = 0
        total_size = 0
        image_files = 0
        metadata_files = 0
        
        for file_path in storage_path.iterdir():
            if file_path.is_file():
                total_files += 1
                total_size += file_path.stat().st_size
                
                if file_path.suffix.lower() in ['.png', '.jpg', '.jpeg']:
                    image_files += 1
                elif file_path.suffix.lower() == '.json':
                    metadata_files += 1
        
        return {
            "storage_path": str(storage_path),
            "total_files": total_files,
            "image_files": image_files,
            "metadata_files": metadata_files,
            "total_size_bytes": total_size,
            "total_size_mb": round(total_size / 1024 / 1024, 2)
        }
        
    except Exception as e:
        logger.error(f"Failed to get storage stats: {e}")
        return {"error": str(e)}