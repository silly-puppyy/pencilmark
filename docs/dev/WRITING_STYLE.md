# Writing style

Rules for pencilmark's documentation. Each names its source. Code has its own page: [code style](CODE_STYLE.md).

## Get the reader to the answer

Most readers scan: in Nielsen Norman's tests 79% scanned a new page and 16% read it word by word
([NN/g](https://www.nngroup.com/articles/how-users-read-on-the-web/)).

1. **Answer first.** The first sentence of a page, section or paragraph says the thing; detail follows
   ([inverted pyramid](https://www.nngroup.com/articles/inverted-pyramid/)).
2. **One idea per paragraph, at most 4 sentences.** Five or six usually means two ideas
   ([Google](https://developers.google.com/style/paragraph-structure)).
3. **Short sentences.** Split a sentence that needs a second comma-clause to make sense.
4. **Headings that name the content**, in sentence case, no skipped levels; a section that runs past a screen gets
   subheadings ([Google](https://developers.google.com/style/headings)).
5. **Half the words.** Cut until removing more would lose information ([NN/g](https://www.nngroup.com/articles/how-users-read-on-the-web/)).
6. **One page, one job**: tutorial, how-to, reference or explanation, never mixed ([Diátaxis](https://diataxis.fr/start-here/)).
   The README routes; the philosophy page states aims; measurements go to the benchmark and the known issues.

## Plain words

Wikipedia's editors list the habits that make text read as machine-written
([Signs of AI writing](https://en.wikipedia.org/wiki/Wikipedia:Signs_of_AI_writing)). They are also just bad writing:

7. **Say "is" and "has"**, not "serves as", "boasts", "stands as".
8. **No inflated words**: pivotal, robust, seamless, comprehensive, crucial, leverage, delve, landscape.
9. **No contrast against a claim nobody made** ("not just X, but Y", "rather than X").
10. **Lists as long as the content**, not padded to three.
11. **Bold only what a scanner must not miss**, at most once per paragraph. No emoji, no "Label: text" bullets by default.
12. **No closing summaries, no hedging filler** ("it is worth noting", "in summary").
13. **The same word for the same thing every time**; terms are defined once in the glossary
    ([Google](https://developers.google.com/style/word-list)).
14. **Active voice, present tense, "you"** ([Google](https://developers.google.com/style/voice)). Full names ("Andrew
    Stuart"); British spelling; no "e.g." / "i.e.".

## Tables, figures, examples

15. **A table needs rows and columns that both mean something.** Two columns of label and value is a list. Long text
    goes under the table or in a collapsible row, not in a cell.
16. **Figures are optional and collapsible**: every figure has alt text, the same facts are in the text, colours pass
    WCAG contrast (4.5:1 text, 3:1 graphics) and are never the only distinction ([WCAG 2.2](https://www.w3.org/TR/WCAG22/)).
17. **Formulas in KaTeX**, each followed by one line saying what the symbols are
    ([Docusaurus math](https://docusaurus.io/docs/markdown-features/math-equations)).
18. **Every example runs**: Python examples are tested, JSON examples validate against their schema, the build fails on
    a broken link ([Docusaurus config](https://docusaurus.io/docs/api/docusaurus-config)).
19. **Minimal samples**; command and output in separate blocks ([Google](https://developers.google.com/style/code-samples)).
20. **Link text names the target**, never "here" ([Google](https://developers.google.com/style/link-text)).

## Project files

21. **CHANGELOG** in the [Keep a Changelog](https://keepachangelog.com/) spirit; [semantic versions](https://semver.org/);
    a change to any card value is a minor version with a changelog line; format changes bump `format_version`.
22. **Formats stay simple**: remove a field rather than deprecate it until someone relies on it.
23. **Commits**: imperative subject, a body that says why, no generated attribution lines.
