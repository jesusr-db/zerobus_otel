CREATE TABLE main.jmr_demo.otel_spans (
  trace_id STRING,
  span_id STRING,
  trace_state STRING,
  parent_span_id STRING,
  flags INT,
  name STRING,
  kind STRING,  
  start_time_unix_nano LONG,
  end_time_unix_nano LONG,
  attributes MAP<STRING, STRING>,
  dropped_attributes_count INT,
  events ARRAY<STRUCT<
    time_unix_nano: LONG,
    name: STRING,
    attributes: MAP<STRING, STRING>,
    dropped_attributes_count: INT
  >>,
  dropped_events_count INT,
  links ARRAY<STRUCT<
    trace_id: STRING,
    span_id: STRING,
    trace_state: STRING,
    attributes: MAP<STRING, STRING>,
    dropped_attributes_count: INT,
    flags: INT
  >>,
  dropped_links_count INT,
  status STRUCT<
    message: STRING,
    code: STRING
  >,
  resource STRUCT<
    attributes: MAP<STRING, STRING>,
    dropped_attributes_count: INT
  >,
  resource_schema_url STRING,
  instrumentation_scope STRUCT<
    name: STRING,
    version: STRING,
    attributes: MAP<STRING, STRING>,
    dropped_attributes_count: INT
  >,
  span_schema_url STRING
) USING DELTA
TBLPROPERTIES (
  'otel.schemaVersion' = 'v1',
  'delta.enableRowTracking' = 'false'
)