# Data Kit

**Six focused checks for everyday data work.** Data Kit handles CSV, JSON, JSONL, and local files with the Python standard library. Each command prints JSON so it can feed another script or CI step.

| Command | Result |
| --- | --- |
| `profile` | CSV row count, empty cells, and distinct values per column. |
| `validate` | CSV required fields, simple types, and unique values against a JSON schema. |
| `shape-diff` | Added, removed, and changed JSON value types. |
| `duplicates` | Files with identical SHA-256 contents under a directory. |
| `jsonl-count` | Counts records by one top-level JSONL field. |
| `date-gaps` | Missing calendar dates between the first and last CSV date. |

## Quick start

```sh
python3 data_kit.py profile examples/orders.csv
python3 data_kit.py validate examples/orders.csv examples/orders.schema.json
python3 data_kit.py shape-diff examples/old.json examples/new.json
python3 data_kit.py duplicates ./assets
python3 data_kit.py jsonl-count ./events.jsonl level
python3 data_kit.py date-gaps examples/orders.csv date
```

`validate` schema example:

```json
{
  "required": ["id", "date"],
  "types": {"date": "date", "amount": "decimal"},
  "unique": ["id"]
}
```

Supported field types are `string`, `integer`, `decimal`, and ISO `date`. Exit code `0` means the command completed without validation findings, `1` means validation or diff findings were returned, and `2` means invalid input. Descriptive commands such as `profile` and `duplicates` return `0` when they complete.

## Tests

```sh
python3 -m unittest -v
```

Tests cover bad numeric cells, duplicate IDs and files, nested JSON changes, JSONL errors, and date gaps.

## Limits

This is a lightweight local toolkit. The JSON shape checker samples the first element of each array; it does not infer heterogeneous array schemas. The CSV validator does not replace a full schema language. The duplicate finder reads local file contents and may be slow on very large directories.

## License

MIT; see [LICENSE](LICENSE).
