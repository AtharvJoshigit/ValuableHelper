import asyncio
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
                if chunk.content:
                    print(chunk.content, end="", flush=True)
            print("\n" + "-" * 40)

    except KeyboardInterrupt: # Handles Ctrl+C
        print("\n\nShutting down gracefully... Bye!")
        sys.exit(0)

if __name__ == "__main__":
    asyncio.run(chat())