# Cairnspan Mailbox

The mailbox is the fallback contract for environments where Cairnspan cannot
or should not launch the target agent directly.

It does not prove that the target agent ran. It proves that a bounded request or
response file is well-formed and safe to route through a file handoff.

## Layout

```text
.cairnspan/
  requests/
    <id>.json
  responses/
    <id>.json
```

Ids must match:

```text
^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$
```

Windows reserved filenames and NTFS alternate-data-stream separators are rejected.

## Request Schema

Required fields:

- `id`
- `origin_agent`
- `target_agent`
- `created_at`
- exactly one of `prompt` or `prompt_ref`
- `sandbox`
- `status`

Optional fields:

- `parent_run_id`
- `run_depth`
- `max_depth`
- `result_ref`
- `error`

Unknown fields are rejected. Inline prompts are bounded, reference fields must be relative and non-traversing, timestamps require a timezone, and nonzero depth requires a parent run id.

Allowed `sandbox` values:

- `read-only`
- `workspace-write`
- `danger-full-access`

Allowed request `status` values:

- `pending`
- `claimed`
- `running`
- `succeeded`
- `failed`
- `cancelled`

## Response Schema

Required fields:

- `id`
- `request_id`
- `origin_agent`
- `target_agent`
- `created_at`
- `status`

Optional fields:

- `result_ref`
- `final`
- `error`

Allowed response `status` values:

- `succeeded`
- `failed`
- `cancelled`

Succeeded responses require `result_ref` or `final`. Failed responses require
`error`.

## Validation

Validate a mailbox file:

```powershell
python skills\cairnspan\scripts\mailbox.py validate request .cairnspan\requests\<id>.json
python skills\cairnspan\scripts\mailbox.py validate response .cairnspan\responses\<id>.json
```

The Python helpers in `skills/cairnspan/scripts/mailbox.py` also provide
validated `write_request()` and `write_response()` functions for tests and
future launchers.

Writes use unique temporary files and no-clobber publication by default.

Validate one immutable exchange with:

```powershell
python skills\cairnspan\scripts\mailbox.py validate-exchange `
  --mailbox-dir .cairnspan `
  --request .cairnspan\requests\<request-id>.json `
  --response .cairnspan\responses\<response-id>.json
```

Exchange validation requires an immutable `pending` request, one terminal response, exact request-id linkage, reversed origin/target agents, contained regular non-reparse files, no hardlinks, resolvable prompt/result references, and exactly one response for the request.

The mailbox still does not authorize an agent, provide notifications, or turn a folder into a trusted queue. A parent must create a fresh route root, define the expected ids and agents, validate manifests after each edge, and decide whether the response may enter another model turn.
