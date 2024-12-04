import argparse
import logging
import sys
import anyio
import asyncio
import os
from config import load_config
from messages.tools import send_call_tool, send_tools_list
from messages.resources import send_resources_list
from messages.prompts import send_prompts_list
from messages.send_initialize_message import send_initialize
from messages.ping import send_ping
from chat_handler import handle_chat_mode
from transport.stdio.stdio_client import stdio_client

# Default path for the configuration file
DEFAULT_CONFIG_FILE = "server_config.json"

# Configure logging
logging.basicConfig(
    level=logging.CRITICAL,
    format='%(asctime)s - %(levelname)s - %(message)s',
    stream=sys.stderr
)

async def handle_command(command: str, read_stream, write_stream):
    """Handle specific commands dynamically."""
    try:
        if command == "ping":
            # ping server
            print("\nPinging Server...")
            result = await send_ping(read_stream, write_stream)
            print("Server is up and running" if result else "Server ping failed")
        elif command == "list-tools":
            # list tools
            print("\nFetching Tools List...")
            tools = await send_tools_list(read_stream, write_stream)
            print("Tools List:", tools)
        elif command == "call-tool":
            # call tool
            tool_name = input("Enter tool name: ").strip()
            if not tool_name:
                print("Tool name cannot be empty.")
                return True

            arguments_str = input("Enter tool arguments as JSON (e.g., {'key': 'value'}): ").strip()
            try:
                arguments = eval(arguments_str)  # Convert string to dict
            except Exception as e:
                print(f"Invalid arguments format: {e}")
                return True

            print(f"\nCalling tool '{tool_name}' with arguments: {arguments}")
            result = await send_call_tool(tool_name, arguments, read_stream, write_stream)
            if result.get("isError"):
                print(f"Error calling tool: {result.get('error')}")
            else:
                print("Tool Response:", result.get("content"))
        elif command == "list-resources":
            # list resources
            print("\nFetching Resources List...")
            resources = await send_resources_list(read_stream, write_stream)
            print("Resources List:", resources)
        elif command == "list-prompts":
            # list prompts
            print("\nFetching Prompts List...")
            prompts = await send_prompts_list(read_stream, write_stream)
            print("Prompts List:", prompts)
        elif command == "chat":
            # Retrieve provider and model from environment variables
            provider = os.getenv("LLM_PROVIDER", "openai")
            model = os.getenv("LLM_MODEL", "gpt-4o-mini")
    
            # Announce provider and model in use
            print(f"\nEntering chat mode using provider '{provider}' and model '{model}'...")

            # handle chat mode
            await handle_chat_mode(read_stream, write_stream, provider,model)
        elif command in ["quit", "exit"]:
            # exit
            print("\nGoodbye!")
            return False
        elif command == "clear":
            if sys.platform == "win32":
                # clear
                os.system("cls")
            else:
                # clear
                os.system("clear")
        elif command == "help":
            # help commands
            print("\nAvailable commands:")
            print("  ping          - Check if server is responsive")
            print("  list-tools    - Display available tools")
            print("  list-resources- Display available resources")
            print("  list-prompts  - Display available prompts")
            print("  chat          - Enter chat mode")
            print("  clear         - Clear the screen")
            print("  help          - Show this help message")
            print("  quit/exit     - Exit the program")
        else:
            print(f"\nUnknown command: {command}")
            print("Type 'help' for available commands")
    except Exception as e:
        print(f"\nError executing command: {e}")
    
    return True


async def get_input():
    """Get input asynchronously."""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, lambda: input("\n> ").strip().lower())

async def interactive_mode(read_stream, write_stream):
    """Run the CLI in interactive mode."""
    print("\nWelcome to the Interactive MCP Command-Line Tool")
    print("Type 'help' for available commands or 'quit' to exit")
    
    while True:
        try:
            command = await get_input()
            if not command:
                continue
                
            should_continue = await handle_command(command, read_stream, write_stream)
            if not should_continue:
                return
                
        except KeyboardInterrupt:
            print("\nUse 'quit' or 'exit' to close the program")
        except EOFError:
            break
        except Exception as e:
            print(f"\nError: {e}")

class GracefulExit(Exception):
    """Custom exception for handling graceful exits."""
    pass

async def main(config_path: str, server_name: str, command: str = None) -> None:
    """Main function to manage server initialization, communication, and shutdown."""
    try:
        # Load server configuration
        server_params = await load_config(config_path, server_name)
        
        # Establish stdio communication
        async with stdio_client(server_params) as (read_stream, write_stream):
            # Initialize the server
            init_result = await send_initialize(read_stream, write_stream)
            if not init_result:
                print("Server initialization failed")
                return

            if command:
                # Single command mode
                await handle_command(command, read_stream, write_stream)
            else:
                # Interactive mode
                await interactive_mode(read_stream, write_stream)
                
            # Break the event loop to ensure clean exit
            loop = asyncio.get_event_loop()
            loop.stop()

    except KeyboardInterrupt:
        # exiting gracefully on keyboard interrupt
        print("\nGoodbye!")
    except Exception as e:
        # Handle any other exceptions
        print(f"Error in main: {e}")
    finally:
        # Ensure we exit the process
        os._exit(0)

if __name__ == "__main__":
    # Argument parser setup
    parser = argparse.ArgumentParser(description="MCP Command-Line Tool")

    # Configuration file argument
    parser.add_argument(
        "--config-file",
        default=DEFAULT_CONFIG_FILE,
        help="Path to the JSON configuration file containing server details.",
    )

    # Server configuration argument
    parser.add_argument(
        "--server",
        required=True,
        help="Name of the server configuration to use from the config file.",
    )

    # Command argument (optional)
    parser.add_argument(
        "command",
        nargs="?",
        choices=["ping", "list-tools", "list-resources", "list-prompts"],
        help="Command to execute (optional - if not provided, enters interactive mode).",
    )

    # Provider argument
    parser.add_argument(
        "--provider",
        choices=["openai", "ollama", "groq"],
        default="openai",
        help="LLM provider to use. Defaults to 'openai'.",
    )

    # Model argument
    parser.add_argument(
        "--model",
        help=(
            "Model to use. Defaults to 'gpt-4o-mini' for 'openai', 'qwen2.5-coder' for 'ollama', "
            "and 'llama3-groq-70b-8192-tool-use-preview' for 'groq'."
        ),
    )

    # Parse arguments
    args = parser.parse_args()

    # Determine the model based on the provider and user input
    default_models = {
        "openai": "gpt-4o-mini",
        "ollama": "qwen2.5-coder",
        "groq": "llama3-groq-70b-8192-tool-use-preview"
    }
    model = args.model or default_models[args.provider]

    # Set environment variables for provider and model
    os.environ["LLM_PROVIDER"] = args.provider
    os.environ["LLM_MODEL"] = model  

    try:
        # Run the main function
        anyio.run(main, args.config_file, args.server, args.command)
    except KeyboardInterrupt:
        # Exit on keyboard interrupt
        os._exit(0)
    except Exception as e:
        print(f"Error occurred: {e}")
        os._exit(1)
