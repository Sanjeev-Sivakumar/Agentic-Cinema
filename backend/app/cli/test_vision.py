import argparse
import asyncio
import json
import sys
from pathlib import Path

from app.core.config import settings
from app.services.vision_provider.factory import get_vision_provider

def main():
    """
    Single-frame vision smoke test utility.
    Processes exactly one image, executes exactly one vision request, prints the parsed result,
    provider/model, and exits cleanly. Does NOT process video.
    """
    parser = argparse.ArgumentParser(
        description="Single-frame visual clearance intelligence smoke test"
    )
    parser.add_argument(
        "--image",
        type=str,
        required=True,
        help="Path to an individual candidate video frame image (JPEG/PNG)",
    )
    parser.add_argument(
        "--provider",
        type=str,
        choices=["gemini", "groq"],
        default="gemini",
        help="Vision LLM provider to test (default: gemini, optional: groq)",
    )

    args = parser.parse_args()
    image_path = Path(args.image)
    if not image_path.exists() or not image_path.is_file():
        print(f"Error: Image file not found: {args.image}", file=sys.stderr)
        sys.exit(1)

    print("==================================================")
    print("CHAIN OF TITLE — SINGLE-FRAME VISION SMOKE TEST")
    print("==================================================")

    provider = get_vision_provider(args.provider)
    print(f"Provider: {provider.provider_name.upper()}")
    print(f"Model:    {getattr(provider, 'model', 'N/A')}")
    print(f"Image:    {image_path.resolve()}")
    print("--------------------------------------------------")
    print("Analyzing single frame...")

    context = {
        "timestamp": 0.0,
        "scene_number": 1,
        "ocr_hints": "Single frame smoke test",
        "obj_hints": "None",
    }

    result = asyncio.run(provider.analyze_frame(str(image_path), context))

    print("\n--------------------------------------------------")
    print(f"Status:   {result.get('status')}")
    print(f"Latency:  {result.get('latency_ms', 0)}ms")
    entities = result.get("entities", [])
    print(f"Entities: {len(entities)} detected")
    print("--------------------------------------------------")
    if entities:
        print(json.dumps(entities, indent=2))
    elif result.get("error"):
        print(f"Error details: {result.get('error')}")
    else:
        print("No clearance-relevant entities detected.")
    print("==================================================")

if __name__ == "__main__":
    main()
