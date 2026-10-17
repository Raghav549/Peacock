// PEACOCK's own static web application and HTML export backend.
//
// Every page, component, navigation decision and renderer in this site is
// authored in PEACOCK. The Python bootstrap compiles and runs this `.pac` file;
// `fs` is the documented host boundary used to read real examples and emit
// semantic HTML, CSS and the project logo. The browser renders standard HTML
// and CSS. No JavaScript or external UI framework is generated.

module peacock_website

use fs
use process
use text

struct UiNode {
    tag: String,
    class_name: String,
    id: String,
    href: String,
    src: String,
    alt: String,
    aria_label: String,
    text: String,
    children: List<UiNode>
}

struct Page {
    slug: String,
    nav_label: String,
    title: String,
    eyebrow: String,
    summary: String,
    sections: List<UiNode>
}

fn ui_node(tag: String, class_name: String, id: String, href: String, src: String, alt: String, aria_label: String, text: String, children: List<UiNode>) -> UiNode {
    return UiNode(tag, class_name, id, href, src, alt, aria_label, text, children);
}

fn text_node(tag: String, class_name: String, value: String) -> UiNode {
    return ui_node(tag, class_name, "", "", "", "", "", value, []);
}

fn element(tag: String, class_name: String, children: List<UiNode>) -> UiNode {
    return ui_node(tag, class_name, "", "", "", "", "", "", children);
}

fn link_node(label: String, href: String, class_name: String) -> UiNode {
    return ui_node("a", class_name, "", href, "", "", "", label, []);
}

fn image_node(source: String, alt_text: String, class_name: String) -> UiNode {
    return ui_node("img", class_name, "", "", source, alt_text, "", "", []);
}

fn html_escape(value: String) -> String {
    let mut escaped = "";
    let mut i = 0;
    while i < len(value) {
        let ch = text.char_at(value, i);
        if ch == "&" {
            escaped = escaped + "&amp;";
        } else if ch == "<" {
            escaped = escaped + "&lt;";
        } else if ch == ">" {
            escaped = escaped + "&gt;";
        } else if ch == "\"" {
            escaped = escaped + "&quot;";
        } else if ch == "'" {
            escaped = escaped + "&#39;";
        } else {
            escaped = escaped + ch;
        }
        i += 1;
    }
    return escaped;
}

fn html_attribute(name: String, value: String) -> String {
    return " " + name + "=\"" + html_escape(value) + "\"";
}

fn render_node(item: UiNode) -> String {
    let mut output = "<" + item.tag;
    if item.class_name != "" {
        output = output + html_attribute("class", item.class_name);
    }
    if item.id != "" {
        output = output + html_attribute("id", item.id);
    }
    if item.href != "" {
        output = output + html_attribute("href", item.href);
    }
    if item.src != "" {
        output = output + html_attribute("src", item.src);
    }
    if item.tag == "img" {
        output = output + html_attribute("alt", item.alt);
    }
    if item.aria_label != "" {
        output = output + html_attribute("aria-label", item.aria_label);
    }
    output = output + ">";
    if item.tag == "img" {
        return output;
    }
    output = output + html_escape(item.text);
    for child in item.children {
        output = output + render_node(child);
    }
    return output + "</" + item.tag + ">";
}

fn badge(label: String, status: String) -> UiNode {
    let mut status_class = "status--planned";
    if status == "implemented" {
        status_class = "status--implemented";
    } else if status == "partial" {
        status_class = "status--partial";
    } else if status == "experimental" {
        status_class = "status--experimental";
    } else if status == "blocked" {
        status_class = "status--blocked";
    }
    return text_node("span", "status " + status_class, label);
}

fn card(title: String, status_label: String, status: String, description: String) -> UiNode {
    return element("article", "panel feature-card", [
        badge(status_label, status),
        text_node("h3", "", title),
        text_node("p", "muted", description)
    ]);
}

fn grid(cards: List<UiNode>) -> UiNode {
    return element("div", "card-grid", cards);
}

fn section_node(section_id: String, title: String, description: String, children: List<UiNode>) -> UiNode {
    return ui_node("section", "content-section", section_id, "", "", "", "", "", [
        element("div", "section-heading", [
            text_node("h2", "", title),
            text_node("p", "muted", description)
        ]),
        element("div", "section-content", children)
    ]);
}

fn code_panel(title: String, source: String) -> UiNode {
    return element("article", "panel code-panel", [
        text_node("h3", "code-title", title),
        text_node("p", "copy-hint", "Selectable source — use your browser's copy command."),
        element("pre", "code-frame", [text_node("code", "language-peacock", source)])
    ]);
}

fn page(slug: String, nav_label: String, title: String, eyebrow: String, summary: String, sections: List<UiNode>) -> Page {
    return Page(slug, nav_label, title, eyebrow, summary, sections);
}

fn nav_markup(pages: List<Page>, current_slug: String) -> String {
    let mut output = "<nav class=\"primary-nav\" aria-label=\"Primary\"><div class=\"nav-links\">";
    for item in pages {
        let mut class_name = "nav-link";
        let mut current = "";
        if item.slug == current_slug {
            class_name = "nav-link is-current";
            current = " aria-current=\"page\"";
        }
        output = output + "<a" + html_attribute("class", class_name) + html_attribute("href", item.slug) + current + ">" + html_escape(item.nav_label) + "</a>";
    }
    return output + "</div></nav>";
}

fn render_page(item: Page, pages: List<Page>) -> String {
    let mut output = "<!doctype html>\n<html lang=\"en\"><head>";
    output = output + "<meta charset=\"utf-8\"><meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">";
    output = output + "<meta name=\"theme-color\" content=\"#080d18\">";
    output = output + "<meta" + html_attribute("name", "description") + html_attribute("content", item.summary) + ">";
    output = output + "<title>" + html_escape(item.nav_label) + " — PEACOCK AI</title>";
    output = output + "<link rel=\"stylesheet\" href=\"styles.css\"></head><body>";
    output = output + "<a class=\"skip-link\" href=\"#main\">Skip to content</a>";
    output = output + "<header class=\"site-header\"><div class=\"header-inner\"><a class=\"brand\" href=\"index.html\" aria-label=\"PEACOCK AI home\">";
    output = output + render_node(image_node("assets/peacock.svg", "", "brand-logo"));
    output = output + "<span class=\"brand-copy\"><strong>PEACOCK AI</strong><span>Language · compiler · studio</span></span></a>";
    output = output + nav_markup(pages, item.slug) + "</div></header>";
    output = output + "<main id=\"main\" class=\"page-main\"><header class=\"page-heading\">";
    output = output + "<p class=\"eyebrow\">" + html_escape(item.eyebrow) + "</p>";
    output = output + "<h1>" + html_escape(item.title) + "</h1>";
    output = output + "<p class=\"page-summary\">" + html_escape(item.summary) + "</p></header>";
    output = output + "<div class=\"content-stack\">";
    for section in item.sections {
        output = output + render_node(section);
    }
    output = output + "</div></main>";
    output = output + "<footer class=\"site-footer\"><div><strong>PEACOCK AI</strong><p>Experimental language and ecosystem. Status is evidence-led, not a release claim.</p></div>";
    output = output + "<div class=\"footer-links\"><a href=\"https://github.com/Raghav549/Peacock\">Repository</a><a href=\"https://github.com/Raghav549/Peacock/blob/main/STATUS.md\">Status</a><a href=\"https://github.com/Raghav549/Peacock/blob/main/SECURITY.md\">Security</a></div></footer>";
    return output + "</body></html>\n";
}

fn home_page(hello_source: String) -> Page {
    let hero = element("section", "hero-panel", [
        badge("Experimental · not self-hosting", "experimental"),
        text_node("p", "hero-kicker", "A programming language for AI-native work"),
        text_node("p", "hero-copy", "PEACOCK brings a real .pac language, a bootstrap compiler and VM, CPU tensor/autodiff tools, and an original software graphics stack into one carefully scoped project."),
        element("div", "hero-actions", [
            link_node("Explore the language", "language.html", "button button-primary"),
            link_node("Run your first program", "download.html", "button button-secondary")
        ]),
        text_node("p", "hero-note", "Python remains the bootstrap. The compiler is not yet self-hosting; mobile, GPU and 3D backends are not implemented.")
    ]);
    let current = section_node("today", "What works today", "These are executable, tested subsystems—not implied platform promises.", [
        grid([
            card("The language and VM", "Implemented", "implemented", "A typed .pac subset compiles through verified IR and bytecode into the Python-hosted PEACOCK VM."),
            card("Small-scale AI", "CPU · small models", "implemented", "Tensor operations, reverse-mode autodiff, dense layers, SGD/Adam, training and evaluation run on CPU."),
            card("Colour and 2D graphics", "Software reference", "implemented", "Perceptual colour utilities, a deterministic 2D software rasteriser and PNG output are available."),
            card("Self-hosting", "Shadow · experimental", "experimental", "PEACOCK lexer/parser parity and expanded semantic-kernel probes; the Python analyser remains authoritative.")
        ])
    ]);
    let snippet = section_node("first-program", "A real .pac program", "This source is read from examples/hello.pac while building the website, then escaped and rendered by PEACOCK.", [
        code_panel("examples/hello.pac", hello_source)
    ]);
    let principles = section_node("principles", "A long horizon, with explicit boundaries", "PEACOCK is an independent language project—not a wrapper around a third-party ML or UI framework.", [
        grid([
            card("Language first", "Working subset", "implemented", "A hand-written lexer, parser, static checker, IR verifier, optimiser, bytecode compiler and VM."),
            card("AI in the type model", "CPU verified", "partial", "Tensor shapes and dtypes inform checks; tested gradients and tiny neural-network workloads are present."),
            card("Original visual stack", "2D today", "partial", "Colour, rasterisation, motion and layout foundations exist; a general interactive UI toolkit and 3D renderer do not."),
            card("Evidence over slogans", "Open status", "implemented", "Tests, limitations, bootstrap boundaries and missing targets are documented in the repository.")
        ])
    ]);
    return page("index.html", "Home", "A language for AI-native software.", "The PEACOCK project", "An independent programming language and development ecosystem in active, early-stage construction.", [hero, current, snippet, principles]);
}

fn language_page(hello_source: String, tour_source: String) -> Page {
    let concepts = section_node("language-core", "The implemented language core", "The current v0.1 language is deliberately smaller than the long-term design.", [
        grid([
            card("Source and grammar", ".pac", "implemented", "Modules, imports of built-in namespaces, structs, functions, expressions, loops, errors and capability declarations."),
            card("Types", "Static subset", "implemented", "Int, Float, Bool, String, Unit, List, tensors, nominal structs and opaque engine types; no user-defined generics yet."),
            card("Diagnostics", "PE1xxx–PE7xxx", "implemented", "Source spans, stable diagnostic codes, error recovery in the Python parser and targeted type/capability messages."),
            card("Collections", "List<T>", "partial", "Mutable lists, indexing and common list operations exist. Unicode and iterator APIs remain limited.")
        ])
    ]);
    let first = section_node("hello", "Start with ordinary code", "The build pipeline consumes this actual PEACOCK source file; it is not Python in a renamed file.", [
        code_panel("examples/hello.pac", hello_source),
        grid([
            card("No implicit numeric coercion", "Explicit", "implemented", "Int and Float are distinct; write an explicit conversion rather than relying on silent widening."),
            card("Capability-gated effects", "Declared + granted", "implemented", "Filesystem, compute and UI authority are declared in source and granted independently by the host.")
        ])
    ]);
    let tour = section_node("syntax", "Read a wider syntax tour", "The tour exercises functions, expressions, lists, structs, control flow and error handling in the supported grammar.", [
        code_panel("examples/tour.pac", tour_source),
        link_node("Open the full language specification", "https://github.com/Raghav549/Peacock/blob/main/SPECIFICATION.md", "inline-link")
    ]);
    return page("language.html", "Language", "A typed language with .pac at its core.", "Language reference", "Learn the syntax and types that the current compiler actually accepts, plus the boundaries that remain future work.", [concepts, first, tour]);
}

fn compiler_page() -> Page {
    let pipeline = section_node("pipeline", "The real compilation pipeline", "Source passes through the same stages used by the CLI and tests.", [
        grid([
            card("Lex and parse", "Implemented", "implemented", "Token stream → AST with source spans and recoverable Python-bootstrap diagnostics."),
            card("Semantic analysis", "Python authoritative", "implemented", "Name resolution, scopes, types, function calls, returns and capability checks annotate the AST."),
            card("IR and optimisation", "Verified subset", "implemented", "Typed linear IR is verified before and after constant/branch folding and dead temporary elimination."),
            card("Bytecode and VM", "Python runtime", "implemented", "The bytecode image is verified, fingerprinted and run by PEACOCK's custom stack VM.")
        ])
    ]);
    let bootstrap = section_node("bootstrap", "Bootstrap and self-hosting", "A PEACOCK-written component is not the same thing as a self-hosting compiler.", [
        grid([
            card("Tokenizer and parser", "Parity-tested", "partial", "PEACOCK source tokenizes and parses the core grammar; parser parity uses structural AST digests."),
            card("Semantic kernel", "Shadow mode", "experimental", "The .pac type model now probes relations, operators, lists/indexing, local scopes, names, declarations, assignments, signatures, calls, conditions and returns."),
            card("Production semantics", "Still Python", "partial", "The Python SemanticAnalyzer produces diagnostics and remains the production reference path."),
            card("IR through VM migration", "Not started", "planned", "IR construction, verification, optimisation, bytecode, runtime and bootstrap reproducibility remain future stages.")
        ]),
        code_panel("Opt in to differential semantic probes", "./bin/peacock check examples/tour.pac --semantic-shadow --json")
    ]);
    return page("compiler.html", "Compiler", "An original compiler, still on its bootstrap.", "Compiler architecture", "The compiler is a working language implementation, but PEACOCK is not self-hosting and does not yet emit native code or WebAssembly.", [pipeline, bootstrap]);
}

fn ai_engine_page(xor_source: String, tensor_source: String) -> Page {
    let capabilities = section_node("ai-capabilities", "What the Intelligence Engine verifies", "The current engine is independently implemented in the repository and uses CPU-only Python numerical kernels.", [
        grid([
            card("Tensor algebra", "CPU · tested", "implemented", "Shape-aware tensors, indexing, reductions, broadcasting, rank-2 matmul, activations and stable softmax."),
            card("Automatic differentiation", "Reverse mode", "implemented", "A local computation graph accumulates gradients; finite-difference checks exercise the tested operations."),
            card("Training", "Small models", "implemented", "Dense/Sequential models, XOR and spiral datasets, MSE/cross-entropy, SGD/Adam and evaluation metrics."),
            card("Inference and save/load", "Custom artifacts", "partial", "Small-model inference and .pkm serialization/quantisation helpers exist; no production model-serving target.")
        ])
    ]);
    let examples = section_node("ai-examples", "Executable AI examples", "The site embeds the current source files at build time; it does not invent benchmark results.", [
        code_panel("examples/tensors.pac", tensor_source),
        code_panel("examples/xor.pac", xor_source),
        text_node("p", "callout", "No GPU, accelerator backend, frontier-scale training, attention stack or mobile inference backend is verified in this checkout.")
    ]);
    return page("ai-engine.html", "AI Engine", "Numerical AI primitives with honest scale limits.", "PEACOCK Intelligence Engine", "A small, testable CPU foundation for tensors, autodiff, neural-network training, evaluation and inference.", [capabilities, examples]);
}

fn frontend_page(aurora_source: String, motion_source: String) -> Page {
    let current = section_node("visual-core", "The visual engine that exists", "PEACOCK has an original 2D software renderer and colour/motion libraries; it does not yet have a general-purpose widget framework.", [
        grid([
            card("Colour", "Perceptual utilities", "implemented", "sRGB/XYZ, CIELAB, Oklab/Oklch, blending, palette generation, gradients and contrast helpers."),
            card("2D rendering", "Software reference", "implemented", "Premultiplied linear-light RGBA, source-over compositing, coverage-sampled shapes, glow approximations and PNG output."),
            card("Motion and layout", "Foundations", "partial", "Easing, springs, timelines, flex layout and 2D AABB physics are libraries; no live input/frame scheduler is integrated."),
            card("Interactive UI and 3D", "Roadmap", "planned", "Widgets, text shaping, accessibility runtime, 3D scene graphs, materials, GPU rasterisation and platform input are not implemented.")
        ])
    ]);
    let site_renderer = section_node("site-renderer", "This website is a PEACOCK application", "website/site.pac builds a component tree, escapes text and attributes, applies route state, then emits accessible static HTML and responsive CSS through the fs capability.", [
        grid([
            card("Declarative component tree", "PEACOCK source", "experimental", "Reusable UiNode, Page, card, section, status and code-panel components are defined in .pac."),
            card("Routes and navigation", "12 static routes", "implemented", "A shared renderer creates page links and marks the current route with aria-current; every page is a separate HTML route."),
            card("Browser boundary", "HTML + CSS only", "implemented", "The bootstrap runs the .pac program; the browser renders generated semantic HTML/CSS. No JavaScript or external UI framework is generated."),
            card("Not a general frontend runtime", "Static export", "partial", "This site generator is a real PEACOCK application, not a claim that interactive native UI or 3D has shipped.")
        ])
    ]);
    let examples = section_node("visual-examples", "See the actual .pac programs", "The snippets below are read from the tested example sources during the site build.", [
        code_panel("examples/aurora.pac", aurora_source),
        code_panel("examples/motion.pac", motion_source)
    ]);
    return page("frontend-studio.html", "Frontend Studio", "A visual stack grows from colour and pixels.", "Frontend Studio", "A measured path from the current software renderer to a native, accessible and interactive application runtime.", [current, site_renderer, examples]);
}

fn docs_page(hello_source: String) -> Page {
    let setup = section_node("setup", "Install the bootstrap and run a program", "This repository currently ships a Python-hosted development toolchain; there is no official binary installer or release package.", [
        code_panel("From a source checkout", "python3 --version\n./bin/peacock version\n./bin/peacock check examples/hello.pac\n./bin/peacock run examples/hello.pac"),
        code_panel("First PEACOCK source", hello_source),
        grid([
            card("Requirements", "Python 3.11+", "implemented", "The bootstrap and tests use the Python standard library; package building uses the declared setuptools build backend."),
            card("Canonical files", ".pac / .pkb", "implemented", "Source files use .pac. The compiler emits verified .pkb bytecode images."),
            card("Capability grants", "Explicit", "implemented", "Use --grant fs, compute or ui only when the source declares the capability and the host boundary is configured."),
            card("Editor support", "Prepared", "partial", "A TextMate grammar and VS Code metadata exist; no published extension or language server is available.")
        ]),
        link_node("CLI reference", "https://github.com/Raghav549/Peacock/blob/main/docs/cli.md", "inline-link"),
        link_node("Language specification", "https://github.com/Raghav549/Peacock/blob/main/SPECIFICATION.md", "inline-link")
    ]);
    let workflow = section_node("workflow", "A minimal developer workflow", "Check, test and build use the same front end; the `test` command runs the repository's unittest suite.", [
        code_panel("Daily commands", "./bin/peacock check path/to/app.pac\n./bin/peacock run path/to/app.pac\n./bin/peacock test\n./bin/peacock build path/to/app.pac -o app.pkb")
    ]);
    return page("docs.html", "Docs", "Get from a checkout to a running .pac program.", "Developer documentation", "Practical, reproducible instructions for the currently supported bootstrap environment.", [setup, workflow]);
}

fn examples_page(hello_source: String, xor_source: String, tensor_source: String, aurora_source: String) -> Page {
    let filters = section_node("example-index", "Browse by working capability", "Choose a category to jump to runnable examples; this is a static, keyboard-accessible filter rather than a JavaScript search widget.", [
        element("div", "filter-links", [
            link_node("Language", "#language-examples", "filter-chip"),
            link_node("AI and tensors", "#ai-examples", "filter-chip"),
            link_node("Graphics", "#graphics-examples", "filter-chip")
        ])
    ]);
    let language = section_node("language-examples", "Language", "A hello-world program and a larger language tour are checked in with the compiler.", [
        code_panel("examples/hello.pac", hello_source),
        link_node("Open examples/tour.pac", "https://github.com/Raghav549/Peacock/blob/main/examples/tour.pac", "inline-link")
    ]);
    let ai = section_node("ai-examples", "AI and tensors", "Small CPU-only programs demonstrate tensor arithmetic and a trainable XOR model.", [
        code_panel("examples/tensors.pac", tensor_source),
        code_panel("examples/xor.pac", xor_source),
        text_node("p", "callout", "Run the training example with `./bin/peacock run examples/xor.pac --grant compute`. No GPU is required or claimed.")
    ]);
    let graphics = section_node("graphics-examples", "Graphics", "The reference renderer can produce deterministic image output from PEACOCK programs.", [
        code_panel("examples/aurora.pac", aurora_source),
        text_node("p", "callout", "The current renderer is software 2D; aurora colour fields are artistic procedural graphics, not a physical sky simulation.")
    ]);
    return page("examples.html", "Examples", "Only runnable examples, grouped by what works.", "Examples gallery", "A verified collection of PEACOCK programs for the implemented compiler, CPU AI and software graphics subset.", [filters, language, ai, graphics]);
}

fn research_page() -> Page {
    let stance = section_node("research-stance", "Research informs engineering; it does not substitute for it", "The repository currently maintains a 162-entry bibliography, a literature review, design decisions, open questions and a reproducible benchmark methodology.", [
        grid([
            card("Compiler and language design", "Applied", "partial", "The implementation uses established compiler, typing, IR and VM principles; no formal soundness proof is claimed."),
            card("Differentiable programming", "Small reverse-mode engine", "partial", "The tensor tape and finite-difference tests are a compact implementation, not an MLIR/JAX-scale compiler."),
            card("Numerical and visual methods", "Documented approximations", "partial", "Floating-point deviations, 4×4 coverage sampling, Oklab colour utilities and artistic fBm are described in project docs."),
            card("AI safety and agents", "Open research", "planned", "Reasoning, planning, multimodal agents, interpretability and safety remain research questions—not shipped capabilities.")
        ])
    ]);
    let sources = section_node("sources", "Source library and verification status", "The bibliography file records 162 entries spanning programming languages, compilers, differentiable programming, numerical methods, graphics, security and evaluation.", [
        text_node("p", "callout", "The current build environment does not permit direct access to arXiv or publisher hosts. Do not treat every identifier in the inherited bibliography as externally verified; the research README records that limitation."),
        link_node("Open research/references.bib", "https://github.com/Raghav549/Peacock/blob/main/research/references.bib", "inline-link"),
        link_node("Open literature review and limitations", "https://github.com/Raghav549/Peacock/blob/main/research/literature-review.md", "inline-link"),
        link_node("Open benchmark methodology", "https://github.com/Raghav549/Peacock/blob/main/research/benchmark-methodology.md", "inline-link")
    ]);
    let decisions = section_node("decisions", "Research questions become implementation decisions", "The next semantic migration is executed as shadow probes against the Python reference: retain the oracle, compare valid and invalid programs, and keep production semantics switched on until parity gates pass.", [
        grid([
            card("Evidence is scoped", "No fabricated numbers", "implemented", "Checked-in benchmarks describe a small reference machine and are not comparative performance claims."),
            card("Limitations are recorded", "Negative results count", "implemented", "The project labels CPU-only, unsupported GPU, incomplete frontends and platform gaps explicitly."),
            card("Research remains open", "No AGI guarantee", "planned", "AGI is an open research objective; no consequence is promised by the language or current implementation.")
        ])
    ]);
    return page("research.html", "Research", "A research library with visible verification limits.", "Research programme", "A maintained source collection and design record, paired with small working implementations and explicit evidence boundaries.", [stance, sources, decisions]);
}

fn roadmap_page() -> Page {
    let status = section_node("status", "Current status", "The project is early-stage. Status below distinguishes implemented and tested code from experiments, plans and blocked targets.", [
        grid([
            card("Lexer → VM", "Implemented · tested", "implemented", "The bootstrap compiler, verifier, bytecode artifact and custom VM run the current language subset."),
            card("AI engine", "Implemented · CPU", "implemented", "Small tensors, autodiff, dense models, training, metrics and serialization are tested on CPU."),
            card("Semantic self-hosting", "Expanded shadow prototype", "experimental", "Type relations, expression typing, scope/name probes, declarations, assignment, user signatures/calls and returns run in PEACOCK shadow checks."),
            card("Website", "PEACOCK-authored static export", "implemented", "Twelve actual routes are produced by compiling and running website/site.pac; generated HTML/CSS contains no JavaScript."),
            card("Native mobile / GPU / 3D", "Not implemented", "planned", "No Android/iOS build, verified GPU kernel, native 3D renderer or self-hosted VM is available.")
        ])
    ]);
    let next = section_node("milestones", "Dependency-ordered milestones", "A staged migration protects the working compiler and keeps each new subsystem testable.", [
        grid([
            card("Semantic analysis", "Next: diagnostics + full modules", "partial", "The shadow kernel is not production-selected; field/method semantics, native overloads, model declarations, complete diagnostics and corpus acceptance remain."),
            card("IR and bytecode", "Planned", "planned", "Port AST-to-IR lowering, verification, optimisation and bytecode generation one coherent stage at a time."),
            card("Runtime and packaging", "Planned", "planned", "Self-host the VM/runtime and then prove reproducible bootstrap compilation before a self-hosting claim."),
            card("Frontend and targets", "Research / partial", "partial", "Build on 2D rendering and this static site export; interactive native UI, 3D, mobile and GPU require independent evidence.")
        ])
    ]);
    return page("roadmap.html", "Roadmap", "A roadmap with acceptance gates—not promises.", "Roadmap and status", "Completed, partial, experimental, planned and blocked work is separated so that file count cannot masquerade as readiness.", [status, next]);
}

fn security_page() -> Page {
    let security_model = section_node("security-model", "A layered capability model", "Authority must be declared by source, checked by the VM and granted by the host.", [
        grid([
            card("Static declarations", "Implemented", "implemented", "Protected native calls require the enclosing function to declare the corresponding capability."),
            card("Host grants", "Independent", "implemented", "`--grant fs`, `compute` or `ui` is separate from a source declaration; grants do not leak between VM instances."),
            card("Filesystem policy", "Best effort", "partial", "Path traversal, absolute path and symlink escapes are rejected; `fs.create_dir` is sandbox-rooted."),
            card("Resource budgets", "Implemented subset", "implemented", "VM steps, call depth, output, tensor elements, dataset samples and training epochs are limited."),
            card("Threat boundary", "Not an OS sandbox", "partial", "Python owns process memory and filesystem syscalls. TOCTOU and hostile-host risks are documented; no formal isolation claim is made.")
        ]),
        code_panel("Capability example", "use fs\nfn main() -> Unit {\n    capability fs;\n    fs.create_dir(\"generated/site\");\n    fs.write_text(\"generated/site/index.txt\", \"hello\");\n}")
    ]);
    let reporting = section_node("reporting", "Responsible vulnerability reporting", "Do not include secrets or exploit payloads in a public issue. Follow the repository security policy for private reports.", [
        link_node("Security policy", "https://github.com/Raghav549/Peacock/blob/main/SECURITY.md", "button button-primary"),
        link_node("Capability design notes", "https://github.com/Raghav549/Peacock/blob/main/docs/security/capabilities.md", "inline-link")
    ]);
    return page("security.html", "Security", "Explicit permissions, modest claims.", "Security architecture", "PEACOCK has layered capability checks and resource budgets; it is not a kernel-enforced sandbox or audited security product.", [security_model, reporting]);
}

fn download_page(hello_source: String) -> Page {
    let get_started = section_node("get-started", "There is no release binary yet", "PEACOCK does not currently publish installers, signed packages or a version manager. Use the source repository and the Python bootstrap.", [
        code_panel("Source checkout", "git clone https://github.com/Raghav549/Peacock.git\ncd Peacock\npython3 --version\n./bin/peacock version\n./bin/peacock run examples/hello.pac"),
        code_panel("First .pac program", hello_source),
        grid([
            card("Verified host", "Linux · headless", "implemented", "The checked-in Python bootstrap and tests run in the repository environment."),
            card("Python requirement", "3.11+", "implemented", "The pyproject declares Python 3.11 or later; no published platform binaries are provided."),
            card("Other platforms", "Unverified / absent", "blocked", "No Android, iOS, desktop-shell or WebAssembly build is claimed by this site."),
            card("Release packages", "Not available", "planned", "No public PEACOCK release, installer or package registry should be inferred from this source checkout.")
        ]),
        link_node("Browse the repository", "https://github.com/Raghav549/Peacock", "button button-secondary")
    ]);
    let faq = section_node("support", "Before you start", "A few important boundaries for a first-time user.", [
        element("details", "panel details-panel", [
            text_node("summary", "", "Can I compile PEACOCK without Python?"),
            text_node("p", "muted", "Not yet. The Python bootstrap remains required to compile, run, build and test PEACOCK programs.")
        ]),
        element("details", "panel details-panel", [
            text_node("summary", "", "Does PEACOCK use a GPU or train frontier models?"),
            text_node("p", "muted", "No. The verified engine is CPU-only and intended for small models and tests.")
        ])
    ]);
    return page("download.html", "Get started", "Start from source; no downloads are invented.", "Download and get started", "A truthful installation path for the environment the project currently supports.", [get_started, faq]);
}

fn community_page() -> Page {
    let participation = section_node("participate", "Build with the project", "PEACOCK is a public, early-stage repository. Contributions should preserve working code, tests and honest status labels.", [
        grid([
            card("Repository", "Public source", "implemented", "Inspect the compiler, runtime, AI engine, frontend, examples, tests and roadmap in one repository."),
            card("Contribution guide", "Read before changes", "implemented", "The guide describes code style, tests, research attribution and how to make focused contributions."),
            card("Issues and discussions", "No community metrics", "partial", "Use GitHub for project participation. This site does not publish invented user, star or community statistics."),
            card("Linguist and editor", "Prepared, not accepted", "partial", "A .pac grammar and editor metadata are present; official GitHub Linguist recognition and extension publication remain unconfirmed.")
        ]),
        element("div", "hero-actions", [
            link_node("GitHub repository", "https://github.com/Raghav549/Peacock", "button button-primary"),
            link_node("Contribution guide", "https://github.com/Raghav549/Peacock/blob/main/CONTRIBUTING.md", "button button-secondary"),
            link_node("Roadmap", "roadmap.html", "button button-secondary")
        ])
    ]);
    let participate = section_node("participate-well", "How to help well", "The most valuable contributions improve real compiler/runtime behavior and add regression evidence.", [
        grid([
            card("Reproduce first", "Tests matter", "implemented", "Run the unittest suite and targeted CLI cases before and after a change."),
            card("Keep the boundary visible", "No hidden framework swap", "implemented", "If a feature depends on Python, a browser API or a host SDK, document that boundary explicitly."),
            card("Research carefully", "Cite inspected work", "implemented", "Record limitations, verify sources when possible, and do not present an idea as a project result."),
            card("Prefer coherent slices", "Small parity gates", "implemented", "Migrate one compiler subsystem at a time and retain the bootstrap oracle until acceptance criteria pass.")
        ])
    ]);
    return page("community.html", "Community", "A public project that grows by verified increments.", "Community and contributing", "Join the language, compiler, AI, graphics and tooling work without overstating what exists today.", [participation, participate]);
}

fn site_pages(hello_source: String, tour_source: String, xor_source: String, tensor_source: String, aurora_source: String, motion_source: String) -> List<Page> {
    return [
        home_page(hello_source),
        language_page(hello_source, tour_source),
        compiler_page(),
        ai_engine_page(xor_source, tensor_source),
        frontend_page(aurora_source, motion_source),
        docs_page(hello_source),
        examples_page(hello_source, xor_source, tensor_source, aurora_source),
        research_page(),
        roadmap_page(),
        security_page(),
        download_page(hello_source),
        community_page()
    ];
}

fn stylesheet() -> String {
    let rules: List<String> = [
        ":root { color-scheme: dark; --bg: #080d18; --surface: #101827; --surface-2: #151f31; --ink: #edf3ff; --muted: #b5c1d5; --line: #2a3850; --teal: #72e4d2; --blue: #9ac8ff; --violet: #c2a2ff; --green: #8de7b7; --amber: #ffd48a; --red: #ff9eaa; --radius: 20px; font-family: Inter, ui-sans-serif, system-ui, sans-serif; }",
        "* { box-sizing: border-box; } html { scroll-behavior: smooth; background: var(--bg); } body { margin: 0; color: var(--ink); background: radial-gradient(ellipse at 12% -10%, #12445166, transparent 38rem), radial-gradient(ellipse at 92% 8%, #34236b55, transparent 34rem), var(--bg); font: 16px/1.65 Inter, ui-sans-serif, system-ui, sans-serif; min-height: 100vh; }",
        "a { color: var(--blue); text-decoration-thickness: .08em; text-underline-offset: .2em; } a:hover { color: var(--teal); } a:focus-visible, summary:focus-visible { outline: 3px solid var(--amber); outline-offset: 4px; border-radius: 4px; }",
        ".skip-link { position: absolute; z-index: 20; top: 8px; left: 8px; padding: 10px 14px; transform: translateY(-160%); background: var(--ink); color: var(--bg); border-radius: 10px; } .skip-link:focus { transform: translateY(0); }",
        ".site-header { position: sticky; top: 0; z-index: 10; border-bottom: 1px solid #d7e6ff1c; background: #080d18e8; backdrop-filter: blur(16px); } .header-inner { max-width: 1280px; padding: 14px 28px; margin: auto; display: flex; align-items: center; justify-content: space-between; gap: 22px; }",
        ".brand { display: inline-flex; align-items: center; gap: 12px; min-width: 225px; color: var(--ink); text-decoration: none; } .brand-logo { width: 42px; height: 42px; border-radius: 14px; box-shadow: 0 0 24px #31c8b455; } .brand-copy { display: grid; line-height: 1.25; } .brand-copy strong { letter-spacing: .12em; font-size: .92rem; } .brand-copy span { color: var(--muted); font-size: .72rem; }",
        ".primary-nav { min-width: 0; } .nav-links { display: flex; flex-wrap: wrap; justify-content: flex-end; gap: 5px; } .nav-link { color: var(--muted); font-size: .8rem; padding: 7px 9px; border-radius: 10px; text-decoration: none; } .nav-link:hover, .nav-link.is-current { color: var(--ink); background: #ffffff12; } .nav-link.is-current { box-shadow: inset 0 -2px var(--teal); }",
        ".page-main { max-width: 1160px; margin: 0 auto; padding: 58px 28px 84px; } .page-heading { max-width: 850px; margin: 0 0 40px; } .eyebrow, .hero-kicker { color: var(--teal); text-transform: uppercase; font-size: .78rem; letter-spacing: .18em; font-weight: 750; } h1, h2, h3, p { margin-top: 0; } h1 { max-width: 900px; font-size: clamp(2.4rem, 5.7vw, 5rem); line-height: 1.02; letter-spacing: -.055em; margin-bottom: 20px; } h2 { font-size: clamp(1.55rem, 3vw, 2.25rem); line-height: 1.15; letter-spacing: -.035em; margin-bottom: 10px; } h3 { font-size: 1.12rem; line-height: 1.3; margin: 12px 0 8px; } .page-summary { max-width: 760px; color: var(--muted); font-size: 1.18rem; } .muted { color: var(--muted); }",
        ".content-stack { display: grid; gap: 28px; } .content-section { scroll-margin-top: 100px; } .section-heading { max-width: 790px; margin-bottom: 18px; } .section-heading p { color: var(--muted); } .section-content { display: grid; gap: 16px; } .card-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 14px; }",
        ".panel { min-width: 0; border: 1px solid #c7d8ef20; border-radius: var(--radius); background: linear-gradient(145deg, #17253aeb, #0d1523ed); box-shadow: 0 18px 50px #0003; } .feature-card { padding: 22px; } .feature-card p { margin-bottom: 0; } .status { display: inline-flex; align-items: center; gap: 7px; width: fit-content; border: 1px solid currentColor; border-radius: 999px; padding: 3px 10px; font-size: .72rem; line-height: 1.5; font-weight: 750; letter-spacing: .025em; } .status::before { content: ''; width: 6px; height: 6px; border-radius: 50%; background: currentColor; } .status--implemented { color: var(--green); } .status--partial { color: var(--amber); } .status--experimental { color: var(--violet); } .status--planned { color: var(--blue); } .status--blocked { color: var(--red); }",
        ".hero-panel { position: relative; isolation: isolate; overflow: hidden; padding: clamp(26px, 5vw, 58px); border: 1px solid #74e5d544; border-radius: 30px; background: radial-gradient(ellipse at 100% 10%, #5e51bd48, transparent 48%), radial-gradient(ellipse at 0 100%, #0a7c8055, transparent 50%), linear-gradient(130deg, #132335f5, #0b1220f5); box-shadow: 0 32px 80px #0005; } .hero-panel::after { content: ''; position: absolute; z-index: -1; width: 240px; height: 240px; right: -60px; top: -80px; border: 1px solid #8df2e822; border-radius: 50%; box-shadow: 0 0 0 22px #8df2e80a, 0 0 0 44px #8df2e805; } .hero-panel > .status { margin-bottom: 22px; } .hero-kicker { margin-bottom: 10px; } .hero-copy { max-width: 760px; color: #d5e2f4; font-size: clamp(1.1rem, 2vw, 1.4rem); } .hero-note { max-width: 780px; color: var(--muted); font-size: .9rem; margin: 22px 0 0; } .hero-actions { display: flex; flex-wrap: wrap; gap: 10px; margin-top: 24px; }",
        ".button { display: inline-flex; align-items: center; justify-content: center; min-height: 44px; padding: 10px 16px; border: 1px solid #c5d8ee44; border-radius: 12px; font-weight: 700; text-decoration: none; transition: transform .18s ease, border-color .18s ease, background .18s ease; } .button:hover { transform: translateY(-2px); border-color: var(--teal); } .button-primary { color: #051514; background: linear-gradient(100deg, #80ebd9, #a2d4ff); border-color: transparent; } .button-primary:hover { color: #051514; background: linear-gradient(100deg, #a2d4ff, #c2a2ff); } .button-secondary { color: var(--ink); background: #ffffff0d; } .inline-link { display: inline-block; width: fit-content; font-weight: 700; }",
        ".code-panel { padding: 20px; overflow: hidden; } .code-title { margin: 0; } .copy-hint { color: var(--muted); font-size: .8rem; margin: 5px 0 12px; } .code-frame { overflow: auto; max-height: 34rem; margin: 0; padding: 17px; border: 1px solid #9fb6d322; border-radius: 14px; background: #060b13; color: #d9ebff; font: .84rem/1.7 ui-monospace, SFMono-Regular, Consolas, monospace; tab-size: 4; } .language-peacock { white-space: pre; } .callout { padding: 16px 18px; border-left: 3px solid var(--teal); border-radius: 0 12px 12px 0; color: #d4e3f5; background: #61dece0c; } .filter-links { display: flex; flex-wrap: wrap; gap: 9px; } .filter-chip { padding: 8px 13px; color: var(--teal); border: 1px solid #72e4d255; border-radius: 999px; text-decoration: none; } .filter-chip:hover { background: #72e4d21a; }",
        ".details-panel { padding: 17px 20px; } details summary { cursor: pointer; color: var(--ink); font-weight: 700; } details p { margin: 12px 0 0; } .site-footer { max-width: 1160px; margin: 0 auto; padding: 28px; border-top: 1px solid #d7e6ff20; display: flex; align-items: center; justify-content: space-between; gap: 22px; color: var(--muted); } .site-footer strong { color: var(--ink); letter-spacing: .1em; } .site-footer p { margin: 5px 0 0; font-size: .84rem; } .footer-links { display: flex; flex-wrap: wrap; gap: 17px; }",
        "@media (max-width: 1050px) { .header-inner { align-items: flex-start; flex-direction: column; gap: 10px; } .brand { min-width: 0; } .nav-links { justify-content: flex-start; } .nav-link { padding: 6px 8px; } }",
        "@media (max-width: 680px) { .header-inner { padding: 12px 16px; } .nav-links { flex-wrap: nowrap; overflow-x: auto; justify-content: flex-start; padding: 2px 1px 8px; scrollbar-width: thin; } .nav-link { flex: 0 0 auto; } .page-main { padding: 38px 17px 58px; } .card-grid { grid-template-columns: 1fr; } .hero-panel { border-radius: 22px; } .site-footer { padding: 23px 17px; align-items: flex-start; flex-direction: column; } .footer-links { gap: 13px; } h1 { font-size: clamp(2.25rem, 12vw, 3.5rem); } .code-frame { font-size: .76rem; } }",
        "@media (prefers-reduced-motion: reduce) { *, *::before, *::after { scroll-behavior: auto !important; animation-duration: .01ms !important; animation-iteration-count: 1 !important; transition-duration: .01ms !important; } }"
    ];
    return rules.join("\n");
}

fn renderer_self_test() -> Unit {
    assert(html_escape("<script>") == "&lt;script&gt;");
    assert(html_escape("A & B") == "A &amp; B");
    assert(html_escape("\"quoted\"") == "&quot;quoted&quot;");
}

fn main() -> Unit {
    capability fs;
    renderer_self_test();
    let args = process.args();
    let mut output_dir = "website/dist";
    if args.len() > 0 {
        output_dir = args.get(0);
    }
    fs.create_dir(output_dir);
    fs.create_dir(output_dir + "/assets");

    let hello_source = fs.read_text("examples/hello.pac");
    let tour_source = fs.read_text("examples/tour.pac");
    let xor_source = fs.read_text("examples/xor.pac");
    let tensor_source = fs.read_text("examples/tensors.pac");
    let aurora_source = fs.read_text("examples/aurora.pac");
    let motion_source = fs.read_text("examples/motion.pac");
    let logo_source = fs.read_text("assets/peacock.svg");
    let pages = site_pages(hello_source, tour_source, xor_source, tensor_source, aurora_source, motion_source);

    for item in pages {
        fs.write_text(output_dir + "/" + item.slug, render_page(item, pages));
    }
    fs.write_text(output_dir + "/styles.css", stylesheet());
    fs.write_text(output_dir + "/assets/peacock.svg", logo_source);
    print("Built 12 PEACOCK-authored pages in " + output_dir);
    print("Static export: semantic HTML + responsive CSS; no JavaScript bundle");
}
