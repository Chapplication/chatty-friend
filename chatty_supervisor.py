# Chatty Supervisor
# Finley 2025
#
# reasoning model works offline from the assistant/user chat to monitor the conversation and provide:
# - new memories
# - escalations
# - summaries

import jinja2
from chatty_config import get_current_date_string, CONTACT_TYPE_PRIMARY_SUPERVISOR
from chatty_communications import chatty_send_email, chatty_send_sms
import asyncio

SUPERVISOR_SYSTEM_PROMPT = """
## Your task is to examine the transcript of a conversation and produce specific extracts as XML tags.
The conversation is between a human user and an automated companion.  The conversation took place audibly and was transcribed for you.
The purpose of the extracts is to enable the companion to provide deeper and more helpful responses to the user in future conversations, and to follow-up on any specific needs that were raised.
The conversation ends when the user instructs the companion to go to sleep.  It is normal for the user to ask the companion to go to sleep so there is no need to report on that.

The instructions for the companion including the user's profile content at the start of the conversation are provided here.
<companion_instructions>
{{transcript_history[0]["content"]}}
</companion_instructions>

{% if supervisor_instructions_from_user %}
## The following additional extraction instructions are provided for the specific circumstances of the conversation:
<additional_extract_instructions>
{{supervisor_instructions_from_user}}
</additional_extract_instructions>
{% endif %}

{% if escalation_contact_configured %}
{% if prior_pre_escalation_notes %}
## the following notes were extracted from a prior conversation and may be relevant when considering whether the escalation instructions that are detailed below should be followed now:
<prior_pre_escalation_notes>
{% for note in prior_pre_escalation_notes %}
{{note}}
{% endfor %}
</prior_pre_escalation_notes>
{% endif %}
{% endif %}

The most recent conversation between the user and the companion is provided here:
<conversation>
{% for item in transcript_history[1:] %}
{% if item.role == "AI" %}<ChattyFriend>{{item.content}}</ChattyFriend>{% else %}<{{user_name}}>{{item.content}}</{{user_name}}>{% endif %}
{% endfor %}
</conversation>

## Response Format: provide the following extracts between XML tags.  Note that the content for each tag may overlap with other tags, be sure to consider each one and answer fully as though they were being asked in isolation:

{% if summary_email_configured %}
- summary: provide a summary of the conversation for future records.  Aim for 100 words or less, no need to transcribe the turns one by one.
{% endif %}
- profile_extensions: if the user shared additional personal biographical information that was not already included in the <companion_instructions> such as their likes and interests, relatives, pets, upcoming appointments, or other biographical information that would be useful for the companion to receive as part of the user's profile in future conversations, include it here as a series of paragraphs separated by newlines.   These profile entries become permament memories for the assistant so they should be timelss facts rather than cicrumstances that are changing.  No need for transient details or to repeat information that was already included in the <companion_instructions>.
- resume_context: if the companion is reset but the user wants to continue this specific conversation, provide enough context about the end of the last conversation in this tag for the companion to pick up where the conversation left off.  Don't include profile information or instructions here as those will be automatically added for the companion to see.  Aim for 100 words or less.
{% if escalation_contact_configured %}
- escalation: if the user shares concering information that should be escalated to one of the authorized contacts, provide a summary of the escalation here and mention the severity in ALL CAPS from the following list: NONE (no escalation), ROUTINE (escalation will be included in in a periodic summary report), IMPORTANT (escalation will be emailed immediately), URGENT (escalation will be texted to primary escalation contact immediately), CRITICAL (escalaton will be texted to all contacts immediately).

{% if prior_pre_escalation_notes %}
- pre_escalation_notes: add any NEW pre-escalation notes but don't repeat any that were alread noted in <prior_pre_escalation_notes>.  Just say NONE if there are no new pre-escalation notes.
{% else %}
- pre_escalation_notes: if the conversation does not merit escalation now but appears to include precursors that will require escalation in the future, include notes here so they can be taken into account when future conversations are reviewed.  Just say NONE if there are no new pre-escalation notes.
{% endif %}

{% endif %}
- other_points_of_note:

Remember to include the XML tags in your response.  Anything you generate outside of XML tags cannot be processed by policy.

today's date is {{today}}.
"""

response_vars = [
    "summary",
    "profile_extensions",
    "resume_context",
    "escalation",
    "pre_escalation_notes", 
    "other_points_of_note"
]

def format_summary_email(master_state, responses):
    # Format the email content
    subject = f"Chatty Summary for {get_current_date_string(with_time=True)}"
    logs_to_include = master_state.get_logs_for_next_summary()

    if responses["escalation"]:
        subject += " - Escalation"

    # Build HTML content
    html_content = """
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body {
                font-family: Arial, sans-serif;
                line-height: 1.6;
                color: #333;
                max-width: 800px;
                margin: 0 auto;
                padding: 20px;
                background-color: #f4f4f4;
            }
            .container {
                background-color: white;
                border-radius: 10px;
                padding: 30px;
                box-shadow: 0 0 10px rgba(0,0,0,0.1);
            }
            h1 {
                color: #2c3e50;
                border-bottom: 3px solid #3498db;
                padding-bottom: 10px;
            }
            h2 {
                color: #34495e;
                margin-top: 30px;
                border-left: 4px solid #3498db;
                padding-left: 10px;
            }
            .escalation {
                background-color: #fee;
                border: 2px solid #f44336;
                border-radius: 5px;
                padding: 15px;
                margin: 20px 0;
            }
            .escalation h2 {
                color: #c62828;
                border-left-color: #f44336;
            }
            .section {
                background-color: #f8f9fa;
                border-radius: 5px;
                padding: 15px;
                margin: 15px 0;
            }
            .transcript {
                background-color: #f5f5f5;
                border-left: 3px solid #ddd;
                padding: 10px;
                margin: 10px 0;
                font-family: 'Courier New', monospace;
                font-size: 14px;
            }
            .speaker {
                font-weight: bold;
                color: #2c3e50;
            }
            .message {
                margin-left: 20px;
                margin-bottom: 10px;
            }
            .cost {
                background-color: #e8f5e9;
                border: 1px solid #4caf50;
                border-radius: 5px;
                padding: 10px;
                margin-top: 20px;
                text-align: center;
                font-size: 18px;
                font-weight: bold;
                color: #2e7d32;
            }
            .note {
                font-style: italic;
                color: #666;
            }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>Chatty Friend Conversation Summary</h1>
            <p class="note">Generated on {date_time}</p>
            <p>Hello, this is a summary of the most recent conversation with <strong>{user_name}</strong>.</p>
    """

    html_content = html_content.replace("{date_time}", get_current_date_string(with_time=True))
    html_content = html_content.replace("{user_name}", master_state.conman.get_config("USER_NAME"))

    # Add escalation section if present
    if responses["escalation"]:
        html_content += f"""
            <div class="escalation">
                <h2>⚠️ Escalation Required</h2>
                <p>Chatty Friend has determined the need to make the following escalation:</p>
                <p><strong>{responses["escalation"]}</strong></p>
            </div>
        """

    # Add summary section
    html_content += f"""
            <h2>📝 Conversation Summary</h2>
            <div class="section">
                <p>{responses["summary"].replace(chr(10), '<br>')}</p>
            </div>
    """

    # Add other points of note if present
    if responses["other_points_of_note"]:
        html_content += f"""
            <h2>📌 Points of Note</h2>
            <div class="section">
                <p>The following points of note were made by the supervisor reviewing the conversation:</p>
                <p>{responses["other_points_of_note"].replace(chr(10), '<br>')}</p>
            </div>
        """

    # Add profile extensions if present
    if responses["profile_extensions"]:
        html_content += f"""
            <h2>👤 Profile Extensions</h2>
            <div class="section">
                <p>The user shared the following profile extensions with Chatty Friend:</p>
                <p>{responses["profile_extensions"].replace(chr(10), '<br>')}</p>
            </div>
        """

    # Add pre-escalation notes if present
    if responses["pre_escalation_notes"]:
        html_content += f"""
            <h2>📋 Pre-Escalation Notes</h2>
            <div class="section">
                <p class="note">Though not concerning at this time, Chatty Friend made note of the following for future consideration:</p>
                <p>{responses["pre_escalation_notes"].replace(chr(10), '<br>')}</p>
            </div>
        """

    # Add transcript section
    html_content += """
            <h2>💬 Conversation Transcript</h2>
            <div class="section">
                <p>Here is a transcript of the conversation for future reference:</p>
    """

    for item in master_state.transcript_history[1:]:
        speaker = "Chatty Friend" if item["role"] == "AI" else master_state.conman.get_config("USER_NAME")
        message = item["content"].replace('<', '&lt;').replace('>', '&gt;').replace(chr(10), '<br>')
        html_content += f"""
                <div class="transcript">
                    <span class="speaker">{speaker}:</span>
                    <div class="message">{message}</div>
                </div>
        """

    html_content += "</div>"

    # add logs section
    if logs_to_include:
        html_content += f"""
            <h2>💬 Logs</h2>
            <div class="section">
                <p>The following logs were generated during the conversation:</p>
        """
        for log in logs_to_include:
            html_content += f"""
                <div class="log">
                    <p>{log}</p>
                </div>
            """
        html_content += "</div>"

    # Add setup section
    html_content += f"""
            <h2>⚙️ Initial Setup</h2>
            <div class="section">
                <p>The following context was provided to Chatty Friend at the start of the conversation:</p>
                <div class="transcript">
                    {master_state.transcript_history[0]["content"].replace('<', '&lt;').replace('>', '&gt;').replace(chr(10), '<br>')}
                </div>
            </div>
    """

    # Add cost section
    total_cost = sum([u["cost"] for u in master_state.usage_history])
    html_content += f"""
            <div class="cost">
                💰 Total Cost: ${total_cost:.2f}
            </div>
        </div>
    </body>
    </html>
    """

    # Create plain text version as fallback
    plain_text = f"""Hello, this is a summary of the most recent conversation with {master_state.conman.get_config("USER_NAME")}.

    """
    if responses["escalation"]:
        plain_text += f"""------------------------------------
    ESCALATION: {responses["escalation"]}
    ------------------------------------

    """
    plain_text += f"""SUMMARY: {responses["summary"]}

    """
    if responses["other_points_of_note"]:
        plain_text += f"""POINTS OF NOTE: {responses["other_points_of_note"]}

    """
    if responses["profile_extensions"]:
        plain_text += f"""PROFILE EXTENSIONS: {responses["profile_extensions"]}

    """
    if responses["pre_escalation_notes"]:
        plain_text += f"""PRE-ESCALATION NOTES: {responses["pre_escalation_notes"]}

    """
    plain_text += "TRANSCRIPT:\n"
    for item in master_state.transcript_history[1:]:
        speaker = "Chatty Friend" if item["role"] == "AI" else master_state.conman.get_config("USER_NAME")
        plain_text += f"{speaker}: {item['content']}\n"

    plain_text += f"\nSETUP: {master_state.transcript_history[0]['content']}\n"

    if logs_to_include:
        plain_text += "\n\n---------LOGS:\n"
        for log in logs_to_include:
            plain_text += str(log) + "\n"
        plain_text += "\n\n---------LOGS END\n"
    else:
        print("NOLOGS")

    plain_text += f"\nTOTAL COST: ${total_cost:.2f}"


    return subject, html_content, plain_text

async def report_conversation_to_supervisor(master_state):

    if not master_state.transcript_history or not master_state.conman.get_config("SUPERVISOR_MODEL") or not master_state.secrets_manager.get_secret("chat_api_key"):
        return None

    # don't summarize if the user never spoke
    user_message_count = sum(1 for item in master_state.transcript_history if item["role"] == "user")
    if not user_message_count and not master_state.logs_for_next_summary:
        return None

    # make sure we have the latest config
    master_state.conman.load_config()
    supervisor_contact = master_state.conman.get_contact_by_type(CONTACT_TYPE_PRIMARY_SUPERVISOR)

    try:
        # build the prompt
        #
        prompt_vars = {
            "supervisor_instructions_from_user": master_state.conman.get_config("SUPERVISOR_INSTRUCTIONS"),
            "escalation_contact_configured": master_state.secrets_manager.has_escalation_contact_configured(),
            "summary_email_configured": master_state.secrets_manager.has_email_configured() and supervisor_contact,
            "prior_pre_escalation_notes": master_state.conman.get_config("PRIOR_PRE_ESCALATION_NOTES"),
            "transcript_history": master_state.transcript_history,
            "today": get_current_date_string(),
            "user_name": master_state.conman.get_config("USER_NAME")
        }

        supervisor_prompt = jinja2.Template(SUPERVISOR_SYSTEM_PROMPT).render(**prompt_vars)

        # call the supervisor
        retries = 3
        response = None
        while retries > 0:
            retries -= 1
            try:
                response = await master_state.async_openai.responses.create(
                    model=master_state.conman.get_config("SUPERVISOR_MODEL"),
                    reasoning={"effort": "low"},
                    instructions="Objective, precise, with attention to detail.  No flowery language or overly verbose language.",
                    input=supervisor_prompt
                )
                break
            except Exception as e:
                print(f"Error calling supervisor: {e}")

            await asyncio.sleep(1)

        if not response:
            return None

        def parse_response_tag(response, tag):
            start_tag = f"<{tag}>"
            end_tag = f"</{tag}>"
            start_index = response.find(start_tag)
            if start_index == -1:
                return None
            end_index = response.find(end_tag, start_index)
            if end_index == -1:
                return None
            return response[start_index + len(start_tag):end_index].strip()


        responses = {}
        for tag in response_vars:
            responses[tag] = parse_response_tag(response.output_text, tag)

        # handle escalations first in case esceptions in the rest of the processing
        if responses["escalation"] and isinstance(responses["escalation"], str) and responses["escalation"].lower().startswith("none"):
            responses["escalation"] = ""

        if responses["escalation"]:
            escalation = responses["escalation"]
            found_severity = "ROUTINE"
            for severity in ["ROUTINE", "IMPORTANT", "URGENT", "CRITICAL"]:
                if severity in escalation or severity.lower() in escalation.lower():
                    found_severity = severity
                    break
            escalation_contacts = None
            if found_severity=="URGENT":
                escalation_contacts = master_state.conman.get_contact_by_type(CONTACT_TYPE_PRIMARY_SUPERVISOR)
            elif found_severity=="CRITICAL":
                # broadcast to all contacts
                escalation_contacts = master_state.conman.get_contacts()

            if escalation_contacts:
                escalation_message = "Urgent escalation from Chatty Friend for "+master_state.conman.get_config("USER_NAME")+".\n\n"
                escalation_message += "Chatty Friend has determined the need to make the following escalation:\n\n"+escalation[:1000]
                for contact in escalation_contacts:
                    if contact.get("email"):
                        await chatty_send_email(master_state, contact["email"], "Urgent Escalation from Chatty Friend "+get_current_date_string(), escalation_message)
                    if contact.get("phone"):
                        await chatty_send_sms(master_state, contact["phone"], escalation_message[:250])

        # these two tags get the same treatment: break up, add date and push to config
        try:
            max_profile_entries = master_state.conman.get_config("MAX_PROFILE_ENTRIES")
            max_profile_entries = max(int(max_profile_entries), 100)
        except:
            max_profile_entries = 100

        for tag, config_key in [("pre_escalation_notes", "PRIOR_PRE_ESCALATION_NOTES"), ("profile_extensions", "USER_PROFILE")]:
            if not responses[tag] or not isinstance(responses[tag], str) or responses[tag].lower().strip().startswith("none"):
                responses[tag] = ""
                continue
            config_value = master_state.conman.get_config(config_key)
            config_value.extend([get_current_date_string() + ": " + r.strip() for r in responses[tag].split("\n") if r.strip()])
            master_state.conman.save_config({config_key: config_value[-max_profile_entries:]})

        if responses["resume_context"]:
            master_state.conman.save_resume_context(responses["resume_context"])

        if responses["summary"] and supervisor_contact:
            subject, html_summary, plain_summary = format_summary_email(master_state, responses)
            for supervisor in supervisor_contact:
                if supervisor and supervisor.get("email"):
                    await chatty_send_email(master_state, supervisor["email"], subject, plain_summary, html_summary)


    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"Error reporting conversation to supervisor: {e}")
        for supervisor in supervisor_contact:
            if supervisor and supervisor.get("email"):
                await chatty_send_email(master_state, supervisor["email"], "Chatty Friend "+get_current_date_string()+" unable to summarize and escalate", "Please review configuration and try again.  Error: "+str(e))