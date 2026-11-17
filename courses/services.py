import logging

import cloudinary.uploader

from django.db import transaction
from django.db.models import F
from django.db.models.deletion import ProtectedError
from django.utils import timezone

from .models import (
    CourseChapter,
    ChapterVideo,
    ChapterPDF,
    ChapterQuiz,
    QuizQuestion,
    QuizOption,
    DeletionAudit,
    CloudinaryDeletionTask,
    get_actor_snapshot,
)


logger = logging.getLogger(__name__)


VALID_CONTENT_TYPES = {
    "chapter": CourseChapter,
    "video": ChapterVideo,
    "pdf": ChapterPDF,
    "quiz": ChapterQuiz,
}


class DeletionServiceError(Exception):
    """Raised when a deletion operation cannot safely be completed."""


# ---------------------------------------------------------------------
# ACTOR AND CLOUDINARY HELPERS
# ---------------------------------------------------------------------

def _actor_name_role(actor):
    """Return the immutable display name and role for an actor dictionary."""
    if not isinstance(actor, dict):
        raise DeletionServiceError("Invalid actor information.")

    role = actor.get("role")
    admin = actor.get("admin")
    teacher = actor.get("teacher")

    if role == "admin" and admin:
        return get_actor_snapshot(admin=admin)

    if role == "teacher" and teacher:
        return get_actor_snapshot(teacher=teacher)

    raise DeletionServiceError("Actor information is incomplete.")


def _original_creator(obj):
    """Find the admin or teacher who originally created the content."""
    admin = getattr(obj, "created_by_admin", None)
    teacher = getattr(obj, "created_by_teacher", None)

    return {
        "admin": admin,
        "teacher": teacher,
        "name": get_actor_snapshot(admin=admin, teacher=teacher)[0],
        "role": get_actor_snapshot(admin=admin, teacher=teacher)[1],
    }


def _cloudinary_public_id(value):
    """Extract a Cloudinary public ID from a CloudinaryField value."""
    if not value:
        return ""

    public_id = getattr(value, "public_id", None)
    if public_id:
        return public_id

    return str(value).strip()


def _is_default_asset(public_id):
    """Shared default thumbnails must never be deleted."""
    return bool(
        public_id
        and public_id.startswith("neolearn/defaults/")
    )


def _assets_for_video(video):
    return [
        (_cloudinary_public_id(video.video_file), "video"),
    ]


def _assets_for_pdf(pdf):
    return [
        (_cloudinary_public_id(pdf.pdf_file), "raw"),
        (_cloudinary_public_id(pdf.pdf_thumbnail), "image"),
    ]


def _assets_for_content(content_type, obj):
    """Capture every owned Cloudinary asset before deleting database rows."""
    if content_type == "video":
        return _assets_for_video(obj)

    if content_type == "pdf":
        return _assets_for_pdf(obj)

    if content_type == "chapter":
        assets = []

        for video in ChapterVideo.objects.filter(chapter=obj).only(
            "id", "video_file"
        ):
            assets.extend(_assets_for_video(video))

        for pdf in ChapterPDF.objects.filter(chapter=obj).only(
            "id", "pdf_file", "pdf_thumbnail"
        ):
            assets.extend(_assets_for_pdf(pdf))

        return assets

    # ChapterQuiz and its questions/options do not own Cloudinary files.
    return []


def _process_cloudinary_task(task_id):
    """Attempt one queued Cloudinary deletion and persist its result."""
    try:
        task = CloudinaryDeletionTask.objects.get(pk=task_id)
    except CloudinaryDeletionTask.DoesNotExist:
        return False

    if task.status == "completed":
        return True

    CloudinaryDeletionTask.objects.filter(pk=task.pk).update(
        attempts=F("attempts") + 1
    )
    task.refresh_from_db(fields=["attempts"])

    try:
        result = cloudinary.uploader.destroy(
            task.public_id,
            resource_type=task.resource_type,
            type="upload",
            invalidate=True,
        )
        result_status = result.get("result") if isinstance(result, dict) else None

        if result_status in {"ok", "not found"}:
            task.status = "completed"
            task.last_error = ""
            task.completed_at = timezone.now()
            task.save(update_fields=[
                "status", "last_error", "completed_at", "updated_at"
            ])
            return True

        task.status = "failed"
        task.last_error = f"Unexpected Cloudinary response: {result!r}"[:4000]
        task.save(update_fields=["status", "last_error", "updated_at"])
        logger.warning("Cloudinary cleanup task %s returned: %s", task.pk, result)
        return False

    except Exception as exc:
        task.status = "failed"
        task.last_error = str(exc)[:4000]
        task.save(update_fields=["status", "last_error", "updated_at"])
        logger.exception("Cloudinary cleanup task %s failed.", task.pk)
        return False


def process_pending_cloudinary_cleanup(limit=100):
    """Retry pending/failed Cloudinary deletions from a worker or command."""
    task_ids = list(
        CloudinaryDeletionTask.objects.filter(
            status__in=["pending", "failed"]
        ).order_by("created_at", "pk").values_list("pk", flat=True)[:limit]
    )
    results = {"completed": 0, "failed": 0}

    for task_id in task_ids:
        if _process_cloudinary_task(task_id):
            results["completed"] += 1
        else:
            results["failed"] += 1
    return results


def _schedule_cloudinary_cleanup(assets):
    """Persist cleanup tasks in the transaction and run them after commit."""
    task_ids = []
    seen = set()

    for public_id, resource_type in assets:
        if not public_id or _is_default_asset(public_id):
            continue
        key = (public_id, resource_type)
        if key in seen:
            continue
        seen.add(key)

        task, _created = CloudinaryDeletionTask.objects.get_or_create(
            public_id=public_id,
            resource_type=resource_type,
            defaults={"status": "pending"},
        )
        if task.status != "completed":
            task_ids.append(task.pk)

    if task_ids:
        transaction.on_commit(
            lambda ids=tuple(task_ids): [
                _process_cloudinary_task(task_id) for task_id in ids
            ]
        )


# CONTENT LOOKUP, SNAPSHOTS AND ORDERING
# ---------------------------------------------------------------------

def get_content_object(
    content_type,
    object_id,
    batch=None,
    subject=None,
    chapter_id=None,
    lock=False,
):
    """
    Resolve content by type and ID, optionally restricting it to the
    requested batch/subject/chapter. Returns None when it does not match.
    """
    model = VALID_CONTENT_TYPES.get(content_type)
    if model is None:
        return None

    queryset = model.objects.all()

    if lock:
        queryset = queryset.select_for_update()

    if content_type == "chapter":
        if batch is not None:
            queryset = queryset.filter(batch=batch)
        if subject is not None:
            queryset = queryset.filter(subject=subject)

    else:
        queryset = queryset.select_related(
            "chapter",
            "chapter__batch",
            "chapter__subject",
        )

        if batch is not None:
            queryset = queryset.filter(chapter__batch=batch)
        if subject is not None:
            queryset = queryset.filter(chapter__subject=subject)
        if chapter_id is not None:
            queryset = queryset.filter(chapter_id=chapter_id)

    return queryset.filter(pk=object_id).first()


def _creator_snapshot(obj):
    creator = _original_creator(obj)
    created_at = getattr(obj, "created_at", None)
    return {
        "created_by_name": creator["name"],
        "created_by_role": creator["role"],
        "original_created_at": created_at.isoformat() if created_at else None,
    }


def build_deletion_snapshot(content_type, obj):
    """
    Build a JSON-safe snapshot before deletion.

    A chapter snapshot includes all child video/PDF/quiz records.
    A quiz snapshot includes every question, option and correct-answer flag.
    Cloudinary public IDs are stored as audit metadata, not file contents.
    """
    if content_type not in VALID_CONTENT_TYPES:
        raise DeletionServiceError("Unsupported content type.")

    chapter = obj if content_type == "chapter" else obj.chapter

    snapshot = {
        "content_type": content_type,
        "object_id": obj.pk,
        "content_name": _content_name(content_type, obj),
        "batch_id": chapter.batch_id,
        "batch_name": chapter.batch.batch_name,
        "subject_id": chapter.subject_id,
        "subject_name": chapter.subject.subject_name,
        "chapter_id": chapter.pk,
        "chapter_name": chapter.chapter_name,
        "original_creator": _creator_snapshot(obj),
    }

    if content_type == "chapter":
        snapshot.update({
            "chapter_description": chapter.chapter_description,
            "chapter_order": chapter.chapter_order,
            "status": chapter.status,
            "videos": [
                {
                    "id": video.pk,
                    "name": video.video_name,
                    "description": video.video_description,
                    "order": video.video_order,
                    "status": video.status,
                    "video_public_id": _cloudinary_public_id(video.video_file),
                    "original_creator": _creator_snapshot(video),
                }
                for video in ChapterVideo.objects.filter(chapter=chapter).order_by(
                    "video_order", "pk"
                )
            ],
            "pdfs": [
                {
                    "id": pdf.pk,
                    "name": pdf.pdf_name,
                    "description": pdf.pdf_description,
                    "order": pdf.pdf_order,
                    "status": pdf.status,
                    "pdf_public_id": _cloudinary_public_id(pdf.pdf_file),
                    "thumbnail_public_id": _cloudinary_public_id(pdf.pdf_thumbnail),
                    "original_creator": _creator_snapshot(pdf),
                }
                for pdf in ChapterPDF.objects.filter(chapter=chapter).order_by(
                    "pdf_order", "pk"
                )
            ],
            "quizzes": [
                _quiz_snapshot(quiz)
                for quiz in ChapterQuiz.objects.filter(chapter=chapter).order_by(
                    "quiz_order", "pk"
                )
            ],
        })

    elif content_type == "video":
        snapshot.update({
            "description": obj.video_description,
            "order": obj.video_order,
            "status": obj.status,
            "video_public_id": _cloudinary_public_id(obj.video_file),
        })

    elif content_type == "pdf":
        snapshot.update({
            "description": obj.pdf_description,
            "order": obj.pdf_order,
            "status": obj.status,
            "pdf_public_id": _cloudinary_public_id(obj.pdf_file),
            "thumbnail_public_id": _cloudinary_public_id(obj.pdf_thumbnail),
        })

    elif content_type == "quiz":
        snapshot.update(_quiz_snapshot(obj))

    return snapshot


def _quiz_snapshot(quiz):
    return {
        "id": quiz.pk,
        "name": quiz.quiz_name,
        "description": quiz.quiz_description,
        "order": quiz.quiz_order,
        "maximum_attempts": quiz.maximum_attempts,
        "answering_time": quiz.answering_time,
        "marks_per_question": quiz.marks_per_question,
        "status": quiz.status,
        "original_creator": _creator_snapshot(quiz),
        "questions": [
            {
                "id": question.pk,
                "question_text": question.question_text,
                "options": [
                    {
                        "id": option.pk,
                        "label": option.option_label,
                        "text": option.option_text,
                        "is_correct": option.is_correct,
                    }
                    for option in QuizOption.objects.filter(
                        question=question
                    ).order_by("option_label", "pk")
                ],
            }
            for question in QuizQuestion.objects.filter(
                quiz=quiz
            ).order_by("pk")
        ],
    }


def _content_name(content_type, obj):
    field_by_type = {
        "chapter": "chapter_name",
        "video": "video_name",
        "pdf": "pdf_name",
        "quiz": "quiz_name",
    }
    return getattr(obj, field_by_type[content_type])


def _order_queryset(content_type, obj):
    """Return the sibling queryset and ordering field for this content."""
    if content_type == "chapter":
        return (
            CourseChapter.objects.filter(
                batch=obj.batch,
                subject=obj.subject,
            ),
            "chapter_order",
        )

    if content_type == "video":
        return ChapterVideo.objects.filter(chapter=obj.chapter), "video_order"

    if content_type == "pdf":
        return ChapterPDF.objects.filter(chapter=obj.chapter), "pdf_order"

    if content_type == "quiz":
        return ChapterQuiz.objects.filter(chapter=obj.chapter), "quiz_order"

    raise DeletionServiceError("Unsupported content type.")


def _close_order_gap(content_type, obj):
    """Close the deleted item's order gap without changing other content."""
    queryset, order_field = _order_queryset(content_type, obj)
    deleted_order = getattr(obj, order_field)

    queryset.filter(
        **{f"{order_field}__gt": deleted_order}
    ).update(
        **{order_field: F(order_field) - 1}
    )


def _require_scope_ids(batch_id, subject_id):
    """
    Require both contextual IDs for every request review/withdraw action.
    The audit row's primary key is globally unique, while these IDs ensure
    the action is being performed from the correct Batch + Subject page.
    """
    if batch_id in (None, "") or subject_id in (None, ""):
        raise DeletionServiceError(
            "Batch and Subject context are required for this deletion action."
        )

    try:
        return int(batch_id), int(subject_id)
    except (TypeError, ValueError):
        raise DeletionServiceError("Invalid Batch or Subject context.")


def _audit_in_scope(audit, batch_id, subject_id):
    """Fail closed unless the audit snapshot matches both selected IDs."""
    batch_id, subject_id = _require_scope_ids(batch_id, subject_id)
    snapshot = audit.snapshot if isinstance(audit.snapshot, dict) else {}

    try:
        saved_batch_id = int(snapshot.get("batch_id"))
        saved_subject_id = int(snapshot.get("subject_id"))
    except (TypeError, ValueError):
        return False

    return saved_batch_id == batch_id and saved_subject_id == subject_id


def _object_in_scope(content_type, obj, batch_id, subject_id):
    """Verify the live object still belongs to the requested Batch + Subject."""
    batch_id, subject_id = _require_scope_ids(batch_id, subject_id)
    chapter = obj if content_type == "chapter" else getattr(obj, "chapter", None)

    return bool(
        chapter
        and chapter.batch_id == batch_id
        and chapter.subject_id == subject_id
    )


# ---------------------------------------------------------------------
# AUDIT RECORD CREATION
# ---------------------------------------------------------------------

def create_deletion_audit(
    content_type,
    obj,
    status,
    actor,
    request_reason="",
    admin_response="",
    deletion_method="",
    snapshot=None,
):
    """Create the permanent audit row, including actor name/role snapshots."""
    creator = _original_creator(obj)
    actor_name, actor_role = _actor_name_role(actor)

    chapter = obj if content_type == "chapter" else obj.chapter
    teacher_actor = actor.get("teacher") if actor.get("role") == "teacher" else None
    admin_actor = actor.get("admin") if actor.get("role") == "admin" else None

    audit = DeletionAudit(
        content_type=content_type,
        object_id=obj.pk,
        content_name=_content_name(content_type, obj),
        batch_name=chapter.batch.batch_name,
        subject_name=chapter.subject.subject_name,
        chapter_name=chapter.chapter_name,
        created_by_admin=creator["admin"],
        created_by_teacher=creator["teacher"],
        original_created_at=getattr(obj, "created_at", None),
        created_by_name=creator["name"],
        created_by_role=creator["role"],
        requested_by_teacher=teacher_actor,
        requested_at=timezone.now() if teacher_actor else None,
        request_reason=request_reason,
        requested_by_name=actor_name if teacher_actor else "",
        requested_by_role=actor_role if teacher_actor else "",
        deleted_by_admin=admin_actor if status == "deleted" else None,
        admin_delete_reason=(
            request_reason if admin_actor and status == "deleted" else ""
        ),
        deleted_by_name=actor_name if admin_actor and status == "deleted" else "",
        deleted_by_role=actor_role if admin_actor and status == "deleted" else "",
        deletion_method=deletion_method,
        status=status,
        deleted_at=timezone.now() if status == "deleted" else None,
        admin_response=admin_response,
        snapshot=snapshot if snapshot is not None else build_deletion_snapshot(
            content_type, obj
        ),
    )
    audit.save()
    return audit


# ---------------------------------------------------------------------
# PROTECTED RELATIONSHIP HANDLING
# ---------------------------------------------------------------------

def _protected_delete_message(exc):
    """
    Build a clear admin-facing message when Django PROTECT prevents deletion.

    The protected rows are intentionally not deleted or modified here.
    """
    protected_objects = list(getattr(exc, "protected_objects", []) or [])
    model_labels = []

    for protected_obj in protected_objects:
        try:
            label = protected_obj._meta.verbose_name
            label = str(label).strip().capitalize()
        except Exception:
            label = protected_obj.__class__.__name__

        if label and label not in model_labels:
            model_labels.append(label)

    if model_labels:
        references = ", ".join(model_labels[:4])
        if len(model_labels) > 4:
            references += ", and other protected records"
        return (
            "This content cannot be deleted because it is still linked to "
            f"protected records: {references}. Resolve or reassign those "
            "records first, then try deleting the content again. "
            "No content or audit history was deleted."
        )

    return (
        "This content cannot be deleted because another protected record "
        "still references it. Resolve or reassign that relationship first. "
        "No content or audit history was deleted."
    )


# ---------------------------------------------------------------------
# CORE DELETION OPERATIONS
# ---------------------------------------------------------------------

def _delete_content_locked(content_type, obj):
    """
    Capture assets and delete the content inside the caller's transaction.
    Returns captured Cloudinary assets for on_commit scheduling.
    """
    assets = _assets_for_content(content_type, obj)
    _close_order_gap(content_type, obj)
    obj.delete()
    return assets


def submit_teacher_deletion_request(
    content_type,
    object_id,
    actor,
    reason,
    batch=None,
    subject=None,
    chapter_id=None,
):
    """Create a pending teacher request. This function never deletes content."""
    if batch is None or subject is None or batch.pk is None or subject.pk is None:
        raise DeletionServiceError("Batch and Subject context are required.")

    if not reason or not reason.strip():
        raise DeletionServiceError("A deletion reason is required.")

    if not isinstance(actor, dict) or actor.get("role") != "teacher" or not actor.get("teacher"):
        raise DeletionServiceError("Only an authenticated teacher can request deletion.")

    with transaction.atomic():
        obj = get_content_object(
            content_type,
            object_id,
            batch=batch,
            subject=subject,
            chapter_id=chapter_id,
            lock=True,
        )
        if obj is None:
            raise DeletionServiceError("The requested content was not found.")

        pending_exists = DeletionAudit.objects.select_for_update().filter(
            content_type=content_type,
            object_id=obj.pk,
            status="pending",
        ).exists()

        if pending_exists:
            raise DeletionServiceError(
                "A deletion request is already pending for this content."
            )

        return create_deletion_audit(
            content_type=content_type,
            obj=obj,
            status="pending",
            actor=actor,
            request_reason=reason.strip(),
            deletion_method="",
        )


def admin_direct_delete(
    content_type,
    object_id,
    actor,
    reason,
    batch=None,
    subject=None,
    chapter_id=None,
):
    """Admin-only direct deletion with mandatory reason and permanent audit."""
    if not isinstance(actor, dict) or actor.get("role") != "admin" or not actor.get("admin"):
        raise DeletionServiceError("Only an admin can directly delete content.")

    if batch is None or subject is None or batch.pk is None or subject.pk is None:
        raise DeletionServiceError("Batch and Subject context are required.")

    if not reason or not reason.strip():
        raise DeletionServiceError("An admin deletion reason is required.")

    try:
        with transaction.atomic():
            obj = get_content_object(
                content_type,
                object_id,
                batch=batch,
                subject=subject,
                chapter_id=chapter_id,
                lock=True,
            )
            if obj is None:
                raise DeletionServiceError("The requested content was not found.")

            snapshot = build_deletion_snapshot(content_type, obj)
            assets = _assets_for_content(content_type, obj)

            # This audit row is created inside the same transaction as the
            # deletion. If PROTECT blocks deletion, the transaction rolls back
            # and this audit row is not incorrectly marked as deleted.
            create_deletion_audit(
                content_type=content_type,
                obj=obj,
                status="deleted",
                actor=actor,
                request_reason=reason.strip(),
                deletion_method="admin_direct",
                snapshot=snapshot,
            )

            _close_order_gap(content_type, obj)
            obj.delete()
            _schedule_cloudinary_cleanup(assets)

    except ProtectedError as exc:
        raise DeletionServiceError(
            _protected_delete_message(exc)
        ) from exc

    return True


def approve_teacher_deletion_request(audit_id, actor, admin_response, batch_id=None, subject_id=None):
    """Approve a pending request and permanently delete its content atomically."""
    if not isinstance(actor, dict) or actor.get("role") != "admin" or not actor.get("admin"):
        raise DeletionServiceError("Only an admin can approve deletion requests.")

    if not admin_response or not admin_response.strip():
        raise DeletionServiceError("An admin response is required for approval.")

    try:
        with transaction.atomic():
            batch_id, subject_id = _require_scope_ids(batch_id, subject_id)
            audit = DeletionAudit.objects.select_for_update().filter(
                pk=audit_id,
                status="pending",
            ).first()

            if audit is None or not _audit_in_scope(audit, batch_id, subject_id):
                raise DeletionServiceError(
                    "This request is no longer pending or does not exist."
                )

            obj = get_content_object(
                audit.content_type,
                audit.object_id,
                lock=True,
            )
            if obj is None or not _object_in_scope(
                audit.content_type, obj, batch_id, subject_id
            ):
                raise DeletionServiceError(
                    "The requested content does not belong to this Batch and Subject. "
                    "No deletion was performed."
                )

            # Keep the audit snapshot as it was at request time; only create one
            # if older audit records do not contain it.
            if not audit.snapshot:
                audit.snapshot = build_deletion_snapshot(audit.content_type, obj)

            actor_name, actor_role = _actor_name_role(actor)
            assets = _assets_for_content(audit.content_type, obj)

            audit.admin_decision = "approved"
            audit.decision_by_admin = actor["admin"]
            audit.decision_by_name = actor_name
            audit.decision_by_role = actor_role
            audit.decision_at = timezone.now()
            audit.admin_response = admin_response.strip()
            audit.deletion_method = "teacher_request_approved"
            audit.deleted_by_admin = actor["admin"]
            audit.deleted_by_name = actor_name
            audit.deleted_by_role = actor_role
            audit.admin_delete_reason = ""
            audit.status = "deleted"
            audit.deleted_at = timezone.now()
            audit.save()

            _close_order_gap(audit.content_type, obj)
            obj.delete()
            _schedule_cloudinary_cleanup(assets)

    except ProtectedError as exc:
        raise DeletionServiceError(
            _protected_delete_message(exc)
        ) from exc

    return audit


def reject_teacher_deletion_request(audit_id, actor, admin_response, batch_id=None, subject_id=None):
    """Reject a pending request without deleting its content."""
    if not isinstance(actor, dict) or actor.get("role") != "admin" or not actor.get("admin"):
        raise DeletionServiceError("Only an admin can reject deletion requests.")

    if not admin_response or not admin_response.strip():
        raise DeletionServiceError("An admin response is required for rejection.")

    actor_name, actor_role = _actor_name_role(actor)

    with transaction.atomic():
        batch_id, subject_id = _require_scope_ids(batch_id, subject_id)
        audit = DeletionAudit.objects.select_for_update().filter(
            pk=audit_id,
            status="pending",
        ).first()

        if audit is None or not _audit_in_scope(audit, batch_id, subject_id):
            raise DeletionServiceError(
                "This request is no longer pending or does not exist."
            )

        audit.admin_decision = "rejected"
        audit.decision_by_admin = actor["admin"]
        audit.decision_by_name = actor_name
        audit.decision_by_role = actor_role
        audit.decision_at = timezone.now()
        audit.admin_response = admin_response.strip()
        audit.status = "rejected"
        audit.save()

    return audit


def withdraw_teacher_deletion_request(audit_id, actor, batch_id=None, subject_id=None):
    """Allow a teacher to withdraw only their own pending request."""
    if not isinstance(actor, dict) or actor.get("role") != "teacher" or not actor.get("teacher"):
        raise DeletionServiceError("Only a teacher can withdraw a teacher request.")

    actor_name, actor_role = _actor_name_role(actor)

    with transaction.atomic():
        batch_id, subject_id = _require_scope_ids(batch_id, subject_id)
        audit = DeletionAudit.objects.select_for_update().filter(
            pk=audit_id,
            requested_by_teacher=actor["teacher"],
            status="pending",
        ).first()

        if audit is None or not _audit_in_scope(audit, batch_id, subject_id):
            raise DeletionServiceError(
                "This pending request was not found or does not belong to you."
            )

        audit.status = "withdrawn"
        audit.withdrawn_by_teacher = actor["teacher"]
        audit.withdrawn_by_name = actor_name
        audit.withdrawn_by_role = actor_role
        audit.withdrawn_at = timezone.now()
        audit.save(update_fields=[
            "status",
            "withdrawn_by_teacher",
            "withdrawn_by_name",
            "withdrawn_by_role",
            "withdrawn_at",
        ])

    return audit