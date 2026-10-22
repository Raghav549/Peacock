# Capability enforcement

Three layers, all required:

1. **Static.** A function must contain `अधिकार नाम;` in its own body to call
   a protected native. Capabilities are not inherited by callees.
2. **VM.** At dispatch, the VM checks the executing frame's declared set and the
   host's grants. Missing declaration or grant → `PE4001`.
3. **Host.** `HostPolicy` gates file and presentation operations, enforces budgets
   and the sandbox root, and refuses to present when no backend is attached
   (`PE4006`).

```peacock
उपयोग सञ्चय
कार्य मुख्य() -> एकक {
    अधिकार सञ्चय;                 // declare to the verifier
    सञ्चय.निधिरचना("out/generated");
    सञ्चय.पाठ्यलेखन("out/generated/status.txt", "सिद्धम्");
}
```

```bash
./bin/peacock run app.सूत्र --grant सञ्चय   # host grants authority
```

Capabilities in 0.2: `गणना`, `सञ्चय`, `दृश्य`.

```bash
./bin/peacock run app.सूत्र --grant दृश्य --present out/preview   # frames on disk
```

Neither layer alone is sufficient: `--grant सञ्चय` does not satisfy the static check;
`अधिकार सञ्चय;` does not grant host authority. The same is true for `दृश्य`: the
declaration is checked statically, the grant is checked by the VM, and the host
must also have attached a presentation backend.

`सञ्चय.निधिरचना(पथ)` creates parent directories inside the same `HostPolicy`
sandbox and requires `सञ्चय`. It does not grant a broader filesystem surface than
`पाठ्यपठन`/`पाठ्यलेखन`; symlink escapes, traversal and absolute paths outside
the root are still rejected. Confinement is best-effort and does not eliminate
host-side TOCTOU races.

`दृश्य` is presentation-only and carries no input or display-query authority.
`peacock audit app.सूत्र --json` lists declared capabilities and statically visible
privileged calls. It is informational only.

See [../../SECURITY.md](../../SECURITY.md) for the threat model, sandbox limits
and reporting process.
