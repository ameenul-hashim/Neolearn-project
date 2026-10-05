from django.db import transaction
from django.db.models import F


# ============================================================
# GET NEXT ORDER
# ============================================================

def get_next_order(queryset, order_field):
    """
    Return the next available order number.

    Example:
        Existing orders: 1, 2, 3, 4, 5
        New item order: 6

    If there are no existing items:
        New item order: 1
    """

    last_item = queryset.order_by(
        f"-{order_field}"
    ).first()

    if last_item is None:
        return 1

    return getattr(last_item, order_field) + 1


# ============================================================
# VALIDATE ORDER
# ============================================================

def validate_order(queryset, requested_order):
    """
    Validate an order number.

    Valid values:
        1 <= requested_order <= total_items

    Example:
        Existing items: 1, 2, 3, 4, 5

        1 -> valid
        3 -> valid
        5 -> valid
        0 -> invalid
        -1 -> invalid
        6 -> invalid
    """

    if requested_order < 1:
        raise ValueError(
            "Order must be greater than or equal to 1."
        )

    total_items = queryset.count()

    if total_items == 0:
        raise ValueError(
            "No items are available for ordering."
        )

    if requested_order > total_items:
        raise ValueError(
            f"Order must be between 1 and {total_items}."
        )

    return True


# ============================================================
# MOVE / CHANGE ORDER
# ============================================================

@transaction.atomic
def move_item(
    item,
    queryset,
    order_field,
    new_order,
):
    """
    Change the order of an existing item.

    Example:

        Existing:
            1
            2
            3
            4
            5

        Move item 3 -> 5

        Result:
            1
            2
            4 -> 3
            5 -> 4
            moved item -> 5

        Final:
            1
            2
            3
            4
            5


    Example:

        Existing:
            1
            2
            3
            4
            5

        Move item 5 -> 3

        Result:
            1
            2
            moved item -> 3
            old 3 -> 4
            old 4 -> 5

        Final:
            1
            2
            3
            4
            5
    """

    old_order = getattr(
        item,
        order_field,
    )

    # --------------------------------------------------------
    # If the order has not changed
    # --------------------------------------------------------

    if old_order == new_order:
        return old_order, new_order

    # --------------------------------------------------------
    # Validate BEFORE changing anything
    # --------------------------------------------------------

    validate_order(
        queryset=queryset,
        requested_order=new_order,
    )

    # --------------------------------------------------------
    # Moving UP
    #
    # Example:
    #
    # 1
    # 2
    # 3  <- moving to 1
    # 4
    # 5
    #
    # Result:
    #
    # 1  <- moved item
    # 2  <- old 1
    # 3  <- old 2
    # 4
    # 5
    # --------------------------------------------------------

    if new_order < old_order:

        queryset.filter(
            **{
                f"{order_field}__gte": new_order,
                f"{order_field}__lt": old_order,
            }
        ).exclude(
            pk=item.pk
        ).update(
            **{
                order_field: F(order_field) + 1
            }
        )

    # --------------------------------------------------------
    # Moving DOWN
    #
    # Example:
    #
    # 1
    # 2
    # 3
    # 4
    # 5  <- moving to 3
    #
    # Result:
    #
    # 1
    # 2
    # 3  <- old 4
    # 4  <- old 5
    # 5  <- moved item
    # --------------------------------------------------------

    else:

        queryset.filter(
            **{
                f"{order_field}__gt": old_order,
                f"{order_field}__lte": new_order,
            }
        ).exclude(
            pk=item.pk
        ).update(
            **{
                order_field: F(order_field) - 1
            }
        )

    # --------------------------------------------------------
    # Finally update the moved item
    # --------------------------------------------------------

    setattr(
        item,
        order_field,
        new_order,
    )

    item.save(
        update_fields=[order_field]
    )

    return old_order, new_order


# ============================================================
# CLOSE ORDER GAP
# ============================================================

@transaction.atomic
def close_order_gap(
    queryset,
    order_field,
    deleted_order,
):
    """
    Close the gap after an item is deleted.

    Example:

        Before:
            1
            2
            3  <- deleted
            4
            5

        After:
            1
            2
            3
            4
    """

    queryset.filter(
        **{
            f"{order_field}__gt": deleted_order
        }
    ).update(
        **{
            order_field: F(order_field) - 1
        }
    )


# ============================================================
# REMOVE ITEM ORDER AND CLOSE GAP
# ============================================================

@transaction.atomic
def remove_item_and_close_gap(
    item,
    queryset,
    order_field,
):
    """
    Prepare ordering for deletion.

    This function does NOT delete the object itself.

    The actual delete/permission/delete-request logic stays
    inside the appropriate view.

    This function only closes the ordering gap.
    """

    deleted_order = getattr(
        item,
        order_field,
    )

    # Exclude the item that is going to be deleted.
    remaining_items = queryset.exclude(
        pk=item.pk
    )

    close_order_gap(
        queryset=remaining_items,
        order_field=order_field,
        deleted_order=deleted_order,
    )

    return deleted_order