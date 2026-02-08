import asyncio
from cgi import print_arguments
import sys
from agents import main_agent

async def chat():
    me = main_agent.create_main_agent()

    print("\n" + "="*50)
    print("🤖 HELPER INITIALIZED & READY TO ROCK")
    print("Type 'q' or 'exit' to leave.")
    print("="*50 + "\n")

    try:
        while True:
            try:
                user_input = input("You: ").strip()
            except EOFError: # Handles Ctrl+D
                break

            if user_input.lower() in ['q', 'exit', 'quit']:
                print("\nCatch ya later! 👋")
                break

            if not user_input:
                continue

            print("\nHelper: ", end="", flush=True)
            async for chunk in me.stream(user_input):
                if chunk.tool_call : 
                    print(chunk.tool_call, end="", flush=True)
                elif chunk.tool_result: 
                    print(chunk.tool_result, end="", flush=True)
                elif chunk.finish_reason: 
                    print(chunk.finish_reason, end="", flush=True)
                elif chunk.content:
                    print(chunk.content, end="", flush=True)
                else : 
                    print(chunk.usage, end="", flush=True)
            print("\n" + "-" * 40)

    except KeyboardInterrupt: # Handles Ctrl+C
        print("\n\nShutting down gracefully... Bye!")
        sys.exit(0)

if __name__ == "__main__":
    asyncio.run(chat())