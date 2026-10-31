from dotenv import load_dotenv
from langchain_openai import ChatOpenAI

from app.services.dispute_state import DisputeState, DisputeAnalysisOutput

load_dotenv()

llm = ChatOpenAI(model="gpt-4o-mini")
structured_llm = llm.with_structured_output(DisputeAnalysisOutput)


def analyze_dispute_node(state: DisputeState) -> dict:
    checklist = state["checklist"]
    original_notes = state["original_notes"]
    original_verification_result = state["original_verification_result"]
    renter_reason = state["renter_reason"]
    renter_evidence_urls = state["renter_evidence_urls"]

    prompt = f"""
You are adjudicating a dispute on a property inspection/verification marketplace.

A reviewer previously visited a property and submitted a report, which was
then AI-verified against a checklist. Now, after moving in, the renter is
disputing that original report.

Checklist that was supposed to be verified:
{checklist}

Reviewer's original notes from the visit:
{original_notes}

Original AI verification result (per checklist item):
{original_verification_result}

Renter's complaint:
{renter_reason}

Renter's evidence (references provided by the renter, e.g. photo/video URLs):
{renter_evidence_urls}

Decide whether this complaint should result in a REFUND to the renter, or
whether the original report should be UPHELD (no refund).

Important principles:
- The original report is a record of what was true AT THE TIME OF INSPECTION,
  not a guarantee about the future. If the complaint is plausibly about
  something that broke or changed after a correct inspection (normal wear,
  later damage), that is NOT grounds for a refund - the original report did
  its job. Lean towards UPHOLD with LOW confidence in that case, so a human
  reviews it rather than the system guessing.
- A refund is appropriate when the renter's complaint and evidence genuinely
  contradict what the original report claimed about the SAME condition at
  the SAME time - i.e. there's a real reason to believe the original report
  was inaccurate or dishonest.
- Only give HIGH confidence (above 0.8) when the case is clear-cut either way.
  Any genuine ambiguity, missing evidence, or plausible "broke after the fact"
  explanation should get a LOW confidence score so a human adjudicates instead.
"""

    result: DisputeAnalysisOutput = structured_llm.invoke(prompt)

    return {
        "recommended_outcome": result.recommended_outcome,
        "confidence": result.confidence,
        "reasoning": result.reasoning,
    }
