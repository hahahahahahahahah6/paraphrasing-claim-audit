# Documentation claim auditor

An offline, deterministic, standard-library-only auditor for sentence restatement claims in repository documentation. Requires Python 3.9 or later. No network, telemetry, model execution, or file writes.

## Install and use

```sh
python3 -m pip install paraphrasing-claim-audit
paraphrasing-claim-audit audit .
python3 -m paraphrasing_claim_audit audit . --json
paraphrasing-claim-audit audit . --verbose --ignore vendor/ --ignore generated/ --fail-on medium
paraphrasing-claim-audit --version
```

The repository defaults to the current directory. Root documentation and Markdown files below the documentation directory are checked. Fenced code blocks are excluded; inline code remains prose. Python sources throughout the repository provide evidence, except Git metadata, bytecode caches, and virtual environments. Each evidence route must be complete in one module. Imported aliases and chained calls are supported; local function and class definitions shadow imported route names.

```text
README.md
docs/**/*.md
documented-paraphrasing-claim-false
documented-no-paraphrasing-claim-false
```

Unsupported positive claims receive HIGH severity. A denial contradicted by source evidence also receives HIGH severity. A denial without source evidence passes. Positive claims in test fixtures receive MEDIUM severity. No claims, or positive claims backed by evidence, pass.

Exit status is 0 when no finding reaches the selected threshold, 2 when one does, and 1 for usage or input errors. The default threshold is high; medium includes both severities. Repeated ignore options skip relative paths starting with each supplied prefix. Verbose decisions go to standard error. JSON output is an array of findings, each containing verdict, message, severity, and path fields; an empty array means no findings.

## Evidence

The checked feature is recognized through a named checkpoint loaded into a supported sequence model and used for generation; a matching text generation pipeline used in a call; embedding pair mining; a back-translation augmenter used for augmentation; or one of the exact generic method names used in a call. Bare imports, unrelated language tasks, string literals, comments, uncalled references, external commands, and incomplete pairs do not qualify.

```text
transformers.AutoModelForSeq2SeqLM
transformers.PegasusForConditionalGeneration
transformers.T5ForConditionalGeneration
transformers.pipeline("text2text-generation", model="...paraphrase...")
sentence_transformers.util.paraphrase_mining
nlpaug.augmenter.word.BackTranslationAug
```

## Differentiation

These neighboring tools cover passage condensing, cross-language rendering, salient-term harvesting, latent theme discovery, and speech synthesis, respectively. This auditor covers same-language sentence restatement, a separate capability from each of those tasks.

```text
summarization-claim-audit
translation-claim-audit
keyword-extraction-claim-audit
topic-modeling-claim-audit
text-to-speech-claim-audit
```

## Limitations

Static patterns establish evidence, not semantic correctness. Phrase matching uses case-insensitive exact substrings, with no stemming, fuzzy matching, or hyphen normalization. Denial spans are removed first. Longest-first matching blanks each matched span, so each occurrence matches once under its longest phrase, even when shorter words occur inside longer forms.

Generic calls can overreach: a shared method name on an unrelated object still counts as evidence. The following call illustrates that limitation.

```python
unrelated.paraphrase()
```

Embedding pair mining finds restated sentence pairs rather than generating restated sentences. It counts as related evidence by design.

```text
paraphrase_mining
```

Checkpoint identifiers containing the following substring are trusted on name alone, without downloading or inspecting weights. Dynamic imports, runtime rebinding, and cross-module data flow are outside this static check. Invalid Python modules provide no evidence. Findings report matched phrases and paths, not line positions.

```text
paraphrase
```

## Development

```sh
python3 -m unittest discover
python3 -m build
```

MIT licensed.
