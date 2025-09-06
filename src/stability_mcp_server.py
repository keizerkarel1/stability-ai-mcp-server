#!/usr/bin/env python3
"""
Stability AI MCP Server

A Model Context Protocol server for generating images using Stability AI's models.
Supports SD3.5 family, Stable Image Core, and Stable Image Ultra.
"""

import asyncio
import logging
import os
import platform
import subprocess
import sys
from typing import Optional

# Configure logging to stderr (MCP requirement)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stderr)]
)
logger = logging.getLogger(__name__)

try:
    from mcp.server import Server
    from mcp.server.stdio import stdio_server
    from mcp.types import Tool, TextContent
except ImportError as e:
    logger.error(f"Missing MCP dependencies: {e}")
    logger.error("Please install: pip install mcp")
    sys.exit(1)

from .models import (
    StabilityModel, 
    get_available_models, 
    get_model_validation_errors,
    DEFAULT_MODEL,
    DEFAULT_ASPECT_RATIO,
    DEFAULT_OUTPUT_FORMAT,
    DEFAULT_SEED,
    DEFAULT_STRENGTH
)
from .stability_client import StabilityClient, StabilityAPIError, generate_image
from .utils import save_image_with_metadata, get_storage_stats, StorageError


def open_image_with_system_viewer(image_path: str) -> bool:
    """Open image with system default viewer."""
    try:
        system = platform.system()
        if system == "Windows":
            os.startfile(image_path)
        elif system == "Darwin":  # macOS
            subprocess.run(["open", image_path], check=True)
        elif system == "Linux":
            subprocess.run(["xdg-open", image_path], check=True)
        else:
            logger.warning(f"Unknown system {system}, cannot open image viewer")
            return False
        return True
    except Exception as e:
        logger.error(f"Failed to open image viewer: {e}")
        return False


# Initialize MCP server
app = Server("stability-ai")


@app.list_tools()
async def list_tools() -> list[Tool]:
    """List available tools."""
    return [
        Tool(
            name="generate_image",
            description=(
                "Generate images using Stability AI models. "
                "Supports text-to-image and image-to-image generation with 6 different models. "
                "Core/Ultra models are optimized for natural language prompts. "
                "SD3.5 models offer more technical control."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "prompt": {
                        "type": "string",
                        "description": "Text description of the desired image. For Core/Ultra models, use natural language. For SD3.5 models, detailed technical descriptions work best."
                    },
                    "model": {
                        "type": "string",
                        "description": f"Model to use for generation. Default: {DEFAULT_MODEL.value}",
                        "enum": [model.value for model in StabilityModel],
                        "default": DEFAULT_MODEL.value
                    },
                    "aspect_ratio": {
                        "type": "string", 
                        "description": f"Image aspect ratio. Default: {DEFAULT_ASPECT_RATIO.value}",
                        "enum": ["1:1", "16:9", "9:16", "21:9", "9:21", "3:2", "2:3", "5:4", "4:5", "4:3", "3:4"],
                        "default": DEFAULT_ASPECT_RATIO.value
                    },
                    "seed": {
                        "type": "integer",
                        "description": f"Random seed for reproducible results. Default: {DEFAULT_SEED}",
                        "minimum": 0,
                        "maximum": 4294967294,
                        "default": DEFAULT_SEED
                    },
                    "output_format": {
                        "type": "string",
                        "description": f"Output image format. Default: {DEFAULT_OUTPUT_FORMAT.value}",
                        "enum": ["png", "jpeg"],
                        "default": DEFAULT_OUTPUT_FORMAT.value
                    },
                    "negative_prompt": {
                        "type": "string",
                        "description": "What to avoid in the image. Not supported by all models.",
                        "default": ""
                    },
                    "image_path": {
                        "type": "string",
                        "description": "Path to input image for image-to-image generation (optional)",
                        "default": ""
                    },
                    "strength": {
                        "type": "number",
                        "description": f"How much to transform input image (0.0-1.0). Only used for image-to-image. Default: {DEFAULT_STRENGTH}",
                        "minimum": 0.0,
                        "maximum": 1.0,
                        "default": DEFAULT_STRENGTH
                    }
                },
                "required": ["prompt"]
            }
        ),
        
        Tool(
            name="list_models",
            description="Get information about available Stability AI models and their capabilities.",
            inputSchema={
                "type": "object",
                "properties": {},
                "required": []
            }
        ),
        
        Tool(
            name="get_storage_info", 
            description="Get information about the image storage directory and its contents.",
            inputSchema={
                "type": "object",
                "properties": {},
                "required": []
            }
        )
    ]


@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    """Handle tool calls."""
    
    if name == "generate_image":
        return await handle_generate_image(arguments)
    
    elif name == "list_models":
        return await handle_list_models(arguments)
    
    elif name == "get_storage_info":
        return await handle_get_storage_info(arguments)
    
    else:
        raise ValueError(f"Unknown tool: {name}")


async def handle_generate_image(arguments: dict) -> list[TextContent]:
    """Handle image generation requests."""
    try:
        # Extract parameters with defaults
        prompt = arguments["prompt"]
        model = arguments.get("model", DEFAULT_MODEL.value)
        aspect_ratio = arguments.get("aspect_ratio", DEFAULT_ASPECT_RATIO.value)
        seed = arguments.get("seed", DEFAULT_SEED)
        output_format = arguments.get("output_format", DEFAULT_OUTPUT_FORMAT.value)
        negative_prompt = arguments.get("negative_prompt", "")
        image_path = arguments.get("image_path", "").strip()
        strength = arguments.get("strength", DEFAULT_STRENGTH)
        
        # Use None for empty image_path to indicate text-to-image
        if not image_path:
            image_path = None
        
        # Validate parameters
        validation_errors = get_model_validation_errors(
            model_name=model,
            aspect_ratio=aspect_ratio,
            output_format=output_format,
            seed=seed,
            strength=strength if image_path else None,
            negative_prompt=negative_prompt if negative_prompt else None,
            image_path=image_path
        )
        
        if validation_errors:
            error_message = "Parameter validation failed:\n" + "\n".join(f"• {error}" for error in validation_errors)
            return [TextContent(
                type="text",
                text=error_message
            )]
        
        # Generate image
        logger.info(f"Generating image with model {model}")
        logger.info(f"Prompt: {prompt[:100]}...")
        
        result = await generate_image(
            prompt=prompt,
            model=model,
            aspect_ratio=aspect_ratio,
            seed=seed,
            output_format=output_format,
            negative_prompt=negative_prompt,
            image_path=image_path,
            strength=strength
        )
        
        # Prepare metadata
        metadata = {
            "prompt": prompt,
            "model": model,
            "aspect_ratio": aspect_ratio,
            "seed": result.seed,
            "output_format": output_format,
            "negative_prompt": negative_prompt,
            "finish_reason": result.finish_reason,
            "generation_type": "image-to-image" if image_path else "text-to-image"
        }
        
        if image_path:
            metadata["input_image_path"] = image_path
            metadata["strength"] = strength
        
        # Save image and metadata to disk
        try:
            image_file_path, metadata_file_path = save_image_with_metadata(
                result.image_data, 
                metadata
            )
            
            # Try to open the image with system viewer
            viewer_opened = open_image_with_system_viewer(image_file_path)
            viewer_status = "🖼️ Opened in system image viewer" if viewer_opened else "📁 Saved to disk"
            
            success_message = (
                f"✅ Image generated successfully!\n\n"
                f"**Model:** {model}\n"
                f"**Type:** {'Image-to-image' if image_path else 'Text-to-image'}\n"
                f"**Seed:** {result.seed}\n" 
                f"**Format:** {output_format}\n"
                f"**File:** {image_file_path}\n"
                f"**Status:** {viewer_status}\n\n"
                f"The image has been saved and should open automatically in your default image viewer."
            )
            
            return [TextContent(type="text", text=success_message)]
            
        except StorageError as e:
            return [TextContent(
                type="text", 
                text=f"❌ Image generated but failed to save: {e}"
            )]
    
    except StabilityAPIError as e:
        logger.error(f"Stability API error: {e.message}")
        error_msg = f"❌ **Stability AI Error:** {e.message}"
        
        # Add helpful suggestions based on error type
        if e.error_type == "authentication_error":
            error_msg += "\n\n💡 **Solution:** Please check your STABILITY_API_KEY in Claude Desktop settings."
        elif e.error_type == "content_filtered":
            error_msg += "\n\n💡 **Suggestions:**\n• Try a different prompt\n• Add negative prompts to avoid restricted content\n• Use more general/abstract descriptions"
        elif "credits" in e.message.lower():
            error_msg += "\n\n💡 **Solution:** Please check your Stability AI account balance at https://platform.stability.ai/"
        elif e.error_type == "network_error":
            error_msg += "\n\n💡 **Solution:** Please check your internet connection and try again."
        
        return [TextContent(type="text", text=error_msg)]
    
    except Exception as e:
        logger.error(f"Unexpected error in generate_image: {e}", exc_info=True)
        return [TextContent(
            type="text",
            text=f"❌ **Unexpected Error:** {e}\n\nPlease check the server logs for more details."
        )]


async def handle_list_models(arguments: dict) -> list[TextContent]:
    """Handle list models requests."""
    try:
        models = get_available_models()
        
        response = "**Available Stability AI Models:**\n\n"
        
        # Group models by type
        core_ultra = []
        sd3_5_models = []
        
        for model_id, description in models.items():
            if "stable-image-" in model_id:
                core_ultra.append((model_id, description))
            else:
                sd3_5_models.append((model_id, description))
        
        # Display Core/Ultra models first (recommended)
        if core_ultra:
            response += "**🚀 Core/Ultra Models (Recommended):**\n"
            for model_id, description in core_ultra:
                default_marker = " ⭐ (Default)" if model_id == DEFAULT_MODEL.value else ""
                response += f"• **{model_id}**{default_marker}: {description}\n"
            response += "\n"
        
        # Display SD3.5 models
        if sd3_5_models:
            response += "**🔧 SD3.5 Family Models:**\n"
            for model_id, description in sd3_5_models:
                response += f"• **{model_id}**: {description}\n"
        
        response += (
            "\n**Usage Tips:**\n"
            "• Core/Ultra models work best with natural language prompts\n"
            "• SD3.5 models offer more technical control and detailed parameters\n"
            "• Use `stable-image-core` for fast, cost-effective generation\n"
            "• Use `stable-image-ultra` for highest quality results\n"
            "• Use `sd3.5-flash` for rapid iteration and previews"
        )
        
        return [TextContent(type="text", text=response)]
    
    except Exception as e:
        logger.error(f"Error listing models: {e}")
        return [TextContent(
            type="text", 
            text=f"❌ Error retrieving model information: {e}"
        )]


async def handle_get_storage_info(arguments: dict) -> list[TextContent]:
    """Handle storage info requests."""
    try:
        stats = get_storage_stats()
        
        if "error" in stats:
            return [TextContent(
                type="text",
                text=f"❌ Error getting storage information: {stats['error']}"
            )]
        
        response = (
            f"**📁 Image Storage Information:**\n\n"
            f"**Storage Path:** {stats['storage_path']}\n"
            f"**Total Files:** {stats['total_files']}\n"
            f"**Image Files:** {stats['image_files']}\n" 
            f"**Metadata Files:** {stats['metadata_files']}\n"
            f"**Total Size:** {stats['total_size_mb']} MB\n\n"
            f"💡 **Tip:** Images are saved automatically after generation and can be opened from their file paths."
        )
        
        return [TextContent(type="text", text=response)]
    
    except Exception as e:
        logger.error(f"Error getting storage info: {e}")
        return [TextContent(
            type="text",
            text=f"❌ Error retrieving storage information: {e}"
        )]


async def main():
    """Main server entry point."""
    # Validate API key on startup
    api_key = os.getenv("STABILITY_API_KEY")
    if not api_key:
        logger.error("STABILITY_API_KEY environment variable not set")
        logger.error("Please configure your API key in Claude Desktop settings")
        sys.exit(1)
    
    logger.info("Starting Stability AI MCP Server...")
    logger.info(f"Default model: {DEFAULT_MODEL.value}")
    
    # Test storage path
    try:
        from .utils import get_storage_path
        storage_path = get_storage_path()
        logger.info(f"Image storage path: {storage_path}")
    except StorageError as e:
        logger.error(f"Storage configuration error: {e}")
        sys.exit(1)
    
    # Run server
    async with stdio_server() as (read_stream, write_stream):
        await app.run(
            read_stream,
            write_stream,
            app.create_initialization_options()
        )


def main_sync():
    """Synchronous entry point for pip-installed console script."""
    asyncio.run(main())


if __name__ == "__main__":
    main_sync()