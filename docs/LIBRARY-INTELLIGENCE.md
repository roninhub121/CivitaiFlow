# CivitaiFlow Library Intelligence

CivitaiFlow 22.5 adds a local model inventory so the Civitai browsing surface can answer a much more useful question than “can I download this?”:

> **Do I already own this exact model file, do I have another version, or should CivitaiFlow download it?**

The feature is designed around the original CivitaiFlow product loop:

```text
See the model on Civitai
        ↓
CivitaiFlow shows local state
        ↓
Send to Forge (one click)
        ↓
Deduplicate before transfer
        ↓
Download + SHA-256 verify
        ↓
Register in local Forge library
```

## Why filename-only duplicate checks are not enough

A model can be renamed, moved to another folder, or downloaded under a different filename. Conversely, two different model versions can share very similar names.

For that reason CivitaiFlow now tracks several identifiers:

- **Civitai model ID** — identifies the model family;
- **Civitai modelVersionId** — identifies a particular published version;
- **SHA-256** — identifies the exact local file bytes;
- **local path** — tells Forge where the asset currently lives.

The strongest duplicate signal is SHA-256. Version IDs are also used when older CivitaiFlow sidecars already identify the installed version.

## Index location

The runtime index is stored in Forge's data directory, not in the Git repository:

```text
<data-dir>/civitai-flow/library-index.json
```

The file contains local inventory metadata and SHA-256 values. It does **not** contain the Civitai API key.

## Indexed locations

22.5 scans these Forge locations when they exist:

| Civitai type | Local location |
| --- | --- |
| LoRA | `models/Lora` |
| Checkpoint | `models/Stable-diffusion` |
| VAE | `models/VAE` |
| Textual Inversion | `<data-dir>/embeddings` |

The primary v22.5 product focus is LoRAs and checkpoints. VAE/Textual Inversion paths are indexed so the storage layer has a consistent foundation.

## Incremental SHA-256 scan

On Forge startup CivitaiFlow starts the indexer in a background thread.

The first scan may need to hash every supported model file. That can take time on a large library, especially for multi-gigabyte checkpoints.

Future scans are incremental:

1. CivitaiFlow compares file path, size, and nanosecond modification time with the persisted index.
2. Unchanged files reuse the cached SHA-256.
3. New or modified files are hashed again.
4. Deleted files disappear from the next index snapshot.

Downloads are intentionally held while the initial inventory is being built. This prevents the “duplicate protection is still warming up, but a download already started” race condition.

## Identifying existing Civitai assets

CivitaiFlow reads its own JSON sidecars when available:

```json
{
  "civitai model id": 123456,
  "civitai version id": 987654,
  "civitai file sha256": "..."
}
```

For older or manually managed files without CivitaiFlow metadata, the indexer can resolve SHA-256 values through Civitai's public batch by-hash endpoint in groups of up to 100 hashes.

That allows the inventory to recognize many pre-existing files even when their filename or folder no longer matches the original Civitai name.

## Browser states

The optional Browser Bridge queries the local Forge service and updates model-card controls.

### Send to Forge

No indexed local model with that model ID/version is known.

```text
[ Send to Forge ]
```

### Installed

The exact target is already present locally.

```text
[ Installed ]
```

The button does not download the same target again.

### Update available

CivitaiFlow knows that a model from the same family is installed, but the current/latest Civitai version is different.

```text
[ Update available ]
```

Clicking it queues the current target version instead of overwriting the older version blindly.

### Downloading

A transfer is active. The card can display live progress:

```text
[ Downloading 64% ]
```

### Verifying

The HTTP transfer finished and CivitaiFlow is hashing the temporary file before making it final.

```text
[ Verifying ]
```

### Indexing library

The local SHA-256 inventory is still being built.

```text
[ Indexing library ]
```

CivitaiFlow holds smart downloads until the index becomes ready.

## Direct Browser Bridge transport

22.5 no longer requires the Browser Bridge to copy a URL into the clipboard when Forge is available locally.

The preferred path is:

```text
Civitai card
   ↓
Browser Bridge service worker
   ↓
http://127.0.0.1:7860/civitaiflow/api/capture
   ↓
CivitaiFlow smart acquisition pipeline
```

If the local service cannot be reached, the content script falls back to the original clipboard/Sniper behavior.

The Browser Bridge never receives the Civitai API token. Authentication stays inside the Forge Python backend.

## Local API

The smart bridge exposes loopback-only endpoints:

```text
GET  /civitaiflow/api/health
GET  /civitaiflow/api/status?modelId=...&modelVersionId=...
POST /civitaiflow/api/capture
GET  /civitaiflow/api/library
POST /civitaiflow/api/reindex
```

Requests from non-loopback clients are rejected. This is deliberate: a Forge instance exposed on a LAN should not silently become a remote model-download service.

## Version-aware resolution

Captured Civitai URLs now preserve `modelVersionId` when it is present.

Example:

```text
https://civitai.com/models/123456?modelVersionId=987654
```

The smart resolver selects `987654` specifically. If the version does not belong to the model/API result, the download fails clearly rather than silently choosing another version.

If no version is specified, the first/current version returned by the Civitai model API remains the target and the status layer can compare it with locally indexed versions.

## Model routing

The smart downloader routes supported Civitai types to their Forge locations instead of writing every `.safetensors` file into the LoRA directory.

Unsupported Civitai resource types fail explicitly.

This eliminates one of the highest-risk behaviors from the original downloader: silently putting a checkpoint in the LoRA repository.

## Download integrity

The final file lifecycle is now:

```text
remote file
   ↓
filename.ext.part
   ↓
stream download
   ↓
SHA-256 calculation
   ↓
compare with Civitai SHA-256 (when supplied)
   ↓
atomic rename to filename.ext
   ↓
write preview + JSON metadata
   ↓
register in local index
```

A hash mismatch rejects the transfer and removes the temporary file. Corrupted bytes are not promoted into the Forge model library.

## Collision behavior

If the intended local filename already exists but has different bytes, CivitaiFlow does not overwrite it blindly. The new target receives a version suffix such as:

```text
ModelName__v987654.safetensors
```

This allows multiple legitimate model versions to coexist while SHA-256 deduplication still prevents storing the exact same file twice.

## Reindexing

The CivitaiFlow Forge panel now shows a compact library status row under the connection card, for example:

```text
● 8,412 indexed · 5,202 LoRA · 2,881 checkpoints     [ Reindex ]
```

Use **Reindex** after manually copying, moving, replacing, or deleting model files while Forge is running.

## Security boundaries

Library Intelligence intentionally does not:

- read browser cookies;
- expose the Civitai API key to the browser extension;
- accept Browser Bridge commands from non-loopback clients;
- remove Civitai/Google iframe protections;
- trust filenames as proof that two files are identical.

## Remaining work

The next improvements should build on this index rather than creating another parallel asset database:

1. configurable storage rules by base model/category;
2. richer update policy (keep old version / replace / archive);
3. stale-version and missing-file repair reports;
4. optional duplicate cleanup after user review;
5. Forge refresh after successful model installation;
6. queue persistence across Forge restarts;
7. optional Windows secure token storage;
8. official Civitai OAuth + PKCE once CivitaiFlow has its own registered client.
