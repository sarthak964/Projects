from dotenv import load_dotenv
from langchain_openai import ChatOpenAI

from app.core.config import ACCEPT_WINDOW_HOURS, SUBMIT_WINDOW_HOURS, DISPUTE_WINDOW_DAYS
from app.services.support_state import SupportState, SupportClassification

load_dotenv()

llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)
structured_llm = llm.with_structured_output(SupportClassification)

KNOWN_FACTS = f"""
How TruStay works:
- A renter requests a verification job for a rental property. A reviewer
  physically visits the property, checks it against a checklist, and submits
  a report with notes and photos.
- An AI compares the report against the checklist and either verifies the job
  (if everything was addressed) or flags it as needing the reviewer to
  re-upload more detail (if something was left unaddressed).
- Once the notes are verified, payment remains held during photo review.
  The renter reviews photos, and approval or the applicable deadline releases payment.
  AI checks rejected photos only. Contested cases go through human review and appeals.
- A reviewer has {ACCEPT_WINDOW_HOURS} hours to accept a posted job, and then
  {SUBMIT_WINDOW_HOURS} hours after accepting to visit the property and submit
  their report. If either deadline passes, the job expires automatically and
  any held payment is refunded to the renter.
- Jobs using photo review must use that workflow and its appeal process.
  Legacy disputes are available only for paid jobs with no photo-review record,
  within {DISPUTE_WINDOW_DAYS} days of verification. AI may recommend an outcome,
  but a human makes the financial decision. Never promise an automatic refund.
- A dispute is NOT meant for something that was true at inspection time but
  changed afterward (e.g. normal wear and tear) - that is not grounds for a
  refund of the inspection fee itself.
"""


def classify_support_message_node(state: SupportState) -> dict:
    renter_message = state["renter_message"]
    job_id = state["job_id"]

    prompt = f"""
You are the first line of support for TruStay, a property verification
marketplace. A renter has sent the following message:

"{renter_message}"

Job ID they referenced (may be absent): {job_id}

{KNOWN_FACTS}

Classify what they need and respond accordingly. Only answer FAQ questions
using the facts given above - never invent details about pricing, timelines,
or policy that weren't stated. If their message is a genuine complaint about
something wrong with an inspection/job, classify it as a dispute rather than
answering it yourself - disputes have their own careful review process.
"""

    result: SupportClassification = structured_llm.invoke(prompt)

    return {
        "intent": result.intent,
        "faq_answer": result.faq_answer,
        "dispute_reason": result.dispute_reason,
        "escalation_summary": result.escalation_summary,
    }
