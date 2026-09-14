STATUS_CANCELLED = 0
STATUS_WAREHOUSE_REVIEW = 1
STATUS_SKU_CONFIRM = 2
STATUS_QTY_CONFIRM = 3
STATUS_PENDING_DISPATCH = 4
STATUS_IN_PROGRESS = 5
STATUS_COMPLETED = 6

OPS_MUTABLE_STATUSES = {1, 2, 3}
ORDER_TERMINAL_STATUSES = {"shipped", "cancelled"}
SUPPORTED_WEBHOOK_EVENTS = {
    "pick.confirmed",
    "pack.confirmed",
    "ship.confirmed",
    "backorder.opened",
    "backorder.fulfillable",
    "inventoryadjusted.completed",
    "return.received",
}
