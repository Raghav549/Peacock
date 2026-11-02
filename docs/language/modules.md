# PEACOCK Modules — user file imports

PEACOCK now supports genuine multi-file programs. This is the foundation for
self-hosting the compiler.

## Syntax

```text
प्रकरण मुख्य
उपयोग सहायक        // file import: सहायक.सूत्र in same directory
उपयोग pkg.गणित     // dotted: pkg/गणित.सूत्र
उपयोग तन्त्रजाल     // builtin: kept as capability namespace

कार्य मुख्य() -> एकक {
    वर्ग(५); // from सहायक.सूत्र
}
```

## Resolution

* `उपयोग <name>;` where `<name>` is **not** a known builtin namespace
  (`तन्त्रजाल`, `सञ्चय`, `गणित`, `पाठ्य`, etc.) is treated as a file import.
* File search: `<base_dir>/<dotted_path>.सूत्र` and `<base_dir>/peacock_modules/<dotted_path>.सूत्र`
  with both internal and surface (Sanskrit) file-name variants.
* Imports are merged flat: top-level `कार्य`/`संघटन`/`प्रतिमान`/`अभ्यास` become
  available in the importer. Duplicate names are errors.
* Recursive imports are resolved depth-first; circular imports are rejected
  with `PE3001`.
* Builtin `उपयोग` entries are preserved for capability checking.

## Example

```
examples/modules/
  सहायक.सूत्र  — defines वर्ग, घन, बिन्दु
  main.सूत्र    — उपयोग सहायक; calls वर्ग(५)
```

```bash
./bin/peacock run examples/modules/main.सूत्र
# वर्ग ५ = 25
```

## Limitations (0.4)

* Flat merge only: `सहायक.वर्ग` qualified calls are not yet supported;
  imported symbols are available unqualified.
* No `रूपेण` aliases.
* No package versioning; `peacock_modules/` is conventional, not enforced.

This is an incremental foundation; future phases will add qualified imports,
re-exports and a deterministic package manager.
