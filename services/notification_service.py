"""
Notification Service for Ethiosadat Furniture
Stub implementation — push/email notifications are not configured.
All functions return False (no-op) so the rest of the app works normally.
"""


class NotificationService:
    """Stub notification service."""

    @staticmethod
    def send_push_notification(title, body, data=None, target='all', user_id=None):
        return False

    @staticmethod
    def send_email_notification(to_email, subject, body, html_body=None):
        return False

    @staticmethod
    def send_order_notification(order_id, status):
        return False

    @staticmethod
    def send_admin_alert(title, body):
        return False


def send_push_notification(title, body, data=None, target='all', user_id=None):
    """No-op push notification — not configured."""
    return False


def send_email_notification(to_email, subject, body, html_body=None):
    """No-op email notification — not configured."""
    return False
