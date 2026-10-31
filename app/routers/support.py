from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.auth import require_roles
from app.core.database import get_db
from app.models.user import User, UserRole
from app.models.job import Job
from app.services.job_lifecycle import check_and_expire_job
from app.models.dispute import DisputeStatus
from app.models.support_ticket import SupportTicket
from app.schemas.support import SupportChatRequest, SupportChatResponse
from app.schemas.dispute import DisputeCreate
from app.services.support_graph import support_graph
from app.routers.dispute import file_dispute, triage_dispute

router = APIRouter(prefix="/support", tags=["support"])

JOB_STATUS_MESSAGES = {
    "requested": "Your job is posted and waiting for a reviewer to accept it.",
    "accepted": "A reviewer has accepted your job and will visit the property soon.",
    "visited": "The reviewer has visited the property and should submit their report shortly.",
    "report_submitted": "The reviewer's report has been submitted and is being verified.",
    "verified": "The notes have been checked. Check the photo-review page for the current action and deadline. Payment follows that review process.",
    "needs_reupload": "The reviewer's report was incomplete on some checklist items, and they have been asked to provide more detail.",
    "paid": "This job is complete and the reviewer has been paid.",
    "expired": "This job expired because a reviewer did not act in time. Any held payment has been automatically refunded.",
    "disputed": "This job has an open dispute currently being reviewed.",
    "refunded": "This job was refunded following a dispute.",
}


@router.post("/chat", response_model=SupportChatResponse)
def support_chat(
    chat_in: SupportChatRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.renter)),
):
    owned_job = None
    if chat_in.job_id is not None:
        owned_job = db.query(Job).filter(Job.id == chat_in.job_id).first()
        if owned_job is None or owned_job.renter_id != current_user.id:
            raise HTTPException(status_code=404, detail="Job not found on your account")
        owned_job = check_and_expire_job(owned_job, db)

    graph_input = {
        "renter_message": chat_in.message,
        "job_id": chat_in.job_id,
        "intent": "",
        "faq_answer": None,
        "dispute_reason": None,
        "escalation_summary": None,
    }

    try:
        final_state = support_graph.invoke(graph_input)
    except Exception:
        raise HTTPException(
            status_code=502, detail="Support is temporarily unavailable. Please retry."
        ) from None
    intent = final_state["intent"]

    if intent == "faq":
        reply = final_state["faq_answer"] or (
            "I don't have a confident answer to that - let me pass it to our team."
        )
        return SupportChatResponse(intent=intent, reply=reply)

    if intent == "status_check":
        if chat_in.job_id is None:
            return SupportChatResponse(
                intent=intent,
                reply="Sure - which job would you like me to check? Please share the job ID.",
            )

        job = db.query(Job).filter(Job.id == chat_in.job_id).first()
        if not job or job.renter_id != current_user.id:
            return SupportChatResponse(
                intent=intent,
                reply="I couldn't find a job with that ID on your account.",
            )

        status_text = JOB_STATUS_MESSAGES.get(
            job.status.value, f"This job's current status is '{job.status.value}'."
        )
        return SupportChatResponse(intent=intent, reply=status_text)

    if intent == "dispute":
        if chat_in.job_id is None:
            return SupportChatResponse(
                intent=intent,
                reply="I'm sorry to hear that. Which job is this about? Please share the job ID so I can file this properly.",
            )

        dispute_in = DisputeCreate(
            job_id=chat_in.job_id,
            reason=final_state["dispute_reason"] or chat_in.message,
            evidence_urls=None,
        )

        try:
            dispute = file_dispute(dispute_in, db, current_user)
        except HTTPException as exc:
            return SupportChatResponse(intent=intent, reply=exc.detail)

        try:
            dispute = triage_dispute(dispute.id, db, current_user)
        except HTTPException as exc:
            return SupportChatResponse(
                intent=intent,
                reply=f"I've filed this as dispute #{dispute.id}, but hit an issue reviewing it automatically: {exc.detail}. Our team will follow up.",
                dispute_id=dispute.id,
            )

        if dispute.status == DisputeStatus.ai_resolved:
            reply = (
                f"I've reviewed this and resolved it: {dispute.resolution_outcome.value}. "
                f"{dispute.resolution_notes}"
            )
        else:
            reply = (
                f"I've filed this as dispute #{dispute.id}. This one needs a closer look, "
                "so I've passed it to our team - they'll make the final call."
            )

        return SupportChatResponse(intent=intent, reply=reply, dispute_id=dispute.id)

    # intent == "escalate" (or anything unexpected, as a safe fallback)
    ticket = SupportTicket(
        renter_id=current_user.id,
        job_id=chat_in.job_id,
        message=chat_in.message,
        ai_summary=final_state["escalation_summary"],
    )
    db.add(ticket)
    db.commit()
    db.refresh(ticket)

    return SupportChatResponse(
        intent="escalate",
        reply="I've passed this on to our support team - they will get back to you shortly.",
        ticket_id=ticket.id,
    )
