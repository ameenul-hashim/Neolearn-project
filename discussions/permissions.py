
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

    # Admin access
    if user.is_staff or user.is_superuser:
        return ROLE_ADMIN

    # Teacher access
    teacher = Teacher.objects.filter(
        user=user,
        is_blocked=False,
    ).first()

    if teacher:
        return ROLE_TEACHER

    # Normal student access
    return ROLE_STUDENT


# ============================================================
# GET TEACHER PROFILE
# ============================================================

def get_active_teacher(user):
    """
    Return the active Teacher profile for the logged-in user.

    Returns None when the user is not an active teacher.
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
    A teacher can access a chapter only when:

    1. The teacher profile is active.
    2. TeacherBatch assignment is active for the chapter's batch.
    3. TeacherSubject assignment is active for the exact
       same batch and subject.

    Chapter creator is NOT checked.

    Any actively assigned teacher can access the discussion,
    regardless of who created the chapter.
    """

    teacher = get_active_teacher(user)

    if not teacher or not chapter:
        return False

    batch_id = chapter.batch_id
    subject_id = chapter.subject_id

    if not batch_id or not subject_id:
        return False

    # Verify active batch assignment.
    has_batch_access = TeacherBatch.objects.filter(
        teacher=teacher,
        batch_id=batch_id,
        is_active=True,
    ).exists()

    if not has_batch_access:
        return False

    # Verify active assignment to this exact subject
    # within this exact batch.
    has_subject_access = TeacherSubject.objects.filter(
        teacher=teacher,
        batch_id=batch_id,
        subject_id=subject_id,
        is_active=True,
    ).exists()

    return has_subject_access


# ============================================================
# STUDENT CHAPTER ACCESS
# ============================================================

def student_can_access_chapter(user, chapter):
    """
    A student can access a chapter only when an active
    batch purchase exists for the chapter's batch.
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
    Central permission function used by all discussion views.

    Admin:
        Access to every chapter discussion.

    Teacher:
        Access to chapters under actively assigned
        Batch + Subject combinations.

    Student:
        Access to chapters under actively purchased batches.
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
        Can moderate any comment or reply platform-wide.

    Teacher:
        Can moderate comments and replies inside assigned
        Batch + Subject discussions.

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
# EDIT COMMENT PERMISSION
# ============================================================

def can_edit_comment(user, comment):
    """
    Students:
        Can edit only their own comments and replies.

    Teachers:
        Can edit their own comments and replies.
        Can also moderate/edit other users' content
        within their assigned Batch + Subject.

    Admins:
        Can edit their own comments and replies.
        Can also moderate/edit other users' content
        platform-wide.
    """

    if not user or not user.is_authenticated or not comment:
        return False

    if comment.is_deleted:
        return False

    # Every user can edit their own content.
    if comment.author_id == user.pk:
        return can_access_chapter_discussion(
            user,
            comment.chapter,
        )

    # Admin and Teacher can moderate other users' content.
    return can_moderate_comment(user, comment)


# ============================================================
# DELETE COMMENT PERMISSION
# ============================================================

def can_delete_comment(user, comment):
    """
    Students:
        Can delete only their own comments and replies.

    Teachers:
        Can delete their own content and moderate other
        users' content inside their assigned Batch + Subject.

    Admins:
        Can delete their own content and moderate any
        other user's content platform-wide.

    Deletion will be handled as a soft delete.
    """

    if not user or not user.is_authenticated or not comment:
        return False

    if comment.is_deleted:
        return False

    # Every user can delete their own content.
    if comment.author_id == user.pk:
        return can_access_chapter_discussion(
            user,
            comment.chapter,
        )

    # Admin and Teacher can moderate other users' content.
    return can_moderate_comment(user, comment)


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
