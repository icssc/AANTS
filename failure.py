import aiosmtplib
from email.message import EmailMessage
import config
import boto3

from config import ALERT_NUMBERS

aws = boto3.client(
    "sns",
    aws_access_key_id=config.AWS_ACCESSKEYID,
    aws_secret_access_key=config.AWS_SECRECTKEY,
    region_name="us-east-1"
)

if __name__ == '__main__':
	for num in ALERT_NUMBERS:
		aws.publish(PhoneNumber=f"+1{num}", Message="Dispatcher has failed. Please check logs and restart.")
