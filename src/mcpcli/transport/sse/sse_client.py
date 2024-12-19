import json
import logging
import asyncio
import traceback
import httpx
from contextlib import asynccontextmanager
from urllib.parse import urlparse
import anyio
import sys

from typing import Optional, Dict, Any
from mcpcli.messages.message_types.json_rpc_message import JSONRPCMessage

@asynccontextmanager
async def sse_client(url: str):
    """建立SSE连接并返回读写流"""
    parsed_url = urlparse(url)
    base_url = f"{parsed_url.scheme}://{parsed_url.netloc}"
    
    # Create memory object streams for reading and writing
    read_stream_writer, read_stream = anyio.create_memory_object_stream(0)
    write_stream, write_stream_reader = anyio.create_memory_object_stream(0)
    
    # Create Asynchttpx client, set timeout and keep connection
    limits = httpx.Limits(max_keepalive_connections=5, max_connections=10)
    async with httpx.AsyncClient(timeout=None, limits=limits) as client:
        # Add shared variable to store message endpoint
        message_endpoint = None
        
        async def sse_reader():
            nonlocal message_endpoint
            while True:  # Add reconnection logic
                try:
                    logging.debug(f"SSE transport endpoint: {url} connection init")
                    async with client.stream('GET', f"{url}", timeout=None) as response:
                        first_lines = []
                        async for line in response.aiter_lines():
                            # Collect first two lines of data
                            if len(first_lines) < 2:
                                first_lines.append(line.strip())
                                if len(first_lines) == 2:
                                    # Extract message endpoint from first line
                                    
                                    endpoint_line = first_lines[1]
                                    if endpoint_line.startswith('data:'):
                                        endpoint_data = endpoint_line.replace('data: ', '').strip()
                                        message_endpoint = endpoint_data
                                        logging.debug("Extracted message endpoint:", message_endpoint)
                                    continue
                                    
                                continue
                            
                            if line.strip().startswith('data: '):
                                data = line.replace('data: ', '').strip()
                                try:
                                    json_data = json.loads(data)
                                    message = JSONRPCMessage.model_validate(json_data)
                                    await read_stream_writer.send(message)
                                except json.JSONDecodeError as e:
                                    logging.error(f"JSON decode error: {e}")
                                except Exception as e:
                                    logging.error(f"Error processing message: {e}")
                except httpx.RequestError as e:
                    logging.error(f"SSE connection error: {e}")
                    await anyio.sleep(1)  # Wait before reconnecting
                except Exception as e:
                    logging.error(f"Unexpected error: {e}")
                    await anyio.sleep(1)  # Wait before reconnecting

        async def message_sender():
            try:
                async with write_stream_reader:
                    async for message in write_stream_reader:
                        json_data = message.model_dump_json(exclude_none=True)
                        try:
                            # Use stored message_endpoint
                            if message_endpoint:
                                endpoint = f"{base_url}{message_endpoint}"
                                logging.debug("Sending message to endpoint:", endpoint,json_data)
                                response = await client.post(
                                    endpoint,
                                    json=json.loads(json_data),
                                    headers={"Content-Type": "application/json"}
                                )
                                logging.debug(f"Message sent successfully: {response.status_code}")
                                logging.debug(f"Response: {response.text}")
                                response.raise_for_status()
                        except Exception as e:
                            traceback.print_exc()
                            logging.error(f"Error sending message: {e}")
            except Exception as e:
                logging.error(f"Message sender error: {e}")

        try:
            async with anyio.create_task_group() as tg:
                tg.start_soon(sse_reader)
                tg.start_soon(message_sender)
                yield read_stream, write_stream
        finally:
            await read_stream.aclose()
            await write_stream.aclose()