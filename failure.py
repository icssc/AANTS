import boto3
import os
from dotenv import load_dotenv

load_dotenv()

aws = boto3.client(
    "sns",
    aws_access_key_id=os.getenv("AWS_ACCESSKEY"),
    aws_secret_access_key=os.getenv("AWS_ACCESSKEY"),
    region_name="us-west-2"
)

alert_number = os.getenv("ALERT_NUMBER")

if __name__ == '__main__':
    aws.publish(PhoneNumber=f"+1{alert_number}", Message="AANTS has crashed. Please check logs and restart.")
