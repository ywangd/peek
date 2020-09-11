// 'oss/mappings'
for mappings in [0] {
specService addEndpointDescription('put_mapping', {
priority: 10, // collides with put doc by id
data_autocomplete_rules: {
__template: {
properties: {
FIELD: {},
},
},
_source: {
enabled: BOOLEAN,
},
_all: {
enabled: BOOLEAN,
},
_field_names: {
index: BOOLEAN,
},
_routing: {
required: BOOLEAN,
},
_index: {
enabled: BOOLEAN,
},
_parent: {
__template: {
type: '',
},
type: '{type}',
},
_timestamp: {
enabled: BOOLEAN,
format: 'YYYY-MM-dd',
default: '',
},
dynamic_date_formats: ['yyyy-MM-dd'],
date_detection: BOOLEAN,
numeric_detection: BOOLEAN,
properties: {
'*': {
type: {
__one_of: [
'text',
'keyword',
'float',
'half_float',
'scaled_float',
'double',
'byte',
'short',
'integer',
'long',
'date',
'boolean',
'binary',
'object',
'nested',
'geo_point',
'geo_shape',
],
},
store: BOOLEAN,
index: BOOLEAN,
term_vector: {
__one_of: ['no', 'yes', 'with_offsets', 'with_positions', 'with_positions_offsets'],
},
boost: 1.0,
null_value: '',
doc_values: BOOLEAN,
eager_global_ordinals: BOOLEAN,
norms: BOOLEAN,
coerce: BOOLEAN,
index_options: {
__one_of: ['docs', 'freqs', 'positions'],
},
analyzer: 'standard',
search_analyzer: 'standard',
include_in_all: {
__one_of: [false, true],
},
ignore_above: 10,
position_increment_gap: 0,
precision_step: 4,
ignore_malformed: BOOLEAN,
scaling_factor: 100,
lat_lon: {
__one_of: [true, false],
},
geohash: {
__one_of: [true, false],
},
geohash_precision: '1m',
geohash_prefix: {
__one_of: [true, false],
},
validate: {
__one_of: [true, false],
},
validate_lat: {
__one_of: [true, false],
},
validate_lon: {
__one_of: [true, false],
},
normalize: {
__one_of: [true, false],
},
normalize_lat: {
__one_of: [true, false],
},
normalize_lon: {
__one_of: [true, false],
},
tree: {
__one_of: ['geohash', 'quadtree'],
},
precision: '5km',
tree_levels: 12,
distance_error_pct: 0.025,
orientation: 'ccw',
format: {
__one_of: _.flatten([
_.map(
[
'date',
'date_time',
'date_time_no_millis',
'ordinal_date',
'ordinal_date_time',
'ordinal_date_time_no_millis',
'time',
'time_no_millis',
't_time',
't_time_no_millis',
'week_date',
'week_date_time',
'week_date_time_no_millis',
],
function (s) {
"return": ['basic_' + s, 'strict_' + s]
}
),
[
'date',
'date_hour',
'date_hour_minute',
'date_hour_minute_second',
'date_hour_minute_second_fraction',
'date_hour_minute_second_millis',
'date_optional_time',
'date_time',
'date_time_no_millis',
'hour',
'hour_minute',
'hour_minute_second',
'hour_minute_second_fraction',
'hour_minute_second_millis',
'ordinal_date',
'ordinal_date_time',
'ordinal_date_time_no_millis',
'time',
'time_no_millis',
't_time',
't_time_no_millis',
'week_date',
'week_date_time',
'weekDateTimeNoMillis',
'week_year',
'weekyearWeek',
'weekyearWeekDay',
'year',
'year_month',
'year_month_day',
'epoch_millis',
'epoch_second',
],
]),
},
fielddata: {
filter: {
regex: '',
frequency: {
min: 0.001,
max: 0.1,
min_segment_size: 500,
},
},
},
similarity: {
__one_of: ['default', 'BM25'],
},
properties: {
__scope_link: 'put_mapping.{type}.properties',
},
fields: {
'*': {
__scope_link: 'put_mapping.type.properties.field',
},
},
copy_to: { __one_of: ['{field}', ['{field}']] },
include_in_parent: BOOLEAN,
include_in_root: BOOLEAN,
},
},
},
})
}
// 'oss/aggregations'
let significantTermsArgs = {
__template: {
field: '',
},
field: '{field}',
size: 10,
shard_size: 10,
shard_min_doc_count: 10,
min_doc_count: 10,
include: { __one_of: ['*', { pattern: '', flags: '' }] },
exclude: { __one_of: ['*', { pattern: '', flags: '' }] },
execution_hint: {
__one_of: ['map', 'global_ordinals', 'global_ordinals_hash'],
},
background_filter: {
__scope_link: 'GLOBAL.filter',
},
mutual_information: {
include_negatives: { __one_of: [true, false] },
},
chi_square: {
include_negatives: { __one_of: [true, false] },
background_is_superset: { __one_of: [true, false] },
},
percentage: {},
gnd: {
background_is_superset: { __one_of: [true, false] },
},
script_heuristic: {
__template: {
script: '_subset_freq/(_superset_freq - _subset_freq + 1)',
},
script: {
},
},
}
let simple_metric = {
__template: { field: '' },
field: '{field}',
missing: 0,
script: {
},
}
let field_metric = {
__template: { field: '' },
field: '{field}',
}
let gap_policy = {
__one_of: ['skip', 'insert_zeros'],
}
let simple_pipeline = {
__template: {
buckets_path: '',
},
buckets_path: '',
format: '',
"gap_policy": gap_policy,
}
let rules = {
'*': {
aggs: {
__template: {
NAME: {
AGG_TYPE: {},
},
},
},
adjacency_matrix: {
filters: {},
},
diversified_sampler: {
shard_size: '',
field: '',
},
min: simple_metric,
max: simple_metric,
avg: simple_metric,
sum: simple_metric,
stats: simple_metric,
extended_stats: simple_metric,
value_count: {
__template: {
field: '',
},
field: '{field}',
script: {
},
},
global: {},
filter: {},
filters: {
__template: {
filters: {
NAME: {},
},
},
filters: {
'*': { __scope_link: 'GLOBAL.filter' },
},
other_bucket: { __one_of: [true, false] },
other_bucket_key: '',
},
missing: field_metric,
nested: {
__template: {
path: '',
},
path: '',
},
reverse_nested: {
__template: {
path: '',
},
path: '',
},
terms: {
__template: {
field: '',
size: 10,
},
field: '{field}',
size: 10,
shard_size: 10,
order: {
__template: {
_key: 'asc',
},
_term: { __one_of: ['asc', 'desc'] },
_count: { __one_of: ['asc', 'desc'] },
'*': { __one_of: ['asc', 'desc'] },
},
min_doc_count: 10,
script: {
},
include: '.*',
exclude: '.*',
execution_hint: {
__one_of: [
'map',
'global_ordinals',
'global_ordinals_hash',
'global_ordinals_low_cardinality',
],
},
show_term_doc_count_error: { __one_of: [true, false] },
collect_mode: { __one_of: ['depth_first', 'breadth_first'] },
missing: '',
},
significant_text: {
"...": @significantTermsArgs,
filter_duplicate_text: '__flag__',
},
significant_terms: significantTermsArgs,
range: {
__template: {
field: '',
ranges: [{ from: 50, to: 100 }],
},
field: '{field}',
ranges: [{ to: 50, from: 100, key: '' }],
keyed: { __one_of: [true, false] },
script: {
},
},
date_range: {
__template: {
field: '',
ranges: [{ from: 'now-10d/d', to: 'now' }],
},
field: '{field}',
format: 'MM-yyy',
ranges: [{ to: '', from: '', key: '' }],
keyed: { __one_of: [true, false] },
script: {
},
},
ip_range: {
__template: {
field: '',
ranges: [{ from: '10.0.0.5', to: '10.0.0.10' }],
},
field: '{field}',
format: 'MM-yyy',
ranges: [{ to: '', from: '', key: '', mask: '10.0.0.127/25' }],
keyed: { __one_of: [true, false] },
script: {
},
},
histogram: {
__template: {
field: 'price',
interval: 50,
},
field: '{field}',
interval: 50,
extended_bounds: {
__template: {
min: 0,
max: 50,
},
min: 0,
max: 50,
},
min_doc_count: 0,
order: {
__template: {
_key: 'asc',
},
_key: { __one_of: ['asc', 'desc'] },
_count: { __one_of: ['asc', 'desc'] },
'*': { __one_of: ['asc', 'desc'] },
},
keyed: { __one_of: [true, false] },
missing: 0,
},
date_histogram: {
__template: {
field: 'date',
interval: 'month',
},
field: '{field}',
interval: {
__one_of: ['year', 'quarter', 'week', 'day', 'hour', 'minute', 'second'],
},
min_doc_count: 0,
extended_bounds: {
__template: {
min: 'now/d',
max: 'now/d',
},
min: 'now/d',
max: 'now/d',
},
order: {
__template: {
_key: 'asc',
},
_key: { __one_of: ['asc', 'desc'] },
_count: { __one_of: ['asc', 'desc'] },
'*': { __one_of: ['asc', 'desc'] },
},
keyed: { __one_of: [true, false] },
pre_zone: '-01:00',
post_zone: '-01:00',
pre_zone_adjust_large_interval: { __one_of: [true, false] },
factor: 1000,
pre_offset: '1d',
post_offset: '1d',
format: 'yyyy-MM-dd',
time_zone: '00:00',
missing: '',
},
geo_distance: {
__template: {
field: 'location',
origin: { lat: 52.376, lon: 4.894 },
ranges: [{ from: 100, to: 300 }],
},
field: '{field}',
origin: { lat: 0.0, lon: 0.0 },
unit: { __one_of: ['mi', 'km', 'in', 'yd', 'm', 'cm', 'mm'] },
ranges: [{ from: 50, to: 100 }],
distance_type: { __one_of: ['arc', 'sloppy_arc', 'plane'] },
},
geohash_grid: {
__template: {
field: '',
precision: 3,
},
field: '{field}',
precision: { __one_of: [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12] },
size: 10,
shard_size: 10,
},
composite: {
__template: {
sources: [
{
NAME: {
AGG_TYPE: {},
},
},
],
},
sources: [
{
__scope_link: '.',
__template: {
NAME: {
AGG_TYPE: {},
},
},
},
],
size: 10,
after: {},
},
percentiles: {
__template: {
field: '',
percents: [1.0, 5.0, 25.0, 50.0, 75.0, 95.0, 99.0],
},
field: '{field}',
percents: {
__template: [1.0, 5.0, 25.0, 50.0, 75.0, 95.0, 99.0],
__any_of: [],
},
script: {
},
compression: 100,
method: { __one_of: ['hdr', 'tdigest'] },
missing: 0,
},
cardinality: {
__template: {
field: '',
},
precision_threshold: 100,
rehash: true,
script: {
},
missing: '',
},
cumulative_cardinality: {
__template: {
buckets_path: '',
},
buckets_path: '',
format: '',
},
scripted_metric: {
__template: {
init_script: '',
map_script: '',
combine_script: '',
reduce_script: '',
},
init_script: {
__scope_link: 'GLOBAL.script',
},
map_script: {
__scope_link: 'GLOBAL.script',
},
combine_script: {
__scope_link: 'GLOBAL.script',
},
reduce_script: {
__scope_link: 'GLOBAL.script',
},
lang: 'groovy',
params: {},
reduce_params: {},
},
geo_bounds: {
__template: {
field: '',
},
field: '{field}',
wrap_longitude: { __one_of: [true, false] },
},
top_hits: {
__template: {
size: 10,
},
from: 0,
size: 10,
sort: {
__template: [],
__scope_link: 'search.sort',
},
highlight: {},
explain: { __one_of: [true, false] },
_source: {
__template: '',
__scope_link: 'search._source',
},
script_fields: {
__scope_link: 'search.script_fields',
},
docvalue_fields: ['{field}'],
version: { __one_of: [true, false] },
},
percentile_ranks: {
__template: {
field: '',
values: [10, 15],
},
field: '{field}',
values: [],
script: {
},
compression: 100,
method: { __one_of: ['hdr', 'tdigest'] },
missing: 0,
},
sampler: {
__template: {},
field: '{field}',
script: {
},
shard_size: 100,
max_docs_per_value: 3,
execution_hint: { __one_of: ['map', 'global_ordinals', 'bytes_hash'] },
},
children: {
__template: {
type: '',
},
type: '',
},
derivative: simple_pipeline,
avg_bucket: simple_pipeline,
max_bucket: simple_pipeline,
min_bucket: simple_pipeline,
stats_bucket: simple_pipeline,
extended_stats_bucket: {
"...": @simple_pipeline,
sigma: '',
},
percentiles_bucket: {
"...": @simple_pipeline,
percents: [],
},
sum_bucket: simple_pipeline,
moving_avg: {
__template: {
buckets_path: '',
},
buckets_path: '',
format: '',
"gap_policy": gap_policy,
window: 5,
model: { __one_of: ['simple', 'linear', 'ewma', 'holt', 'holt_winters'] },
settings: {
type: { __one_of: ['add', 'mult'] },
alpha: 0.5,
beta: 0.5,
gamma: 0.5,
period: 7,
},
},
cumulative_sum: {
__template: {
buckets_path: '',
},
buckets_path: '',
format: '',
},
serial_diff: {
__template: {
buckets_path: '',
lag: 7,
},
lag: 7,
"gap_policy": gap_policy,
buckets_path: '',
format: '',
},
bucket_script: {
__template: {
buckets_path: {},
script: '',
},
buckets_path: {},
format: '',
"gap_policy": gap_policy,
script: '',
},
bucket_selector: {
__template: {
buckets_path: {},
script: '',
},
buckets_path: {},
"gap_policy": gap_policy,
script: '',
},
bucket_sort: {
__template: {
sort: [],
},
sort: ['{field}'],
from: 0,
size: 0,
"gap_policy": gap_policy,
},
matrix_stats: {
__template: {
fields: [],
},
fields: ['{field}'],
},
},
}
let terms = rules['*']
let histogram = rules['*']
let date_histogram = rules['*']
for aggs in [0] {
specService addGlobalAutocompleteRules('aggregations', rules)
specService addGlobalAutocompleteRules('aggs', rules)
specService addGlobalAutocompleteRules('groupByAggs', {
"*": { "terms": terms, "histogram": histogram, "date_histogram": date_histogram },
})
}
// 'oss/reindex'
for reindex in [0] {
specService addEndpointDescription('reindex', {
methods: ['POST'],
patterns: ['_reindex'],
data_autocomplete_rules: {
__template: {
source: {},
dest: {},
},
source: {
index: '',
type: '',
query: {
__scope_link: 'GLOBAL.query',
},
sort: {
__template: {
FIELD: 'desc',
},
FIELD: { __one_of: ['asc', 'desc'] },
},
size: 1000,
remote: {
__template: {
host: '',
},
host: '',
username: '',
password: '',
socket_timeout: '30s',
connect_timeout: '30s',
},
},
dest: {
index: '',
version_type: { __one_of: ['internal', 'external'] },
op_type: 'create',
routing: { __one_of: ['keep', 'discard', '=SOME TEXT'] },
pipeline: '',
},
conflicts: 'proceed',
size: 10,
script: { __scope_link: 'GLOBAL.script' },
},
})
}
// 'oss/search'
for search in [0] {
specService addEndpointDescription('search', {
priority: 10, // collides with get doc by id
data_autocomplete_rules: {
query: {
},
profile: {
__one_of: ['true', 'false'],
},
aggs: {
__template: {
NAME: {
AGG_TYPE: {},
},
},
},
post_filter: {
__scope_link: 'GLOBAL.filter',
},
size: {
__template: 20,
},
from: 0,
sort: {
__template: [
{
FIELD: {
order: 'desc',
},
},
],
__any_of: [
{
'{field}': {
order: {
__one_of: ['desc', 'asc'],
},
missing: {
__one_of: ['_last', '_first'],
},
mode: {
__one_of: ['min', 'max', 'avg', 'sum'],
},
nested_path: '',
nested_filter: {
__scope_link: 'GLOBAL.filter',
},
},
},
'{field}',
'_score',
{
_geo_distance: {
__template: {
FIELD: {
lat: 40,
lon: -70,
},
order: 'asc',
},
'{field}': {
__one_of: [
{
__template: {
lat: 40,
lon: -70,
},
lat: 40,
lon: -70,
},
[
{
__template: {
lat: 40,
lon: -70,
},
lat: 40,
lon: -70,
},
],
[''],
'',
],
},
distance_type: { __one_of: ['sloppy_arc', 'arc', 'plane'] },
sort_mode: { __one_of: ['min', 'max', 'avg'] },
order: { __one_of: ['asc', 'desc'] },
unit: 'km',
},
},
],
},
stored_fields: ['{field}'],
suggest: {
__template: {
YOUR_SUGGESTION: {
text: 'YOUR TEXT',
term: {
FIELD: 'MESSAGE',
},
},
},
'*': {
include: [],
exclude: [],
},
},
docvalue_fields: ['{field}'],
collapse: {
__template: {
field: 'FIELD',
},
},
indices_boost: {
__template: [{ INDEX: 1.0 }],
},
rescore: {
__template: {
query: {},
window_size: 50,
},
},
script_fields: {
__template: {
FIELD: {
script: {
},
},
},
'*': {
__scope_link: 'GLOBAL.script',
},
},
partial_fields: {
__template: {
NAME: {
include: [],
},
},
'*': {
include: [],
exclude: [],
},
},
highlight: {
},
_source: {
__one_of: [
'{field}',
['{field}'],
{
includes: {
__one_of: ['{field}', ['{field}']],
},
excludes: {
__one_of: ['{field}', ['{field}']],
},
},
],
},
explain: {
__one_of: [true, false],
},
stats: [''],
timeout: '1s',
version: { __one_of: [true, false] },
track_total_hits: { __one_of: [true, false] },
},
})
specService addEndpointDescription('search_template', {
data_autocomplete_rules: {
template: {
__one_of: [{ __scope_link: 'search' }, { __scope_link: 'GLOBAL.script' }],
},
params: {},
},
})
specService addEndpointDescription('render_search_template', {
data_autocomplete_rules: {
__one_of: [{ source: { __scope_link: 'search' } }, { __scope_link: 'GLOBAL.script' }],
params: {},
},
})
specService addEndpointDescription('_search/template/{id}', {
data_autocomplete_rules: {
template: {
__scope_link: 'search',
},
},
})
}
// 'oss/filter'
let filters = {}
let filters.and = {
__template: {
filters: [{}],
},
filters: [
{
__scope_link: '.',
},
],
}
let filters.bool = {
__scope_link: 'GLOBAL.query',
}
let filters.exists = {
__template: {
field: 'FIELD_NAME',
},
field: '{field}',
}
let filters.ids = {
__template: {
values: ['ID'],
},
type: '{type}',
values: [''],
}
let filters.limit = {
__template: {
value: 100,
},
value: 100,
}
let filters.type = {
__template: {
value: 'TYPE',
},
value: '{type}',
}
let filters.geo_bounding_box = {
__template: {
FIELD: {
top_left: {
lat: 40.73,
lon: -74.1,
},
bottom_right: {
lat: 40.717,
lon: -73.99,
},
},
},
'{field}': {
top_left: {
lat: 40.73,
lon: -74.1,
},
bottom_right: {
lat: 40.73,
lon: -74.1,
},
},
type: {
__one_of: ['memory', 'indexed'],
},
}
let filters.geo_distance = {
__template: {
distance: 100,
distance_unit: 'km',
FIELD: {
lat: 40.73,
lon: -74.1,
},
},
distance: 100,
distance_unit: {
__one_of: ['km', 'miles'],
},
distance_type: {
__one_of: ['arc', 'plane'],
},
optimize_bbox: {
__one_of: ['memory', 'indexed', 'none'],
},
'{field}': {
lat: 40.73,
lon: -74.1,
},
}
let filters.geo_distance_range = {
__template: {
from: 100,
to: 200,
distance_unit: 'km',
FIELD: {
lat: 40.73,
lon: -74.1,
},
},
from: 100,
to: 200,
distance_unit: {
__one_of: ['km', 'miles'],
},
distance_type: {
__one_of: ['arc', 'plane'],
},
include_lower: {
__one_of: [true, false],
},
include_upper: {
__one_of: [true, false],
},
'{field}': {
lat: 40.73,
lon: -74.1,
},
}
let filters.geo_polygon = {
__template: {
FIELD: {
points: [
{
lat: 40.73,
lon: -74.1,
},
{
lat: 40.83,
lon: -75.1,
},
],
},
},
'{field}': {
points: [
{
lat: 40.73,
lon: -74.1,
},
],
},
}
let filters.geo_shape = {
__template: {
FIELD: {
shape: {
type: 'envelope',
coordinates: [
[-45, 45],
[45, -45],
],
},
relation: 'within',
},
},
'{field}': {
shape: {
type: '',
coordinates: [],
},
indexed_shape: {
id: '',
index: '{index}',
type: '{type}',
shape_field_name: 'shape',
},
relation: {
__one_of: ['within', 'intersects', 'disjoint'],
},
},
}
let filters.has_child = {
__template: {
type: 'TYPE',
filter: {},
},
type: '{type}',
query: {},
filter: {},
_scope: '',
min_children: 1,
max_children: 10,
}
let filters.has_parent = {
__template: {
parent_type: 'TYPE',
filter: {},
},
parent_type: '{type}',
query: {},
filter: {},
_scope: '',
}
let filters.missing = {
__template: {
field: 'FIELD',
},
existence: {
__one_of: [true, false],
},
null_value: {
__one_of: [true, false],
},
field: '{field}',
}
let filters.not = {
__template: {
filter: {},
},
filter: {},
}
let filters.range = {
__template: {
FIELD: {
gte: 10,
lte: 20,
},
},
'{field}': {
gte: 1,
gt: 1,
lte: 20,
lt: 20,
time_zone: '+01:00',
format: 'dd/MM/yyyy||yyyy',
execution: { __one_of: ['index', 'fielddata'] },
},
}
let filters.or = {
__template: {
filters: [{}],
},
filters: [
{
__scope_link: '.',
},
],
}
let filters.prefix = {
__template: {
FIELD: 'VALUE',
},
'{field}': '',
}
let filters.query = {
}
let filters.script = {
__template: {
script: {},
},
script: {
},
}
let filters.term = {
__template: {
FIELD: 'VALUE',
},
'{field}': '',
}
let filters.terms = {
__template: {
FIELD: ['VALUE1', 'VALUE2'],
},
field: ['{field}'],
execution: {
__one_of: ['plain', 'bool', 'and', 'or', 'bool_nocache', 'and_nocache', 'or_nocache'],
},
}
let filters.nested = {
__template: {
path: 'path_to_nested_doc',
query: {},
},
query: {},
path: '',
_name: '',
}
for filter in [0] {
specService addGlobalAutocompleteRules('filter', filters)
}
// 'oss/settings'
for settings in [0] {
specService addEndpointDescription('put_settings', {
data_autocomplete_rules: {
refresh_interval: '1s',
number_of_shards: 1,
number_of_replicas: 1,
'blocks.read_only': BOOLEAN,
'blocks.read': BOOLEAN,
'blocks.write': BOOLEAN,
'blocks.metadata': BOOLEAN,
term_index_interval: 32,
term_index_divisor: 1,
'translog.flush_threshold_ops': 5000,
'translog.flush_threshold_size': '200mb',
'translog.flush_threshold_period': '30m',
'translog.disable_flush': BOOLEAN,
'cache.filter.max_size': '2gb',
'cache.filter.expire': '2h',
'gateway.snapshot_interval': '10s',
routing: {
allocation: {
include: {
tag: '',
},
exclude: {
tag: '',
},
require: {
tag: '',
},
total_shards_per_node: -1,
},
},
'recovery.initial_shards': {
__one_of: ['quorum', 'quorum-1', 'half', 'full', 'full-1'],
},
'ttl.disable_purge': BOOLEAN,
analysis: {
analyzer: {},
tokenizer: {},
filter: {},
char_filter: {},
},
'cache.query.enable': BOOLEAN,
shadow_replicas: BOOLEAN,
shared_filesystem: BOOLEAN,
data_path: 'path',
codec: {
__one_of: ['default', 'best_compression', 'lucene_default'],
},
},
})
}
// 'oss/document'
for document in [0] {
specService addEndpointDescription('update', {
data_autocomplete_rules: {
script: {
},
doc: {},
upsert: {},
scripted_upsert: { __one_of: [true, false] },
},
})
specService addEndpointDescription('put_script', {
methods: ['POST', 'PUT'],
patterns: ['_scripts/{lang}/{id}', '_scripts/{lang}/{id}/_create'],
url_components: {
lang: ['groovy', 'expressions'],
},
data_autocomplete_rules: {
script: '',
},
})
specService addEndpointDescription('termvectors', {
data_autocomplete_rules: {
fields: ['{field}'],
offsets: { __one_of: [false, true] },
payloads: { __one_of: [false, true] },
positions: { __one_of: [false, true] },
term_statistics: { __one_of: [true, false] },
field_statistics: { __one_of: [false, true] },
per_field_analyzer: {
__template: { FIELD: '' },
'{field}': '',
},
routing: '',
version: 1,
version_type: ['external', 'external_gt', 'external_gte', 'force', 'internal'],
doc: {},
filter: {
max_num_terms: 1,
min_term_freq: 1,
max_term_freq: 1,
min_doc_freq: 1,
max_doc_freq: 1,
min_word_length: 1,
max_word_length: 1,
},
},
})
}
// 'oss/aliases'
for aliases in [0] {
let aliasRules = {
filter: {},
routing: '1',
search_routing: '1,2',
index_routing: '1',
}
specService addGlobalAutocompleteRules('aliases', {
'*': aliasRules,
})
}
// 'oss/globals'
let highlightOptions = {
boundary_chars: {},
boundary_max_scan: 20,
boundary_scanner: {
__one_of: ['chars', 'sentence', 'word'],
},
boundary_scanner_locale: {},
encoder: {
__one_of: ['default', 'html'],
},
force_source: {
__one_of: ['false', 'true'],
},
fragmenter: {
__one_of: ['simple', 'span'],
},
highlight_query: {
__scope_link: 'GLOBAL.query',
},
matched_fields: ['FIELD'],
order: {},
no_match_size: 0,
number_of_fragments: 5,
phrase_limit: 256,
pre_tags: {},
post_tags: {},
require_field_match: {
__one_of: ['true', 'false'],
},
tags_schema: {},
}
for globals in [0] {
specService addGlobalAutocompleteRules('highlight', {
"...": @highlightOptions,
fields: {
'{field}': {
fragment_size: 20,
number_of_fragments: 3,
"...": @highlightOptions,
},
},
})
specService addGlobalAutocompleteRules('script', {
__template: {
source: 'SCRIPT',
},
source: 'SCRIPT',
file: 'FILE_SCRIPT_NAME',
id: 'SCRIPT_ID',
lang: '',
params: {},
})
}
// 'oss/index'
// 'oss/ingest'
let commonPipelineParams = {
on_failure: [],
ignore_failure: {
__one_of: [false, true],
},
if: '',
tag: '',
}
let appendProcessorDefinition = {
append: {
__template: {
field: '',
value: [],
},
field: '',
value: [],
"...": @commonPipelineParams,
},
}
let bytesProcessorDefinition = {
bytes: {
__template: {
field: '',
},
field: '',
target_field: '',
ignore_missing: {
__one_of: [false, true],
},
"...": @commonPipelineParams,
},
}
let circleProcessorDefinition = {
circle: {
__template: {
field: '',
error_distance: '',
shape_type: '',
},
field: '',
target_field: '',
error_distance: '',
shape_type: {
__one_of: ['geo_shape', 'shape'],
},
ignore_missing: {
__one_of: [false, true],
},
"...": @commonPipelineParams,
},
}
let csvProcessorDefinition = {
csv: {
__template: {
field: '',
target_fields: [''],
},
field: '',
target_fields: [''],
separator: '',
quote: '',
empty_value: '',
trim: {
__one_of: [true, false],
},
ignore_missing: {
__one_of: [false, true],
},
"...": @commonPipelineParams,
},
}
let convertProcessorDefinition = {
convert: {
__template: {
field: '',
type: '',
},
field: '',
type: {
__one_of: ['integer', 'float', 'string', 'boolean', 'auto'],
},
target_field: '',
ignore_missing: {
__one_of: [false, true],
},
"...": @commonPipelineParams,
},
}
let dateProcessorDefinition = {
date: {
__template: {
field: '',
formats: [],
},
field: '',
target_field: '@timestamp',
formats: [],
timezone: 'UTC',
locale: 'ENGLISH',
"...": @commonPipelineParams,
},
}
let dateIndexNameProcessorDefinition = {
date_index_name: {
__template: {
field: '',
date_rounding: '',
},
field: '',
date_rounding: {
__one_of: ['y', 'M', 'w', 'd', 'h', 'm', 's'],
},
date_formats: [],
timezone: 'UTC',
locale: 'ENGLISH',
index_name_format: 'yyyy-MM-dd',
"...": @commonPipelineParams,
},
}
let dissectProcessorDefinition = {
dissect: {
__template: {
field: '',
pattern: '',
},
field: '',
pattern: '',
append_separator: '',
ignore_missing: {
__one_of: [false, true],
},
"...": @commonPipelineParams,
},
}
let dotExpanderProcessorDefinition = {
dot_expander: {
__template: {
field: '',
},
field: '',
path: '',
"...": @commonPipelineParams,
},
}
let dropProcessorDefinition = {
drop: {
__template: {},
"...": @commonPipelineParams,
},
}
let failProcessorDefinition = {
fail: {
__template: {
message: '',
},
message: '',
"...": @commonPipelineParams,
},
}
let foreachProcessorDefinition = {
foreach: {
__template: {
field: '',
processor: {},
},
field: '',
processor: {
__scope_link: '_processor',
},
"...": @commonPipelineParams,
},
}
let geoipProcessorDefinition = {
geoip: {
__template: {
field: '',
},
field: '',
target_field: '',
database_file: '',
properties: [''],
ignore_missing: {
__one_of: [false, true],
},
first_only: {
__one_of: [false, true],
},
},
}
let grokProcessorDefinition = {
grok: {
__template: {
field: '',
patterns: [],
},
field: '',
patterns: [],
pattern_definitions: {},
trace_match: {
__one_of: [false, true],
},
ignore_missing: {
__one_of: [false, true],
},
"...": @commonPipelineParams,
},
}
let gsubProcessorDefinition = {
gsub: {
__template: {
field: '',
pattern: '',
replacement: '',
},
field: '',
pattern: '',
replacement: '',
"...": @commonPipelineParams,
},
}
let htmlStripProcessorDefinition = {
html_strip: {
__template: {
field: '',
},
field: '',
target_field: '',
ignore_missing: {
__one_of: [false, true],
},
"...": @commonPipelineParams,
},
}
let inferenceProcessorDefinition = {
inference: {
__template: {
model_id: '',
field_map: {},
inference_config: {},
},
model_id: '',
field_map: {},
inference_config: {},
target_field: '',
"...": @commonPipelineParams,
},
}
let joinProcessorDefinition = {
join: {
__template: {
field: '',
separator: '',
},
field: '',
separator: '',
"...": @commonPipelineParams,
},
}
let jsonProcessorDefinition = {
json: {
__template: {
field: '',
},
field: '',
target_field: '',
add_to_root: {
__one_of: [false, true],
},
"...": @commonPipelineParams,
},
}
let kvProcessorDefinition = {
kv: {
__template: {
field: '',
field_split: '',
value_split: '',
},
field: '',
field_split: '',
value_split: '',
target_field: '',
include_keys: [],
ignore_missing: {
__one_of: [false, true],
},
"...": @commonPipelineParams,
},
}
let lowercaseProcessorDefinition = {
lowercase: {
__template: {
field: '',
},
field: '',
ignore_missing: {
__one_of: [false, true],
},
"...": @commonPipelineParams,
},
}
let pipelineProcessorDefinition = {
pipeline: {
__template: {
name: '',
},
name: '',
"...": @commonPipelineParams,
},
}
let removeProcessorDefinition = {
remove: {
__template: {
field: '',
},
field: '',
"...": @commonPipelineParams,
},
}
let renameProcessorDefinition = {
rename: {
__template: {
field: '',
target_field: '',
},
field: '',
target_field: '',
ignore_missing: {
__one_of: [false, true],
},
"...": @commonPipelineParams,
},
}
let scriptProcessorDefinition = {
script: {
__template: {},
lang: 'painless',
file: '',
id: '',
source: '',
params: {},
"...": @commonPipelineParams,
},
}
let setProcessorDefinition = {
set: {
__template: {
field: '',
value: '',
},
field: '',
value: '',
override: {
__one_of: [true, false],
},
"...": @commonPipelineParams,
},
}
let setSecurityUserProcessorDefinition = {
set_security_user: {
__template: {
field: '',
},
field: '',
properties: [''],
"...": @commonPipelineParams,
},
}
let splitProcessorDefinition = {
split: {
__template: {
field: '',
separator: '',
},
field: '',
separator: '',
ignore_missing: {
__one_of: [false, true],
},
"...": @commonPipelineParams,
},
}
let sortProcessorDefinition = {
sort: {
__template: {
field: '',
},
field: '',
order: 'asc',
"...": @commonPipelineParams,
},
}
let trimProcessorDefinition = {
trim: {
__template: {
field: '',
},
field: '',
ignore_missing: {
__one_of: [false, true],
},
"...": @commonPipelineParams,
},
}
let uppercaseProcessorDefinition = {
uppercase: {
__template: {
field: '',
},
field: '',
ignore_missing: {
__one_of: [false, true],
},
"...": @commonPipelineParams,
},
}
let urlDecodeProcessorDefinition = {
urldecode: {
__template: {
field: '',
},
field: '',
target_field: '',
ignore_missing: {
__one_of: [false, true],
},
"...": @commonPipelineParams,
},
}
let userAgentProcessorDefinition = {
user_agent: {
__template: {
field: '',
},
field: '',
target_field: '',
regex_file: '',
properties: [''],
ignore_missing: {
__one_of: [false, true],
},
},
}
let processorDefinition = {
__one_of: [
appendProcessorDefinition,
bytesProcessorDefinition,
csvProcessorDefinition,
circleProcessorDefinition,
convertProcessorDefinition,
dateProcessorDefinition,
dateIndexNameProcessorDefinition,
dissectProcessorDefinition,
dotExpanderProcessorDefinition,
dropProcessorDefinition,
failProcessorDefinition,
foreachProcessorDefinition,
geoipProcessorDefinition,
grokProcessorDefinition,
gsubProcessorDefinition,
htmlStripProcessorDefinition,
inferenceProcessorDefinition,
joinProcessorDefinition,
jsonProcessorDefinition,
kvProcessorDefinition,
lowercaseProcessorDefinition,
pipelineProcessorDefinition,
removeProcessorDefinition,
renameProcessorDefinition,
scriptProcessorDefinition,
setProcessorDefinition,
setSecurityUserProcessorDefinition,
splitProcessorDefinition,
sortProcessorDefinition,
trimProcessorDefinition,
uppercaseProcessorDefinition,
urlDecodeProcessorDefinition,
userAgentProcessorDefinition,
],
}
let pipelineDefinition = {
description: '',
processors: [processorDefinition],
version: 123,
}
for ingest in [0] {
specService addEndpointDescription('_processor', {
data_autocomplete_rules: processorDefinition,
})
specService addEndpointDescription('ingest.put_pipeline', {
methods: ['PUT'],
patterns: ['_ingest/pipeline/{id}'],
data_autocomplete_rules: pipelineDefinition,
})
specService addEndpointDescription('ingest.simulate', {
data_autocomplete_rules: {
pipeline: pipelineDefinition,
docs: [],
},
})
}
// 'oss/templates'
let regexpTemplate = {
FIELD: 'REGEXP',
}
let fuzzyTemplate = {
FIELD: {},
}
let prefixTemplate = {
FIELD: {
value: '',
},
}
let rangeTemplate = {
FIELD: {
gte: 10,
lte: 20,
},
}
let spanFirstTemplate = {
match: {
span_term: {
FIELD: 'VALUE',
},
},
end: 3,
}
let spanNearTemplate = {
clauses: [
{
span_term: {
FIELD: {
value: 'VALUE',
},
},
},
],
slop: 12,
in_order: false,
}
let spanTermTemplate = {
FIELD: {
value: 'VALUE',
},
}
let spanNotTemplate = {
include: {
span_term: {
FIELD: {
value: 'VALUE',
},
},
},
exclude: {
span_term: {
FIELD: {
value: 'VALUE',
},
},
},
}
let spanOrTemplate = {
clauses: [
{
span_term: {
FIELD: {
value: 'VALUE',
},
},
},
],
}
let spanContainingTemplate = {
little: {
span_term: {
FIELD: {
value: 'VALUE',
},
},
},
big: {
span_near: {
clauses: [
{
span_term: {
FIELD: {
value: 'VALUE',
},
},
},
{
span_term: {
FIELD: {
value: 'VALUE',
},
},
},
],
slop: 5,
in_order: false,
},
},
}
let spanWithinTemplate = {
little: {
span_term: {
FIELD: {
value: 'VALUE',
},
},
},
big: {
span_near: {
clauses: [
{
span_term: {
FIELD: {
value: 'VALUE',
},
},
},
{
span_term: {
FIELD: {
value: 'VALUE',
},
},
},
],
slop: 5,
in_order: false,
},
},
}
let wildcardTemplate = {
FIELD: {
value: 'VALUE',
},
}
// 'oss/dsl'
spanFirstTemplate,
spanNearTemplate,
spanOrTemplate,
spanNotTemplate,
spanTermTemplate,
spanContainingTemplate,
spanWithinTemplate,
wildcardTemplate,
fuzzyTemplate,
prefixTemplate,
rangeTemplate,
regexpTemplate,
} from './templates'
let matchOptions = {
cutoff_frequency: 0.001,
query: '',
operator: {
__one_of: ['and', 'or'],
},
zero_terms_query: {
__one_of: ['none', 'all'],
},
max_expansions: 10,
analyzer: '',
boost: 1.0,
lenient: {
__one_of: ['true', 'false'],
},
fuzzy_transpositions: {
__one_of: ['true', 'false'],
},
auto_generate_synonyms_phrase_query: {
__one_of: ['true', 'false'],
},
fuzziness: 1.0,
prefix_length: 1,
minimum_should_match: 1,
}
let innerHits = {
docvalue_fields: ['FIELD'],
from: {},
size: {},
sort: {},
name: {},
highlight: {},
_source: {
__one_of: ['true', 'false'],
},
explain: {
__one_of: ['true', 'false'],
},
script_fields: {
__template: {
FIELD: {
script: {},
},
},
'{field}': {
script: {},
},
},
version: {
__one_of: ['true', 'false'],
},
}
let SPAN_QUERIES_NO_FIELD_MASK = {
span_first: {
__template: spanFirstTemplate,
__scope_link: '.span_first',
},
span_near: {
__template: spanNearTemplate,
__scope_link: '.span_near',
},
span_or: {
__template: spanOrTemplate,
__scope_link: '.span_or',
},
span_not: {
__template: spanNotTemplate,
__scope_link: '.span_not',
},
span_term: {
__template: spanTermTemplate,
__scope_link: '.span_term',
},
span_containing: {
__template: spanContainingTemplate,
__scope_link: '.span_containing',
},
span_within: {
__template: spanWithinTemplate,
__scope_link: '.span_within',
},
}
let SPAN_QUERIES = {
"...": @SPAN_QUERIES_NO_FIELD_MASK,
field_masking_span: {
__template: {
query: {
SPAN_QUERY: {},
},
},
query: SPAN_QUERIES_NO_FIELD_MASK,
field: '',
},
}
let SPAN_MULTI_QUERIES = {
wildcard: {
__template: wildcardTemplate,
__scope_link: '.wildcard',
},
fuzzy: {
__template: fuzzyTemplate,
__scope_link: '.fuzzy',
},
prefix: {
__template: prefixTemplate,
__scope_link: '.prefix',
},
range: {
__template: rangeTemplate,
__scope_link: '.range',
},
regexp: {
__template: regexpTemplate,
__scope_link: '.regexp',
},
}
let DECAY_FUNC_DESC = {
__template: {
FIELD: {
origin: '',
scale: '',
},
},
'{field}': {
origin: '',
scale: '',
offset: '',
decay: 0.5,
},
}
let SCORING_FUNCS = {
script_score: {
__template: {
script: "_score * doc['f'].value",
},
script: {
},
},
boost_factor: 2.0,
random_score: {
seed: 314159265359,
},
linear: DECAY_FUNC_DESC,
exp: DECAY_FUNC_DESC,
gauss: DECAY_FUNC_DESC,
field_value_factor: {
__template: {
field: '',
},
field: '{field}',
factor: 1.2,
modifier: {
__one_of: [
'none',
'log',
'log1p',
'log2p',
'ln',
'ln1p',
'ln2p',
'square',
'sqrt',
'reciprocal',
],
},
},
}
for query in [0] {
specService addGlobalAutocompleteRules('query', {
match: {
__template: {
FIELD: 'TEXT',
},
'{field}': {
type: {
__one_of: ['phrase', 'phrase_prefix', 'boolean'],
},
"...": @matchOptions,
},
},
match_phrase: {
__template: {
FIELD: 'PHRASE',
},
'{field}': {
query: '',
analyzer: '',
slop: 1,
},
},
match_phrase_prefix: {
__template: {
FIELD: 'PREFIX',
},
'{field}': {
query: '',
analyzer: '',
max_expansions: 10,
prefix_length: 1,
fuzziness: 0.1,
},
},
regexp: {
__template: regexpTemplate,
'{field}': {
value: '',
flags: {
__one_of: ['ALL', 'ANYSTRING', 'COMPLEMENT', 'EMPTY', 'INTERSECTION', 'INTERVAL', 'NONE'],
},
max_determinized_states: 10000,
},
},
multi_match: {
__template: {
query: '',
fields: [],
},
"...": @matchOptions,
fields: ['{field}'],
use_dis_max: {
__template: true,
__one_of: [true, false],
},
tie_breaker: 0.0,
type: {
__one_of: ['best_fields', 'most_fields', 'cross_fields', 'phrase', 'phrase_prefix'],
},
},
bool: {
must: [
{
__scope_link: '.',
},
],
must_not: [
{
__scope_link: '.',
},
],
should: [
{
__scope_link: '.',
},
],
filter: [
{
__scope_link: 'GLOBAL.filter',
},
],
minimum_should_match: 1,
boost: 1.0,
},
boosting: {
positive: {
__scope_link: '.',
},
negative: {
__scope_link: '.',
},
negative_boost: 0.2,
},
ids: {
type: '',
values: [],
},
constant_score: {
__template: {
filter: {},
boost: 1.2,
},
query: {},
filter: {},
boost: 1.2,
},
dis_max: {
__template: {
tie_breaker: 0.7,
boost: 1.2,
queries: [],
},
tie_breaker: 0.7,
boost: 1.2,
queries: [
{
__scope_link: '.',
},
],
},
distance_feature: {
__template: {
field: '',
origin: '',
pivot: '',
},
field: '{field}',
origin: '',
pivot: '',
},
exists: {
field: '',
},
field: {
'{field}': {
query: '',
boost: 2.0,
enable_position_increments: {
__template: false,
__one_of: [true, false],
},
},
},
fuzzy: {
__template: fuzzyTemplate,
'{field}': {
value: '',
boost: 1.0,
fuzziness: 0.5,
prefix_length: 0,
},
},
has_child: {
__template: {
type: 'TYPE',
query: {},
},
inner_hits: { "...": @innerHits },
type: '{type}',
score_mode: {
__one_of: ['none', 'max', 'sum', 'avg'],
},
_scope: '',
query: {},
min_children: 1,
max_children: 10,
},
has_parent: {
__template: {
parent_type: 'TYPE',
query: {},
},
parent_type: '{type}',
score_mode: {
__one_of: ['none', 'score'],
},
_scope: '',
query: {},
},
match_all: {
boost: 1,
},
more_like_this: {
__template: {
fields: ['FIELD'],
like: 'text like this one',
min_term_freq: 1,
max_query_terms: 12,
},
fields: ['{field}'],
like: '',
percent_terms_to_match: 0.3,
min_term_freq: 2,
max_query_terms: 25,
stop_words: [''],
min_doc_freq: 5,
max_doc_freq: 100,
min_word_len: 0,
max_word_len: 0,
boost_terms: 1,
boost: 1.0,
analyzer: '',
docs: [
{
_index: '{index}',
_type: '{type}',
_id: '',
},
],
ids: [''],
},
mlt: {
__template: {
fields: ['FIELD'],
like: 'text like this one',
min_term_freq: 1,
max_query_terms: 12,
},
__scope_link: '.more_like_this',
},
prefix: {
__template: prefixTemplate,
'{field}': {
value: '',
boost: 1.0,
},
},
query_string: {
__template: {
default_field: 'FIELD',
query: 'this AND that OR thus',
},
query: '',
default_field: '{field}',
fields: ['{field}'],
default_operator: {
__one_of: ['OR', 'AND'],
},
analyzer: '',
allow_leading_wildcard: {
__one_of: [true, false],
},
enable_position_increments: {
__one_of: [true, false],
},
fuzzy_max_expansions: 50,
fuzziness: 0.5,
fuzzy_prefix_length: 0,
phrase_slop: 0,
boost: 1.0,
analyze_wildcard: {
__one_of: [false, true],
},
auto_generate_phrase_queries: {
__one_of: [false, true],
},
minimum_should_match: '20%',
lenient: {
__one_of: [false, true],
},
use_dis_max: {
__one_of: [true, false],
},
tie_breaker: 0,
time_zone: '+01:00',
},
simple_query_string: {
__template: {
query: '',
fields: [],
},
query: '',
fields: ['{field}'],
default_operator: { __one_of: ['OR', 'AND'] },
analyzer: '',
flags: 'OR|AND|PREFIX',
locale: 'ROOT',
lenient: { __one_of: [true, false] },
},
range: {
__template: rangeTemplate,
'{field}': {
__template: {
gte: 10,
lte: 20,
},
gte: 10,
gt: 10,
lte: 20,
lt: 20,
time_zone: '+01:00',
boost: 1.0,
format: 'dd/MM/yyyy||yyyy',
},
},
span_first: {
__template: spanFirstTemplate,
match: SPAN_QUERIES,
},
span_multi: {
__template: {
match: {
MULTI_TERM_QUERY: {},
},
},
match: SPAN_MULTI_QUERIES,
},
span_near: {
__template: spanNearTemplate,
clauses: [SPAN_QUERIES],
slop: 12,
in_order: {
__one_of: [false, true],
},
collect_payloads: {
__one_of: [false, true],
},
},
span_term: {
__template: spanTermTemplate,
'{field}': {
value: '',
boost: 2.0,
},
},
span_not: {
__template: spanNotTemplate,
include: SPAN_QUERIES,
exclude: SPAN_QUERIES,
},
span_or: {
__template: spanOrTemplate,
clauses: [SPAN_QUERIES],
},
span_containing: {
__template: spanContainingTemplate,
little: SPAN_QUERIES,
big: SPAN_QUERIES,
},
span_within: {
__template: spanWithinTemplate,
little: SPAN_QUERIES,
big: SPAN_QUERIES,
},
term: {
__template: {
FIELD: {
value: 'VALUE',
},
},
'{field}': {
value: '',
boost: 2.0,
},
},
terms: {
__template: {
FIELD: ['VALUE1', 'VALUE2'],
},
'{field}': [''],
},
wildcard: {
__template: wildcardTemplate,
'{field}': {
value: '',
boost: 2.0,
},
},
nested: {
__template: {
path: 'path_to_nested_doc',
query: {},
},
inner_hits: { "...": @innerHits },
path: '',
query: {},
score_mode: {
__one_of: ['avg', 'total', 'max', 'none'],
},
},
percolate: {
__template: {
field: '',
document: {},
},
field: '',
document: {},
name: '',
documents: [{}],
document_type: '',
index: '',
type: '',
id: '',
routing: '',
preference: '',
},
common: {
__template: {
FIELD: {
query: {},
},
},
'{field}': {
query: {},
cutoff_frequency: 0.001,
minimum_should_match: {
low_freq: {},
high_freq: {},
},
},
},
custom_filters_score: {
__template: {
query: {},
filters: [
{
filter: {},
},
],
},
query: {},
filters: [
{
filter: {},
boost: 2.0,
script: {
},
},
],
score_mode: {
__one_of: ['first', 'min', 'max', 'total', 'avg', 'multiply'],
},
max_boost: 2.0,
params: {},
lang: '',
},
indices: {
__template: {
indices: ['INDEX1', 'INDEX2'],
query: {},
},
indices: ['{index}'],
query: {},
no_match_query: {
__scope_link: '.',
},
},
geo_shape: {
__template: {
location: {},
relation: 'within',
},
__scope_link: '.filter.geo_shape',
},
function_score: _.defaults(
{
__template: {
query: {},
functions: [{}],
},
query: {},
functions: [
_.defaults(
{
filter: {},
weight: 1.0,
},
SCORING_FUNCS
),
],
boost: 1.0,
boost_mode: {
__one_of: ['multiply', 'replace', 'sum', 'avg', 'max', 'min'],
},
score_mode: {
__one_of: ['multiply', 'sum', 'first', 'avg', 'max', 'min'],
},
max_boost: 10,
min_score: 1.0,
},
SCORING_FUNCS
),
script: {
__template: {
script: "_score * doc['f'].value",
},
script: {
},
},
wrapper: {
__template: {
query: 'QUERY_BASE64_ENCODED',
},
query: '',
},
})
}
// 'x-pack/index'
// 'x-pack/ingest'
let commonPipelineParams = {
on_failure: [],
ignore_failure: {
__one_of: [false, true],
},
if: '',
tag: '',
}
let enrichProcessorDefinition = {
enrich: {
__template: {
policy_name: '',
field: '',
target_field: '',
},
policy_name: '',
field: '',
target_field: '',
ignore_missing: {
__one_of: [false, true],
},
override: {
__one_of: [true, false],
},
max_matches: 1,
shape_relation: 'INTERSECTS',
"...": @commonPipelineParams,
},
}
let inferenceProcessorDefinition = {
inference: {
__template: {
model_id: '',
inference_config: {},
field_mappings: {},
},
target_field: '',
model_id: '',
field_mappings: {
__template: {},
},
inference_config: {
regression: {
__template: {},
results_field: '',
},
classification: {
__template: {},
results_field: '',
num_top_classes: 2,
top_classes_results_field: '',
},
},
"...": @commonPipelineParams,
},
}