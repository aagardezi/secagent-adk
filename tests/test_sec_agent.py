import os
import sys

# Ensure the edgar_agent module can be found
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from edgar_agent.agent import root_agent
from google.adk import Runner
from google.adk.sessions import InMemorySessionService

def test_sec_agent():
    print("Testing SEC Agent with query: 'Analyze the latest 10-K risk factors for TSLA'")
    print("\n\n--- AGENT RESPONSE ---")
    
    from google.adk.sessions import Session
    session_service = InMemorySessionService()
    
    import asyncio
    asyncio.run(session_service.create_session(app_name="sec_test_app", user_id="test_user", session_id="test_session"))
    
    runner = Runner(agent=root_agent, app_name="sec_test_app", session_service=session_service)
    
    from google.genai import types
    query_msg = types.Content(role="user", parts=[types.Part.from_text(text="Analyze the latest 10-K risk factors for TSLA")])
    
    for event in runner.run(
        user_id="test_user", 
        session_id="test_session", 
        new_message=query_msg
    ):
        if hasattr(event, 'text') and event.text:
             print(event.text, end="", flush=True)

    print("\n")

if __name__ == "__main__":
    test_sec_agent()



