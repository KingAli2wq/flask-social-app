"""Convenience exports for service layer."""
from .auth_service import (
    authenticate_user,
    create_access_token,
    decode_access_token,
    get_current_user,
    get_optional_user,
    register_user,
)
from .cleanup_service import CleanupError, CleanupSummary, run_cleanup
from .follow_service import FollowStats, follow_user, get_follow_stats, unfollow_user
from .friendship_service import (
    list_friend_requests,
    list_friends,
    respond_to_request,
    require_friendship,
    send_friend_request,
)
from .media_service import delete_old_media, list_media_for_user
from .message_service import create_group_chat, delete_message, delete_old_messages, list_messages, send_message
from .notification_service import (
    NotificationType,
    add_notification,
    count_unread_notifications,
    delete_old_notifications,
    list_notifications,
    mark_all_read,
)
from .post_service import (
    create_post_comment,
    create_post_record,
    delete_old_posts,
    delete_post_record,
    list_feed_records,
    list_post_comments,
    set_post_like_state,
)
from .profile_service import get_profile, update_profile
from .settings_service import (
    build_settings_response,
    confirm_email_verification,
    request_email_verification,
    update_contact_settings,
    update_password,
    update_preferences,
    update_profile_settings,
)
from .spaces_service import SpacesConfigurationError, SpacesUploadError, get_spaces_client, upload_file_to_spaces

__all__ = [
    "authenticate_user",
    "register_user",
    "create_access_token",
    "decode_access_token",
    "get_current_user",
    "get_optional_user",
    "create_group_chat",
    "delete_message",
    "list_messages",
    "send_message",
    "delete_old_messages",
    "list_friends",
    "list_friend_requests",
    "send_friend_request",
    "respond_to_request",
    "require_friendship",
    "list_media_for_user",
    "delete_old_media",
    "CleanupError",
    "CleanupSummary",
    "run_cleanup",
    "NotificationType",
    "add_notification",
    "count_unread_notifications",
    "list_notifications",
    "mark_all_read",
    "delete_old_notifications",
    "create_post_comment",
    "create_post_record",
    "delete_post_record",
    "delete_old_posts",
    "list_feed_records",
    "list_post_comments",
    "set_post_like_state",
    "FollowStats",
    "follow_user",
    "unfollow_user",
    "get_follow_stats",
    "get_profile",
    "update_profile",
    "build_settings_response",
    "update_profile_settings",
    "update_contact_settings",
    "update_preferences",
    "update_password",
    "request_email_verification",
    "confirm_email_verification",
    "SpacesConfigurationError",
    "SpacesUploadError",
    "get_spaces_client",
    "upload_file_to_spaces",
]
