from django.utils import timezone

from django.contrib.auth.models import User

from teachers.models import Teacher

from .models import (
    CourseChapter,
    ChapterChangeLog,
    ChapterVideo,
    VideoChangeLog,
    ChapterPDF,
    PDFChangeLog,
    ChapterQuiz,
    QuizChangeLog,
    DeletionAudit,
    get_actor_snapshot,
)

# ============================================================
# ACTOR VALIDATION
# ============================================================

def _get_actor_fields(
    admin=None,
    teacher=None,
):
    """
    Return all actor information required for a timeline record.

    Exactly one actor must be provided.

    The timeline stores both:

        1. Foreign-key reference
        2. Permanent name + role snapshot

    Admin:
        admin=User instance

    Teacher:
        teacher=Teacher instance
    """

    if admin is not None and teacher is not None:
        raise ValueError(
            "Only one actor can be provided: admin or teacher."
        )

    if admin is None and teacher is None:
        raise ValueError(
            "An admin or teacher actor is required."
        )

    # --------------------------------------------------------
    # ADMIN
    # --------------------------------------------------------

    if admin is not None:
        if not isinstance(admin, User):
            raise ValueError(
                "The admin actor must be a User instance."
            )

        actor_name, actor_role = get_actor_snapshot(
            admin=admin,
            teacher=None,
        )

        if not actor_name:
            raise ValueError(
                "Unable to determine the admin's full name."
            )

        return {
            "changed_by_admin": admin,
            "changed_by_teacher": None,
            "changed_by_name": actor_name,
            "changed_by_role": actor_role,
        }

    # --------------------------------------------------------
    # TEACHER
    # --------------------------------------------------------

    if not isinstance(teacher, Teacher):
        raise ValueError(
            "The teacher actor must be a Teacher instance."
        )

    actor_name, actor_role = get_actor_snapshot(
        admin=None,
        teacher=teacher,
    )

    if not actor_name:
        raise ValueError(
            "Unable to determine the teacher's full name."
        )

    return {
        "changed_by_admin": None,
        "changed_by_teacher": teacher,
        "changed_by_name": actor_name,
        "changed_by_role": actor_role,
    }


# ============================================================
# DELETION AUDIT ACTOR VALIDATION
# ============================================================

def _get_creation_actor_fields(
    admin=None,
    teacher=None,
):
    """
    Return creator fields used by DeletionAudit.

    Exactly one creator must be provided.
    """

    if admin is not None and teacher is not None:
        raise ValueError(
            "Only one creator can be provided: admin or teacher."
        )

    if admin is None and teacher is None:
        raise ValueError(
            "The original creator must be provided."
        )

    # --------------------------------------------------------
    # ADMIN CREATOR
    # --------------------------------------------------------

    if admin is not None:
        if not isinstance(admin, User):
            raise ValueError(
                "The admin creator must be a User instance."
            )

        return {
            "created_by_admin": admin,
            "created_by_teacher": None,
        }

    # --------------------------------------------------------
    # TEACHER CREATOR
    # --------------------------------------------------------

    if not isinstance(teacher, Teacher):
        raise ValueError(
            "The teacher creator must be a Teacher instance."
        )

    return {
        "created_by_admin": None,
        "created_by_teacher": teacher,
    }


# ============================================================
# COMMON TIMELINE RECORD
# ============================================================

def _create_timeline_entry(
    log_model,
    action,
    field_name="",
    old_value="",
    new_value="",
    change_summary="",
    admin=None,
    teacher=None,
    **extra_fields,
):
    """
    Common timeline creator.

    Every timeline entry automatically stores:

        - actor ForeignKey
        - actor full name snapshot
        - actor role snapshot
        - action
        - field name
        - old value
        - new value
        - change summary

    The specific content relationship is passed through
    extra_fields because each timeline model uses a different
    ForeignKey field.
    """

    actor_fields = _get_actor_fields(
        admin=admin,
        teacher=teacher,
    )

    return log_model.objects.create(
        **extra_fields,
        **actor_fields,
        action=action,
        field_name=field_name,
        old_value=str(old_value),
        new_value=str(new_value),
        change_summary=change_summary,
    )


# ============================================================
# CHAPTER TIMELINE
# ============================================================

def record_chapter_created(
    chapter,
    admin=None,
    teacher=None,
):
    """
    Record the complete Chapter snapshot at creation time.

    The Chapter Timeline must remember what the Chapter looked
    like when it was created.

    Stored snapshot:

        - Chapter name
        - Chapter description
        - Chapter order
        - Chapter status
        - Created datetime

    The actor information is stored separately by
    _create_timeline_entry().
    """

    chapter_snapshot = (
        f"Chapter Name: {chapter.chapter_name}\n"
        f"Description: {chapter.chapter_description}\n"
        f"Order: {chapter.chapter_order}\n"
        f"Status: {chapter.status}\n"
        f"Created At: {chapter.created_at}"
    )

    return _create_timeline_entry(
        log_model=ChapterChangeLog,
        action="created",
        field_name="chapter_snapshot",
        old_value="",
        new_value=chapter_snapshot,
        change_summary=(
            f"Chapter '{chapter.chapter_name}' was created."
        ),
        admin=admin,
        teacher=teacher,
        chapter=chapter,
    )


# ============================================================

def record_chapter_updated(
    chapter,
    field_name,
    old_value,
    new_value,
    admin=None,
    teacher=None,
):
    """
    Record one Chapter field update.

    This stores the exact before and after values.

    Examples:

        chapter_name
        chapter_description
        status
    """

    return _create_timeline_entry(
        log_model=ChapterChangeLog,
        action="updated",
        field_name=field_name,
        old_value=old_value,
        new_value=new_value,
        change_summary=(
            f"Chapter field '{field_name}' was updated."
        ),
        admin=admin,
        teacher=teacher,
        chapter=chapter,
    )


def record_chapter_order_changed(
    chapter,
    old_order,
    new_order,
    admin=None,
    teacher=None,
):
    """
    Record a Chapter order change.

    Example:

        Chapter order changed from 3 to 1.
    """

    return _create_timeline_entry(
        log_model=ChapterChangeLog,
        action="order_changed",
        field_name="chapter_order",
        old_value=old_order,
        new_value=new_order,
        change_summary=(
            f"Chapter order changed from "
            f"{old_order} to {new_order}."
        ),
        admin=admin,
        teacher=teacher,
        chapter=chapter,
    )


# ============================================================
# VIDEO TIMELINE
# ============================================================

def record_video_created(
    video,
    admin=None,
    teacher=None,
):
    """
    Record the complete Video snapshot at creation time.

    Stored snapshot:

        - Video name
        - Video description
        - Video order
        - Video status
        - Created datetime

    The actual Cloudinary video file is intentionally not stored
    in the visible timeline snapshot.
    """

    video_snapshot = (
        f"Video Name: {video.video_name}\n"
        f"Description: {video.video_description}\n"
        f"Order: {video.video_order}\n"
        f"Status: {video.status}\n"
        f"Created At: {video.created_at}"
    )

    return _create_timeline_entry(
        log_model=VideoChangeLog,
        action="created",
        field_name="video_snapshot",
        old_value="",
        new_value=video_snapshot,
        change_summary=(
            f"Video '{video.video_name}' was created."
        ),
        admin=admin,
        teacher=teacher,
        video=video,
    )


def record_video_updated(
    video,
    field_name,
    old_value,
    new_value,
    admin=None,
    teacher=None,
):
    """
    Record one video field update.
    """

    return _create_timeline_entry(
        log_model=VideoChangeLog,
        action="updated",
        field_name=field_name,
        old_value=old_value,
        new_value=new_value,
        change_summary=(
            f"Video field '{field_name}' was updated."
        ),
        admin=admin,
        teacher=teacher,
        video=video,
    )


def record_video_order_changed(
    video,
    old_order,
    new_order,
    admin=None,
    teacher=None,
):
    """
    Record video order change.
    """

    return _create_timeline_entry(
        log_model=VideoChangeLog,
        action="order_changed",
        field_name="video_order",
        old_value=old_order,
        new_value=new_order,
        change_summary=(
            f"Video order changed from "
            f"{old_order} to {new_order}."
        ),
        admin=admin,
        teacher=teacher,
        video=video,
    )


# ============================================================
# PDF TIMELINE
# ============================================================

def record_pdf_created(
    pdf,
    admin=None,
    teacher=None,
):
    """
    Record the complete PDF snapshot at creation time.

    Stored snapshot:

        - PDF name
        - PDF description
        - PDF order
        - PDF status
        - Created datetime

    The actual Cloudinary PDF file is intentionally not stored
    in the visible timeline snapshot.
    """

    pdf_snapshot = (
        f"PDF Name: {pdf.pdf_name}\n"
        f"Description: {pdf.pdf_description}\n"
        f"Order: {pdf.pdf_order}\n"
        f"Status: {pdf.status}\n"
        f"Created At: {pdf.created_at}"
    )

    return _create_timeline_entry(
        log_model=PDFChangeLog,
        action="created",
        field_name="pdf_snapshot",
        old_value="",
        new_value=pdf_snapshot,
        change_summary=(
            f"PDF '{pdf.pdf_name}' was created."
        ),
        admin=admin,
        teacher=teacher,
        pdf=pdf,
    )


def record_pdf_updated(
    pdf,
    field_name,
    old_value,
    new_value,
    admin=None,
    teacher=None,
):
    """
    Record one PDF field update.
    """

    return _create_timeline_entry(
        log_model=PDFChangeLog,
        action="updated",
        field_name=field_name,
        old_value=old_value,
        new_value=new_value,
        change_summary=(
            f"PDF field '{field_name}' was updated."
        ),
        admin=admin,
        teacher=teacher,
        pdf=pdf,
    )


def record_pdf_order_changed(
    pdf,
    old_order,
    new_order,
    admin=None,
    teacher=None,
):
    """
    Record PDF order change.
    """

    return _create_timeline_entry(
        log_model=PDFChangeLog,
        action="order_changed",
        field_name="pdf_order",
        old_value=old_order,
        new_value=new_order,
        change_summary=(
            f"PDF order changed from "
            f"{old_order} to {new_order}."
        ),
        admin=admin,
        teacher=teacher,
        pdf=pdf,
    )


# ============================================================
# QUIZ TIMELINE
# ============================================================

def record_quiz_created(
    quiz,
    admin=None,
    teacher=None,
):
    """
    Record the complete Quiz snapshot at creation time.

    Stored snapshot:

        - Quiz name
        - Quiz description
        - Quiz order
        - Maximum attempts
        - Quiz status
        - Created datetime
    """

    quiz_snapshot = (
        f"Quiz Name: {quiz.quiz_name}\n"
        f"Description: {quiz.quiz_description}\n"
        f"Order: {quiz.quiz_order}\n"
        f"Maximum Attempts: {quiz.maximum_attempts}\n"
        f"Status: {quiz.status}\n"
        f"Created At: {quiz.created_at}"
    )

    return _create_timeline_entry(
        log_model=QuizChangeLog,
        action="created",
        field_name="quiz_snapshot",
        old_value="",
        new_value=quiz_snapshot,
        change_summary=(
            f"Quiz '{quiz.quiz_name}' was created."
        ),
        admin=admin,
        teacher=teacher,
        quiz=quiz,
    )


def record_quiz_updated(
    quiz,
    field_name,
    old_value,
    new_value,
    admin=None,
    teacher=None,
):
    """
    Record one quiz field update.
    """

    return _create_timeline_entry(
        log_model=QuizChangeLog,
        action="updated",
        field_name=field_name,
        old_value=old_value,
        new_value=new_value,
        change_summary=(
            f"Quiz field '{field_name}' was updated."
        ),
        admin=admin,
        teacher=teacher,
        quiz=quiz,
    )


def record_quiz_order_changed(
    quiz,
    old_order,
    new_order,
    admin=None,
    teacher=None,
):
    """
    Record quiz order change.
    """

    return _create_timeline_entry(
        log_model=QuizChangeLog,
        action="order_changed",
        field_name="quiz_order",
        old_value=old_order,
        new_value=new_order,
        change_summary=(
            f"Quiz order changed from "
            f"{old_order} to {new_order}."
        ),
        admin=admin,
        teacher=teacher,
        quiz=quiz,
    )


# ============================================================
# QUIZ QUESTION TIMELINE
# ============================================================

def record_quiz_question_added(
    question,
    admin=None,
    teacher=None,
):
    """
    Record a quiz question being added.
    """

    return _create_timeline_entry(
        log_model=QuizChangeLog,
        action="question_added",
        field_name="question_text",
        new_value=question.question_text,
        change_summary=(
            "A new quiz question was added."
        ),
        admin=admin,
        teacher=teacher,
        quiz=question.quiz,
    )


def record_quiz_question_updated(
    question,
    field_name,
    old_value,
    new_value,
    admin=None,
    teacher=None,
):
    """
    Record a quiz question field update.
    """

    return _create_timeline_entry(
        log_model=QuizChangeLog,
        action="question_updated",
        field_name=field_name,
        old_value=old_value,
        new_value=new_value,
        change_summary=(
            f"Quiz question field '{field_name}' "
            f"was updated."
        ),
        admin=admin,
        teacher=teacher,
        quiz=question.quiz,
    )


def record_quiz_question_deleted(
    quiz,
    question_text,
    admin=None,
    teacher=None,
):
    """
    Record a quiz question deletion.

    The question may already be deleted, so the quiz and
    question text are passed separately.
    """

    return _create_timeline_entry(
        log_model=QuizChangeLog,
        action="question_deleted",
        field_name="question_text",
        old_value=question_text,
        change_summary=(
            "A quiz question was deleted."
        ),
        admin=admin,
        teacher=teacher,
        quiz=quiz,
    )


# ============================================================
# QUIZ OPTION TIMELINE
# ============================================================

def record_quiz_option_added(
    option,
    admin=None,
    teacher=None,
):
    """
    Record a quiz option being added.
    """

    return _create_timeline_entry(
        log_model=QuizChangeLog,
        action="option_added",
        field_name=f"option_{option.option_label}",
        new_value=option.option_text,
        change_summary=(
            f"Quiz option {option.option_label} was added."
        ),
        admin=admin,
        teacher=teacher,
        quiz=option.question.quiz,
    )


def record_quiz_option_updated(
    option,
    old_value,
    new_value,
    admin=None,
    teacher=None,
):
    """
    Record a quiz option text update.
    """

    return _create_timeline_entry(
        log_model=QuizChangeLog,
        action="option_updated",
        field_name=f"option_{option.option_label}",
        old_value=old_value,
        new_value=new_value,
        change_summary=(
            f"Quiz option {option.option_label} "
            f"was updated."
        ),
        admin=admin,
        teacher=teacher,
        quiz=option.question.quiz,
    )


def record_quiz_option_deleted(
    quiz,
    option_label,
    option_text,
    admin=None,
    teacher=None,
):
    """
    Record a quiz option deletion.
    """

    return _create_timeline_entry(
        log_model=QuizChangeLog,
        action="option_deleted",
        field_name=f"option_{option_label}",
        old_value=option_text,
        change_summary=(
            f"Quiz option {option_label} was deleted."
        ),
        admin=admin,
        teacher=teacher,
        quiz=quiz,
    )


def record_correct_answer_changed(
    option,
    old_value,
    new_value,
    admin=None,
    teacher=None,
):
    """
    Record a correct-answer change.

    Example:

        B -> C
    """

    return _create_timeline_entry(
        log_model=QuizChangeLog,
        action="correct_answer_changed",
        field_name="correct_answer",
        old_value=old_value,
        new_value=new_value,
        change_summary=(
            f"Correct answer changed from "
            f"{old_value} to {new_value}."
        ),
        admin=admin,
        teacher=teacher,
        quiz=option.question.quiz,
    )


# ============================================================
# DELETION AUDIT - CONTENT INFORMATION
# ============================================================

def _get_deletion_content_information(content):
    """
    Return the common information needed for DeletionAudit.

    Supported content:

        CourseChapter
        ChapterVideo
        ChapterPDF
        ChapterQuiz
    """

    if isinstance(content, CourseChapter):
        return {
            "content_type": "chapter",
            "content_name": content.chapter_name,
            "batch_name": content.batch.batch_name,
            "subject_name": content.subject.subject_name,
            "chapter_name": content.chapter_name,
        }

    if isinstance(content, ChapterVideo):
        return {
            "content_type": "video",
            "content_name": content.video_name,
            "batch_name": content.chapter.batch.batch_name,
            "subject_name": content.chapter.subject.subject_name,
            "chapter_name": content.chapter.chapter_name,
        }

    if isinstance(content, ChapterPDF):
        return {
            "content_type": "pdf",
            "content_name": content.pdf_name,
            "batch_name": content.chapter.batch.batch_name,
            "subject_name": content.chapter.subject.subject_name,
            "chapter_name": content.chapter.chapter_name,
        }

    if isinstance(content, ChapterQuiz):
        return {
            "content_type": "quiz",
            "content_name": content.quiz_name,
            "batch_name": content.chapter.batch.batch_name,
            "subject_name": content.chapter.subject.subject_name,
            "chapter_name": content.chapter.chapter_name,
        }

    raise ValueError(
        "Unsupported content type for deletion audit."
    )


# ============================================================
# DELETION AUDIT - SNAPSHOT
# ============================================================

def _build_content_snapshot(content):
    """
    Build a snapshot of the content before deletion.

    The snapshot remains available even after the original
    content object has been deleted.
    """

    if isinstance(content, CourseChapter):
        return {
            "model": "CourseChapter",
            "id": content.pk,
            "chapter_name": content.chapter_name,
            "chapter_description": content.chapter_description,
            "chapter_order": content.chapter_order,
            "status": content.status,
            "batch_id": content.batch_id,
            "batch_name": content.batch.batch_name,
            "subject_id": content.subject_id,
            "subject_name": content.subject.subject_name,
            "created_at": (
                content.created_at.isoformat()
                if content.created_at
                else None
            ),
        }

    if isinstance(content, ChapterVideo):
        return {
            "model": "ChapterVideo",
            "id": content.pk,
            "video_name": content.video_name,
            "video_description": content.video_description,
            "video_order": content.video_order,
            "status": content.status,
            "chapter_id": content.chapter_id,
            "chapter_name": content.chapter.chapter_name,
            "batch_id": content.chapter.batch_id,
            "batch_name": content.chapter.batch.batch_name,
            "subject_id": content.chapter.subject_id,
            "subject_name": content.chapter.subject.subject_name,
            "created_at": (
                content.created_at.isoformat()
                if content.created_at
                else None
            ),
        }

    if isinstance(content, ChapterPDF):
        return {
            "model": "ChapterPDF",
            "id": content.pk,
            "pdf_name": content.pdf_name,
            "pdf_description": content.pdf_description,
            "pdf_order": content.pdf_order,
            "status": content.status,
            "chapter_id": content.chapter_id,
            "chapter_name": content.chapter.chapter_name,
            "batch_id": content.chapter.batch_id,
            "batch_name": content.chapter.batch.batch_name,
            "subject_id": content.chapter.subject_id,
            "subject_name": content.chapter.subject.subject_name,
            "created_at": (
                content.created_at.isoformat()
                if content.created_at
                else None
            ),
        }

    if isinstance(content, ChapterQuiz):
        questions = []

        for question in content.questions.all():
            options = []

            for option in question.options.all():
                options.append(
                    {
                        "id": option.pk,
                        "label": option.option_label,
                        "text": option.option_text,
                        "is_correct": option.is_correct,
                    }
                )

            questions.append(
                {
                    "id": question.pk,
                    "question_text": question.question_text,
                    "marks": question.marks,
                    "options": options,
                }
            )

        return {
            "model": "ChapterQuiz",
            "id": content.pk,
            "quiz_name": content.quiz_name,
            "quiz_description": content.quiz_description,
            "quiz_order": content.quiz_order,
            "maximum_attempts": content.maximum_attempts,
            "status": content.status,
            "chapter_id": content.chapter_id,
            "chapter_name": content.chapter.chapter_name,
            "batch_id": content.chapter.batch_id,
            "batch_name": content.chapter.batch.batch_name,
            "subject_id": content.chapter.subject_id,
            "subject_name": content.chapter.subject.subject_name,
            "questions": questions,
            "created_at": (
                content.created_at.isoformat()
                if content.created_at
                else None
            ),
        }

    raise ValueError(
        "Unsupported content type for deletion snapshot."
    )


# ============================================================
# CREATE DELETION AUDIT
# ============================================================

def create_deletion_audit(
    content,
    admin=None,
    teacher=None,
):
    """
    Create the deletion audit record before deletion.

    This function does not delete the content.

    The original content must still exist when this function
    is called.
    """

    content_info = _get_deletion_content_information(
        content
    )

    creator_fields = _get_creation_actor_fields(
        admin=admin,
        teacher=teacher,
    )

    snapshot = _build_content_snapshot(
        content
    )

    return DeletionAudit.objects.create(
        content_type=content_info["content_type"],
        object_id=content.pk,
        content_name=content_info["content_name"],
        batch_name=content_info["batch_name"],
        subject_name=content_info["subject_name"],
        chapter_name=content_info["chapter_name"],
        original_created_at=content.created_at,
        snapshot=snapshot,
        status="pending",
        **creator_fields,
    )


# ============================================================
# TEACHER DELETE REQUEST
# ============================================================

def mark_teacher_delete_requested(
    audit,
    teacher,
    reason,
):
    """
    Mark a deletion audit as requested by a teacher.

    This function does not delete anything.
    """

    if not isinstance(audit, DeletionAudit):
        raise ValueError(
            "A valid DeletionAudit instance is required."
        )

    if not isinstance(teacher, Teacher):
        raise ValueError(
            "The requester must be a Teacher instance."
        )

    reason = str(reason).strip()

    if not reason:
        raise ValueError(
            "A deletion reason is required."
        )

    if audit.status != "pending":
        raise ValueError(
            "This deletion audit is no longer pending."
        )

    audit.requested_by_teacher = teacher
    audit.requested_at = timezone.now()
    audit.request_reason = reason
    audit.status = "pending"

    audit.save(
        update_fields=[
            "requested_by_teacher",
            "requested_at",
            "request_reason",
            "status",
        ]
    )

    return audit


# ============================================================
# ADMIN DELETION DECISION
# ============================================================

def mark_admin_deletion_decision(
    audit,
    admin,
    decision,
    response="",
):
    """
    Record the Admin decision on a Teacher deletion request.

    Allowed decisions:

        approved
        rejected

    This function does not delete the content.
    """

    if not isinstance(audit, DeletionAudit):
        raise ValueError(
            "A valid DeletionAudit instance is required."
        )

    if not isinstance(admin, User):
        raise ValueError(
            "The decision maker must be a User instance."
        )

    if decision not in {
        "approved",
        "rejected",
    }:
        raise ValueError(
            "Decision must be either approved or rejected."
        )

    if audit.requested_by_teacher is None:
        raise ValueError(
            "This audit does not contain a teacher deletion request."
        )

    if audit.admin_decision:
        raise ValueError(
            "An admin decision has already been recorded."
        )

    audit.admin_decision = decision
    audit.decision_by_admin = admin
    audit.decision_at = timezone.now()
    audit.admin_response = str(response).strip()

    if decision == "approved":
        audit.status = "approved"
    else:
        audit.status = "rejected"

    audit.save(
        update_fields=[
            "admin_decision",
            "decision_by_admin",
            "decision_at",
            "admin_response",
            "status",
        ]
    )

    return audit


# ============================================================
# ADMIN DIRECT DELETE
# ============================================================

def mark_admin_direct_delete(
    audit,
    admin,
    reason="",
):
    """
    Mark a deletion audit as a direct Admin deletion.

    The actual object deletion is performed by the
    appropriate Admin view.
    """

    if not isinstance(audit, DeletionAudit):
        raise ValueError(
            "A valid DeletionAudit instance is required."
        )

    if not isinstance(admin, User):
        raise ValueError(
            "The deleting actor must be a User instance."
        )

    audit.deleted_by_admin = admin
    audit.admin_delete_reason = str(reason).strip()
    audit.deletion_method = "admin_direct"

    audit.save(
        update_fields=[
            "deleted_by_admin",
            "admin_delete_reason",
            "deletion_method",
        ]
    )

    return audit


# ============================================================
# FINAL DELETION COMPLETION
# ============================================================

def mark_deletion_completed(
    audit,
    deletion_method,
):
    """
    Mark the audit after the actual content object has
    successfully been deleted.

    Allowed deletion methods:

        admin_direct
        teacher_request_approved
    """

    if not isinstance(audit, DeletionAudit):
        raise ValueError(
            "A valid DeletionAudit instance is required."
        )

    if deletion_method not in {
        "admin_direct",
        "teacher_request_approved",
    }:
        raise ValueError(
            "Invalid deletion method."
        )

    if audit.status not in {
        "approved",
        "pending",
    }:
        raise ValueError(
            "This audit cannot be marked as deleted from "
            "its current status."
        )

    audit.deletion_method = deletion_method
    audit.status = "deleted"
    audit.deleted_at = timezone.now()

    audit.save(
        update_fields=[
            "deletion_method",
            "status",
            "deleted_at",
        ]
    )

    return audit