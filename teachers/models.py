"""
Teacher App Models
==================

The Teacher app does NOT own the Teacher, Batch, Subject, or
Teacher assignment models.

Those models are created and managed by the Admin app.

Admin is responsible for:
    - Creating teachers
    - Creating batches
    - Creating subjects
    - Assigning teachers to batches
    - Assigning teachers to subjects
    - Managing teacher access

Teacher is responsible for:
    - Teacher authentication
    - Teacher dashboard
    - Viewing assigned batches
    - Viewing assigned subjects
    - Accessing the Courses module
    - Managing course content through the Courses module

Therefore, the actual database models remain in:

    admins.models

This file only re-exports those models so existing Teacher-side
code can continue importing them from teachers.models without
creating duplicate Django models.
"""

from admins.models import (
    Teacher,
    TeacherBatch,
    TeacherSubject,
    Batch,
    Subject,
)


__all__ = [
    "Teacher",
    "TeacherBatch",
    "TeacherSubject",
    "Batch",
    "Subject",
]

