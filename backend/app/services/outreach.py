from ..config import ANTHROPIC_MODEL
from ..llm.client import get_client
from ..models import ScoredLead


def _mock_draft(lead: ScoredLead, channel: str) -> str:
    hook = (
        f"noticed {lead.company_name} is actively hiring"
        if lead.is_hiring
        else f"came across {lead.company_name} in the {lead.industry} space"
    )
    if channel == "linkedin":
        return (
            f"Hi {lead.contact_name or 'there'} — {hook}. Given your team's work with "
            f"{', '.join(lead.tech_stack) or 'your current stack'}, thought it might be "
            f"worth a quick chat about how we could help. Open to connecting?\n\n"
            f"[mock draft — set ANTHROPIC_API_KEY for a real Claude-written draft]"
        )
    return (
        f"Subject: Quick question about {lead.company_name}'s growth plans\n\n"
        f"Hi {lead.contact_name or 'there'},\n\n"
        f"{hook.capitalize()}, and it looked like a strong fit for what we do. "
        f"Companies using {', '.join(lead.tech_stack) or 'a similar stack'} typically see "
        f"the most value from our platform.\n\n"
        f"Worth 15 minutes this week to see if it's relevant for {lead.company_name}?\n\n"
        f"Best,\n[Your name]\n\n"
        f"[mock draft — set ANTHROPIC_API_KEY for a real Claude-written draft]"
    )


def generate_outreach_draft(lead: ScoredLead, channel: str = "email") -> str:
    client = get_client()
    if client is None:
        return _mock_draft(lead, channel)

    prompt = f"""Write a short, personalized first-touch {channel} message to a B2B
sales prospect. Reference specific facts about them rather than generic filler.

Contact: {lead.contact_name or "there"} ({lead.contact_title or "unknown title"})
Company: {lead.company_name}
Industry: {lead.industry}
Tech stack: {", ".join(lead.tech_stack) or "unknown"}
Currently hiring: {lead.is_hiring}
Why they're a fit: {lead.llm_rationale}

Keep it under 120 words, no subject line needed for LinkedIn, include a subject
line for email. No placeholders except [Your name] at the end.
"""
    try:
        response = client.messages.create(
            model=ANTHROPIC_MODEL,
            max_tokens=400,
            messages=[{"role": "user", "content": prompt}],
        )
        return "".join(block.text for block in response.content if block.type == "text").strip()
    except Exception as exc:  # noqa: BLE001
        return f"{_mock_draft(lead, channel)}\n\n(LLM call failed: {exc})"
