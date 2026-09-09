from django.db import transaction


def get_active_items(
    queryset,
    *,
    order_field,
    deleted_field="is_deleted",
):
    """
    Return active/non-deleted items ordered by their order field.

    This can be reused for:
    - CourseChapter
    - ChapterVideo
    - ChapterPDF
    - Other ordered Course Builder content
    """

    if deleted_field:
        queryset = queryset.filter(**{deleted_field: False})

    return queryset.order_by(order_field, "pk")


def get_next_order(
    queryset,
    *,
    order_field,
    deleted_field="is_deleted",
):
    """
    Return the next available order number.

    Example:

        Existing:
            1, 2, 3, 4, 5

        New item:
            6

    If there are no active items:

        New item:
            1
    """

    active_items = get_active_items(
        queryset,
        order_field=order_field,
        deleted_field=deleted_field,
    )

    last_item = active_items.last()

    if last_item is None:
        return 1

    current_order = getattr(
        last_item,
        order_field,
        0,
    ) or 0

    return current_order + 1


@transaction.atomic
def move_item(
    queryset,
    item,
    *,
    order_field,
    new_order,
    deleted_field="is_deleted",
    start=1,
):
    """
    Move an active item to a new position.

    The affected items are automatically shifted.

    Example:

        Before:
            1 A
            2 B
            3 C
            4 D
            5 E

        Move E -> 2

        After:
            1 A
            2 E
            3 B
            4 C
            5 D

    The same logic works for moving an item downward.

    Returns:
        (old_order, new_order)
    """

    if item is None:
        raise ValueError("An item is required.")

    old_order = getattr(
        item,
        order_field,
        None,
    )

    if old_order is None:
        raise ValueError(
            f"The item does not have a valid "
            f"'{order_field}' value."
        )

    active_items = list(
        get_active_items(
            queryset,
            order_field=order_field,
            deleted_field=deleted_field,
        )
    )

    if item not in active_items:
        raise ValueError(
            "The item must belong to the active ordering queryset."
        )

    total_items = len(active_items)

    if total_items == 0:
        return old_order, old_order

    last_order = start + total_items - 1

    if new_order < start:
        new_order = start

    if new_order > last_order:
        new_order = last_order

    if old_order == new_order:
        return old_order, new_order

    # Moving UP.
    if new_order < old_order:

        for other_item in active_items:

            if other_item.pk == item.pk:
                continue

            other_order = getattr(
                other_item,
                order_field,
            )

            if new_order <= other_order < old_order:
                setattr(
                    other_item,
                    order_field,
                    other_order + 1,
                )

                other_item.save(
                    update_fields=[order_field]
                )

    # Moving DOWN.
    else:

        for other_item in active_items:

            if other_item.pk == item.pk:
                continue

            other_order = getattr(
                other_item,
                order_field,
            )

            if old_order < other_order <= new_order:
                setattr(
                    other_item,
                    order_field,
                    other_order - 1,
                )

                other_item.save(
                    update_fields=[order_field]
                )

    setattr(
        item,
        order_field,
        new_order,
    )

    item.save(
        update_fields=[order_field]
    )

    return old_order, new_order


@transaction.atomic
def remove_item_from_order(
    queryset,
    item,
    *,
    order_field,
    deleted_field="is_deleted",
):
    """
    Remove an item from the active ordering sequence.

    This does NOT delete the database object.

    It only closes the ordering gap.

    Example:

        Before:
            1 A
            2 B
            3 C
            4 D

        Remove C:

            1 A
            2 B
            3 D

    The actual deletion or soft deletion is handled
    by the appropriate view.

    Returns:
        old_order
    """

    if item is None:
        raise ValueError("An item is required.")

    old_order = getattr(
        item,
        order_field,
        None,
    )

    if old_order is None:
        raise ValueError(
            f"The item does not have a valid "
            f"'{order_field}' value."
        )

    active_items = list(
        get_active_items(
            queryset,
            order_field=order_field,
            deleted_field=deleted_field,
        )
    )

    if item not in active_items:
        return old_order

    for other_item in active_items:

        if other_item.pk == item.pk:
            continue

        other_order = getattr(
            other_item,
            order_field,
        )

        if other_order > old_order:
            setattr(
                other_item,
                order_field,
                other_order - 1,
            )

            other_item.save(
                update_fields=[order_field]
            )

    return old_order