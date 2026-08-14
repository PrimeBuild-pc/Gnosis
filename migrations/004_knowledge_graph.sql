CREATE TABLE IF NOT EXISTS entities (
    id bigserial PRIMARY KEY,
    type text NOT NULL,
    name text NOT NULL,
    normalized_name text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (type, normalized_name)
);

CREATE TABLE IF NOT EXISTS entity_mentions (
    entity_id bigint NOT NULL REFERENCES entities(id) ON DELETE CASCADE,
    message_id bigint NOT NULL REFERENCES messages(id) ON DELETE CASCADE,
    created_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (entity_id, message_id)
);
CREATE INDEX IF NOT EXISTS entity_mentions_message_idx ON entity_mentions (message_id);

CREATE TABLE IF NOT EXISTS entity_relations (
    id bigserial PRIMARY KEY,
    source_entity_id bigint NOT NULL REFERENCES entities(id) ON DELETE CASCADE,
    target_entity_id bigint NOT NULL REFERENCES entities(id) ON DELETE CASCADE,
    relation text NOT NULL,
    message_id bigint REFERENCES messages(id) ON DELETE SET NULL,
    created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS entity_relations_source_idx ON entity_relations (source_entity_id);
CREATE INDEX IF NOT EXISTS entity_relations_target_idx ON entity_relations (target_entity_id);
