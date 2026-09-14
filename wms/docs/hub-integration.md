# Hub ERP integration

> Added for the Hub ERP integration on 2026-09-14. Upstream Sentry WMS remains the warehouse execution service; Hub owns submissions, category master data, and the cross-system workflow state.

## 1. Database order and item mapping

Run the normal Sentry schema/migrations, including `db/migrations/082_hub_item_master_fields.sql`.

`items.category_id` is a logical reference to `hub.category.id`. WMS does not create or migrate the `hub` schema. A write-time trigger enforces that every non-null value points to an active second-level category (`parent_id IS NOT NULL`). This avoids making WMS bootstrap depend on Hub migration order. If `hub.category` is unavailable, writes with a non-null `category_id` fail with SQLSTATE `23503`; legacy rows with a null mapping remain usable.

Existing `items.category` text is preserved. Hub must perform the one-time review/backfill from that free text to `category_id`; the migration cannot infer category identity safely. Referenced categories should be disabled with `is_active=false`, not hard-deleted.

Existing WMS items receive `code_status='active'`. New Hub items may be `draft` or `active`; Hub remains responsible for preventing draft SKU use in submission lines.

## 2. Environment

Copy `.env.example` to `.env` and set the required secrets. The integration-specific WMS settings are:

```dotenv
SENTRY_INBOUND_MAPPINGS_DIR=/db/mappings
SENTRY_INBOUND_MAX_BODY_KB=256
INBOUND_RATE_LIMIT_PER_MINUTE=500
DISPATCHER_ENABLED=true
```

For local-only HTTP webhook testing, `SENTRY_ALLOW_HTTP_WEBHOOKS=true` is permitted only outside production. Production subscriptions must use HTTPS. Never store the inbound token or webhook HMAC secret in the repository.

## 3. Enable the Hub inbound source

1. Copy `db/mappings/hub.yaml.template` to `db/mappings/hub.yaml`.
2. Add the source allowlist row:

   ```sql
   INSERT INTO inbound_source_systems_allowlist (source_system, kind)
   VALUES ('hub', 'internal_tool')
   ON CONFLICT (source_system) DO NOTHING;
   ```

3. In **Admin > Tokens**, issue a token with:
   - `source_system`: `hub`
   - `inbound_resources`: `items`, `sales_orders`
   - warehouse scope restricted to the warehouse IDs Hub may target
4. Store the plaintext token in Hub's secret store. It is shown only once.
5. Restart the API after creating or changing the mapping file; mappings load at boot.

## 4. Push an item before its first order

Hub must push every active SKU before sending an order that references it. The envelope is common to all inbound resources:

```http
POST /api/v1/inbound/items
X-WMS-Token: <hub-wms-token>
Content-Type: application/json
```

```json
{
  "external_id": "A001-1",
  "external_version": "2026-09-14T10:00:00Z",
  "source_payload": {
    "sku_code": "A001-1",
    "item_name": "玻璃杯",
    "category_id": 101,
    "code_status": "active",
    "spec_name": null,
    "barcode": null,
    "is_active": true
  }
}
```

The inbound write creates `cross_system_mappings(source_system='hub', source_type='item', source_id='A001-1')`. Sales-order line lookup uses that mapping, not a name match.

## 5. Push one sales order per submission order

Endpoint: `POST /api/v1/inbound/sales_orders` with the same `X-WMS-Token` header.

Use `submission_order.external_id` as the envelope `external_id`; use its monotonic update timestamp as `external_version`. One request represents one order number, even when the Hub submission batch contains multiple orders.

```json
{
  "external_id": "0b4bd2e2-3f16-45f4-8b58-1cb4e5e99430",
  "external_version": "2026-09-14T10:05:00Z",
  "source_payload": {
    "order_no": "ORDER-10001",
    "warehouse_id": 1,
    "remark": "Handle with care",
    "order_origin": "hub",
    "status": "OPEN",
    "lines": [
      {"line_no": 1, "sku_code": "A001-1", "qty": 2}
    ]
  }
}
```

The endpoint is idempotent on `(source_system, external_id, external_version)`. A newer version may replace lines only before allocation/pick/pack/ship activity. A missing item mapping returns `409 cross_system_lookup_miss`; push the item first, then retry.

## 6. Configure callbacks to Hub

1. Ensure `webhook-dispatcher` is running with `DISPATCHER_ENABLED=true`.
2. In **Admin > Integrations**, create/select the Hub connector record.
3. In **Admin > Webhooks**, create a subscription targeting Hub's `POST /webhooks/sentry` endpoint.
4. Set the event filter to:

   ```json
   {
     "event_types": [
       "pick.confirmed",
       "pack.confirmed",
       "ship.confirmed",
       "backorder.opened",
       "backorder.fulfillable",
       "return.received",
       "inventoryadjusted.completed"
     ]
   }
   ```

5. Save the one-time webhook secret in Hub's secret store.

Hub must verify `X-Sentry-Signature` against the exact raw request bytes and `X-Sentry-Timestamp`, reject requests outside a five-minute replay window, and deduplicate only by `event_id`. Delivery is at least once; return a 2xx only after the event and its state change are committed together.

Use `aggregate_id` / the source external IDs in the event payload to resolve `submission_order.external_id`. For `ship.confirmed`, persist every package tracking number and mark the batch complete only when all child orders are shipped or cancelled.

## 7. Manual shipping

The warehouse uses `GET /api/shipping/order/<barcode>` followed by `POST /api/shipping/fulfill`. Both the standalone **Ship** PDA screen and the combined **Pack / Ship** screen accept operator-entered `carrier` and `tracking_number`. This path writes the fulfillment, updates the order, and emits `ship.confirmed`; it does not call dockd or any carrier API and requires no carrier credentials.

The separate `/api/v1/dockd/*` integration remains upstream code and is not part of the Hub workflow. Do not issue a token with the `dockd.dispatch` endpoint scope for this deployment.
