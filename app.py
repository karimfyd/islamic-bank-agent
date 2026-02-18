import os
import markdown
import json
import time
from flask import Flask, render_template, request, Response
from openai import OpenAI
from dotenv import load_dotenv
import concurrent.futures

load_dotenv()

app = Flask(__name__)
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

DEFAULT_CONTEXT = """Title:
Digital & Growth Transformation Strategy for a GCC Islamic Bank

📖 Storyline
Al Noor Islamic Bank is a 30-year-old Shariah-compliant retail and SME bank headquartered in the GCC, with operations across the UAE, Saudi Arabia, and Qatar.

Historically, the bank built its reputation on:

Strong personal banking relationships

Conservative risk management

SME financing

Physical branch dominance

However, the regional banking landscape is rapidly evolving:

Governments are accelerating Vision 2030–style national transformation agendas

Open banking regulations are being introduced

Fintech startups are attracting younger customers

Digital wallets and super apps are gaining traction

Customers expect fully digital Shariah-compliant products

ESG and sustainable finance are becoming strategic priorities

Additionally:

The bank’s cost-to-income ratio has increased to 58%

Customer acquisition among under-35s has dropped by 20%

Core banking systems are legacy and fragmented

Employee productivity varies significantly across markets

The Board has engaged a leading consulting firm to design a 3-year transformation strategy that balances:

Digital acceleration

Operational efficiency

Regulatory compliance

Islamic finance principles

Sustainable growth"""

PROMPTS = {
    "market_analyst": """You are a senior market analyst specialised in GCC financial services. Based on the context provided, write the "Market & Strategic Context" section of a transformation proposal. Include: GCC banking competition, regulatory shifts, customer behaviour shifts, Islamic banking growth trends, and impact of national transformation programmes. Use markdown headings and bullet points.""",
    "problem_analyst": """You are a strategy consultant. Based on the context, write the "Key Problem Areas" section. Structure it into Strategic, Operational, Technology, and Talent & Organisation sub‑sections. Be specific and use the data given (cost‑to‑income 58%, youth acquisition drop 20%, etc.).""",
    "strategy_architect": """You are a transformation expert. Write the "Proposed Consulting Approach" section, detailing the three phases (Diagnostic, Strategy Design, Implementation) with deliverables. Use the suggested timeline (8‑10 weeks for phase 1) and be precise.""",
    "financial_analyst": """You are a financial analyst. Write the "Financial & Strategic Impact" section. Estimate cost reduction potential (e.g., 10‑15% opex savings), revenue uplift, cost‑to‑income improvement, market share growth, and NPS improvement. Base on reasonable assumptions and the bank's current figures.""",
    "risk_specialist": """You are a risk management expert. Write the "Risks & Mitigation" section. Consider regional realities: regulatory delays, Shariah compliance, cultural resistance, talent scarcity, macroeconomic volatility. Propose mitigation strategies. Use a table if helpful.""",
    "editor": """You are a lead consultant. Combine the following sections written by your team into one cohesive proposal. Ensure the flow is logical, language is professional, and there is no duplication. The final output must have exactly these seven headings: 1. Executive Summary, 2. Market & Strategic Context, 3. Key Problem Areas, 4. Proposed Consulting Approach, 5. Value Proposition of Your Consulting Firm, 6. Financial & Strategic Impact, 7. Risks & Mitigation. You will receive sections 2‑6 from your team; you must also write the Executive Summary (section 1) and the Value Proposition (section 5) yourself, based on the overall content. Then assemble everything into a single markdown document."""
}

def call_agent(role, context):
    messages = [
        {"role": "system", "content": PROMPTS[role]},
        {"role": "user", "content": f"Context:\n{context}\n\nPlease provide your section."}
    ]
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=messages,
        temperature=0.7,
        max_tokens=2000
    )
    return response.choices[0].message.content

def summarize_section(agent_name, section_text):
    """Generate a one-line summary of an agent's section."""
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "Summarize the following section in one concise sentence (max 15 words)."},
                {"role": "user", "content": section_text[:1000]}
            ],
            temperature=0.3,
            max_tokens=30
        )
        return response.choices[0].message.content.strip()
    except Exception:
        return f"{agent_name} completed."

@app.route('/')
def index():
    return render_template('index.html', default_context=DEFAULT_CONTEXT)

@app.route('/generate_agentic_stream', methods=['GET'])
def generate_agentic_stream():
    context = request.args.get('context', DEFAULT_CONTEXT)

    def event_stream():
        agents = ["market_analyst", "problem_analyst", "strategy_architect", "financial_analyst", "risk_specialist"]
        agent_names = {
            "market_analyst": "Market Analyst",
            "problem_analyst": "Problem Analyst",
            "strategy_architect": "Strategy Architect",
            "financial_analyst": "Financial Analyst",
            "risk_specialist": "Risk Specialist"
        }

        # Send start events
        for agent in agents:
            yield f"event: status\ndata: {json.dumps({'agent': agent_names[agent], 'status': 'started'})}\n\n"
            time.sleep(0.2)

        # Run specialists in parallel
        with concurrent.futures.ThreadPoolExecutor() as executor:
            futures = {
                executor.submit(call_agent, agent, context): agent
                for agent in agents
            }
            results = {}
            for future in concurrent.futures.as_completed(futures):
                agent = futures[future]
                try:
                    section = future.result()
                    results[agent] = section
                    yield f"event: status\ndata: {json.dumps({'agent': agent_names[agent], 'status': 'finished'})}\n\n"
                    # Generate and send summary
                    summary = summarize_section(agent_names[agent], section)
                    yield f"event: summary\ndata: {json.dumps({'agent': agent_names[agent], 'summary': summary})}\n\n"
                except Exception as e:
                    yield f"event: error\ndata: {json.dumps({'error': str(e)})}\n\n"
                    return

        # Prepare combined sections for editor
        combined_sections = f"""
## Market & Strategic Context
{results['market_analyst']}

## Key Problem Areas
{results['problem_analyst']}

## Proposed Consulting Approach
{results['strategy_architect']}

## Financial & Strategic Impact
{results['financial_analyst']}

## Risks & Mitigation
{results['risk_specialist']}
"""

        # Start editor with streaming
        yield f"event: status\ndata: {json.dumps({'agent': 'Editor', 'status': 'started'})}\n\n"

        messages = [
            {"role": "system", "content": PROMPTS["editor"]},
            {"role": "user", "content": f"Context:\n{context}\n\nSections from team:\n{combined_sections}\n\nPlease produce the final proposal."}
        ]

        stream = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages,
            temperature=0.7,
            max_tokens=4000,
            stream=True
        )

        full_response = ""
        for chunk in stream:
            if chunk.choices[0].delta.content:
                token = chunk.choices[0].delta.content
                full_response += token
                yield f"event: token\ndata: {json.dumps({'token': token})}\n\n"

        yield f"event: status\ndata: {json.dumps({'agent': 'Editor', 'status': 'finished'})}\n\n"
        html_full = markdown.markdown(full_response, extensions=['extra'])
        yield f"event: done\ndata: {json.dumps({'html': html_full})}\n\n"

    return Response(event_stream(), mimetype="text/event-stream")

if __name__ == '__main__':
    app.run(debug=True, threaded=True)