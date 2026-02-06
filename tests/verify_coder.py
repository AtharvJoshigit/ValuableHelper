import sys
import os

# Add project root to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.agents.coder_agent import CoderAgent

def main():
    print("Initializing CoderAgent...")
    try:
        agent = CoderAgent().start()
    except Exception as e:
        print(f"Failed to start CoderAgent: {e}")
        return

    message = "Please create a new file called 'test_protocol.py' with a print statement 'Permission Check Passed'."
    print(f"
Sending message: {message}")
    
    try:
        # Send the request to the agent
        response = agent.chat(message)
        
        print("
--- Agent Response ---")
        print(response)
        print("----------------------")
        
    except Exception as e:
        print(f"Error during communication: {e}")

if __name__ == "__main__":
    main()