# PostgreSQL Converter Issues

## Missing Type Conversions

The MySQL-to-PostgreSQL converter fails to handle certain MySQL types. The following issues were found in `sql/base/postgresql/characters_database.sql`:

### `character_cuf_profiles` table
- Table was not converted at all - still uses MySQL syntax
- `bigint unsigned` should convert to `BIGINT`
- `tinyint unsigned` should convert to `SMALLINT`
- `smallint unsigned` should convert to `INTEGER`
- `int unsigned` should convert to `INTEGER`
- `CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci` should be stripped
- `COMMENT '...'` should be stripped or converted to PostgreSQL COMMENT statements
- `ENGINE=InnoDB DEFAULT CHARSET=...` should be stripped
- `KEY "index" (id)` should convert to `CREATE INDEX ... ON table (column)`

### Root cause
The converter pipeline (preprocessing, splitting, transformation, postprocessing) missed this table entirely. Investigate why certain CREATE TABLE statements fall through without conversion.

### Hotfixes schema issues
- `)--` (missing semicolon after CREATE TABLE closing paren, 81 instances)
- `\'` backslash-escaped quotes should be converted to `''` (8 instances)
- `SMALLINT` used for MySQL `SMALLINT UNSIGNED` columns exceeds PostgreSQL SMALLINT range (max 32767). Values up to 65535 require `INTEGER`.
- `BYTEA` used for `hotfix_blob.blob` column but data is numeric, not binary. Should be `TEXT`.
