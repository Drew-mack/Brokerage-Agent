import boto3


class SESEmailSender:
    """Send HTML email through Amazon SES."""

    def __init__(
        self,
        sender_email: str,
        recipient_email: str,
        aws_region: str = "us-east-2",
        aws_profile: str | None = None,
        sender_name: str = "Portfolio Agent",
    ):
        self.sender_email = sender_email
        self.recipient_email = recipient_email
        self.sender_name = sender_name

        if aws_profile:
            session = boto3.Session(
                profile_name=aws_profile,
                region_name=aws_region,
            )

            self.client = session.client(
                "ses"
            )
        else:
            self.client = boto3.client(
                "ses",
                region_name=aws_region,
            )

    def send(
        self,
        subject: str,
        html: str,
        text: str | None = None,
    ) -> str:
        """Send one portfolio email and return the SES message ID."""

        source = (
            f"{self.sender_name} "
            f"<{self.sender_email}>"
        )

        body = {
            "Html": {
                "Charset": "UTF-8",
                "Data": html,
            }
        }

        if text:
            body["Text"] = {
                "Charset": "UTF-8",
                "Data": text,
            }

        response = self.client.send_email(
            Source=source,
            Destination={
                "ToAddresses": [
                    self.recipient_email
                ]
            },
            Message={
                "Subject": {
                    "Charset": "UTF-8",
                    "Data": subject,
                },
                "Body": body,
            },
        )

        return response["MessageId"]