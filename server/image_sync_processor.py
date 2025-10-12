import asyncio
import base64
from typing import Any, Dict, Optional

import requests
from loguru import logger
from pipecat.frames.frames import (
    ErrorFrame,
    Frame,
    OutputImageRawFrame,
    TranscriptionFrame,
    URLImageRawFrame,
)
from pipecat.processors.frame_processor import FrameDirection, FrameProcessor
from pipecat.processors.frameworks.rtvi import RTVIServerMessageFrame


class GeminiASLImageGenerator(FrameProcessor):
    def __init__(
        self,
        llm_service=None,
        image_gen_service=None,
        sign_cache=None,
        rtvi_processor=None,
    ):
        super().__init__()
        self.llm_service = llm_service
        self.image_gen_service = image_gen_service
        self.sign_cache = sign_cache or {}
        self.current_sentence = ""
        self.rtvi_processor = rtvi_processor

    async def translate_to_asl_gloss(self, english_text: str) -> str:
        """Translate English text to ASL gloss using LLM"""
        if not self.llm_service:
            logger.warning("No LLM service available, returning original text")
            return english_text.lower().strip()

        try:
            prompt = f"Translate the following English text to American Sign Language (ASL) gloss notation. Return only the ASL gloss words separated by spaces: {english_text}"

            # Send the prompt to the LLM service using run_inference
            from pipecat.processors.aggregators.llm_context import LLMContext

            context = LLMContext(messages=[{"role": "user", "content": prompt}])
            response = await self.llm_service.run_inference(context)
            return (
                response.strip().lower() if response else english_text.lower().strip()
            )
        except Exception as e:
            logger.error(f"Error translating to ASL gloss: {e}")
            return english_text.lower().strip()

    async def generate_sign_image(self, word: str) -> Optional[Dict[str, Any]]:
        """Generate hand sign image for a given word using Google Imagen"""
        # Clean the word
        clean_word = (
            word.lower()
            .strip()
            .replace(".", "")
            .replace(",", "")
            .replace("!", "")
            .replace("?", "")
        )

        # Check cache first
        if clean_word in self.sign_cache:
            logger.info(f"Using cached image for word: {clean_word}")
            return self.sign_cache[clean_word]

        # Generate new image if not cached
        if not self.image_gen_service:
            logger.warning("No image generation service available")
            return None

        try:
            prompt = f"Photorealistic hand gesture showing American Sign Language sign for '{clean_word}', clear hand position, neutral background, professional reference photo"

            logger.info(f"Generating ASL image for word: {clean_word}")

            # Generate image using Google Imagen
            image_data = None
            async for frame in self.image_gen_service.run_image_gen(prompt):
                logger.debug(
                    f"Received frame type: {type(frame)} for word: {clean_word}"
                )
                if isinstance(frame, URLImageRawFrame):
                    logger.info(f"Got URLImageRawFrame for word '{clean_word}'")

                    # Check if frame has direct image data
                    if hasattr(frame, "image") and frame.image is not None:
                        logger.info(
                            f"Frame has direct image data: {len(frame.image)} bytes"
                        )
                        image_bytes = frame.image

                        # Get image size from frame if available
                        image_size = getattr(frame, "size", (512, 512))

                        # Get image format from frame if available
                        image_format = getattr(frame, "format", "PNG")

                        image_data = {
                            "bytes": image_bytes,
                            "size": image_size,
                            "format": image_format,
                        }

                        # Cache the result
                        self.sign_cache[clean_word] = image_data
                        logger.info(
                            f"Generated and cached ASL image for word: {clean_word}"
                        )
                        break

                    # Fallback: try to download from URL if available
                    elif hasattr(frame, "url") and frame.url is not None:
                        logger.info(f"Frame has URL: {frame.url}")
                        logger.debug(f"Downloading image from URL: {frame.url}")
                        response = requests.get(frame.url)
                        if response.status_code == 200:
                            image_bytes = response.content
                            logger.info(
                                f"Successfully downloaded image for '{clean_word}': {len(image_bytes)} bytes"
                            )

                            # Try to get image dimensions from frame or use default
                            image_size = getattr(frame, "size", (512, 512))
                            image_format = getattr(frame, "format", "PNG")

                            image_data = {
                                "bytes": image_bytes,
                                "size": image_size,
                                "format": image_format,
                            }

                            # Cache the result
                            self.sign_cache[clean_word] = image_data
                            logger.info(
                                f"Generated and cached ASL image for word: {clean_word}"
                            )
                            break
                        else:
                            logger.error(
                                f"Failed to download image: HTTP {response.status_code}"
                            )
                    else:
                        logger.error(
                            f"No image data or URL found in frame for word: {clean_word}"
                        )

                elif isinstance(frame, ErrorFrame):
                    logger.error(
                        f"Error generating image for word '{clean_word}': {frame.error}"
                    )
                    return None
                else:
                    logger.debug(f"Unexpected frame type: {type(frame)}")

            if image_data is None:
                logger.warning(f"No image data received for word: {clean_word}")
            else:
                logger.info(f"Returning image data for word: {clean_word}")

            return image_data

        except Exception as e:
            logger.error(f"Exception generating ASL image for word '{clean_word}': {e}")
            return None

    async def process_frame(self, frame: Frame, direction: FrameDirection):
        await super().process_frame(frame, direction)

        # Only process user input (TranscriptionFrame) for ASL images
        # Skip LLM responses (TextFrame) to avoid generating images for Gemini's text
        if isinstance(frame, TranscriptionFrame):
            english_text = frame.text

            asl_gloss = await self.translate_to_asl_gloss(english_text)

            # Process each word and generate hand sign images
            words = asl_gloss.split()
            for i, word in enumerate(words):
                if word:  # Skip empty strings
                    try:
                        sign_image = await self.generate_sign_image(word)

                        if sign_image:
                            logger.info(
                                f"Processing image for word '{word}': {len(sign_image['bytes'])} bytes"
                            )

                            # Convert image to base64 for transmission
                            image_base64 = base64.b64encode(sign_image["bytes"]).decode(
                                "utf-8"
                            )
                            logger.debug(
                                f"Converted image to base64: {len(image_base64)} characters"
                            )

                            # Send image data as custom message to client
                            if self.rtvi_processor:
                                message_data = {
                                    "type": "asl_image",
                                    "image": image_base64,
                                    "format": sign_image["format"],
                                    "size": sign_image["size"],
                                    "word": word,
                                    "timestamp": asyncio.get_event_loop().time(),
                                }
                                logger.info(f"Sending RTVI message for word '{word}'")

                                await self.rtvi_processor.push_frame(
                                    RTVIServerMessageFrame(data=message_data)
                                )
                                logger.info(f"Sent RTVI message for word '{word}'")

                            # Also push the original frame for compatibility
                            logger.info(
                                f"Pushing OutputImageRawFrame for word '{word}'"
                            )
                            await self.push_frame(
                                OutputImageRawFrame(
                                    image=sign_image["bytes"],
                                    size=sign_image["size"],
                                    format=sign_image["format"],
                                )
                            )
                            logger.info(f"Pushed OutputImageRawFrame for word '{word}'")

                            # Add delay between images for sequential display
                            if i < len(words) - 1:  # Don't delay after the last word
                                logger.debug("Waiting 800ms before next word...")
                                await asyncio.sleep(0.8)  # 800ms delay between images
                        else:
                            # Send error message for failed image generation
                            if self.rtvi_processor:
                                error_data = {
                                    "type": "asl_image_error",
                                    "word": word,
                                    "error": "Failed to generate ASL image",
                                    "timestamp": asyncio.get_event_loop().time(),
                                }
                                await self.rtvi_processor.push_frame(
                                    RTVIServerMessageFrame(data=error_data)
                                )

                    except Exception as e:
                        logger.error(f"Error processing word '{word}': {e}")
                        # Continue with next word even if one fails
                        continue

        await self.push_frame(frame, direction)
