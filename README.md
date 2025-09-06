# Stability AI MCP Server

A [Model Context Protocol](https://modelcontextprotocol.io/) server for Stability AI image generation. This Python implementation extends the original work by [@tadasant](https://github.com/tadasant/mcp-server-stability-ai) with support for the newer Core and Ultra models, plus **inline image display** in Claude.

## Credit

This project builds upon the excellent foundation laid by [@tadasant's original MCP server for Stability AI](https://github.com/tadasant/mcp-server-stability-ai). Please refer to the original repository for additional usage examples and patterns. This Python implementation adds:

- Support for the new `stable-image-core` and `stable-image-ultra` endpoints
- Updated SD3.5 model support
- **Inline image display** - images appear directly in Claude chat instead of just file paths
- Python-based implementation for easier community contribution
- Enhanced error handling and validation

## Supported Models

**Core/Ultra Models (newer endpoints):**
- `stable-image-core` (default): Fast, affordable, natural language optimized
- `stable-image-ultra`: Highest quality, state-of-the-art results

**SD3.5 Family Models:**
- `sd3.5-large`: 8B parameter model with maximum detail
- `sd3.5-large-turbo`: Faster version of SD3.5 Large
- `sd3.5-medium`: 2B parameter model, efficient
- `sd3.5-flash`: Ultra-fast 4-step generation

## Requirements

- Python 3.10+
- Stability AI API key from [platform.stability.ai/account/keys](https://platform.stability.ai/account/keys)
- Claude Desktop

## Installation

Install directly from GitHub:

```bash
pip install git+https://github.com/keizerkarel1/stability-ai-mcp-server
```

## Configuration

Add to your Claude Desktop configuration file:

**macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`  
**Windows**: `%APPDATA%\Claude\claude_desktop_config.json`

### Windows Configuration:
```json
{
  "mcpServers": {
    "stability-ai": {
      "command": "C:\\Users\\yourusername\\AppData\\Roaming\\Python\\Python311\\Scripts\\stability-mcp-server.exe",
      "env": {
        "STABILITY_API_KEY": "your-stability-api-key-here",
        "IMAGE_STORAGE_PATH": "C:\\Users\\yourusername\\Pictures\\StabilityAI"
      }
    }
  }
}
```

### macOS Configuration:
```json
{
  "mcpServers": {
    "stability-ai": {
      "command": "stability-mcp-server",
      "env": {
        "STABILITY_API_KEY": "your-stability-api-key-here",
        "IMAGE_STORAGE_PATH": "/Users/yourusername/Pictures/StabilityAI"
      }
    }
  }
}
```

**Required:**
- `STABILITY_API_KEY`: Your Stability AI API key

**Optional:**
- `IMAGE_STORAGE_PATH`: Directory for saving generated images (defaults to `./images/`)

Restart Claude Desktop after configuration.

## Usage

**Text-to-image:**
```
Generate a mountain landscape at sunset
```

**With specific model:**
```
Generate a cityscape using sd3.5-large model
```

**Image-to-image:**
```
Transform this image: /path/to/image.jpg into a watercolor style
```

Images will display inline in Claude and also be saved to your configured storage path.

## Tools

### `generate_image`
**Parameters:**
- `prompt` (required): Text description
- `model`: Model to use (default: `stable-image-core`)
- `aspect_ratio`: Image ratio (default: `1:1`)
- `seed`: Random seed (default: `0`)
- `output_format`: `png` or `jpeg` (default: `png`)
- `negative_prompt`: What to avoid in the image
- `image_path`: Input image for image-to-image
- `strength`: Transformation strength 0.0-1.0 (default: `0.7`)

### `list_models`
Returns available models and their capabilities.

### `get_storage_info`
Returns storage directory information and statistics.

## File Storage

Images are automatically saved with timestamps and metadata:

```
/your/storage/path/
├── stability_20250106_143022_12345.png
├── stability_20250106_143022_12345_metadata.json
```

Metadata includes generation parameters, file info, and API response details.

## Model Selection

**stable-image-core** (default): Fast, affordable, natural language optimized. Good for everyday use.

**stable-image-ultra**: Highest quality results. Better for important or detailed images.

**sd3.5-large**: Maximum control and detail. Good for technical artwork.

**sd3.5-medium**: Balanced performance and cost.

**sd3.5-flash**: Fastest generation. Good for quick previews and iteration.

## Contributing

Contributions are welcome. Please submit issues or pull requests to improve the code, documentation, or add features.

## License

Open source. See LICENSE file for details.

## Acknowledgments

- [@tadasant](https://github.com/tadasant/mcp-server-stability-ai) for the original MCP server implementation
- [Stability AI](https://stability.ai/) for the image generation APIs
- [Model Context Protocol](https://modelcontextprotocol.io/) team

- [Anthropic](https://anthropic.com/) for Claude Desktop
