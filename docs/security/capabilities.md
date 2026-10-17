# Capability enforcement

Three layers, all required:

1. **Static.** A function must contain `capability name;` in its own body to call
   a protected native. Capabilities are not inherited by callees.
2. **VM.** At dispatch, the VM checks the executing frame's declared set and the
   host's grants. Missing declaration or grant → `PE4001`.
3. **Host.** `HostPolicy` gates file and presentation operations, enforces budgets
   and the sandbox root, and refuses to present when no backend is attached
   (`PE4006`).

```peacock
use fs
fn main() -> Unit {
    capability fs;                 // declare to the verifier
    fs.write_text("out.txt", "ok");
}
```

```bash
./bin/peacock run app.pac --grant fs   # host grants authority
```

Capabilities in 0.1: `compute`, `fs`, `ui`.

```bash
./bin/peacock run app.pac --grant ui --present out/preview   # frames on disk
```

Neither layer alone is sufficient: `--grant fs` does not satisfy the static check;
`capability fs;` does not grant host authority. The same is true for `ui`: the
declaration is checked statically, the grant is checked by the VM, and the host
must also have attached a presentation backend.

`ui` is presentation-only and carries no input or display-query authority.
`peacock audit app.pac --json` lists declared capabilities and statically visible
privileged calls. It is informational only.

See [../../SECURITY.md](../../SECURITY.md) for the threat model, sandbox limits
and reporting process.
