# src/console_chat.py
import asyncio
import sys
from agents import main_agent

async def run_console_chat():
    """
    Initializes the main agent and runs a console-based chat loop.
    """
    me = main_agent.create_main_agent()

    print("\n" + "="*50)
    print("🤖 HELPER INITIALIZED & READY TO ROCK")
    print("Type 'q' or 'exit' to leave.")
    print("="*50 + "\n")

    try:
        step = 1
        while True:
            try:
                user_input = input(f"[{step}] You: ").strip()
            except EOFError:  # Handles Ctrl+D
                print("\n\nCatch ya later! 👋")
                break

            if user_input.lower() in ['q', 'exit', 'quit']:
                print("\nCatch ya later! 👋")
                break

            if not user_input:
                continue

            print("\nHelper: ", end="", flush=True)
            async for chunk in me.stream(user_input):
                if hasattr(chunk, 'tool_call') and chunk.tool_call:
                    # Nicely print tool calls
                    args = str(chunk.tool_call.arguments)
                    if len(args) > 50: args = args[:50] + "..."
                    print(f"\n> Calling Tool: '{chunk.tool_call.name}' with arguments: {args}\n", flush=True)
                elif hasattr(chunk, 'tool_result') and chunk.tool_result:
                    # Nicely print tool results
                    res = str(chunk.tool_result.result)
                    if len(res) > 50: res = res[:50] + "..."
                    print(f"\n< Tool '{chunk.tool_result.name}' finished. with result {res}\n", flush=True)
                elif hasattr(chunk, 'content') and chunk.content:
                    # Stream content as it arrives
                    print()
                    print(chunk.content, end="", flush=True)
                elif hasattr(chunk, 'permission_request') :
                    print(chunk.permission_request, end="", flush=True)
                else : 
                    print(f'Usage: {chunk.usage}')

            print("\n" + "-" * 50)
            step += 1

    except KeyboardInterrupt:  # Handles Ctrl+C
        print("\n\nShutting down gracefully... Bye!")
    finally:
        # Perform any cleanup here if necessary
        pass

if __name__ == "__main__":
    # This allows running the console chat directly for testing
    asyncio.run(run_console_chat())
