"""Slack notification when a lead crosses the "hot" threshold.

Posts via slack_sdk when SLACK_BOT_TOKEN + SLACK_CHANNEL_ID are configured;
otherwise (or if the live call fails) just logs and stores the alert
in-memory for the frontend's alerts panel to display.
"""

from loguru import logger
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

from ..config import SLACK_BOT_TOKEN, SLACK_CHANNEL_ID
from ..models import Alert, ScoredLead
from .. import storage

_slack_preflight_done = False


def _preflight_check_slack(client: WebClient) -> None:
    """One-time, best-effort diagnostics so a bad token/scope/uninvited bot
    shows up as one clear log line instead of a generic API error buried
    inside the first real alert send. Never raises -- purely informational,
    the actual post's own try/except still handles the real failure mode.
    """
    global _slack_preflight_done
    if _slack_preflight_done:
        return
    _slack_preflight_done = True

    try:
        auth = client.auth_test()
        logger.info("Slack bot token valid for workspace '{}' as {}", auth.get("team"), auth.get("user"))
    except SlackApiError as exc:
        logger.warning(
            "Slack auth.test failed ({}) — SLACK_BOT_TOKEN is likely invalid/revoked; "
            "alerts will fall back to local-only.",
            exc.response["error"],
        )
        return

    try:
        info = client.conversations_info(channel=SLACK_CHANNEL_ID)
        if not info["channel"].get("is_member", True):
            logger.warning(
                "Slack bot is not a member of channel {} — invite it with "
                "'/invite @<bot-name>' in Slack, or chat.postMessage will fail.",
                SLACK_CHANNEL_ID,
            )
    except SlackApiError as exc:
        logger.warning(
            "Couldn't verify Slack channel {} ({}) — check SLACK_CHANNEL_ID and that "
            "the bot has the channels:read/groups:read scope.",
            SLACK_CHANNEL_ID,
            exc.response["error"],
        )


def _post_to_slack(message: str) -> None:
    client = WebClient(token=SLACK_BOT_TOKEN)
    _preflight_check_slack(client)
    client.chat_postMessage(channel=SLACK_CHANNEL_ID, text=message)


def maybe_alert(lead: ScoredLead) -> Alert | None:
    if lead.bucket != "hot":
        return None

    message = (
        f":fire: Hot lead: *{lead.company_name}* scored {lead.combined_score}/100 "
        f"({lead.industry}, {lead.employee_count} employees). {lead.llm_rationale}"
    )
    alert = Alert(
        lead_id=lead.id,
        company_name=lead.company_name,
        combined_score=lead.combined_score,
        message=message,
    )

    if SLACK_BOT_TOKEN and SLACK_CHANNEL_ID:
        try:
            _post_to_slack(message)
            logger.info("Slack alert posted: {}", message)
        except SlackApiError as exc:
            logger.warning("Slack alert failed, storing locally only: {}", exc.response["error"])
    else:
        logger.info("Slack alert (stub): {}", message)

    storage.add_alert(alert)
    return alert
