from functools import wraps
import logging

from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST

from courses.models import CourseChapter

from .models import DiscussionComment, DiscussionReaction

from .helpers import (
    get_chapter_discussion,
    get_discussion_statistics,
    get_comment_reaction_counts,
    get_user_reaction,
    broadcast_discussion_update,
)

from .permissions import (
    can_access_chapter_discussion,
    can_edit_comment,
    can_delete_comment,
    can_moderate_comment,
    can_react_to_comment,
)


MAX_COMMENT_LENGTH = 2500

logger = logging.getLogger(__name__)


def _safe_broadcast_discussion_update(*, chapter_id, event, comment_id):
    """
    Send a best-effort Channels notification after the database change commits.

    The database action must remain successful even if Redis/Channels is
    temporarily unavailable. The frontend's discussion polling can still
    retrieve the saved change.
    """
    try:
        broadcast_discussion_update(
            chapter_id=chapter_id,
            event=event,
            comment_id=comment_id,
        )
    except Exception:
        logger.exception(
            "Discussion broadcast failed: chapter_id=%s event=%s comment_id=%s",
            chapter_id,
            event,
            comment_id,
        )


# ============================================================
# JSON AUTHENTICATION
# ============================================================

def discussion_login_required(view_func):
    """
    Return JSON for unauthenticated requests instead of
    redirecting Fetch requests to the login page.
    """

    @wraps(view_func)
    def wrapper(request, *args, **kwargs):

        if not request.user.is_authenticated:
            return JsonResponse(
                {
                    "success": False,
                    "message": "Please log in to use discussions.",
                },
                status=401,
            )

        return view_func(request, *args, **kwargs)

    return wrapper


# ============================================================
# JSON RESPONSE HELPERS
# ============================================================

def success_response(message, data=None, status=200):

    response_data = {
        "success": True,
        "message": message,
    }

    if data is not None:
        response_data["data"] = data

    return JsonResponse(
        response_data,
        status=status,
    )


def error_response(message, status=400):

    return JsonResponse(
        {
            "success": False,
            "message": message,
        },
        status=status,
    )


# ============================================================
# COMMENT SERIALIZATION
# ============================================================

def _get_related_profile(user, related_name):
    """
    Safely return a user's related profile, if it exists.
    """
    try:
        return getattr(user, related_name, None)
    except Exception:
        return None


def _get_student_profile(user):
    """
    Find the StudentProfile reverse relation without assuming
    an unconfirmed related_name in the students app.
    """
    for relation in user._meta.related_objects:
        related_model = getattr(relation, "related_model", None)

        if not related_model:
            continue

        if related_model.__name__.lower() != "studentprofile":
            continue

        accessor_name = relation.get_accessor_name()

        if not accessor_name:
            continue

        try:
            profile = getattr(user, accessor_name, None)
        except Exception:
            profile = None

        if profile is not None:
            return profile

    return None


def _profile_image_url(profile):
    """
    Return either a Cloudinary image URL or a normal URLField value.
    Return None when the profile or image is unavailable.
    """
    if not profile:
        return None

    image = getattr(profile, "profile_image", None)

    if not image:
        return None

    try:
        image_url = getattr(image, "url", None)

        if image_url:
            return str(image_url)

        return str(image)
    except (ValueError, AttributeError, TypeError):
        return None


def _get_comment_author_details(user):
    """
    Resolve the display name, account role and profile image
    for Admin, Teacher and Student accounts.

    Existing user authentication and discussion permissions
    remain responsible for deciding who can access the discussion.
    """
    if user.is_staff or user.is_superuser:
        profile = _get_related_profile(user, "admin_profile")
        profile_name = getattr(profile, "full_name", "") if profile else ""

        return {
            "name": profile_name.strip() or user.get_full_name().strip() or user.username,
            "role": "Admin",
            "avatar": _profile_image_url(profile),
        }

    teacher_profile = _get_related_profile(user, "teacher_profile")

    if teacher_profile is not None:
        teacher_name = getattr(teacher_profile, "full_name", "")

        return {
            "name": teacher_name.strip() or user.get_full_name().strip() or user.username,
            "role": "Teacher",
            "avatar": _profile_image_url(teacher_profile),
        }

    student_profile = _get_student_profile(user)

    student_name = ""
    if student_profile is not None:
        student_name = getattr(student_profile, "full_name", "") or ""

    return {
        "name": student_name.strip() or user.get_full_name().strip() or user.username,
        "role": "Student",
        "avatar": _profile_image_url(student_profile),
    }


def serialize_comment(comment, user):
    """
    Convert a comment and its nested replies into JSON-safe data.

    Deleted comments display a placeholder while retaining
    their child replies.
    """
    author = comment.author

    author_details = _get_comment_author_details(author)

    author_name = (
        "Deleted user"
        if comment.is_deleted and not author.is_active
        else author_details["name"]
    )

    reaction_counts = get_comment_reaction_counts(comment)

    current_reaction = get_user_reaction(
        user,
        comment,
    )

    is_own_comment = (
        comment.author_id == user.pk
    )

    can_edit = can_edit_comment(
        user,
        comment,
    )

    can_delete = can_delete_comment(
        user,
        comment,
    )

    can_moderate = can_moderate_comment(
        user,
        comment,
    )

    replies = getattr(
        comment,
        "replies_list",
        [],
    )

    return {
        "id": comment.pk,
        "chapter_id": comment.chapter_id,
        "parent_id": comment.parent_id,

        "content": (
            ""
            if comment.is_deleted
            else comment.content
        ),

        "is_deleted": comment.is_deleted,
        "is_edited": bool(comment.edited_at),

        "author": {
            "id": author.pk,
            "name": author_name,
            "role": author_details["role"],
            "avatar": author_details["avatar"],
        },

        "created_at": comment.created_at.isoformat(),
        "updated_at": comment.updated_at.isoformat(),

        "reactions": {
            "likes": reaction_counts["likes"],
            "dislikes": reaction_counts["dislikes"],
            "current_user_reaction": current_reaction,
        },

        "permissions": {
            "is_own_comment": is_own_comment,
            "can_edit": can_edit,
            "can_delete": can_delete,
            "can_moderate": can_moderate,
        },

        "replies": [
            serialize_comment(reply, user)
            for reply in replies
        ],
    }

# ============================================================
# GET CHAPTER DISCUSSION
# ============================================================

@discussion_login_required
@require_GET
def chapter_discussion_view(request, chapter_id):
    """
    Return the complete chapter discussion.

    Admin:
        Platform-wide access.

    Teacher:
        Exact active Batch + Subject assignment.

    Student:
        Active batch purchase.
    """

    chapter = get_object_or_404(
        CourseChapter.objects.select_related(
            "batch",
            "subject",
        ),
        pk=chapter_id,
    )

    if not can_access_chapter_discussion(
        request.user,
        chapter,
    ):
        return error_response(
            "You do not have access to this chapter discussion.",
            status=403,
        )

    comment_tree = get_chapter_discussion(
        request.user,
        chapter,
    )

    comments_data = [
        serialize_comment(
            comment,
            request.user,
        )
        for comment in comment_tree
    ]

    statistics = get_discussion_statistics(
        request.user,
        chapter,
    )

    return success_response(
        "Discussion loaded successfully.",
        {
            "chapter_id": chapter.pk,
            "comments": comments_data,
            "statistics": statistics,
            "max_comment_length": MAX_COMMENT_LENGTH,
        },
    )


# ============================================================
# CREATE COMMENT OR NESTED REPLY
# ============================================================

@discussion_login_required
@require_POST
def create_discussion_comment_view(request, chapter_id):
    """
    Create a main comment or reply to an existing comment.

    parent_id is optional.

    No parent_id:
        Create a main question/comment.

    parent_id provided:
        Create a reply to that exact comment or reply.
    """

    chapter = get_object_or_404(
        CourseChapter,
        pk=chapter_id,
    )

    if not can_access_chapter_discussion(
        request.user,
        chapter,
    ):
        return error_response(
            "You do not have permission to participate in this discussion.",
            status=403,
        )

    content = request.POST.get(
        "content",
        "",
    ).strip()

    if not content:
        return error_response(
            "Please enter a comment."
        )

    if len(content) > MAX_COMMENT_LENGTH:
        return error_response(
            f"Comments and replies cannot exceed {MAX_COMMENT_LENGTH} characters."
        )

    parent_id = request.POST.get(
        "parent_id",
        "",
    ).strip()

    parent = None

    if parent_id:

        try:
            parent = DiscussionComment.objects.get(
                pk=parent_id,
                chapter=chapter,
                is_deleted=False,
            )

        except (
            DiscussionComment.DoesNotExist,
            ValueError,
            TypeError,
        ):
            return error_response(
                "The comment you are replying to does not exist or is unavailable.",
                status=404,
            )

    comment = DiscussionComment(
        chapter=chapter,
        author=request.user,
        parent=parent,
        content=content,
    )

    comment.full_clean()
    comment.save()

    # Prepare the new comment for serialization.
    comment.replies_list = []

    # Broadcast only after successful creation.
    transaction.on_commit(
        lambda: _safe_broadcast_discussion_update(
            chapter_id=comment.chapter_id,
            event="comment_created",
            comment_id=comment.pk,
        )
    )

    return success_response(
        (
            "Reply posted successfully."
            if parent
            else "Comment posted successfully."
        ),
        {
            "comment": serialize_comment(
                comment,
                request.user,
            ),
        },
        status=201,
    )


# ============================================================
# EDIT COMMENT OR REPLY
# ============================================================

@discussion_login_required
@require_POST
def edit_discussion_comment_view(request, comment_id):
    """
    Edit own content or moderate another user's content
    when the current user's role and scope allow it.
    """

    comment = get_object_or_404(
        DiscussionComment.objects.select_related(
            "chapter",
            "author",
        ),
        pk=comment_id,
    )

    if not can_edit_comment(
        request.user,
        comment,
    ):
        return error_response(
            "You do not have permission to edit this comment.",
            status=403,
        )

    content = request.POST.get(
        "content",
        "",
    ).strip()

    if not content:
        return error_response(
            "Comment content cannot be empty."
        )

    if len(content) > MAX_COMMENT_LENGTH:
        return error_response(
            f"Comments and replies cannot exceed {MAX_COMMENT_LENGTH} characters."
        )

    comment.content = content
    comment.edited_at = timezone.now()

    comment.save(
        update_fields=[
            "content",
            "edited_at",
            "updated_at",
        ]
    )

    transaction.on_commit(
        lambda: _safe_broadcast_discussion_update(
            chapter_id=comment.chapter_id,
            event="comment_updated",
            comment_id=comment.pk,
        )
    )

    return success_response(
        "Comment updated successfully.",
        {
            "comment": serialize_comment(
                comment,
                request.user,
            ),
        },
    )


# ============================================================
# DELETE COMMENT OR REPLY
# ============================================================

@discussion_login_required
@require_POST
def delete_discussion_comment_view(request, comment_id):
    """
    Permanently delete the selected comment/reply and its entire
    nested reply branch.

    The existing permission rules are preserved.
    Parent comments and sibling replies are not affected.
    """

    comment = get_object_or_404(
        DiscussionComment.objects.select_related(
            "chapter",
            "author",
        ),
        pk=comment_id,
    )

    if not can_delete_comment(
        request.user,
        comment,
    ):
        return error_response(
            "You do not have permission to delete this comment.",
            status=403,
        )

    # Save these values before deletion. Django clears the deleted
    # model instance's primary key after Model.delete() completes.
    deleted_comment_id = comment.pk
    chapter_id = comment.chapter_id

    # This permanently deletes the selected comment/reply, all its
    # nested descendants, and reactions attached to those records.
    comment.delete_branch()

    # Notify connected clients only after the database transaction commits.
    transaction.on_commit(
        lambda: _safe_broadcast_discussion_update(
            chapter_id=chapter_id,
            event="comment_deleted",
            comment_id=deleted_comment_id,
        )
    )

    return success_response(
        "Comment and its entire reply branch deleted permanently.",
        {
            "comment_id": deleted_comment_id,
            "permanently_deleted": True,
        },
    )


# ============================================================
# LIKE / DISLIKE / REMOVE REACTION
# ============================================================

@discussion_login_required
@require_POST
def toggle_discussion_reaction_view(request, comment_id):
    """
    Toggle a user's reaction.

    No existing reaction + like:
        Create like.

    No existing reaction + dislike:
        Create dislike.

    Existing like + like:
        Remove reaction.

    Existing dislike + dislike:
        Remove reaction.

    Existing like + dislike:
        Switch to dislike.

    Existing dislike + like:
        Switch to like.
    """

    comment = get_object_or_404(
        DiscussionComment.objects.select_related(
            "chapter",
        ),
        pk=comment_id,
    )

    if not can_react_to_comment(
        request.user,
        comment,
    ):
        return error_response(
            "You do not have permission to react to this comment.",
            status=403,
        )

    reaction_type = request.POST.get(
        "reaction_type",
        "",
    ).strip().lower()

    if reaction_type not in {
        DiscussionReaction.LIKE,
        DiscussionReaction.DISLIKE,
    }:
        return error_response(
            "Select a valid reaction."
        )

    with transaction.atomic():

        reaction = DiscussionReaction.objects.filter(
            comment=comment,
            user=request.user,
        ).first()

        if reaction:

            if reaction.reaction_type == reaction_type:

                reaction.delete()

                current_reaction = None

            else:

                reaction.reaction_type = reaction_type

                reaction.save(
                    update_fields=[
                        "reaction_type",
                        "updated_at",
                    ]
                )

                current_reaction = reaction_type

        else:

            DiscussionReaction.objects.create(
                comment=comment,
                user=request.user,
                reaction_type=reaction_type,
            )

            current_reaction = reaction_type

    reaction_counts = get_comment_reaction_counts(
        comment,
    )

    transaction.on_commit(
        lambda: _safe_broadcast_discussion_update(
            chapter_id=comment.chapter_id,
            event="reaction_updated",
            comment_id=comment.pk,
        )
    )

    return success_response(
        "Reaction updated successfully.",
        {
            "comment_id": comment.pk,
            "likes": reaction_counts["likes"],
            "dislikes": reaction_counts["dislikes"],
            "current_user_reaction": current_reaction,
        },
    )