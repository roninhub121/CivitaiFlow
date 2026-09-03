# CivitaiFlow Model Updates

CivitaiFlow 22.6 adds update discovery and safe auto-update behavior on top of the 22.5 Library Intelligence index.

The goal is simple:

> **If a locally installed LoRA or checkpoint has a newer Civitai version, CivitaiFlow should know about it without forcing the user to manually rediscover every model.**

## Update model

CivitaiFlow treats a Civitai model as a family and `modelVersionId` as the exact published version inside that family.

The update pipeline is:

```text
Indexed local library
      ↓
unique Civitai model IDs
      ↓
Civitai model API
      ↓
latest downloadable version
      ↓
compare latest modelVersionId + SHA-256 with local index
      │
      ├─ already present → CURRENT
      │
      └─ newer target missing → UPDATE AVAILABLE
```

The update scanner does not rely on filename comparisons.

## Update Center

The Forge CivitaiFlow connection panel now receives a compact **Model updates** row below the Library Intelligence status.

Example:

```text
● Model updates · 14 available
  Notify only · checked 2h ago · every 24h

[ Review ] [ Scan ] [ Update all ]
```

Opening **Review** shows individual assets:

```text
LoRA       Character Style     local 12345 → v3
Checkpoint Realistic XL       local 99120 → 110044
```

Each item can be queued independently.

## Safe update policy

CivitaiFlow intentionally does not delete or overwrite an installed version as part of automatic updating.

The v22.6 policies are:

- **Disabled** — no scheduled update scans.
- **Notify only** — default; scan and report newer versions without downloading them automatically.
- **Auto-download LoRAs (keep old)** — automatically queue newer LoRA versions and preserve the existing file.
- **Auto-download LoRAs + checkpoints (keep old)** — automatically queue newer LoRA and checkpoint versions and preserve the existing files.

Keeping the old version is the safe default for automatic acquisition because Stable Diffusion workflows can depend on the exact behavior of a specific checkpoint/LoRA release.

Replacement/archive policies can be added later as explicit opt-in library-management actions.

## Settings

Forge → Settings → **CivitaiFlow Manager** exposes:

- **Model update behavior**
- **Check Civitai model updates every N hours**
- **Auto-update concurrent downloads**
- **Maximum automatic model updates per scan**
- **Check for Civitai model updates after Forge starts**

The default configuration is intentionally conservative:

```text
Mode: Notify only
Interval: 24 hours
Concurrency: 2
Max automatic updates per cycle: 10
Startup check: enabled
```

## Scheduled checks

The update scheduler runs in the Forge process.

It waits for Library Intelligence to finish indexing before checking Civitai. This matters because update decisions require trustworthy local model/version state.

The scanner groups local files by Civitai model ID, so several installed versions of the same model family result in one remote model lookup.

A cached update report is stored in:

```text
<data-dir>/civitai-flow/update-cache.json
```

The cache contains update metadata only. It does not contain the Civitai API key.

## Determining the latest version

For each known model family, CivitaiFlow fetches the current Civitai model metadata and selects the newest published/downloadable version for which a supported model file exists.

The update is ignored when:

- the latest `modelVersionId` is already indexed locally; or
- the latest remote file SHA-256 is already present locally under another name/path.

This prevents an update scan from turning a rename or folder move into a duplicate download.

## Applying an update

An update is handed to the existing 22.5 smart acquisition pipeline using an explicit `modelVersionId`.

That means update downloads receive the same protections as manual **Send to Forge** actions:

```text
explicit target version
      ↓
local duplicate check
      ↓
type-aware storage routing
      ↓
*.part transfer
      ↓
SHA-256 verification
      ↓
collision-safe destination
      ↓
metadata + preview
      ↓
register in library index
```

If the old version and new version would share a filename but contain different bytes, the new file receives a `__v<modelVersionId>` suffix instead of overwriting the old file.

## Manual Update all

**Update all** queues all currently known newer versions.

The UI requires explicit confirmation and states that existing versions will be retained.

Automatic scheduled updating additionally honors the per-cycle limit from Settings, which prevents a newly indexed large library from unexpectedly queueing hundreds of downloads in one cycle.

## Local API

22.6 adds these loopback-only endpoints:

```text
GET  /civitaiflow/api/updates
POST /civitaiflow/api/updates/scan
POST /civitaiflow/api/updates/apply
POST /civitaiflow/api/updates/apply-all
```

They inherit the same loopback security boundary used by Library Intelligence. Non-local clients are rejected.

## Relationship with the Browser Bridge

The Browser Bridge already asks the local Forge service whether a Civitai model is installed or whether another version exists.

The Update Center adds the reverse workflow:

```text
Browsing Civitai
    ↓
card says Update available
```

and also:

```text
Forge library
    ↓
periodic scan
    ↓
14 installed models have newer Civitai versions
```

Both paths use the same library index and smart acquisition pipeline.

After an updated model is installed, future Browser Bridge status queries can resolve the new version as installed.

## Why updates do not replace files automatically

A newer Stable Diffusion asset is not always a drop-in replacement.

Possible changes include:

- different trigger words;
- different recommended weight;
- training changes;
- base-model changes;
- changed visual behavior;
- workflow incompatibility;
- regressions in a creator's newer release.

For that reason v22.6 defines **auto-update as automatic acquisition of the newer version, not automatic destruction of the older version**.

A future library-management layer can offer explicit policies such as:

```text
KEEP BOTH
ARCHIVE OLD
REPLACE OLD
```

with **KEEP BOTH** remaining the safest default.

## Remaining update work

Recommended follow-up improvements:

1. show Civitai version release notes / creator description changes before updating;
2. allow per-model pinning so selected assets never auto-update;
3. allow per-model/channel rules such as only updating within the same base model;
4. refresh Forge's LoRA/checkpoint inventories immediately after an update completes;
5. persistent/resumable download queue for multi-GB checkpoint updates;
6. disk-space estimation before **Update all**;
7. optional archive/replace policies with explicit user confirmation;
8. notifications when a scheduled scan finds new versions;
9. update history and rollback helpers.
