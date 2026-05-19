# Database and Vector Indexing Guide

This document outlines the indexing strategies implemented in DocQuery to ensure high performance, scalability, and absolute tenant data isolation in production deployments.

---

## 1. Vector Database (Qdrant)

Qdrant utilizes payload indexes to filter query points before calculating vector similarities. In DocQuery, these indexes are validated and created at application startup in `Backend/Database/qdrant.py`.

| Field Name | Index Type | Purpose | Production Benefit |
| :--- | :--- | :--- | :--- |
| **`organization_id`** | `KEYWORD` | Tenant boundary validation. | Guarantees multi-tenant data isolation by restricting vector matching to the user's workspace. |
| **`document_id`** | `KEYWORD` | Document-level grouping. | Accelerates bulk updates and fast cascading deletions of document embeddings. |
| **`upload_user_id`** | `KEYWORD` | Creator attribution. | Speeds up user-specific search scope restrictions. |
| **`status`** | `KEYWORD` | Privacy level access control. | Allows public users to query only `"public"` documents, while securely excluding `"private"` data. |

### How it is configured (`Backend/Database/qdrant.py`):
```python
# Ensure payload indexes exist for filtering
qdrant_client.create_payload_index(
    collection_name=COLLECTION_NAME,
    field_name="organization_id",
    field_schema=PayloadSchemaType.KEYWORD,
)
qdrant_client.create_payload_index(
    collection_name=COLLECTION_NAME,
    field_name="document_id",
    field_schema=PayloadSchemaType.KEYWORD,
)
qdrant_client.create_payload_index(
    collection_name=COLLECTION_NAME,
    field_name="upload_user_id",
    field_schema=PayloadSchemaType.KEYWORD,
)
qdrant_client.create_payload_index(
    collection_name=COLLECTION_NAME,
    field_name="status",
    field_schema=PayloadSchemaType.KEYWORD,
)
```

---

## 2. NoSQL Database (MongoDB)

MongoDB indexes prevent full collection scans. In DocQuery, these are verified and constructed asynchronously at startup inside `Backend/Database/mongodb.py` during `connect_to_mongo()`.

### Index Definitions by Collection

#### 1. `users` Collection
* **`email` (Unique Index)**
  * **Configuration**: `{"email": 1}` with `unique=True`
  * **Purpose**: Enforces distinct user identities and speeds up authentication/login lookup queries.
* **`subscribed_org_ids` (Multikey Index)**
  * **Configuration**: `{"subscribed_org_ids": 1}`
  * **Purpose**: Speeds up subscription checks and authorization queries for public users.

#### 2. `queries` (Chat History) Collection
* **`user_id` + `timestamp` (Compound Index)**
  * **Configuration**: `[("user_id", 1), ("timestamp", -1)]`
  * **Purpose**: Optimizes fetching user conversation histories sorted by the most recent interactions.
* **`organization_id` (Index)**
  * **Configuration**: `{"organization_id": 1}`
  * **Purpose**: Accelerates workspace-wide audit logs and admin analytics dashboard queries.
* **`conversation_id` (Index)**
  * **Configuration**: `{"conversation_id": 1}`
  * **Purpose**: Speeds up fetching the ordered sequence of messages in a single chat thread.

#### 3. `documents` Collection
* **`organization_id` (Index)**
  * **Configuration**: `{"organization_id": 1}`
  * **Purpose**: Speeds up loading the files dashboard inside a specific workspace.
* **`document_id` (Unique Index)**
  * **Configuration**: `{"document_id": 1}` with `unique=True`
  * **Purpose**: Ensures fast file matching between MongoDB metadata and Qdrant points.

### How it is configured (`Backend/Database/mongodb.py`):
```python
async def ensure_mongo_indexes():
    """Ensure database indexes exist in MongoDB for production performance."""
    if mongodb.db is None:
        return

    try:
        # 1. Users collection indexes
        await mongodb.db.users.create_index("email", unique=True)
        await mongodb.db.users.create_index("subscribed_org_ids")
        
        # 2. Queries collection indexes
        await mongodb.db.queries.create_index([("user_id", 1), ("timestamp", -1)])
        await mongodb.db.queries.create_index("organization_id")
        await mongodb.db.queries.create_index("conversation_id")

        # 3. Documents collection indexes
        await mongodb.db.documents.create_index("organization_id")
        await mongodb.db.documents.create_index("document_id", unique=True)
        
    except Exception as exc:
        logger.warning("Failed to create MongoDB indexes: %s. Continuing startup...", str(exc))
```
