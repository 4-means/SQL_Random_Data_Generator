import re
import os
import argparse
import random
import uuid
import decimal
from datetime import datetime, date, time
import json
from typing import List, Dict, Any, Tuple
from pathlib import Path

try:
    from faker import Faker
except ImportError:
    raise SystemExit("Please install faker: pip install Faker")

fake = Faker()

# ---------- Parsing helpers ----------

# Matches: CREATE TABLE [schema.]"table" or CREATE TABLE schema.table
table_re = re.compile(
    r"""CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?
        (?:
            (?P<schema>"?\w+"?)\.
        )?
        "?(?P<name>\w+)"?
    """,
    re.IGNORECASE | re.VERBOSE
)

# Very forgiving column line matcher (stops before constraints / commas handled by strip)
col_re = re.compile(
    r"""
    ^\s*"? (?P<col>\w+) "?\s+
    (?P<type>[^(),\s]+(?:\s+[^(),\s]+)*)   # type may include spaces (e.g., character varying)
    (?:\((?P<lens>\d+(?:,\d+)?)\))?       # optional (len) or (precision,scale)
    \s*(?:,)?\s*$
    """,
    re.IGNORECASE | re.VERBOSE
)

constraint_starts = (
    "primary key", "foreign key", "unique", "check", "constraint",
    "index", "key", "references"
)

def parse_schema_file(path: str) -> Tuple[str, List[Dict[str, Any]]]:
    tbl = None
    cols: List[Dict[str, Any]] = []
    with open(path, 'r', encoding='utf-8', errors='ignore') as f:
        for raw in f:
            line = raw.strip()
            if not line:
                continue
            if tbl is None:
                m = table_re.search(line)
                if m:
                    tbl = m.group('name')
                continue

            # End of column list
            if line.startswith(')') or line.endswith(');'):
                break

            # Skip constraints
            low = line.lower()
            if low.startswith(constraint_starts):
                continue

            m = col_re.match(line.rstrip(','))
            if m:
                cols.append({
                    'name': m.group('col'),
                    'type': (m.group('type') or '').strip(),
                    'lens': (m.group('lens') or '').strip(),
                })
    return tbl, cols

# ---------- Data generation ----------

def _int_between(max_value: int = 1_000_000) -> int:
    return random.randint(0, max_value)

def _decimal_random(precision: int, scale: int) -> decimal.Decimal:
    if precision <= 0:
        precision = 10
    if scale < 0:
        scale = 0
    # max digits left of decimal
    left = max(0, precision - scale)
    max_whole = 10 ** left - 1 if left > 0 else 0
    whole = random.randint(0, max_whole) if left > 0 else 0
    frac = random.randint(0, 10 ** scale - 1) if scale > 0 else 0
    val = decimal.Decimal(whole)
    if scale > 0:
        val += decimal.Decimal(frac) / (decimal.Decimal(10) ** scale)
    return val

def _char_exact(n: int) -> str:
    n = max(1, min(n, 255))
    return fake.pystr(min_chars=n, max_chars=n)

def _char_up_to(n: int) -> str:
    n = max(1, min(n, 255))
    return fake.pystr(min_chars=1, max_chars=n)

def generate_random(col_def: Dict[str, Any]):
    t = (col_def['type'] or '').strip().lower()
    lens = (col_def.get('lens') or '').strip()

    # Normalize type keywords
    t_norm = t.replace('character varying', 'varchar').replace('double precision', 'float8')

    # Integer-like
    if any(k in t_norm for k in ('bigint', 'int8')):
        return _int_between(9_000_000_000)
    if any(k in t_norm for k in ('smallint', 'int2')):
        return _int_between(32_000)
    if any(k in t_norm for k in ('integer', 'int', 'int4')):
        return _int_between()

    # Decimal / Numeric
    if 'numeric' in t_norm or 'decimal' in t_norm:
        p, s = 10, 0
        if lens:
            parts = lens.split(',')
            try:
                p = int(parts[0])
                if len(parts) > 1:
                    s = int(parts[1])
            except Exception:
                p, s = 10, 0
        return _decimal_random(p, s)

    # Floating (use Python float)
    if any(k in t_norm for k in ('float', 'double', 'real')):
        return random.uniform(0, 1_000_000)

    # UUID
    if 'uuid' in t_norm:
        return str(uuid.uuid4())

    # Boolean
    if 'bool' in t_norm:
        return random.choice([True, False])

    # Date / Time
    if t_norm.strip() == 'date':
        return fake.date_object()
    if 'timestamp' in t_norm:
        return fake.date_time()
    if t_norm.strip() == 'time' or t_norm.startswith('time '):
        return time(hour=random.randint(0, 23),
                    minute=random.randint(0, 59),
                    second=random.randint(0, 59))

    # Character types (fixed and varying)
    if 'varchar' in t_norm or 'nvarchar' in t_norm or 'varying' in t_norm:
        max_len = int(lens.split(',')[0]) if lens else 32
        return _char_up_to(max_len)
    if 'bpchar' in t_norm or t_norm.startswith('char'):
        n = int(lens.split(',')[0]) if lens else 1
        return _char_exact(n)

    # Text / JSON-ish
    if t_norm in ('text', 'json', 'jsonb'):
        # modest length text to keep SQL lines readable
        s = fake.paragraph(nb_sentences=2)
        return s

    # Fallback string
    return fake.word()

def to_sql_literal(val):
    if val is None:
        return 'NULL'
    if isinstance(val, bool):
        return 'TRUE' if val else 'FALSE'
    if isinstance(val, (int, float, decimal.Decimal)):
        return str(val)
    if isinstance(val, datetime):
        return f"'{val.isoformat(sep=' ', timespec='seconds')}'"
    if isinstance(val, date) and not isinstance(val, datetime):
        return f"'{val.isoformat()}'"
    if isinstance(val, time):
        return f"'{val.isoformat(timespec='seconds')}'"
    # escape single quotes for strings
    s = str(val).replace("'", "''")
    return f"'{s}'"

def emit_insert_sql(table: str, cols: List[Dict[str, Any]], rows: List[Dict[str, Any]]):
    if not rows:
        return ''
    quoted_cols = ['"' + c['name'] + '"' for c in cols]
    values_lines = []
    for row in rows:
        vals = [to_sql_literal(row[c['name']]) for c in cols]
        values_lines.append('(' + ', '.join(vals) + ')')
    cols_part = ', '.join(quoted_cols)
    values_part = ",\n  ".join(values_lines)
    return f'INSERT INTO "{table}" ({cols_part})\nVALUES\n  {values_part};\n'

def json_default(o):
    if isinstance(o, (datetime, date)):
        return o.isoformat()
    if isinstance(o, time):
        return o.isoformat(timespec='seconds')
    if isinstance(o, decimal.Decimal):
        return str(o)
    return str(o)

def write_outputs(table: str, cols: List[Dict[str, Any]], rows: List[Dict[str, Any]], outdir: str):
    outdir_path = Path(outdir)
    outdir_path.mkdir(parents=True, exist_ok=True)

    # SQL
    sql = emit_insert_sql(table, cols, rows)
    sql_path = outdir_path / f"{table}_inserts.sql"
    sql_path.write_text(sql, encoding='utf-8')

    # JSON (array of row objects)
    json_path = outdir_path / f"{table}_inserts.json"
    with open(json_path, 'w', encoding='utf-8') as jf:
        json.dump(rows, jf, default=json_default, indent=2)

    return str(sql_path), str(json_path)

def parse_keyval_map(s: str, pair_sep=',', kv_sep='='):
    out: Dict[str, str] = {}
    if not s:
        return out
    for piece in (p.strip() for p in s.split(pair_sep)):
        if not piece:
            continue
        if kv_sep not in piece:
            continue
        k, v = (x.strip() for x in piece.split(kv_sep, 1))
        out[k] = v
    return out

# ---------- Main CLI ----------

def parse_schema_dir(schema_dir: str) -> Dict[str, List[Dict[str, Any]]]:
    schemas: Dict[str, List[Dict[str, Any]]] = {}
    for fname in os.listdir(schema_dir):
        if not fname.lower().endswith('.sql'):
            continue
        path = os.path.join(schema_dir, fname)
        tbl, cols = parse_schema_file(path)
        if tbl and cols:
            schemas[tbl] = cols
    return schemas

def main_cli(schema_dir='.', key_fields='', num_rows=10, multipliers='', foreign_map='', output_dir='.'):
    # Load schemas
    schemas = parse_schema_dir(schema_dir)

    if not schemas:
        raise SystemExit("No .sql schema files found in --schema-dir.")

    # Determine parent table: choose the one containing all key_fields if available
    parent_table = next(iter(schemas.keys()))
    if key_fields:
        keys = {k.strip() for k in key_fields.split(',') if k.strip()}
        for tname, cols in schemas.items():
            colset = {c['name'] for c in cols}
            if keys and keys.issubset(colset):
                parent_table = tname
                break

    parent_cols = schemas[parent_table]
    parent_keys = [k.strip() for k in key_fields.split(',') if k.strip()]

    # Build parent rows respecting schema types; enforce composite key uniqueness
    def composite_key(row: Dict[str, Any], keys: List[str]):
        return tuple(row[k] for k in keys)

    seen_keys = set()
    parent_rows = []
    for _ in range(num_rows):
        for _attempt in range(200):
            row = {}
            for c in parent_cols:
                row[c['name']] = generate_random(c)
            if parent_keys:
                comp = composite_key(row, parent_keys)
                if comp in seen_keys:
                    continue
                seen_keys.add(comp)
            parent_rows.append(row)
            break
        else:
            raise RuntimeError("Could not generate a unique composite key after many attempts")

    # Write parent outputs
    os.makedirs(output_dir, exist_ok=True)
    write_outputs(parent_table, parent_cols, parent_rows, output_dir)

    # Prepare child generation
    mult_map = {k: int(v) for k, v in parse_keyval_map(multipliers).items()}
    fkey_map = parse_keyval_map(foreign_map)  # child_col -> parent_col

    # Generate children
    for tbl, cols in schemas.items():
        if tbl == parent_table:
            continue
        m = mult_map.get(tbl, 1)
        child_rows = []
        for prow in parent_rows:
            for _ in range(m):
                crow = {}
                for c in cols:
                    cname = c['name']
                    if cname in fkey_map and fkey_map[cname] in prow:
                        crow[cname] = prow[fkey_map[cname]]
                    else:
                        crow[cname] = generate_random(c)
                child_rows.append(crow)
        write_outputs(tbl, cols, child_rows, output_dir)

    # Summary printout
    print(f"Parent table: {parent_table} -> {len(parent_rows)} rows written to {output_dir}")
    for tbl, cols in schemas.items():
        if tbl == parent_table:
            continue
        print(f"Child table:  {tbl} (multiplier={mult_map.get(tbl,1)}) -> {tbl}_inserts.sql / {tbl}_inserts.json")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate random INSERT SQL and matching JSON from CREATE TABLE schemas.")
    parser.add_argument("--schema-dir", default=".", help="Directory containing .sql schema files (default: .)")
    parser.add_argument("--key-fields", default="", help="Comma-separated key field names for the parent table (e.g., 'hdr_type,hdr_key')")
    parser.add_argument("--num-rows", type=int, default=10, help="Number of parent rows to generate (default: 10)")
    parser.add_argument("--multipliers", default="", help="Comma-separated table multipliers 'ChildA=3,ChildB=2' (default: 1 each)")
    parser.add_argument("--foreign-map", default="", help="Comma-separated mapping 'child_col=parent_col' to copy key values into children")
    parser.add_argument("--output-dir", default=".", help="Directory to write output files (default: .)")
    args = parser.parse_args()

    main_cli(
        schema_dir=args.schema_dir,
        key_fields=args.key_fields,
        num_rows=args.num_rows,
        multipliers=args.multipliers,
        foreign_map=args.foreign_map,
        output_dir=args.output_dir,
    )