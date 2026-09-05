from django import forms
from django.core.exceptions import ValidationError


# ============================================================
# CURRENT MODEL LOCATION
# ============================================================
#
# IMPORTANT:
# The Course Builder models are STILL inside teachers.models.
#
# We are deliberately NOT moving the models yet.
#
# Later, after the shared Course Builder is fully tested,
# these imports will be changed to:
#
#     from .models import ...
#
# Do NOT change that now.
# ============================================================

from teachers.models import (
    CourseChapter,
    ChapterVideo,
    ChapterPDF,
    ChapterQuiz,
    QuizQuestion,
)


# ============================================================
# COMMON HELPERS
# ============================================================


def _clean_text(value):
    """
    Normalize text entered through a normal Django form.

    We deliberately strip leading/trailing whitespace on the
    server rather than relying on JavaScript.
    """
    if value is None:
        return ""

    return str(value).strip()


def _validate_uploaded_file_not_empty(uploaded_file, empty_message):
    """
    Common uploaded-file validation.

    Django receives the real uploaded file here, so this check
    cannot be bypassed by disabling JavaScript in the browser.
    """

    if not uploaded_file:
        raise ValidationError(empty_message)

    if getattr(uploaded_file, "size", 0) <= 0:
        raise ValidationError(
            "The selected file is empty."
        )

    return uploaded_file


# ============================================================
# CHAPTER CREATE
# ============================================================


class ChapterCreateForm(forms.ModelForm):
    """
    Shared Chapter Create form.

    Used by:
        - Admin Course Builder
        - Teacher Course Builder

    Batch and Subject are intentionally NOT form fields.

    They are determined by the authenticated user's current
    Course Builder context in the view.

    chapter_order is also NOT a form field because new chapter
    order is calculated automatically by the server.
    """

    class Meta:
        model = CourseChapter

        fields = [
            "chapter_name",
            "chapter_description",
            "status",
        ]

        widgets = {
            "chapter_name": forms.TextInput(
                attrs={
                    "maxlength": 255,
                    "autocomplete": "off",
                }
            ),
            "chapter_description": forms.TextInput(
                attrs={
                    "maxlength": 255,
                }
            ),
            "status": forms.Select(),
        }

        error_messages = {
            "chapter_name": {
                "required": "Chapter name is required.",
                "max_length": (
                    "Chapter name cannot exceed 255 characters."
                ),
            },
            "chapter_description": {
                "max_length": (
                    "Chapter description cannot exceed 255 characters."
                ),
            },
            "status": {
                "invalid_choice": (
                    "Please select a valid chapter status."
                ),
            },
        }

    def __init__(
        self,
        *args,
        batch=None,
        subject=None,
        instance=None,
        **kwargs,
    ):
        super().__init__(
            *args,
            instance=instance,
            **kwargs,
        )

        self.batch = batch
        self.subject = subject

    def clean_chapter_name(self):
        chapter_name = _clean_text(
            self.cleaned_data.get("chapter_name")
        )

        if not chapter_name:
            raise ValidationError(
                "Chapter name is required."
            )

        if len(chapter_name) > 255:
            raise ValidationError(
                "Chapter name cannot exceed 255 characters."
            )

        return chapter_name

    def clean_chapter_description(self):
        description = _clean_text(
            self.cleaned_data.get(
                "chapter_description"
            )
        )

        if len(description) > 255:
            raise ValidationError(
                "Chapter description cannot exceed 255 characters."
            )

        return description

    def clean_status(self):
        status = (
            self.cleaned_data.get("status")
            or ""
        ).strip().lower()

        valid_statuses = {
            value
            for value, label
            in CourseChapter.STATUS_CHOICES
        }

        if status not in valid_statuses:
            raise ValidationError(
                "Please select a valid chapter status."
            )

        return status

    def clean(self):
        cleaned_data = super().clean()

        chapter_name = cleaned_data.get(
            "chapter_name"
        )

        if (
            chapter_name
            and self.batch is not None
            and self.subject is not None
        ):
            duplicate_exists = (
                CourseChapter.objects
                .filter(
                    batch=self.batch,
                    subject=self.subject,
                    chapter_name__iexact=chapter_name,
                    is_deleted=False,
                )
                .exclude(
                    pk=self.instance.pk
                    if self.instance
                    and self.instance.pk
                    else None
                )
                .exists()
            )

            if duplicate_exists:
                self.add_error(
                    "chapter_name",
                    (
                        "A chapter with this name already "
                        "exists in this subject."
                    ),
                )

        return cleaned_data


# ============================================================
# CHAPTER EDIT
# ============================================================


class ChapterEditForm(forms.ModelForm):
    """
    Shared Chapter Edit form.

    The existing Chapter object is supplied as instance.

    chapter_order is intentionally included because the existing
    Course Builder allows the chapter order to be managed during
    editing.

    The actual order update/reordering operation will later live
    in courses.services.py.
    """

    class Meta:
        model = CourseChapter

        fields = [
            "chapter_name",
            "chapter_description",
            "chapter_order",
            "status",
        ]

        widgets = {
            "chapter_name": forms.TextInput(
                attrs={
                    "maxlength": 255,
                    "autocomplete": "off",
                }
            ),
            "chapter_description": forms.TextInput(
                attrs={
                    "maxlength": 255,
                }
            ),
            "chapter_order": forms.NumberInput(
                attrs={
                    "min": 1,
                    "step": 1,
                }
            ),
            "status": forms.Select(),
        }

        error_messages = {
            "chapter_name": {
                "required": "Chapter name is required.",
                "max_length": (
                    "Chapter name cannot exceed 255 characters."
                ),
            },
            "chapter_description": {
                "max_length": (
                    "Chapter description cannot exceed 255 characters."
                ),
            },
            "chapter_order": {
                "required": "Chapter order is required.",
                "invalid": (
                    "Chapter order must be a positive whole number."
                ),
            },
            "status": {
                "invalid_choice": (
                    "Please select a valid chapter status."
                ),
            },
        }

    def __init__(
        self,
        *args,
        batch=None,
        subject=None,
        instance=None,
        **kwargs,
    ):
        super().__init__(
            *args,
            instance=instance,
            **kwargs,
        )

        self.batch = batch
        self.subject = subject

    def clean_chapter_name(self):
        chapter_name = _clean_text(
            self.cleaned_data.get("chapter_name")
        )

        if not chapter_name:
            raise ValidationError(
                "Chapter name is required."
            )

        if len(chapter_name) > 255:
            raise ValidationError(
                "Chapter name cannot exceed 255 characters."
            )

        return chapter_name

    def clean_chapter_description(self):
        description = _clean_text(
            self.cleaned_data.get(
                "chapter_description"
            )
        )

        if len(description) > 255:
            raise ValidationError(
                "Chapter description cannot exceed 255 characters."
            )

        return description

    def clean_chapter_order(self):
        order = self.cleaned_data.get(
            "chapter_order"
        )

        if order is None:
            raise ValidationError(
                "Chapter order is required."
            )

        if order < 1:
            raise ValidationError(
                "Chapter order must be at least 1."
            )

        return order

    def clean_status(self):
        status = (
            self.cleaned_data.get("status")
            or ""
        ).strip().lower()

        valid_statuses = {
            value
            for value, label
            in CourseChapter.STATUS_CHOICES
        }

        if status not in valid_statuses:
            raise ValidationError(
                "Please select a valid chapter status."
            )

        return status

    def clean(self):
        cleaned_data = super().clean()

        chapter_name = cleaned_data.get(
            "chapter_name"
        )

        if (
            chapter_name
            and self.batch is not None
            and self.subject is not None
        ):
            duplicate_exists = (
                CourseChapter.objects
                .filter(
                    batch=self.batch,
                    subject=self.subject,
                    chapter_name__iexact=chapter_name,
                    is_deleted=False,
                )
                .exclude(
                    pk=self.instance.pk
                    if self.instance
                    and self.instance.pk
                    else None
                )
                .exists()
            )

            if duplicate_exists:
                self.add_error(
                    "chapter_name",
                    (
                        "A chapter with this name already "
                        "exists in this subject."
                    ),
                )

        return cleaned_data


# ============================================================
# VIDEO UPLOAD
# ============================================================


class VideoUploadForm(forms.ModelForm):
    """
    Shared Video Upload form.

    Server-side rules preserved from the current Teacher
    Course Builder:

        - name required
        - name <= 255 characters
        - description required
        - description <= 5000 characters
        - MP4 extension required
        - empty files rejected
        - known non-video MIME types rejected

    video_order is NOT submitted because the server automatically
    places a new video after the current last active video.
    """

    class Meta:
        model = ChapterVideo

        fields = [
            "video_name",
            "video_description",
            "video_file",
        ]

        widgets = {
            "video_name": forms.TextInput(
                attrs={
                    "maxlength": 255,
                    "autocomplete": "off",
                }
            ),
            "video_description": forms.Textarea(
                attrs={
                    "maxlength": 5000,
                    "rows": 4,
                }
            ),
            "video_file": forms.ClearableFileInput(
                attrs={
                    "accept": ".mp4,video/mp4",
                }
            ),
        }

        error_messages = {
            "video_name": {
                "required": "Video name is required.",
                "max_length": (
                    "Video name cannot exceed 255 characters."
                ),
            },
            "video_description": {
                "required": "Video description is required.",
                "max_length": (
                    "Video description cannot exceed 5000 characters."
                ),
            },
            "video_file": {
                "required": (
                    "Please select a valid MP4 video file."
                ),
            },
        }

    def __init__(
        self,
        *args,
        chapter=None,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)

        self.chapter = chapter

    def clean_video_name(self):
        video_name = _clean_text(
            self.cleaned_data.get("video_name")
        )

        if not video_name:
            raise ValidationError(
                "Video name is required."
            )

        if len(video_name) > 255:
            raise ValidationError(
                "Video name cannot exceed 255 characters."
            )

        if self.chapter is not None:
            duplicate_exists = (
                ChapterVideo.objects
                .filter(
                    chapter=self.chapter,
                    video_name__iexact=video_name,
                    is_deleted=False,
                )
                .exists()
            )

            if duplicate_exists:
                raise ValidationError(
                    (
                        "A video with this name already "
                        "exists in this chapter."
                    )
                )

        return video_name

    def clean_video_description(self):
        description = _clean_text(
            self.cleaned_data.get(
                "video_description"
            )
        )

        if not description:
            raise ValidationError(
                "Video description is required."
            )

        if len(description) > 5000:
            raise ValidationError(
                "Video description cannot exceed 5000 characters."
            )

        return description

    def clean_video_file(self):
        video_file = self.cleaned_data.get(
            "video_file"
        )

        _validate_uploaded_file_not_empty(
            video_file,
            "Please select a valid MP4 video file.",
        )

        filename = (
            getattr(
                video_file,
                "name",
                "",
            )
            or ""
        ).strip().lower()

        if not filename.endswith(".mp4"):
            raise ValidationError(
                (
                    "Invalid video format. "
                    "Only MP4 video files are allowed."
                )
            )

        content_type = (
            getattr(
                video_file,
                "content_type",
                "",
            )
            or ""
        ).strip().lower()

        rejected_types = {
            "text/plain",
            "text/html",
            "application/pdf",
            "application/zip",
            "application/x-zip-compressed",
            "image/jpeg",
            "image/png",
            "image/gif",
            "audio/mpeg",
            "audio/mp3",
            "audio/wav",
        }

        if content_type in rejected_types:
            raise ValidationError(
                "The selected file is not a valid MP4 video."
            )

        return video_file


# ============================================================
# VIDEO EDIT
# ============================================================


class VideoEditForm(forms.ModelForm):
    """
    Shared Video Edit form.

    Existing video file is optional during editing because the
    teacher/admin may edit only the name, description or order.

    If a replacement file is supplied, it must be a valid MP4.
    """

    class Meta:
        model = ChapterVideo

        fields = [
            "video_name",
            "video_description",
            "video_file",
            "video_order",
        ]

        widgets = {
            "video_name": forms.TextInput(
                attrs={
                    "maxlength": 255,
                    "autocomplete": "off",
                }
            ),
            "video_description": forms.Textarea(
                attrs={
                    "maxlength": 5000,
                    "rows": 4,
                }
            ),
            "video_file": forms.ClearableFileInput(
                attrs={
                    "accept": ".mp4,video/mp4",
                }
            ),
            "video_order": forms.NumberInput(
                attrs={
                    "min": 1,
                    "step": 1,
                }
            ),
        }

        error_messages = {
            "video_name": {
                "required": "Video name is required.",
                "max_length": (
                    "Video name cannot exceed 255 characters."
                ),
            },
            "video_description": {
                "required": "Video description is required.",
                "max_length": (
                    "Video description cannot exceed 5000 characters."
                ),
            },
            "video_order": {
                "required": "Video order is required.",
                "invalid": (
                    "Video order must be a positive whole number."
                ),
            },
        }

    def __init__(
        self,
        *args,
        chapter=None,
        instance=None,
        **kwargs,
    ):
        super().__init__(
            *args,
            instance=instance,
            **kwargs,
        )

        self.chapter = chapter

    def clean_video_name(self):
        video_name = _clean_text(
            self.cleaned_data.get("video_name")
        )

        if not video_name:
            raise ValidationError(
                "Video name is required."
            )

        if len(video_name) > 255:
            raise ValidationError(
                "Video name cannot exceed 255 characters."
            )

        if self.chapter is not None:
            duplicate_exists = (
                ChapterVideo.objects
                .filter(
                    chapter=self.chapter,
                    video_name__iexact=video_name,
                    is_deleted=False,
                )
                .exclude(
                    pk=self.instance.pk
                    if self.instance
                    and self.instance.pk
                    else None
                )
                .exists()
            )

            if duplicate_exists:
                raise ValidationError(
                    (
                        "A video with this name already "
                        "exists in this chapter."
                    )
                )

        return video_name

    def clean_video_description(self):
        description = _clean_text(
            self.cleaned_data.get(
                "video_description"
            )
        )

        if not description:
            raise ValidationError(
                "Video description is required."
            )

        if len(description) > 5000:
            raise ValidationError(
                "Video description cannot exceed 5000 characters."
            )

        return description

    def clean_video_order(self):
        order = self.cleaned_data.get(
            "video_order"
        )

        if order is None:
            raise ValidationError(
                "Video order is required."
            )

        if order < 1:
            raise ValidationError(
                "Video order must be at least 1."
            )

        return order

    def clean_video_file(self):
        video_file = self.cleaned_data.get(
            "video_file"
        )

        # Replacement file is optional during edit.
        if not video_file:
            return video_file

        _validate_uploaded_file_not_empty(
            video_file,
            "The selected video file is empty.",
        )

        filename = (
            getattr(
                video_file,
                "name",
                "",
            )
            or ""
        ).strip().lower()

        if not filename.endswith(".mp4"):
            raise ValidationError(
                (
                    "Invalid video format. "
                    "Only MP4 video files are allowed."
                )
            )

        content_type = (
            getattr(
                video_file,
                "content_type",
                "",
            )
            or ""
        ).strip().lower()

        rejected_types = {
            "text/plain",
            "text/html",
            "application/pdf",
            "application/zip",
            "application/x-zip-compressed",
            "image/jpeg",
            "image/png",
            "image/gif",
            "audio/mpeg",
            "audio/mp3",
            "audio/wav",
        }

        if content_type in rejected_types:
            raise ValidationError(
                "The selected file is not a valid MP4 video."
            )

        return video_file


# ============================================================
# PDF UPLOAD
# ============================================================


class PDFUploadForm(forms.ModelForm):
    """
    Shared PDF Upload form.

    Preserves the current backend rules:

        - PDF name required
        - maximum 255 characters
        - description required
        - maximum 5000 characters
        - PDF extension required
        - empty PDF rejected
        - known invalid MIME types rejected
        - thumbnail optional
        - thumbnail PNG/JPG/JPEG/WEBP only
    """

    class Meta:
        model = ChapterPDF

        fields = [
            "pdf_name",
            "pdf_description",
            "pdf_file",
            "pdf_thumbnail",
        ]

        widgets = {
            "pdf_name": forms.TextInput(
                attrs={
                    "maxlength": 255,
                    "autocomplete": "off",
                }
            ),
            "pdf_description": forms.Textarea(
                attrs={
                    "maxlength": 5000,
                    "rows": 4,
                }
            ),
            "pdf_file": forms.ClearableFileInput(
                attrs={
                    "accept": ".pdf,application/pdf",
                }
            ),
            "pdf_thumbnail": forms.ClearableFileInput(
                attrs={
                    "accept": ".png,.jpg,.jpeg,.webp,image/*",
                }
            ),
        }

        error_messages = {
            "pdf_name": {
                "required": "PDF name is required.",
                "max_length": (
                    "PDF name cannot exceed 255 characters."
                ),
            },
            "pdf_description": {
                "required": "PDF description is required.",
                "max_length": (
                    "PDF description cannot exceed 5000 characters."
                ),
            },
            "pdf_file": {
                "required": (
                    "Please select a valid PDF file."
                ),
            },
        }

    def __init__(
        self,
        *args,
        chapter=None,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)

        self.chapter = chapter

    def clean_pdf_name(self):
        pdf_name = _clean_text(
            self.cleaned_data.get("pdf_name")
        )

        if not pdf_name:
            raise ValidationError(
                "PDF name is required."
            )

        if len(pdf_name) > 255:
            raise ValidationError(
                "PDF name cannot exceed 255 characters."
            )

        if self.chapter is not None:
            duplicate_exists = (
                ChapterPDF.objects
                .filter(
                    chapter=self.chapter,
                    pdf_name__iexact=pdf_name,
                    is_deleted=False,
                )
                .exists()
            )

            if duplicate_exists:
                raise ValidationError(
                    (
                        "A PDF with this name already "
                        "exists in this chapter."
                    )
                )

        return pdf_name

    def clean_pdf_description(self):
        description = _clean_text(
            self.cleaned_data.get(
                "pdf_description"
            )
        )

        if not description:
            raise ValidationError(
                "PDF description is required."
            )

        if len(description) > 5000:
            raise ValidationError(
                "PDF description cannot exceed 5000 characters."
            )

        return description

    def clean_pdf_file(self):
        pdf_file = self.cleaned_data.get(
            "pdf_file"
        )

        _validate_uploaded_file_not_empty(
            pdf_file,
            "Please select a PDF file.",
        )

        filename = (
            getattr(
                pdf_file,
                "name",
                "",
            )
            or ""
        ).strip().lower()

        if not filename.endswith(".pdf"):
            raise ValidationError(
                (
                    "Invalid PDF format. "
                    "Only PDF files are allowed."
                )
            )

        content_type = (
            getattr(
                pdf_file,
                "content_type",
                "",
            )
            or ""
        ).strip().lower()

        rejected_types = {
            "image/jpeg",
            "image/png",
            "image/gif",
            "image/webp",
            "video/mp4",
            "audio/mpeg",
            "audio/wav",
            "application/zip",
            "application/x-zip-compressed",
            "text/plain",
            "text/html",
        }

        if content_type in rejected_types:
            raise ValidationError(
                "The selected file is not a valid PDF document."
            )

        return pdf_file

    def clean_pdf_thumbnail(self):
        thumbnail = self.cleaned_data.get(
            "pdf_thumbnail"
        )

        if not thumbnail:
            return thumbnail

        filename = (
            getattr(
                thumbnail,
                "name",
                "",
            )
            or ""
        ).strip().lower()

        extension = (
            "."
            + filename.rsplit(".", 1)[1]
            if "." in filename
            else ""
        )

        allowed_extensions = {
            ".png",
            ".jpg",
            ".jpeg",
            ".webp",
        }

        if extension not in allowed_extensions:
            raise ValidationError(
                (
                    "Invalid thumbnail format. "
                    "Only PNG, JPG, JPEG, and WEBP "
                    "images are allowed."
                )
            )

        if getattr(thumbnail, "size", 0) <= 0:
            raise ValidationError(
                "The selected thumbnail image is empty."
            )

        content_type = (
            getattr(
                thumbnail,
                "content_type",
                "",
            )
            or ""
        ).strip().lower()

        allowed_content_types = {
            "image/png",
            "image/jpeg",
            "image/webp",
        }

        if (
            content_type
            and content_type not in allowed_content_types
        ):
            raise ValidationError(
                (
                    "The selected thumbnail is not a "
                    "valid image. Use PNG, JPG, JPEG, or WEBP."
                )
            )

        return thumbnail


# ============================================================
# PDF EDIT
# ============================================================


class PDFEditForm(forms.ModelForm):
    """
    Shared PDF Edit form.

    PDF file and thumbnail are optional during editing.

    If replacement files are supplied, they are validated exactly
    like the upload form.
    """

    class Meta:
        model = ChapterPDF

        fields = [
            "pdf_name",
            "pdf_description",
            "pdf_file",
            "pdf_thumbnail",
            "pdf_order",
        ]

        widgets = {
            "pdf_name": forms.TextInput(
                attrs={
                    "maxlength": 255,
                    "autocomplete": "off",
                }
            ),
            "pdf_description": forms.Textarea(
                attrs={
                    "maxlength": 5000,
                    "rows": 4,
                }
            ),
            "pdf_file": forms.ClearableFileInput(
                attrs={
                    "accept": ".pdf,application/pdf",
                }
            ),
            "pdf_thumbnail": forms.ClearableFileInput(
                attrs={
                    "accept": ".png,.jpg,.jpeg,.webp,image/*",
                }
            ),
            "pdf_order": forms.NumberInput(
                attrs={
                    "min": 1,
                    "step": 1,
                }
            ),
        }

        error_messages = {
            "pdf_name": {
                "required": "PDF name is required.",
                "max_length": (
                    "PDF name cannot exceed 255 characters."
                ),
            },
            "pdf_description": {
                "required": "PDF description is required.",
                "max_length": (
                    "PDF description cannot exceed 5000 characters."
                ),
            },
            "pdf_order": {
                "required": "PDF order is required.",
                "invalid": (
                    "PDF order must be a positive whole number."
                ),
            },
        }

    def __init__(
        self,
        *args,
        chapter=None,
        instance=None,
        **kwargs,
    ):
        super().__init__(
            *args,
            instance=instance,
            **kwargs,
        )

        self.chapter = chapter

    def clean_pdf_name(self):
        pdf_name = _clean_text(
            self.cleaned_data.get("pdf_name")
        )

        if not pdf_name:
            raise ValidationError(
                "PDF name is required."
            )

        if len(pdf_name) > 255:
            raise ValidationError(
                "PDF name cannot exceed 255 characters."
            )

        if self.chapter is not None:
            duplicate_exists = (
                ChapterPDF.objects
                .filter(
                    chapter=self.chapter,
                    pdf_name__iexact=pdf_name,
                    is_deleted=False,
                )
                .exclude(
                    pk=self.instance.pk
                    if self.instance
                    and self.instance.pk
                    else None
                )
                .exists()
            )

            if duplicate_exists:
                raise ValidationError(
                    (
                        "A PDF with this name already "
                        "exists in this chapter."
                    )
                )

        return pdf_name

    def clean_pdf_description(self):
        description = _clean_text(
            self.cleaned_data.get(
                "pdf_description"
            )
        )

        if not description:
            raise ValidationError(
                "PDF description is required."
            )

        if len(description) > 5000:
            raise ValidationError(
                "PDF description cannot exceed 5000 characters."
            )

        return description

    def clean_pdf_order(self):
        order = self.cleaned_data.get(
            "pdf_order"
        )

        if order is None:
            raise ValidationError(
                "PDF order is required."
            )

        if order < 1:
            raise ValidationError(
                "PDF order must be at least 1."
            )

        return order

    def clean_pdf_file(self):
        pdf_file = self.cleaned_data.get(
            "pdf_file"
        )

        if not pdf_file:
            return pdf_file

        _validate_uploaded_file_not_empty(
            pdf_file,
            "The selected PDF file is empty.",
        )

        filename = (
            getattr(
                pdf_file,
                "name",
                "",
            )
            or ""
        ).strip().lower()

        if not filename.endswith(".pdf"):
            raise ValidationError(
                (
                    "Invalid PDF format. "
                    "Only PDF files are allowed."
                )
            )

        content_type = (
            getattr(
                pdf_file,
                "content_type",
                "",
            )
            or ""
        ).strip().lower()

        rejected_types = {
            "image/jpeg",
            "image/png",
            "image/gif",
            "image/webp",
            "video/mp4",
            "audio/mpeg",
            "audio/wav",
            "application/zip",
            "application/x-zip-compressed",
            "text/plain",
            "text/html",
        }

        if content_type in rejected_types:
            raise ValidationError(
                "The selected file is not a valid PDF document."
            )

        return pdf_file

    def clean_pdf_thumbnail(self):
        thumbnail = self.cleaned_data.get(
            "pdf_thumbnail"
        )

        if not thumbnail:
            return thumbnail

        filename = (
            getattr(
                thumbnail,
                "name",
                "",
            )
            or ""
        ).strip().lower()

        extension = (
            "."
            + filename.rsplit(".", 1)[1]
            if "." in filename
            else ""
        )

        allowed_extensions = {
            ".png",
            ".jpg",
            ".jpeg",
            ".webp",
        }

        if extension not in allowed_extensions:
            raise ValidationError(
                (
                    "Invalid thumbnail format. "
                    "Only PNG, JPG, JPEG, and WEBP "
                    "images are allowed."
                )
            )

        if getattr(thumbnail, "size", 0) <= 0:
            raise ValidationError(
                "The selected thumbnail image is empty."
            )

        content_type = (
            getattr(
                thumbnail,
                "content_type",
                "",
            )
            or ""
        ).strip().lower()

        allowed_content_types = {
            "image/png",
            "image/jpeg",
            "image/webp",
        }

        if (
            content_type
            and content_type not in allowed_content_types
        ):
            raise ValidationError(
                (
                    "The selected thumbnail is not a "
                    "valid image. Use PNG, JPG, JPEG, or WEBP."
                )
            )

        return thumbnail


# ============================================================
# QUIZ BASIC CREATE / EDIT
# ============================================================


class QuizForm(forms.ModelForm):
    """
    Shared Quiz Create/Edit form for the basic quiz fields.

    The question collection is intentionally handled separately
    because your current UI allows multiple dynamic questions
    inside one quiz.

    Fields:
        - quiz_name
        - quiz_description
        - attempt_limit
    """

    class Meta:
        model = ChapterQuiz

        fields = [
            "quiz_name",
            "quiz_description",
            "attempt_limit",
        ]

        widgets = {
            "quiz_name": forms.TextInput(
                attrs={
                    "maxlength": 255,
                    "autocomplete": "off",
                }
            ),
            "quiz_description": forms.Textarea(
                attrs={
                    "maxlength": 5000,
                    "rows": 5,
                }
            ),
            "attempt_limit": forms.NumberInput(
                attrs={
                    "min": 1,
                    "max": 100,
                    "step": 1,
                }
            ),
        }

        error_messages = {
            "quiz_name": {
                "required": "Quiz name is required.",
                "max_length": (
                    "Quiz name cannot exceed 255 characters."
                ),
            },
            "quiz_description": {
                "required": "Quiz description is required.",
            },
            "attempt_limit": {
                "required": "Maximum attempts is required.",
                "invalid": (
                    "Maximum attempts must be a positive whole number."
                ),
            },
        }

    def __init__(
        self,
        *args,
        chapter=None,
        instance=None,
        **kwargs,
    ):
        super().__init__(
            *args,
            instance=instance,
            **kwargs,
        )

        self.chapter = chapter

    def clean_quiz_name(self):
        quiz_name = _clean_text(
            self.cleaned_data.get("quiz_name")
        )

        if not quiz_name:
            raise ValidationError(
                "Quiz name is required."
            )

        if len(quiz_name) < 2:
            raise ValidationError(
                "Quiz name must contain at least 2 characters."
            )

        if len(quiz_name) > 255:
            raise ValidationError(
                "Quiz name cannot exceed 255 characters."
            )

        if self.chapter is not None:
            duplicate_exists = (
                ChapterQuiz.objects
                .filter(
                    chapter=self.chapter,
                    quiz_name__iexact=quiz_name,
                    is_deleted=False,
                )
                .exclude(
                    pk=self.instance.pk
                    if self.instance
                    and self.instance.pk
                    else None
                )
                .exists()
            )

            if duplicate_exists:
                raise ValidationError(
                    (
                        "A quiz with this name already "
                        "exists in this chapter."
                    )
                )

        return quiz_name

    def clean_quiz_description(self):
        description = _clean_text(
            self.cleaned_data.get(
                "quiz_description"
            )
        )

        if not description:
            raise ValidationError(
                "Quiz description is required."
            )

        if len(description) < 5:
            raise ValidationError(
                "Quiz description must contain at least 5 characters."
            )

        if len(description) > 5000:
            raise ValidationError(
                "Quiz description cannot exceed 5000 characters."
            )

        return description

    def clean_attempt_limit(self):
        attempt_limit = self.cleaned_data.get(
            "attempt_limit"
        )

        if attempt_limit is None:
            raise ValidationError(
                "Maximum attempts is required."
            )

        if attempt_limit < 1:
            raise ValidationError(
                "Maximum attempts must be greater than 0."
            )

        if attempt_limit > 100:
            raise ValidationError(
                "Maximum attempts cannot be greater than 100."
            )

        return attempt_limit


# ============================================================
# QUIZ QUESTION
# ============================================================


class QuizQuestionForm(forms.ModelForm):
    """
    Shared validation for one quiz question.

    The existing Teacher Course Builder uses:

        question_text
        marks
        option A
        option B
        option C
        option D
        correct option

    QuizOption stores A-D as separate database rows, so the
    form exposes them as normal fields for the HTML.
    """

    option_a = forms.CharField(
        max_length=500,
        required=True,
        strip=True,
    )

    option_b = forms.CharField(
        max_length=500,
        required=True,
        strip=True,
    )

    option_c = forms.CharField(
        max_length=500,
        required=True,
        strip=True,
    )

    option_d = forms.CharField(
        max_length=500,
        required=True,
        strip=True,
    )

    correct_option = forms.ChoiceField(
        choices=[
            ("A", "Option A"),
            ("B", "Option B"),
            ("C", "Option C"),
            ("D", "Option D"),
        ],
        required=True,
    )

    class Meta:
        model = QuizQuestion

        fields = [
            "question_text",
            "marks",
            "option_a",
            "option_b",
            "option_c",
            "option_d",
            "correct_option",
        ]

        widgets = {
            "question_text": forms.Textarea(
                attrs={
                    "maxlength": 10000,
                    "rows": 4,
                }
            ),
            "marks": forms.NumberInput(
                attrs={
                    "min": 1,
                    "max": 1000,
                    "step": 1,
                }
            ),
            "option_a": forms.TextInput(
                attrs={
                    "maxlength": 500,
                }
            ),
            "option_b": forms.TextInput(
                attrs={
                    "maxlength": 500,
                }
            ),
            "option_c": forms.TextInput(
                attrs={
                    "maxlength": 500,
                }
            ),
            "option_d": forms.TextInput(
                attrs={
                    "maxlength": 500,
                }
            ),
            "correct_option": forms.Select(),
        }

        error_messages = {
            "question_text": {
                "required": (
                    "Question text is required."
                ),
            },
            "marks": {
                "required": (
                    "Marks are required."
                ),
                "invalid": (
                    "Marks must be a positive whole number."
                ),
            },
        }

    def clean_question_text(self):
        question_text = _clean_text(
            self.cleaned_data.get(
                "question_text"
            )
        )

        if not question_text:
            raise ValidationError(
                "Question text is required."
            )

        if len(question_text) < 3:
            raise ValidationError(
                (
                    "Question must contain at least "
                    "3 characters."
                )
            )

        if len(question_text) > 10000:
            raise ValidationError(
                (
                    "Question cannot exceed "
                    "10000 characters."
                )
            )

        return question_text

    def clean_marks(self):
        marks = self.cleaned_data.get(
            "marks"
        )

        if marks is None:
            raise ValidationError(
                "Marks are required."
            )

        if marks < 1 or marks > 1000:
            raise ValidationError(
                "Marks must be between 1 and 1000."
            )

        return marks

    def _clean_option(self, field_name, label):
        value = _clean_text(
            self.cleaned_data.get(field_name)
        )

        if not value:
            raise ValidationError(
                f"Option {label} is required."
            )

        if len(value) > 500:
            raise ValidationError(
                (
                    f"Option {label} cannot exceed "
                    "500 characters."
                )
            )

        return value

    def clean_option_a(self):
        return self._clean_option(
            "option_a",
            "A",
        )

    def clean_option_b(self):
        return self._clean_option(
            "option_b",
            "B",
        )

    def clean_option_c(self):
        return self._clean_option(
            "option_c",
            "C",
        )

    def clean_option_d(self):
        return self._clean_option(
            "option_d",
            "D",
        )

    def clean_correct_option(self):
        correct_option = (
            self.cleaned_data.get(
                "correct_option"
            )
            or ""
        ).strip().upper()

        if correct_option not in {
            "A",
            "B",
            "C",
            "D",
        }:
            raise ValidationError(
                "Select exactly one correct answer."
            )

        return correct_option

    def clean(self):
        cleaned_data = super().clean()

        options = [
            cleaned_data.get("option_a"),
            cleaned_data.get("option_b"),
            cleaned_data.get("option_c"),
            cleaned_data.get("option_d"),
        ]

        normalized_options = [
            value.casefold()
            for value in options
            if value
        ]

        if (
            len(normalized_options) == 4
            and len(set(normalized_options)) != 4
        ):
            raise ValidationError(
                (
                    "All four answer options must "
                    "be different."
                )
            )

        return cleaned_data


# ============================================================
# QUIZ QUESTION EDIT
# ============================================================
#
# QuizQuestionForm is intentionally reusable for both:
#
#     create question
#     edit question
#
# The instance parameter determines whether Django updates
# an existing question or creates a new one.
#
# No separate duplicate QuestionEditForm is necessary.
# ============================================================


QuizQuestionEditForm = QuizQuestionForm


# ============================================================
# QUIZ QUESTION COLLECTION RULES
# ============================================================
#
# Your current Quiz Create/Edit UI allows dynamic questions.
#
# These rules belong to the Course Builder validation layer,
# but the dynamic collection itself is processed in the
# service/view because the browser submits fields such as:
#
#     question_1_question_text
#     question_1_option_a
#     question_1_option_b
#     question_1_option_c
#     question_1_option_d
#     question_1_correct
#     question_1_marks
#
# The common limits currently used by your working Teacher
# implementation are:
#
#     Minimum questions: 1
#     Maximum questions: 100
#     Maximum attempts: 100
#     Question text: 3-10000 characters
#     Option text: required, <= 500 characters
#     Marks: 1-1000
#     Correct answer: A/B/C/D
#
# We will create a dedicated QuizQuestionCollection / service
# parser in the next layer so that the same validation works
# for both Admin and Teacher without duplicating request.POST
# parsing.
# ============================================================


# ============================================================
# COMMON DELETE-REASON FORM
# ============================================================
#
# This is intentionally ONLY the common reason validation.
#
# IMPORTANT:
# The actual deletion permission is NOT here.
#
# Teacher:
#     submit deletion request
#
# Admin:
#     direct deletion / management
#
# Those workflows remain in their respective role-specific
# views/services.
# ============================================================


class DeleteReasonForm(forms.Form):

    delete_reason = forms.CharField(
        required=True,
        max_length=2000,
        strip=True,
        widget=forms.Textarea(
            attrs={
                "maxlength": 2000,
                "rows": 4,
            }
        ),
        error_messages={
            "required": (
                "Please enter a reason for requesting deletion."
            ),
            "max_length": (
                "Delete reason cannot exceed 2000 characters."
            ),
        },
    )

    def clean_delete_reason(self):
        reason = _clean_text(
            self.cleaned_data.get(
                "delete_reason"
            )
        )

        if not reason:
            raise ValidationError(
                "Please enter a reason for requesting deletion."
            )

        if len(reason) > 2000:
            raise ValidationError(
                "Delete reason cannot exceed 2000 characters."
            )

        return reason