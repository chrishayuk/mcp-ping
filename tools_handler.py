import json
import logging
import re
from typing import Optional, Dict, Any
from messages.tools import send_call_tool, send_tools_list

def parse_tool_response(response: str) -> Optional[Dict[str, Any]]:
    """Parse tool call from Llama's XML-style format."""
    function_regex = r"<function=(\w+)>(.*?)</function>"
    match = re.search(function_regex, response)
    
    if match:
        function_name, args_string = match.groups()
        try:
            args = json.loads(args_string)
            return {
                "function": function_name,
                "arguments": args,
            }
        except json.JSONDecodeError as error:
            logging.debug(f"Error parsing function arguments: {error}")
    return None

async def handle_tool_call(tool_call, conversation_history, read_stream, write_stream):
    """Handle a single tool call for both OpenAI and Llama formats."""
    try:
        # Handle object-style tool calls from both OpenAI and Ollama
        if hasattr(tool_call, 'function') or (isinstance(tool_call, dict) and 'function' in tool_call):
            # Get tool name and arguments based on format
            if hasattr(tool_call, 'function'):
                tool_name = tool_call.function.name
                raw_arguments = tool_call.function.arguments
            else:
                tool_name = tool_call['function']['name']
                raw_arguments = tool_call['function']['arguments']
        else:
            # Parse Llama's XML format from the last message
            last_message = conversation_history[-1]["content"]
            parsed_tool = parse_tool_response(last_message)
            if not parsed_tool:
                logging.debug("Unable to parse tool call from message")
                return
            
            tool_name = parsed_tool["function"]
            raw_arguments = parsed_tool["arguments"]

        # Parse the tool arguments
        tool_args = json.loads(raw_arguments) if isinstance(raw_arguments, str) else raw_arguments
        
        # print the tool invocation
        print(f"\nTool: '{tool_name}' invoked with arguments: {tool_args}")

        # execute the tool
        tool_response = await send_call_tool(tool_name, tool_args, read_stream, write_stream)
        if tool_response.get("isError"):
            logging.debug(f"Error calling tool: {tool_response.get('error')}")
            return

        # Format and display the response
        formatted_response = format_tool_response(tool_response.get("content", []))
        logging.debug(f"Tool '{tool_name}' Response: {formatted_response}")  # Fixed logging line

        # Add the tool call to conversation history (required for OpenAI)
        conversation_history.append({
            "role": "assistant",
            "content": None,
            "tool_calls": [{
                "id": f"call_{tool_name}",
                "type": "function",
                "function": {
                    "name": tool_name,
                    "arguments": json.dumps(tool_args) if isinstance(tool_args, dict) else tool_args
                }
            }]
        })

        # Add the tool response to conversation history
        conversation_history.append({
            "role": "tool",
            "name": tool_name,
            "content": formatted_response,
            "tool_call_id": f"call_{tool_name}"
        })

    except json.JSONDecodeError:
        logging.debug(f"Error decoding arguments for tool '{tool_name}': {raw_arguments}")
    except Exception as e:
        logging.debug(f"Error handling tool call: {str(e)}")

def format_tool_response(response_content):
    """Format the response content from a tool."""
    if isinstance(response_content, list):
        return "\n".join(
            item.get("text", "No content") for item in response_content if item.get("type") == "text"
        )
    
    # return the formatted tool response
    return str(response_content)

async def fetch_tools(read_stream, write_stream):
    """Fetch tools from the server."""
    logging.debug("\nFetching tools for chat mode...")

    # get the tools list
    tools_response = await send_tools_list(read_stream, write_stream)
    tools = tools_response.get("tools", [])

    # check the tools are valid
    if not isinstance(tools, list) or not all(isinstance(tool, dict) for tool in tools):
        # invalid tools
        logging.debug("Invalid tools format received.")
        return None
    
    # return the tools
    return tools

def convert_to_openai_tools(tools):
    """Convert tools into OpenAI-compatible function definitions."""
    openai_tools = []
    for tool in tools:
        # Ensure tool has required fields
        if "name" not in tool or "inputSchema" not in tool:
            logging.debug(f"Skipping invalid tool: {tool}")
            continue

        # Convert tool to OpenAI format
        openai_tool = {
            "type": "function",
            "function": {
                "name": tool["name"],
                "description": tool.get("description", ""),
                "parameters": tool.get("inputSchema", {})
            }
        }

        # Ensure parameters has type and properties
        if "type" not in openai_tool["function"]["parameters"]:
            openai_tool["function"]["parameters"]["type"] = "object"
        if "properties" not in openai_tool["function"]["parameters"]:
            openai_tool["function"]["parameters"]["properties"] = {}

        openai_tools.append(openai_tool)

    return openai_tools