"""
Stability AI API client with support for multiple endpoints.
"""

import os
import logging
from typing import Dict, Optional, Tuple
from pathlib import Path
from dataclasses import dataclass

import httpx
from PIL import Image as PILImage

from .models import StabilityModel, MODEL_INFO, get_model_by_name
from .utils import StorageError


logger = logging.getLogger(__name__)


class StabilityAPIError(Exception):
    """Custom exception for Stability AI API errors."""
    
    def __init__(self, message: str, status_code: Optional[int] = None, error_type: str = "api_error"):
        self.message = message
        self.status_code = status_code
        self.error_type = error_type
        super().__init__(self.message)


@dataclass
class GenerationResult:
    """Result of image generation."""
    image_data: bytes
    seed: int
    finish_reason: str
    model: str
    file_path: Optional[str] = None
    metadata_path: Optional[str] = None


class StabilityClient:
    """Client for Stability AI API with multi-endpoint support."""
    
    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize Stability AI client.
        
        Args:
            api_key: API key. If None, will try to get from STABILITY_API_KEY env var
        """
        self.api_key = api_key or os.getenv("STABILITY_API_KEY")
        if not self.api_key:
            raise StabilityAPIError(
                "Stability API key not found. Please set STABILITY_API_KEY environment variable.",
                error_type="authentication_error"
            )
        
        self.base_url = "https://api.stability.ai"
        self.headers = {
            "Accept": "image/*",
            "Authorization": f"Bearer {self.api_key}"
        }
        
        # Create async HTTP client with timeout
        self.client = httpx.AsyncClient(
            timeout=httpx.Timeout(300.0),  # 5 minutes timeout
            headers=self.headers
        )
    
    async def __aenter__(self):
        """Async context manager entry."""
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.client.aclose()
    
    async def _prepare_files_and_data(
        self, 
        params: Dict,
        image_path: Optional[str] = None
    ) -> Tuple[Dict, Dict]:
        """
        Prepare files and data for API request.
        
        Args:
            params: Request parameters
            image_path: Optional path to image file for image-to-image
            
        Returns:
            Tuple[Dict, Dict]: (files, data)
        """
        files = {}
        data = params.copy()
        
        # Handle image file for image-to-image
        if image_path:
            image_file_path = Path(image_path)
            if not image_file_path.exists():
                raise StabilityAPIError(
                    f"Image file not found: {image_path}",
                    error_type="file_error"
                )
            
            # Validate it's an image
            try:
                with PILImage.open(image_file_path) as img:
                    img.verify()
            except Exception as e:
                raise StabilityAPIError(
                    f"Invalid image file: {image_path}. Error: {e}",
                    error_type="file_error"
                )
            
            # Add image to files
            files["image"] = open(image_file_path, "rb")
            
            # Remove image_path from data as it's now in files
            data.pop("image_path", None)
        
        # Add empty file if no files (API requirement)
        if not files:
            files["none"] = ""
        
        return files, data
    
    async def _make_request(
        self, 
        endpoint: str, 
        params: Dict,
        image_path: Optional[str] = None
    ) -> GenerationResult:
        """
        Make request to Stability API.
        
        Args:
            endpoint: API endpoint
            params: Request parameters  
            image_path: Optional image file path
            
        Returns:
            GenerationResult: Generation result
        """
        url = f"{self.base_url}{endpoint}"
        
        try:
            # Prepare files and data
            files, data = await self._prepare_files_and_data(params, image_path)
            
            logger.info(f"Making request to {url}")
            logger.info(f"Parameters: {data}")
            
            # Make request
            response = await self.client.post(
                url,
                files=files,
                data=data
            )
            
            # Close file handles
            for file_obj in files.values():
                if hasattr(file_obj, 'close'):
                    file_obj.close()
            
            # Handle response
            if not response.is_success:
                error_message = f"HTTP {response.status_code}: {response.text}"
                
                # Add contextual error messages
                if response.status_code == 401:
                    error_message = "Invalid API key. Please check your STABILITY_API_KEY."
                elif response.status_code == 402:
                    error_message = "Insufficient credits. Please check your Stability AI account balance."
                elif response.status_code == 400:
                    error_message = f"Bad request: {response.text}. Please check your parameters."
                elif response.status_code == 429:
                    error_message = "Rate limit exceeded. Please wait and try again."
                
                raise StabilityAPIError(
                    error_message,
                    status_code=response.status_code
                )
            
            # Get response data
            image_data = response.content
            finish_reason = response.headers.get("finish-reason", "SUCCESS")
            seed = int(response.headers.get("seed", 0))
            
            # Check for content filtering
            if finish_reason == "CONTENT_FILTERED":
                raise StabilityAPIError(
                    "Generated content was filtered due to NSFW detection. "
                    "Try a different prompt or add negative prompts to avoid restricted content.",
                    error_type="content_filtered"
                )
            
            return GenerationResult(
                image_data=image_data,
                seed=seed,
                finish_reason=finish_reason,
                model=params.get("model", "unknown")
            )
            
        except httpx.RequestError as e:
            raise StabilityAPIError(
                f"Network error: {e}. Please check your internet connection.",
                error_type="network_error"
            )
        except Exception as e:
            if isinstance(e, StabilityAPIError):
                raise
            raise StabilityAPIError(f"Unexpected error: {e}")
    
    async def generate_text_to_image(
        self,
        prompt: str,
        model: str = "stable-image-core",
        aspect_ratio: str = "1:1",
        seed: int = 0,
        output_format: str = "png",
        negative_prompt: str = ""
    ) -> GenerationResult:
        """
        Generate image from text prompt.
        
        Args:
            prompt: Text description of desired image
            model: Model to use for generation
            aspect_ratio: Image aspect ratio
            seed: Random seed for generation
            output_format: Output image format
            negative_prompt: What to avoid in the image
            
        Returns:
            GenerationResult: Generated image result
        """
        model_enum = get_model_by_name(model)
        if not model_enum:
            raise StabilityAPIError(f"Invalid model: {model}")
        
        model_info = MODEL_INFO[model_enum]
        endpoint = model_info.endpoint
        
        # Build parameters based on model type
        params = {
            "prompt": prompt,
            "aspect_ratio": aspect_ratio,
            "seed": seed,
            "output_format": output_format
        }
        
        # Add model for SD3 endpoint
        if endpoint == "/v2beta/stable-image/generate/sd3":
            params["model"] = model
            params["mode"] = "text-to-image"
        
        # Add negative prompt if supported and provided
        if negative_prompt and model_info.supports_negative_prompt:
            params["negative_prompt"] = negative_prompt
        
        return await self._make_request(endpoint, params)
    
    async def generate_image_to_image(
        self,
        image_path: str,
        prompt: str,
        model: str = "stable-image-core",
        strength: float = 0.7,
        seed: int = 0,
        output_format: str = "png",
        negative_prompt: str = ""
    ) -> GenerationResult:
        """
        Transform existing image using text prompt.
        
        Args:
            image_path: Path to input image
            prompt: Text description of desired transformation
            model: Model to use for generation
            strength: How much to transform the image (0.0-1.0)
            seed: Random seed for generation
            output_format: Output image format
            negative_prompt: What to avoid in the transformation
            
        Returns:
            GenerationResult: Generated image result
        """
        model_enum = get_model_by_name(model)
        if not model_enum:
            raise StabilityAPIError(f"Invalid model: {model}")
        
        model_info = MODEL_INFO[model_enum]
        if not model_info.supports_image_to_image:
            raise StabilityAPIError(f"Model {model} does not support image-to-image generation")
        
        endpoint = model_info.endpoint
        
        # Build parameters
        params = {
            "prompt": prompt,
            "seed": seed,
            "output_format": output_format
        }
        
        # Add strength if supported
        if model_info.supports_strength:
            params["strength"] = strength
        
        # Add model for SD3 endpoint
        if endpoint == "/v2beta/stable-image/generate/sd3":
            params["model"] = model
            params["mode"] = "image-to-image"
        
        # Add negative prompt if supported and provided
        if negative_prompt and model_info.supports_negative_prompt:
            params["negative_prompt"] = negative_prompt
        
        return await self._make_request(endpoint, params, image_path)


# Convenience function for single requests
async def generate_image(
    prompt: str,
    model: str = "stable-image-core",
    aspect_ratio: str = "1:1",
    seed: int = 0,
    output_format: str = "png",
    negative_prompt: str = "",
    image_path: Optional[str] = None,
    strength: float = 0.7
) -> GenerationResult:
    """
    Generate image using Stability AI API.
    
    Args:
        prompt: Text description
        model: Model to use
        aspect_ratio: Image aspect ratio
        seed: Random seed
        output_format: Output format
        negative_prompt: What to avoid
        image_path: Input image for image-to-image (optional)
        strength: Transformation strength for image-to-image
        
    Returns:
        GenerationResult: Generated image result
    """
    async with StabilityClient() as client:
        if image_path:
            return await client.generate_image_to_image(
                image_path=image_path,
                prompt=prompt,
                model=model,
                strength=strength,
                seed=seed,
                output_format=output_format,
                negative_prompt=negative_prompt
            )
        else:
            return await client.generate_text_to_image(
                prompt=prompt,
                model=model,
                aspect_ratio=aspect_ratio,
                seed=seed,
                output_format=output_format,
                negative_prompt=negative_prompt
            )