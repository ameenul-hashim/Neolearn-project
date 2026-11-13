
from django.urls import path

from . import views


app_name = "discussions"


urlpatterns = [

    # Load chapter discussion
    path(
        "chapter/<int:chapter_id>/",
        views.chapter_discussion_view,
        name="chapter_discussion",
    ),

    # Create main comment or nested reply
    path(
        "chapter/<int:chapter_id>/comment/create/",
        views.create_discussion_comment_view,
        name="create_comment",
    ),

    # Edit comment or reply
    path(
        "comment/<int:comment_id>/edit/",
        views.edit_discussion_comment_view,
        name="edit_comment",
    ),

    # Delete comment or reply
    path(
        "comment/<int:comment_id>/delete/",
        views.delete_discussion_comment_view,
        name="delete_comment",
    ),

    # Like / dislike / remove reaction
    path(
        "comment/<int:comment_id>/reaction/",
        views.toggle_discussion_reaction_view,
        name="toggle_reaction",
    ),

]
