
import asyncio
import logging
import sys
from agents import main_agent
from services.plan_director import PlanDirector

# --- Logging Configuration ---
# Set root logger to WARNING to silence third-party libs
logging.basicConfig(level=logging.WARNING, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

# Explicitly set our application loggers to INFO so we see what's happening
logging.getLogger("src").setLevel(logging.INFO)
logging.getLogger("agents").setLevel(logging.INFO)
logging.getLogger("services").setLevel(logging.INFO)
logging.getLogger("engine").setLevel(logging.INFO)

# Silence specific noisy libraries further if needed
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logging.getLogger("google").setLevel(logging.WARNING)

async def run_console_chat():
    """
    Initializes the main agent and runs a console-based chat loop.
    """
    # 1. Start the Plan Director (The Orchestrator)
    # It will listen for Task events in the background
    director = PlanDirector()
    director.start()

    # 2. Create the Main Agent (The User Interface)
    me = main_agent.create_main_agent()

    print("\n" + "="*50)
    print("🤖 HELPER INITIALIZED & READY TO ROCK")
    print("Type 'q' or 'exit' to leave.")
    print("="*50 + "\n")

    try:
        step = 1
        while True:
            try:
                # Basic input loop
                user_input = input(f"\n[{step}] You: ").strip()
            except EOFError:
                print("\n\nCatch ya later! 👋")
                break

            if user_input.lower() in ['q', 'exit', 'quit']:
                print("\nCatch ya later! 👋")
                break

            if not user_input:
                continue

            print("\nHelper: ", end="", flush=True)
            
            # 3. Stream response from Main Agent
            try:
                async for chunk in me.stream(user_input):
                    # Handle Tool Calls (The Thought)
                    if hasattr(chunk, 'tool_call') and chunk.tool_call:
                        args = str(chunk.tool_call.arguments)
                        if len(args) > 100: args = args[:100] + "..."
                        print(f"\n[⚙️ Calling: {chunk.tool_call.name}({args})]", end="", flush=True)
                    
                    # Handle Tool Results (The Action)
                    elif hasattr(chunk, 'tool_result') and chunk.tool_result:
                        res = str(chunk.tool_result.result)
                        # if len(res) > 100: res = res[:100] + "..."
                        print(f" -> [✅ Result: {res}]\n", flush=True)
                    
                    # Handle Text Content (The Speech)
                    elif hasattr(chunk, 'content') and chunk.content:
                        print(chunk.content, end="", flush=True)
                    
                    # Handle Permission Requests (HITL)
                    elif hasattr(chunk, 'permission_request') and chunk.permission_request:
                        names = ", ".join([t.name for t in chunk.permission_request])
                        print(f"\n\n⚠️  PERMISSION REQUIRED: I need to run: {names}\nType 'yes' to approve.", end="", flush=True)

            except Exception as e:
                print(f"\n❌ Error during processing: {e}")

            print("\n" + "-" * 50)
            step += 1

    except KeyboardInterrupt:
        print("\n\nShutting down gracefully... Bye!")
    finally:
        # Cleanup if needed
        pass

if __name__ == "__main__":
    try:
        asyncio.run(run_console_chat())
    except KeyboardInterrupt:
        pass
