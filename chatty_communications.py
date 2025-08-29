import smtplib
from email.mime.text import MIMEText
from twilio.rest import Client as TwilioClient
from email.mime.multipart import MIMEMultipart

async def chatty_send_email(master_state, recipient, subject, content, html_content=None):
    # Get email settings from secrets manager
    smtp_server = master_state.secrets_manager.get_secret('email_smtp_server', 'smtp.gmail.com')
    smtp_port = int(master_state.secrets_manager.get_secret('email_smtp_port', '587'))
    username = master_state.secrets_manager.get_secret('email_username')
    password = master_state.secrets_manager.get_secret('email_password')
    
    if not all([username, password, smtp_server, smtp_port, recipient]):
        print("Email service not configured. Please configure email credentials.")
        return

    if not html_content:
        msg = MIMEText(content.encode('utf-8'), _charset='utf-8')
        msg['Subject'] = subject.encode('utf-8').decode('ascii','ignore')
        msg['From'] = username
        msg['To'] = master_state.secrets_manager.get_secret('email_recipient')

        #Connect to SMTP Server
        session = smtplib.SMTP(smtp_server, smtp_port)
        session.ehlo()
        session.starttls()
        session.ehlo()

        #Login to email service
        session.login(username, password)

        #Send Email & Exit
        session.sendmail(username, recipient, msg.as_string())
        session.quit()
    else:
        # Create the email message
        msg = MIMEMultipart('alternative')
        msg['Subject'] = subject
        msg['From'] = username
        msg['To'] = master_state.secrets_manager.get_secret('email_recipient')

        # Attach both versions
        part1 = MIMEText(content, 'plain', 'utf-8')
        part2 = MIMEText(html_content, 'html', 'utf-8')

        msg.attach(part1)
        msg.attach(part2)

        # Send the email
        session = smtplib.SMTP(smtp_server, smtp_port)
        session.ehlo()
        session.starttls()
        session.ehlo()
        session.login(username, password)
        session.sendmail(username, recipient, msg.as_string())
        session.quit()

    print("EMAIL DONE")




async def chatty_send_sms(master_state, recipient, message):

    client = TwilioClient(master_state.secrets_manager.get_secret('twilio_account_sid'), master_state.secrets_manager.get_secret('twilio_auth_token'))
    
    message = client.messages.create(
        body=message,
        from_=master_state.secrets_manager.get_secret('twilio_phone_number'),
        to=recipient
    )
    return True, message.sid
