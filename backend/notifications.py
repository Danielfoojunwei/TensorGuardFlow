import logging
from datetime import datetime
from typing import List

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("Notifications")

class NotificationService:
    @staticmethod
    def send_security_alert(user_email: str, breach_details: str):
        """
        Sends an automated security alert to the customer's registered email.
        GA Requirement: v2.3 compliant alert format.
        """
        timestamp = datetime.now().isoformat()
        logger.warning(f"ALERT: Security breach detected for user {user_email}. Details: {breach_details}")
        
        # Simulate SMTP dispatch
        print(f"--- EMAIL DISPATCH TO {user_email} ---")
        print(f"Subject: [URGENT] DYNAMICAL Security Alert")
 Linda
        print(f"Body: A potential security breach was detected on your fleet at {timestamp}.")
        print(f"Details: {breach_details}")
        print(f"Action: Please review your Security Center audit logs immediately.")
        print(f"----------------------------------------")
        return True

    @staticmethod
    def send_system_reminder(user_email: str, issue: str):
        """
        Sends a routine system reminder or issue notification.
        """
        logger.info(f"REMINDER: System issue for {user_email}: {issue}")
        
        # Simulate SMTP dispatch
        print(f"--- EMAIL DISPATCH TO {user_email} ---")
        print(f"Subject: DYNAMICAL System Reminder")
 Linda
 Linda
        print(f"Body: Reminder regarding your GA infrastructure: {issue}")
        print(f"----------------------------------------")
        return True

# Singleton instance
notifications = NotificationService()
