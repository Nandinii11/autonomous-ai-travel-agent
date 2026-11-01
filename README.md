#  Autonomous AI Travel Agent

An AI-powered travel planning assistant that helps users create personalized travel itineraries based on their destination, budget, duration, interests, and travel preferences.

Built using **Python, Streamlit, LangGraph, and Groq LLM**, this project demonstrates how Agentic AI can understand user requests, plan tasks, execute tools, handle failures, and generate customized travel recommendations.

##  Features

- **Natural Language Understanding:** Understands travel requests written in everyday language.
- **Intelligent Travel Planning:** Creates personalized travel plans based on user preferences.
- **Multi-Agent Workflow:** Uses LangGraph to coordinate different stages of the travel-planning process.
- **Weather Information:** Retrieves weather forecasts using the Open-Meteo API.
- **Flight Cost Estimation:** Provides estimated flight costs using sample airline data and distance-based calculations.
- **Hotel Recommendations:** Suggests hotels based on budget and preferred category.
- **Attractions & Restaurants:** Recommends tourist attractions and restaurants using stored destination data.
- **Budget Management:** Calculates estimated expenses, including accommodation, transportation, food, activities, and 10% contingency.
- **Currency Conversion:** Retrieves exchange rates using the Frankfurter API.
- **Retry & Fallback Mechanism:** Handles service failures using retries and alternative data sources.
- **Short-Term Conversation Memory:** Maintains travel preferences across follow-up messages.
- **Interactive Interface:** Provides a user-friendly Streamlit interface.
- **Failure Simulation:** Allows users to simulate tool failures and observe how the agent handles them.

##  Technologies Used

| Technology | Purpose |
|---|---|
| Python | Core programming language |
| Streamlit | Interactive web application |
| LangGraph | Agent workflow orchestration |
| Groq API | LLM-powered request understanding |
| Llama 3.3 70B Versatile | Language model |
| Open-Meteo API | Weather information |
| Frankfurter API | Currency exchange rates |
| Pandas | Data processing |
| Python Requests | API communication |

##  Project Architecture

The application follows a multi-step Agentic AI workflow using LangGraph.

### Workflow

```text
             User Request
                  |
                  v
          Understand Node
                  |
                  v
             Plan Node
                  |
                  v
            Execute Node
                  |
                  v
            Reflect Node
                  |
          +-------+-------+
          |               |
       Incomplete       Complete
          |               |
          v               v
       Execute         Compose
          |               |
          +---------------+
                          |
                          v
                  Final Itinerary
```

### Workflow Explanation

**1. Understand**

- Accepts the user's travel request.
- Extracts destination, source, duration, budget, number of travellers, and interests.
- Uses Groq LLM when configured, with rule-based parsing as an alternative.
- Requests clarification when essential information is missing.

**2. Plan**

- Determines which travel services are required.
- Selects the appropriate tools based on the user's request.
- Organizes the execution workflow.

**3. Execute**

Executes the selected tools to collect travel information, such as:

- Weather information
- Flight cost estimates
- Hotel recommendations
- Tourist attractions
- Restaurant recommendations
- Budget calculations
- Currency conversion

**4. Reflect**

- Evaluates the results returned by the tools.
- Handles failures and incomplete results.
- Uses retries and fallback mechanisms where implemented.
- Can adjust hotel preferences and recalculate when the estimated budget exceeds the user's limit.

**5. Compose**

- Combines the collected information.
- Generates a personalized day-by-day itinerary.
- Provides estimated expenses and travel recommendations.
- Considers weather conditions when suggesting indoor and outdoor activities.

##  Project Structure

```text
autonomous-ai-travel-agent/
│
├── app.py              # Streamlit frontend
├── agent.py            # LangGraph agent workflow
├── tools.py            # Travel tools and API integrations
├── data.py             # Destination and sample data
├── llm.py              # LLM integration
├── cli.py              # Command-line interface
├── requirements.txt    # Project dependencies
├── README.md           # Project documentation
├── .gitignore          # Git ignored files
└── .env                # Local API credentials (not uploaded)
```

##  Installation and Setup

### Prerequisites

- Python 3.10 or later
- Git
- Groq API key (optional)

### 1. Clone the repository

```bash
git clone https://github.com/Nandinii11/autonomous-ai-travel-agent.git
```

### 2. Navigate to the project directory

```bash
cd autonomous-ai-travel-agent
```

### 3. Create a virtual environment

```bash
python -m venv .venv
```

Activate it on Windows PowerShell:

```powershell
.venv\Scripts\Activate.ps1
```

### 4. Install dependencies

```bash
pip install -r requirements.txt
```

### 5. Configure environment variables

Create a `.env` file in the project directory:

```env
GROQ_API_KEY=your_groq_api_key
```

Keep your API key private. Never upload your `.env` file to GitHub.

The application can also use its rule-based functionality when Groq is not configured.

### 6. Run the application

```bash
python -m streamlit run app.py
```

Open the local URL displayed in your terminal.

##  API Failure Handling

The application uses fallback mechanisms to improve reliability.

| Service | Primary Method | Fallback |
|---|---|---|
| Weather | Open-Meteo API | Stored seasonal climate data |
| Currency | Frankfurter API | Predefined exchange rates |
| Flights | Mock airline data and sample calculations | Distance-based cost estimation |
| Hotels | Local sample hotel data | No separate external API fallback |
| Attractions | Stored destination data | No separate external API fallback |
| Restaurants | Stored destination data | No separate external API fallback |

**Retry:** Attempts the same service again after a temporary failure.

**Fallback:** Uses an alternative data source or calculation method when the primary method is unavailable.

##  Budget Calculation

The agent estimates travel expenses using the following components:

- Transportation
- Hotel accommodation
- Food expenses
- Local transportation
- Tourist attractions and activities
- 10% contingency for unexpected expenses

**Total Estimated Budget = Base Travel Cost + 10% Contingency**

##  Human-Agent Interaction

The application supports interaction between the user and the AI agent through:

- Natural-language travel requests
- Clarification questions
- Follow-up instructions
- Modification of existing travel plans
- Inspection of the agent's execution trace

The agent maintains short-term conversation context so users can request changes without starting the planning process again.

##  Example Usage

Try the following request:

```text
Plan a 4-day trip to Goa from Mumbai
for 2 people under ₹60,000.
I like beaches and food.
```

Example follow-up instructions:

- Make it cheaper.
- Extend the trip by 2 days.
- Show me the weather in Goa.
- Suggest more tourist attractions.

You can also enable failure simulation to observe how the agent responds to tool failures.

##  Project Limitations

- Flight information is based on mock/sample data and estimated calculations, not live airline inventory.
- Hotel information comes from locally stored sample data, not live hotel availability.
- Attractions and restaurant recommendations use predefined destination data.
- Weather forecasts depend on API availability and forecast coverage.
- The application provides travel planning and cost estimates; it does not perform actual flight or hotel bookings.
- Currency conversion may use stored rates when the external API is unavailable.

##  Future Improvements

- Integrate live flight search APIs.
- Integrate live hotel booking and availability APIs.
- Add real-time restaurant and attraction search.
- Implement an explicit human approval step before booking-related actions.
- Add user authentication and persistent travel history.
- Improve itinerary personalization using user preferences.
- Deploy the application with Streamlit Community Cloud.

---
 If you find this project interesting, consider giving the repository a star!

**Built with Python, LangGraph, and Agentic AI.**
