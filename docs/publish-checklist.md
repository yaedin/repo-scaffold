# Publish checklist (functions 6 and 7)

`just publish-check` automates most of this. This document is the reasoning, for
the cases where you want to override it or the cases it cannot see.

Run it before making a repo public, and before putting its URL in an application.

## Governance (function 6)

- [ ] **`LICENSE` exists.** Without one the repo is legally all-rights-reserved:
      nobody may fork, extend, or build on it, whatever the README invites. MIT
      unless you have a reason. This is a five-minute fix that silently blocks
      everything downstream.
- [ ] **`CITATION.cff` filled in.** GitHub renders a "Cite this repository" button
      from it. No `REPLACE` markers left. Add ORCID if you have one.
- [ ] **`.env` is not tracked.** `publish-check` treats this as critical. Check
      history too, not just the working tree — `git log --all -- .env`.
- [ ] **Co-authors named** in `CITATION.cff` and the README byline, with their
      agreement.
- [ ] **Third-party material is not redistributed.** Reference PDFs stay out of
      the repo; so do full-text extractions of them, which are the same thing.
- [ ] **Nothing unsafe to release.** Raw generations from red-team work stay
      gitignored. If you release curated excerpts, generate them by script.
- [ ] **The repo is not carrying something huge.** `publish-check` prints the ten
      largest tracked blobs. A first push that hangs is nearly always a large file
      committed weeks ago, and by then removing it means rewriting history.

## Dissemination (function 7)

- [ ] **README leads with the claim,** not the setup. A reader decides in fifteen
      seconds; give them the result and how much to believe it.
- [ ] **A figure is embedded in the README.** Most readers will never clone. A repo
      with no visible evidence asks them to take the paper's word for it.
- [ ] **Figures are committed and regenerable** — `just figures` reproduces them.
- [ ] **Paper source is committed,** not only the PDF. A PDF you cannot regenerate
      is a paper you cannot amend, fork, or diff. `just paper` rebuilds it from the
      Markdown, so the PDF stays a build artifact.
- [ ] **Results table maps claim → evidence path.** Allows for easier replication
      of work that has been executed.
- [ ] **Known gaps section exists.** Unsourced numbers, specified-but-unrun
      experiments, missing controls.
- [ ] **`just check` passes** — no claim points at a file that does not exist.

## Optional, in rough order of value per hour

- [ ] **Link the sprint/workshop page** and any write-up, so the repo is findable
      from the work and vice versa.
- [ ] **A one-page landing site.** `docs/index.md` with GitHub Pages: headline
      figure, one-paragraph claim, links to paper/repo/data. Twenty minutes, and it
      is most of the value of a companion site. Build something interactive only if
      the result is genuinely explorable.
- [ ] **Dataset release** on HuggingFace for anything safe to publish, with a DOI.
- [ ] **Zenodo DOI** for the repo itself, giving an immutable citable URL.
- [ ] **arXiv** if the work stands on its own.
