import datetime
import os
from zoneinfo import ZoneInfo
from google.adk.agents import Agent, ParallelAgent, SequentialAgent
from google.adk.tools.function_tool import FunctionTool
from google.adk.tools import google_search # Keeping google_search as it's not a finhub tool
import vertexai
from .config import config

# Import only the new SEC tools
from .tools.sec import full_text_search, get_recent_filings, extract_filing_section

def get_current_date() -> str:
    """Returns the current date in YYYY-MM-DD format."""
    return datetime.date.today().strftime("%Y-%m-%d")

get_current_date_tool = FunctionTool(get_current_date)


vertexai.init(
    project=os.environ['GOOGLE_CLOUD_PROJECT'],
    location="global",
)

search_agent = Agent(
    name="search_agent",
    # model="gemini-2.5-flash",
    model=config.gemini_model,
    description=(
        "Agent to search about anything"
    ),
    instruction="I can answer your questions by searching the internet. Just ask me anything!",
    tools=[google_search],
)

sec_search_agent = Agent(
    name="sec_search_agent",
    model=config.gemini_model,
    description="Agent for searching across all recent SEC filings for specific topics or keywords.",
    instruction=(
        "You are an SEC research assistant. Use the `full_text_search` tool to find SEC filings "
        "mentioning specific keywords, phrases, or topics. "
        "ALWAYS use the `get_current_date` tool first to determine the date range if the user doesn't specify one, "
        "defaulting to searching the past year. "
        "Summarize the findings clearly, noting which companies are discussing these topics."
    ),
    tools=[get_current_date_tool, full_text_search],
    output_key="sec_search_results"
)

sec_filing_agent = Agent(
    name="sec_filing_agent",
    model=config.gemini_model,
    description="Agent for finding and extracting specific sections from a company's SEC filings.",
    instruction=(
        "You are an SEC filing extraction specialist. When asked about a specific company's financials or risks: "
        "1. Use `get_recent_filings` to find the URL for the most recent filing (default to 10-K). "
        "2. Use `extract_filing_section` with that URL to pull exactly the text needed (e.g., '1A' for Risk Factors, '7' for Management Discussion). "
        "Return the raw extracted text so the report agent can analyze it."
    ),
    tools=[get_recent_filings, extract_filing_section],
    output_key="sec_filing_extracts"
)

sec_report_agent = Agent(
    name="sec_report_agent",
    model=config.gemini_model,
    description="Agent that synthesizes raw SEC filing text into comprehensive financial reports.",
    instruction=(
        "You are a highly skilled financial analyst. Your job is to read raw SEC extracts and search results "
        "and synthesize them into a professional, structured investment report. "
        "Make sure to highlight key risk factors, management discussion points, and broad market trends "
        "based strictly on the provided context. "
        "Do NOT invent information. If data is missing, state what is missing.\n"
        "Input Context:\n"
        "Search Results: {sec_search_results}\n"
        "Filing Extracts: {sec_filing_extracts}\n"
    ),
    output_key="sec_final_report"
)

# A sequential agent representing the pipeline for deep company analysis
sec_master_agent = SequentialAgent(
    name="sec_master_agent",
    description="Master agent that coordinates SEC search, extraction, and report generation.",
    sub_agents=[sec_search_agent, sec_filing_agent, sec_report_agent]
)

# The report_creation_agent needs to be updated to reflect the new SEC agents and removed finhub agents.
# For now, I'll keep its structure but remove references to finhub results.
# The instruction will need to be updated to reflect what data it now receives.
report_creation_agent = Agent(
    name="report_creation_agent",
    model=config.gemini_model,
    description=(
        "You are an agent helping an investment analyst create a report on an asset or stock"
    ),
    instruction=(
        """
        Your primary task is to synthesize the following research summaries, clearly attributing findings to their source areas. Structure your response using headings for each topic. Ensure the report is coherent and integrates the key points smoothly.
        **Crucially: Your entire response MUST be grounded *exclusively* on the information provided in the 'Input Summaries' below. Do NOT add any external knowledge, facts, or details not present in these specific summaries.**
         **Input Summaries:**

 *   **SEC Analysis:**
     {sec_final_report}

        **Comprehensive Report:** Your report should be comprehensive, detailed and contain the following sections:
                            *   **SEC Analysis:** Provide a detailed overview of the SEC search results and filing extracts, highlighting key risk factors, management discussion points, and broad market trends.

                        **4. Data Handling and Error Management:**

                        *   **Data Completeness:** If a function requires date that is not present or unavailable, use the current year as the default period. Report missing data but don't let it stop you.
                        *   **Function Execution:** Execute functions carefully, ensuring you have the necessary data, especially dates and symbols, before invoking any function.
                        *   **Clear Output:** Present results in a clear and concise manner, suitable for an asset management investor.

                        **5. Analytical Perspective:**

                        *   **Asset Management Lens:** Conduct all analysis with an asset manager's perspective in mind. Evaluate the company as a potential investment, focusing on risk, return, and long-term prospects."""
    )
)

# The data_retrieval_agent needs to be updated to reflect the new SEC agents and removed finhub agents.
# It will now only contain the sec_master_agent.
data_retrieval_agent = ParallelAgent(
    name="data_retrieval_agent",
    description=(
        "You are an agent that helps a financial analyst to retrieve info about a company or stock"
    ),
    sub_agents=[sec_master_agent]
)


# The sequential_agent needs to be updated to reflect the new SEC agents and removed finhub agents.
# It will now use the data_retrieval_agent (which contains sec_master_agent) and then report_creation_agent.
# The symbol_lookup_agent is removed.
sequential_agent = SequentialAgent(
    name="sequential_agent",
    description=(
        "you are the agent that runs the process for collecting the data and creating the report"
    ),
    sub_agents=[data_retrieval_agent, report_creation_agent]
)



# The root_agent needs to be updated to reflect the new SEC agents and removed finhub agents.
# Its instruction needs to be simplified to reflect the new capabilities.
root_agent = Agent(
    name="investment_agent",
    model=config.gemini_model,
    description=(
        "You are an agent helping an investment analyst at an asset manager"
    ),
    instruction=(
        """You are a highly skilled financial analyst specializing in asset management. Your task is to conduct thorough financial analysis and generate detailed reports from an investor's perspective. Follow these guidelines meticulously:

                        **1. Date Handling:**

                        *   **Current Date Determination:** Use the `get_current_date` function to obtain the current date at the beginning of each analysis. This date is critical for subsequent time-sensitive operations.
                        *   **Default Year Range:** If a function call requires a date range and the user has not supplied one, calculate the start and end dates for the *current year* using the date obtained from `current_date`. Use these as the default start and end dates in the relevant function calls.
                        *   Make sure you get the date and calculate the start and end date based on the current date if the prompt asks.
                        If the prompt already mentions a start and end date then use it.
                        Do not generate code to handle date, use the the get_current_date tool to do the date calculation.

                        **2. Analysis Components:**

                        Use the data_retrieval_agent to collect data for the following sections

                        *   **Comprehensive Report:** Your report should be comprehensive, detailed and contain the following sections:
                            *   **SEC Analysis:** Provide a detailed overview of the SEC search results and filing extracts, highlighting key risk factors, management discussion points, and broad market trends.


                        **3. Data Handling and Error Management:**

                        *   **Data Completeness:** If a function requires date that is not present or unavailable, use the current year as the default period. Report missing data but don't let it stop you.
                        *   **Function Execution:** Execute functions carefully, ensuring you have the necessary data, especially dates and symbols, before invoking any function.
                        *   **Clear Output:** Present results in a clear and concise manner, suitable for an asset management investor.

                        **4. Analytical Perspective:**

                        *   **Asset Management Lens:** Conduct all analysis with an asset manager's perspective in mind. Evaluate the company as a potential investment, focusing on risk, return, and long-term prospects.

                        **Example Workflow (Implicit):**

                        1.  Get the current date using `get_current_date`.
                        2.  Call the data_retrieval_agent to perform SEC searches and filing extractions.
                        3.  Assemble a detailed and insightful report that addresses the SEC analysis section mentioned above using report_creation_agent.
                        
                        "Make sure you run all the sub agents" 
                        "Use the report_creation_agent to create a report on the investment and return it"
                        "in order to analyse a company use the data_retrieval_agent"
                        "report_creation_agent should be called right at the end of the analysis to create the final report."
                        Always call report_creation_agent at the end of the analysis.

                        """

    ),
    tools=[get_current_date_tool],
    sub_agents=[sequential_agent]
)