# PEACOCK for VS Code (prepared)

A minimal, declarative extension: language registration for `.pac`, bracket and
comment behaviour, and a TextMate grammar shared with the proposed Linguist
submission. There is no language server, formatter or debugger yet.

```bash
cd editors/vscode
npm install -g @vscode/vsce   # optional, external tool; not required to edit
vsce package
```

This package has **not** been published to the VS Code Marketplace, and GitHub
does not yet recognise PEACOCK. The grammar is also usable by any TextMate-
compatible editor by copying `syntaxes/peacock.tmLanguage.json`.

Known limitations: contextual keywords (`input`, `output`, `stack`, `epochs`,
...), named arguments and type parameters receive only generic highlighting.
