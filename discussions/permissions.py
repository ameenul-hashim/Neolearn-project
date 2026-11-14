
from admins.models import Teacher, TeacherBatch, TeacherSubject
from orders.models import StudentBatchPurchase


# ============================================================
# DISCUSSION USER ROLES
# ============================================================

ROLE_ADMIN = "admin"
ROLE_TEACHER = "teacher"
ROLE_STUDENT = "student"


def get_discussion_role(user):
    """
    Identify the logged-in user's NeoLearn discussion role.

    Admin:
        Staff or superuser.

    Teacher:
        Has an active teacher profile and is not an admin.

    Student:
        Normal authenticated user who is neither admin nor teacher.
    """

    if not user or not user.is_authenticated:
        return None

    if user.is_staff or user.is_superuser:
        return ROLE_ADMIN

    teacher = Teacher.objects.filter(
        user=user,
        is_blocked=False,
    ).first()

    if teacher:
        return ROLE_TEACHER

    return ROLE_STUDENT


# ============================================================
# GET ACTIVE TEACHER PROFILE
# ============================================================

def get_active_teacher(user):
    """
    Return the active Teacher profile for the logged-in user.
    """

    if not user or not user.is_authenticated:
        return None

    if user.is_staff or user.is_superuser:
        return None

    return Teacher.objects.filter(
        user=user,
        is_blocked=False,
    ).first()


# ============================================================
# TEACHER CHAPTER ACCESS
# ============================================================

def teacher_can_access_chapter(user, chapter):
    """
    Teacher must have active assignments for the exact
    Batch + Subject combination of the chapter.
    """

    teacher = get_active_teacher(user)

    if not teacher or not chapter:
        return False

    batch_id = chapter.batch_id
    subject_id = chapter.subject_id

    if not batch_id or not subject_id:
        return False

    has_batch_access = TeacherBatch.objects.filter(
        teacher=teacher,
        batch_id=batch_id,
        is_active=True,
    ).exists()

    if not has_batch_access:
        return False

    return TeacherSubject.objects.filter(
        teacher=teacher,
        batch_id=batch_id,
        subject_id=subject_id,
        is_active=True,
    ).exists()


# ============================================================
# STUDENT CHAPTER ACCESS
# ============================================================

def student_can_access_chapter(user, chapter):
    """
    Student must have an active purchase for the chapter's batch.
    """

    if not user or not user.is_authenticated:
        return False

    if user.is_staff or user.is_superuser:
        return False

    if not chapter or not chapter.batch_id:
        return False

    return StudentBatchPurchase.objects.filter(
        student=user,
        batch_id=chapter.batch_id,
        status=StudentBatchPurchase.Status.ACTIVE,
    ).exists()


# ============================================================
# CHAPTER DISCUSSION ACCESS
# ============================================================

def can_access_chapter_discussion(user, chapter):
    """
    Admin:
        All chapter discussions.

    Teacher:
        Assigned Batch + Subject discussions.

    Student:
        Purchased batch discussions.
    """

    role = get_discussion_role(user)

    if not role or not chapter:
        return False

    if role == ROLE_ADMIN:
        return True

    if role == ROLE_TEACHER:
        return teacher_can_access_chapter(user, chapter)

    if role == ROLE_STUDENT:
        return student_can_access_chapter(user, chapter)

    return False


# ============================================================
# COMMENT MODERATION PERMISSION
# ============================================================

def can_moderate_comment(user, comment):
    """
    Admin:
        Can moderate all discussions.

    Teacher:
        Can moderate comments inside assigned discussions.

    Student:
        Cannot moderate other users' content.
    """

    if not user or not user.is_authenticated or not comment:
        return False

    role = get_discussion_role(user)

    if role == ROLE_ADMIN:
        return True

    if role == ROLE_TEACHER:
        return teacher_can_access_chapter(
            user,
            comment.chapter,
        )

    return False


# ============================================================
# COMMENT REPLY LOCK
# ============================================================

def is_comment_locked(user, comment):
    """
    Lock the original author's own comment/reply after it
    receives at least one direct reply.

    Applies to:
        - Student's own comments and replies.
        - Teacher's own comments and replies.

    Does not apply to Admins.

    This lock does not prevent Teachers from moderating
    Student-authored content.
    """

    if not user or not user.is_authenticated or not comment:
        return False

    role = get_discussion_role(user)

    if role not in (ROLE_STUDENT, ROLE_TEACHER):
        return False

    if comment.author_id != user.pk:
        return False

    return bool(comment.has_received_reply)


# ============================================================
# EDIT COMMENT PERMISSION
# ============================================================

def can_edit_comment(user, comment):
    """
    Admin:
        Can edit any comment/reply platform-wide.

    Teacher:
        Can edit own content before receiving a reply.
        Cannot edit own content after receiving a reply.
        Can edit Student-authored content in assigned discussions,
        regardless of whether it has received replies.
        Cannot edit Admin-authored or other Teacher-authored content.

    Student:
        Can edit only own content before receiving a reply.
    """

    if not user or not user.is_authenticated or not comment:
        return False

    if comment.is_deleted:
        return False

    role = get_discussion_role(user)

    # Admin has unrestricted editing permission.
    if role == ROLE_ADMIN:
        return True

    # Teacher permissions.
    if role == ROLE_TEACHER:

        if not teacher_can_access_chapter(
            user,
            comment.chapter,
        ):
            return False

        # Teacher editing own content.
        if comment.author_id == user.pk:
            return not is_comment_locked(user, comment)

        # Teacher can moderate Student-authored content only.
        author_role = get_discussion_role(comment.author)

        if author_role == ROLE_STUDENT:
            return True

        # Admin and other Teacher content are protected.
        return False

    # Student permissions.
    if role == ROLE_STUDENT:

        if comment.author_id != user.pk:
            return False

        if is_comment_locked(user, comment):
            return False

        return can_access_chapter_discussion(
            user,
            comment.chapter,
        )

    return False


# ============================================================
# DELETE COMMENT PERMISSION
# ============================================================

def can_delete_comment(user, comment):
    """
    Admin:
        Can delete any comment/reply platform-wide.

    Teacher:
        Can delete own content before receiving a reply.
        Cannot delete own content after receiving a reply.
        Can delete Student-authored content in assigned discussions,
        regardless of whether it has received replies.
        Cannot delete Admin-authored or other Teacher-authored content.

    Student:
        Can delete only own content before receiving a reply.
    """

    if not user or not user.is_authenticated or not comment:
        return False

    if comment.is_deleted:
        return False

    role = get_discussion_role(user)

    # Admin has unrestricted deletion permission.
    if role == ROLE_ADMIN:
        return True

    # Teacher permissions.
    if role == ROLE_TEACHER:

        if not teacher_can_access_chapter(
            user,
            comment.chapter,
        ):
            return False

        # Teacher deleting own content.
        if comment.author_id == user.pk:
            return not is_comment_locked(user, comment)

        # Teacher can delete Student-authored content only.
        author_role = get_discussion_role(comment.author)

        if author_role == ROLE_STUDENT:
            return True

        # Admin and other Teacher content are protected.
        return False

    # Student permissions.
    if role == ROLE_STUDENT:

        if comment.author_id != user.pk:
            return False

        if is_comment_locked(user, comment):
            return False

        return can_access_chapter_discussion(
            user,
            comment.chapter,
        )

    return False


# ============================================================
# REACTION PERMISSION
# ============================================================

def can_react_to_comment(user, comment):
    """
    Any user with access to the chapter discussion
    can like or dislike a comment or reply.
    """

    if not user or not user.is_authenticated or not comment:
        return False

    if comment.is_deleted:
        return False

    return can_access_chapter_discussion(
        user,
        comment.chapter,
    )
