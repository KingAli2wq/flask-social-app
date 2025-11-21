"""Convenience exports for service layer."""
from .auth_service import (
    authenticate_user,
    create_access_token,
    get_current_user,
    register_user,
)
from .cleanup_service import CleanupError, CleanupSummary, run_cleanup
from .media_service import delete_old_media, list_media_for_user
from .message_service import create_group_chat, delete_old_messages, list_messages, send_message
from .notification_service import add_notification, delete_old_notifications, list_notifications, mark_all_read
from .post_service import create_post_record, delete_old_posts, delete_post_record, list_feed_records
from .profile_service import get_profile, update_profile
from .spaces_service import SpacesUploadError, get_spaces_client, upload_file_to_spaces

__all__ = [
    "authenticate_user",
    "register_user",
    "create_access_token",
    "get_current_user",
    "create_group_chat",
    "list_messages",
    "send_message",
    "delete_old_messages",
    "list_media_for_user",
    "delete_old_media",
    "CleanupError",
    "CleanupSummary",
    "run_cleanup",
    "add_notification",
    "list_notifications",
    "mark_all_read",
    "delete_old_notifications",
    "create_post_record",
    "delete_post_record",
    "delete_old_posts",
    "list_feed_records",
    "get_profile",
    "update_profile",
    "SpacesUploadError",
    "get_spaces_client",
    "upload_file_to_spaces",
]
