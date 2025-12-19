#
# Copyright (c) 2025, Daily
#
# SPDX-License-Identifier: BSD 2-Clause License
#

import os
import sys

from dotenv import load_dotenv
from image_sync_processor import GeminiASLImageGenerator
from loguru import logger
from pipecat.audio.vad.silero import SileroVADAnalyzer
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.runner import PipelineRunner
from pipecat.pipeline.task import PipelineParams, PipelineTask
from pipecat.processors.frameworks.rtvi import RTVIConfig, RTVIObserver, RTVIProcessor
from pipecat.serializers.protobuf import ProtobufFrameSerializer
from pipecat.services.google.image import GoogleImageGenService
from pipecat.services.google.llm import GoogleLLMService
from pipecat.services.google.stt import GoogleSTTService
from pipecat.transports.websocket.fastapi import (
    FastAPIWebsocketParams,
    FastAPIWebsocketTransport,
)

load_dotenv(override=True)
logger.remove(0)
logger.add(sys.stderr, level="DEBUG")


async def run_bot(websocket_client):
    ws_transport = FastAPIWebsocketTransport(
        websocket=websocket_client,
        params=FastAPIWebsocketParams(
            audio_in_enabled=True,
            audio_out_enabled=False,
            add_wav_header=False,
            vad_analyzer=SileroVADAnalyzer(),
            serializer=ProtobufFrameSerializer(),
        ),
    )

    stt = GoogleSTTService(
        credentials_path=os.getenv("GOOGLE_APPLICATION_CREDENTIALS"),
    )

    # Initialize Gemini LLM for ASL gloss translation
    gemini_llm = GoogleLLMService(
        api_key=os.getenv("GOOGLE_API_KEY") or "",
    )

    # Initialize Google Imagen for ASL image generation
    image_gen_service = GoogleImageGenService(
        api_key=os.getenv("GOOGLE_API_KEY") or "",
        params=GoogleImageGenService.InputParams(model="imagen-4.0-fast-generate-001")
    )

    # RTVI events for Pipecat client UI
    rtvi = RTVIProcessor(config=RTVIConfig(config=[]))

    # ASL Image Generator for hand sign display
    asl_image_generator = GeminiASLImageGenerator(
        llm_service=gemini_llm,  # Pass the Gemini LLM service
        image_gen_service=image_gen_service,  # Pass the Imagen service
        rtvi_processor=rtvi,  # Pass RTVI processor for custom messages
    )

    pipeline = Pipeline(
        [
            ws_transport.input(),
            rtvi,
            stt,
            asl_image_generator,
            ws_transport.output(),
        ]
    )

    task = PipelineTask(
        pipeline,
        params=PipelineParams(
            enable_metrics=True,
            enable_usage_metrics=True,
        ),
        observers=[RTVIObserver(rtvi)],
    )

    @rtvi.event_handler("on_client_ready")
    async def on_client_ready(rtvi):
        logger.info("Pipecat client ready.")
        await rtvi.set_bot_ready()

    @ws_transport.event_handler("on_client_connected")
    async def on_client_connected(transport, client):
        logger.info("Pipecat Client connected")

    @ws_transport.event_handler("on_client_disconnected")
    async def on_client_disconnected(transport, client):
        logger.info("Pipecat Client disconnected")
        await task.cancel()

    runner = PipelineRunner(handle_sigint=False)
    await runner.run(task)
