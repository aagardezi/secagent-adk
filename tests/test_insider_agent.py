import os
import sys

# Set environment variables
os.environ["GOOGLE_CLOUD_LOCATION"] = "global"
os.environ["GOOGLE_GENAI_USE_VERTEXAI"] = "true"

# Ensure the edgar_agent module can be found
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from edgar_agent.agent import root_agent
from google.adk import Runner
from google.adk.sessions import InMemorySessionService

def test_insider_agent():
    print("Testing Insider Trading Agent with query: 'Analyze insider trading for TSLA'")
    print("\n\n--- AGENT RESPONSE ---")
    
    from google.adk.sessions import Session
    session_service = InMemorySessionService()
    
    import asyncio
    asyncio.run(session_service.create_session(app_name="sec_test_app", user_id="test_user", session_id="test_session"))
    
    runner = Runner(agent=root_agent, app_name="sec_test_app", session_service=session_service)
    
    from google.genai import types
    query_msg = types.Content(role="user", parts=[types.Part.from_text(text="Analyze insider trading for TSLA")])
    
    print("Starting runner loop...")
    with open("/tmp/event_logs_pro_final.txt", "w") as f:
        try:
            for i, event in enumerate(runner.run(
                user_id="test_user", 
                session_id="test_session", 
                new_message=query_msg
            )):
                f.write(f"--- Event {i} ---\n")
                f.write(f"Type: {type(event)}\n")
                f.write(f"Repr: {repr(event)}\n")
                if hasattr(event, '__dict__'):
                     f.write(f"Dict: {event.__dict__}\n")
                f.write("\n")
                print(".", end="", flush=True)
            print("\nRunner loop finished. Logs written to /tmp/event_logs_pro_final.txt")
        except Exception as e:
            f.write(f"Error during runner.run: {e}\n")
            print(f"Error: {e}")

    print("\n")

if __name__ == "__main__":
    test_insider_agent()
