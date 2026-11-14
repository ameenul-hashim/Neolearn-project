
from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer

from courses.models import CourseChapter

from .permissions import can_access_chapter_discussion


class DiscussionConsumer(AsyncJsonWebsocketConsumer):
    """
    Real-time chapter discussion consumer.

    Admin:
        Can connect to any chapter discussion.

    Teacher:
        Can connect only to chapters under actively assigned
        Batch + Subject combinations.

    Student:
        Can connect only to chapters under purchased batches.

    All users share the same discussion WebSocket implementation.
    """

    async def connect(self):

        self.chapter_id = self.scope["url_route"]["kwargs"].get(
            "chapter_id"
        )

        self.group_name = None

        user = self.scope.get("user")

        # ----------------------------------------------------
        # AUTHENTICATION CHECK
        # ----------------------------------------------------

        if not user or not user.is_authenticated:
            await self.close(code=4401)
            return

        # ----------------------------------------------------
        # CHAPTER ACCESS CHECK
        # ----------------------------------------------------

        has_access = await self.check_chapter_access(
            user,
            self.chapter_id,
        )

        if not has_access:
            await self.close(code=4403)
            return

        # ----------------------------------------------------
        # JOIN CHAPTER DISCUSSION GROUP
        # ----------------------------------------------------

        self.group_name = (
            f"discussion_chapter_{self.chapter_id}"
        )

        await self.channel_layer.group_add(
            self.group_name,
            self.channel_name,
        )

        await self.accept()

        await self.send_json(
            {
                "type": "connection_established",
                "message": "Connected to chapter discussion.",
                "chapter_id": self.chapter_id,
            }
        )

    async def disconnect(self, close_code):

        if self.group_name:

            await self.channel_layer.group_discard(
                self.group_name,
                self.channel_name,
            )

    async def receive_json(self, content, **kwargs):
        """
        Clients cannot directly broadcast discussion events.

        All comment, reply, edit, delete and reaction operations
        must pass through authenticated Django HTTP views.

        Those views will broadcast approved events to this group.
        """

        await self.send_json(
            {
                "type": "error",
                "message": (
                    "Use the discussion API to submit comments, "
                    "replies and reactions."
                ),
            }
        )

    # ========================================================
    # DATABASE PERMISSION VALIDATION
    # ========================================================

    @database_sync_to_async
    def check_chapter_access(self, user, chapter_id):

        try:
            chapter = CourseChapter.objects.get(
                pk=chapter_id,
            )

        except (
            CourseChapter.DoesNotExist,
            ValueError,
            TypeError,
        ):
            return False

        return can_access_chapter_discussion(
            user,
            chapter,
        )

    # ========================================================
    # RECEIVE SERVER-SIDE DISCUSSION EVENTS
    # ========================================================

    async def discussion_event(self, event):
        """
        Receive approved events sent by Django HTTP views.

        Examples:
        - comment_created
        - comment_updated
        - comment_deleted
        - reaction_updated
        """

        await self.send_json(
            event["payload"]
        )
