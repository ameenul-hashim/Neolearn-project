
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.utils import timezone

from courses.models import CourseChapter


class DiscussionComment(models.Model):
    """
    Stores chapter-wide discussion comments and unlimited nested replies.

    parent = None       -> Main comment / question
    parent = comment    -> Reply to that exact comment or reply

    Deleting a comment permanently deletes its entire nested reply branch.
    """

    chapter = models.ForeignKey(
        CourseChapter,
        on_delete=models.CASCADE,
        related_name="discussion_comments",
    )

    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="discussion_comments",
    )

    parent = models.ForeignKey(
        "self",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="replies",
    )

    content = models.TextField(
        max_length=2500,
    )

    # Retained for compatibility with existing database records.
    # New deletions use permanent deletion instead of soft deletion.
    is_deleted = models.BooleanField(
        default=False,
    )

    deleted_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    deleted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="deleted_discussion_comments",
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    edited_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    class Meta:
        ordering = ["created_at"]

        indexes = [
            models.Index(
                fields=["chapter", "created_at"],
                name="disc_chapter_created_idx",
            ),
            models.Index(
                fields=["parent", "created_at"],
                name="disc_parent_created_idx",
            ),
            models.Index(
                fields=["author", "created_at"],
                name="disc_author_created_idx",
            ),
        ]

    def clean(self):
        super().clean()

        if self.parent_id:
            if self.parent.chapter_id != self.chapter_id:
                raise ValidationError(
                    "A reply must belong to the same chapter as its parent comment."
                )

            if self.parent_id == self.pk:
                raise ValidationError(
                    "A comment cannot be its own parent."
                )

    def save(self, *args, **kwargs):
        if self.parent_id and self.chapter_id:
            if self.parent.chapter_id != self.chapter_id:
                raise ValidationError(
                    "A reply must belong to the same chapter as its parent comment."
                )

        super().save(*args, **kwargs)

    def delete_branch(self):
        """
        Permanently delete this comment or reply and its entire nested branch.

        Automatically deletes:
        - The selected comment or reply.
        - All replies belonging to it.
        - All nested replies at every depth.
        - All reactions belonging to deleted comments and replies.

        Parent comments and sibling replies remain unaffected.
        """

        with transaction.atomic():
            return self.delete()

    def mark_edited(self):
        """Record when a comment or reply was edited."""

        self.edited_at = timezone.now()

        self.save(
            update_fields=[
                "edited_at",
                "updated_at",
            ]
        )

    def __str__(self):
        if self.parent_id:
            return f"Reply by {self.author} - Chapter {self.chapter_id}"

        return f"Comment by {self.author} - Chapter {self.chapter_id}"


class DiscussionReaction(models.Model):
    """
    Stores one reaction per user per discussion comment/reply.

    Users can like, dislike, switch reactions, or remove their reaction.
    """

    LIKE = "like"
    DISLIKE = "dislike"

    REACTION_CHOICES = [
        (LIKE, "Like"),
        (DISLIKE, "Dislike"),
    ]

    comment = models.ForeignKey(
        DiscussionComment,
        on_delete=models.CASCADE,
        related_name="reactions",
    )

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="discussion_reactions",
    )

    reaction_type = models.CharField(
        max_length=10,
        choices=REACTION_CHOICES,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    class Meta:
        ordering = ["created_at"]

        constraints = [
            models.UniqueConstraint(
                fields=["comment", "user"],
                name="unique_discussion_user_reaction",
            ),
        ]

        indexes = [
            models.Index(
                fields=["comment", "reaction_type"],
                name="disc_reaction_count_idx",
            ),
        ]

    def __str__(self):
        return (
            f"{self.user} - {self.reaction_type} "
            f"- Comment {self.comment_id}"
        )
