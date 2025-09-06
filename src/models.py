"""
Stability AI model definitions and parameter validation.
"""

from enum import Enum
from typing import Dict, List, Optional, Union
from dataclasses import dataclass


class StabilityModel(Enum):
    """Available Stability AI models."""
    
    # Core/Ultra models (newer, natural language optimized)
    CORE = "stable-image-core"
    ULTRA = "stable-image-ultra"
    
    # SD3.5 family models
    SD3_5_LARGE = "sd3.5-large"
    SD3_5_LARGE_TURBO = "sd3.5-large-turbo"
    SD3_5_MEDIUM = "sd3.5-medium"
    SD3_5_FLASH = "sd3.5-flash"


class AspectRatio(Enum):
    """Supported aspect ratios."""
    SQUARE = "1:1"
    LANDSCAPE_16_9 = "16:9"
    PORTRAIT_9_16 = "9:16"
    LANDSCAPE_21_9 = "21:9"
    PORTRAIT_9_21 = "9:21"
    LANDSCAPE_3_2 = "3:2"
    PORTRAIT_2_3 = "2:3"
    LANDSCAPE_5_4 = "5:4"
    PORTRAIT_4_5 = "4:5"
    LANDSCAPE_4_3 = "4:3"
    PORTRAIT_3_4 = "3:4"


class OutputFormat(Enum):
    """Supported output formats."""
    JPEG = "jpeg"
    PNG = "png"


@dataclass
class ModelInfo:
    """Information about a specific model."""
    name: str
    description: str
    endpoint: str
    supports_negative_prompt: bool
    supports_image_to_image: bool
    supports_strength: bool
    max_seed: int = 4294967294


# Model definitions with their capabilities
MODEL_INFO: Dict[StabilityModel, ModelInfo] = {
    StabilityModel.CORE: ModelInfo(
        name="Stable Image Core",
        description="Fast, affordable, natural language optimized. Best for everyday use.",
        endpoint="/v2beta/stable-image/generate/core",
        supports_negative_prompt=True,
        supports_image_to_image=True,
        supports_strength=True
    ),
    
    StabilityModel.ULTRA: ModelInfo(
        name="Stable Image Ultra", 
        description="Highest quality results. State-of-the-art, SD3.5-based. Use for important or complex images.",
        endpoint="/v2beta/stable-image/generate/ultra",
        supports_negative_prompt=True,
        supports_image_to_image=True,
        supports_strength=True
    ),
    
    StabilityModel.SD3_5_LARGE: ModelInfo(
        name="SD3.5 Large",
        description="8B parameter model. Maximum control and detail. Good for technical or artistic work.",
        endpoint="/v2beta/stable-image/generate/sd3",
        supports_negative_prompt=True,
        supports_image_to_image=True,
        supports_strength=True
    ),
    
    StabilityModel.SD3_5_LARGE_TURBO: ModelInfo(
        name="SD3.5 Large Turbo",
        description="Distilled faster version of SD3.5 Large. Good balance of quality and speed.",
        endpoint="/v2beta/stable-image/generate/sd3",
        supports_negative_prompt=True,
        supports_image_to_image=True,
        supports_strength=True
    ),
    
    StabilityModel.SD3_5_MEDIUM: ModelInfo(
        name="SD3.5 Medium",
        description="2B parameter model. Efficient and fast with good quality.",
        endpoint="/v2beta/stable-image/generate/sd3",
        supports_negative_prompt=True,
        supports_image_to_image=True,
        supports_strength=True
    ),
    
    StabilityModel.SD3_5_FLASH: ModelInfo(
        name="SD3.5 Flash",
        description="Ultra-fast 4-step generation. Fastest generation, good for rapid iteration and previews.",
        endpoint="/v2beta/stable-image/generate/sd3",
        supports_negative_prompt=False,
        supports_image_to_image=True,
        supports_strength=True
    )
}


def get_model_by_name(model_name: str) -> Optional[StabilityModel]:
    """Get model enum by string name."""
    for model in StabilityModel:
        if model.value == model_name:
            return model
    return None


def get_available_models() -> Dict[str, str]:
    """Get dictionary of available models and their descriptions."""
    return {
        model.value: MODEL_INFO[model].description 
        for model in StabilityModel
    }


def validate_aspect_ratio(aspect_ratio: str) -> bool:
    """Validate aspect ratio string."""
    valid_ratios = [ratio.value for ratio in AspectRatio]
    return aspect_ratio in valid_ratios


def validate_output_format(output_format: str) -> bool:
    """Validate output format string."""
    valid_formats = [format.value for format in OutputFormat]
    return output_format in valid_formats


def validate_seed(seed: int) -> bool:
    """Validate seed value."""
    return 0 <= seed <= 4294967294


def validate_strength(strength: float) -> bool:
    """Validate strength value for image-to-image."""
    return 0.0 <= strength <= 1.0


def get_model_validation_errors(
    model_name: str,
    aspect_ratio: str,
    output_format: str,
    seed: int,
    strength: Optional[float] = None,
    negative_prompt: Optional[str] = None,
    image_path: Optional[str] = None
) -> List[str]:
    """Validate all parameters for a model and return list of errors."""
    errors = []
    
    # Validate model
    model = get_model_by_name(model_name)
    if not model:
        available = ", ".join([m.value for m in StabilityModel])
        errors.append(f"Invalid model '{model_name}'. Available models: {available}")
        return errors  # Can't validate further without valid model
    
    model_info = MODEL_INFO[model]
    
    # Validate aspect ratio
    if not validate_aspect_ratio(aspect_ratio):
        valid_ratios = ", ".join([r.value for r in AspectRatio])
        errors.append(f"Invalid aspect ratio '{aspect_ratio}'. Valid ratios: {valid_ratios}")
    
    # Validate output format
    if not validate_output_format(output_format):
        valid_formats = ", ".join([f.value for f in OutputFormat])
        errors.append(f"Invalid output format '{output_format}'. Valid formats: {valid_formats}")
    
    # Validate seed
    if not validate_seed(seed):
        errors.append(f"Invalid seed '{seed}'. Must be between 0 and 4294967294")
    
    # Validate strength for image-to-image
    if image_path and strength is not None:
        if not model_info.supports_strength:
            errors.append(f"Model '{model_name}' does not support strength parameter")
        elif not validate_strength(strength):
            errors.append(f"Invalid strength '{strength}'. Must be between 0.0 and 1.0")
    
    # Validate negative prompt support
    if negative_prompt and not model_info.supports_negative_prompt:
        errors.append(f"Model '{model_name}' does not support negative prompts")
    
    # Validate image-to-image support
    if image_path and not model_info.supports_image_to_image:
        errors.append(f"Model '{model_name}' does not support image-to-image generation")
    
    return errors


# Default values
DEFAULT_MODEL = StabilityModel.CORE
DEFAULT_ASPECT_RATIO = AspectRatio.SQUARE
DEFAULT_OUTPUT_FORMAT = OutputFormat.PNG
DEFAULT_SEED = 0
DEFAULT_STRENGTH = 0.7