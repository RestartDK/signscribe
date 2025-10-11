import asyncio
import os
import base64
from pipecat.frames.frames import Frame, OutputImageRawFrame, TranscriptionFrame, TextFrame
from pipecat.processors.frame_processor import FrameDirection, FrameProcessor
from pipecat.processors.frameworks.rtvi import RTVIServerMessageFrame
from PIL import Image

# Dummy data configuration 
ASSETS_DIR = os.path.join(os.path.dirname(__file__), "assets")

# Dummy word to hand image mapping
DUMMY_WORD_TO_HAND_MAPPING = {
    "hello": "hand-1.png",
    "hi": "hand-2.png", 
    "thanks": "hand-3.png",
    "yes": "hand-4.png",
    "no": "hand-5.png",
    "good": "hand-1.png",
    "bad": "hand-2.png",
    "please": "hand-3.png",
    "sorry": "hand-4.png",
    "welcome": "hand-5.png"
}

def load_dummy_hand_images():
    """Load and cache all hand images for dummy implementation"""
    hand_images = {}
    for i in range(1, 6):
        image_path = os.path.join(ASSETS_DIR, f"hand-{i}.png")
        if os.path.exists(image_path):
            img = Image.open(image_path)
            # Convert to RGB if necessary for consistent format
            if img.mode != 'RGB':
                img = img.convert('RGB')
            
            # Save to bytes buffer to get proper PNG/JPEG data
            import io
            buffer = io.BytesIO()
            img.save(buffer, format='PNG')
            image_bytes = buffer.getvalue()
            
            hand_images[f"hand-{i}.png"] = {
                'bytes': image_bytes,
                'size': img.size,
                'format': 'PNG'
            }
            print(f"Loaded hand-{i}.png: {len(image_bytes)} bytes, size: {img.size}")
    return hand_images

# Load dummy hand images at module level
DUMMY_HAND_IMAGES = load_dummy_hand_images()

class GeminiASLImageGenerator(FrameProcessor):
    def __init__(self, llm_service=None, sign_cache=None, rtvi_processor=None):
        super().__init__()
        self.llm_service = llm_service  
        self.sign_cache = sign_cache or {}  
        self.current_sentence = ""
        self.rtvi_processor = rtvi_processor  
        
    async def translate_to_asl_gloss(self, english_text: str) -> str:
        """Dummy implementation - just return the input text split by words"""
        return english_text.lower().strip()
    
    async def generate_sign_image(self, word: str) -> dict:
        """Generate hand sign image for a given word using dummy mapping"""
        # Clean the word
        clean_word = word.lower().strip().replace('.', '').replace(',', '').replace('!', '').replace('?', '')
        
        # Check if we have a direct mapping
        if clean_word in DUMMY_WORD_TO_HAND_MAPPING:
            hand_image = DUMMY_WORD_TO_HAND_MAPPING[clean_word]
        else:
            # Use hash to deterministically select a hand image for unmapped words
            hand_index = (hash(clean_word) % 5) + 1
            hand_image = f"hand-{hand_index}.png"
        
        # Return cached image data
        if hand_image in DUMMY_HAND_IMAGES:
            return DUMMY_HAND_IMAGES[hand_image]
        
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
                    sign_image = await self.generate_sign_image(word)
                    
                    if sign_image:
                        # Convert image to base64 for transmission
                        image_base64 = base64.b64encode(sign_image['bytes']).decode('utf-8')
                        
                        # Send image data as custom message to client
                        if self.rtvi_processor:
                            message_data = {
                                "type": "asl_image",
                                "image": image_base64,
                                "format": sign_image['format'],
                                "size": sign_image['size'],
                                "word": word,
                                "timestamp": asyncio.get_event_loop().time()
                            }
                            
                            await self.rtvi_processor.push_frame(
                                RTVIServerMessageFrame(data=message_data)
                            )
                        
                        # Also push the original frame for compatibility
                        await self.push_frame(
                            OutputImageRawFrame(
                                image=sign_image['bytes'],
                                size=sign_image['size'],
                                format=sign_image['format']
                            )
                        )
                        
                        # Add delay between images for sequential display
                        if i < len(words) - 1:  # Don't delay after the last word
                            await asyncio.sleep(0.8)  # 800ms delay between images
        
        await self.push_frame(frame, direction)