# PEACOCK 0.4 idioms and common mistakes

Valid patterns:

```peacock
कार्य मुख्य() -> एकक {
    स्थापय परिवर्तनीय योग = ०;
    प्रति अङ्क मध्ये ०..५ { योग += अङ्क; }       // half-open range
    स्थापय मूल्यानि: सूची<पूर्णाङ्क> = [];       // empty list needs annotation
    मूल्यानि.योजय(योग);
    यदि मूल्यानि.अन्तर्भूत(१०) { मुद्रय("दश"); }
}
```

```peacock
कार्य विभाजय(अ: पूर्णाङ्क, ब: पूर्णाङ्क) -> पूर्णाङ्क {
    यदि ब == ० { क्षिप "शून्येन विभाजनम्"; }
    प्रत्यानय अ / ब;
}
```

```peacock
उपयोग सञ्चय
उपयोग पाठ्य
कार्य मुख्य() -> एकक {
    अधिकार सञ्चय;
    स्थापय पाठ = सञ्चय.पाठ्यपठन("input.txt");
    प्रति पङ्क्ति मध्ये पाठ्य.पङ्क्तिविभाजन(पाठ) { मुद्रय(पङ्क्ति); }
}
```

```peacock
उपयोग सञ्चय
कार्य मुख्य() -> एकक {
    अधिकार सञ्चय;
    सञ्चय.निधिरचना("out/reports");
    सञ्चय.पाठ्यलेखन("out/reports/status.txt", "सिद्धम्");
}
```

`सञ्चय.निधिरचना` is sandbox-rooted and still requires both the source declaration
and host `--grant सञ्चय`; see [capabilities](../security/capabilities.md).

```peacock
उपयोग रङ्ग
उपयोग चित्र
कार्य मुख्य() -> एकक {
    अधिकार दृश्य;
    स्थापय पट्ट = चित्र.चित्रपट्ट(३२०, १८०);
    स्थापय वर्णसूची = [रङ्ग.ओकएलसीएच(०.२, ०.०५, २५०.०), रङ्ग.ओकएलसीएच(०.६, ०.१५, ६०.०)];
    चित्र.वर्णक्रम(पट्ट, वर्णसूची, ३०.०);
    चित्र.प्रदर्शय(पट्ट);                 // host decides where the frame goes
}
```

Common mistakes and diagnostics:

| Mistake | Diagnostic |
|---|---|
| `१ + २.०` | PE3003; use `दशमलवीकरण(१) + २.०` |
| `स्थापय क्ष = १; क्ष = २;` | PE3007; declare `स्थापय परिवर्तनीय क्ष` |
| `मूल्यानि = []` without annotation | PE3003 |
| named argument before a positional one | PE2033 |
| chained comparison `अ < ब < च` | PE2031 |
| calling `अज्ञात.चित्रपट्ट` | PE3006; unknown namespace |
| `सञ्चय.पाठ्यपठन` without `अधिकार सञ्चय;` | PE3005 |
| `सञ्चय.पाठ्यपठन` declared but host did not grant | PE4001 |
| integer overflow | PE4004 |
| out-of-bounds list access | PE4002 (catchable) |
| `विह्वल` inside `यत्न` | PE4011; not catchable |
| `चित्र.प्रदर्शय` without `अधिकार दृश्य;` | PE3005 |
| `चित्र.प्रदर्शय` declared but no host backend | PE4006 (host configuration) |

Formatting: four spaces, one statement per line, braces on the same line,
trailing commas allowed in structs and lists. The source extension is `.सूत्र`.
Identifiers are Unicode; ASCII user identifiers remain possible, but the reserved
language and standard-library vocabulary is Sanskrit.
