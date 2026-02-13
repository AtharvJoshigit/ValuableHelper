import asyncio
import logging
import sys
from agents.agent_id import AGENT_ID
from engine.core.agent_instance_manager import get_agent_manager

# --- Logging Configuration ---
# Set root logger to WARNING to silence third-party libs
logging.getLogger().setLevel(logging.WARNING)

# Explicitly set our application loggers to INFO
logging.getLogger("src").setLevel(logging.INFO)
logging.getLogger("agents").setLevel(logging.INFO)
logging.getLogger("services").setLevel(logging.INFO)
logging.getLogger("engine").setLevel(logging.INFO)

async def run_console_chat():
    """
    Runs a console-based chat loop using the Main Agent.
    """
    print("\n" + "="*50)
    print("🤖 HELPER INITIALIZED & READY TO ROCK")
    print("Type 'q' or 'exit' to leave.")
    print("="*50 + "\n")

    # Get the Main Agent from the manager (it should be started by main.py)
    manager = get_agent_manager()
    me = manager.get_agent(AGENT_ID.MAIN_AGENT)
    
    if not me:
        print("❌ Error: Main Agent not found. Did you start ALLFixedAgents?")
        return

    step = 1
    try:
        while True:
            try:
                # Use asyncio.to_thread for input to not block the event loop entirely
                # (though standard input() is blocking, in this simple loop it's acceptable
                # unless we want background tasks to run *while* waiting for input.
                # Since PlanDirector runs in background, we should use a non-blocking input if possible,
                # but for simplicity, standard input blocks the loop. 
                # To allow background tasks (PlanDirector) to run, we should offload input.)
                
                # Simple blocking input for now - PlanDirector might pause while waiting for user input
                # if we don't offload.
                # BETTER APPROACH: Use run_in_executor
                
                user_input = await asyncio.get_event_loop().run_in_executor(None, input, f"\n[{step}] You: ")
                user_input = user_input.strip()

            except EOFError:
                print("\n\nCatch ya later! 👋")
                break

            if user_input.lower() in ['q', 'exit', 'quit']:
                print("\nCatch ya later! 👋")
                break

            if not user_input:
                continue

            print("\nHelper: ", end="", flush=True)
            
            # Stream response
            try:
                async for chunk in me.stream(user_input):
                    # Handle Tool Calls
                    if hasattr(chunk, 'tool_call') and chunk.tool_call:
                        args = str(chunk.tool_call.arguments)
                        if len(args) > 100: args = args[:100] + "..."
                        print(f"\n[⚙️ Calling: {chunk.tool_call.name}({args})]", end="", flush=True)
                    
                    # Handle Tool Results
                    elif hasattr(chunk, 'tool_result') and chunk.tool_result:
                        res = str(chunk.tool_result.result)
                        print(f" -> [✅ Result: {res[:100]}...]\n", flush=True)
                    
                    # Handle Text Content
                    elif hasattr(chunk, 'content') and chunk.content:
                        print(chunk.content, end="", flush=True)
                    
                    # Handle Permission Requests (HITL)
                    elif hasattr(chunk, 'permission_request') and chunk.permission_request:
                        names = ", ".join([t.name for t in chunk.permission_request])
                        print(f"\n\n⚠️  PERMISSION REQUIRED: I need to run: {names}")
                        decision = await asyncio.get_event_loop().run_in_executor(None, input, "Type 'yes' to approve: ")
                        # Logic to approve/deny would go here, but stream might handle it differently 
                        # depending on how 'permission_request' is implemented in the agent.
                        # For now, just notifying user.

            except Exception as e:
                print(f"\n❌ Error during processing: {e}")

            print("\n" + "-" * 50)
            step += 1

    except KeyboardInterrupt:
        print("\n\nShutting down gracefully... Bye!")

if __name__ == "__main__":
    try:
        # For standalone testing, we need to init the agent manually
        from agents.all_agents import ALLFixedAgents
        from engine.core.provide import auto_register_providers
        auto_register_providers()
        ALLFixedAgents.start()
        
        asyncio.run(run_console_chat())
    except KeyboardInterrupt:
        pass