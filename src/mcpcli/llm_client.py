import logging
import os
import uuid
import json
from typing import Any, Dict, List

import ollama
import boto3
from dotenv import load_dotenv
from openai import OpenAI

# Load environment variables
load_dotenv()

BEDROCK_MODEL_IDS = {
        "claude-3.5-haiku": "anthropic.claude-3-5-haiku-20241022-v1:0",
        "claude-3.5-sonnet": "anthropic.claude-3-5-sonnet-20241022-v2:0",
        "nova-lite":"amazon.nova-lite-v1:0",
        "nova-pro":"amazon.nova-pro-v1:0",
    }

class LLMClient:
    def __init__(self, provider="openai", model="gpt-4o-mini", api_key=None):
        # set the provider, model and api key
        self.provider = provider
        self.model = model
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self.base_url = None or os.getenv("OPENAI_BASE_URL")

        # ensure we have the api key for openai if set
        if provider == "openai" and not self.api_key:
            raise ValueError("The OPENAI_API_KEY environment variable is not set.")

        # check ollama is good
        if provider == "ollama" and not hasattr(ollama, "chat"):
            raise ValueError("Ollama is not properly configured in this environment.")
        
        # check amazon is good
        if provider == "amazon" and not hasattr(boto3, "client"):
            raise ValueError("Amazon is not properly configured in this environment.")
        
    def create_completion(
        self, messages: List[Dict], tools: List = None
    ) -> Dict[str, Any]:
        """Create a chat completion using the specified LLM provider."""
        if self.provider == "openai":
            # perform an openai completion
            return self._openai_completion(messages, tools)
        elif self.provider == "ollama":
            # perform an ollama completion
            return self._ollama_completion(messages, tools)
        elif self.provider == "amazon":
            # perform an amazon completion'
            return self._amazon_completion(messages, tools)
        else:
            # unsupported providers
            raise ValueError(f"Unsupported provider: {self.provider}")

    def _openai_completion(self, messages: List[Dict], tools: List) -> Dict[str, Any]:
        """Handle OpenAI chat completions."""
        # get the openai client
        client = OpenAI(api_key=self.api_key)
        
        try:
            # make a request, passing in tools
            response = client.chat.completions.create(
                model=self.model,
                messages=messages,
                tools=tools or [],
            )

            # return the response
            return {
                "response": response.choices[0].message.content,
                "tool_calls": getattr(response.choices[0].message, "tool_calls", []),
            }
        except Exception as e:
            # error
            logging.error(f"OpenAI API Error: {str(e)}")
            raise ValueError(f"OpenAI API Error: {str(e)}")

    def _ollama_completion(self, messages: List[Dict], tools: List) -> Dict[str, Any]:
        """Handle Ollama chat completions."""
        # Format messages for Ollama
        ollama_messages = [
            {"role": msg["role"], "content": msg["content"]} for msg in messages
        ]

        try:
            # Make API call with tools
            response = ollama.chat(
                model=self.model,
                messages=ollama_messages,
                stream=False,
                tools=tools or [],
            )

            logging.info(f"Ollama raw response: {response}")

            # Extract the message and tool calls
            message = response.message
            tool_calls = []

            # Convert Ollama tool calls to OpenAI format
            if hasattr(message, "tool_calls") and message.tool_calls:
                for tool in message.tool_calls:
                    tool_calls.append(
                        {
                            "id": str(uuid.uuid4()),  # Generate unique ID
                            "type": "function",
                            "function": {
                                "name": tool.function.name,
                                "arguments": tool.function.arguments,
                            },
                        }
                    )

            return {
                "response": message.content if message else "No response",
                "tool_calls": tool_calls,
            }

        except Exception as e:
            # error
            logging.error(f"Ollama API Error: {str(e)}")
            raise ValueError(f"Ollama API Error: {str(e)}")

    def _amazon_completion(self, messages: List[Dict], tools: List) -> Dict[str, Any]:
        """Handle Amazon chat completions."""
        client = boto3.client('bedrock-runtime', region_name=os.getenv("AWS_REGION", "us-east-1"))
        model_id = BEDROCK_MODEL_IDS.get(self.model, "anthropic.claude-3-5-sonnet-20241022-v2:0")
        try:
            # Separate system messages from other messages
            system_prompts = []
            conversation_messages = []
            
            
            for msg in messages:
                if msg["role"] == "system":
                    system_prompts.append({"text": msg["content"]})
                else:
                    # Handle tool results differently
                    
                    if isinstance(msg["content"], list) and msg["content"] and "toolResult" in msg["content"][0]:
                        
                        if 'toolResult' in msg["content"][0]:
                            if 'tool_call_result' not in msg['content'][0]['toolResult']['content'][0]['json']:
                                msg['content'][0]['toolResult']['content'][0]['json']={"tool_call_result":msg['content'][0]['toolResult']['content'][0]['json']}
                            conversation_messages.append({
                                "role": msg["role"],
                                "content": msg["content"]  # Keep the original toolResult structure
                            })
                    else:
                        conversation_messages.append({
                            "role": msg["role"],
                            "content": [{"text": msg["content"]}]
                        })

            # Use the list of system prompt dictionaries directly
            # Handle nested text content for assistant messages
            for msg in conversation_messages:
                if msg["role"] == "assistant" and isinstance(msg["content"], list) and len(msg["content"]) == 1 and isinstance(msg["content"][0]["text"], list):
                    msg["content"] = msg["content"][0]["text"]
            logging.debug("conversation_messages", conversation_messages)
            # Convert OpenAI format tools to Amazon Bedrock format
            tool_config = {
                "tools": []
            }
            
            if tools:
                for tool in tools:
                    if tool["type"] == "function":
                        func = tool["function"]
                        bedrock_tool = {
                            "toolSpec": {
                                "name": func["name"].replace("-", "_"),
                                "description": func.get("description", func["name"]),
                                "inputSchema": {
                                    "json": func["parameters"]
                                }
                            }
                        }
                        tool_config["tools"].append(bedrock_tool)

            # Make API call with tools
            response = client.converse(
                modelId=model_id,
                messages=conversation_messages,
                toolConfig=tool_config if tools else None,
                system=system_prompts
            )

            logging.info(f"Amazon raw response: {response}")

            # Extract the message and tool calls
            output_message = response.get('output', {}).get('message', {})
            content_list = output_message.get('content', [])
            
            # Extract text response and tool calls
            response_text = ""
            tool_calls = []


            
            
            for content in content_list:
                if 'text' in content:
                    response_text += content['text']
                elif 'toolUse' in content:
                    tool_use = content['toolUse']
                    tool_calls.append({
                        'id': tool_use.get('toolUseId', str(uuid.uuid4())),
                        'type': 'function',
                        'function': {
                            'name': tool_use['name'].replace("_", "-"),
                            'arguments': json.dumps(tool_use.get('input', {}))
                        }
                    })
            return {
                "response": response_text or "No response",
                "tool_calls": tool_calls
            }

        except Exception as e:
            import traceback
            traceback.print_exc()
            logging.error(f"Amazon API Error: {str(e)}")
            raise ValueError(f"Amazon API Error: {str(e)}")
