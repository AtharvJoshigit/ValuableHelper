
import json
import os
from typing import Optional
from dotenv import load_dotenv

from tele_bot import bot
from src.handler.main_agent_handler import create_main_agent



def main():
    
    agent = create_main_agent(
        provider="google",
        model="gemini-2.5-flash",
    )
    
    print("Main Agent initialized. Type 'exit' to quit, 'reset' to clear conversation.\n")
    
    while True:
        user_input = input("You: ").strip()
        
        if not user_input:
            continue
        
        if user_input.lower() == "exit":
            print("Goodbye!")
            break
        
        if user_input.lower() == "reset":
            agent.reset_conversation()
            print("Conversation reset.\n")
            continue
        
        if user_input.lower() == "save":
            agent.save_conversation("conversation.json")
            print("Conversation saved to conversation.json\n")
            continue
        
        response = agent.chat(user_input)
        
        if response["status"] == "success":
            print(f"\nAssistant: {response['response']}\n")
            
            if response.get("agent_calls", 0) > 0:
                print(f"[Used {response['agent_calls']} agent call(s) in {response['iterations']} iteration(s)]")
                for detail in response.get("details", []):
                    print(f"  - {detail['agent']}: {detail['status']}")
                print()
        else:
            print(f"\nError: {json.dumps(response, indent=2)}\n")


if __name__ == "__main__":
    load_dotenv(override=True)
    # main()
    bot.run()
