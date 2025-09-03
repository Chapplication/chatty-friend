from .llm_tool_base import LLMTool, LLMToolParameter
from chatty_communications import chatty_send_email, chatty_send_sms
from chatty_config import CONTACT_TYPE_PRIMARY_SUPERVISOR

class CommunicationTool(LLMTool):
    def __init__(self, master_state):
        contacts = master_state.conman.get_contacts()
        contact_names = [contact["name"] for contact in contacts]
        if contact_names:
            recipient = LLMToolParameter("recipient", "Contact name from the address book", enum=contact_names, required=True)
        else:
            recipient = None
        subject = LLMToolParameter("subject", "Message subject or title")  
        message = LLMToolParameter("message", "Message content to send")
        priority = LLMToolParameter("priority", "Delivery method: 'urgent'=immediate SMS, 'high'=SMS preferred, 'medium'/'low'=email only", enum=["low", "medium", "high", "urgent"])
        
        super().__init__("communication_tool",
                         "Use this tool to send notifications to contacts via email or SMS when directly asked or in response to a need to escalate events communicated by the user.", 
                         [recipient, subject, message, priority] if recipient else [subject, message, priority],
                         master_state)

    async def invoke(self, args):
        try:
            recipient = args.get("recipient", "").strip()
            subject = args.get("subject", "").strip()
            message = args.get("message", "").strip()
            priority = args.get("priority", "").strip().lower()

            if not recipient:
                primary_contact = self.master_state.conman.get_contact_by_type(CONTACT_TYPE_PRIMARY_SUPERVISOR)
                if primary_contact:
                    recipient = primary_contact[0]["name"]
                else:
                    contact_names = [contact["name"] for contact in self.master_state.conman.get_contacts()]
                    if contact_names:
                        recipient = contact_names[0]

            recipient_contact = self.master_state.conman.get_contact_by_name(recipient.lower().strip())
            if not recipient_contact:
                return f"Contact '{recipient}' not found. No way to reach them.  Check configuration - make sure spelling is correct and they are in the address book."
            
            if not message:
                if subject:
                    message = subject

            if not subject:
                if message:
                    subject = message[:50]+"..."

            if not priority or priority not in ["low", "medium", "high", "urgent"]:
                priority = "urgent"

            if not message and not subject:
                subject = "Chatty Friend message from "+self.master_state.conman.get_config("USER_NAME")
                message = self.master_state.conman.get_config("USER_NAME")+" sent you an empty message."

            if priority in ["urgent","high"] and recipient_contact["phone"]:
                message = priority.upper()+" from "+self.master_state.conman.get_config("USER_NAME")+": "+message
                await chatty_send_sms(self.master_state, recipient_contact["phone"], message)
            else:
                subject = priority.upper()+" from "+self.master_state.conman.get_config("USER_NAME")+" - "+subject
                await chatty_send_email(self.master_state, recipient_contact["email"], subject, message)

            return f"Message sent to {recipient_contact['name']} via {priority} priority."

        except Exception as e:
            import traceback
            traceback.print_exc()
            return f"Could not send communication!!"