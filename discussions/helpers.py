
from django.db.models import Count, Q
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from .models import DiscussionComment, DiscussionReaction
from .permissions import can_access_chapter_discussion


# ============================================================
# GET CHAPTER DISCUSSION COMMENTS
# ============================================================

def get_chapter_comments(user, chapter):
    """
    Return all comments belonging to one chapter.

    Access is checked before comments are returned.

    Includes:
    - Main comments
    - Nested replies
    - Author information
    - Reaction information
    """

    if not can_access_chapter_discussion(user, chapter):
        return DiscussionComment.objects.none()

    return (
        DiscussionComment.objects
        .filter(chapter=chapter)
        .select_related(
            "author",
            "parent",
        )
        .prefetch_related(
            "reactions",
        )
        .order_by("created_at", "pk")
    )


# ============================================================
# BUILD NESTED COMMENT TREE
# ============================================================

def build_comment_tree(comments):
    """
    Convert a flat list of comments into a nested reply tree.

    Every reply stays under its exact parent comment.

    Supports unlimited nesting.
    """

    comment_map = {}
    root_comments = []

    for comment in comments:

        comment.replies_list = []

        comment_map[comment.pk] = comment

    for comment in comments:

        if comment.parent_id:

            parent = comment_map.get(
                comment.parent_id
            )

            if parent:
                parent.replies_list.append(comment)

        else:
            root_comments.append(comment)

    return root_comments


# ============================================================
# GET COMPLETE DISCUSSION TREE
# ============================================================

def get_chapter_discussion(user, chapter):
    """
    Return the complete nested discussion for a chapter.
    """

    comments = list(
        get_chapter_comments(
            user=user,
            chapter=chapter,
        )
    )

    return build_comment_tree(comments)


# ============================================================
# GET DISCUSSION STATISTICS
# ============================================================

def get_discussion_statistics(user, chapter):
    """
    Return dynamic discussion statistics.

    Counts:
    - Total comments and replies
    - Main questions
    - Unique participants
    - Total likes
    - Total dislikes
    """

    if not can_access_chapter_discussion(user, chapter):

        return {
            "total_comments": 0,
            "total_questions": 0,
            "total_participants": 0,
            "total_likes": 0,
            "total_dislikes": 0,
        }

    comments = DiscussionComment.objects.filter(
        chapter=chapter,
    )

    reaction_counts = DiscussionReaction.objects.filter(
        comment__chapter=chapter,
    ).aggregate(
        total_likes=Count(
            "id",
            filter=Q(reaction_type="like"),
        ),
        total_dislikes=Count(
            "id",
            filter=Q(reaction_type="dislike"),
        ),
    )

    return {
        "total_comments": comments.count(),

        "total_questions": comments.filter(
            parent__isnull=True,
        ).count(),

        "total_participants": comments.values(
            "author_id",
        ).distinct().count(),

        "total_likes": reaction_counts["total_likes"] or 0,

        "total_dislikes": reaction_counts["total_dislikes"] or 0,
    }


# ============================================================
# GET COMMENT REACTION COUNTS
# ============================================================

def get_comment_reaction_counts(comment):
    """
    Return like and dislike counts for one comment or reply.
    """

    counts = DiscussionReaction.objects.filter(
        comment=comment,
    ).aggregate(
        likes=Count(
            "id",
            filter=Q(reaction_type="like"),
        ),
        dislikes=Count(
            "id",
            filter=Q(reaction_type="dislike"),
        ),
    )

    return {
        "likes": counts["likes"] or 0,
        "dislikes": counts["dislikes"] or 0,
    }


# ============================================================
# GET CURRENT USER REACTION
# ============================================================

def get_user_reaction(user, comment):
    """
    Return the current user's reaction to a comment.

    Possible results:
    - like
    - dislike
    - None
    """

    if not user or not user.is_authenticated:
        return None

    reaction = DiscussionReaction.objects.filter(
        user=user,
        comment=comment,
    ).values_list(
        "reaction_type",
        flat=True,
    ).first()

    return reaction

def broadcast_discussion_update(
    chapter_id,
    event,
    comment_id=None,
):
    """
    Broadcast a discussion update to everyone connected
    to the specified chapter's WebSocket group.

    The frontend will receive the event and refresh
    the chapter discussion through the HTTP API.
    """

    channel_layer = get_channel_layer()

    if channel_layer is None:
        return

    group_name = f"discussion_chapter_{chapter_id}"

    payload = {
        "type": "discussion_update",
        "event": event,
        "chapter_id": chapter_id,
        "comment_id": comment_id,
    }

    async_to_sync(channel_layer.group_send)(
        group_name,
        {
            "type": "discussion.event",
            "payload": payload,
        },
    )