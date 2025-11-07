"""
UI Components Module - Isolated, Reusable Components
====================================================
Component-based architecture to prevent flickering by only updating changed components.
Each component manages its own state and only re-renders when its specific data changes.
"""

from __future__ import annotations
from typing import Any, Callable, Optional, TYPE_CHECKING
from dataclasses import dataclass
import customtkinter as ctk
import hashlib
import json

if TYPE_CHECKING:
    from tkinter import PhotoImage


@dataclass
class ComponentState:
    """Track component state to prevent unnecessary re-renders"""
    signature: str = ""
    last_render_time: float = 0.0
    widget: Optional[Any] = None
    data_snapshot: Any = None


class BaseComponent:
    """Base class for all UI components with smart update detection"""
    
    def __init__(self, component_id: str):
        self.component_id = component_id
        self.state = ComponentState()
        self._mounted = False
        
    def compute_signature(self, data: Any) -> str:
        """Generate unique signature for component data"""
        try:
            serialized = json.dumps(data, sort_keys=True, ensure_ascii=False, default=str)
        except (TypeError, ValueError):
            serialized = repr(data)
        return hashlib.sha1(serialized.encode("utf-8", "ignore")).hexdigest()[:16]
    
    def should_update(self, new_data: Any) -> bool:
        """Determine if component needs re-rendering"""
        new_signature = self.compute_signature(new_data)
        if new_signature != self.state.signature:
            self.state.signature = new_signature
            self.state.data_snapshot = new_data
            return True
        return False
    
    def mount(self, container: ctk.CTkFrame) -> None:
        """Initial component mount"""
        self._mounted = True
        
    def unmount(self) -> None:
        """Cleanup when component is removed"""
        if self.state.widget and hasattr(self.state.widget, 'destroy'):
            self.state.widget.destroy()
        self._mounted = False
        
    def update(self, data: Any) -> None:
        """Update component only if data changed"""
        if self.should_update(data):
            self.render(data)
            
    def render(self, data: Any) -> None:
        """Override in subclasses to implement rendering logic"""
        raise NotImplementedError


# ============================================================================
# MESSAGE COMPONENTS (For DM System)
# ============================================================================

class SingleMessageComponent(BaseComponent):
    """Individual message item - only updates when this message changes"""
    
    def __init__(self, message_id: str, palette: dict[str, str]):
        super().__init__(f"message_{message_id}")
        self.message_id = message_id
        self.palette = palette
        self.container: Optional[ctk.CTkFrame] = None
        
    def render(self, message_data: dict[str, Any]) -> None:
        """Render single message without affecting others"""
        if not self.container:
            return
            
        # Clear only this message's widgets if they exist
        if self.state.widget:
            self.state.widget.destroy()
            
        sender = message_data.get("sender", "Unknown")
        content = message_data.get("content", "")
        timestamp = message_data.get("time", "")
        is_own = message_data.get("is_own", False)
        
        # Create message bubble
        msg_frame = ctk.CTkFrame(
            self.container,
            fg_color=self.palette.get("accent", "#4c8dff") if is_own else self.palette.get("card", "#18263f"),
            corner_radius=12
        )
        msg_frame.pack(
            anchor="e" if is_own else "w",
            padx=(60 if is_own else 10, 10 if is_own else 60),
            pady=4,
            fill="x"
        )
        
        # Sender label (only for received messages)
        if not is_own:
            ctk.CTkLabel(
                msg_frame,
                text=f"@{sender}",
                text_color=self.palette.get("accent", "#4c8dff"),
                font=ctk.CTkFont(weight="bold", size=12),
                anchor="w"
            ).pack(anchor="w", padx=12, pady=(8, 0))
        
        # Message content
        ctk.CTkLabel(
            msg_frame,
            text=content,
            text_color="white" if is_own else self.palette.get("text", "#e2e8f0"),
            wraplength=400,
            justify="left",
            anchor="w"
        ).pack(anchor="w", padx=12, pady=(4 if not is_own else 8, 4))
        
        # Timestamp
        ctk.CTkLabel(
            msg_frame,
            text=timestamp,
            text_color=self.palette.get("muted", "#94a3b8"),
            font=ctk.CTkFont(size=9),
            anchor="w"
        ).pack(anchor="w", padx=12, pady=(0, 6))
        
        self.state.widget = msg_frame
        

class MessageListComponent(BaseComponent):
    """Message list container - only adds/updates changed messages"""
    
    def __init__(self, palette: dict[str, str]):
        super().__init__("message_list")
        self.palette = palette
        self.message_components: dict[str, SingleMessageComponent] = {}
        self.container: Optional[ctk.CTkScrollableFrame] = None
        
    def mount(self, container: ctk.CTkScrollableFrame) -> None:
        """Mount the message list"""
        super().mount(container)
        self.container = container
        
    def update(self, messages: list[dict[str, Any]]) -> None:
        """Efficiently update only changed messages"""
        if not self.container:
            return
            
        # Create signature based on message IDs and content
        message_signatures = [
            (msg.get("id"), self.compute_signature(msg)) 
            for msg in messages
        ]
        
        current_ids = set(comp.message_id for comp in self.message_components.values())
        new_ids = set(msg.get("id") for msg in messages if msg.get("id"))
        
        # Remove deleted messages
        removed_ids = current_ids - new_ids
        for msg_id in removed_ids:
            if msg_id in self.message_components:
                self.message_components[msg_id].unmount()
                del self.message_components[msg_id]
        
        # Update or create messages
        for message in messages:
            msg_id = message.get("id")
            if not msg_id:
                continue
                
            if msg_id not in self.message_components:
                # Create new message component
                component = SingleMessageComponent(msg_id, self.palette)
                component.container = self.container
                self.message_components[msg_id] = component
                component.render(message)
            else:
                # Update existing message only if changed
                component = self.message_components[msg_id]
                component.update(message)


# ============================================================================
# NOTIFICATION COMPONENTS
# ============================================================================

class SingleNotificationComponent(BaseComponent):
    """Individual notification item"""
    
    def __init__(self, notification_id: str, palette: dict[str, str], on_click: Optional[Callable] = None):
        super().__init__(f"notification_{notification_id}")
        self.notification_id = notification_id
        self.palette = palette
        self.on_click = on_click
        self.container: Optional[ctk.CTkFrame] = None
        
    def render(self, notification_data: dict[str, Any]) -> None:
        """Render single notification"""
        if not self.container:
            return
            
        if self.state.widget:
            self.state.widget.destroy()
            
        message = notification_data.get("message", "")
        timestamp = notification_data.get("time", "")
        meta = notification_data.get("meta", {})
        is_clickable = bool(meta.get("type"))
        
        # Notification card
        card = ctk.CTkFrame(
            self.container,
            corner_radius=12,
            fg_color=self.palette.get("card", "#18263f")
        )
        card.pack(fill="x", padx=0, pady=6)
        
        # Message text
        message_label = ctk.CTkLabel(
            card,
            text=message,
            wraplength=580,
            justify="left",
            text_color=self.palette.get("accent", "#4c8dff") if is_clickable else self.palette.get("text", "#e2e8f0")
        )
        message_label.pack(anchor="w", padx=16, pady=(12, 4))
        
        if is_clickable and self.on_click:
            message_label.configure(cursor="hand2")
            message_label.bind("<Button-1>", lambda e: self.on_click(notification_data))
        
        # Timestamp
        ctk.CTkLabel(
            card,
            text=timestamp,
            text_color=self.palette.get("muted", "#94a3b8"),
            font=ctk.CTkFont(size=10)
        ).pack(anchor="w", padx=16, pady=(0, 12))
        
        self.state.widget = card


class NotificationListComponent(BaseComponent):
    """Notification list - only updates changed notifications"""
    
    def __init__(self, palette: dict[str, str], on_notification_click: Optional[Callable] = None):
        super().__init__("notification_list")
        self.palette = palette
        self.on_notification_click = on_notification_click
        self.notification_components: dict[str, SingleNotificationComponent] = {}
        self.container: Optional[ctk.CTkScrollableFrame] = None
        
    def mount(self, container: ctk.CTkScrollableFrame) -> None:
        super().mount(container)
        self.container = container
        
    def update(self, notifications: list[dict[str, Any]]) -> None:
        """Efficiently update only changed notifications"""
        if not self.container:
            return
            
        # Use timestamp + message as ID since notifications might not have IDs
        notification_keys = []
        for idx, notif in enumerate(notifications):
            key = f"{notif.get('time', '')}_{notif.get('message', '')[:50]}_{idx}"
            notification_keys.append((key, notif))
        
        current_keys = set(self.notification_components.keys())
        new_keys = set(key for key, _ in notification_keys)
        
        # Remove old notifications
        removed_keys = current_keys - new_keys
        for key in removed_keys:
            if key in self.notification_components:
                self.notification_components[key].unmount()
                del self.notification_components[key]
        
        # Update or create notifications
        for key, notification in notification_keys:
            if key not in self.notification_components:
                component = SingleNotificationComponent(key, self.palette, self.on_notification_click)
                component.container = self.container
                self.notification_components[key] = component
                component.render(notification)
            else:
                component = self.notification_components[key]
                component.update(notification)


# ============================================================================
# POST/FEED COMPONENTS
# ============================================================================

class SinglePostComponent(BaseComponent):
    """Individual post card - updates only when this post changes"""
    
    def __init__(self, post_id: str, palette: dict[str, str], callbacks: dict[str, Callable]):
        super().__init__(f"post_{post_id}")
        self.post_id = post_id
        self.palette = palette
        self.callbacks = callbacks  # like, comment, etc.
        self.container: Optional[ctk.CTkFrame] = None
        
    def render(self, post_data: dict[str, Any]) -> None:
        """Render single post without affecting other posts"""
        if not self.container:
            return
            
        if self.state.widget:
            self.state.widget.destroy()
            
        author = post_data.get("author", "Unknown")
        content = post_data.get("content", "")
        timestamp = post_data.get("created_at", "")
        likes = post_data.get("likes", 0)
        reply_count = len(post_data.get("replies", []))
        
        # Post card
        card = ctk.CTkFrame(
            self.container,
            fg_color=self.palette.get("card", "#18263f"),
            corner_radius=16
        )
        card.pack(fill="x", padx=0, pady=8)
        
        # Author header
        header = ctk.CTkFrame(card, fg_color="transparent")
        header.pack(fill="x", padx=16, pady=(12, 8))
        
        ctk.CTkLabel(
            header,
            text=f"@{author}",
            text_color=self.palette.get("accent", "#4c8dff"),
            font=ctk.CTkFont(weight="bold", size=14)
        ).pack(side="left")
        
        ctk.CTkLabel(
            header,
            text=timestamp,
            text_color=self.palette.get("muted", "#94a3b8"),
            font=ctk.CTkFont(size=11)
        ).pack(side="right")
        
        # Post content
        ctk.CTkLabel(
            card,
            text=content,
            text_color=self.palette.get("text", "#e2e8f0"),
            wraplength=600,
            justify="left",
            anchor="w"
        ).pack(anchor="w", padx=16, pady=(0, 12))
        
        # Action buttons
        actions = ctk.CTkFrame(card, fg_color="transparent")
        actions.pack(fill="x", padx=16, pady=(0, 12))
        
        ctk.CTkLabel(
            actions,
            text=f"👍 {likes}",
            text_color=self.palette.get("muted", "#94a3b8"),
            font=ctk.CTkFont(size=12)
        ).pack(side="left", padx=(0, 16))
        
        ctk.CTkLabel(
            actions,
            text=f"💬 {reply_count}",
            text_color=self.palette.get("muted", "#94a3b8"),
            font=ctk.CTkFont(size=12)
        ).pack(side="left")
        
        self.state.widget = card


class FeedComponent(BaseComponent):
    """Feed container - only updates changed posts"""
    
    def __init__(self, palette: dict[str, str], post_callbacks: dict[str, Callable]):
        super().__init__("feed")
        self.palette = palette
        self.post_callbacks = post_callbacks
        self.post_components: dict[str, SinglePostComponent] = {}
        self.container: Optional[ctk.CTkScrollableFrame] = None
        
    def mount(self, container: ctk.CTkScrollableFrame) -> None:
        super().mount(container)
        self.container = container
        
    def update(self, posts: list[dict[str, Any]]) -> None:
        """Efficiently update only changed posts"""
        if not self.container:
            return
            
        current_ids = set(self.post_components.keys())
        new_ids = set(post.get("id") for post in posts if post.get("id"))
        
        # Remove deleted posts
        removed_ids = current_ids - new_ids
        for post_id in removed_ids:
            if post_id in self.post_components:
                self.post_components[post_id].unmount()
                del self.post_components[post_id]
        
        # Update or create posts
        for post in posts:
            post_id = post.get("id")
            if not post_id:
                continue
                
            if post_id not in self.post_components:
                component = SinglePostComponent(post_id, self.palette, self.post_callbacks)
                component.container = self.container
                self.post_components[post_id] = component
                component.render(post)
            else:
                component = self.post_components[post_id]
                component.update(post)


# ============================================================================
# BUTTON COMPONENTS (Follow, Like, etc.)
# ============================================================================

class FollowButtonComponent(BaseComponent):
    """Isolated follow button - updates only when follow state changes"""
    
    def __init__(self, username: str, palette: dict[str, str], on_click: Callable):
        super().__init__(f"follow_btn_{username}")
        self.username = username
        self.palette = palette
        self.on_click = on_click
        self.parent_widget: Optional[Any] = None
        
    def render(self, is_following: bool) -> None:
        """Update button state without re-rendering entire profile"""
        if not self.parent_widget:
            return
            
        if self.state.widget:
            self.state.widget.destroy()
            
        button = ctk.CTkButton(
            self.parent_widget,
            text="Following" if is_following else "Follow",
            fg_color="transparent" if is_following else self.palette.get("accent", "#4c8dff"),
            border_width=1 if is_following else 0,
            border_color=self.palette.get("muted", "#94a3b8"),
            text_color=self.palette.get("muted", "#94a3b8") if is_following else "white",
            command=lambda: self.on_click(self.username)
        )
        
        self.state.widget = button
        return button


# ============================================================================
# BADGE COMPONENT
# ============================================================================

class NotificationBadgeComponent(BaseComponent):
    """Notification badge counter - updates independently"""
    
    def __init__(self, palette: dict[str, str]):
        super().__init__("notification_badge")
        self.palette = palette
        self.button_widget: Optional[ctk.CTkButton] = None
        
    def set_button(self, button: ctk.CTkButton) -> None:
        """Link to the notification button"""
        self.button_widget = button
        
    def update(self, count: int) -> None:
        """Update badge without re-rendering navigation"""
        if not self.button_widget:
            return
            
        # Only update if count actually changed
        if not self.should_update({"count": count}):
            return
            
        # Update button appearance based on count
        has_notifications = count > 0
        
        # This updates just the button state, not the entire nav bar
        try:
            if hasattr(self.button_widget, 'configure'):
                # Could add badge indicator or change icon here
                pass
        except Exception:
            pass


# ============================================================================
# COMPONENT REGISTRY
# ============================================================================

class ComponentRegistry:
    """Global registry to manage all active components"""
    
    def __init__(self):
        self.components: dict[str, BaseComponent] = {}
        
    def register(self, component: BaseComponent) -> None:
        """Register a component"""
        self.components[component.component_id] = component
        
    def unregister(self, component_id: str) -> None:
        """Unregister and cleanup a component"""
        if component_id in self.components:
            self.components[component_id].unmount()
            del self.components[component_id]
            
    def get(self, component_id: str) -> Optional[BaseComponent]:
        """Get a registered component"""
        return self.components.get(component_id)
        
    def clear_all(self) -> None:
        """Cleanup all components"""
        for component in list(self.components.values()):
            component.unmount()
        self.components.clear()


# Global registry instance
component_registry = ComponentRegistry()
