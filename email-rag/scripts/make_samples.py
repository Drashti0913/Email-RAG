"""Generate deterministic synthetic MIME fixtures. No real personal information."""
from email.message import EmailMessage
from email import policy
from pathlib import Path
import mailbox

ROOT = Path(__file__).resolve().parents[1] / 'sample_data'


def make(user, name, sender, subject, date, body, attachment=None, html=False):
    msg = EmailMessage(policy=policy.SMTP)
    msg['Message-ID'] = f'<{name}@example.test>'
    msg['From'] = sender
    msg['To'] = f'{user.title()} <{user}@example.test>'
    msg['Subject'] = subject
    msg['Date'] = date
    msg.set_content(body)
    if html:
        msg.add_alternative('<html><body><p>' + body + '</p><script>ignore me</script></body></html>', subtype='html')
    if attachment:
        filename, text = attachment
        msg.add_attachment(text.encode(), maintype='text', subtype='csv' if filename.endswith('.csv') else 'plain', filename=filename)
    path = ROOT / user / (name + '.eml')
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(msg.as_bytes())
    return msg


def main():
    make('alice','a01-budget','Sarah Chen <sarah@example.test>','Q4 budget approval',
         'Mon, 14 Sep 2026 09:00:00 -0400',
         'The approved Q4 budget is $120,000. Allocate $70,000 to engineering and $50,000 to marketing. Please freeze spending plans by September 25.',
         ('q4-budget.csv','department,amount_usd\nengineering,70000\nmarketing,50000\ncontingency_included_in_engineering,5000\n'))
    make('alice','a02-api','Dev Patel <dev@example.test>','API integration project kickoff',
         'Tue, 15 Sep 2026 10:00:00 -0400',
         'The API integration project will use OAuth 2.0. Priya owns the connector. Staging integration is due October 8. The attached checklist contains retry requirements.',
         ('api-checklist.txt','API retry policy: exponential backoff with jitter, at most 5 retries. HTTP 429 and 503 are retryable. Idempotency keys are required on POST requests.'))
    make('alice','a03-marketing','Marketing Team <marketing@example.test>','Marketing team weekly update',
         'Fri, 18 Sep 2026 15:00:00 -0400','The marketing team has completed draft launch messaging.',html=True)
    make('alice','a04-launch','Maya Ross <maya@example.test>','Product launch - original plan',
         'Mon, 21 Sep 2026 11:00:00 -0400','The product launch was planned for October 15. Maya owns launch coordination. A security review is still pending.')
    make('alice','a05-launch-update','Maya Ross <maya@example.test>','Re: Product launch - revised plan',
         'Thu, 24 Sep 2026 11:00:00 -0400','The product launch is moved to October 22 because the security review needs an extra week. This replaces the October 15 plan.')
    make('alice','a06-marketing-latest','Marketing Team <marketing@example.test>','Marketing team final campaign update',
         'Wed, 30 Sep 2026 16:30:00 -0400','The marketing team approved the email campaign for the October 22 product launch. Campaign owner: Elena. Landing page review is due October 5.')
    make('alice','a07-lunch','Chris <chris@example.test>','Friday lunch',
         'Wed, 30 Sep 2026 12:00:00 -0400','Lunch is at noon at the office cafe. Please bring your own mug.')
    make('bob','b01-private','Finance <finance@example.test>','Orion acquisition confidential',
         'Tue, 22 Sep 2026 10:00:00 -0400','The private Orion acquisition code is COBALT-731. The acquisition budget is $9,300,000. This message belongs only to Bob.')
    make('bob','b02-budget','Sarah Chen <sarah@example.test>','Q4 budget approval',
         'Wed, 23 Sep 2026 09:00:00 -0400','Bob, your Q4 budget is $42,000. Allocate $30,000 to research and $12,000 to operations.')
    make('bob','b03-api','Leo <leo@example.test>','API integration project',
         'Thu, 24 Sep 2026 09:00:00 -0400','Bob owns the internal API integration, due November 2. Use service account credentials for the internal staging system.')
    boxpath = ROOT / 'alice.mbox'
    boxpath.unlink(missing_ok=True)
    box = mailbox.mbox(boxpath)
    for file in sorted((ROOT/'alice').glob('*.eml')):
        box.add(mailbox.mboxMessage(file.read_bytes()))
    box.flush()
    box.close()


if __name__ == '__main__':
    main()
